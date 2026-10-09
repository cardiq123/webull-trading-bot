"""Five-second sandbox watch for the VWAP books and QQQ Trapdoor.

The minute cycle reloads Yahoo and takes about six seconds, so it is not
run every five seconds. This process polls a batched Webull snapshot for
SPY and QQQ, and one batched option snapshot for contracts that are open.
It exits through the same bot-managed limit sell the minute cycle uses,
and it enters a journaled pending signal when the live price is inside
the stop and the target. The full signal cycle still runs, once, three
seconds after each five-minute bar close.

Documented OpenAPI market-data limits, checked 2026-10-09
(https://developer.webull.com/apis/docs/rate-limits), per endpoint and
per app key. Stock snapshot ``GET /market-data/stocks/snapshots/list``
and option snapshot ``GET /market-data/options/snapshots/list`` are
30 requests / 60s in sandbox and 60 / 60s in production. Option depth
on the stock endpoint is not a supported category.
This process stays at or under 15 requests / 60s on each snapshot
endpoint, half the sandbox cap. One call passes every symbol for that
category. A 429 backs off and does not retry in a loop. A quote failure
does not change an open position and does not block the bar-based exit.

The file lock ``data/forward/cycle.lock`` is shared with ``forward-test``.
The two never send orders at the same time.
"""

from __future__ import annotations

import csv
import fcntl
import logging
import re
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

LATEST: dict = {}


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
        delay = BACKOFF_SECONDS[min(strike, len(BACKOFF_SECONDS) - 1)]
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


def fast_tick(journal, broker, now: datetime, prices: dict[str, float], names: list[str]) -> list[str]:
    """Exits and pending entries for the cached bars. Quote failures stay local."""
    from webull_bot.calendar import to_ny
    from webull_bot.execution.forward_quotes import prime_forward_quotes
    from webull_bot.execution.forward_cash import prepare_cash
    from webull_bot.execution.forward_trapdoor import NAME as TRAP_NAME
    from webull_bot.execution.forward_trapdoor import STAKE as TRAP_STAKE
    from webull_bot.execution.forward_trapdoor import _log_market as trap_log
    from webull_bot.execution.forward_trapdoor import _manage_open as trap_manage
    from webull_bot.execution.forward_trapdoor import _take_signals as trap_take
    from webull_bot.execution.forward_trapdoor import load_state as trap_load
    from webull_bot.execution.forward_vwap import BOOKS, _ACTIVE, _activate, load_state
    from webull_bot.execution.forward_vwap import _log_market, _manage_open, _stake, _take_signals

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
    try:
        prime_forward_quotes(journal, broker, specs, now, include_ladder=log_minute)
    except Exception:
        lines.append("Option snapshot was not taken. Open positions were not changed.")
    for name in names:
        if name not in BOOKS:
            continue
        symbol = BOOKS[name]
        token = _activate(name)
        try:
            state = load_state(journal)
            if prepare_cash(state, broker, _stake(), local.date()):
                journal.forward_save(name, state)
            try:
                _manage_open(state, _frame(bars5, symbol), now, view, lines, journal)
            except Exception:
                lines.append(f"{name} exit check failed. The position was not changed.")
            try:
                _take_signals(
                    state, _frame(bars15, symbol), _frame(bars5, symbol), now, points, closes, view, lines, journal
                )
            except Exception:
                lines.append(f"{name} entry check failed. No order was sent for that failure.")
            _write_ticks(name, symbol, state, prices.get(symbol), broker, now)
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
        try:
            trap_manage(state, _frame(bars5, "QQQ"), now, view, lines, journal)
        except Exception:
            lines.append("QQQ Trapdoor exit check failed. The position was not changed.")
        try:
            trap_take(state, _frame(bars5, "QQQ"), now, points, closes, view, lines, journal)
        except Exception:
            lines.append("QQQ Trapdoor entry check failed. No order was sent for that failure.")
        _write_ticks(TRAP_NAME, "QQQ", state, prices.get("QQQ"), broker, now)
        if log_minute:
            try:
                trap_log(state, _frame(bars5, "QQQ"), now, broker, lines, journal, save=True)
            except Exception:
                lines.append("QQQ Trapdoor minute quote log failed. Entry and exit were not changed.")
        if prepare_cash(state, broker, TRAP_STAKE, local.date()):
            journal.forward_save(TRAP_NAME, state)
    if log_minute:
        LATEST["minute"] = minute_key
    if not lines:
        lines.append("Fast tick. No stop, target, or pending entry.")
    return lines


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
        if full_cycle_due(now, LATEST.get("full")):
            from webull_bot.cli import _forward_vwap

            code = _forward_vwap(config, _named(args, names, dry_run, now))
            LATEST["full"] = boundary_of(now)
            if once:
                return code
            continue
        if dry_run:
            print(
                f"forward-watch fast tick at {now.astimezone(NY).isoformat()}. "
                "Dry run: no snapshots, no orders, journal not written."
            )
            if once:
                return 0
            time.sleep(next_wake(_clock()))
            continue
        lines = _locked_fast(config, names, now)
        print("\n".join(lines))
        if once:
            return 0
        time.sleep(next_wake(_clock()))


def _locked_fast(config, names: list[str], now: datetime) -> list[str]:
    from webull_bot.broker.webull import WebullBroker, assert_sandbox_hosts
    from webull_bot.journal.store import Journal
    import os

    raw = os.environ.get("WEBULL_ENV", "").strip().lower()
    if raw not in {"sandbox", "uat", "test"}:
        return [
            "Refusing to forward-watch without WEBULL_ENV=sandbox. "
            "Orders go only to *.sandbox.webull.com. Live trading stays off."
        ]
    with cycle_lock(0) as acquired:
        if not acquired:
            return ["Fast tick skipped. The full cycle holds the lock. No second cycle."]
        broker = getattr(_locked_fast, "broker", None)
        if broker is None:
            try:
                broker = WebullBroker(environment="sandbox")
                broker.sandbox_only = True
                broker.connect()
                assert_sandbox_hosts(broker.hosts)
                guard_market_data(broker)
            except Exception:
                return ["Fast tick could not connect. Open positions wait for the next tick."]
            _locked_fast.broker = broker
        if not LATEST.get("bars5"):
            _prime(config, now, names, broker)
        symbols = watch_symbols(names)
        budget = guard_market_data(broker)
        prices = snapshot_prices(broker, symbols, budget)
        journal = Journal(config.get("journal", "path", default="data/journal.sqlite"))
        try:
            return fast_tick(journal, broker, now, prices, names)
        except Exception:
            return ["Fast tick failed. Open positions were left for the next tick and the bar cycle."]


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
    symbols = [BOOKS[name] for name in names if name in BOOKS]
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


def _named(args, names: list[str], dry_run: bool, now: datetime):
    from types import SimpleNamespace

    return SimpleNamespace(strategy=list(names), dry_run=dry_run, now=now.astimezone(NY).isoformat())


def _watch_now(args) -> datetime:
    stamp = datetime.fromisoformat(str(args.now))
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=NY)
    return stamp.astimezone(NY)


def _clock() -> datetime:
    return datetime.now(NY)


def watch_symbols(names: list[str]) -> list[str]:
    from webull_bot.execution.forward_trapdoor import NAME as TRAP_NAME
    from webull_bot.execution.forward_vwap import BOOKS

    found = [BOOKS[name] for name in names if name in BOOKS]
    if TRAP_NAME in names:
        found.append("QQQ")
    return list(dict.fromkeys(found))
