"""Options sub-book for the sandbox chop-breakout forward test.

The ladder is the corrected one. Contracts 1-4 keep the initial -20%
premium stop. Only the runner moves to break-even, and only after the
+15% tier fills. Each tier is its own option LIMIT sell. Stops are
bot-managed. There is no option OCO, and a stop sells only contracts the
journal still shows open.

The premium is the same Black-Scholes model as the backtest, not a Webull
quote. Five contracts are taken only when the debit fits in $1,000. Longs
buy calls. Shorts buy puts. The share book does not send those shorts.
"""

from __future__ import annotations

import copy
from datetime import date, timedelta
from typing import Any, Optional

import pandas as pd

from webull_bot.broker.webull import build_single_option_order, new_client_order_id
from webull_bot.calendar import to_ny
from webull_bot.chart_reads.premium_scale import (
    CORRECTED_DELTA,
    CORRECTED_DTE,
    CORRECTED_STOP,
    SCALE_CONTRACTS,
    SCALE_TIERS,
    apply_scale_bar,
    new_state,
)
from webull_bot.chart_reads.simulate import (
    DIVIDEND,
    RATE,
    _buy,
    _option_bid,
    _realized,
    _right_strike,
    _vol,
    _years,
)
from webull_bot.execution.forward_chop import (
    MAX_HOLD_SESSIONS,
    _bar,
    _is_last_slot,
    _quote,
    _sessions_held,
    _signal_id,
)
from webull_bot.mtf_vwap.detect import rth
from webull_bot.options.fees import CONTRACT_MULTIPLIER, option_leg_fees

OPTION_CASH = 1_000.0
OPTION_MAX_POSITIONS = 3
IV_PREMIUM = 1.15
SPREAD_MULTIPLIER = 1.0


def option_lines(state: dict[str, Any]) -> list[str]:
    """Separate block for the forward-test report."""
    signals = state.get("option_signals") or []
    orders = state.get("option_orders") or []
    fills = state.get("option_fills") or []
    exits = state.get("option_exits") or []
    positions = state.get("option_positions") or []
    if not any((signals, orders, fills, exits, positions)):
        return []
    lines = [
        "Options sub-book. Corrected five-contract ladder. Sandbox paper only.",
        (
            f"21 DTE, delta {CORRECTED_DELTA:.2f}, initial stop {CORRECTED_STOP:.0%}. "
            "Break-even is the runner only, after the +15% tier. "
            f"Five contracts only when the debit fits in ${OPTION_CASH:,.0f}."
        ),
        "Signals",
    ]
    lines.extend(_rows(signals, lambda row: f"- {row.get('signal_time')} {row.get('symbol')} {row.get('right')} {row.get('status')}"))
    lines.append("Orders")
    lines.extend(
        _rows(
            orders,
            lambda row: (
                f"- {row.get('session')} {row.get('side')} {row.get('qty')} {row.get('symbol')} "
                f"{row.get('right')} {row.get('order_type')} {row.get('limit') or ''} {row.get('status')}"
            ).rstrip(),
        )
    )
    lines.append("Fills")
    lines.extend(
        _rows(
            fills,
            lambda row: (
                f"- {row.get('time')} {row.get('side')} {row.get('qty')} {row.get('symbol')} "
                f"{row.get('right')} @ {float(row.get('price') or 0):.2f} {row.get('reason') or ''}"
            ).rstrip(),
        )
    )
    lines.append("Exits")
    realized = 0.0
    if not exits:
        lines.append("(none)")
    for row in exits:
        pnl = float(row.get("pnl") or 0.0)
        realized += pnl
        lines.append(
            f"- {row.get('time')} {row.get('symbol')} {row.get('right')} reason {row.get('reason')} "
            f"runner {row.get('runner')} P&L ${pnl:.2f}"
        )
    lines.append("Open option positions")
    if not positions:
        lines.append("(none)")
    for row in positions:
        lines.append(
            f"- {row.get('symbol')} {row.get('right')} {row.get('qty_open')} open, "
            f"entry {float(row.get('entry') or 0):.2f}, runner stop {row.get('runner_stop')}"
        )
    lines.append(f"Options book realized P&L ${realized:.2f}. Not part of the share book.")
    lines.append("")
    return lines


def mark_options(state, setups, frames, now, lines, broker, dry_run, journal) -> None:
    """One cycle of the options book. Dry-run prints and does not write or send."""
    _ensure(state)
    lines.append(
        "Options sub-book, corrected ladder. Sandbox paper only. "
        "Each tier is its own option LIMIT sell. Stops are bot-managed. No option OCO."
    )
    _mark_open_options(state, frames, now, lines, broker, dry_run, journal)
    for setup in setups:
        _on_option(state, setup, frames, now, lines, broker, dry_run, journal)


def _ensure(state: dict) -> None:
    for key in ("option_signals", "option_orders", "option_fills", "option_exits", "option_positions"):
        state.setdefault(key, [])


def _rows(rows, render) -> list[str]:
    if not rows:
        return ["(none)"]
    return [render(row) for row in rows]


def _known(state, key) -> set[str]:
    return {str(row.get("id")) for row in state.get(key, [])}


def _daily_from_hourly(frames) -> dict[str, pd.DataFrame]:
    daily = {}
    for symbol, frame in frames.items():
        bars = rth(frame) if frame is not None else None
        if bars is None or bars.empty:
            continue
        grouped = bars.groupby(bars.index.date).agg(
            open=("open", "first"),
            high=("high", "max"),
            low=("low", "min"),
            close=("close", "last"),
            volume=("volume", "sum"),
        )
        grouped.index = pd.to_datetime(grouped.index)
        daily[symbol] = grouped
    return daily


def _contract(frame, symbol: str, direction: str, now, rv) -> Optional[dict]:
    spot = _quote(frame, now)
    if spot is None:
        return None
    sigma = _vol(rv.get(symbol, pd.Series(dtype=float)), to_ny(now).date(), IV_PREMIUM)
    if sigma is None:
        return None
    years = _years(CORRECTED_DTE, pd.Timestamp(to_ny(now)))
    right, strike, _raw, years = _right_strike(direction, spot, years, sigma, CORRECTED_DELTA)
    from webull_bot.options.pricing import option_delta, option_price

    mid = option_price(right, spot, strike, years, sigma, RATE, DIVIDEND)
    delta = option_delta(right, spot, strike, years, sigma, RATE, DIVIDEND)
    ask = _buy(mid, delta, SPREAD_MULTIPLIER)
    if ask <= 0:
        return None
    fees = option_leg_fees(SCALE_CONTRACTS, ask, sell=False)
    debit = SCALE_CONTRACTS * ask * CONTRACT_MULTIPLIER + fees
    expiry = (to_ny(now).date() + timedelta(days=CORRECTED_DTE)).isoformat()
    return {
        "right": right,
        "option_type": "CALL" if right == "call" else "PUT",
        "strike": float(strike),
        "expiry": expiry,
        "ask": float(ask),
        "debit": float(debit),
        "sigma": float(sigma),
        "delta": float(delta),
        "years": float(years),
        "spot": float(spot),
    }


def _on_option(state, setup, frames, now, lines, broker, dry_run, journal) -> None:
    signal_id = _signal_id(setup.symbol, setup.signal_time, setup.direction) + "|option"
    if signal_id in _known(state, "option_signals"):
        lines.append(
            f"Option {setup.symbol} {setup.direction} signal already journaled. Not sent again."
        )
        return
    if any(row["symbol"] == setup.symbol and row["direction"] == setup.direction for row in state["option_positions"]):
        lines.append(f"Option {setup.symbol} {setup.direction} already open. Not sent again.")
        return
    if len(state["option_positions"]) >= OPTION_MAX_POSITIONS:
        lines.append(f"Option {setup.symbol} skipped. Max {OPTION_MAX_POSITIONS} option positions.")
        return
    rv = _realized(_daily_from_hourly(frames))
    contract = _contract(frames.get(setup.symbol), setup.symbol, setup.direction, now, rv)
    record = {
        "id": signal_id,
        "symbol": setup.symbol,
        "direction": setup.direction,
        "signal_time": pd.Timestamp(setup.signal_time).isoformat(),
    }
    if contract is None:
        lines.append(
            f"Option {setup.symbol} {setup.direction} has no modeled premium. Not sent."
        )
        return
    record["right"] = contract["option_type"]
    if contract["debit"] > OPTION_CASH:
        lines.append(
            f"Option {setup.symbol} {contract['option_type']} skipped. "
            f"Five contracts cost ${contract['debit']:.2f}, above the ${OPTION_CASH:,.0f} sub-book."
        )
        if not dry_run:
            record["status"] = "too_expensive"
            state["option_signals"].append(record)
            journal.forward_save(_name(), state)
        return
    verb = "Would BUY" if dry_run else "BUY"
    lines.append(
        f"{verb} {SCALE_CONTRACTS} {setup.symbol} {contract['option_type']} "
        f"strike {contract['strike']:.2f} expiry {contract['expiry']} LIMIT {contract['ask']:.2f} DAY. "
        f"Modeled ask, not a Webull quote. Debit ${contract['debit']:.2f}."
    )
    for pct, qty in SCALE_TIERS:
        limit = contract["ask"] * (1.0 + pct)
        place = "Would place" if dry_run else "Place"
        lines.append(
            f"{place} SELL {qty} {setup.symbol} {contract['option_type']} LIMIT {limit:.2f} DAY "
            f"({pct:.0%} of the premium)."
        )
    lines.append(
        f"Bot-managed stop: contracts 1-4 stay at {contract['ask'] * (1.0 + CORRECTED_STOP):.2f} "
        f"({CORRECTED_STOP:.0%}). The runner stays there until the +15% tier fills, then "
        f"its stop is break-even {contract['ask']:.2f}. A stop sells only contracts still open."
    )
    if dry_run:
        return
    scale = new_state(contract["ask"], "scale", "premium", CORRECTED_STOP)
    position = {
        "id": signal_id,
        "symbol": setup.symbol,
        "direction": setup.direction,
        "right": contract["right"],
        "option_type": contract["option_type"],
        "strike": contract["strike"],
        "expiry": contract["expiry"],
        "entry": contract["ask"],
        "debit": contract["debit"],
        "sigma": contract["sigma"],
        "years": contract["years"],
        "opened_at": to_ny(now).isoformat(),
        "qty_open": SCALE_CONTRACTS,
        "runner_stop": contract["ask"] * (1.0 + CORRECTED_STOP),
        "scale": scale,
        "last_bar": None,
        "limits": [],
        "opened_on": to_ny(now).date().isoformat(),
    }
    if not _place_option_orders(state, position, now, lines, broker, journal, include_entry=True):
        lines.append(f"Option entry for {setup.symbol} was not opened. Not tracked. Not sent again this attempt.")
        return
    record["status"] = "ordered"
    state["option_signals"].append(record)
    state["option_positions"].append(position)
    journal.forward_save(_name(), state)
    _step_position(state, position, frames, now, lines, broker, dry_run, journal, entry_bar=True)
    if position["scale"].get("done"):
        state["option_positions"] = [row for row in state["option_positions"] if row["id"] != position["id"]]
        journal.forward_save(_name(), state)


def _mark_open_options(state, frames, now, lines, broker, dry_run, journal) -> None:
    still = []
    for position in list(state["option_positions"]):
        if any(row.get("id") == position["id"] for row in state["option_exits"]):
            continue
        if not dry_run:
            _place_option_orders(state, position, now, lines, broker, journal, include_entry=False)
        _step_position(state, position, frames, now, lines, broker, dry_run, journal, entry_bar=False)
        if not position["scale"].get("done"):
            position["qty_open"] = int(position["scale"]["remaining"])
            position["runner_stop"] = position["scale"].get("runner_stop") or position["scale"].get("stop_px")
            still.append(position)
    state["option_positions"] = still


def _step_position(state, position, frames, now, lines, broker, dry_run, journal, entry_bar: bool) -> None:
    frame = frames.get(position["symbol"])
    row = _bar(frame, now) if frame is not None else None
    if row is None:
        return
    bar_id = pd.Timestamp(_bar_index(frame, now)).isoformat()
    if position.get("last_bar") == bar_id:
        lines.append(f"Option {position['symbol']} already marked for {bar_id}. No new order.")
        return
    quotes = _quotes(position, row, entry_bar)
    if quotes is None:
        return
    before = copy.deepcopy(position["scale"])
    reason = apply_scale_bar(
        position["scale"],
        quotes,
        entry_bar=entry_bar,
        terminal=_terminal(position, now, entry_bar),
    )
    position["last_bar"] = bar_id
    _journal_scale_diff(state, position, before, quotes, now, lines, broker, dry_run, journal, reason)


def _bar_index(frame, now):
    from webull_bot.execution.forward_chop import completed_hourly

    done = completed_hourly(frame, now)
    return done.index[-1]


def _terminal(position, now, entry_bar: bool) -> Optional[str]:
    """Same five-session clock as the share book, and the 21 DTE expiry."""
    if entry_bar:
        return None
    today = to_ny(now).date()
    opened = position.get("opened_on") or to_ny(pd.Timestamp(position["opened_at"])).date().isoformat()
    held = _sessions_held(opened, today)
    expiry = date_from(position.get("expiry"))
    last = _is_last_slot(now)
    if expiry is not None and (today > expiry or (today == expiry and last)):
        return "expiry"
    if held > MAX_HOLD_SESSIONS or (held == MAX_HOLD_SESSIONS and last):
        return "time_stop"
    return None


def date_from(value) -> Optional[date]:
    if not value:
        return None
    return date.fromisoformat(str(value)[:10])


def _aware(value) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        return ts.tz_localize("America/New_York")
    return ts.tz_convert("America/New_York")


def _quotes(position, row, entry_bar: bool) -> Optional[dict]:
    try:
        open_ = float(row["open"])
        high = float(row["high"])
        low = float(row["low"])
        close = float(row["close"])
    except (TypeError, ValueError, KeyError):
        return None
    pos = {
        "right": position["right"],
        "strike": position["strike"],
        "sigma": position["sigma"],
        "expiry_years": position["years"],
        "entry_time": _aware(position["opened_at"]),
        "direction": position["direction"],
    }
    params = {"spread_multiplier": SPREAD_MULTIPLIER}
    ts = _aware(getattr(row, "name", None) or position["opened_at"])
    if position["direction"] == "long":
        adverse, favorable = low, high
    else:
        adverse, favorable = high, low
    return {
        "open_bid": _option_bid(pos, ts, open_, params),
        "adverse_bid": _option_bid(pos, ts, adverse, params),
        "favorable_bid": _option_bid(pos, ts, favorable, params),
        "close_bid": _option_bid(pos, ts, close, params),
        "underlying_hit": False,
        "underlying_bid": 0.0,
        "entry_bar": entry_bar,
    }


def _journal_scale_diff(state, position, before, quotes, now, lines, broker, dry_run, journal, reason) -> None:
    after = position["scale"]
    limit_adds = []
    limit_qty = 0
    for key, qty in after["sold"].items():
        added = int(qty) - int(before["sold"].get(key, 0))
        if added > 0:
            limit_qty += added
            price = float(position["entry"]) * (1.0 + float(key))
            limit_adds.append((added, price, f"limit {float(key):.0%}", f"{position['id']}|limit|{position.get('last_bar')}|{key}"))
    stopped = (int(before["remaining"]) - int(after["remaining"])) - limit_qty
    runner_only = False
    stop_price = float(quotes["adverse_bid"])
    stop_reason = reason or "initial_stop"
    if stopped > 0:
        runner_only = (
            after.get("runner") == "breakeven"
            and before.get("runner") != "breakeven"
            and stopped == int(before.get("runner_open") or 0)
        )
        if reason in {"time_stop", "expiry", "window_end"}:
            stop_price = float(quotes["close_bid"])
            stop_reason = reason
        elif runner_only:
            stop_price = min(float(quotes["adverse_bid"]), float(position["entry"]))
            stop_reason = "breakeven"
        else:
            stop_reason = "initial_stop" if reason in {None, "initial_stop"} else str(reason)
        sent = _stop_sell(
            state,
            position,
            before,
            stopped,
            stop_price,
            stop_reason,
            now,
            lines,
            broker,
            dry_run,
            journal,
            runner_only=runner_only,
        )
        if not dry_run and not sent:
            position["scale"] = before
            position["last_bar"] = None
            lines.append(
                f"Option stop for {position['symbol']} was not sent. "
                "This bar stays unmarked so the next cycle can retry. Contracts already sold are not sold again."
            )
            journal.forward_save(_name(), state)
            return
    for added, price, fill_reason, key in limit_adds:
        _fill(state, position, added, price, fill_reason, now, lines, dry_run, key)
    if stopped > 0:
        _record_stop_fill(state, position, stopped, stop_price, stop_reason, now, dry_run)
    if after.get("done") and not any(row.get("id") == position["id"] for row in state["option_exits"]):
        pnl = float(after["credit"]) - float(position["debit"])
        state["option_exits"].append(
            {
                "id": position["id"],
                "symbol": position["symbol"],
                "right": position["option_type"],
                "reason": after.get("reason"),
                "runner": after.get("runner"),
                "pnl": pnl,
                "time": to_ny(now).isoformat(),
            }
        )
        lines.append(
            f"Option {position['symbol']} {position['option_type']} closed reason {after.get('reason')} "
            f"runner {after.get('runner')}. P&L ${pnl:.2f}."
        )
    if not dry_run:
        position["qty_open"] = int(position["scale"]["remaining"])
        journal.forward_save(_name(), state)


def _fill(state, position, qty, price, reason, now, lines, dry_run, key: str) -> None:
    if any(row.get("key") == key for row in state["option_fills"]):
        lines.append(
            f"Option limit fill {qty} {position['symbol']} already journaled ({reason}). Not sent again."
        )
        return
    lines.append(
        f"Option limit fill {qty} {position['symbol']} {position['option_type']} @ {price:.2f} ({reason}). "
        "The resting LIMIT is the sell. Not sent again."
    )
    if dry_run:
        return
    state["option_fills"].append(
        {
            "id": position["id"],
            "key": key,
            "time": to_ny(now).isoformat(),
            "side": "SELL",
            "qty": qty,
            "symbol": position["symbol"],
            "right": position["option_type"],
            "price": price,
            "reason": reason,
        }
    )


def _record_stop_fill(state, position, qty, price, reason, now, dry_run) -> None:
    key = f"{position['id']}|stop|{position.get('last_bar')}|{reason}|{qty}"
    if any(row.get("key") == key for row in state["option_fills"]):
        return
    if dry_run:
        return
    state["option_fills"].append(
        {
            "id": position["id"],
            "key": key,
            "time": to_ny(now).isoformat(),
            "side": "SELL",
            "qty": qty,
            "symbol": position["symbol"],
            "right": position["option_type"],
            "price": price,
            "reason": reason,
        }
    )


def _stop_sell(state, position, before, qty, price, reason, now, lines, broker, dry_run, journal, runner_only: bool) -> bool:
    verb = "Would SELL" if dry_run else "SELL"
    lines.append(
        f"{verb} {qty} {position['symbol']} {position['option_type']} LIMIT {price:.2f} DAY "
        f"bot stop {reason}. Only contracts still open. Not an OCO."
    )
    if dry_run:
        return True
    key = f"{position['id']}|stop|{position.get('last_bar')}|{reason}|{qty}"
    already = any(
        row.get("key") == key and row.get("status") in {"intent", "submitted"} for row in state["option_orders"]
    )
    if not already:
        _cancel_stopped_limits(broker, position, before, runner_only)
    return _send(state, position, None, "stop", now, lines, broker, journal, key=key, qty=qty, limit=price)


def _place_option_orders(state, position, now, lines, broker, journal, include_entry: bool) -> bool:
    session = to_ny(now).date().isoformat()
    if include_entry:
        opened = _send(
            state,
            position,
            None,
            "entry",
            now,
            lines,
            broker,
            journal,
            key=f"{position['id']}|entry",
            qty=SCALE_CONTRACTS,
            limit=float(position["entry"]),
            intent="BUY_TO_OPEN",
        )
        if not opened:
            return False
    scale = position["scale"]
    if scale.get("done"):
        return True
    for tier in scale["tiers"]:
        key = f"{position['id']}|{tier['pct']}|{session}"
        if key in position["limits"]:
            continue
        sent = _send(
            state,
            position,
            None,
            "limit",
            now,
            lines,
            broker,
            journal,
            key=key,
            qty=int(tier["qty"]),
            limit=float(tier["limit"]),
        )
        order = next(row for row in reversed(state["option_orders"]) if row.get("key") == key)
        if sent or order.get("status") == "rejected":
            tier["order_id"] = order["id"]
            position["limits"].append(key)
    return True


def _payload(position, side: str, qty: int, limit: float, intent: str) -> dict:
    return build_single_option_order(
        client_order_id=new_client_order_id(),
        symbol=position["symbol"],
        side=side,
        quantity=float(qty),
        strike_price=float(position["strike"]),
        option_expire_date=position["expiry"],
        option_type=position["option_type"],
        limit_price=float(limit),
        order_type="LIMIT",
        time_in_force="DAY",
        position_intent=intent,
    )


def _send(
    state,
    position,
    payload,
    kind,
    now,
    lines,
    broker,
    journal,
    *,
    key: str,
    qty: int,
    limit: float,
    intent: str = "SELL_TO_CLOSE",
) -> bool:
    """Save the intent before the broker call so a retry cannot sell the same contracts twice."""
    side = "BUY" if intent == "BUY_TO_OPEN" else "SELL"
    existing = next((row for row in state["option_orders"] if row.get("key") == key), None)
    if existing and existing.get("status") in {"intent", "submitted"}:
        lines.append(f"Option {kind} for {position['symbol']} already journaled. Not sent again.")
        return True
    if existing is None:
        client_id = new_client_order_id()
        order = {
            "id": client_id,
            "key": key,
            "session": to_ny(now).date().isoformat(),
            "side": side,
            "qty": str(int(qty)),
            "symbol": position["symbol"],
            "right": position["option_type"],
            "order_type": "LIMIT",
            "limit": f"{float(limit):.2f}",
            "status": "intent",
            "kind": kind,
        }
        state["option_orders"].append(order)
    else:
        order = existing
        order["status"] = "intent"
        client_id = order["id"]
    journal.forward_save(_name(), state)
    sender = getattr(broker, "place_option_order", None)
    if sender is None:
        order["status"] = "not_sent"
        lines.append(f"Option {kind} for {position['symbol']} was not sent. The broker has no option order path.")
        journal.forward_save(_name(), state)
        return False
    built = payload or _payload(position, side, int(qty), float(limit), intent)
    built["client_order_id"] = client_id
    try:
        sender(built)
    except Exception as exc:
        order["status"] = "rejected"
        order["error"] = str(exc)
        lines.append(f"Option {kind} for {position['symbol']} was rejected: {exc}")
        journal.forward_save(_name(), state)
        return False
    order["status"] = "submitted"
    journal.forward_save(_name(), state)
    return True


def _cancel_stopped_limits(broker, position, before, runner_only: bool) -> None:
    """Cancel the limits this stop replaces. Leave the share book's orders alone."""
    if broker is None or not hasattr(broker, "cancel_order"):
        return
    for tier in before.get("tiers") or []:
        if runner_only and tier.get("role") != "runner":
            continue
        order_id = tier.get("order_id")
        if not order_id:
            continue
        try:
            broker.cancel_order(order_id)
        except Exception:
            pass
        position["limits"] = [key for key in position.get("limits", []) if not key.startswith(f"{position['id']}|{tier['pct']}|")]


def _name() -> str:
    from webull_bot.execution.forward_chop import NAME

    return NAME
