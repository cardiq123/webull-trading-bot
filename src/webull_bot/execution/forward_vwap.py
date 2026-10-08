"""Sandbox forward test of the 15-minute 2 SD VWAP continuation.

The rules are the frozen extension book in ``vwap_band``: session VWAP, a
15-minute close strictly outside the 2 SD band, fill on the next open, a
stop one cent beyond the signal bar, a 1R target, and a flat at the 15:45
open. One at-the-money 0 DTE contract. ``vwap_band_15m`` trades SPY.
``vwap_band_15m_qqq`` trades QQQ with the same rules and its own journal
key. ``vwap_band_15m_qqq_aggr`` is QQQ Aggressive: the same QQQ signal,
1R exits, entry expiry, and 15:45 flatten, with three at-the-money 0 DTE
contracts and a fresh $2,500 cash mirror. The ticket is three contracts
or it is skipped and journaled. It is never cut down and never sized
above three. One position per book. The one-contract books use the scored
$1,000 mirror: the model debit has to fit settled cash, a sale settles
the next session, and equity at or under $1 stops new entries.

The cycle is every 5 minutes from 09:50 through 15:50 ET. Signals come
from completed 15-minute bars, including the bar that just closed when the
next 15-minute bar is not in the file yet. The backtest fill is still that
next open, and the stop and 1R target stay on that modeled fill. The order
goes in on the first cycle after the signal bar closes when the current
price is still strictly between the stop and that target, and only when
that cycle is still within ``VWAP_MAX_ENTRY_DELAY_MIN`` minutes of the
signal bar's close (default 10). A later cycle journals the signal as
expired, late, and does not enter. A position already open keeps its
stop, its target, and the 15:45 exit. The report marks that fill as an
off-plan late entry. A stop or target that printed before the order is
not a skip. Exits walk only 5-minute bars
that start at or after the actual entry. The journal records the modeled
next open and the actual entry. A 5-minute bar can still close the trade
before the 15-minute bar that contains both levels.

Run the cycle a few seconds after each 5-minute boundary so the bar that
just closed is in the file and the new open is the price. Thirty seconds
past the boundary (systemd, America/New_York):
``Mon..Fri *-*-* 09..15:00/5:30``. Minute-only cron, one minute past:
``1,6,11,16,21,26,31,36,41,46,51,56 9-15 * * 1-5``. A schedule at :02/:07
is late enough that the first 5-minute bar of the fill can already have
closed. The entry rule above still sends the order if price is inside the
bracket. Stopping the clock at :00:30 and :15:30 only would leave the 5-minute
stop unmanaged for the rest of the quarter hour.

CPI, NFP, and FOMC days are not skipped. The scored backtest does not
skip them.

``--dry-run`` replays the session from a fresh cash mirror ($1,000 on the
one-contract books, $2,500 on QQQ Aggressive) and does not connect or
write the journal. A real cycle requires ``WEBULL_ENV=sandbox``. Live
trading stays off. The runner names ``vwap_band_15m``,
``vwap_band_15m_qqq_aggr``, and ``neckline_trapdoor_qqq``. The one-contract
QQQ book stays available so its journal can still be read.
"""

from __future__ import annotations

import contextvars
import math
import os
from datetime import date, datetime, time, timedelta
from typing import Any, Optional
from zoneinfo import ZoneInfo

import pandas as pd

from webull_bot.broker.webull import build_single_option_order, new_client_order_id
from webull_bot.calendar import is_trading_day, next_trading_day, to_ny
from webull_bot.chart_reads.vwap_band import (
    DIVIDEND,
    FLAT,
    OUTER_DEFAULT,
    RATE,
    VOL_CAP,
    VOL_FLOOR,
    _half_spread,
    _option_mid,
    _years,
    find_signals,
    target_price,
    walk_exit,
)
from webull_bot.data.yfinance_provider import bar_end, latest_completed_bar_start
from webull_bot.journal.store import Journal
from webull_bot.mtf_vwap.detect import rth
from webull_bot.options.fees import CONTRACT_MULTIPLIER, option_leg_fees
from webull_bot.options.pricing import listed_strike, option_price

NY = ZoneInfo("America/New_York")
NAME = "vwap_band_15m"
QQQ_NAME = "vwap_band_15m_qqq"
QQQ_AGGR_NAME = "vwap_band_15m_qqq_aggr"
SYMBOL = "SPY"
BOOKS = {
    NAME: "SPY",
    QQQ_NAME: "QQQ",
    QQQ_AGGR_NAME: "QQQ",
}
DISPLAY = {
    NAME: "SPY VWAP",
    QQQ_NAME: "QQQ VWAP",
    QQQ_AGGR_NAME: "QQQ Aggressive",
}
# One contract on the scored books. QQQ Aggressive is the fixed 3-lot cell.
QUANTITIES = {
    NAME: 1,
    QQQ_NAME: 1,
    QQQ_AGGR_NAME: 3,
}
STAKES = {
    NAME: 1_000.0,
    QQQ_NAME: 1_000.0,
    QQQ_AGGR_NAME: 2_500.0,
}
# New entries across the sandbox forward books, including QQQ Trapdoor.
# The one-contract QQQ journal still counts when the runner no longer calls it.
COMBINED_ENTRY_CAP = 5
ENTRY_BOOKS = (NAME, QQQ_NAME, QQQ_AGGR_NAME, "neckline_trapdoor_qqq")
_ACTIVE: contextvars.ContextVar[str] = contextvars.ContextVar("vwap_forward_book", default=NAME)
WINDOW_START = time(9, 50)
WINDOW_END = time(15, 50, 59)
STAKE = 1_000.0
# A cycle later than this after the signal bar closes does not enter.
DEFAULT_MAX_ENTRY_DELAY_MIN = 10.0
# Written down so a reader can see the scored book did not skip these days.
SKIPS_EVENT_DAYS = False


def _book() -> str:
    name = _ACTIVE.get()
    return name if name in BOOKS else NAME


def _symbol() -> str:
    return BOOKS[_book()]


def _display() -> str:
    return DISPLAY.get(_book(), _book())


def _stake() -> float:
    return float(STAKES.get(_book(), STAKE))


def _quantity() -> int:
    """Fixed lot for the active book. QQQ Aggressive is 3 and is never larger."""
    qty = int(QUANTITIES.get(_book(), 1))
    return qty if qty > 0 else 1


def _lot(row: dict | None = None) -> int:
    """Contracts on this ticket, capped at the book's fixed lot."""
    cap = _quantity()
    if isinstance(row, dict) and row.get("qty") not in (None, ""):
        try:
            qty = int(row["qty"])
        except (TypeError, ValueError):
            qty = 0
        if qty > 0:
            return min(qty, cap)
    return cap


def _contract_phrase() -> str:
    qty = _quantity()
    word = {1: "One", 3: "Three"}.get(qty, str(qty))
    noun = "contract" if qty == 1 else "contracts"
    return f"{word} ATM 0 DTE {_symbol()} {noun}"


def _activate(book: str) -> contextvars.Token:
    return _ACTIVE.set(book if book in BOOKS else NAME)


def opened_on(state: dict | None, day: date) -> int:
    """Filled entries whose actual entry time falls on ``day``. Skips do not count."""
    if not isinstance(state, dict):
        return 0
    count = 0
    for row in state.get("signals") or []:
        if not isinstance(row, dict) or row.get("status") not in {"open", "closed"}:
            continue
        if str(row.get("entry_time") or "")[:10] == day.isoformat():
            count += 1
    return count


def combined_entries(journal, day: date, book: str, state: dict) -> int:
    """Entries already opened today on this book plus the other forward journals.

    The in-memory state is the current book, so a fill that has not been
    saved yet is still counted. The other books are whatever the journal
    last saved.
    """
    total = opened_on(state, day)
    if journal is None:
        return total
    for name in ENTRY_BOOKS:
        if name == book:
            continue
        try:
            saved = journal.forward_load(name)
        except Exception:
            saved = None
        total += opened_on(saved, day)
    return total


def max_entry_delay_minutes() -> float:
    """Minutes after the signal bar closes that an entry is still allowed.

    ``VWAP_MAX_ENTRY_DELAY_MIN`` overrides the default. A blank or unusable
    value keeps the default. Both VWAP books read the same cap.
    """
    raw = os.environ.get("VWAP_MAX_ENTRY_DELAY_MIN", "").strip()
    if not raw:
        return DEFAULT_MAX_ENTRY_DELAY_MIN
    try:
        minutes = float(raw)
    except ValueError:
        return DEFAULT_MAX_ENTRY_DELAY_MIN
    if not math.isfinite(minutes) or minutes < 0:
        return DEFAULT_MAX_ENTRY_DELAY_MIN
    return minutes


def _as_ny(stamp) -> pd.Timestamp:
    clock = pd.Timestamp(stamp)
    if clock.tzinfo is None:
        return clock.tz_localize(NY)
    return clock.tz_convert(NY)


def _entry_deadline(signal_time) -> pd.Timestamp:
    return bar_end(signal_time, "15m") + pd.Timedelta(minutes=max_entry_delay_minutes())


def _entry_is_late(signal_time, when) -> bool:
    """True when ``when`` is after the signal bar close plus the entry cap."""
    if signal_time is None or when is None:
        return False
    return _as_ny(when) > _entry_deadline(signal_time)


def _off_plan_late(row: dict) -> bool:
    """A fill already in the journal that arrived after the entry cap."""
    if not isinstance(row, dict):
        return False
    return _entry_is_late(row.get("signal_time"), row.get("entry_time"))


def in_forward_window(moment: datetime) -> bool:
    local = to_ny(moment)
    if not is_trading_day(local.date()):
        return False
    return WINDOW_START <= local.time() <= WINDOW_END


def empty_state() -> dict[str, Any]:
    return {
        "book": _book(),
        "stake": _stake(),
        "settled": _stake(),
        "unsettled": [],
        "stopped": False,
        "signals": [],
        "orders": [],
        "fills": [],
        "exits": [],
        "positions": [],
        "last_cycle": None,
    }


def load_state(journal: Journal) -> dict[str, Any]:
    saved = journal.forward_load(_book())
    state = empty_state()
    if isinstance(saved, dict):
        for key in state:
            if key in saved:
                state[key] = saved[key]
    return state


def cycle_id(moment: datetime) -> str:
    local = to_ny(moment).replace(second=0, microsecond=0)
    local = local.replace(minute=(local.minute // 5) * 5)
    return local.strftime("%Y-%m-%dT%H:%M")


def run_cycle(
    *,
    journal: Journal,
    bars15: pd.DataFrame,
    bars5: pd.DataFrame,
    now: datetime,
    iv_points: dict | None = None,
    iv_closes: dict | None = None,
    broker=None,
    dry_run: bool = False,
    book: str = NAME,
) -> list[str]:
    """One idempotent cycle. ``dry_run`` prints the rule and does not write or send."""
    token = _activate(book)
    try:
        return _run_cycle(
            journal=journal,
            bars15=bars15,
            bars5=bars5,
            now=now,
            iv_points=iv_points,
            iv_closes=iv_closes,
            broker=broker,
            dry_run=dry_run,
        )
    finally:
        _ACTIVE.reset(token)


def _run_cycle(
    *,
    journal: Journal,
    bars15: pd.DataFrame,
    bars5: pd.DataFrame,
    now: datetime,
    iv_points: dict | None = None,
    iv_closes: dict | None = None,
    broker=None,
    dry_run: bool = False,
) -> list[str]:
    local = to_ny(now)
    if not in_forward_window(now):
        return [
            f"forward-test idle at {local.isoformat()}. "
            "Outside the 09:50-15:50 ET window. No orders."
        ]
    lines = _header(local, dry_run)
    points = iv_points or {}
    if not dry_run:
        state = load_state(journal)
        if state.get("last_cycle") == cycle_id(now):
            lines.append(f"Already journaled {cycle_id(now)}. No new orders.")
            return lines
    else:
        state = empty_state()

    problems = data_problems(bars15, bars5, now, book=_book())
    if problems:
        if (not dry_run) and state.get("positions") and local.time() >= FLAT:
            lines.append(
                "Underlying data is stale (" + "; ".join(problems) + "). "
                "The 15:45 flatten is mandatory, so the open option is closed and the stop check is skipped."
            )
            _flatten_open(state, now, broker, lines, journal)
            _finish(state, journal, now, dry_run=False)
            return lines
        lines.append(
            f"Refusing to trade {_book()}. Data is stale: "
            + "; ".join(problems)
            + ". No orders."
        )
        return lines

    if dry_run:
        events = plan_day(
            bars15=bars15,
            bars5=bars5,
            now=now,
            iv_points=points,
            iv_closes=iv_closes,
            broker=broker,
            settled=_stake(),
            book=_book(),
        )
        lines.extend(_clock_lines(bars15, bars5, now))
        if not events:
            lines.append("No 2 SD continuation through this cycle.")
            pending = _pending_fill(bars15, now)
            if pending:
                lines.append(pending)
        for event in events:
            lines.append(_event_line(event) + " Dry run: not sent.")
        lines.append("Dry run: orders are not sent and the journal is not written.")
        return lines

    _settle(state, local.date())
    lines.extend(_clock_lines(bars15, bars5, now))
    _manage_open(state, bars5, now, broker, lines, journal)
    _take_signals(state, bars15, bars5, now, points, iv_closes, broker, lines, journal)
    if not any(line.startswith("Signal ") or line.startswith("Exit ") or line.startswith("Skip ") for line in lines):
        pending = _pending_fill(bars15, now)
        if pending:
            lines.append(pending)
        elif not state.get("positions"):
            lines.append("No new 2 SD continuation. No open position.")
    _finish(state, journal, now, dry_run=False)
    return lines


def plan_day(
    *,
    bars15: pd.DataFrame,
    bars5: pd.DataFrame,
    now: datetime,
    iv_points: dict | None = None,
    iv_closes: dict | None = None,
    broker=None,
    settled: float | None = None,
    stopped: bool = False,
    book: str = NAME,
) -> list[dict]:
    token = _activate(book)
    try:
        cash = _stake() if settled is None else float(settled)
        return _plan_day(
            bars15=bars15,
            bars5=bars5,
            now=now,
            iv_points=iv_points,
            iv_closes=iv_closes,
            broker=broker,
            settled=cash,
            stopped=stopped,
        )
    finally:
        _ACTIVE.reset(token)


def _plan_day(
    *,
    bars15: pd.DataFrame,
    bars5: pd.DataFrame,
    now: datetime,
    iv_points: dict | None = None,
    iv_closes: dict | None = None,
    broker=None,
    settled: float = STAKE,
    stopped: bool = False,
) -> list[dict]:
    """What the forward rule would have done from the open through ``now``.

    This is the dry-run story. It assumes a cycle at every 5-minute boundary,
    so a one-position skip is permanent even when this process was not here.
    The entry is the first of those cycles after the signal bar closes, at
    the price then, and only when that price is still between the stop and
    the 1R target measured from the modeled next open.
    """
    now_ts = pd.Timestamp(to_ny(now))
    points = iv_points or {}
    cash = float(settled)
    equity = cash
    bust = bool(stopped) or equity <= 1.0
    busy: Optional[pd.Timestamp] = None
    position: Optional[dict] = None
    seen: set[str] = set()
    events: list[dict] = []
    for moment in _replay_moments(now_ts):
        path = _exit_path(bars5, moment)
        if position is not None:
            outcome = _exit_after(position, path, moment)
            if outcome is not None:
                _mark_exit(position, *outcome)
                equity = cash + float(position["model_credit"])
                busy = pd.Timestamp(position["exit_time"])
                position = None
                if equity <= 1.0:
                    bust = True
        view = _signal_view(bars15, moment)
        for signal in _extensions(view, moment):
            sid = _signal_id(signal)
            if sid in seen:
                continue
            if bust or equity <= 1.0:
                row = _skip(signal, "bust", "equity is at or under $1")
                events.append(row)
                seen.add(sid)
                continue
            fill_at = pd.Timestamp(signal.fill_time)
            blocked = position is not None or (busy is not None and fill_at <= busy)
            if blocked:
                row = _skip(signal, "overlap", "one position already open")
                events.append(row)
                seen.add(sid)
                continue
            built = _decide_entry(signal, bars15, bars5, moment, points, cash, iv_closes, broker)
            if built.get("status") == "wait":
                continue
            seen.add(sid)
            if built.get("status") == "skip":
                events.append(built)
                continue
            cash -= float(built["model_debit"])
            outcome = _exit_after(built, path, moment)
            if outcome is not None:
                _mark_exit(built, *outcome)
                equity = cash + float(built["model_credit"])
                busy = pd.Timestamp(built["exit_time"])
            else:
                equity = cash
                position = built
                busy = None
            built["settled_after"] = cash
            built["equity"] = equity
            events.append(built)
            if equity <= 1.0:
                bust = True
    return events


def data_problems(
    bars15: pd.DataFrame, bars5: pd.DataFrame, now: datetime, book: str = NAME
) -> list[str]:
    """Today's completed 15-minute and 5-minute bars have to be in the frames."""
    token = _activate(book)
    try:
        problems = []
        symbol = _symbol()
        missing15 = _missing(bars15, now, "15m")
        if missing15:
            problems.append(f"{symbol} 15-minute data is stale: missing {missing15} ET")
        missing5 = _missing(bars5, now, "5m")
        if missing5:
            problems.append(
                f"{symbol} 5-minute data is stale: missing {missing5} ET. The stop cannot be managed"
            )
        return problems
    finally:
        _ACTIVE.reset(token)


def report_text(journal: Journal, book: str = NAME) -> str:
    token = _activate(book)
    try:
        return _report_text(journal)
    finally:
        _ACTIVE.reset(token)


def _report_text(journal: Journal) -> str:
    state = load_state(journal)
    if not state.get("signals") and not state.get("orders") and not state.get("exits"):
        return f"No forward-test journal for {_book()} yet.\n"
    lines = [
        f"{_book()} ({_display()}) sandbox forward test. Live trading stays off.",
        f"{_contract_phrase()}. 2 SD continuation, 1R, stop one cent beyond the signal bar, flat at 15:45.",
        "The journal records the modeled next open and the actual entry. Exits start after the actual entry.",
        "A 5-minute bar can exit before the 15-minute bar that holds both the stop and the target.",
        "CPI, NFP, and FOMC days are not skipped.",
        f"Cash mirror settled ${float(state.get('settled') or 0):.2f} of a ${_stake():,.0f} start.",
        (
            f"A new entry has to be within {max_entry_delay_minutes():g} minutes of the signal bar close. "
            "A position already open still exits at the stop, the target, or 15:45."
        ),
        "Signals",
    ]
    signals = state.get("signals") or []
    if not signals:
        lines.append("(none)")
    for row in signals:
        lines.append("- " + _event_line(row))
    lines.append("Orders")
    orders = state.get("orders") or []
    if not orders:
        lines.append("(none)")
    for row in orders:
        lines.append(
            f"- {row.get('side')} {row.get('qty')} {row.get('symbol')} {row.get('right')} "
            f"limit {row.get('limit')} status {row.get('status')} "
            f"model {row.get('model_price')} sandbox {row.get('sandbox_price')} "
            f"{row.get('price_source')}"
        )
    lines.append("Fills")
    fills = state.get("fills") or []
    if not fills:
        lines.append("(none)")
    for row in fills:
        lines.append(
            f"- {row.get('time')} {row.get('side')} {row.get('qty')} {row.get('right')} "
            f"@ {row.get('price')} underlying {row.get('underlying')} {row.get('price_source')}"
        )
    lines.append("Exits")
    realized = 0.0
    exits = state.get("exits") or []
    if not exits:
        lines.append("(none)")
    for row in exits:
        pnl = float(row.get("pnl") or 0.0)
        realized += pnl
        lines.append(
            f"- {row.get('time')} {row.get('right')} reason {row.get('reason')} "
            f"underlying {row.get('underlying')} P&L ${pnl:.2f}"
        )
    lines.append("Open position")
    positions = state.get("positions") or []
    if not positions:
        lines.append("(none)")
    for row in positions:
        note = " off-plan late entry" if _off_plan_late(row) else ""
        lines.append(
            f"- {row.get('right')} strike {row.get('strike')} expiry {row.get('expiry')} "
            f"stop {row.get('stop')} target {row.get('target')}{note}"
        )
    if any(_off_plan_late(row) for row in list(signals) + list(positions)):
        lines.append(
            "Off-plan late entry. The stop, the target, and the 15:45 flat still manage that position."
        )
    lines.append(f"Realized P&L on the model mirror ${realized:.2f}.")
    lines.append("")
    return "\n".join(lines) + "\n"


def _header(local: datetime, dry_run: bool) -> list[str]:
    lines = [
        f"Forward test {_display()} ({_book()}). Sandbox paper only. Live trading stays off.",
        (
            f"{_contract_phrase()}. Session VWAP, a 15-minute close outside the 2 SD band, "
            "1R target and stop measured from the modeled next open, order on the first cycle after that bar "
            "when the price is still between them, flat at the 15:45 open."
        ),
        (
            "Exits are bot-managed. Webull options have no OCO and no trailing stop. "
            "A marketable limit closes the contract when the underlying hits the stop or the target. "
            "The 15:45 flatten is mandatory."
        ),
        (
            "A completed 5-minute bar can exit before the 15-minute bar that contains both the stop and the target. "
            "The backtest fills the stop on that 15-minute bar."
        ),
        "CPI, NFP, and FOMC days are not skipped. The scored backtest does not skip them.",
        (
            f"Window {local.isoformat()}. Cash mirror ${_stake():,.0f}. One position. "
            + (
                "1 contract."
                if _quantity() == 1
                else f"{_quantity()} contracts. A smaller lot is not bought, and the size does not go above {_quantity()}."
            )
        ),
        (
            f"Entry only through {max_entry_delay_minutes():g} minutes after the signal bar closes. "
            "A later cycle journals the signal as expired, late."
        ),
    ]
    if dry_run:
        lines.append(
            f"Dry run replays each 5-minute cycle from a fresh ${_stake():,.0f} and does not connect or write the journal."
        )
    return lines


def _clock_lines(bars15, bars5, now) -> list[str]:
    last15 = _last_key(bars15, now, "15m")
    last5 = _last_key(bars5, now, "5m")
    return [f"Last completed 15-minute bar {last15}. Last completed 5-minute bar {last5}."]


def _finish(state: dict, journal: Journal, now: datetime, dry_run: bool) -> None:
    if dry_run:
        return
    state["last_cycle"] = cycle_id(now)
    journal.forward_save(_book(), state)


def _settle(state: dict, day: date) -> None:
    still = []
    settled = float(state.get("settled") or 0.0)
    for item in state.get("unsettled") or []:
        due = date.fromisoformat(str(item.get("date"))[:10])
        if due <= day:
            settled += float(item.get("amount") or 0.0)
        else:
            still.append(item)
    state["settled"] = settled
    state["unsettled"] = still
    equity = settled + sum(float(item.get("amount") or 0.0) for item in still)
    if equity <= 1.0:
        state["stopped"] = True


def _manage_open(state, bars5, now, broker, lines, journal) -> None:
    kept = []
    for position in list(state.get("positions") or []):
        outcome = _position_exit(position, bars5, now)
        if outcome is None:
            kept.append(position)
            note = " Off-plan late entry." if _off_plan_late(position) else ""
            lines.append(
                f"Open {position.get('right')} from {position.get('entry_time') or position.get('fill_time')} "
                f"stop {float(position.get('stop')):.2f} target {float(position.get('target')):.2f}. Still open.{note}"
            )
            continue
        reason, underlying, when = outcome
        if _send_close(state, position, reason, underlying, when, broker, lines, journal):
            continue
        kept.append(position)
    state["positions"] = kept


def _take_signals(state, bars15, bars5, now, points, iv_closes, broker, lines, journal) -> None:
    now_ts = pd.Timestamp(to_ny(now))
    view = _signal_view(bars15, now_ts)
    known = {str(row.get("id")) for row in state.get("signals") or []}
    open_ids = {str(row.get("id")) for row in state.get("positions") or []}
    for signal in _extensions(view, now_ts):
        sid = _signal_id(signal)
        if sid in known or sid in open_ids:
            lines.append(f"Signal {_clock(signal.signal_time)} already journaled. Not sent again.")
            continue
        if state.get("positions"):
            row = _skip(signal, "overlap", "one position already open")
            state["signals"].append(row)
            lines.append("Skip " + _event_line(row))
            journal.forward_save(_book(), state)
            continue
        if state.get("stopped") or float(state.get("settled") or 0.0) <= 1.0:
            row = _skip(signal, "bust", "equity is at or under $1")
            state["signals"].append(row)
            lines.append("Skip " + _event_line(row))
            journal.forward_save(_book(), state)
            continue
        if combined_entries(journal, now_ts.date(), _book(), state) >= COMBINED_ENTRY_CAP:
            row = _skip(signal, "cap", "the forward books already opened 5 trades today")
            state["signals"].append(row)
            lines.append("Skip " + _event_line(row))
            journal.forward_save(_book(), state)
            continue
        built = _decide_entry(
            signal, bars15, bars5, now_ts, points, float(state.get("settled") or 0.0), iv_closes, broker
        )
        if built.get("status") == "wait":
            lines.append(str(built.get("detail") or "Waiting on the next open. No order."))
            continue
        if built.get("status") == "skip":
            state["signals"].append(built)
            lines.append("Skip " + _event_line(built))
            journal.forward_save(_book(), state)
            continue
        _send_open(state, built, now, broker, lines, journal)


def _flatten_open(state, now, broker, lines, journal) -> None:
    now_ts = pd.Timestamp(to_ny(now))
    kept = []
    for position in list(state.get("positions") or []):
        if _send_close(state, position, "flat", float(position.get("entry") or 0.0), now_ts, broker, lines, journal):
            continue
        kept.append(position)
    state["positions"] = kept


def _send_open(state, built, now, broker, lines, journal) -> None:
    key = f"{built['id']}|entry"
    existing = next((row for row in state.get("orders") or [] if row.get("key") == key), None)
    if existing and existing.get("status") in {"intent", "submitted"}:
        lines.append("Entry already journaled. Not sent again.")
        return
    quote = _entry_quote(broker, built)
    model_ask = float(built["model_ask"])
    sandbox_ask = None
    source = "model"
    strike = float(built["strike"])
    expiry = str(built["expiry"])
    option_symbol = ""
    limit_basis = model_ask
    if quote and quote.get("ask"):
        sandbox_ask = float(quote["ask"])
        limit_basis = sandbox_ask
        source = "webull"
        if quote.get("strike"):
            strike = float(quote["strike"])
        if quote.get("expiry"):
            expiry = str(quote["expiry"])[:10]
        option_symbol = str(quote.get("option_symbol") or "")
    limit = _buy_limit(limit_basis)
    qty = _lot(built)
    if existing is None:
        order = {
            "key": key,
            "id": new_client_order_id(),
            "side": "BUY",
            "qty": str(qty),
            "symbol": _symbol(),
            "right": built["option_type"],
            "limit": f"{limit:.2f}",
            "status": "intent",
            "model_price": f"{model_ask:.4f}",
            "sandbox_price": None if sandbox_ask is None else f"{sandbox_ask:.4f}",
            "price_source": source,
            "kind": "entry",
        }
        state["orders"].append(order)
    else:
        order = existing
        order["status"] = "intent"
        order["limit"] = f"{limit:.2f}"
        order["model_price"] = f"{model_ask:.4f}"
        order["sandbox_price"] = None if sandbox_ask is None else f"{sandbox_ask:.4f}"
        order["price_source"] = source
    journal.forward_save(_book(), state)
    payload = build_single_option_order(
        client_order_id=order["id"],
        symbol=_symbol(),
        side="BUY",
        quantity=qty,
        strike_price=strike,
        option_expire_date=expiry,
        option_type=built["option_type"],
        limit_price=limit,
        order_type="LIMIT",
        position_intent="BUY_TO_OPEN",
    )
    if not _place(broker, payload, order, lines, "entry"):
        journal.forward_save(_book(), state)
        return
    order["status"] = "submitted"
    position = {
        "id": built["id"],
        "direction": built["direction"],
        "right": built["right"],
        "option_type": built["option_type"],
        "strike": strike,
        "model_strike": built["strike"],
        "expiry": expiry,
        "option_symbol": option_symbol,
        "signal_time": built["signal_time"],
        "fill_time": built["fill_time"],
        "entry_time": built["entry_time"],
        "entry": built["entry"],
        "modeled_entry": built["modeled_entry"],
        "stop": built["stop"],
        "target": built["target"],
        "model_ask": model_ask,
        "qty": qty,
        "model_debit": built["model_debit"],
        "sandbox_ask": sandbox_ask,
        "price_source": source,
        "iv": built["iv"],
        "iv_source": built.get("iv_source"),
    }
    built["status"] = "open"
    built["price_source"] = source
    built["sandbox_ask"] = sandbox_ask
    built["order_strike"] = strike
    state["signals"].append(built)
    state["positions"].append(position)
    state["fills"].append(
        {
            "time": built["entry_time"],
            "side": "BUY",
            "qty": str(qty),
            "right": built["right"],
            "price": f"{limit:.2f}",
            "underlying": built["entry"],
            "modeled_entry": built["modeled_entry"],
            "modeled_fill_time": built["fill_time"],
            "price_source": source,
            "id": built["id"],
        }
    )
    state["settled"] = float(state.get("settled") or 0.0) - float(built["model_debit"])
    lines.append(
        "Signal "
        + _event_line(built)
        + f" Order BUY {qty} {built['right']} limit {limit:.2f} ({source}). "
        + _quote_clause(model_ask, sandbox_ask)
    )
    journal.forward_save(_book(), state)


def _send_close(state, position, reason, underlying, when, broker, lines, journal) -> bool:
    key = f"{position['id']}|exit"
    existing = next((row for row in state.get("orders") or [] if row.get("key") == key), None)
    if existing and existing.get("status") in {"intent", "submitted"}:
        lines.append(f"Exit {position.get('right')} already journaled. Not sent again.")
        return existing.get("status") == "submitted"
    qty = _lot(position)
    model_bid = _exit_model_bid(position, underlying, when)
    sandbox_bid = _exit_bid(broker, position)
    source = "webull" if sandbox_bid is not None else "model"
    limit = _sell_limit(sandbox_bid if sandbox_bid is not None else model_bid)
    if existing is None:
        order = {
            "key": key,
            "id": new_client_order_id(),
            "side": "SELL",
            "qty": str(qty),
            "symbol": _symbol(),
            "right": position.get("option_type"),
            "limit": f"{limit:.2f}",
            "status": "intent",
            "model_price": f"{model_bid:.4f}",
            "sandbox_price": None if sandbox_bid is None else f"{sandbox_bid:.4f}",
            "price_source": source,
            "kind": "exit",
            "reason": reason,
        }
        state["orders"].append(order)
    else:
        order = existing
        order["status"] = "intent"
        order["limit"] = f"{limit:.2f}"
        order["model_price"] = f"{model_bid:.4f}"
        order["sandbox_price"] = None if sandbox_bid is None else f"{sandbox_bid:.4f}"
        order["price_source"] = source
    journal.forward_save(_book(), state)
    payload = build_single_option_order(
        client_order_id=order["id"],
        symbol=_symbol(),
        side="SELL",
        quantity=qty,
        strike_price=float(position["strike"]),
        option_expire_date=str(position["expiry"])[:10],
        option_type=str(position["option_type"]),
        limit_price=limit,
        order_type="LIMIT",
        position_intent="SELL_TO_CLOSE",
    )
    if not _place(broker, payload, order, lines, "exit"):
        journal.forward_save(_book(), state)
        return False
    order["status"] = "submitted"
    credit = model_bid * CONTRACT_MULTIPLIER * qty - option_leg_fees(qty, model_bid, sell=True)
    debit = float(position.get("model_debit") or 0.0)
    pnl = credit - debit
    when_iso = pd.Timestamp(when).isoformat()
    state["exits"].append(
        {
            "id": position["id"],
            "time": when_iso,
            "right": position.get("right"),
            "reason": reason,
            "underlying": float(underlying),
            "model_bid": model_bid,
            "sandbox_bid": sandbox_bid,
            "price_source": source,
            "pnl": pnl,
        }
    )
    state["fills"].append(
        {
            "time": when_iso,
            "side": "SELL",
            "qty": str(qty),
            "right": position.get("right"),
            "price": f"{limit:.2f}",
            "underlying": float(underlying),
            "price_source": source,
            "id": position["id"],
            "reason": reason,
        }
    )
    for row in state.get("signals") or []:
        if row.get("id") == position["id"]:
            row["status"] = "closed"
            row["reason"] = reason
            row["exit"] = float(underlying)
            row["exit_time"] = when_iso
            row["model_bid"] = model_bid
            row["model_credit"] = credit
            row["pnl"] = pnl
    due = next_trading_day(_as_date(when))
    state.setdefault("unsettled", []).append({"date": due.isoformat(), "amount": credit})
    lines.append(
        f"Exit {position.get('right')} reason {reason} underlying {float(underlying):.2f} "
        f"at {_clock(when)}. Model bid {model_bid:.4f}. "
        f"Order SELL {qty} limit {limit:.2f} ({source}). "
        + _quote_clause(model_bid, sandbox_bid, bid=True)
    )
    journal.forward_save(_book(), state)
    return True


def _place(broker, payload, order, lines, kind: str) -> bool:
    sender = getattr(broker, "place_option_order", None)
    if sender is None:
        order["status"] = "not_sent"
        lines.append(f"Option {kind} was not sent. The broker has no option order path.")
        return False
    try:
        sender(payload)
    except Exception:
        order["status"] = "rejected"
        order["error"] = "rejected"
        lines.append(f"Option {kind} was rejected. The reason was not printed.")
        return False
    return True


def _entry_quote(broker, built) -> Optional[dict]:
    if broker is None or not hasattr(broker, "option_zero_dte_quote"):
        return None
    try:
        return broker.option_zero_dte_quote(_symbol(), built["option_type"], float(built["entry"]), built["expiry"])
    except Exception:
        return None


def _exit_bid(broker, position) -> Optional[float]:
    symbol = str(position.get("option_symbol") or "")
    if broker is None or not symbol or not hasattr(broker, "option_contract_quote"):
        return None
    try:
        quote = broker.option_contract_quote(symbol)
    except Exception:
        return None
    if not quote or quote.get("bid") in (None, ""):
        return None
    bid = float(quote["bid"])
    if not math.isfinite(bid) or bid <= 0:
        return None
    return bid


def _exit_model_bid(position, underlying: float, when) -> float:
    iv = float(position.get("iv") or 0.0)
    strike = float(position.get("model_strike") or position.get("strike") or 0.0)
    right = "call" if position.get("direction") == "long" else "put"
    mid = _option_mid(right, float(underlying), strike, pd.Timestamp(when), iv, 0)
    return max(0.0, mid - _half_spread(mid))


def _position_exit(position, bars5, now):
    now_ts = pd.Timestamp(to_ny(now))
    path = _exit_path(bars5, now_ts)
    return _exit_after(position, path, now_ts)


def resolve_volatility(day, points, closes, broker, spot, option_type, when) -> tuple[Optional[float], str]:
    """VIX1D prior close, then VIX, then the last cached close, then a sandbox quote.

    The scored backtest still requires a prior close. This chain is only the
    forward book, so a missing print does not skip the trade while any source
    has a number. The journal records which source was used.
    """
    chosen = _prior_close(day, points)
    if chosen is not None:
        return chosen
    cached = _cached_close(day, closes)
    if cached is not None:
        return cached
    quoted = _quote_volatility(broker, spot, option_type, when)
    if quoted is not None:
        return quoted, "sandbox option quote"
    return None, ""


def _prior_close(day, points) -> Optional[tuple[float, str]]:
    point = (points or {}).get(day)
    if not point:
        return None
    try:
        raw = float(point[0])
    except (TypeError, ValueError, IndexError):
        return None
    name = str(point[1]) if len(point) > 1 else "VIX"
    iv = _clip_points(raw)
    if iv is None:
        return None
    if name == "VIX1D":
        return iv, "VIX1D prior close"
    if name == "VIX":
        return iv, "VIX prior close"
    return iv, f"{name} prior close"


def _clip_points(raw: float) -> Optional[float]:
    if not math.isfinite(raw) or raw <= 0:
        return None
    return min(VOL_CAP, max(VOL_FLOOR, float(raw) / 100.0))


def _cached_close(day, closes) -> Optional[tuple[float, str]]:
    series_map = closes or {}
    for key, label in (("^VIX1D", "cached VIX1D"), ("^VIX", "cached VIX")):
        value = _latest_before(series_map.get(key), day)
        if value is None:
            continue
        iv = _clip_points(value)
        if iv is not None:
            return iv, label
    return None


def _latest_before(series, day: date) -> Optional[float]:
    if series is None or len(getattr(series, "index", ())) == 0:
        return None
    frame = series.astype(float)
    index = pd.to_datetime(frame.index)
    if getattr(index, "tz", None) is not None:
        index = index.tz_convert(NY).tz_localize(None)
    order = index.argsort()
    best = None
    for pos in order:
        value = float(frame.iloc[int(pos)])
        if not math.isfinite(value) or value <= 0:
            continue
        session = pd.Timestamp(index[int(pos)]).date()
        if session >= day:
            continue
        best = value
    return best


def _quote_volatility(broker, spot, option_type, when) -> Optional[float]:
    if broker is None or not hasattr(broker, "option_zero_dte_quote"):
        return None
    try:
        spot_value = float(spot)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(spot_value) or spot_value <= 0:
        return None
    try:
        quote = broker.option_zero_dte_quote(_symbol(), option_type, spot_value, _as_date(when))
    except Exception:
        return None
    if not quote:
        return None
    ask = _positive(quote.get("ask"))
    if ask is None:
        return None
    bid = _positive(quote.get("bid"))
    mid = (ask + bid) / 2.0 if bid is not None else ask
    strike = _positive(quote.get("strike")) or listed_strike(spot_value, spot_value)
    right = "call" if str(option_type).upper() == "CALL" else "put"
    return _implied_vol(right, spot_value, float(strike), when, mid)


def _positive(value) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number <= 0:
        return None
    return number


def _implied_vol(right: str, spot: float, strike: float, when, mid: float) -> Optional[float]:
    if mid <= 0 or spot <= 0 or strike <= 0:
        return None
    years = _years(pd.Timestamp(when), 0)

    def price(sigma: float) -> float:
        return float(option_price(right, spot, strike, years, sigma, RATE, DIVIDEND))

    if mid <= price(VOL_FLOOR):
        return VOL_FLOOR
    if mid >= price(VOL_CAP):
        return VOL_CAP
    lo = VOL_FLOOR
    hi = VOL_CAP
    for _ in range(48):
        guess = 0.5 * (lo + hi)
        if price(guess) < mid:
            lo = guess
        else:
            hi = guess
    return 0.5 * (lo + hi)


def _decide_entry(signal, bars15, bars5, now_ts, points, settled: float, iv_closes=None, broker=None) -> dict:
    """Price the order at this cycle. A missing open waits. It is not a skip.

    The stop and the 1R target stay on the modeled next open. The order uses
    the current price, and only when that price is still strictly between them.
    The cycle also has to fall within the entry cap after the signal bar
    closes. Bars between the modeled fill and this cycle are not an exit.
    A position that is already open is not decided here.
    """
    if _entry_is_late(signal.signal_time, now_ts):
        row = _skip(signal, "expired", "expired, late")
        row["reason"] = "expired, late"
        row["entry_deadline"] = _entry_deadline(signal.signal_time).isoformat()
        row["seen_at"] = _as_ny(now_ts).isoformat()
        return row
    if now_ts.time() >= FLAT:
        return _skip(signal, "flat", "the 15:45 flat has already passed")
    modeled = _print_open(bars15, signal.fill_time, now_ts)
    if modeled is None:
        modeled = _print_open(bars5, signal.fill_time, now_ts)
    if modeled is None:
        return {
            "status": "wait",
            "detail": (
                f"The {_clock(signal.signal_time)} extension is waiting on the next open. No order."
            ),
        }
    stop = float(signal.stop)
    if not math.isfinite(modeled) or modeled <= 0 or not math.isfinite(stop):
        return _skip(signal, "no_bar", "the fill is not a price")
    if abs(modeled - stop) <= 0:
        return _skip(signal, "dust", "the stop is on the fill")
    spot = _spot(bars5, now_ts)
    if spot is None:
        return {
            "status": "wait",
            "detail": (
                f"The {_clock(signal.signal_time)} extension is waiting on a price. No order."
            ),
        }
    level = float(target_price(signal, modeled, "r"))
    if not _inside(signal.direction, spot, stop, level):
        row = _skip(
            signal,
            "outside",
            (
                f"the price {spot:.2f} is no longer between the stop {stop:.2f} "
                f"and the target {level:.2f}"
            ),
        )
        row["modeled_entry"] = modeled
        row["entry"] = spot
        row["stop"] = stop
        row["target"] = level
        return row
    day = _as_date(signal.fill_time)
    right = "call" if signal.direction == "long" else "put"
    option_type = "CALL" if signal.direction == "long" else "PUT"
    iv, iv_source = resolve_volatility(day, points, iv_closes, broker, spot, option_type, now_ts)
    if iv is None:
        return _skip(
            signal,
            "iv",
            "no VIX1D prior close, VIX prior close, cached close, or sandbox option quote",
        )
    strike = listed_strike(spot, spot)
    entry_mid = _option_mid(right, spot, strike, now_ts, iv, 0)
    model_ask = entry_mid + _half_spread(entry_mid)
    qty = _quantity()
    debit = model_ask * CONTRACT_MULTIPLIER * qty + option_leg_fees(qty, model_ask, sell=False)
    if debit <= 0 or debit > settled + 1e-9:
        detail = "the model debit does not fit settled cash"
        if qty != 1:
            detail = f"the model debit for {qty} contracts does not fit settled cash"
        row = _skip(signal, "premium", detail)
        row["qty"] = qty
        row["model_ask"] = model_ask
        row["model_debit"] = debit
        row["strike"] = strike
        row["modeled_entry"] = modeled
        row["entry"] = spot
        row["iv"] = iv
        row["iv_source"] = iv_source
        return row
    row = dict(_base(signal))
    row.update(
        {
            "status": "open",
            "reason": "open",
            "entry": spot,
            "entry_time": pd.Timestamp(now_ts).isoformat(),
            "modeled_entry": modeled,
            "exit": None,
            "exit_time": None,
            "stop": stop,
            "target": level,
            "right": right,
            "option_type": option_type,
            "strike": strike,
            "expiry": day.isoformat(),
            "iv": iv,
            "iv_source": iv_source,
            "qty": qty,
            "model_ask": model_ask,
            "model_bid": None,
            "model_debit": debit,
            "model_credit": None,
            "pnl": None,
            "price_source": "model",
            "sandbox_ask": None,
        }
    )
    return row


def _mark_exit(built: dict, reason: str, underlying: float, when) -> None:
    iv = float(built["iv"])
    strike = float(built["strike"])
    right = str(built["right"])
    exit_mid = _option_mid(right, float(underlying), strike, pd.Timestamp(when), iv, 0)
    model_bid = max(0.0, exit_mid - _half_spread(exit_mid))
    qty = _lot(built)
    credit = model_bid * CONTRACT_MULTIPLIER * qty - option_leg_fees(qty, model_bid, sell=True)
    debit = float(built["model_debit"])
    built["status"] = "closed"
    built["reason"] = reason
    built["exit"] = float(underlying)
    built["exit_time"] = pd.Timestamp(when).isoformat()
    built["model_bid"] = model_bid
    built["model_credit"] = credit
    built["pnl"] = credit - debit


def _exit_after(built, path, now_ts: pd.Timestamp):
    """Stop, target, or flat on bars that start at or after the actual entry."""
    if path is None or path.empty:
        if now_ts.time() >= FLAT:
            return "flat", float(built.get("entry") or 0.0), now_ts
        return None
    loc = _first_exit_index(path, built.get("entry_time") or built.get("fill_time"))
    if loc is None:
        if now_ts.time() >= FLAT:
            return "flat", float(path.iloc[-1]["close"]), path.index[-1]
        return None
    reason, price, when = walk_exit(
        path, loc, str(built.get("direction")), float(built.get("stop")), float(built.get("target"))
    )
    if reason in {"stop", "target", "flat"}:
        return reason, float(price), when
    if now_ts.time() >= FLAT:
        return "flat", float(path.iloc[-1]["open"]), path.index[-1]
    return None


def _extensions(view: pd.DataFrame, now_ts: pd.Timestamp) -> list:
    if view is None or view.empty:
        return []
    ready = _with_unclosed_next(view, now_ts)
    done = {_minute_key(ts) for ts in view.index if bar_end(ts, "15m") <= now_ts}
    found = []
    for signal in find_signals(ready, _symbol(), OUTER_DEFAULT):
        if signal.mode != "extension":
            continue
        if _as_date(signal.signal_time) != now_ts.date():
            continue
        if _minute_key(signal.signal_time) not in done:
            continue
        if pd.Timestamp(signal.fill_time) > now_ts:
            continue
        if signal.fill_time.time() >= FLAT:
            continue
        found.append(signal)
    return found


def _with_unclosed_next(view: pd.DataFrame, now_ts: pd.Timestamp) -> pd.DataFrame:
    """Give the last closed bar a next timestamp when that bar has not finished.

    ``find_signals`` will not emit a continuation unless the next bar exists.
    The live file often has only closed bars, so the signal would otherwise
    wait until the fill bar itself had closed. The placeholder is the prior
    close with zero volume. It does not change earlier VWAP rows, and its own
    bar has not closed, so it is not a signal.
    """
    done = [ts for ts in view.index if bar_end(ts, "15m") <= now_ts]
    if not done:
        return view
    last = pd.Timestamp(done[-1])
    nxt = last + pd.Timedelta(minutes=15)
    if _minute_key(nxt) in {_minute_key(ts) for ts in view.index}:
        return view
    if bar_end(nxt, "15m") <= now_ts:
        return view
    close = float(view.loc[done[-1], "close"])
    extra = pd.DataFrame(
        [(close, close, close, close, 0.0)],
        columns=["open", "high", "low", "close", "volume"],
        index=pd.DatetimeIndex([nxt]),
    )
    return pd.concat([view, extra])


def _signal_view(frame: pd.DataFrame, now_ts: pd.Timestamp) -> pd.DataFrame:
    bars = _today(frame, now_ts)
    if bars.empty:
        return bars
    done = [ts for ts in bars.index if bar_end(ts, "15m") <= now_ts]
    if not done:
        return bars.iloc[0:0]
    last = done[-1]
    loc = bars.index.get_loc(last)
    extra = []
    if isinstance(loc, int) and loc + 1 < len(bars):
        nxt = bars.index[loc + 1]
        if pd.Timestamp(nxt) <= now_ts:
            extra.append(nxt)
    return bars.loc[pd.DatetimeIndex(done + extra)]


def _exit_path(frame: pd.DataFrame, now_ts: pd.Timestamp) -> pd.DataFrame:
    bars = _today(frame, now_ts)
    if bars.empty:
        return bars
    done = [ts for ts in bars.index if bar_end(ts, "5m") <= now_ts]
    extra = []
    if now_ts.time() >= FLAT:
        for ts in bars.index:
            if pd.Timestamp(ts).time() == FLAT and ts not in done and pd.Timestamp(ts) <= now_ts:
                extra.append(ts)
                break
    keep = done + extra
    if not keep:
        return bars.iloc[0:0]
    return bars.loc[pd.DatetimeIndex(keep)]


def _today(frame: pd.DataFrame, now_ts: pd.Timestamp) -> pd.DataFrame:
    bars = _bars(frame)
    if bars.empty:
        return bars
    keep = [ts for ts in bars.index if _as_date(ts) == now_ts.date()]
    if not keep:
        return bars.iloc[0:0]
    return bars.loc[pd.DatetimeIndex(keep)]


def _bars(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or len(frame) == 0:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    return rth(frame)


def _missing(frame: pd.DataFrame, now: datetime, interval: str) -> Optional[str]:
    expected = _expected_keys(now, interval)
    if not expected:
        return "no completed bar"
    have = {_minute_key(ts) for ts in _bars(frame).index}
    missing = [key for key in expected if key not in have]
    if not missing:
        return None
    suffix = f" ({len(missing)} bars)" if len(missing) > 1 else ""
    return missing[0] + suffix


def _expected_keys(now: datetime, interval: str) -> list[str]:
    need = latest_completed_bar_start(now, interval)
    if need is None:
        return []
    local = to_ny(now)
    step = {"15m": 15, "5m": 5}[interval]
    cursor = datetime.combine(local.date(), time(9, 30), tzinfo=NY)
    last = pd.Timestamp(need)
    keys = []
    while pd.Timestamp(cursor) <= last:
        keys.append(_minute_key(cursor))
        cursor += timedelta(minutes=step)
    return keys


def _last_key(frame, now, interval: str) -> str:
    bars = _today(frame, pd.Timestamp(to_ny(now)))
    done = [ts for ts in bars.index if bar_end(ts, interval) <= pd.Timestamp(to_ny(now))]
    if not done:
        return "none"
    return _minute_key(done[-1])


def _pending_fill(frame, now) -> Optional[str]:
    """A finished close outside the band with no next open in the file."""
    now_ts = pd.Timestamp(to_ny(now))
    bars = _today(frame, now_ts)
    completed = [ts for ts in bars.index if bar_end(ts, "15m") <= now_ts]
    if not completed:
        return None
    last = completed[-1]
    loc = _locate(bars, last)
    if loc is not None and loc + 1 < len(bars) and pd.Timestamp(bars.index[loc + 1]) <= now_ts:
        return None
    from webull_bot.chart_reads.detect import session_bands

    lone = bars.loc[pd.DatetimeIndex(completed)]
    band = session_bands(lone, deviations=1.0)
    if band.empty:
        return None
    band_loc = _locate(band, last)
    bar_loc = _locate(lone, last)
    if band_loc is None or bar_loc is None:
        return None
    width = band.iloc[band_loc]
    std = float(width["std"])
    vwap = float(width["vwap"])
    close = float(lone.iloc[bar_loc]["close"])
    if not math.isfinite(std) or std <= 0 or not math.isfinite(vwap):
        return None
    upper = vwap + OUTER_DEFAULT * std
    lower = vwap - OUTER_DEFAULT * std
    outside = close > upper or close < lower
    prev_inside = True
    if len(completed) > 1:
        prev_band = _locate(band, completed[-2])
        prev_bar = _locate(lone, completed[-2])
        if prev_band is not None and prev_bar is not None:
            prow = band.iloc[prev_band]
            pstd = float(prow["std"])
            pv = float(prow["vwap"])
            if math.isfinite(pstd) and pstd > 0 and math.isfinite(pv):
                pc = float(lone.iloc[prev_bar]["close"])
                prev_inside = (pv - OUTER_DEFAULT * pstd) <= pc <= (pv + OUTER_DEFAULT * pstd)
    if outside and prev_inside and pd.Timestamp(last).time() <= time(15, 15):
        return (
            f"The {_minute_key(last)} ET bar closed outside the 2 SD band, "
            "and the next open is not in the file yet. No order."
        )
    return None


def _locate(frame: pd.DataFrame, stamp) -> Optional[int]:
    if frame is None or len(frame) == 0:
        return None
    key = _minute_key(stamp)
    for i, ts in enumerate(frame.index):
        if _minute_key(ts) == key:
            return i
    return None


def _skip(signal, code: str, detail: str) -> dict:
    row = _base(signal)
    row.update({"status": "skip", "skip": code, "reason": code, "detail": detail})
    return row


def _base(signal) -> dict:
    return {
        "id": _signal_id(signal),
        "mode": "extension",
        "symbol": _symbol(),
        "direction": signal.direction,
        "signal_time": pd.Timestamp(signal.signal_time).isoformat(),
        "fill_time": pd.Timestamp(signal.fill_time).isoformat(),
        "stop": float(signal.stop),
    }


def _signal_id(signal) -> str:
    return f"{_symbol()}|{pd.Timestamp(signal.signal_time).isoformat()}|{signal.direction}|extension"


def _event_line(event: dict) -> str:
    direction = event.get("direction") or ""
    when = _clock(event.get("signal_time"))
    if event.get("status") == "skip":
        text = f"{when} {direction} extension skipped: {event.get('detail') or event.get('skip')}."
        if event.get("iv_source"):
            text += f" Volatility {event['iv_source']}."
        return text
    modeled = event.get("modeled_entry")
    if not isinstance(modeled, (int, float)):
        modeled = event.get("entry")
    actual = event.get("entry")
    modeled_txt = f"{float(modeled):.2f}" if isinstance(modeled, (int, float)) else "?"
    actual_txt = f"{float(actual):.2f}" if isinstance(actual, (int, float)) else "?"
    stop = event.get("stop")
    target = event.get("target")
    ask = event.get("model_ask")
    ask_txt = f"{float(ask):.4f}" if isinstance(ask, (int, float)) else "?"
    entry_time = event.get("entry_time") or event.get("fill_time")
    body = (
        f"{when} {direction} extension modeled fill {_clock(event.get('fill_time'))} open {modeled_txt} "
        f"actual {_clock(entry_time)} {actual_txt} "
        f"stop {float(stop):.2f} target {float(target):.2f} model ask {ask_txt}"
    )
    qty = event.get("qty")
    if isinstance(qty, int) and qty > 0:
        body += f" {qty} contract" + ("" if qty == 1 else "s")
    if event.get("status") == "closed":
        body += (
            f" closed {_clock(event.get('exit_time'))} reason {event.get('reason')} "
            f"underlying {float(event.get('exit') or 0):.2f}"
        )
        if event.get("model_bid") is not None:
            body += f" model bid {float(event['model_bid']):.4f}"
    else:
        body += " still open"
    if event.get("iv_source"):
        body += f" volatility {event['iv_source']}"
    if _off_plan_late(event):
        body += " off-plan late entry"
    return body


def _quote_clause(model: float, sandbox: Optional[float], bid: bool = False) -> str:
    label = "bid" if bid else "ask"
    if sandbox is None:
        return f"Model {label} {model:.4f}. No sandbox {label}."
    return f"Model {label} {model:.4f}. Sandbox {label} {sandbox:.4f}."


def _replay_moments(now_ts: pd.Timestamp) -> list[pd.Timestamp]:
    """5-minute boundaries from 09:50 through ``now``, plus ``now`` if it falls between them."""
    if now_ts.tzinfo is None:
        now_ts = now_ts.tz_localize(NY)
    else:
        now_ts = now_ts.tz_convert(NY)
    start = pd.Timestamp(datetime.combine(now_ts.date(), WINDOW_START, tzinfo=NY))
    if now_ts < start:
        return []
    moments: list[pd.Timestamp] = []
    cursor = start
    while cursor <= now_ts:
        moments.append(cursor)
        cursor += pd.Timedelta(minutes=5)
    if not moments or moments[-1] != now_ts:
        moments.append(now_ts)
    return moments


def _print_open(frame, stamp, now_ts: pd.Timestamp) -> Optional[float]:
    """Open of the bar at ``stamp``, once that bar has started. The close is not read."""
    bars = _today(frame, now_ts)
    loc = _locate(bars, stamp)
    if loc is None:
        return None
    start = pd.Timestamp(bars.index[loc])
    if start.tzinfo is None:
        start = start.tz_localize(NY)
    else:
        start = start.tz_convert(NY)
    if start > now_ts:
        return None
    price = float(bars.iloc[loc]["open"])
    if not math.isfinite(price) or price <= 0:
        return None
    return price


def _spot(frame, now_ts: pd.Timestamp) -> Optional[float]:
    """Price knowable at ``now``: the open of the 5-minute bar in progress, else the last close."""
    bars = _today(frame, now_ts)
    if bars.empty:
        return None
    for ts in bars.index:
        start = pd.Timestamp(ts)
        if start.tzinfo is None:
            start = start.tz_localize(NY)
        else:
            start = start.tz_convert(NY)
        if start <= now_ts < bar_end(start, "5m"):
            price = float(bars.loc[ts, "open"])
            if math.isfinite(price) and price > 0:
                return price
    done = [ts for ts in bars.index if bar_end(ts, "5m") <= now_ts]
    if not done:
        return None
    price = float(bars.loc[done[-1], "close"])
    if math.isfinite(price) and price > 0:
        return price
    return None


def _inside(direction: str, price: float, stop: float, target: float) -> bool:
    if direction == "long":
        return stop < price < target
    return target < price < stop


def _first_exit_index(path: pd.DataFrame, entry_time) -> Optional[int]:
    """First completed bar that starts at the entry, or the next bar when entry is mid-bar.

    A bar that was already printing when the order went in contains prices from
    before the fill. Those prices are not the trade.
    """
    if entry_time is None or path is None or len(path) == 0:
        return None
    entry = pd.Timestamp(entry_time)
    if entry.tzinfo is None:
        entry = entry.tz_localize(NY)
    else:
        entry = entry.tz_convert(NY)
    floored = entry.replace(second=0, microsecond=0)
    floored = floored.replace(minute=(floored.minute // 5) * 5)
    anchor = floored if entry == floored else floored + pd.Timedelta(minutes=5)
    for i, ts in enumerate(path.index):
        stamp = pd.Timestamp(ts)
        if stamp.tzinfo is None:
            stamp = stamp.tz_localize(NY)
        else:
            stamp = stamp.tz_convert(NY)
        if stamp >= anchor:
            return i
    return None


def _credit(bid: float) -> float:
    return bid * CONTRACT_MULTIPLIER - option_leg_fees(1, bid, sell=True)


def _buy_limit(price: float) -> float:
    return math.ceil((float(price) - 1e-9) * 100.0) / 100.0


def _sell_limit(price: float) -> float:
    floored = math.floor((float(price) + 1e-9) * 100.0) / 100.0
    return max(0.01, floored)


def _minute_key(stamp) -> str:
    clock = pd.Timestamp(stamp)
    if clock.tzinfo is not None:
        clock = clock.tz_convert(NY)
    return clock.strftime("%Y-%m-%d %H:%M")


def _clock(stamp) -> str:
    if stamp is None:
        return "?"
    clock = pd.Timestamp(stamp)
    if clock.tzinfo is not None:
        clock = clock.tz_convert(NY)
    if clock.second or clock.microsecond:
        return clock.strftime("%Y-%m-%d %H:%M:%S ET")
    return clock.strftime("%Y-%m-%d %H:%M ET")


def _as_date(stamp) -> date:
    clock = pd.Timestamp(stamp)
    if clock.tzinfo is not None:
        clock = clock.tz_convert(NY)
    return clock.date()
