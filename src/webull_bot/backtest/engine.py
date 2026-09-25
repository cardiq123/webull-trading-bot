"""Event-driven backtester.

Fill rules, which are the no-lookahead contract:

* A signal computed from the close of bar t (``entry_next_open``) fills at
  the open of bar t+1. It never fills at bar t's close.
* A signal that is allowed to use the open (``entry_this_open``) fills at
  that open. Strategies that set this flag must not read that bar's high,
  low, close, or volume.
* While deciding at the open, existing positions are marked at the open.
  The bar's close is applied only after stops and exits.
* Protective stops are live on the fill bar. A gap through the stop fills
  at the open, not at the stop. If the bar's range touches both the stop
  and the target, the stop is assumed to have been hit first.
* The last bar in the file cannot fill a next-open order.
* Day strategies are flattened at the session close and do not carry a
  next-open signal into the following session.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Optional

import numpy as np
import pandas as pd

from webull_bot.calendar import next_trading_day
from webull_bot.costs import CostModel, buy_fees, buy_price, sell_price, sell_regulatory_fees
from webull_bot.models import Position
from webull_bot.risk.manager import RiskLimits, RiskState, plan_entry
from webull_bot.strategies.base import Strategy


@dataclass
class _Position:
    symbol: str
    strategy: str
    quantity: float
    entry_price: float
    entry_time: pd.Timestamp
    stop_price: float
    take_profit: Optional[float]
    max_hold: Optional[int]
    holds_overnight: bool
    sector: str
    trail_pct: Optional[float]
    bars_held: int = 0
    peak_price: float = 0.0
    entry_fees: float = 0.0
    opened_on: Optional[date] = None
    reserved_day_trade: bool = False


@dataclass
class _Queued:
    symbol: str
    kind: str
    strategy: str
    stop_price: float
    take_profit: Optional[float]
    max_hold: Optional[int]
    holds_overnight: bool
    trail_pct: Optional[float]
    sector: str
    signal_session: date


@dataclass
class _Book:
    strategy: str
    symbol: str
    entry_next: np.ndarray
    entry_this: np.ndarray
    exit_next: np.ndarray
    exit_close: np.ndarray
    stop: np.ndarray
    take: np.ndarray
    max_hold: np.ndarray
    holds_overnight: bool
    trail_pct: Optional[float]
    sector: str


@dataclass
class BacktestResult:
    equity: pd.Series
    exposure: pd.Series
    trades: pd.DataFrame
    rejected: dict[str, int] = field(default_factory=dict)
    ending_equity: float = 0.0

    def daily_equity(self) -> pd.Series:
        if self.equity.empty:
            return self.equity
        sessions = [_session_date(ts) for ts in self.equity.index]
        grouped = self.equity.groupby(sessions).last()
        grouped.index = pd.to_datetime(list(grouped.index))
        return grouped


def _session_date(ts: Any) -> date:
    stamp = pd.Timestamp(ts)
    if stamp.tzinfo is not None:
        stamp = stamp.tz_convert("America/New_York")
    return stamp.date()


def _clean(series: pd.Series, index: pd.Index, fill: float) -> np.ndarray:
    return series.reindex(index).fillna(fill).to_numpy(dtype=float)


def _bools(series: pd.Series, index: pd.Index) -> np.ndarray:
    return series.reindex(index).fillna(False).to_numpy(dtype=bool)


def run_backtest(
    bars: dict[str, pd.DataFrame],
    strategies: list[Strategy],
    regime: pd.DataFrame,
    *,
    starting_equity: float,
    costs: CostModel,
    limits: RiskLimits,
    sectors: dict[str, str],
    account_type: str = "margin",
    params: Optional[dict[str, dict[str, Any]]] = None,
    trade_start: Optional[pd.Timestamp] = None,
    trade_end: Optional[pd.Timestamp] = None,
    flatten_at_end: bool = False,
) -> BacktestResult:
    generated: dict[str, dict[str, pd.DataFrame]] = {}
    for strategy in strategies:
        chosen = dict(strategy.default_params)
        if params and strategy.name in params:
            chosen.update(params[strategy.name])
        generated[strategy.name] = strategy.generate(bars, regime, chosen)

    clock_source = bars.get("SPY")
    if clock_source is None:
        for symbol, frame in bars.items():
            if not str(symbol).startswith("^"):
                clock_source = frame
                break
    if clock_source is None or clock_source.empty:
        return _empty(starting_equity)

    clock = clock_source.index
    if trade_start is not None:
        clock = clock[clock >= pd.Timestamp(trade_start)]
    if trade_end is not None:
        clock = clock[clock <= pd.Timestamp(trade_end)]
    if len(clock) == 0:
        return _empty(starting_equity)

    symbols = [symbol for symbol in bars if not str(symbol).startswith("^")]
    opens = {symbol: _clean(bars[symbol]["open"], clock, np.nan) for symbol in symbols}
    highs = {symbol: _clean(bars[symbol]["high"], clock, np.nan) for symbol in symbols}
    lows = {symbol: _clean(bars[symbol]["low"], clock, np.nan) for symbol in symbols}
    closes = {symbol: _clean(bars[symbol]["close"], clock, np.nan) for symbol in symbols}
    close_frame = pd.DataFrame({symbol: pd.Series(closes[symbol], index=clock) for symbol in symbols})
    returns = close_frame.pct_change()

    books: list[_Book] = []
    for strategy in strategies:
        for symbol, frame in generated[strategy.name].items():
            if symbol not in opens:
                continue
            books.append(
                _Book(
                    strategy=strategy.name,
                    symbol=symbol,
                    entry_next=_bools(frame["entry_next_open"], clock),
                    entry_this=_bools(frame["entry_this_open"], clock),
                    exit_next=_bools(frame["exit_next_open"], clock),
                    exit_close=_bools(frame["exit_this_close"], clock),
                    stop=_clean(frame["stop_price"], clock, np.nan),
                    take=_clean(frame["take_profit"], clock, np.nan),
                    max_hold=_clean(frame["max_hold"], clock, np.nan),
                    holds_overnight=strategy.holds_overnight,
                    trail_pct=strategy.trail_pct,
                    sector=sectors.get(symbol, "unknown"),
                )
            )

    # Symbol name is the tie-break. Dict order is not, because it follows
    # PYTHONHASHSEED and would make the same bars produce different trades.
    strategy_order = {strategy.name: index for index, strategy in enumerate(strategies)}
    books.sort(key=lambda book: (strategy_order.get(book.strategy, 0), book.symbol))

    cash = float(starting_equity)
    unsettled: list[tuple[date, float]] = []
    positions: dict[str, _Position] = {}
    queue: list[_Queued] = []
    last_close: dict[str, float] = {}
    day_trade_dates: list[date] = []
    trades: list[dict[str, Any]] = []
    equity_values: list[float] = []
    exposure_values: list[float] = []
    rejected: dict[str, int] = {}
    drawdown_halt = False
    daily_halt = False
    peak_equity = float(starting_equity)
    day_start_equity = float(starting_equity)
    previous_session: Optional[date] = None
    sessions = [_session_date(ts) for ts in clock]

    def reject(reason: str) -> None:
        key = reason.split(":")[0][:96]
        rejected[key] = rejected.get(key, 0) + 1

    def equity_of(mark: dict[str, float]) -> float:
        invested = 0.0
        for pos in positions.values():
            invested += pos.quantity * mark.get(pos.symbol, pos.entry_price)
        return cash + sum(amount for _, amount in unsettled) + invested

    def close_position(symbol: str, raw_price: float, ts: pd.Timestamp, reason: str, session: date) -> None:
        nonlocal cash
        pos = positions.get(symbol)
        if pos is None or not np.isfinite(raw_price) or raw_price <= 0:
            return
        fill = sell_price(float(raw_price), costs)
        fees = sell_regulatory_fees(fill, pos.quantity, costs)
        proceeds = fill * pos.quantity - fees
        if account_type == "cash":
            unsettled.append((next_trading_day(session), proceeds))
        else:
            cash += proceeds
        if pos.opened_on == session and not pos.reserved_day_trade:
            day_trade_dates.append(session)
        trades.append(
            {
                "symbol": symbol,
                "strategy": pos.strategy,
                "quantity": pos.quantity,
                "entry_time": pos.entry_time,
                "entry_price": pos.entry_price,
                "exit_time": ts,
                "exit_price": fill,
                "pnl": (fill - pos.entry_price) * pos.quantity - fees - pos.entry_fees,
                "fees": fees + pos.entry_fees,
                "reason": reason,
                "bars_held": pos.bars_held,
            }
        )
        del positions[symbol]

    def try_enter(
        book: _Book,
        raw_price: float,
        stop_price: float,
        ts: pd.Timestamp,
        session: date,
        mark: dict[str, float],
        bar_index: int,
        max_hold: Optional[int],
        take_profit: Optional[float],
    ) -> None:
        nonlocal cash
        symbol = book.symbol
        if symbol in positions or daily_halt or drawdown_halt:
            return
        if not np.isfinite(raw_price) or raw_price <= 0:
            return
        if not np.isfinite(stop_price) or stop_price <= 0 or stop_price >= raw_price:
            reject("invalid stop")
            return
        fill = buy_price(float(raw_price), costs)
        if fill <= stop_price:
            reject("fill through stop")
            return
        state = RiskState(
            equity=equity_of(mark),
            cash=cash,
            peak_equity=peak_equity,
            day_start_equity=day_start_equity,
            positions=[
                Position(symbol=pos.symbol, quantity=pos.quantity, avg_price=pos.entry_price, sector=pos.sector)
                for pos in positions.values()
            ],
            day_trade_dates=list(day_trade_dates),
            drawdown_halt=drawdown_halt,
            account_type=account_type,
        )
        plan = plan_entry(
            state,
            limits,
            symbol=symbol,
            entry_price=fill,
            stop_price=float(stop_price),
            sector=book.sector,
            as_of=session,
            prices=mark,
            returns=returns.iloc[:bar_index],
            would_day_trade_on_close=not book.holds_overnight,
        )
        if not plan.accepted:
            reject(plan.reason)
            return
        fee = buy_fees(costs)
        spent = plan.quantity * fill + fee
        if spent > cash + 1e-8:
            reject("insufficient cash")
            return
        cash -= spent
        positions[symbol] = _Position(
            symbol=symbol,
            strategy=book.strategy,
            quantity=plan.quantity,
            entry_price=fill,
            entry_time=ts,
            stop_price=float(stop_price),
            take_profit=take_profit,
            max_hold=max_hold,
            holds_overnight=book.holds_overnight,
            sector=book.sector,
            trail_pct=book.trail_pct,
            peak_price=fill,
            entry_fees=fee,
            opened_on=session,
            reserved_day_trade=not book.holds_overnight,
        )
        mark[symbol] = fill
        if not book.holds_overnight:
            day_trade_dates.append(session)

    books_by_symbol: dict[str, list[_Book]] = {}
    for book in books:
        books_by_symbol.setdefault(book.symbol, []).append(book)

    n = len(clock)
    for i, ts in enumerate(clock):
        session = sessions[i]
        is_last_in_session = i == n - 1 or sessions[i + 1] != session
        mark = dict(last_close)
        for symbol in symbols:
            if np.isfinite(opens[symbol][i]):
                mark[symbol] = float(opens[symbol][i])

        if previous_session is None or session != previous_session:
            still: list[tuple[date, float]] = []
            for available_on, amount in unsettled:
                if available_on <= session:
                    cash += amount
                else:
                    still.append((available_on, amount))
            unsettled = still
            day_start_equity = equity_of(mark)
            daily_halt = False
            previous_session = session

        exited: set[str] = set()
        deferred_entries: list[_Queued] = []
        for order in queue:
            if order.kind == "exit":
                raw = opens.get(order.symbol, np.array([np.nan]))[i] if order.symbol in opens else np.nan
                if order.symbol in positions and np.isfinite(raw):
                    close_position(order.symbol, float(raw), ts, "signal", session)
                    exited.add(order.symbol)
                continue
            if not order.holds_overnight and order.signal_session != session:
                continue
            deferred_entries.append(order)
        queue = []
        for order in deferred_entries:
            if order.symbol in exited or order.symbol in positions:
                continue
            raw = opens[order.symbol][i]
            dummy = _Book(
                strategy=order.strategy,
                symbol=order.symbol,
                entry_next=np.array([]),
                entry_this=np.array([]),
                exit_next=np.array([]),
                exit_close=np.array([]),
                stop=np.array([]),
                take=np.array([]),
                max_hold=np.array([]),
                holds_overnight=order.holds_overnight,
                trail_pct=order.trail_pct,
                sector=order.sector,
            )
            try_enter(
                dummy,
                float(raw),
                order.stop_price,
                ts,
                session,
                mark,
                i,
                order.max_hold,
                order.take_profit,
            )

        for book in books:
            if not book.entry_this[i] or book.symbol in exited:
                continue
            try_enter(
                book,
                float(opens[book.symbol][i]),
                float(book.stop[i]),
                ts,
                session,
                mark,
                i,
                _hold(book.max_hold[i]),
                _take(book.take[i]),
            )

        for symbol in list(positions):
            pos = positions[symbol]
            bar_open = opens[symbol][i]
            bar_high = highs[symbol][i]
            bar_low = lows[symbol][i]
            if not (np.isfinite(bar_open) and np.isfinite(bar_high) and np.isfinite(bar_low)):
                continue
            if bar_open <= pos.stop_price or bar_low <= pos.stop_price:
                raw = float(bar_open) if bar_open <= pos.stop_price else pos.stop_price
                close_position(symbol, raw, ts, "stop", session)
                continue
            if pos.take_profit is not None and (bar_open >= pos.take_profit or bar_high >= pos.take_profit):
                raw = float(bar_open) if bar_open >= pos.take_profit else pos.take_profit
                close_position(symbol, raw, ts, "target", session)

        for symbol in list(positions):
            pos = positions[symbol]
            if pos.trail_pct is None:
                continue
            bar_high = highs[symbol][i]
            bar_low = lows[symbol][i]
            if not np.isfinite(bar_high):
                continue
            pos.peak_price = max(pos.peak_price, float(bar_high))
            trailed = pos.peak_price * (1.0 - pos.trail_pct)
            if trailed > pos.stop_price:
                pos.stop_price = trailed
                # Pessimistic path: the high prints before the low, so a
                # trail tightened by this bar's high can stop out on this
                # bar's low. The initial stop was already tested above.
                if np.isfinite(bar_low) and bar_low <= pos.stop_price:
                    close_position(symbol, pos.stop_price, ts, "stop", session)

        for symbol in list(positions):
            pos = positions[symbol]
            bar_close = closes[symbol][i]
            if not np.isfinite(bar_close):
                continue
            pos.bars_held += 1
            reason = None
            for book in books_by_symbol.get(symbol, []):
                if book.strategy == pos.strategy and book.exit_close[i]:
                    reason = "signal_close"
                    break
            if pos.max_hold is not None and pos.bars_held >= pos.max_hold:
                reason = "max_hold"
            if is_last_in_session and not pos.holds_overnight:
                reason = "session_flat"
            if reason:
                close_position(symbol, float(bar_close), ts, reason, session)

        for symbol in symbols:
            if np.isfinite(closes[symbol][i]):
                last_close[symbol] = float(closes[symbol][i])
                mark[symbol] = float(closes[symbol][i])

        if flatten_at_end and i == n - 1:
            for symbol in list(positions):
                if np.isfinite(closes[symbol][i]):
                    close_position(symbol, float(closes[symbol][i]), ts, "window_end", session)
        equity_now = equity_of(mark)
        if day_start_equity > 0 and equity_now <= day_start_equity * (1.0 - limits.daily_max_loss_pct):
            daily_halt = True
            if limits.flatten_on_daily_loss:
                for symbol in list(positions):
                    if np.isfinite(closes[symbol][i]):
                        close_position(symbol, float(closes[symbol][i]), ts, "daily_loss_breaker", session)
                equity_now = equity_of(mark)

        peak_equity = max(peak_equity, equity_now)
        if peak_equity > 0 and (1.0 - equity_now / peak_equity) >= limits.max_drawdown_pct - 1e-12:
            drawdown_halt = True
            if limits.flatten_on_max_drawdown:
                for symbol in list(positions):
                    if np.isfinite(closes[symbol][i]):
                        close_position(symbol, float(closes[symbol][i]), ts, "drawdown_breaker", session)
                equity_now = equity_of(mark)

        invested = sum(pos.quantity * mark.get(pos.symbol, pos.entry_price) for pos in positions.values())
        exposure_values.append(invested / equity_now if equity_now else 0.0)
        equity_values.append(equity_now)

        if daily_halt or drawdown_halt or i == n - 1:
            continue

        queued_symbols: set[str] = set()
        for book in books:
            in_pos = book.symbol in positions and positions[book.symbol].strategy == book.strategy
            if book.exit_next[i] and in_pos:
                queue.append(
                    _Queued(
                        symbol=book.symbol,
                        kind="exit",
                        strategy=book.strategy,
                        stop_price=0.0,
                        take_profit=None,
                        max_hold=None,
                        holds_overnight=book.holds_overnight,
                        trail_pct=book.trail_pct,
                        sector=book.sector,
                        signal_session=session,
                    )
                )
            if not book.entry_next[i]:
                continue
            if is_last_in_session and not book.holds_overnight:
                continue
            if in_pos and book.exit_next[i]:
                continue
            if book.symbol in queued_symbols:
                continue
            stop = float(book.stop[i])
            if not np.isfinite(stop):
                continue
            queued_symbols.add(book.symbol)
            queue.append(
                _Queued(
                    symbol=book.symbol,
                    kind="enter",
                    strategy=book.strategy,
                    stop_price=stop,
                    take_profit=_take(book.take[i]),
                    max_hold=_hold(book.max_hold[i]),
                    holds_overnight=book.holds_overnight,
                    trail_pct=book.trail_pct,
                    sector=book.sector,
                    signal_session=session,
                )
            )

    equity = pd.Series(equity_values, index=pd.DatetimeIndex(clock[: len(equity_values)]), name="equity")
    exposure = pd.Series(exposure_values, index=equity.index, name="exposure")
    ending = float(equity.iloc[-1]) if len(equity) else starting_equity
    return BacktestResult(
        equity=equity,
        exposure=exposure,
        trades=pd.DataFrame(trades),
        rejected=rejected,
        ending_equity=ending,
    )


def _empty(starting_equity: float) -> BacktestResult:
    return BacktestResult(
        equity=pd.Series(dtype=float),
        exposure=pd.Series(dtype=float),
        trades=pd.DataFrame(),
        ending_equity=starting_equity,
    )


def _hold(value: float) -> Optional[int]:
    if not np.isfinite(value):
        return None
    return int(value)


def _take(value: float) -> Optional[float]:
    if not np.isfinite(value):
        return None
    return float(value)
