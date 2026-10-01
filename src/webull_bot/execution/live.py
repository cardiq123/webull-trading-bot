"""Live order path.

Decisions use the same causal signals as paper. Orders go only through
``WebullBroker``, which calls the official SDK. This module does not run
unless the CLI has already demanded ``live_trading_enabled`` and the
confirmation phrase. Fills are not simulated: the broker is the source of
truth on the next poll.
"""

from __future__ import annotations

import time
from datetime import datetime, time
from zoneinfo import ZoneInfo

import pandas as pd

from webull_bot.broker.webull import WebullBroker, new_client_order_id
from webull_bot.calendar import is_after_close_scan, is_regular_hours
from webull_bot.journal.store import Journal
from webull_bot.models import Order, OrderType, Side, TimeInForce
from webull_bot.notify.webhook import notify
from webull_bot.risk.manager import RiskLimits, RiskState, plan_entry
from webull_bot.strategies.regime import build_regime
from webull_bot.universe import STOCK_UNIVERSE, all_sectors

NY = ZoneInfo("America/New_York")


def run_live(
    *,
    broker: WebullBroker,
    data_provider,
    strategies,
    journal: Journal,
    limits: RiskLimits,
    symbols: list[str],
    webhook: str,
    poll_seconds: int,
    max_cycles: int,
) -> None:
    cycles = 0
    while True:
        now = datetime.now(NY)
        if is_regular_hours(now) or is_after_close_scan(now):
            _cycle(broker, data_provider, strategies, journal, limits, symbols, webhook)
        else:
            print(f"Market closed at {now.isoformat()}. Live loop is idle.")
            journal.event("schedule", "live idle, market closed", {})
        cycles += 1
        if max_cycles and cycles >= max_cycles:
            return
        time.sleep(poll_seconds)


def _cycle(broker, data_provider, strategies, journal, limits, symbols, webhook) -> None:
    bars = data_provider.latest(symbols, "1d", lookback_days=500)
    if "SPY" not in bars or bars["SPY"].empty:
        journal.event("live", "no SPY bars; no orders", {})
        return
    regime = build_regime(bars, [symbol for symbol in STOCK_UNIVERSE if symbol in bars])
    snapshot = broker.snapshot()
    held = {pos.symbol for pos in snapshot.positions}
    last_ts = bars["SPY"].index[-1]
    # Signals are taken from the last completed bar only. The next poll
    # sends the order; we do not fill it locally.
    for strategy in strategies:
        if getattr(strategy, "custom_universe", False):
            journal.event(
                "live",
                f"skip {strategy.name}; backtest and paper only, no live orders",
                {},
            )
            continue
        params = dict(strategy.default_params)
        params["symbols"] = strategy.universe("etf") or ["__none__"]
        book = strategy.generate(bars, regime, params)
        for symbol, frame in book.items():
            if symbol in held or frame.empty:
                continue
            row = frame.iloc[-1]
            # A daily bar dated today is still forming before the cash close.
            # Using it would treat an incomplete close as a finished signal.
            bar_day = pd.Timestamp(frame.index[-1])
            if getattr(bar_day, "tzinfo", None) is not None:
                bar_day = bar_day.tz_convert(NY)
            now = datetime.now(NY)
            if bar_day.date() == now.date() and now.time() < time(16, 0) and len(frame) >= 2:
                row = frame.iloc[-2]
            if not bool(row.get("entry_next_open")) and not bool(row.get("entry_this_open")):
                continue
            stop = row.get("stop_price")
            if stop is None or pd.isna(stop):
                continue
            price = float(bars[symbol]["close"].iloc[-1])
            state = RiskState(
                equity=snapshot.equity,
                cash=snapshot.cash,
                peak_equity=snapshot.equity,
                day_start_equity=snapshot.equity,
                positions=snapshot.positions,
                account_type="margin",
            )
            plan = plan_entry(
                state,
                limits,
                symbol=symbol,
                entry_price=price,
                stop_price=float(stop),
                sector=all_sectors().get(symbol, "unknown"),
                as_of=pd.Timestamp(last_ts).date(),
                prices={pos.symbol: pos.avg_price for pos in snapshot.positions},
                would_day_trade_on_close=not strategy.holds_overnight,
            )
            if not plan.accepted:
                journal.event("reject", plan.reason, {"symbol": symbol})
                continue
            entry = Order(
                client_order_id=new_client_order_id(),
                symbol=symbol,
                side=Side.BUY,
                quantity=plan.quantity,
                order_type=OrderType.MARKET,
                time_in_force=TimeInForce.DAY,
                strategy=strategy.name,
            )
            broker.place_order(entry)
            protective = Order(
                client_order_id=new_client_order_id(),
                symbol=symbol,
                side=Side.SELL,
                quantity=plan.quantity,
                order_type=OrderType.STOP,
                stop_price=float(stop),
                time_in_force=TimeInForce.GTC,
                strategy=strategy.name,
            )
            broker.place_order(protective)
            journal.event("live_order", f"submitted {symbol}", {"qty": plan.quantity, "stop": float(stop)})
            notify(webhook, "fill", f"Live order submitted {symbol} qty {plan.quantity} stop {float(stop):.2f}")
            held.add(symbol)
            snapshot = broker.snapshot()
