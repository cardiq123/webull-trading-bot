"""Paper replay and the market-hours loop.

Replay is a simulated session: each cycle is one historical bar, signals are
read from completed history, and the paper broker prints the fills. The
polling loop is for paper or live use during the NYSE session. Live is only
reachable after the CLI has already required the config flag and the typed
confirmation.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

from webull_bot.broker.paper import PaperBroker
from webull_bot.calendar import is_after_close_scan, is_regular_hours
from webull_bot.costs import buy_fees, buy_price
from webull_bot.journal.store import Journal
from webull_bot.models import Order, OrderType, Position, Side, TimeInForce
from webull_bot.notify.webhook import notify
from webull_bot.risk.manager import RiskLimits, RiskState, circuit_update, plan_entry
from webull_bot.strategies.base import Strategy
from webull_bot.universe import all_sectors

NY = ZoneInfo("America/New_York")


def run_replay(
    bars: dict[str, pd.DataFrame],
    strategies: list[Strategy],
    regime: pd.DataFrame,
    broker: PaperBroker,
    journal: Journal,
    *,
    cycles: int,
    limits: RiskLimits,
    webhook: str = "",
    params: dict[str, dict] | None = None,
    start=None,
    quiet: bool = False,
    flatten_at_end: bool = False,
    include_prior_open: bool = True,
) -> dict[str, Any]:
    """Step through historical sessions on ``bars``.

    ``cycles`` is the number of SPY bars at the end of the file, which is
    the number of sessions when the bars are daily. ``start`` replays from
    that timestamp instead. Signals are rebuilt on bars up through the
    current bar. A next-open signal fills on the following bar.
    """
    if "SPY" not in bars or bars["SPY"].empty:
        raise RuntimeError("Replay needs SPY bars")
    clock = bars["SPY"].index
    if start is not None:
        start_i = _start_index(clock, start)
    else:
        if len(clock) < cycles + 30:
            raise RuntimeError("Not enough history to replay a session")
        start_i = len(clock) - cycles
    start = start_i
    fills_n = 0
    orders_n = 0
    day_trades: list = []
    rejected: dict[str, int] = {}
    triggers: list[dict[str, str]] = []
    closed: list[dict[str, float | str]] = []
    open_lots: dict[str, dict] = {}
    equity_curve: list[float] = []
    opening = broker.snapshot()
    peak = opening.equity
    drawdown_halt = False
    current_session = None
    day_start = opening.equity
    flattened_today = False
    working: dict[str, dict] = {}
    for i in range(start, len(clock)):
        ts = clock[i]
        session = _session_day(ts)
        last_bar = i == len(clock) - 1 or _session_day(clock[i + 1]) != session
        prior_ok = include_prior_open or i > start
        _mark_opens(broker, bars, ts)
        if session != current_session:
            current_session = session
            day_start = broker.snapshot().equity
            flattened_today = False
        history = {symbol: frame.loc[:ts] for symbol, frame in bars.items()}
        regime_now = _regime_through(regime, ts)
        books = {}
        for strategy in strategies:
            chosen = dict(strategy.default_params)
            if params and strategy.name in params:
                chosen.update(params[strategy.name])
            if not chosen.get("symbols"):
                if strategy.custom_universe:
                    chosen["symbols"] = strategy.universe("dow") or ["__none__"]
                else:
                    chosen["symbols"] = strategy.universe("etf") or ["__none__"]
            books[strategy.name] = strategy.generate(history, regime_now, chosen)
        snapshot = broker.snapshot()
        prices = {pos.symbol: pos.peak_price or pos.avg_price for pos in snapshot.positions}
        prior_history = {symbol: frame.iloc[:-1] for symbol, frame in history.items() if len(frame)}
        returns = _close_returns(prior_history)
        # A resting sell is the target or stop for a position already in the
        # snapshot. Counting it as another position made swing books hit the
        # concurrent cap and the sector cap while the backtest still had room.
        held = {pos.symbol for pos in snapshot.positions}
        pending = [
            Position(
                symbol=order.symbol,
                quantity=order.quantity,
                avg_price=prices.get(order.symbol, 1.0),
                strategy=order.strategy,
                sector=all_sectors().get(order.symbol, "unknown"),
            )
            for order in broker.open_orders()
            if order.side == Side.BUY and order.symbol not in held
        ]
        cash_left = snapshot.cash
        staged: dict[str, dict] = {}
        # The backtest fills a prior bar's exit at this open before it sizes
        # new entries. Doing the buy first counted the name that was about to
        # leave toward the sector cap, and it sized the new trade on equity
        # that still included that open position.
        exited_now: set[str] = set()
        held_now = {(pos.symbol, pos.strategy) for pos in snapshot.positions}
        for strategy in strategies:
            for symbol in sorted(books[strategy.name]):
                _row, previous, bar = _signal_row(books[strategy.name], history, symbol, ts)
                if bar is None or previous is None or not prior_ok:
                    continue
                if not bool(previous.get("exit_next_open")):
                    continue
                if (symbol, strategy.name) not in held_now:
                    continue
                exit_fills = broker.fill_exit(symbol, float(bar["open"]), "signal")
                fills_n += len(exit_fills)
                _record_fills(exit_fills, closed, open_lots, journal)
                working.pop(symbol, None)
                exited_now.add(symbol)
        if exited_now:
            snapshot = broker.snapshot()
            prices = {pos.symbol: pos.peak_price or pos.avg_price for pos in snapshot.positions}
            cash_left = snapshot.cash
            held = {pos.symbol for pos in snapshot.positions}
            pending = [
                Position(
                    symbol=order.symbol,
                    quantity=order.quantity,
                    avg_price=prices.get(order.symbol, 1.0),
                    strategy=order.strategy,
                    sector=all_sectors().get(order.symbol, "unknown"),
                )
                for order in broker.open_orders()
                if order.side == Side.BUY and order.symbol not in held
            ]
        for strategy in strategies:
            symbols = sorted(books[strategy.name])
            for symbol in symbols:
                _row, previous, bar = _signal_row(books[strategy.name], history, symbol, ts)
                if bar is None:
                    continue
                enter = bool(_row.get("entry_this_open")) if _row is not None else False
                stop = _row.get("stop_price") if _row is not None else None
                take = _row.get("take_profit") if _row is not None else None
                hold = _row.get("max_hold") if _row is not None else None
                if previous is not None and prior_ok and bool(previous.get("entry_next_open")):
                    enter = True
                    stop = previous.get("stop_price")
                    take = previous.get("take_profit")
                    hold = previous.get("max_hold")
                # A same-bar signal exit consumes the entry. The engine never
                # queues that entry, because the position was still open when
                # the signal was read.
                if symbol in exited_now:
                    enter = False
                sector = all_sectors().get(symbol, "unknown")
                raw_open = float(bar["open"]) if _finite(bar["open"]) else 0.0
                if enter and _finite(stop) and raw_open > 0 and not flattened_today:
                    # Same gate as the backtest: a stop at or through the raw
                    # open is invalid. Slippage is applied once, on the fill.
                    fill_px = buy_price(raw_open, broker.costs)
                    stop_px = float(stop)
                    if stop_px >= raw_open:
                        rejected["invalid stop"] = rejected.get("invalid stop", 0) + 1
                    elif fill_px <= stop_px:
                        rejected["fill through stop"] = rejected.get("fill through stop", 0) + 1
                    else:
                        order, plan = _sized_order(
                            limits,
                            snapshot,
                            prices,
                            pending,
                            peak_equity=peak,
                            day_start_equity=day_start,
                            drawdown_halt=drawdown_halt,
                            symbol=symbol,
                            raw_price=fill_px,
                            stop_price=float(stop),
                            strategy=strategy.name,
                            session=session,
                            sector=sector,
                            holds_overnight=strategy.holds_overnight,
                            day_trade_dates=day_trades,
                            returns=returns,
                            cash=cash_left,
                        )
                        if plan.flatten_now:
                            flattened_today = True
                            triggers.append({"session": session.isoformat(), "kind": plan.halt_kind or "daily"})
                            flat_fills = broker.flatten()
                            fills_n += len(flat_fills)
                            _record_fills(flat_fills, closed, open_lots, journal)
                            working.clear()
                        elif order is not None:
                            broker.place_order(order)
                            orders_n += 1
                            _place_target(broker, order, take)
                            cash_left -= order.quantity * fill_px + buy_fees(broker.costs)
                            pending.append(
                                Position(
                                    symbol=symbol,
                                    quantity=order.quantity,
                                    avg_price=fill_px,
                                    strategy=strategy.name,
                                    sector=sector,
                                )
                            )
                            staged[symbol] = {
                                "take_profit": float(take) if _finite(take) else None,
                                "max_hold": int(hold) if _finite(hold) else None,
                                "bars_held": 0,
                                "trail_pct": strategy.trail_pct,
                                "peak": fill_px,
                                "sector": sector,
                                "strategy": strategy.name,
                                "holds_overnight": strategy.holds_overnight,
                            }
                            if not strategy.holds_overnight:
                                day_trades.append(session)
                            journal.event("order", f"replay submit {symbol}", {"strategy": strategy.name})
                        else:
                            rejected[plan.reason] = rejected.get(plan.reason, 0) + 1
        for symbol, frame in history.items():
            if str(symbol).startswith("^") or ts not in frame.index:
                continue
            bar = frame.loc[ts]
            if isinstance(bar, pd.DataFrame):
                bar = bar.iloc[-1]
            if not _finite(bar["open"]):
                continue
            bar_fills = broker.process_bar(symbol, float(bar["open"]), float(bar["high"]), float(bar["low"]), float(bar["close"]))
            fills_n += len(bar_fills)
            _record_fills(bar_fills, closed, open_lots, journal)
            for fill in bar_fills:
                journal.event("fill", f"{fill.side.value} {fill.quantity} {fill.symbol} @ {fill.price:.2f}", {"reason": fill.reason})
                notify(webhook, "fill", f"Paper {fill.side.value} {fill.quantity} {fill.symbol} @ {fill.price:.2f}")
                if fill.reason == "stop":
                    notify(webhook, "stop", f"Paper stop {fill.symbol} @ {fill.price:.2f}")
                if fill.side == Side.BUY and symbol in staged:
                    working[symbol] = staged.pop(symbol)
                    working[symbol]["peak"] = float(fill.price)
                    broker.set_sector(symbol, working[symbol]["sector"])
                elif fill.side == Side.SELL:
                    working.pop(symbol, None)
        for symbol in list(staged):
            for order in broker.open_orders():
                if order.symbol == symbol:
                    broker.cancel_order(order.client_order_id)
        _drop_closed(broker, working)
        for symbol, meta in list(working.items()):
            if symbol not in history or ts not in history[symbol].index:
                continue
            bar = history[symbol].loc[ts]
            if isinstance(bar, pd.DataFrame):
                bar = bar.iloc[-1]
            pos = next((item for item in broker.positions() if item.symbol == symbol), None)
            if pos is None:
                working.pop(symbol, None)
                continue
            trail = meta.get("trail_pct")
            if trail:
                peak_px = max(float(meta.get("peak") or pos.avg_price), float(bar["high"]))
                meta["peak"] = peak_px
                trailed = peak_px * (1.0 - float(trail))
                stop_now = float(pos.stop_price or 0.0)
                if trailed > stop_now:
                    broker.update_stop(symbol, trailed)
                    if _finite(bar["low"]) and float(bar["low"]) <= trailed:
                        stop_fills = broker.fill_exit(symbol, trailed, "stop")
                        fills_n += len(stop_fills)
                        _record_fills(stop_fills, closed, open_lots, journal)
                        working.pop(symbol, None)
                        continue
            meta["bars_held"] = int(meta.get("bars_held") or 0) + 1
            reason = None
            signal_row = None
            for strategy in strategies:
                frame = books.get(strategy.name, {}).get(symbol)
                if frame is not None and ts in frame.index and strategy.name == meta.get("strategy"):
                    signal_row = frame.loc[ts]
                    if isinstance(signal_row, pd.DataFrame):
                        signal_row = signal_row.iloc[-1]
            if signal_row is not None and bool(signal_row.get("exit_this_close")):
                reason = "signal_close"
            if meta.get("max_hold") is not None and meta["bars_held"] >= int(meta["max_hold"]):
                reason = "max_hold"
            if last_bar and not meta.get("holds_overnight"):
                reason = "session_flat"
            if reason:
                flat_fills = broker.fill_exit(symbol, float(bar["close"]), reason)
                fills_n += len(flat_fills)
                _record_fills(flat_fills, closed, open_lots, journal)
                working.pop(symbol, None)
        snap = broker.snapshot()
        state = circuit_update(
            RiskState(
                equity=snap.equity,
                cash=snap.cash,
                peak_equity=peak,
                day_start_equity=day_start,
                positions=snap.positions,
                drawdown_halt=drawdown_halt,
                account_type=snap.account_type,
            ),
            limits,
        )
        peak = state.peak_equity
        drawdown_halt = state.drawdown_halt
        daily_hit = day_start > 0 and (1.0 - snap.equity / day_start) >= limits.daily_max_loss_pct - 1e-12
        if daily_hit and limits.flatten_on_daily_loss and not flattened_today:
            flattened_today = True
            triggers.append({"session": session.isoformat(), "kind": "daily_loss"})
            if snap.positions or broker.open_orders():
                flat_fills = broker.flatten()
                fills_n += len(flat_fills)
                _record_fills(flat_fills, closed, open_lots, journal)
                working.clear()
            journal.event("kill", "paper daily-loss flatten", {"session": session.isoformat()})
        elif state.drawdown_halt and limits.flatten_on_max_drawdown and not flattened_today:
            if snap.positions or broker.open_orders():
                flattened_today = True
                triggers.append({"session": session.isoformat(), "kind": "drawdown"})
                flat_fills = broker.flatten()
                fills_n += len(flat_fills)
                _record_fills(flat_fills, closed, open_lots, journal)
                working.clear()
                journal.event("kill", "paper drawdown flatten", {"session": session.isoformat()})
        snap = broker.snapshot()
        equity_curve.append(snap.equity)
        journal.equity(snap.equity, snap.cash, "paper")
        if not quiet:
            print(
                f"{session.isoformat()} equity {snap.equity:,.2f} cash {snap.cash:,.2f} "
                f"positions {len(snap.positions)}"
            )
    if flatten_at_end and (broker.positions() or broker.open_orders()):
        end_fills = broker.flatten()
        fills_n += len(end_fills)
        _record_fills(end_fills, closed, open_lots, journal)
        snap = broker.snapshot()
        equity_curve.append(snap.equity)
    snap = broker.snapshot()
    wins = [row for row in closed if float(row["pnl"]) > 0]
    summary = {
        "cycles": len(clock) - start,
        "orders": orders_n,
        "fills": fills_n,
        "ending_equity": snap.equity,
        "cash": snap.cash,
        "pnl": snap.equity - opening.equity,
        "win_rate": (len(wins) / len(closed)) if closed else 0.0,
        "closed_trades": len(closed),
        "max_drawdown": _max_drawdown(equity_curve, opening.equity),
        "risk_triggers": triggers,
        "rejected": rejected,
        "positions": [pos.symbol for pos in snap.positions],
        "trades": closed,
    }
    notify(webhook, "daily_summary", f"Paper replay equity {snap.equity:,.2f}, fills {fills_n}")
    journal.event("daily_summary", "replay complete", summary)
    return summary


def run_poll_loop(
    *,
    broker: PaperBroker,
    journal: Journal,
    strategies: list[Strategy],
    data_provider,
    symbols: list[str],
    limits: RiskLimits,
    webhook: str,
    poll_seconds: int,
    max_cycles: int,
) -> None:
    """Poll during regular hours and run one after-close scan.

    With ``max_cycles`` set, the loop stops even if the market is closed so
    an unattended run cannot spin. A max_cycles of 0 means run until killed.
    """
    cycles = 0
    scanned: set = set()
    while True:
        now = datetime.now(NY)
        if is_regular_hours(now) or is_after_close_scan(now):
            bars = data_provider.latest(symbols, "1d", lookback_days=500)
            if "SPY" in bars and not bars["SPY"].empty:
                from webull_bot.strategies.regime import build_regime
                from webull_bot.universe import STOCK_UNIVERSE

                regime = build_regime(bars, [s for s in STOCK_UNIVERSE if s in bars])
                # One cycle uses the latest completed daily bar as a paper step.
                run_replay(
                    bars,
                    strategies,
                    regime,
                    broker,
                    journal,
                    cycles=1,
                    limits=limits,
                    webhook=webhook,
                )
                if is_after_close_scan(now):
                    scanned.add(now.date())
                    snap = broker.snapshot()
                    notify(webhook, "daily_summary", f"After-close equity {snap.equity:,.2f}")
        else:
            journal.event("schedule", "market closed", {"now": now.isoformat()})
            print(f"Market closed at {now.isoformat()}. Paper loop is idle.")
        cycles += 1
        if max_cycles and cycles >= max_cycles:
            break
        time.sleep(poll_seconds)


def _sized_order(limits, snapshot, prices, pending, **kwargs):
    from webull_bot.broker.webull import new_client_order_id

    state = RiskState(
        equity=snapshot.equity,
        cash=float(kwargs["cash"]) if kwargs.get("cash") is not None else snapshot.cash,
        peak_equity=float(kwargs["peak_equity"]),
        day_start_equity=float(kwargs["day_start_equity"]),
        positions=list(snapshot.positions) + list(pending),
        day_trade_dates=list(kwargs.get("day_trade_dates") or []),
        drawdown_halt=bool(kwargs.get("drawdown_halt")),
        account_type=snapshot.account_type,
    )
    plan = plan_entry(
        state,
        limits,
        symbol=kwargs["symbol"],
        entry_price=kwargs["raw_price"],
        stop_price=kwargs["stop_price"],
        sector=kwargs["sector"],
        as_of=kwargs["session"],
        prices={**prices, kwargs["symbol"]: kwargs["raw_price"]},
        returns=kwargs.get("returns"),
        would_day_trade_on_close=not kwargs["holds_overnight"],
    )
    if not plan.accepted:
        return None, plan
    return Order(
        client_order_id=new_client_order_id(),
        symbol=kwargs["symbol"],
        side=Side.BUY,
        quantity=plan.quantity,
        order_type=OrderType.MARKET,
        time_in_force=TimeInForce.DAY,
        stop_price=kwargs["stop_price"],
        strategy=kwargs["strategy"],
    ), plan


def _record_fills(fills, closed: list, open_lots: dict, journal: Journal) -> None:
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
            open_lots[fill.symbol] = {
                "price": fill.price,
                "qty": fill.quantity,
                "fees": fill.fees,
                "strategy": fill.strategy,
            }
            continue
        lot = open_lots.pop(fill.symbol, None)
        if lot is None:
            continue
        qty = min(float(fill.quantity), float(lot["qty"]))
        pnl = (float(fill.price) - float(lot["price"])) * qty - float(fill.fees) - float(lot["fees"])
        closed.append(
            {
                "symbol": fill.symbol,
                "pnl": pnl,
                "strategy": fill.strategy or lot["strategy"],
                "reason": fill.reason,
            }
        )


def _signal_row(book: dict, history: dict, symbol: str, ts):
    """Return the current signal row, the prior signal row, and the price bar.

    The prior row is the next-open signal. A missing price bar means this
    symbol does not trade on the clock bar.
    """
    frame = book.get(symbol)
    if frame is None or symbol not in history or ts not in history[symbol].index:
        return None, None, None
    bar = history[symbol].loc[ts]
    if isinstance(bar, pd.DataFrame):
        bar = bar.iloc[-1]
    if not _finite(bar["open"]):
        return None, None, None
    if ts not in frame.index:
        return None, None, bar
    row = frame.loc[ts]
    if isinstance(row, pd.DataFrame):
        row = row.iloc[-1]
    previous = frame.iloc[-2] if len(frame) >= 2 else None
    if isinstance(previous, pd.DataFrame):
        previous = previous.iloc[-1]
    return row, previous, bar


def _regime_through(regime: pd.DataFrame, ts):
    if regime is None or len(regime) == 0:
        return regime
    try:
        return regime.loc[:ts]
    except TypeError:
        return regime


def _start_index(clock: pd.DatetimeIndex, start) -> int:
    start_ts = pd.Timestamp(start)
    if getattr(clock, "tz", None) is not None and start_ts.tzinfo is None:
        start_ts = start_ts.tz_localize(clock.tz)
    elif getattr(clock, "tz", None) is not None and start_ts.tzinfo is not None:
        start_ts = start_ts.tz_convert(clock.tz)
    elif getattr(clock, "tz", None) is None and start_ts.tzinfo is not None:
        start_ts = start_ts.tz_convert("America/New_York").tz_localize(None)
    loc = int(clock.searchsorted(start_ts))
    return min(loc, len(clock) - 1)


def _session_day(ts) -> object:
    stamp = pd.Timestamp(ts)
    if stamp.tzinfo is not None:
        stamp = stamp.tz_convert("America/New_York")
    return stamp.date()


def _mark_opens(broker: PaperBroker, bars: dict[str, pd.DataFrame], ts) -> None:
    marks = {}
    for symbol, frame in bars.items():
        if str(symbol).startswith("^") or ts not in frame.index:
            continue
        bar = frame.loc[ts]
        if isinstance(bar, pd.DataFrame):
            bar = bar.iloc[-1]
        if _finite(bar["open"]):
            marks[symbol] = float(bar["open"])
    if marks:
        broker.mark_prices(marks)


def _place_target(broker: PaperBroker, order: Order, take) -> None:
    if not _finite(take):
        return
    from webull_bot.broker.webull import new_client_order_id

    broker.place_order(
        Order(
            client_order_id=new_client_order_id(),
            symbol=order.symbol,
            side=Side.SELL,
            quantity=order.quantity,
            order_type=OrderType.LIMIT,
            time_in_force=TimeInForce.GTC,
            limit_price=float(take),
            strategy=order.strategy,
        )
    )


def _drop_closed(broker: PaperBroker, working: dict) -> None:
    held = {pos.symbol for pos in broker.positions()}
    for symbol in list(working):
        if symbol not in held:
            working.pop(symbol, None)


def _close_returns(history: dict[str, pd.DataFrame]) -> pd.DataFrame:
    spy = history.get("SPY")
    index = spy.index if spy is not None and len(spy) else None
    columns = {}
    for symbol, frame in history.items():
        if str(symbol).startswith("^") or frame.empty or "close" not in frame:
            continue
        series = frame["close"].astype(float)
        if index is not None:
            series = series.reindex(index)
        columns[symbol] = series.pct_change()
    if not columns:
        return pd.DataFrame()
    return pd.DataFrame(columns)


def _max_drawdown(equity: list[float], start: float) -> float:
    peak = start
    worst = 0.0
    for value in equity:
        peak = max(peak, value)
        if peak > 0:
            worst = min(worst, value / peak - 1.0)
    return worst


def _finite(value) -> bool:
    try:
        return value is not None and pd.notna(value) and float(value) > 0
    except (TypeError, ValueError):
        return False
