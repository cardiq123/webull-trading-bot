"""Sandbox forward test of the 15-minute 2 SD VWAP continuation.

The rules are the frozen extension book in ``vwap_band``: session VWAP, a
15-minute close strictly outside the 2 SD band, fill on the next open, a
stop one cent beyond the signal bar, a 1R target, and a flat at the 15:45
open. One at-the-money 0 DTE SPY contract. One position. The cash mirror
is the scored $1,000 book: the model debit has to fit settled cash, a sale
settles the next session, and equity at or under $1 stops new entries.

The cycle is every 5 minutes from 09:50 through 15:50 ET. Signals come
from completed 15-minute bars. Webull options have no OCO and no trailing
stop, so each cycle walks completed 5-minute bars and sells with a
marketable limit when the stop or the target trades. A 5-minute bar can
close the trade before the 15-minute bar that contains both levels. The
backtest fills the stop on that 15-minute bar.

CPI, NFP, and FOMC days are not skipped. The scored backtest does not
skip them.

``--dry-run`` replays the session from a fresh $1,000 and does not connect
or write the journal. A real cycle requires ``WEBULL_ENV=sandbox``. Live
trading stays off.
"""

from __future__ import annotations

import math
from datetime import date, datetime, time, timedelta
from typing import Any, Optional
from zoneinfo import ZoneInfo

import pandas as pd

from webull_bot.broker.webull import build_single_option_order, new_client_order_id
from webull_bot.calendar import is_trading_day, next_trading_day, to_ny
from webull_bot.chart_reads.vwap_band import (
    FLAT,
    OUTER_DEFAULT,
    _half_spread,
    _iv_on,
    _option_mid,
    find_signals,
    target_price,
    walk_exit,
)
from webull_bot.data.yfinance_provider import bar_end, latest_completed_bar_start
from webull_bot.journal.store import Journal
from webull_bot.mtf_vwap.detect import rth
from webull_bot.options.fees import CONTRACT_MULTIPLIER, option_leg_fees
from webull_bot.options.pricing import listed_strike

NY = ZoneInfo("America/New_York")
NAME = "vwap_band_15m"
SYMBOL = "SPY"
WINDOW_START = time(9, 50)
WINDOW_END = time(15, 50, 59)
STAKE = 1_000.0
# Written down so a reader can see the scored book did not skip these days.
SKIPS_EVENT_DAYS = False


def in_forward_window(moment: datetime) -> bool:
    local = to_ny(moment)
    if not is_trading_day(local.date()):
        return False
    return WINDOW_START <= local.time() <= WINDOW_END


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

    problems = data_problems(bars15, bars5, now)
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
            "Refusing to trade vwap_band_15m. Data is stale: "
            + "; ".join(problems)
            + ". No orders."
        )
        return lines

    if dry_run:
        events = plan_day(bars15=bars15, bars5=bars5, now=now, iv_points=points, settled=STAKE)
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
    _take_signals(state, bars15, bars5, now, points, broker, lines, journal)
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
    settled: float = STAKE,
    stopped: bool = False,
) -> list[dict]:
    """What the frozen rule would have done from the open through ``now``.

    This is the dry-run story. It assumes every earlier cycle ran, so a
    one-position skip is permanent even when this process was not here.
    """
    now_ts = pd.Timestamp(to_ny(now))
    points = iv_points or {}
    view = _signal_view(bars15, now_ts)
    path = _exit_path(bars5, now_ts)
    signals = _extensions(view, now_ts)
    cash = float(settled)
    equity = cash
    bust = bool(stopped) or equity <= 1.0
    busy: Optional[pd.Timestamp] = None
    events: list[dict] = []
    for signal in signals:
        if bust or equity <= 1.0:
            events.append(_skip(signal, "bust", "equity is at or under $1"))
            continue
        if busy is not None and pd.Timestamp(signal.fill_time) <= busy:
            events.append(_skip(signal, "overlap", "one position already open"))
            continue
        built = _price_signal(signal, view, path, now_ts, points, cash)
        if built.get("status") == "skip":
            events.append(built)
            continue
        cash -= float(built["model_debit"])
        if built["status"] == "closed":
            equity = cash + float(built["model_credit"])
            busy = pd.Timestamp(built["exit_time"])
        else:
            equity = cash
            busy = pd.Timestamp(now_ts.date().isoformat(), tz=NY) + pd.Timedelta(hours=23)
        built["settled_after"] = cash
        built["equity"] = equity
        events.append(built)
        if equity <= 1.0:
            bust = True
    return events


def data_problems(bars15: pd.DataFrame, bars5: pd.DataFrame, now: datetime) -> list[str]:
    """Today's completed 15-minute and 5-minute bars have to be in the frames."""
    problems = []
    missing15 = _missing(bars15, now, "15m")
    if missing15:
        problems.append(f"SPY 15-minute data is stale: missing {missing15} ET")
    missing5 = _missing(bars5, now, "5m")
    if missing5:
        problems.append(
            f"SPY 5-minute data is stale: missing {missing5} ET. The stop cannot be managed"
        )
    return problems


def report_text(journal: Journal) -> str:
    state = load_state(journal)
    if not state.get("signals") and not state.get("orders") and not state.get("exits"):
        return f"No forward-test journal for {NAME} yet.\n"
    lines = [
        f"{NAME} sandbox forward test. Live trading stays off.",
        "One ATM 0 DTE SPY contract. 2 SD continuation, 1R, stop one cent beyond the signal bar, flat at 15:45.",
        "A 5-minute bar can exit before the 15-minute bar that holds both the stop and the target.",
        "CPI, NFP, and FOMC days are not skipped.",
        f"Cash mirror settled ${float(state.get('settled') or 0):.2f} of a ${STAKE:,.0f} start.",
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
        lines.append(
            f"- {row.get('right')} strike {row.get('strike')} expiry {row.get('expiry')} "
            f"stop {row.get('stop')} target {row.get('target')}"
        )
    lines.append(f"Realized P&L on the model mirror ${realized:.2f}.")
    lines.append("")
    return "\n".join(lines) + "\n"


def _header(local: datetime, dry_run: bool) -> list[str]:
    lines = [
        f"Forward test {NAME}. Sandbox paper only. Live trading stays off.",
        (
            "One ATM 0 DTE SPY contract. Session VWAP, a 15-minute close outside the 2 SD band, "
            "fill on the next open, 1R target, stop one cent beyond the signal bar, flat at the 15:45 open."
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
        f"Window {local.isoformat()}. Cash mirror ${STAKE:,.0f}. One position.",
    ]
    if dry_run:
        lines.append(
            "Dry run replays the frozen rule from a fresh $1,000 and does not connect or write the journal."
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
        outcome = _position_exit(position, bars5, now)
        if outcome is None:
            kept.append(position)
            lines.append(
                f"Open {position.get('right')} from {position.get('fill_time')} "
                f"stop {float(position.get('stop')):.2f} target {float(position.get('target')):.2f}. Still open."
            )
            continue
        reason, underlying, when = outcome
        if _send_close(state, position, reason, underlying, when, broker, lines, journal):
            continue
        kept.append(position)
    state["positions"] = kept


def _take_signals(state, bars15, bars5, now, points, broker, lines, journal) -> None:
    now_ts = pd.Timestamp(to_ny(now))
    view = _signal_view(bars15, now_ts)
    path = _exit_path(bars5, now_ts)
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
            journal.forward_save(NAME, state)
            continue
        if state.get("stopped") or float(state.get("settled") or 0.0) <= 1.0:
            row = _skip(signal, "bust", "equity is at or under $1")
            state["signals"].append(row)
            lines.append("Skip " + _event_line(row))
            journal.forward_save(NAME, state)
            continue
        built = _price_signal(signal, view, path, now_ts, points, float(state.get("settled") or 0.0))
        if built.get("status") == "skip":
            state["signals"].append(built)
            lines.append("Skip " + _event_line(built))
            journal.forward_save(NAME, state)
            continue
        fill_open = _fill_bar_open(built["fill_time"], now_ts)
        if built["status"] == "closed" or not fill_open:
            why = "already_closed" if built["status"] == "closed" else "missed"
            text = (
                "the stop or target already traded before this order"
                if why == "already_closed"
                else "the fill bar already closed"
            )
            built["status"] = "skip"
            built["skip"] = why
            built["detail"] = text
            state["signals"].append(built)
            lines.append("Skip " + _event_line(built))
            journal.forward_save(NAME, state)
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
    if existing is None:
        order = {
            "key": key,
            "id": new_client_order_id(),
            "side": "BUY",
            "qty": "1",
            "symbol": SYMBOL,
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
    journal.forward_save(NAME, state)
    payload = build_single_option_order(
        client_order_id=order["id"],
        symbol=SYMBOL,
        side="BUY",
        quantity=1,
        strike_price=strike,
        option_expire_date=expiry,
        option_type=built["option_type"],
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
        "direction": built["direction"],
        "right": built["right"],
        "option_type": built["option_type"],
        "strike": strike,
        "model_strike": built["strike"],
        "expiry": expiry,
        "option_symbol": option_symbol,
        "signal_time": built["signal_time"],
        "fill_time": built["fill_time"],
        "entry": built["entry"],
        "stop": built["stop"],
        "target": built["target"],
        "model_ask": model_ask,
        "model_debit": built["model_debit"],
        "sandbox_ask": sandbox_ask,
        "price_source": source,
        "iv": built["iv"],
    }
    built["status"] = "open"
    built["price_source"] = source
    built["sandbox_ask"] = sandbox_ask
    built["order_strike"] = strike
    state["signals"].append(built)
    state["positions"].append(position)
    state["fills"].append(
        {
            "time": built["fill_time"],
            "side": "BUY",
            "qty": "1",
            "right": built["right"],
            "price": f"{limit:.2f}",
            "underlying": built["entry"],
            "price_source": source,
            "id": built["id"],
        }
    )
    state["settled"] = float(state.get("settled") or 0.0) - float(built["model_debit"])
    lines.append(
        "Signal "
        + _event_line(built)
        + f" Order BUY 1 {built['right']} limit {limit:.2f} ({source}). "
        + _quote_clause(model_ask, sandbox_ask)
    )
    journal.forward_save(NAME, state)


def _send_close(state, position, reason, underlying, when, broker, lines, journal) -> bool:
    key = f"{position['id']}|exit"
    existing = next((row for row in state.get("orders") or [] if row.get("key") == key), None)
    if existing and existing.get("status") in {"intent", "submitted"}:
        lines.append(f"Exit {position.get('right')} already journaled. Not sent again.")
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
    journal.forward_save(NAME, state)
    payload = build_single_option_order(
        client_order_id=order["id"],
        symbol=SYMBOL,
        side="SELL",
        quantity=1,
        strike_price=float(position["strike"]),
        option_expire_date=str(position["expiry"])[:10],
        option_type=str(position["option_type"]),
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
            "qty": "1",
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
        f"Order SELL 1 limit {limit:.2f} ({source}). "
        + _quote_clause(model_bid, sandbox_bid, bid=True)
    )
    journal.forward_save(NAME, state)
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
        return broker.option_zero_dte_quote(SYMBOL, built["option_type"], float(built["entry"]), built["expiry"])
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
    if path.empty:
        if now_ts.time() >= FLAT:
            return "flat", float(position.get("entry") or 0.0), now_ts
        return None
    loc = _locate(path, position["fill_time"])
    if loc is None:
        later = None
        for i, ts in enumerate(path.index):
            if pd.Timestamp(ts) >= pd.Timestamp(position["fill_time"]):
                later = i
                break
        loc = later
    if loc is None:
        if now_ts.time() >= FLAT:
            return "flat", float(path.iloc[-1]["close"]), path.index[-1]
        return None
    reason, price, when = walk_exit(
        path, loc, str(position["direction"]), float(position["stop"]), float(position["target"])
    )
    if reason in {"stop", "target", "flat"}:
        return reason, float(price), when
    if now_ts.time() >= FLAT:
        return "flat", float(path.iloc[-1]["open"]), path.index[-1]
    return None


def _price_signal(signal, view, path, now_ts, points, settled: float) -> dict:
    base = _base(signal)
    fill_loc = _locate(view, signal.fill_time)
    if fill_loc is None:
        return _skip(signal, "no_bar", "the next 15-minute open is not in the file")
    fill = float(view.iloc[fill_loc]["open"])
    stop = float(signal.stop)
    if not math.isfinite(fill) or fill <= 0 or not math.isfinite(stop):
        return _skip(signal, "no_bar", "the fill is not a price")
    distance = abs(fill - stop)
    if distance <= 0:
        return _skip(signal, "dust", "the stop is on the fill")
    loc = _locate(path, signal.fill_time)
    if path.empty or loc is None:
        return _skip(signal, "no_bar", "the 5-minute bar at the fill is missing")
    level = float(target_price(signal, fill, "r"))
    walked = path.copy()
    walked.iloc[loc, walked.columns.get_loc("open")] = fill
    reason, exit_raw, exit_time = walk_exit(walked, loc, signal.direction, stop, level)
    closed = reason in {"stop", "target", "flat"}
    day = _as_date(signal.fill_time)
    iv = _iv_on(day, points)
    if iv is None:
        return _skip(signal, "iv", "no prior VIX1D or VIX close")
    right = "call" if signal.direction == "long" else "put"
    option_type = "CALL" if signal.direction == "long" else "PUT"
    strike = listed_strike(fill, fill)
    entry_mid = _option_mid(right, fill, strike, pd.Timestamp(signal.fill_time), iv, 0)
    model_ask = entry_mid + _half_spread(entry_mid)
    debit = model_ask * CONTRACT_MULTIPLIER + option_leg_fees(1, model_ask, sell=False)
    if debit <= 0 or debit > settled + 1e-9:
        row = _skip(signal, "premium", "the model debit does not fit settled cash")
        row["model_ask"] = model_ask
        row["model_debit"] = debit
        row["strike"] = strike
        return row
    model_bid = None
    credit = None
    pnl = None
    if closed:
        exit_mid = _option_mid(right, float(exit_raw), strike, pd.Timestamp(exit_time), iv, 0)
        model_bid = max(0.0, exit_mid - _half_spread(exit_mid))
        credit = _credit(model_bid)
        pnl = credit - debit
    row = dict(base)
    row.update(
        {
            "status": "closed" if closed else "open",
            "reason": reason if closed else "open",
            "entry": fill,
            "exit": float(exit_raw) if closed else None,
            "exit_time": pd.Timestamp(exit_time).isoformat() if closed else None,
            "stop": stop,
            "target": level,
            "right": right,
            "option_type": option_type,
            "strike": strike,
            "expiry": day.isoformat(),
            "iv": iv,
            "model_ask": model_ask,
            "model_bid": model_bid,
            "model_debit": debit,
            "model_credit": credit,
            "pnl": pnl,
            "price_source": "model",
            "sandbox_ask": None,
        }
    )
    return row


def _extensions(view: pd.DataFrame, now_ts: pd.Timestamp) -> list:
    if view is None or view.empty:
        return []
    done = { _minute_key(ts) for ts in view.index if bar_end(ts, "15m") <= now_ts }
    found = []
    for signal in find_signals(view, SYMBOL, OUTER_DEFAULT):
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
        "symbol": SYMBOL,
        "direction": signal.direction,
        "signal_time": pd.Timestamp(signal.signal_time).isoformat(),
        "fill_time": pd.Timestamp(signal.fill_time).isoformat(),
        "stop": float(signal.stop),
    }


def _signal_id(signal) -> str:
    return f"{SYMBOL}|{pd.Timestamp(signal.signal_time).isoformat()}|{signal.direction}|extension"


def _event_line(event: dict) -> str:
    direction = event.get("direction") or ""
    when = _clock(event.get("signal_time"))
    if event.get("status") == "skip":
        return (
            f"{when} {direction} extension skipped: {event.get('detail') or event.get('skip')}."
        )
    fill = event.get("entry")
    fill_txt = f"{float(fill):.2f}" if isinstance(fill, (int, float)) else "?"
    stop = event.get("stop")
    target = event.get("target")
    ask = event.get("model_ask")
    ask_txt = f"{float(ask):.4f}" if isinstance(ask, (int, float)) else "?"
    body = (
        f"{when} {direction} extension fill {_clock(event.get('fill_time'))} open {fill_txt} "
        f"stop {float(stop):.2f} target {float(target):.2f} model ask {ask_txt}"
    )
    if event.get("status") == "closed":
        body += (
            f" closed {_clock(event.get('exit_time'))} reason {event.get('reason')} "
            f"underlying {float(event.get('exit') or 0):.2f}"
        )
        if event.get("model_bid") is not None:
            body += f" model bid {float(event['model_bid']):.4f}"
    else:
        body += " still open"
    return body


def _quote_clause(model: float, sandbox: Optional[float], bid: bool = False) -> str:
    label = "bid" if bid else "ask"
    if sandbox is None:
        return f"Model {label} {model:.4f}. No sandbox {label}."
    return f"Model {label} {model:.4f}. Sandbox {label} {sandbox:.4f}."


def _fill_bar_open(fill_time, now_ts: pd.Timestamp) -> bool:
    stamp = pd.Timestamp(fill_time)
    return stamp <= now_ts < bar_end(stamp, "15m")


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
    return clock.strftime("%Y-%m-%d %H:%M ET")


def _as_date(stamp) -> date:
    clock = pd.Timestamp(stamp)
    if clock.tzinfo is not None:
        clock = clock.tz_convert(NY)
    return clock.date()
