"""Sandbox forward test of the hourly chop-v2 box breakout.

One cycle, meant to be run at 5 minutes after each 60-minute bar close
(10:35 through 15:35 ET). It is idempotent. Outside that window it prints
a no-op and does not send an order.

Stock only, on the named list from the 60-minute book. The OpenAPI equity
order is ``entrust_type=QTY`` and the published examples are whole shares.
This adapter does not send a fractional or cash-amount order, so the
sub-book is $10,000 of whole shares, at most 3 positions, one slot each.

The exit is a native equity ``TRAILING_STOP_LOSS`` at 15% (DAY, so it is
placed again each session). If that place call fails, the same 15% trail
is kept in the journal and a later cycle sells at the market. The time
stop is the scored one: exit on the 15:35 cycle of the fifth session, or
on the next cycle if that one was missed.

``--dry-run`` prints the orders and does not connect to Webull. A real
cycle requires ``WEBULL_ENV=sandbox``. Live trading stays off.
"""

from __future__ import annotations

import hashlib
import math
from datetime import date, datetime, time
from typing import Any, Optional
from zoneinfo import ZoneInfo

import pandas as pd

from webull_bot.broker.webull import build_trailing_stop_order, new_client_order_id
from webull_bot.calendar import is_trading_day, to_ny, trading_days_between
from webull_bot.chart_reads.research import SYMBOLS
from webull_bot.journal.store import Journal
from webull_bot.models import Order, OrderType, Side, TimeInForce
from webull_bot.mtf_vwap.detect import rth
from webull_bot.strategies.chop_breakout import (
    FLATTEN_EOD,
    MAX_HOLD_SESSIONS,
    TRAIL_PCT,
    ChopBreakout60m,
)

NY = ZoneInfo("America/New_York")
WINDOW_START = time(10, 35)
WINDOW_END = time(15, 35, 59)
# Whole shares. See the module docstring.
FRACTIONAL_SHARES = False
NOTIONAL = 10_000.0
MAX_POSITIONS = 3
SLOT = NOTIONAL / MAX_POSITIONS
NAME = ChopBreakout60m.name


def in_forward_window(moment: datetime) -> bool:
    local = to_ny(moment)
    if not is_trading_day(local.date()):
        return False
    return WINDOW_START <= local.time() <= WINDOW_END


def whole_shares(price: float, budget: float) -> int:
    if not math.isfinite(price) or price <= 0 or budget <= 0:
        return 0
    return int(math.floor(budget / price))


def empty_state() -> dict[str, Any]:
    return {
        "signals": [],
        "orders": [],
        "fills": [],
        "exits": [],
        "positions": [],
        "trails": [],
        "shadow_positions": [],
        "shadow_exits": [],
        "spy": None,
        "option_signals": [],
        "option_orders": [],
        "option_fills": [],
        "option_exits": [],
        "option_positions": [],
    }


def load_state(journal: Journal) -> dict[str, Any]:
    saved = journal.forward_load(NAME)
    state = empty_state()
    if isinstance(saved, dict):
        for key in state:
            if key in saved:
                state[key] = saved[key]
    return state


def completed_hourly(frame: pd.DataFrame, now: datetime) -> pd.DataFrame:
    """Bars whose session window has ended. The 15:30 bar ends at 16:00."""
    bars = rth(frame) if frame is not None else None
    if bars is None or bars.empty:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    now_ny = pd.Timestamp(to_ny(now))
    keep = []
    for ts in bars.index:
        start = pd.Timestamp(ts)
        close_at = start.normalize() + pd.Timedelta(hours=16)
        end = min(start + pd.Timedelta(hours=1), close_at)
        keep.append(end <= now_ny)
    return bars.loc[keep]


def _last_completed(frames: dict[str, pd.DataFrame], now: datetime) -> Optional[pd.Timestamp]:
    last = None
    for frame in frames.values():
        done = completed_hourly(frame, now)
        if done.empty:
            continue
        stamp = pd.Timestamp(done.index[-1])
        if last is None or stamp > last:
            last = stamp
    return last


def _signal_id(symbol: str, signal_time, direction: str) -> str:
    return f"{symbol}|{pd.Timestamp(signal_time).isoformat()}|{direction}"


def _same_bar(left, right) -> bool:
    return pd.Timestamp(left).isoformat() == pd.Timestamp(right).isoformat()


def _quote(frame: pd.DataFrame, now: datetime) -> Optional[float]:
    """Next open after the last completed bar, else that bar's close."""
    if frame is None or frame.empty:
        return None
    bars = rth(frame)
    done = completed_hourly(frame, now)
    if done.empty:
        return None
    last = done.index[-1]
    loc = bars.index.get_loc(last)
    if isinstance(loc, slice):
        loc = loc.start
    if isinstance(loc, int) and loc + 1 < len(bars):
        price = float(bars.iloc[loc + 1]["open"])
        if math.isfinite(price) and price > 0:
            return price
    price = float(done.iloc[-1]["close"])
    if math.isfinite(price) and price > 0:
        return price
    return None


def _bar(frame: pd.DataFrame, now: datetime):
    done = completed_hourly(frame, now)
    if done.empty:
        return None
    return done.iloc[-1]


def _sessions_held(opened_on: str, today: date) -> int:
    opened = date.fromisoformat(opened_on)
    if today < opened:
        return 0
    return len(trading_days_between(opened, today))


def _is_last_slot(moment: datetime) -> bool:
    local = to_ny(moment)
    return local.hour == 15 and local.minute >= 35


def _shadow_symbol(signal_id: str) -> str:
    digest = hashlib.sha256(f"17|{signal_id}".encode()).digest()
    return SYMBOLS[digest[0] % len(SYMBOLS)]


def trailing_order(symbol: str, quantity: int) -> Order:
    return Order(
        client_order_id=new_client_order_id(),
        symbol=symbol,
        side=Side.SELL,
        quantity=float(quantity),
        order_type=OrderType.TRAILING,
        time_in_force=TimeInForce.DAY,
        trail_type="PERCENTAGE",
        trail_step=TRAIL_PCT,
        strategy=NAME,
    )


def trailing_payload(symbol: str, quantity: int) -> dict[str, str]:
    return build_trailing_stop_order(
        client_order_id=new_client_order_id(),
        symbol=symbol,
        side="SELL",
        quantity=float(quantity),
        trailing_type="PERCENTAGE",
        trailing_stop_step=TRAIL_PCT,
    )


def run_cycle(
    *,
    journal: Journal,
    frames: dict[str, pd.DataFrame],
    now: datetime,
    strategy: ChopBreakout60m | None = None,
    broker=None,
    dry_run: bool = False,
    scan=None,
) -> list[str]:
    """One idempotent cycle. ``dry_run`` prints orders and does not write or send."""
    strategy = strategy or ChopBreakout60m()
    local = to_ny(now)
    if not in_forward_window(now):
        line = (
            f"forward-test idle at {local.isoformat()}. "
            "Outside the 10:35-15:35 ET window. No orders."
        )
        return [line]

    lines = [
        f"Forward test {NAME}. Sandbox paper only. Live trading stays off.",
        (
            "Whole shares, $10,000 notional, at most 3 positions. "
            "OpenAPI equity orders are QTY, and this adapter does not send a fractional order."
        ),
        f"Window {local.isoformat()}. Trail {TRAIL_PCT:.0%} DAY, time stop {MAX_HOLD_SESSIONS} sessions, "
        f"flatten_eod {FLATTEN_EOD}.",
    ]
    if dry_run:
        lines.append("Dry run: orders are built and not sent.")
    elif broker is None:
        raise RuntimeError("A sandbox broker is required unless --dry-run is set.")

    state = load_state(journal)
    last = _last_completed(frames, now)
    if last is None:
        lines.append("No completed 60-minute bar. No orders.")
        return lines
    lines.append(f"Last completed 60-minute bar {pd.Timestamp(last).isoformat()}.")

    detector = scan or strategy.scan
    setups = detector(frames)
    actionable = [
        setup
        for setup in setups
        if setup.symbol in frames and _same_bar(setup.signal_time, _symbol_last(frames[setup.symbol], now))
    ]
    if not actionable:
        lines.append("No new chop-v2 breakout on the last completed bar.")

    _mark_open(state, frames, now, lines, broker, dry_run, journal)
    for setup in actionable:
        _on_signal(state, setup, frames, now, lines, broker, dry_run, journal)
    from webull_bot.execution.forward_options import mark_options

    mark_options(state, actionable, frames, now, lines, broker, dry_run, journal)
    _mark_shadows(state, frames, now, lines, dry_run)
    _mark_spy(state, frames, now, lines, dry_run)

    if not dry_run:
        journal.forward_save(NAME, state)
        journal.event("forward_cycle", lines[-1], {"strategy": NAME, "dry_run": False})
    else:
        lines.append("No broker call.")
    return lines


def _symbol_last(frame: pd.DataFrame, now: datetime):
    done = completed_hourly(frame, now)
    if done.empty:
        return None
    return done.index[-1]


def _known_ids(state: dict, key: str, field: str = "id") -> set[str]:
    return {str(row.get(field)) for row in state.get(key, [])}


def _on_signal(state, setup, frames, now, lines, broker, dry_run, journal) -> None:
    signal_id = _signal_id(setup.symbol, setup.signal_time, setup.direction)
    if signal_id in _known_ids(state, "signals"):
        lines.append(
            f"{NAME} {setup.symbol} {setup.direction} signal {pd.Timestamp(setup.signal_time).isoformat()} "
            "already journaled. Not sent again."
        )
        return
    record = {
        "id": signal_id,
        "symbol": setup.symbol,
        "direction": setup.direction,
        "signal_time": pd.Timestamp(setup.signal_time).isoformat(),
        "stop": float(setup.stop),
        "kind": setup.kind,
    }
    if setup.direction != "long":
        record["status"] = "skipped_short"
        lines.append(
            f"{NAME} {setup.symbol} short signal at {pd.Timestamp(setup.signal_time).isoformat()} "
            "skipped. The sandbox book is long stock only. Not sent."
        )
        if not dry_run:
            state["signals"].append(record)
            journal.forward_save(NAME, state)
        return

    price = _quote(frames.get(setup.symbol), now)
    if price is None:
        lines.append(f"{NAME} {setup.symbol} long signal has no fill price. Not sent.")
        return
    if any(pos["symbol"] == setup.symbol for pos in state["positions"]):
        lines.append(f"{NAME} {setup.symbol} already open. Not sent again.")
        if not dry_run:
            record["status"] = "already_open"
            state["signals"].append(record)
            journal.forward_save(NAME, state)
        return
    if len(state["positions"]) >= MAX_POSITIONS:
        lines.append(f"{NAME} {setup.symbol} skipped. Max {MAX_POSITIONS} positions.")
        if not dry_run:
            record["status"] = "max_positions"
            state["signals"].append(record)
            journal.forward_save(NAME, state)
        return
    used = sum(float(pos["qty"]) * float(pos["entry"]) for pos in state["positions"])
    room = max(0.0, NOTIONAL - used)
    shares = min(whole_shares(price, SLOT), whole_shares(price, room))
    if shares < 1:
        lines.append(
            f"{NAME} {setup.symbol} skipped. One share at {price:.2f} does not fit "
            f"the ${SLOT:,.2f} slot of the ${NOTIONAL:,.0f} book."
        )
        if not dry_run:
            record["status"] = "too_expensive"
            state["signals"].append(record)
            journal.forward_save(NAME, state)
        return

    record["status"] = "ordered" if not dry_run else "dry_run"
    record["shares"] = shares
    record["price"] = price
    lines.append(
        f"{NAME} {setup.symbol} long signal {pd.Timestamp(setup.signal_time).isoformat()}. "
        f"{'Would BUY' if dry_run else 'BUY'} {shares} {setup.symbol} MARKET DAY. "
        f"Notional slot ${SLOT:,.2f} of the ${NOTIONAL:,.0f} whole-share book. "
        f"Fill estimate ${price:.2f}."
    )
    if dry_run:
        payload = trailing_payload(setup.symbol, shares)
        lines.append(
            f"Would place SELL {shares} {setup.symbol} {payload['order_type']} "
            f"{payload['trailing_type']} {payload['trailing_stop_step']} DAY."
        )
        lines.append(
            "If the sandbox rejects that order, the journal keeps a bot-managed 15% trail "
            f"from the fill, plus the {MAX_HOLD_SESSIONS}-session time stop."
        )
        _preview_shadow(state, signal_id, frames, now, lines, shares_hint=shares)
        return

    state["signals"].append(record)
    order = {
        "id": signal_id,
        "symbol": setup.symbol,
        "side": "BUY",
        "qty": shares,
        "order_type": "MARKET",
        "status": "intent",
        "session": to_ny(now).date().isoformat(),
    }
    state["orders"].append(order)
    journal.forward_save(NAME, state)
    buy = Order(
        client_order_id=new_client_order_id(),
        symbol=setup.symbol,
        side=Side.BUY,
        quantity=float(shares),
        order_type=OrderType.MARKET,
        time_in_force=TimeInForce.DAY,
        strategy=NAME,
    )
    try:
        broker.place_order(buy)
    except Exception as exc:
        order["status"] = "rejected"
        order["error"] = str(exc)
        lines.append(f"BUY {setup.symbol} was rejected: {exc}")
        journal.forward_save(NAME, state)
        journal.event("forward_order", lines[-1], {"strategy": NAME, "symbol": setup.symbol})
        return
    order["status"] = "submitted"
    opened_on = to_ny(now).date().isoformat()
    position = {
        "id": signal_id,
        "symbol": setup.symbol,
        "qty": shares,
        "entry": price,
        "opened_on": opened_on,
        "peak": price,
        "trail": "pending",
        "entry_bar": pd.Timestamp(_symbol_last(frames[setup.symbol], now)).isoformat(),
    }
    state["positions"].append(position)
    state["fills"].append(
        {
            "id": signal_id,
            "symbol": setup.symbol,
            "side": "BUY",
            "qty": shares,
            "price": price,
            "time": to_ny(now).isoformat(),
            "estimated": True,
        }
    )
    journal.forward_save(NAME, state)
    journal.event("forward_order", lines[-1], {"strategy": NAME, "symbol": setup.symbol, "qty": shares})
    _place_trail(state, position, now, lines, broker, journal)
    _open_shadow(state, signal_id, frames, now, lines)


def _place_trail(state, position, now, lines, broker, journal) -> None:
    session = to_ny(now).date().isoformat()
    trail_key = f"{position['id']}|{session}"
    if trail_key in state["trails"]:
        lines.append(
            f"Open {position['symbol']} {position['qty']} shares. "
            f"Trail for {session} already placed. No new order."
        )
        return
    shares = int(position["qty"])
    payload = trailing_payload(position["symbol"], shares)
    order = trailing_order(position["symbol"], shares)
    try:
        broker.place_order(order)
    except Exception as exc:
        position["trail"] = "bot"
        state["trails"].append(trail_key)
        lines.append(
            f"Native trail refused ({exc}). Bot-managed 15% trail stored in the journal "
            f"for {position['symbol']}."
        )
        journal.forward_save(NAME, state)
        journal.event("forward_trail", lines[-1], {"strategy": NAME, "symbol": position["symbol"], "mode": "bot"})
        return
    position["trail"] = "native"
    state["trails"].append(trail_key)
    state["orders"].append(
        {
            "id": trail_key,
            "symbol": position["symbol"],
            "side": "SELL",
            "qty": shares,
            "order_type": payload["order_type"],
            "trailing_type": payload["trailing_type"],
            "trailing_stop_step": payload["trailing_stop_step"],
            "time_in_force": "DAY",
            "status": "submitted",
            "session": session,
        }
    )
    lines.append(
        f"Placed SELL {shares} {position['symbol']} {payload['order_type']} "
        f"{payload['trailing_type']} {payload['trailing_stop_step']} DAY."
    )
    journal.forward_save(NAME, state)
    journal.event("forward_trail", lines[-1], {"strategy": NAME, "symbol": position["symbol"], "mode": "native"})


def _mark_open(state, frames, now, lines, broker, dry_run, journal) -> None:
    today = to_ny(now).date()
    still = []
    for position in list(state["positions"]):
        held = _sessions_held(position["opened_on"], today)
        last_bar = position.get("entry_bar")
        current = _symbol_last(frames.get(position["symbol"]), now)
        same_entry_bar = last_bar is not None and current is not None and _same_bar(last_bar, current)
        time_stop = held > MAX_HOLD_SESSIONS or (held == MAX_HOLD_SESSIONS and _is_last_slot(now))
        trail_hit = False
        if not same_entry_bar:
            row = _bar(frames.get(position["symbol"]), now)
            if row is not None:
                high = float(row["high"])
                low = float(row["low"])
                position["peak"] = max(float(position["peak"]), high)
                stop = float(position["peak"]) * (1.0 - TRAIL_PCT)
                trail_hit = low <= stop
        if any(row.get("id") == position["id"] for row in state["exits"]):
            continue
        if time_stop or trail_hit or position.get("exit_status") == "intent":
            reason = position.get("exit_reason") or ("time_stop" if time_stop else "trail")
            if dry_run:
                price = _quote(frames.get(position["symbol"]), now) or float(position["entry"])
                lines.append(
                    f"Would SELL {int(position['qty'])} {position['symbol']} MARKET DAY "
                    f"reason {reason}. Fill estimate ${price:.2f}."
                )
                still.append(position)
                continue
            if _exit_position(state, position, frames, now, reason, lines, broker, journal):
                continue
            still.append(position)
            continue
        if not dry_run and broker is not None:
            _reconcile_fill(position, broker)
            _place_trail(state, position, now, lines, broker, journal)
        elif dry_run:
            session = today.isoformat()
            trail_key = f"{position['id']}|{session}"
            if trail_key in state["trails"]:
                lines.append(
                    f"Open {position['symbol']} {int(position['qty'])} shares. "
                    f"Trail for {session} already placed. No new order."
                )
            else:
                payload = trailing_payload(position["symbol"], int(position["qty"]))
                lines.append(
                    f"Would place SELL {int(position['qty'])} {position['symbol']} {payload['order_type']} "
                    f"{payload['trailing_type']} {payload['trailing_stop_step']} DAY."
                )
        still.append(position)
    state["positions"] = still


def _reconcile_fill(position, broker) -> None:
    positions = getattr(broker, "positions", None)
    if not callable(positions):
        return
    for held in positions():
        if held.symbol == position["symbol"] and held.avg_price:
            position["entry"] = float(held.avg_price)
            if float(position["peak"]) < float(held.avg_price):
                position["peak"] = float(held.avg_price)


def _exit_position(state, position, frames, now, reason, lines, broker, journal) -> bool:
    """Sell and drop the position. A rejected sell leaves it open for the next cycle."""
    price = _quote(frames.get(position["symbol"]), now) or float(position["entry"])
    shares = int(position["qty"])
    position["exit_status"] = "intent"
    position["exit_reason"] = reason
    journal.forward_save(NAME, state)
    if broker is not None:
        for order in list(broker.open_orders()):
            if order.symbol == position["symbol"] and order.client_order_id:
                try:
                    broker.cancel_order(order.client_order_id)
                except Exception:
                    pass
        sell = Order(
            client_order_id=new_client_order_id(),
            symbol=position["symbol"],
            side=Side.SELL,
            quantity=float(shares),
            order_type=OrderType.MARKET,
            time_in_force=TimeInForce.DAY,
            strategy=NAME,
        )
        try:
            broker.place_order(sell)
        except Exception as exc:
            position["exit_status"] = "rejected"
            lines.append(f"SELL {position['symbol']} was rejected: {exc}. Position stays open.")
            journal.forward_save(NAME, state)
            return False
    pnl = (price - float(position["entry"])) * shares
    state["exits"].append(
        {
            "id": position["id"],
            "symbol": position["symbol"],
            "qty": shares,
            "price": price,
            "entry": float(position["entry"]),
            "reason": reason,
            "pnl": pnl,
            "time": to_ny(now).isoformat(),
        }
    )
    state["orders"].append(
        {
            "id": f"exit|{position['id']}",
            "symbol": position["symbol"],
            "side": "SELL",
            "qty": shares,
            "order_type": "MARKET",
            "status": "submitted",
            "reason": reason,
            "session": to_ny(now).date().isoformat(),
        }
    )
    lines.append(
        f"SELL {shares} {position['symbol']} MARKET DAY reason {reason}. "
        f"Fill estimate ${price:.2f}. P&L ${pnl:.2f}."
    )
    journal.forward_save(NAME, state)
    journal.event("forward_exit", lines[-1], {"strategy": NAME, "symbol": position["symbol"], "reason": reason, "pnl": pnl})
    return True


def _preview_shadow(state, signal_id, frames, now, lines, shares_hint: int) -> None:
    symbol = _shadow_symbol(signal_id)
    price = _quote(frames.get(symbol), now)
    if price is None:
        return
    shares = whole_shares(price, SLOT)
    lines.append(
        f"Shadow random entry, seed 17: would track {symbol} at ${price:.2f}, {shares} shares, "
        f"same 15% trail and {MAX_HOLD_SESSIONS}-session time stop. Not sent."
    )
    _ = shares_hint


def _open_shadow(state, signal_id, frames, now, lines) -> None:
    if any(row.get("id") == signal_id for row in state["shadow_positions"]):
        return
    symbol = _shadow_symbol(signal_id)
    price = _quote(frames.get(symbol), now)
    if price is None:
        return
    shares = whole_shares(price, SLOT)
    if shares < 1:
        lines.append(f"Shadow random entry {symbol} does not fit one share in the slot. Not tracked.")
        return
    state["shadow_positions"].append(
        {
            "id": signal_id,
            "symbol": symbol,
            "qty": shares,
            "entry": price,
            "opened_on": to_ny(now).date().isoformat(),
            "peak": price,
            "entry_bar": pd.Timestamp(_symbol_last(frames[symbol], now)).isoformat(),
        }
    )
    lines.append(
        f"Shadow random entry, seed 17: tracking {symbol} at ${price:.2f}, {shares} shares. Not sent."
    )


def _mark_shadows(state, frames, now, lines, dry_run) -> None:
    if dry_run:
        return
    today = to_ny(now).date()
    still = []
    for position in list(state["shadow_positions"]):
        held = _sessions_held(position["opened_on"], today)
        current = _symbol_last(frames.get(position["symbol"]), now)
        same_entry_bar = current is not None and _same_bar(position.get("entry_bar"), current)
        time_stop = held > MAX_HOLD_SESSIONS or (held == MAX_HOLD_SESSIONS and _is_last_slot(now))
        trail_hit = False
        if not same_entry_bar:
            row = _bar(frames.get(position["symbol"]), now)
            if row is not None:
                position["peak"] = max(float(position["peak"]), float(row["high"]))
                trail_hit = float(row["low"]) <= float(position["peak"]) * (1.0 - TRAIL_PCT)
        if time_stop or trail_hit:
            price = _quote(frames.get(position["symbol"]), now) or float(position["entry"])
            pnl = (price - float(position["entry"])) * int(position["qty"])
            state["shadow_exits"].append(
                {
                    "id": position["id"],
                    "symbol": position["symbol"],
                    "qty": int(position["qty"]),
                    "price": price,
                    "entry": float(position["entry"]),
                    "reason": "time_stop" if time_stop else "trail",
                    "pnl": pnl,
                    "time": to_ny(now).isoformat(),
                }
            )
            lines.append(
                f"Shadow random {position['symbol']} exit {('time_stop' if time_stop else 'trail')} "
                f"P&L ${pnl:.2f}. Not sent."
            )
            continue
        still.append(position)
    state["shadow_positions"] = still


def _mark_spy(state, frames, now, lines, dry_run) -> None:
    price = _quote(frames.get("SPY"), now)
    if price is None:
        return
    if state.get("spy") is None:
        shares = whole_shares(price, NOTIONAL)
        verb = "Would mark" if dry_run else "Marked"
        text = (
            f"Shadow SPY buy-and-hold: {verb} {shares} shares from ${price:.2f}. Not sent."
        )
        lines.append(text)
        if dry_run or shares < 1:
            return
        state["spy"] = {
            "shares": shares,
            "entry": price,
            "time": to_ny(now).isoformat(),
            "last": price,
        }
        return
    if dry_run:
        return
    state["spy"]["last"] = price


def render_report(state: dict[str, Any]) -> str:
    """Signals, orders, fills, exits, and the two shadow books."""
    if not state or state == empty_state() or _blank(state):
        return f"No forward-test journal for {NAME} yet.\n"
    lines = [
        f"Forward test {NAME}. Sandbox paper only. Live trading stays off.",
        f"Book: whole shares, ${NOTIONAL:,.0f} notional, max {MAX_POSITIONS} positions, "
        f"trail {TRAIL_PCT:.0%}, time stop {MAX_HOLD_SESSIONS} sessions.",
        "",
        "Signals",
    ]
    if not state["signals"]:
        lines.append("(none)")
    for row in state["signals"]:
        lines.append(
            f"- {row.get('signal_time')} {row.get('symbol')} {row.get('direction')} {row.get('status')}"
        )
    lines.append("")
    lines.append("Orders")
    if not state["orders"]:
        lines.append("(none)")
    for row in state["orders"]:
        extra = row.get("order_type", "")
        if row.get("trailing_type"):
            extra = f"{extra} {row['trailing_type']} {row.get('trailing_stop_step')}"
        lines.append(
            f"- {row.get('session')} {row.get('side')} {row.get('qty')} {row.get('symbol')} "
            f"{extra} {row.get('status')} {row.get('reason') or ''}".rstrip()
        )
    lines.append("")
    lines.append("Fills")
    if not state["fills"]:
        lines.append("(none)")
    for row in state["fills"]:
        lines.append(
            f"- {row.get('time')} {row.get('side')} {row.get('qty')} {row.get('symbol')} "
            f"@ {float(row.get('price') or 0):.2f}"
        )
    lines.append("")
    lines.append("Exits")
    realized = 0.0
    if not state["exits"]:
        lines.append("(none)")
    for row in state["exits"]:
        pnl = float(row.get("pnl") or 0.0)
        realized += pnl
        lines.append(
            f"- {row.get('time')} {row.get('symbol')} {row.get('qty')} reason {row.get('reason')} "
            f"@ {float(row.get('price') or 0):.2f} P&L ${pnl:.2f}"
        )
    open_pnl = 0.0
    lines.append("")
    lines.append("Open positions")
    if not state["positions"]:
        lines.append("(none)")
    for row in state["positions"]:
        last = float(row.get("peak") or row.get("entry") or 0.0)
        pnl = (last - float(row["entry"])) * int(row["qty"])
        open_pnl += pnl
        lines.append(
            f"- {row.get('symbol')} {row.get('qty')} entry {float(row['entry']):.2f} "
            f"peak {float(row.get('peak') or 0):.2f} trail {row.get('trail')} open P&L ${pnl:.2f}"
        )
    shadow_realized = sum(float(row.get("pnl") or 0.0) for row in state["shadow_exits"])
    shadow_open = 0.0
    for row in state["shadow_positions"]:
        shadow_open += (float(row.get("peak") or row["entry"]) - float(row["entry"])) * int(row["qty"])
    lines.append("")
    lines.append(f"Chop book realized P&L ${realized:.2f}. Open P&L ${open_pnl:.2f}.")
    lines.append(
        f"Random-entry shadow, seed 17, same 15% trail and {MAX_HOLD_SESSIONS}-session time stop: "
        f"realized ${shadow_realized:.2f}, open ${shadow_open:.2f}. Not sent."
    )
    spy = state.get("spy")
    if not spy:
        lines.append("SPY buy-and-hold: not started.")
    else:
        pnl = (float(spy["last"]) - float(spy["entry"])) * int(spy["shares"])
        lines.append(
            f"SPY buy-and-hold: {int(spy['shares'])} shares from ${float(spy['entry']):.2f} "
            f"marked ${float(spy['last']):.2f}, P&L ${pnl:.2f}. Not sent."
        )
    from webull_bot.execution.forward_options import option_lines

    extra = option_lines(state)
    if extra:
        lines.append("")
        lines.extend(extra)
    lines.append("")
    return "\n".join(lines)


def _blank(state: dict) -> bool:
    return not any(
        state.get(key)
        for key in (
            "signals",
            "orders",
            "fills",
            "exits",
            "positions",
            "shadow_positions",
            "shadow_exits",
            "spy",
            "option_signals",
            "option_orders",
            "option_fills",
            "option_exits",
            "option_positions",
        )
    )


def report_text(journal: Journal) -> str:
    return render_report(load_state(journal))
