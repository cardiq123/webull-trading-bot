"""Sandbox forward test of the QQQ neckline trapdoor.

The book is the one neckline cell that cleared the frozen gate:
``QQQ_confirmed_short_r1_0dte``. A double top is the short mirror of the
mechanical double bottom (swing width 2, 6 to 30 bars apart, tolerance
the wider of 0.15% and half an ATR, and a 0.5 ATR run over the prior 12
bars). The trigger is a 5-minute close strictly below the neckline and
below both the 9 and 20 EMA. The neckline is the lowest low strictly
between the two swing highs. The stop is one cent above the second high.
The target is 1R from the modeled next open. The position is flat at the
15:45 open.

One at-the-money 0 DTE QQQ put. The cash mirror is the scored $2,500.
One position. This book opens at most three trades a day, which is the
scored cap. A new entry is also refused when the sandbox forward books
together have already opened five trades today.

The order goes out on the first cycle after the signal bar closes, and
only when QQQ is still strictly between the stop and the 1R target. Those
levels stay on the modeled next open. The same ``VWAP_MAX_ENTRY_DELAY_MIN``
cap (default 10 minutes after the bar close) expires a signal that was
not entered. A journaled signal is not sent again. Exits are bot-managed.
Webull options have no OCO. A marketable limit sells the put when a
completed 5-minute bar or the live underlying quote hits the stop or the
target. The 15:45 flatten is mandatory.

``--dry-run`` replays the session from a fresh $2,500 and does not connect
or write the journal. A real cycle requires ``WEBULL_ENV=sandbox``. Live
trading stays off. This module is the forward book. The neckline research
modules do not import it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Any, Optional

import pandas as pd

from webull_bot.broker.webull import build_single_option_order, new_client_order_id
from webull_bot.calendar import is_trading_day, next_trading_day, to_ny
from webull_bot.chart_reads.neckline import FLAT, STAKE, Cell, prepare, select_events
from webull_bot.chart_reads.vwap_band import _half_spread, _option_mid, walk_exit
from webull_bot.data.yfinance_provider import bar_end
from webull_bot.execution.forward_vwap import (
    COMBINED_ENTRY_CAP,
    combined_entries,
    in_forward_window,
    max_entry_delay_minutes,
    opened_on,
    resolve_volatility,
)
from webull_bot.execution.forward_vwap import (
    _as_date,
    _as_ny,
    _bars,
    _buy_limit,
    _clock,
    _credit,
    _exit_bid,
    _exit_model_bid,
    _exit_path,
    _first_exit_index,
    _inside,
    _last_key,
    _minute_key,
    _missing,
    _place,
    _print_open,
    _sell_limit,
    _spot,
)
from webull_bot.journal.store import Journal
from webull_bot.options.fees import CONTRACT_MULTIPLIER, option_leg_fees
from webull_bot.options.pricing import listed_strike

NAME = "neckline_trapdoor_qqq"
DISPLAY = "QQQ Trapdoor"
SYMBOL = "QQQ"
BOOK_CAP = 3
CELL = Cell(SYMBOL, "confirmed", "short", "r1", "0dte")
NY = "America/New_York"


@dataclass
class _Signal:
    signal_time: pd.Timestamp
    fill_time: pd.Timestamp
    stop: float
    neckline: float
    close: float
    second: float
    direction: str = "short"


def empty_state() -> dict[str, Any]:
    return {
        "book": NAME,
        "stake": STAKE,
        "settled": STAKE,
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
    saved = journal.forward_load(NAME)
    state = empty_state()
    if isinstance(saved, dict):
        for key in state:
            if key in saved:
                state[key] = saved[key]
    return state


def cycle_id(moment: datetime) -> str:
    """One decision per minute. The runner fires at :30 past each minute."""
    local = to_ny(moment).replace(second=0, microsecond=0)
    return local.strftime("%Y-%m-%dT%H:%M")


def run_cycle(
    *,
    journal: Journal,
    bars5: pd.DataFrame,
    now: datetime,
    iv_points: dict | None = None,
    iv_closes: dict | None = None,
    broker=None,
    dry_run: bool = False,
) -> list[str]:
    """One idempotent cycle. ``dry_run`` prints the rule and does not write or send."""
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

    problems = data_problems(bars5, now)
    if problems:
        if (not dry_run) and state.get("positions") and local.time() >= FLAT:
            lines.append(
                "Underlying data is stale (" + "; ".join(problems) + "). "
                "The 15:45 flatten is mandatory, so the open option is closed and the stop check is skipped."
            )
            _flatten_open(state, bars5, now, broker, lines, journal)
            _finish(state, journal, now, dry_run=False)
            return lines
        lines.append(
            f"Refusing to trade {NAME}. Data is stale: "
            + "; ".join(problems)
            + ". No orders."
        )
        return lines

    if dry_run:
        events = plan_day(
            bars5=bars5,
            now=now,
            iv_points=points,
            iv_closes=iv_closes,
            broker=broker,
            settled=STAKE,
        )
        lines.append(f"Last completed 5-minute bar {_last_key(bars5, now, '5m')}.")
        if not events:
            lines.append("No QQQ trapdoor through this cycle.")
        for event in events:
            lines.append(_event_line(event) + " Dry run: not sent.")
        lines.append("Dry run: orders are not sent and the journal is not written.")
        return lines

    _settle(state, local.date())
    lines.append(f"Last completed 5-minute bar {_last_key(bars5, now, '5m')}.")
    _manage_open(state, bars5, now, broker, lines, journal)
    _take_signals(state, bars5, now, points, iv_closes, broker, lines, journal)
    if not any(line.startswith("Signal ") or line.startswith("Exit ") or line.startswith("Skip ") for line in lines):
        if not state.get("positions"):
            lines.append("No new QQQ trapdoor. No open position.")
    _finish(state, journal, now, dry_run=False)
    return lines


def plan_day(
    *,
    bars5: pd.DataFrame,
    now: datetime,
    iv_points: dict | None = None,
    iv_closes: dict | None = None,
    broker=None,
    settled: float = STAKE,
    stopped: bool = False,
) -> list[dict]:
    """What QQQ Trapdoor would have done from 09:50 through ``now``.

    The replay assumes a cycle every minute at :30 past, which is the
    runner. One position, and at most three new entries. The cross-book
    cap of five is applied on a real cycle, where the other journals exist.
    """
    now_ts = _as_ny(now)
    points = iv_points or {}
    cash = float(settled)
    equity = cash
    bust = bool(stopped) or equity <= 1.0
    position: Optional[dict] = None
    seen: set[str] = set()
    events: list[dict] = []
    known = signals_through(bars5, now_ts)
    opened = 0
    for moment in _replay_moments(now_ts):
        path = _exit_path(bars5, moment)
        if position is not None:
            outcome = _exit_after(position, path, bars5, moment, broker)
            if outcome is not None:
                _mark_exit(position, *outcome)
                equity = cash + float(position["model_credit"])
                position = None
                if equity <= 1.0:
                    bust = True
        for signal in known:
            if bar_end(signal.signal_time, "5m") > moment:
                continue
            if _as_ny(signal.fill_time) > moment:
                continue
            sid = _signal_id(signal)
            if sid in seen:
                continue
            if bust or equity <= 1.0:
                row = _skip(signal, "bust", "equity is at or under $1")
                events.append(row)
                seen.add(sid)
                continue
            if position is not None:
                row = _skip(signal, "overlap", "one position already open")
                events.append(row)
                seen.add(sid)
                continue
            if opened >= BOOK_CAP:
                row = _skip(signal, "cap", "this book already opened 3 trades today")
                events.append(row)
                seen.add(sid)
                continue
            built = _decide_entry(signal, bars5, moment, points, cash, iv_closes, broker)
            if built.get("status") == "wait":
                continue
            seen.add(sid)
            if built.get("status") == "skip":
                events.append(built)
                continue
            opened += 1
            cash -= float(built["model_debit"])
            outcome = _exit_after(built, path, bars5, moment, broker)
            if outcome is not None:
                _mark_exit(built, *outcome)
                equity = cash + float(built["model_credit"])
            else:
                equity = cash
                position = built
            built["settled_after"] = cash
            built["equity"] = equity
            events.append(built)
            if equity <= 1.0:
                bust = True
    return events


def data_problems(bars5: pd.DataFrame, now: datetime) -> list[str]:
    """Today's completed 5-minute QQQ bars have to be in the frame."""
    missing = _missing(bars5, now, "5m")
    if not missing:
        return []
    return [f"{SYMBOL} 5-minute data is stale: missing {missing} ET. The stop cannot be managed"]


def report_text(journal: Journal) -> str:
    state = load_state(journal)
    if not state.get("signals") and not state.get("orders") and not state.get("exits"):
        return f"No forward-test journal for {NAME} yet.\n"
    lines = [
        f"{DISPLAY} ({NAME}) sandbox forward test. Live trading stays off.",
        (
            "One ATM 0 DTE QQQ put. Double top, 5-minute close below the neckline and below "
            "the 9 and 20 EMA, 1R target and stop one cent above the second high, flat at 15:45."
        ),
        (
            "The journal records the modeled next open and the actual entry. "
            "A signal is entered only while QQQ is strictly between the stop and the 1R target."
        ),
        (
            f"This book opens at most {BOOK_CAP} trades a day. "
            f"The forward books together open at most {COMBINED_ENTRY_CAP}."
        ),
        f"Cash mirror settled ${float(state.get('settled') or 0):.2f} of a ${STAKE:,.0f} start.",
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
    lines.append(f"Realized P&L on the model mirror ${realized:.2f}.")
    lines.append("")
    return "\n".join(lines) + "\n"


def signals_through(frame: pd.DataFrame, now_ts: pd.Timestamp) -> list[_Signal]:
    """Confirmed QQQ shorts whose 5-minute bar has closed by ``now_ts``."""
    ready = _ready(frame, now_ts)
    if ready is None or ready.empty:
        return []
    book = prepare(ready, SYMBOL)
    found: list[_Signal] = []
    now_ts = _as_ny(now_ts)
    for event in select_events(book.events, CELL):
        signal_time = pd.Timestamp(book.index[event.signal_i])
        fill_time = pd.Timestamp(book.index[event.fill_i])
        if _as_date(signal_time) != now_ts.date():
            continue
        if bar_end(signal_time, "5m") > now_ts:
            continue
        if _as_ny(fill_time).time() >= FLAT:
            continue
        found.append(
            _Signal(
                signal_time=signal_time,
                fill_time=fill_time,
                stop=float(event.stop),
                neckline=float(event.neckline),
                close=float(book.close[event.signal_i]),
                second=float(event.second),
            )
        )
    return found


def _ready(frame: pd.DataFrame, now_ts: pd.Timestamp) -> pd.DataFrame:
    """Closed bars, plus the next bar so the last close can name its fill.

    The next bar is the real one when the file has it. Otherwise it is the
    prior close with zero volume. That placeholder is not a signal: its bar
    has not closed. It does not move the EMAs on the closed bars.
    """
    bars = _bars(frame)
    if bars.empty:
        return bars
    now_ts = _as_ny(now_ts)
    done = [ts for ts in bars.index if bar_end(ts, "5m") <= now_ts]
    if not done:
        return bars.iloc[0:0]
    view = bars.loc[pd.DatetimeIndex(done)]
    last = _as_ny(done[-1])
    nxt = last + pd.Timedelta(minutes=5)
    if nxt.time() >= time(16, 0):
        return view
    real = { _minute_key(ts): ts for ts in bars.index }
    key = _minute_key(nxt)
    if key in real:
        return pd.concat([view, bars.loc[[real[key]]]])
    close = float(view.iloc[-1]["close"])
    extra = pd.DataFrame(
        [(close, close, close, close, 0.0)],
        columns=["open", "high", "low", "close", "volume"],
        index=pd.DatetimeIndex([nxt]),
    )
    return pd.concat([view, extra])


def _header(local: datetime, dry_run: bool) -> list[str]:
    lines = [
        f"Forward test {DISPLAY} ({NAME}). Sandbox paper only. Live trading stays off.",
        (
            "One ATM 0 DTE QQQ put. Double top, a 5-minute close below the neckline and below "
            "both the 9 and 20 EMA, 1R target and stop measured from the modeled next open, "
            "order on the first cycle after that bar when QQQ is still between them, flat at the 15:45 open."
        ),
        (
            "Exits are bot-managed. Webull options have no OCO and no trailing stop. "
            "A marketable limit closes the put when a completed bar or the live underlying quote "
            "hits the stop or the target. The 15:45 flatten is mandatory."
        ),
        (
            f"This book opens at most {BOOK_CAP} trades a day. "
            f"The forward books together open at most {COMBINED_ENTRY_CAP} new trades a day."
        ),
        f"Window {local.isoformat()}. Cash mirror ${STAKE:,.0f}. One position.",
        (
            f"Entry only through {max_entry_delay_minutes():g} minutes after the signal bar closes. "
            "A later cycle journals the signal as expired, late."
        ),
    ]
    if dry_run:
        lines.append(
            "Dry run replays each minute from a fresh $2,500 and does not connect or write the journal."
        )
    return lines


def _finish(state: dict, journal: Journal, now: datetime, dry_run: bool) -> None:
    if dry_run:
        return
    state["last_cycle"] = cycle_id(now)
    journal.forward_save(NAME, state)


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
        outcome = _exit_after(position, _exit_path(bars5, _as_ny(now)), bars5, _as_ny(now), broker)
        if outcome is None:
            kept.append(position)
            note = " Off-plan late entry." if _off_plan_late(position) else ""
            lines.append(
                f"Open put from {position.get('entry_time')} "
                f"stop {float(position.get('stop')):.2f} target {float(position.get('target')):.2f}. Still open.{note}"
            )
            continue
        reason, underlying, when = outcome
        if _send_close(state, position, reason, underlying, when, broker, lines, journal):
            continue
        kept.append(position)
    state["positions"] = kept


def _take_signals(state, bars5, now, points, iv_closes, broker, lines, journal) -> None:
    now_ts = _as_ny(now)
    known = {str(row.get("id")) for row in state.get("signals") or []}
    open_ids = {str(row.get("id")) for row in state.get("positions") or []}
    for signal in signals_through(bars5, now_ts):
        if _as_ny(signal.fill_time) > now_ts:
            continue
        sid = _signal_id(signal)
        if sid in known or sid in open_ids:
            lines.append(f"Signal {_clock(signal.signal_time)} already journaled. Not sent again.")
            continue
        if state.get("positions"):
            row = _skip(signal, "overlap", "one position already open")
            state["signals"].append(row)
            lines.append("Skip " + _event_line(row))
            journal.forward_save(NAME, state)
            continue
        if state.get("stopped") or float(state.get("settled") or 0.0) <= 1.0:
            row = _skip(signal, "bust", "equity is at or under $1")
            state["signals"].append(row)
            lines.append("Skip " + _event_line(row))
            journal.forward_save(NAME, state)
            continue
        if opened_on(state, now_ts.date()) >= BOOK_CAP:
            row = _skip(signal, "cap", "this book already opened 3 trades today")
            state["signals"].append(row)
            lines.append("Skip " + _event_line(row))
            journal.forward_save(NAME, state)
            continue
        if combined_entries(journal, now_ts.date(), NAME, state) >= COMBINED_ENTRY_CAP:
            row = _skip(signal, "cap", "the forward books already opened 5 trades today")
            state["signals"].append(row)
            lines.append("Skip " + _event_line(row))
            journal.forward_save(NAME, state)
            continue
        built = _decide_entry(
            signal, bars5, now_ts, points, float(state.get("settled") or 0.0), iv_closes, broker
        )
        if built.get("status") == "wait":
            lines.append(str(built.get("detail") or "Waiting on a price. No order."))
            continue
        if built.get("status") == "skip":
            state["signals"].append(built)
            lines.append("Skip " + _event_line(built))
            journal.forward_save(NAME, state)
            continue
        _send_open(state, built, now, broker, lines, journal)


def _flatten_open(state, bars5, now, broker, lines, journal) -> None:
    now_ts = _as_ny(now)
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
    if existing is None:
        order = {
            "key": key,
            "id": new_client_order_id(),
            "side": "BUY",
            "qty": "1",
            "symbol": SYMBOL,
            "right": "PUT",
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
    journal.forward_save(NAME, state)
    payload = build_single_option_order(
        client_order_id=order["id"],
        symbol=SYMBOL,
        side="BUY",
        quantity=1,
        strike_price=strike,
        option_expire_date=expiry,
        option_type="PUT",
        limit_price=limit,
        order_type="LIMIT",
        position_intent="BUY_TO_OPEN",
    )
    if not _place(broker, payload, order, lines, "entry"):
        journal.forward_save(NAME, state)
        return
    order["status"] = "submitted"
    position = {
        "id": built["id"],
        "direction": "short",
        "right": "put",
        "option_type": "PUT",
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
        "neckline": built["neckline"],
        "second": built["second"],
        "model_ask": model_ask,
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
            "qty": "1",
            "right": "put",
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
        + f" Order BUY 1 put limit {limit:.2f} ({source}). "
        + _quote_clause(model_ask, sandbox_ask)
    )
    journal.forward_save(NAME, state)


def _send_close(state, position, reason, underlying, when, broker, lines, journal) -> bool:
    key = f"{position['id']}|exit"
    existing = next((row for row in state.get("orders") or [] if row.get("key") == key), None)
    if existing and existing.get("status") in {"intent", "submitted"}:
        lines.append("Exit put already journaled. Not sent again.")
        return existing.get("status") == "submitted"
    model_bid = _exit_model_bid(position, underlying, when)
    sandbox_bid = _exit_bid(broker, position)
    source = "webull" if sandbox_bid is not None else "model"
    limit = _sell_limit(sandbox_bid if sandbox_bid is not None else model_bid)
    if existing is None:
        order = {
            "key": key,
            "id": new_client_order_id(),
            "side": "SELL",
            "qty": "1",
            "symbol": SYMBOL,
            "right": "PUT",
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
    journal.forward_save(NAME, state)
    payload = build_single_option_order(
        client_order_id=order["id"],
        symbol=SYMBOL,
        side="SELL",
        quantity=1,
        strike_price=float(position["strike"]),
        option_expire_date=str(position["expiry"])[:10],
        option_type="PUT",
        limit_price=limit,
        order_type="LIMIT",
        position_intent="SELL_TO_CLOSE",
    )
    if not _place(broker, payload, order, lines, "exit"):
        journal.forward_save(NAME, state)
        return False
    order["status"] = "submitted"
    credit = _credit(model_bid)
    debit = float(position.get("model_debit") or 0.0)
    pnl = credit - debit
    when_iso = pd.Timestamp(when).isoformat()
    state["exits"].append(
        {
            "id": position["id"],
            "time": when_iso,
            "right": "put",
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
            "qty": "1",
            "right": "put",
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
        f"Exit put reason {reason} underlying {float(underlying):.2f} "
        f"at {_clock(when)}. Model bid {model_bid:.4f}. "
        f"Order SELL 1 limit {limit:.2f} ({source}). "
        + _quote_clause(model_bid, sandbox_bid, bid=True)
    )
    journal.forward_save(NAME, state)
    return True


def _entry_quote(broker, built) -> Optional[dict]:
    if broker is None or not hasattr(broker, "option_zero_dte_quote"):
        return None
    try:
        return broker.option_zero_dte_quote(SYMBOL, "PUT", float(built["entry"]), built["expiry"])
    except Exception:
        return None


def _decide_entry(signal: _Signal, bars5, now_ts, points, settled: float, iv_closes=None, broker=None) -> dict:
    """Price the put at this cycle. A missing price waits. It is not a skip."""
    now_ts = _as_ny(now_ts)
    if _late(signal.signal_time, now_ts):
        row = _skip(signal, "expired", "expired, late")
        row["reason"] = "expired, late"
        row["entry_deadline"] = _deadline(signal.signal_time).isoformat()
        row["seen_at"] = now_ts.isoformat()
        return row
    if now_ts.time() >= FLAT:
        return _skip(signal, "flat", "the 15:45 flat has already passed")
    modeled, modeled_from = _modeled_open(signal, bars5, now_ts)
    if modeled is None:
        return {
            "status": "wait",
            "detail": f"The {_clock(signal.signal_time)} trapdoor is waiting on a price. No order.",
        }
    stop = float(signal.stop)
    if not math.isfinite(modeled) or modeled <= 0 or not math.isfinite(stop) or stop <= modeled:
        return _skip(signal, "dust", "the stop is not above the fill")
    spot = _underlying(broker, bars5, now_ts)
    if spot is None:
        return {
            "status": "wait",
            "detail": f"The {_clock(signal.signal_time)} trapdoor is waiting on a price. No order.",
        }
    target = modeled - (stop - modeled)
    if not _inside("short", spot, stop, target):
        row = _skip(
            signal,
            "outside",
            (
                f"the price {spot:.2f} is no longer between the stop {stop:.2f} "
                f"and the target {target:.2f}"
            ),
        )
        row["modeled_entry"] = modeled
        row["entry"] = spot
        row["stop"] = stop
        row["target"] = target
        return row
    day = _as_date(signal.fill_time)
    iv, iv_source = resolve_volatility(day, points, iv_closes, broker, spot, "PUT", now_ts)
    if iv is None:
        return _skip(
            signal,
            "iv",
            "no VIX1D prior close, VIX prior close, cached close, or sandbox option quote",
        )
    strike = listed_strike(spot, spot)
    entry_mid = _option_mid("put", spot, strike, now_ts, iv, 0)
    model_ask = entry_mid + _half_spread(entry_mid)
    debit = model_ask * CONTRACT_MULTIPLIER + option_leg_fees(1, model_ask, sell=False)
    if debit <= 0 or debit > settled + 1e-9:
        row = _skip(signal, "premium", "the model debit does not fit settled cash")
        row["model_ask"] = model_ask
        row["model_debit"] = debit
        row["strike"] = strike
        row["modeled_entry"] = modeled
        row["entry"] = spot
        row["iv"] = iv
        row["iv_source"] = iv_source
        return row
    return {
        "id": _signal_id(signal),
        "symbol": SYMBOL,
        "direction": "short",
        "status": "open",
        "reason": "open",
        "signal_time": pd.Timestamp(signal.signal_time).isoformat(),
        "fill_time": pd.Timestamp(signal.fill_time).isoformat(),
        "entry": spot,
        "entry_time": now_ts.isoformat(),
        "modeled_entry": modeled,
        "modeled_from": modeled_from,
        "exit": None,
        "exit_time": None,
        "stop": stop,
        "target": target,
        "neckline": float(signal.neckline),
        "second": float(signal.second),
        "right": "put",
        "option_type": "PUT",
        "strike": strike,
        "expiry": day.isoformat(),
        "iv": iv,
        "iv_source": iv_source,
        "model_ask": model_ask,
        "model_bid": None,
        "model_debit": debit,
        "model_credit": None,
        "pnl": None,
        "price_source": "model",
        "sandbox_ask": None,
    }


def _modeled_open(signal: _Signal, bars5, now_ts: pd.Timestamp) -> tuple[Optional[float], str]:
    opened = _print_open(bars5, signal.fill_time, now_ts)
    if opened is not None:
        return opened, "next open"
    if bar_end(signal.signal_time, "5m") <= now_ts and math.isfinite(signal.close) and signal.close > 0:
        return float(signal.close), "signal close"
    return None, ""


def _underlying(broker, bars5, now_ts: pd.Timestamp) -> Optional[float]:
    """Live quote when the broker has one, otherwise the latest knowable print."""
    getter = getattr(broker, "underlying_quote", None)
    if getter is not None:
        try:
            quoted = getter(SYMBOL)
        except Exception:
            quoted = None
        price = _positive(quoted)
        if price is not None:
            return price
    return _spot(bars5, now_ts)


def _positive(value) -> Optional[float]:
    try:
        price = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(price) or price <= 0:
        return None
    return price


def _mark_exit(built: dict, reason: str, underlying: float, when) -> None:
    iv = float(built["iv"])
    strike = float(built.get("model_strike") or built.get("strike") or 0.0)
    exit_mid = _option_mid("put", float(underlying), strike, pd.Timestamp(when), iv, 0)
    model_bid = max(0.0, exit_mid - _half_spread(exit_mid))
    credit = _credit(model_bid)
    debit = float(built["model_debit"])
    built["status"] = "closed"
    built["reason"] = reason
    built["exit"] = float(underlying)
    built["exit_time"] = pd.Timestamp(when).isoformat()
    built["model_bid"] = model_bid
    built["model_credit"] = credit
    built["pnl"] = credit - debit


def _exit_after(position, path, bars5, now_ts: pd.Timestamp, broker):
    """Flat, then a completed bar, then the live underlying quote."""
    now_ts = _as_ny(now_ts)
    if now_ts.time() >= FLAT:
        opened = _print_open(bars5, _flat_stamp(now_ts), now_ts)
        price = opened if opened is not None else _underlying(broker, bars5, now_ts)
        if price is None:
            price = float(position.get("entry") or 0.0)
        return "flat", float(price), now_ts
    if path is not None and not path.empty:
        loc = _first_exit_index(path, position.get("entry_time") or position.get("fill_time"))
        if loc is not None:
            reason, price, when = walk_exit(
                path, loc, "short", float(position.get("stop")), float(position.get("target"))
            )
            if reason in {"stop", "target", "flat"}:
                return reason, float(price), when
    spot = _underlying(broker, bars5, now_ts)
    if spot is None:
        return None
    stop = float(position.get("stop"))
    target = float(position.get("target"))
    if spot >= stop:
        return "stop", spot, now_ts
    if spot <= target:
        return "target", spot, now_ts
    return None


def _flat_stamp(now_ts: pd.Timestamp) -> pd.Timestamp:
    return now_ts.normalize() + pd.Timedelta(hours=15, minutes=45)


def _deadline(signal_time) -> pd.Timestamp:
    return bar_end(signal_time, "5m") + pd.Timedelta(minutes=max_entry_delay_minutes())


def _late(signal_time, when) -> bool:
    if signal_time is None or when is None:
        return False
    return _as_ny(when) > _deadline(signal_time)


def _off_plan_late(row: dict) -> bool:
    if not isinstance(row, dict):
        return False
    return _late(row.get("signal_time"), row.get("entry_time"))


def _replay_moments(now_ts: pd.Timestamp) -> list[pd.Timestamp]:
    now_ts = _as_ny(now_ts)
    if not is_trading_day(now_ts.date()):
        return []
    start = now_ts.normalize() + pd.Timedelta(hours=9, minutes=50, seconds=30)
    end = now_ts.normalize() + pd.Timedelta(hours=15, minutes=50, seconds=30)
    last = min(now_ts, end)
    moments = []
    cursor = start
    while cursor <= last:
        moments.append(cursor)
        cursor += pd.Timedelta(minutes=1)
    if now_ts <= end and (not moments or moments[-1] != now_ts):
        if now_ts >= now_ts.normalize() + pd.Timedelta(hours=9, minutes=50):
            moments.append(now_ts)
    return moments


def _skip(signal: _Signal, code: str, detail: str) -> dict:
    row = _base(signal)
    row.update({"status": "skip", "skip": code, "reason": code, "detail": detail})
    return row


def _base(signal: _Signal) -> dict:
    return {
        "id": _signal_id(signal),
        "symbol": SYMBOL,
        "direction": "short",
        "signal_time": pd.Timestamp(signal.signal_time).isoformat(),
        "fill_time": pd.Timestamp(signal.fill_time).isoformat(),
        "stop": float(signal.stop),
        "neckline": float(signal.neckline),
        "second": float(signal.second),
    }


def _signal_id(signal: _Signal) -> str:
    return f"{SYMBOL}|{_minute_key(signal.signal_time)}|short|trapdoor"


def _event_line(event: dict) -> str:
    when = _clock(event.get("signal_time"))
    if event.get("status") == "skip":
        return f"{when} QQQ put skipped ({event.get('skip')}): {event.get('detail')}"
    entry = event.get("entry")
    modeled = event.get("modeled_entry")
    stop = event.get("stop")
    target = event.get("target")
    bits = [f"{when} QQQ put"]
    if entry is not None:
        bits.append(f"entry {float(entry):.2f}")
    if modeled is not None:
        bits.append(f"modeled {float(modeled):.2f}")
    if stop is not None and target is not None:
        bits.append(f"stop {float(stop):.2f} target {float(target):.2f}")
    neck = event.get("neckline")
    if neck is not None:
        bits.append(f"neckline {float(neck):.2f}")
    if event.get("iv_source"):
        bits.append(str(event["iv_source"]))
    if event.get("status") == "closed":
        bits.append(f"exit {event.get('reason')} underlying {float(event.get('exit') or 0):.2f}")
    return " ".join(bits)


def _quote_clause(model: float, sandbox: Optional[float], bid: bool = False) -> str:
    side = "bid" if bid else "ask"
    if sandbox is None:
        return f"Model {side} {model:.4f}. No sandbox quote."
    return f"Sandbox {side} {sandbox:.4f}. Model {side} {model:.4f}."
