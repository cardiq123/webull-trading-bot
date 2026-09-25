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
from webull_bot.journal.store import Journal
from webull_bot.models import Order, OrderType, Side, TimeInForce
from webull_bot.notify.webhook import notify
from webull_bot.risk.manager import RiskLimits, RiskState, plan_entry
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
) -> dict[str, Any]:
    """Step through the last ``cycles`` daily sessions on ``bars``."""
    if "SPY" not in bars or bars["SPY"].empty:
        raise RuntimeError("Replay needs SPY bars")
    clock = bars["SPY"].index
    if len(clock) < cycles + 30:
        raise RuntimeError("Not enough history to replay a session")
    start = len(clock) - cycles
    fills_n = 0
    day_trades: list = []
    for i in range(start, len(clock)):
        ts = clock[i]
        session = pd.Timestamp(ts).date()
        history = {symbol: frame.loc[:ts] for symbol, frame in bars.items()}
        regime_now = regime.loc[:ts] if len(regime) else regime
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
        for strategy in strategies:
            for symbol, frame in books[strategy.name].items():
                if ts not in frame.index or symbol not in history:
                    continue
                row = frame.loc[ts]
                previous = frame.iloc[-2] if len(frame) >= 2 else None
                enter = bool(row.get("entry_this_open"))
                stop = row.get("stop_price")
                if previous is not None and bool(previous.get("entry_next_open")):
                    enter = True
                    stop = previous.get("stop_price")
                bar = history[symbol].loc[ts]
                if enter and _finite(stop) and _finite(bar["open"]):
                    order = _sized_order(
                        broker,
                        limits,
                        snapshot,
                        prices,
                        symbol=symbol,
                        raw_price=float(bar["open"]),
                        stop_price=float(stop),
                        strategy=strategy.name,
                        session=session,
                        sector=all_sectors().get(symbol, "unknown"),
                        holds_overnight=strategy.holds_overnight,
                        day_trade_dates=day_trades,
                    )
                    if order is not None:
                        broker.place_order(order)
                        if not strategy.holds_overnight:
                            day_trades.append(session)
                        journal.event("order", f"replay submit {symbol}", {"strategy": strategy.name})
                if (
                    previous is not None
                    and bool(previous.get("exit_next_open"))
                    and any(pos.symbol == symbol and pos.strategy == strategy.name for pos in snapshot.positions)
                ):
                    broker.fill_exit(symbol, float(bar["open"]), "signal")
        for symbol, frame in history.items():
            if symbol.startswith("^") or ts not in frame.index:
                continue
            bar = frame.loc[ts]
            if not _finite(bar["open"]):
                continue
            for fill in broker.process_bar(symbol, float(bar["open"]), float(bar["high"]), float(bar["low"]), float(bar["close"])):
                fills_n += 1
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
                journal.event("fill", f"{fill.side.value} {fill.quantity} {fill.symbol} @ {fill.price:.2f}", {"reason": fill.reason})
                notify(webhook, "fill", f"Paper {fill.side.value} {fill.quantity} {fill.symbol} @ {fill.price:.2f}")
                if fill.reason == "stop":
                    notify(webhook, "stop", f"Paper stop {fill.symbol} @ {fill.price:.2f}")
            for strategy in strategies:
                if strategy.holds_overnight:
                    continue
                if any(pos.symbol == symbol for pos in broker.positions()):
                    for fill in broker.fill_exit(symbol, float(bar["close"]), "session_flat"):
                        fills_n += 1
                        journal.event("fill", f"flat {symbol}", {"price": fill.price})
        snap = broker.snapshot()
        journal.equity(snap.equity, snap.cash, "paper")
        print(
            f"{session.isoformat()} equity {snap.equity:,.2f} cash {snap.cash:,.2f} "
            f"positions {len(snap.positions)}"
        )
    snap = broker.snapshot()
    summary = {
        "cycles": cycles,
        "fills": fills_n,
        "ending_equity": snap.equity,
        "cash": snap.cash,
        "positions": [pos.symbol for pos in snap.positions],
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


def _sized_order(broker, limits, snapshot, prices, **kwargs):
    from webull_bot.broker.webull import new_client_order_id

    state = RiskState(
        equity=snapshot.equity,
        cash=snapshot.cash,
        peak_equity=snapshot.equity,
        day_start_equity=snapshot.equity,
        positions=snapshot.positions,
        day_trade_dates=list(kwargs.get("day_trade_dates") or []),
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
        returns=None,
        would_day_trade_on_close=not kwargs["holds_overnight"],
    )
    if not plan.accepted:
        return None
    return Order(
        client_order_id=new_client_order_id(),
        symbol=kwargs["symbol"],
        side=Side.BUY,
        quantity=plan.quantity,
        order_type=OrderType.MARKET,
        time_in_force=TimeInForce.DAY,
        stop_price=kwargs["stop_price"],
        strategy=kwargs["strategy"],
    )


def _finite(value) -> bool:
    try:
        return value is not None and pd.notna(value) and float(value) > 0
    except (TypeError, ValueError):
        return False
