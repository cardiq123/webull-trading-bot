"""Live and sandbox order path.

Decisions use the same causal signals as the backtest. Orders go only
through ``WebullBroker``, which calls the official SDK. Production live
does not start unless the CLI has already demanded ``live_trading_enabled``
and the confirmation phrase. Sandbox paper uses this module too, and the
broker still refuses any host other than ``*.sandbox.webull.com``. Fills
are not simulated: the broker is the source of truth on the next poll.
"""

from __future__ import annotations

import time
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

from webull_bot.broker.webull import WebullBroker, new_client_order_id
from webull_bot.calendar import is_after_close_scan, is_regular_hours
from webull_bot.costs import CostModel
from webull_bot.execution.reconcile import (
    decide_stop,
    is_allocation,
    line_for,
    mark_price,
    open_targets,
    protective_stop,
    remember_peak,
)
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
    dry_run: bool = False,
    sandbox: bool = False,
) -> None:
    if sandbox:
        from webull_bot.broker.webull import WebullError, assert_sandbox_hosts

        hosts = list(getattr(broker, "hosts", []) or [])
        try:
            assert_sandbox_hosts(hosts)
        except WebullError:
            raise
        environment = str(getattr(broker, "environment", "")).lower()
        if environment not in {"sandbox", "uat", "test"}:
            raise WebullError(
                "Sandbox paper mode refuses a non-sandbox environment. "
                "Orders are sent only to *.sandbox.webull.com."
            )
        broker.sandbox_only = True
    cycles = 0
    day_start = None
    peak = None
    session_day = None
    while True:
        now = datetime.now(NY)
        if dry_run or is_regular_hours(now) or is_after_close_scan(now):
            if sandbox and session_day != now.date():
                session_day = now.date()
                day_start = None
            day_start, peak = _cycle(
                broker,
                data_provider,
                strategies,
                journal,
                limits,
                symbols,
                webhook,
                dry_run=dry_run,
                sandbox=sandbox,
                day_start_equity=day_start if sandbox else None,
                peak_equity=peak if sandbox else None,
            )
        else:
            print(f"Market closed at {now.isoformat()}. Live loop is idle.")
            journal.event("schedule", "live idle, market closed", {})
        cycles += 1
        if max_cycles and cycles >= max_cycles:
            return
        time.sleep(poll_seconds)


def run_sandbox(
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
    dry_run: bool = False,
) -> None:
    """Send orders only to the Webull paper sandbox.

    This does not consult ``live_trading_enabled`` or the live confirmation
    phrase. It refuses any host other than ``*.sandbox.webull.com`` before
    the first cycle. ``dry_run`` builds orders and does not send them.
    """
    run_live(
        broker=broker,
        data_provider=data_provider,
        strategies=strategies,
        journal=journal,
        limits=limits,
        symbols=symbols,
        webhook=webhook,
        poll_seconds=poll_seconds,
        max_cycles=max_cycles,
        dry_run=dry_run,
        sandbox=True,
    )


def _cycle(
    broker,
    data_provider,
    strategies,
    journal,
    limits,
    symbols,
    webhook,
    *,
    dry_run: bool = False,
    sandbox: bool = False,
    day_start_equity: float | None = None,
    peak_equity: float | None = None,
    now: datetime | None = None,
    costs: CostModel | None = None,
) -> tuple[float | None, float | None]:
    now = now or datetime.now(NY)
    # Long enough for a 2017-start dual-momentum replay, not just the last signal day.
    bars = data_provider.latest(symbols, "1d", lookback_days=6000)
    if "SPY" not in bars or bars["SPY"].empty:
        text = "no SPY bars; no orders"
        print(text)
        journal.event("dry_run" if dry_run else "live", text, {})
        return day_start_equity, peak_equity
    from webull_bot.execution.reconcile import split_forming_bar

    completed, _forming = split_forming_bar(bars, now)
    if "SPY" not in completed or completed["SPY"].empty:
        text = "no completed SPY bar; no orders"
        print(text)
        journal.event("dry_run" if dry_run else "live", text, {})
        return day_start_equity, peak_equity
    regime = build_regime(completed, [symbol for symbol in STOCK_UNIVERSE if symbol in completed])
    snapshot = broker.snapshot()
    if day_start_equity is None:
        day_start_equity = snapshot.equity
    if peak_equity is None:
        peak_equity = snapshot.equity
    else:
        peak_equity = max(peak_equity, snapshot.equity)
    costs = costs or CostModel()
    last_ts = completed["SPY"].index[-1]
    for strategy in strategies:
        if getattr(strategy, "forward_only", False):
            text = f"skip {strategy.name}; sandbox forward-test only. Live trading refuses it."
            print(text)
            journal.event("dry_run" if dry_run else "live", text, {})
            continue
        if getattr(strategy, "custom_universe", False):
            text = f"skip {strategy.name}; backtest and paper only, no live orders"
            print(text)
            journal.event("dry_run" if dry_run else "live", text, {})
            continue
        params = dict(strategy.default_params)
        params["symbols"] = strategy.universe("etf") or ["__none__"]
        book = strategy.generate(completed, regime, params)
        targets = open_targets(
            bars,
            book,
            strategy=strategy.name,
            trail_pct=getattr(strategy, "trail_pct", None),
            holds_overnight=bool(strategy.holds_overnight),
            now=now,
            costs=costs,
        )
        held_now = {pos.symbol: pos for pos in snapshot.positions if pos.quantity > 0}
        for symbol in sorted(book):
            if book[symbol] is None or getattr(book[symbol], "empty", False):
                continue
            target = targets.get(symbol)
            position = held_now.get(symbol)
            line = _line_for_symbol(
                strategy,
                symbol,
                target,
                position,
                snapshot,
                bars,
                limits,
                peak_equity,
                day_start_equity,
                last_ts,
                journal,
                dry_run=dry_run,
                allocation=is_allocation(strategy),
                now=now,
            )
            print(line.text)
            journal.event(
                "dry_run" if dry_run else "cycle",
                line.text,
                {"symbol": symbol, "strategy": strategy.name, "action": line.kind, "qty": line.quantity, "stop": line.stop},
            )
            if line.kind == "reject" and line.cancel_stops and sandbox and not dry_run:
                broker.flatten()
                snapshot = broker.snapshot()
                continue
            if dry_run or line.kind in {"hold", "idle", "flat", "reject"}:
                continue
            _execute(broker, line, webhook, journal)
            snapshot = broker.snapshot()
            held_now = {pos.symbol: pos for pos in snapshot.positions if pos.quantity > 0}
    return day_start_equity, peak_equity


def _line_for_symbol(
    strategy,
    symbol,
    target,
    position,
    snapshot,
    bars,
    limits,
    peak_equity,
    day_start_equity,
    last_ts,
    journal,
    *,
    dry_run: bool,
    allocation: bool,
    now: datetime,
):
    from webull_bot.execution.reconcile import CycleLine

    if target is not None:
        decision = decide_stop(target, bars, now, journal, strategy.name)
        if position is not None and decision.stopped:
            text = line_for(
                strategy=strategy.name, symbol=symbol, kind="sell",
                quantity=position.quantity, dry_run=dry_run,
            )
            return CycleLine(
                strategy.name, symbol, text, "sell", position.quantity,
                decision.stop, decision.peak, decision.entry_key, cancel_stops=True,
            )
        if position is not None:
            remember_peak(journal, strategy.name, symbol, decision.entry_key, decision.peak, decision.stop)
            resting = protective_stop(snapshot.open_orders, symbol)
            qty = position.quantity
            if resting is None or resting.stop_price is None or decision.stop > round(float(resting.stop_price), 2) + 1e-9:
                text = line_for(
                    strategy=strategy.name, symbol=symbol, kind="trail",
                    quantity=qty, stop=decision.stop, dry_run=dry_run,
                )
                return CycleLine(
                    strategy.name, symbol, text, "trail", qty, decision.stop,
                    decision.peak, decision.entry_key,
                )
            text = line_for(strategy=strategy.name, symbol=symbol, kind="hold", dry_run=dry_run)
            return CycleLine(
                strategy.name, symbol, text, "hold", qty, decision.stop,
                decision.peak, decision.entry_key,
            )
        price = mark_price(bars, symbol)
        if decision.stopped or price is None or decision.stop <= 0 or decision.stop >= price:
            detail = f"{strategy.name} {symbol} stop already through"
            text = line_for(strategy=strategy.name, symbol=symbol, kind="reject", detail=detail, dry_run=dry_run)
            return CycleLine(strategy.name, symbol, text, "reject")
        remember_peak(journal, strategy.name, symbol, decision.entry_key, decision.peak, decision.stop)
        state = RiskState(
            equity=snapshot.equity,
            cash=snapshot.cash,
            peak_equity=peak_equity,
            day_start_equity=day_start_equity,
            positions=snapshot.positions,
            account_type=snapshot.account_type or "cash",
        )
        plan = plan_entry(
            state,
            limits,
            symbol=symbol,
            entry_price=price,
            stop_price=decision.stop,
            sector=all_sectors().get(symbol, "unknown"),
            as_of=pd.Timestamp(last_ts).date(),
            prices={pos.symbol: pos.avg_price for pos in snapshot.positions},
            would_day_trade_on_close=not strategy.holds_overnight,
        )
        if not plan.accepted or plan.quantity <= 0:
            detail = f"{strategy.name} {symbol} {plan.reason or 'size is zero'}"
            text = line_for(strategy=strategy.name, symbol=symbol, kind="reject", detail=detail, dry_run=dry_run)
            return CycleLine(
                strategy.name, symbol, text, "reject",
                cancel_stops=bool(plan.flatten_now),
            )
        text = line_for(
            strategy=strategy.name, symbol=symbol, kind="buy",
            quantity=plan.quantity, stop=decision.stop, dry_run=dry_run,
        )
        return CycleLine(
            strategy.name, symbol, text, "buy", plan.quantity, decision.stop,
            decision.peak, decision.entry_key,
        )
    if target is None and position is not None:
        text = line_for(
            strategy=strategy.name, symbol=symbol, kind="sell",
            quantity=position.quantity, dry_run=dry_run,
        )
        return CycleLine(
            strategy.name, symbol, text, "sell", position.quantity, cancel_stops=True,
        )
    kind = "idle" if allocation else "flat"
    text = line_for(strategy=strategy.name, symbol=symbol, kind=kind, dry_run=dry_run)
    return CycleLine(strategy.name, symbol, text, kind)


def _execute(broker, line, webhook, journal) -> None:
    if line.kind == "sell":
        for order in list(broker.open_orders()):
            if order.symbol == line.symbol and order.side == Side.SELL and order.order_type == OrderType.STOP:
                if order.client_order_id:
                    broker.cancel_order(order.client_order_id)
        sell = Order(
            client_order_id=new_client_order_id(),
            symbol=line.symbol,
            side=Side.SELL,
            quantity=line.quantity,
            order_type=OrderType.MARKET,
            time_in_force=TimeInForce.DAY,
            strategy=line.strategy,
        )
        broker.place_order(sell)
        journal.event("live_order", line.text, {"symbol": line.symbol, "qty": line.quantity})
        notify(webhook, "exit", line.text)
        return
    if line.kind == "trail":
        resting = protective_stop(broker.open_orders(), line.symbol)
        if resting is not None and resting.client_order_id:
            broker.replace_order(resting.client_order_id, line.quantity, stop_price=line.stop)
        else:
            broker.place_order(
                Order(
                    client_order_id=new_client_order_id(),
                    symbol=line.symbol,
                    side=Side.SELL,
                    quantity=line.quantity,
                    order_type=OrderType.STOP,
                    stop_price=line.stop,
                    time_in_force=TimeInForce.GTC,
                    strategy=line.strategy,
                )
            )
        journal.event("live_order", line.text, {"symbol": line.symbol, "stop": line.stop})
        return
    if line.kind != "buy":
        return
    entry = Order(
        client_order_id=new_client_order_id(),
        symbol=line.symbol,
        side=Side.BUY,
        quantity=line.quantity,
        order_type=OrderType.MARKET,
        time_in_force=TimeInForce.DAY,
        strategy=line.strategy,
    )
    protective = Order(
        client_order_id=new_client_order_id(),
        symbol=line.symbol,
        side=Side.SELL,
        quantity=line.quantity,
        order_type=OrderType.STOP,
        stop_price=line.stop,
        time_in_force=TimeInForce.GTC,
        strategy=line.strategy,
    )
    broker.place_order(entry)
    broker.place_order(protective)
    journal.event("live_order", line.text, {"symbol": line.symbol, "qty": line.quantity, "stop": line.stop})
    notify(webhook, "fill", line.text)
