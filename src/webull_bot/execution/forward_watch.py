"""Five-second sandbox watch for the VWAP books and QQQ Trapdoor.

Exit checks run every five seconds and do not wait on a bar download.
Three seconds after each five-minute close, one short tail of new bars
is merged into the cache and every book reads that same cache. A download
that runs long is abandoned so the entry check still starts. The old full
history reload is not on this loop.

Documented OpenAPI market-data limits, checked 2026-10-09
(https://developer.webull.com/apis/docs/rate-limits), per endpoint and
per app key. Stock snapshot ``GET /market-data/stocks/snapshots/list``
and option snapshot ``GET /market-data/options/snapshots/list`` are
30 requests / 60s in sandbox and 60 / 60s in production. Option depth
on the stock endpoint is not a supported category.
This process stays at or under 15 requests / 60s on each snapshot
endpoint, half the sandbox cap. One call passes every symbol for that
category. A 429 backs off with jitter and does not retry in a loop.
Stop and target checks run before a new quote fetch and before a new
entry. Option-chain lookups share one result across books for a minute
and sit on the same budget. A quote failure does not change an open
position and does not block the bar-based exit.

The file lock ``data/forward/cycle.lock`` is shared with ``forward-test``.
The two never send orders at the same time.
"""

from __future__ import annotations

import csv
import fcntl
import logging
import random
import re
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterator, Optional
from zoneinfo import ZoneInfo

import pandas as pd

NY = ZoneInfo("America/New_York")
# Half the sandbox snapshot cap (30/60s). Production is 60/60s.
REQUESTS_PER_MINUTE = 15
WINDOW_SECONDS = 60.0
BACKOFF_SECONDS = (15.0, 30.0, 60.0)
BAR_LAG = timedelta(seconds=3)
TICK_SECONDS = 5.0
# A bar-close entry check should start inside this window. The alert is the
# longer stall: a cycle that is still running after a minute.
ENTRY_TARGET_S = 30.0
SLOW_CYCLE_S = 60.0
BAR_REFRESH_TIMEOUT_S = 20.0
TAIL_DAYS = 3

LATEST: dict = {}
_REFRESH_THREAD: Optional[threading.Thread] = None


class BudgetExceeded(RuntimeError):
    """The local cap was reached. The request was not sent."""


class EndpointBudget:
    """Rolling cap plus a 429 backoff. One counter per endpoint."""

    def __init__(self, cap: int = REQUESTS_PER_MINUTE, window: float = WINDOW_SECONDS) -> None:
        self.cap = int(cap)
        self.window = float(window)
        self.stamps: dict[str, list[float]] = {}
        self.blocked_until: dict[str, float] = {}
        self.strikes: dict[str, int] = {}

    def cooling(self, endpoint: str, now: Optional[float] = None) -> bool:
        clock = time.monotonic() if now is None else float(now)
        return clock < float(self.blocked_until.get(endpoint) or 0.0)

    def gate(self, endpoint: str, now: Optional[float] = None) -> None:
        clock = time.monotonic() if now is None else float(now)
        if self.cooling(endpoint, clock):
            raise BudgetExceeded(endpoint)
        stamps = [item for item in self.stamps.get(endpoint, []) if clock - item < self.window]
        if len(stamps) >= self.cap:
            self.stamps[endpoint] = stamps
            raise BudgetExceeded(endpoint)
        stamps.append(clock)
        self.stamps[endpoint] = stamps

    def penalize(self, endpoint: str, now: Optional[float] = None) -> float:
        clock = time.monotonic() if now is None else float(now)
        strike = int(self.strikes.get(endpoint) or 0)
        base = BACKOFF_SECONDS[min(strike, len(BACKOFF_SECONDS) - 1)]
        delay = base + random.uniform(0.0, base * 0.25)
        self.strikes[endpoint] = strike + 1
        self.blocked_until[endpoint] = clock + delay
        self.stamps[endpoint] = []
        return delay

    def clear_strike(self, endpoint: str) -> None:
        self.strikes[endpoint] = 0


def rate_limited(exc: BaseException) -> bool:
    code = getattr(exc, "status_code", None)
    if code is None:
        code = getattr(exc, "http_status_code", None)
    if code == 429:
        return True
    text = str(exc)
    return "429" in text or "Too Many Requests" in text


@contextmanager
def cycle_lock(block_seconds: float = 0.0, path: Optional[Path] = None) -> Iterator[bool]:
    """Exclusive lock. Yields False when the other cycle still holds it."""
    target = Path(path) if path is not None else Path("data/forward/cycle.lock")
    target.parent.mkdir(parents=True, exist_ok=True)
    handle = target.open("a+")
    start = time.monotonic()
    acquired = False
    try:
        while True:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
                break
            except BlockingIOError:
                if time.monotonic() - start >= float(block_seconds):
                    break
                time.sleep(0.05)
        yield acquired
    finally:
        if acquired:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def boundary_of(moment: datetime) -> datetime:
    local = moment.astimezone(NY)
    minute = (local.minute // 5) * 5
    return local.replace(minute=minute, second=0, microsecond=0)


def full_cycle_due(moment: datetime, last: Optional[datetime]) -> bool:
    """True once the clock is at least three seconds past a five-minute close."""
    local = moment.astimezone(NY)
    boundary = boundary_of(local)
    if local < boundary + BAR_LAG:
        return False
    if last is not None and boundary_of(last.astimezone(NY)) == boundary:
        return False
    return True


def next_wake(moment: datetime) -> float:
    """Seconds until the next five-second mark or the next bar-close-plus-three."""
    local = moment.astimezone(NY)
    boundary = boundary_of(local)
    upcoming = boundary + BAR_LAG
    if upcoming <= local:
        upcoming = boundary + timedelta(minutes=5) + BAR_LAG
    bar_wait = (upcoming - local).total_seconds()
    return max(0.2, min(TICK_SECONDS, bar_wait))


def remember_frames(bars15, bars5, points, closes) -> None:
    LATEST["bars15"] = bars15 or {}
    LATEST["bars5"] = bars5 or {}
    LATEST["points"] = points or {}
    LATEST["closes"] = closes or {}


def timing_lines(exits_s: float, bars_s: float, entries_s: float) -> list[str]:
    """One timing line, and an alert when the cycle is over a minute."""
    total = float(exits_s) + float(bars_s) + float(entries_s)
    lines = [
        (
            f"Cycle timing: exits {float(exits_s):.2f}s, bars {float(bars_s):.2f}s, "
            f"entries {float(entries_s):.2f}s, total {total:.2f}s."
        )
    ]
    if total > SLOW_CYCLE_S:
        lines.append(f"Cycle alert: the watch cycle took {total:.1f}s, over {SLOW_CYCLE_S:.0f}s.")
    return lines


def entry_lag_line(started_s: float, close: datetime) -> list[str]:
    """How long after the bar close the entry pass began."""
    stamp = close.astimezone(NY).strftime("%H:%M")
    lines = [
        (
            f"Entry check started {float(started_s):.1f}s after the {stamp} ET bar close. "
            "Books share one bar cache."
        )
    ]
    if float(started_s) > ENTRY_TARGET_S:
        lines.append(
            f"Cycle alert: entries started {float(started_s):.1f}s after the bar close, "
            f"past {ENTRY_TARGET_S:.0f}s."
        )
    return lines


class _SdkOneLine(logging.Filter):
    """One short line for an SDK error, then silence the same line for a minute.

    The SDK logs the whole request on HTTP 417 and 429. That dump can carry
    the signed request. This filter keeps the status and drops the body.
    """

    def __init__(self) -> None:
        super().__init__()
        self._last = ""
        self._last_at = 0.0

    def filter(self, record: logging.LogRecord) -> bool:
        if record.levelno < logging.ERROR:
            return True
        text = record.getMessage()
        short = _sdk_line(text)
        now = time.monotonic()
        if short == self._last and now - self._last_at < 60.0:
            return False
        self._last = short
        self._last_at = now
        record.msg = short
        record.args = ()
        return True


def _sdk_line(text: str) -> str:
    if "UNSUPPORTED_CATEGORY" in text or re.search(r"\b417\b", text):
        return "Webull market data rejected the category (HTTP 417). The request was not logged."
    if "Too Many Requests" in text or re.search(r"\b429\b", text):
        return "Webull market data rate limit (HTTP 429). The request was not logged."
    match = re.search(r"\b([45]\d\d)\b", text)
    if match:
        return f"Webull market data error (HTTP {match.group(1)}). The request was not logged."
    return "Webull market data error. The request was not logged."


def quiet_sdk_errors() -> None:
    """Attach the one-line filter to the SDK client logger. Safe to call twice."""
    log = logging.getLogger("webull.core.client")
    if any(isinstance(item, _SdkOneLine) for item in log.filters):
        return
    log.addFilter(_SdkOneLine())


def guard_market_data(broker, budget: Optional[EndpointBudget] = None) -> EndpointBudget:
    """Count snapshot and bar calls, and back off on HTTP 429."""
    quiet_sdk_errors()
    book = budget or getattr(broker, "_watch_budget", None) or EndpointBudget()
    broker._watch_budget = book
    client = getattr(broker, "_data", None)
    if client is None or getattr(client, "_watch_guard", False):
        return book
    _wrap(client, "market_data", "get_snapshot", "stock_snapshot", book)
    _wrap(client, "market_data", "get_batch_history_bar", "stock_bars", book)
    _wrap(client, "option_market_data", "get_option_snapshot", "option_snapshot", book)
    _wrap(client, "instrument", "list_option_contracts", "option_chain", book)
    client._watch_guard = True
    return book


def _wrap(client, group: str, method: str, endpoint: str, budget: EndpointBudget) -> None:
    holder = getattr(client, group, None)
    real = getattr(holder, method, None) if holder is not None else None
    if holder is None or real is None or getattr(real, "_watch_wrapped", False):
        return

    def wrapped(*args, **kwargs):
        try:
            budget.gate(endpoint)
        except BudgetExceeded:
            raise
        try:
            result = real(*args, **kwargs)
        except Exception as exc:
            if rate_limited(exc):
                budget.penalize(endpoint)
            raise
        budget.clear_strike(endpoint)
        return result

    wrapped._watch_wrapped = True
    setattr(holder, method, wrapped)


class _LivePrice:
    """Broker view whose underlying quote is the snapshot from this tick."""

    def __init__(self, inner, prices: dict[str, float]) -> None:
        self._inner = inner
        self._prices = dict(prices)

    def underlying_quote(self, symbol: str):
        value = self._prices.get(symbol)
        if value is None:
            raise RuntimeError("no snapshot")
        return value

    def __getattr__(self, name):
        return getattr(self._inner, name)


def snapshot_prices(broker, symbols: list[str], budget: EndpointBudget) -> dict[str, float]:
    """One batched stock snapshot. A failure returns no prices and changes nothing."""
    client = getattr(broker, "_data", None)
    market = getattr(client, "market_data", None) if client is not None else None
    if market is None or not symbols:
        return {}
    try:
        payload = market.get_snapshot(list(symbols), "US_ETF")
    except BudgetExceeded:
        return {}
    except Exception:
        return {}
    return _prices(payload)


def option_snapshot(broker, symbols: list[str]) -> dict[str, dict]:
    """One batched option snapshot. A failure returns nothing."""
    client = getattr(broker, "_data", None)
    market = getattr(client, "option_market_data", None) if client is not None else None
    if market is None or not symbols:
        return {}
    try:
        payload = market.get_option_snapshot(list(symbols), "US_OPTION")
    except Exception:
        return {}
    return _option_rows(payload)


def fast_tick(
    journal,
    broker,
    now: datetime,
    prices: dict[str, float],
    names: list[str],
    *,
    do_exits: bool = True,
    do_entries: bool = True,
) -> list[str]:
    """Exits and pending entries for the cached bars. Quote failures stay local.

    Exits do not wait on a quote refresh. Entries still run when the option
    endpoints are cooling; only the new quote fetch waits.
    """
    from webull_bot.calendar import to_ny
    from webull_bot.execution.forward_four_hour import NAME as HOUR_NAME
    from webull_bot.execution.forward_quotes import prime_forward_quotes
    from webull_bot.execution.forward_trapdoor import NAME as TRAP_NAME
    from webull_bot.execution.forward_vwap import BOOKS

    lines: list[str] = []
    view = _LivePrice(broker, prices)
    local = to_ny(now)
    bars15 = LATEST.get("bars15") or {}
    bars5 = LATEST.get("bars5") or {}
    points = LATEST.get("points") or {}
    closes = LATEST.get("closes") or {}
    minute_key = local.strftime("%Y-%m-%d %H:%M")
    log_minute = LATEST.get("minute") != minute_key
    specs = [(name, BOOKS[name], _frame(bars5, BOOKS[name])) for name in names if name in BOOKS]
    if TRAP_NAME in names:
        specs.append((TRAP_NAME, "QQQ", _frame(bars5, "QQQ")))
    if HOUR_NAME in names:
        specs.append((HOUR_NAME, "QQQ", _frame(bars5, "QQQ")))
    budget = getattr(broker, "_watch_budget", None)
    cooling = False
    if budget is not None and (
        budget.cooling("stock_snapshot")
        or budget.cooling("option_snapshot")
        or budget.cooling("option_chain")
    ):
        cooling = True
        lines.append(
            "Rate limit backoff. Stop and target checks still run. "
            "New quotes wait. Entry checks still run on the cached bars."
        )
    if log_minute and do_exits:
        lines.append("Watching " + ", ".join(names) + ".")
    # Stops and targets first. Quote fetches for new entries come after.
    if do_exits:
        _visit_books(
            names,
            journal,
            broker,
            now,
            view,
            lines,
            local,
            bars15,
            bars5,
            points,
            closes,
            prices,
            log_minute,
            entries=False,
        )
    if do_entries:
        if not cooling:
            try:
                prime_forward_quotes(journal, broker, specs, now, include_ladder=log_minute)
            except Exception:
                lines.append("Option snapshot was not taken. Open positions were not changed.")
        _visit_books(
            names,
            journal,
            broker,
            now,
            view,
            lines,
            local,
            bars15,
            bars5,
            points,
            closes,
            prices,
            log_minute,
            entries=True,
        )
    if log_minute and do_entries:
        LATEST["minute"] = minute_key
    if do_exits and do_entries and not lines:
        lines.append("Fast tick. No stop, target, or pending entry.")
    return lines


def _visit_books(
    names,
    journal,
    broker,
    now,
    view,
    lines,
    local,
    bars15,
    bars5,
    points,
    closes,
    prices,
    log_minute: bool,
    entries: bool,
) -> None:
    """Exits on the first pass. New entries only after the shared quote fetch."""
    from webull_bot.execution.forward_cash import prepare_cash
    from webull_bot.execution.forward_four_hour import NAME as HOUR_NAME
    from webull_bot.execution.forward_four_hour import STAKE as HOUR_STAKE
    from webull_bot.execution.forward_four_hour import _log_market as hour_log
    from webull_bot.execution.forward_four_hour import _manage_open as hour_manage
    from webull_bot.execution.forward_four_hour import _take_signals as hour_take
    from webull_bot.execution.forward_four_hour import load_state as hour_load
    from webull_bot.execution.forward_trapdoor import NAME as TRAP_NAME
    from webull_bot.execution.forward_trapdoor import STAKE as TRAP_STAKE
    from webull_bot.execution.forward_trapdoor import _log_market as trap_log
    from webull_bot.execution.forward_trapdoor import _manage_open as trap_manage
    from webull_bot.execution.forward_trapdoor import _take_signals as trap_take
    from webull_bot.execution.forward_trapdoor import load_state as trap_load
    from webull_bot.execution.forward_vwap import BOOKS, _ACTIVE, _activate, load_state
    from webull_bot.execution.forward_vwap import _log_market, _manage_open, _stake, _take_signals

    for name in names:
        if name not in BOOKS:
            continue
        symbol = BOOKS[name]
        token = _activate(name)
        try:
            state = load_state(journal)
            if prepare_cash(state, broker, _stake(), local.date()):
                journal.forward_save(name, state)
            if not entries:
                from webull_bot.execution.forward_reconcile import chase_exit_orders

                if chase_exit_orders(state, broker, now, lines):
                    journal.forward_save(name, state)
                try:
                    _manage_open(state, _frame(bars5, symbol), now, view, lines, journal)
                except Exception:
                    lines.append(f"{name} exit check failed. The position was not changed.")
                _write_ticks(name, symbol, state, prices.get(symbol), broker, now)
            else:
                try:
                    _take_signals(
                        state, _frame(bars15, symbol), _frame(bars5, symbol), now, points, closes, view, lines, journal
                    )
                except Exception:
                    lines.append(f"{name} entry check failed. No order was sent for that failure.")
                if log_minute:
                    try:
                        _log_market(state, _frame(bars5, symbol), now, broker, lines, journal, save=True)
                    except Exception:
                        lines.append(f"{name} minute quote log failed. Entry and exit were not changed.")
            if prepare_cash(state, broker, _stake(), local.date()):
                journal.forward_save(name, state)
        finally:
            _ACTIVE.reset(token)
    if TRAP_NAME in names:
        state = trap_load(journal)
        if prepare_cash(state, broker, TRAP_STAKE, local.date()):
            journal.forward_save(TRAP_NAME, state)
        if not entries:
            from webull_bot.execution.forward_reconcile import chase_exit_orders as chase_trap_exits

            if chase_trap_exits(state, broker, now, lines):
                journal.forward_save(TRAP_NAME, state)
            try:
                trap_manage(state, _frame(bars5, "QQQ"), now, view, lines, journal)
            except Exception:
                lines.append("QQQ Trapdoor exit check failed. The position was not changed.")
            _write_ticks(TRAP_NAME, "QQQ", state, prices.get("QQQ"), broker, now)
        else:
            try:
                trap_take(state, _frame(bars5, "QQQ"), now, points, closes, view, lines, journal)
            except Exception:
                lines.append("QQQ Trapdoor entry check failed. No order was sent for that failure.")
            if log_minute:
                try:
                    trap_log(state, _frame(bars5, "QQQ"), now, broker, lines, journal, save=True)
                except Exception:
                    lines.append("QQQ Trapdoor minute quote log failed. Entry and exit were not changed.")
        if prepare_cash(state, broker, TRAP_STAKE, local.date()):
            journal.forward_save(TRAP_NAME, state)
    if HOUR_NAME in names:
        state = hour_load(journal)
        if prepare_cash(state, broker, HOUR_STAKE, local.date()):
            journal.forward_save(HOUR_NAME, state)
        if not entries:
            from webull_bot.execution.forward_reconcile import chase_exit_orders as chase_hour_exits

            if chase_hour_exits(state, broker, now, lines):
                journal.forward_save(HOUR_NAME, state)
            try:
                hour_manage(state, _frame(bars5, "QQQ"), now, view, lines, journal)
            except Exception:
                lines.append("4hr exit check failed. The position was not changed.")
            _write_ticks(HOUR_NAME, "QQQ", state, prices.get("QQQ"), broker, now)
        else:
            try:
                hour_take(state, _frame(bars5, "QQQ"), now, points, closes, view, lines, journal)
            except Exception:
                lines.append("4hr entry check failed. No order was sent for that failure.")
            if log_minute:
                try:
                    hour_log(state, _frame(bars5, "QQQ"), now, broker, lines, journal, save=True)
                except Exception:
                    lines.append("4hr minute quote log failed. Entry and exit were not changed.")
        if prepare_cash(state, broker, HOUR_STAKE, local.date()):
            journal.forward_save(HOUR_NAME, state)


def _frame(book, symbol: str) -> pd.DataFrame:
    frame = book.get(symbol) if isinstance(book, dict) else None
    if frame is None:
        return pd.DataFrame()
    return frame


def _write_ticks(book: str, symbol: str, state: dict, underlying, broker, now: datetime) -> None:
    from webull_bot.execution.forward_quotes import cached_option

    positions = [row for row in (state.get("positions") or []) if isinstance(row, dict)]
    if not positions:
        return
    quotes = {str(row.get("option_symbol") or ""): cached_option(str(row.get("option_symbol") or "")) for row in positions}
    folder = Path("data/forward")
    try:
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"ticks_{book}_{now.astimezone(NY).strftime('%Y%m%d')}.csv"
        new_file = not path.exists()
        with path.open("a", newline="") as handle:
            fields = ["timestamp", "book", "symbol", "underlying", "option_symbol", "bid", "ask", "bid_size", "ask_size"]
            writer = csv.DictWriter(handle, fieldnames=fields)
            if new_file:
                writer.writeheader()
            for row in positions:
                contract = str(row.get("option_symbol") or "")
                quote = quotes.get(contract) or {}
                writer.writerow(
                    {
                        "timestamp": now.astimezone(NY).isoformat(),
                        "book": book,
                        "symbol": symbol,
                        "underlying": "" if underlying is None else f"{float(underlying):.4f}",
                        "option_symbol": contract,
                        "bid": _cell(quote.get("bid")),
                        "ask": _cell(quote.get("ask")),
                        "bid_size": _cell(quote.get("bid_size")),
                        "ask_size": _cell(quote.get("ask_size")),
                    }
                )
    except Exception:
        return


def _prices(payload) -> dict[str, float]:
    rows = _as_rows(payload)
    found = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        symbol = str(row.get("symbol") or row.get("ticker") or "")
        price = _num(row, "price", "last", "last_price", "lastPrice", "close", "tradePrice", "p")
        quote = row.get("quote") if isinstance(row.get("quote"), dict) else None
        if price is None and quote is not None:
            price = _num(quote, "price", "last", "last_price", "p", "close")
        if symbol and price is not None and price > 0:
            found[symbol] = price
    return found


def _option_rows(payload) -> dict[str, dict]:
    found = {}
    for row in _as_rows(payload):
        if not isinstance(row, dict):
            continue
        symbol = str(row.get("symbol") or row.get("option_symbol") or row.get("instrument_id") or "")
        quote = row.get("quote") if isinstance(row.get("quote"), dict) else {}
        bid = _num(row, "bid", "bid_price", "bidPrice") 
        ask = _num(row, "ask", "ask_price", "askPrice")
        if bid is None:
            bid = _num(quote, "bid", "bid_price", "bp")
        if ask is None:
            ask = _num(quote, "ask", "ask_price", "ap")
        if not symbol:
            continue
        found[symbol] = {
            "bid": "" if bid is None else bid,
            "ask": "" if ask is None else ask,
            "bid_size": row.get("bid_size") or quote.get("bid_size") or "",
            "ask_size": row.get("ask_size") or quote.get("ask_size") or "",
        }
    return found


def _as_rows(payload) -> list:
    if isinstance(payload, dict) and hasattr(payload, "json"):
        try:
            payload = payload.json()
        except Exception:
            pass
    if hasattr(payload, "json") and not isinstance(payload, dict):
        try:
            payload = payload.json()
        except Exception:
            return []
    if isinstance(payload, dict):
        rows = payload.get("result") or payload.get("data") or [payload]
        if isinstance(rows, dict):
            return [rows]
        return list(rows) if isinstance(rows, list) else []
    if isinstance(payload, list):
        return payload
    return []


def _num(row: dict, *keys: str) -> Optional[float]:
    if not isinstance(row, dict):
        return None
    for key in keys:
        if key not in row or row[key] in (None, ""):
            continue
        try:
            value = float(row[key])
        except (TypeError, ValueError):
            continue
        if value == value:
            return value
    return None


def overlay_webull_bars(broker, bars15, bars5, symbols: list[str], five_symbols: list[str], start: str, end: str):
    """Use Webull bars when the call returns a frame. Keep Yahoo where it does not."""
    from webull_bot.data.webull_provider import WebullDataProvider

    if broker is None or getattr(broker, "_data", None) is None:
        return bars15, bars5
    try:
        provider = WebullDataProvider(broker)
        fresh15 = provider.history(symbols, start, end, "15m") if symbols else {}
        fresh5 = provider.history(five_symbols, start, end, "5m") if five_symbols else {}
    except Exception:
        return bars15, bars5
    return _prefer(bars15, fresh15), _prefer(bars5, fresh5)


def _prefer(fallback, fresh) -> dict:
    base = dict(fallback or {})
    for symbol, frame in (fresh or {}).items():
        if frame is not None and len(frame) > 0:
            base[symbol] = frame
    return base


def _cell(value) -> str:
    if value in (None, ""):
        return ""
    return str(value)


def run_watch(config, args, names: list[str]) -> int:
    """Long-running loop. ``--once`` performs a single tick and returns."""
    from webull_bot.execution.forward_vwap import in_forward_window

    quiet_sdk_errors()

    once = bool(getattr(args, "once", False))
    dry_run = bool(getattr(args, "dry_run", False))
    while True:
        now = _watch_now(args) if once and getattr(args, "now", None) else _clock()
        if not in_forward_window(now):
            print(
                f"forward-watch idle at {now.astimezone(NY).isoformat()}. "
                "Outside the 09:50-15:50 ET window. No orders."
            )
            if once:
                return 0
            time.sleep(min(30.0, next_wake(now)))
            continue
        if dry_run and not full_cycle_due(now, LATEST.get("full")):
            print(
                f"forward-watch fast tick at {now.astimezone(NY).isoformat()}. "
                "Dry run: no snapshots, no orders, journal not written."
            )
            if once:
                return 0
            time.sleep(next_wake(_clock()))
            continue
        lines = watch_cycle(config, args, names, now, dry_run)
        print("\n".join(lines))
        if once:
            return 0
        time.sleep(next_wake(_clock()))


def watch_cycle(config, args, names: list[str], now: datetime, dry_run: bool) -> list[str]:
    """Exits, then a shared bar refresh when a close is due, then entries.

    The entry pass does not wait on a full history reload. Live trading
    stays off. A dry run does not connect.
    """
    if dry_run:
        return _dry_cycle(config, names, now)
    return _live_cycle(config, names, now)


def _finish_cycle(exit_lines, bar_lines, entry_lines, exits_s, bars_s, entries_s, refresh_due, now) -> list[str]:
    lines = list(exit_lines) + list(bar_lines) + list(entry_lines)
    lines.extend(timing_lines(exits_s, bars_s, entries_s))
    if refresh_due:
        lines.extend(entry_lag_line(exits_s + bars_s, boundary_of(now)))
    return lines


def _dry_cycle(config, names: list[str], now: datetime) -> list[str]:
    refresh_due = full_cycle_due(now, LATEST.get("full")) or not LATEST.get("bars5")
    started = time.monotonic()
    exits_s = time.monotonic() - started
    bar_started = time.monotonic()
    bar_lines: list[str] = []
    if refresh_due:
        bar_lines = refresh_closed_bars(config, now, names, None)
        LATEST["full"] = boundary_of(now)
    bars_s = time.monotonic() - bar_started
    entry_started = time.monotonic()
    entry_lines = dry_entry_checks(config, names, now)
    entries_s = time.monotonic() - entry_started
    return _finish_cycle([], bar_lines, entry_lines, exits_s, bars_s, entries_s, refresh_due, now)


def _live_cycle(config, names: list[str], now: datetime) -> list[str]:
    """One sandbox cycle. The lock covers orders. Exits run before the bar fetch."""
    from webull_bot.broker.webull import WebullBroker, assert_sandbox_hosts
    from webull_bot.journal.store import Journal
    import os

    raw = os.environ.get("WEBULL_ENV", "").strip().lower()
    if raw not in {"sandbox", "uat", "test"}:
        return [
            "Refusing to forward-watch without WEBULL_ENV=sandbox. "
            "Orders go only to *.sandbox.webull.com. Live trading stays off."
        ]
    refresh_due = full_cycle_due(now, LATEST.get("full")) or not LATEST.get("bars5")
    with cycle_lock(0) as acquired:
        if not acquired:
            return ["Fast tick skipped. The full cycle holds the lock. No second cycle."]
        broker = getattr(_live_cycle, "broker", None)
        if broker is None:
            try:
                broker = WebullBroker(environment="sandbox")
                broker.sandbox_only = True
                broker.connect()
                assert_sandbox_hosts(broker.hosts)
                guard_market_data(broker)
            except Exception:
                return ["Fast tick could not connect. Open positions wait for the next tick."]
            _live_cycle.broker = broker
        symbols = watch_symbols(names)
        budget = guard_market_data(broker)
        if budget.cooling("stock_snapshot"):
            prices = dict(LATEST.get("prices") or {})
        else:
            prices = snapshot_prices(broker, symbols, budget)
            if prices:
                LATEST["prices"] = prices
        journal = Journal(config.get("journal", "path", default="data/journal.sqlite"))
        started = time.monotonic()
        try:
            exit_lines = fast_tick(journal, broker, now, prices, names, do_exits=True, do_entries=False)
        except Exception:
            exit_lines = ["Fast tick failed. Open positions were left for the next tick and the bar cycle."]
        exits_s = time.monotonic() - started
        bar_started = time.monotonic()
        bar_lines: list[str] = []
        if refresh_due:
            bar_lines = refresh_closed_bars(config, now, names, broker)
            LATEST["full"] = boundary_of(now)
        bars_s = time.monotonic() - bar_started
        entry_started = time.monotonic()
        try:
            entry_lines = fast_tick(journal, broker, now, prices, names, do_exits=False, do_entries=True)
        except Exception:
            entry_lines = ["Entry check failed. No order was sent for that failure."]
        entries_s = time.monotonic() - entry_started
        return _finish_cycle(exit_lines, bar_lines, entry_lines, exits_s, bars_s, entries_s, refresh_due, now)


def dry_entry_checks(config, names: list[str], now: datetime) -> list[str]:
    """Replay every book on the shared cache. No connection and no journal write."""
    from concurrent.futures import ThreadPoolExecutor

    from webull_bot.execution.forward_four_hour import NAME as HOUR_NAME
    from webull_bot.execution.forward_four_hour import run_cycle as hour_cycle
    from webull_bot.execution.forward_trapdoor import NAME as TRAP_NAME
    from webull_bot.execution.forward_trapdoor import run_cycle as trap_cycle
    from webull_bot.execution.forward_vwap import BOOKS, run_cycle
    from webull_bot.journal.store import Journal

    journal_path = config.get("journal", "path", default="data/journal.sqlite")
    Journal(journal_path)
    points = LATEST.get("points") or {}
    closes = LATEST.get("closes") or {}
    bars15 = LATEST.get("bars15") or {}
    bars5 = LATEST.get("bars5") or {}

    def one(name: str) -> list[str]:
        journal = Journal(journal_path)
        if name in BOOKS:
            symbol = BOOKS[name]
            return run_cycle(
                journal=journal,
                bars15=_frame(bars15, symbol),
                bars5=_frame(bars5, symbol),
                now=now,
                iv_points=points,
                iv_closes=closes,
                broker=None,
                dry_run=True,
                book=name,
            )
        if name == TRAP_NAME:
            return trap_cycle(
                journal=journal,
                bars5=_frame(bars5, "QQQ"),
                now=now,
                iv_points=points,
                iv_closes=closes,
                broker=None,
                dry_run=True,
            )
        if name == HOUR_NAME:
            return hour_cycle(
                journal=journal,
                bars5=_frame(bars5, "QQQ"),
                now=now,
                iv_points=points,
                iv_closes=closes,
                broker=None,
                dry_run=True,
            )
        return [f"{name} is not a forward book. No order."]

    blocks = [f"Entry checks for {len(names)} books share one bar cache and run together."]
    workers = max(1, min(6, len(names)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for book_lines in pool.map(one, list(names)):
            blocks.append("\n".join(book_lines))
    return blocks


def refresh_closed_bars(config, now: datetime, names: list[str], broker=None) -> list[str]:
    """Merge the new 5-minute bars into the cache. One fetch for every book.

    The first load reads history once. Later closes append a short tail.
    A fetch that exceeds ``BAR_REFRESH_TIMEOUT_S`` does not hold the loop.
    """
    global _REFRESH_THREAD
    if _REFRESH_THREAD is not None and _REFRESH_THREAD.is_alive():
        return ["Bar refresh already running. Entries use the cached bars."]
    box: dict = {}

    def work() -> None:
        try:
            if not LATEST.get("bars5"):
                _prime(config, now, names, _overlay_broker(broker))
                box["kind"] = "loaded"
                return
            _append_tail(config, now, names, _overlay_broker(broker))
            box["kind"] = "appended"
        except Exception:
            box["kind"] = "failed"

    thread = threading.Thread(target=work, daemon=True, name="forward-bars")
    _REFRESH_THREAD = thread
    thread.start()
    thread.join(BAR_REFRESH_TIMEOUT_S)
    if thread.is_alive():
        return [
            (
                f"Bar refresh timed out after {BAR_REFRESH_TIMEOUT_S:.0f}s. "
                "Entries use the cached bars. The full history was not reloaded."
            )
        ]
    kind = box.get("kind")
    if kind == "appended":
        return ["Bar cache updated from the new 5-minute bars. Books share this cache."]
    if kind == "loaded":
        return ["Bar cache loaded. Later cycles append the new bars."]
    return ["Bar refresh failed. Entries use the cached bars."]


def _overlay_broker(broker):
    """Skip the Webull bar call while that endpoint is cooling."""
    budget = getattr(broker, "_watch_budget", None) if broker is not None else None
    if budget is not None and budget.cooling("stock_bars"):
        return None
    return broker


def _append_tail(config, now: datetime, names: list[str], broker) -> None:
    from datetime import timedelta as _delta

    from webull_bot.data.yfinance_provider import YFinanceProvider
    from webull_bot.execution.forward_vwap import BOOKS

    provider = YFinanceProvider(config.get("data", "cache_dir", default="data/cache"))
    symbols = list(dict.fromkeys(BOOKS[name] for name in names if name in BOOKS))
    five_symbols = watch_symbols(names)
    fresh5 = provider.append_recent(five_symbols, "5m", now, days=TAIL_DAYS)
    fresh15 = provider.append_recent(symbols, "15m", now, days=TAIL_DAYS) if symbols else {}
    if broker is not None:
        start = (now.date() - _delta(days=TAIL_DAYS)).isoformat()
        end = (now.date() + _delta(days=1)).isoformat()
        try:
            fresh15, fresh5 = overlay_webull_bars(
                broker, fresh15, fresh5, symbols, five_symbols, start, end
            )
        except Exception:
            pass
    bars15 = dict(LATEST.get("bars15") or {})
    bars5 = dict(LATEST.get("bars5") or {})
    for symbol, frame in (fresh5 or {}).items():
        if frame is not None and len(frame) > 0:
            bars5[symbol] = frame
    for symbol, frame in (fresh15 or {}).items():
        if frame is not None and len(frame) > 0:
            bars15[symbol] = frame
    remember_frames(bars15, bars5, LATEST.get("points"), LATEST.get("closes"))


def _prime(config, now: datetime, names: list[str], broker) -> None:
    """One bar load so a mid-bar start can still see a pending signal. Not every tick."""
    from datetime import timedelta as _delta

    from webull_bot.chart_reads.orb_mwf import prior_iv
    from webull_bot.data.yfinance_provider import YFinanceProvider
    from webull_bot.execution.forward_vwap import BOOKS

    end = now.date()
    start = end - _delta(days=50)
    provider = YFinanceProvider(config.get("data", "cache_dir", default="data/cache"))
    end_s = (end + _delta(days=1)).isoformat()
    symbols = list(dict.fromkeys(BOOKS[name] for name in names if name in BOOKS))
    five_symbols = watch_symbols(names)
    bars15 = provider.history(symbols, start.isoformat(), end_s, "15m") if symbols else {}
    bars5 = provider.history(five_symbols, start.isoformat(), end_s, "5m")
    try:
        bars15, bars5 = overlay_webull_bars(broker, bars15, bars5, symbols, five_symbols, start.isoformat(), end_s)
    except Exception:
        pass
    daily = provider.history(["^VIX", "^VIX1D"], "2016-01-01", end_s, "1d")
    closes = {}
    for symbol, frame in daily.items():
        if frame is None or getattr(frame, "empty", True) or "close" not in frame:
            continue
        closes[symbol] = frame["close"]
    points = prior_iv(closes.get("^VIX1D", pd.Series(dtype=float)), closes.get("^VIX", pd.Series(dtype=float)))
    remember_frames(bars15, bars5, points, closes)


def _watch_now(args) -> datetime:
    stamp = datetime.fromisoformat(str(args.now))
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=NY)
    return stamp.astimezone(NY)


def _clock() -> datetime:
    return datetime.now(NY)


def watch_symbols(names: list[str]) -> list[str]:
    from webull_bot.execution.forward_four_hour import NAME as HOUR_NAME
    from webull_bot.execution.forward_trapdoor import NAME as TRAP_NAME
    from webull_bot.execution.forward_vwap import BOOKS

    found = [BOOKS[name] for name in names if name in BOOKS]
    if TRAP_NAME in names or HOUR_NAME in names:
        found.append("QQQ")
    return list(dict.fromkeys(found))
