"""Replay Chart Fanatics signals through the paper broker.

Long orders use ``PaperBroker`` fills, protective stops, and the account
daily-loss flatten. Short signals are counted and not sent. Futures and
crypto prints reserve margin (notional divided by leverage) so one
contract-sized position can exist on the paper cash ledger. That leverage
is off for stock replay. Nothing here calls Webull.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from webull_bot.broker.paper import PaperBroker
from webull_bot.broker.webull import new_client_order_id
from webull_bot.execution.session import _session_day
from webull_bot.fanatics.data import INSTRUMENTS
from webull_bot.fanatics.simulate import Signal, _contracts
from webull_bot.journal.store import Journal
from webull_bot.models import Order, OrderType, Side, TimeInForce
from webull_bot.risk.manager import RiskLimits, RiskState, circuit_update

# Enough to reserve initial margin for one or two index contracts on a
# $100,000 paper ledger. Stock replay does not use this.
FUTURES_LEVERAGE = 20.0


def replay_signals(
    frames: dict[str, pd.DataFrame],
    signals: list[Signal],
    broker: PaperBroker,
    journal: Journal,
    limits: RiskLimits,
    *,
    strategy: str,
    risk: float,
    trade_start,
    max_open: int = 4,
) -> dict[str, Any]:
    """Walk execution bars in time order and send long signals only."""
    start_day = pd.Timestamp(trade_start).date()
    indexed: dict[str, list[tuple[int, Signal]]] = {symbol: [] for symbol in frames}
    shorts = 0
    for signal in signals:
        frame = frames.get(signal.symbol)
        if frame is None:
            continue
        fill_loc = signal.signal_loc if signal.limit_entry is not None else signal.signal_loc + 1
        if fill_loc >= len(frame) or fill_loc < 0:
            continue
        if _session_day(frame.index[fill_loc]) < start_day:
            continue
        if signal.side < 0:
            shorts += 1
            continue
        indexed.setdefault(signal.symbol, []).append((fill_loc, signal))
    for rows in indexed.values():
        rows.sort(key=lambda item: item[0])

    events: list[tuple[pd.Timestamp, str, int]] = []
    for symbol, frame in frames.items():
        for loc, ts in enumerate(frame.index):
            if _session_day(ts) < start_day:
                continue
            events.append((pd.Timestamp(ts), symbol, loc))
    events.sort(key=lambda item: (item[0], item[1]))

    opening = broker.snapshot()
    peak = opening.equity
    drawdown_halt = False
    current_day = None
    day_start = opening.equity
    flattened_today = False
    live: dict[str, dict] = {}
    orders_n = 0
    fills_n = 0
    rejected: dict[str, int] = {}
    triggers: list[dict[str, str]] = []
    closed: list[dict[str, float]] = []
    equity_curve: list[float] = []
    open_lots: dict[str, dict] = {}
    cursor = {symbol: 0 for symbol in indexed}

    def _realize(fills) -> None:
        nonlocal fills_n
        fills_n += len(fills)
        for fill in fills:
            journal.trade(
                symbol=fill.symbol,
                strategy=fill.strategy,
                side=fill.side.value,
                quantity=fill.quantity,
                price=fill.price,
                fees=fill.fees,
                pnl=None,
                reason=fill.reason,
                mode="paper",
            )
            if fill.side == Side.BUY:
                open_lots[fill.symbol] = {"price": fill.price, "qty": fill.quantity, "fees": fill.fees}
                continue
            lot = open_lots.pop(fill.symbol, None)
            if lot is None:
                continue
            qty = min(float(fill.quantity), float(lot["qty"]))
            pnl = (float(fill.price) - float(lot["price"])) * qty - float(fill.fees) - float(lot["fees"])
            closed.append({"symbol": fill.symbol, "pnl": pnl})

    grouped: dict[pd.Timestamp, list[tuple[str, int]]] = {}
    for ts, symbol, loc in events:
        grouped.setdefault(ts, []).append((symbol, loc))

    for ts in sorted(grouped):
        session = _session_day(ts)
        broker.mark_prices(
            {symbol: float(frames[symbol].iloc[loc]["open"]) for symbol, loc in grouped[ts]}
        )
        if session != current_day:
            current_day = session
            day_start = broker.snapshot().equity
            flattened_today = False
        for symbol, loc in grouped[ts]:
            frame = frames[symbol]
            bar = frame.iloc[loc]
            state = live.get(symbol)
            if state is not None and state.get("close_stop_armed"):
                _realize(broker.fill_exit(symbol, float(bar["open"]), "close_stop"))
                live.pop(symbol, None)
                state = None
            elif state is not None and loc == state["time_exit"] and loc != state["entry_loc"]:
                _realize(broker.fill_exit(symbol, float(bar["open"]), "time"))
                live.pop(symbol, None)
                state = None
            if state is None and not flattened_today and not drawdown_halt:
                signal = _pop_signal(indexed[symbol], cursor, symbol, loc)
                if signal is not None:
                    _submit(
                        broker,
                        signal,
                        frame,
                        loc,
                        limits_open=max_open,
                        risk=risk,
                        strategy=strategy,
                        rejected=rejected,
                        live_ready=live,
                    )
            pending = live.pop(f"_pending_{symbol}", None)
            if pending is not None:
                orders_n += 1
            fills = broker.process_bar(symbol, float(bar["open"]), float(bar["high"]), float(bar["low"]), float(bar["close"]))
            _realize(fills)
            bought = any(fill.side == Side.BUY and fill.symbol == symbol for fill in fills)
            if pending is not None and bought:
                entry = next(fill.price for fill in fills if fill.side == Side.BUY and fill.symbol == symbol)
                live[symbol] = _arm(pending, loc, float(entry))
            elif pending is not None:
                for order in broker.open_orders():
                    if order.symbol == symbol:
                        broker.cancel_order(order.client_order_id)
                rejected["unfilled"] = rejected.get("unfilled", 0) + 1
            state = live.get(symbol)
            if state is None:
                continue
            if loc == state["time_exit"] == state["entry_loc"]:
                _realize(broker.fill_exit(symbol, float(bar["close"]), "time"))
                live.pop(symbol, None)
                continue
            if state["close_stop"] is not None and float(bar["close"]) < state["close_stop"]:
                state["close_stop_armed"] = True
            if state["be_level"] is not None and not state["be_done"] and float(bar["high"]) >= state["be_level"]:
                broker.update_stop(symbol, state["entry"])
                state["be_done"] = True
                state["be_level"] = None
        snap = broker.snapshot()
        updated = circuit_update(
            RiskState(
                equity=snap.equity,
                cash=snap.cash,
                peak_equity=peak,
                day_start_equity=day_start,
                positions=snap.positions,
                drawdown_halt=drawdown_halt,
            ),
            limits,
        )
        peak = updated.peak_equity
        drawdown_halt = updated.drawdown_halt
        daily_hit = day_start > 0 and (1.0 - snap.equity / day_start) >= limits.daily_max_loss_pct - 1e-12
        if daily_hit and limits.flatten_on_daily_loss and not flattened_today:
            flattened_today = True
            triggers.append({"session": session.isoformat(), "kind": "daily_loss"})
            if snap.positions or broker.open_orders():
                _realize(broker.flatten())
                live.clear()
            journal.event("kill", "paper daily-loss flatten", {"session": session.isoformat(), "strategy": strategy})
        elif updated.drawdown_halt and limits.flatten_on_max_drawdown and not flattened_today:
            if snap.positions or broker.open_orders():
                flattened_today = True
                triggers.append({"session": session.isoformat(), "kind": "drawdown"})
                _realize(broker.flatten())
                live.clear()
                journal.event("kill", "paper drawdown flatten", {"session": session.isoformat(), "strategy": strategy})
        equity_curve.append(broker.snapshot().equity)

    if broker.positions() or broker.open_orders():
        _realize(broker.flatten())
    snap = broker.snapshot()
    wins = [row for row in closed if row["pnl"] > 0]
    peak_eq = opening.equity
    worst = 0.0
    for value in equity_curve:
        peak_eq = max(peak_eq, value)
        if peak_eq > 0:
            worst = min(worst, value / peak_eq - 1.0)
    return {
        "orders": orders_n,
        "fills": fills_n,
        "closed_trades": len(closed),
        "pnl": snap.equity - opening.equity,
        "ending_equity": snap.equity,
        "win_rate": (len(wins) / len(closed)) if closed else 0.0,
        "max_drawdown": worst,
        "risk_triggers": triggers,
        "rejected": rejected,
        "shorts_not_sent": shorts,
        "positions": [pos.symbol for pos in snap.positions],
    }


def _pop_signal(rows: list[tuple[int, Signal]], cursor: dict[str, int], symbol: str, loc: int) -> Signal | None:
    index = cursor.get(symbol, 0)
    while index < len(rows) and rows[index][0] < loc:
        index += 1
    cursor[symbol] = index
    if index < len(rows) and rows[index][0] == loc:
        cursor[symbol] = index + 1
        return rows[index][1]
    return None


def _submit(
    broker: PaperBroker,
    signal: Signal,
    frame: pd.DataFrame,
    loc: int,
    *,
    limits_open: int,
    risk: float,
    strategy: str,
    rejected: dict[str, int],
    live_ready: dict,
) -> None:
    if any(pos.symbol == signal.symbol for pos in broker.positions()):
        rejected["already in a position"] = rejected.get("already in a position", 0) + 1
        return
    if len(broker.positions()) + len([key for key in live_ready if str(key).startswith("_pending_")]) >= limits_open:
        rejected["max open"] = rejected.get("max open", 0) + 1
        return
    spec = INSTRUMENTS.get(signal.symbol) or {"tick": 0.01, "point_value": 1.0, "usd_quote": True}
    raw_open = float(frame["open"].iloc[loc])
    tick = float(spec["tick"])
    entry = raw_open + tick
    if signal.stop >= entry:
        rejected["fill through stop"] = rejected.get("fill through stop", 0) + 1
        return
    equity = broker.snapshot().equity
    contracts = _contracts(spec, equity, entry, signal.stop, risk, etf=False)
    if contracts <= 0:
        rejected["position size rounded to zero"] = rejected.get("position size rounded to zero", 0) + 1
        return
    if spec.get("fractional"):
        quantity = float(contracts)
    else:
        quantity = float(contracts) * float(spec["point_value"])
    order = Order(
        client_order_id=new_client_order_id(),
        symbol=signal.symbol,
        side=Side.BUY,
        quantity=quantity,
        order_type=OrderType.MARKET,
        time_in_force=TimeInForce.DAY,
        stop_price=float(signal.stop),
        strategy=strategy,
    )
    broker.place_order(order)
    if signal.target and signal.target > 0:
        broker.place_order(
            Order(
                client_order_id=new_client_order_id(),
                symbol=signal.symbol,
                side=Side.SELL,
                quantity=quantity,
                order_type=OrderType.LIMIT,
                time_in_force=TimeInForce.GTC,
                limit_price=float(signal.target),
                strategy=strategy,
            )
        )
    live_ready[f"_pending_{signal.symbol}"] = signal


def _arm(signal: Signal, loc: int, entry: float) -> dict:
    be_level = None
    if signal.be_r is not None:
        risk = abs(entry - float(signal.stop))
        be_level = entry + float(signal.be_r) * risk
    return {
        "entry_loc": loc,
        "entry": entry,
        "time_exit": int(signal.time_exit_loc),
        "close_stop": signal.close_stop,
        "close_stop_armed": False,
        "be_level": be_level,
        "be_done": False,
    }
