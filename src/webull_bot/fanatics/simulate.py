"""Fill model for the Chart Fanatics studies.

Next-bar-open entries. A gap through the stop fills at the open. If a bar
could hit both the stop and the target, the stop fills. Stop fills are
another ``stop_extra_ticks`` worse than the stop price (the digest's 1–2
tick stop slippage; the default is the low end, and the stress test uses
the high end). Commission is $2 per side per contract. ETF books use the
stock cost model instead.

This module does not send orders.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from webull_bot.backtest.engine import BacktestResult
from webull_bot.costs import CostModel, buy_fees, buy_price, sell_price, sell_regulatory_fees
from webull_bot.fanatics.data import INSTRUMENTS

STARTING_EQUITY = 100_000.0


@dataclass
class Signal:
    symbol: str
    side: int
    signal_loc: int
    stop: float
    target: float
    time_exit_loc: int
    be_r: float | None = None
    close_stop: float | None = None
    window: tuple[int, int] | None = None
    limit_entry: float | None = None


def _pnl(spec: dict, side: int, entry: float, exit_price: float, contracts: float) -> float:
    if spec["usd_quote"]:
        gross = side * (exit_price - entry) * spec["point_value"] * contracts
    else:
        gross = side * (exit_price - entry) / exit_price * spec["point_value"] * contracts
    if spec.get("fee_bps"):
        fees = (abs(entry) + abs(exit_price)) * abs(contracts) * spec["point_value"] * float(spec["fee_bps"]) / 10_000.0
    else:
        fees = 4.0 * abs(contracts)
    return float(gross - fees)


def _risk_dollars(spec: dict, entry: float, stop: float, contracts: int) -> float:
    distance = abs(entry - stop)
    if spec["usd_quote"]:
        return distance * spec["point_value"] * contracts
    return distance / entry * spec["point_value"] * contracts


def _contracts(spec: dict, equity: float, entry: float, stop: float, risk: float, etf: bool) -> float:
    distance = abs(entry - stop)
    if distance <= 0 or entry <= 0 or equity <= 0:
        return 0
    if etf:
        raw = int((equity * risk) // distance)
        cap = int((equity * 0.20) // entry)
        return max(min(raw, cap), 0)
    budget = equity * risk
    unit = distance * spec["point_value"] if spec["usd_quote"] else distance / entry * spec["point_value"]
    if unit <= 0:
        return 0
    if spec.get("fractional"):
        qty = budget / unit
        cap = equity / (entry * spec["point_value"])
        qty = min(qty, cap)
        return qty if qty * entry >= 50 else 0.0
    return int(budget // unit)


def simulate(
    bars: dict[str, pd.DataFrame],
    signals: list[Signal],
    *,
    risk: float = 0.005,
    stop_extra_ticks: int = 1,
    entry_slip_ticks: int = 1,
    max_consecutive_losses: int = 2,
    day_loss_r: float = 3.0,
    day_win_r: float = 3.0,
    max_trades_per_day: int | None = None,
    max_open: int = 4,
    etf: bool = False,
    costs: CostModel | None = None,
    calendar: pd.DatetimeIndex | None = None,
) -> tuple[BacktestResult, pd.DataFrame]:
    """Simulate signals in entry-time order on a shared cash account."""
    costs = costs or CostModel()
    prepared = []
    for signal in signals:
        frame = bars.get(signal.symbol)
        if frame is None:
            continue
        if signal.limit_entry is None and signal.signal_loc + 1 >= len(frame):
            continue
        if signal.limit_entry is not None and signal.signal_loc >= len(frame):
            continue
        fill_loc = signal.signal_loc if signal.limit_entry is not None else signal.signal_loc + 1
        prepared.append((frame.index[fill_loc], signal, fill_loc))
    prepared.sort(key=lambda item: item[0])

    equity = STARTING_EQUITY
    pending: list[dict] = []
    trades: list[dict] = []
    day_r: dict[str, float] = {}
    day_losses = 0
    day_trades: dict[str, int] = {}
    current_day = None
    arrays: dict[int, tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]] = {}

    def _realize(as_of: pd.Timestamp) -> None:
        nonlocal equity, day_losses
        ready = [item for item in pending if item["exit_time"] <= as_of]
        pending[:] = [item for item in pending if item["exit_time"] > as_of]
        ready.sort(key=lambda item: item["exit_time"])
        for item in ready:
            equity += item["pnl"]
            day_r[item["day"]] = day_r.get(item["day"], 0.0) + item["r"]
            if item["day"] == current_day:
                day_losses = day_losses + 1 if item["r"] < 0 else 0

    for fill_time, signal, fill_loc in prepared:
        frame = bars[signal.symbol]
        spec = INSTRUMENTS.get(signal.symbol) or {
            "tick": 0.01,
            "point_value": 1.0,
            "usd_quote": True,
        }
        day = str(fill_time.tz_convert("America/New_York").date()) if fill_time.tzinfo else str(fill_time.date())
        if day != current_day:
            current_day = day
            day_losses = 0
        _realize(fill_time)
        if any(item["symbol"] == signal.symbol for item in pending):
            continue
        if len(pending) >= max_open:
            continue
        if day_losses >= max_consecutive_losses:
            continue
        if day_r.get(day, 0.0) <= -day_loss_r or day_r.get(day, 0.0) >= day_win_r:
            continue
        if max_trades_per_day is not None and day_trades.get(day, 0) >= max_trades_per_day:
            continue

        tick = float(spec["tick"])
        raw_open = float(frame["open"].iloc[fill_loc])
        slip = entry_slip_ticks * tick
        if signal.limit_entry is not None:
            limit = float(signal.limit_entry)
            bar_low = float(frame["low"].iloc[fill_loc])
            bar_high = float(frame["high"].iloc[fill_loc])
            if signal.side > 0 and bar_low > limit and raw_open > limit:
                continue
            if signal.side < 0 and bar_high < limit and raw_open < limit:
                continue
            # A resting limit does not receive a better price than the limit.
            entry = limit + signal.side * slip
        else:
            entry = raw_open + signal.side * slip
        if etf and signal.limit_entry is None:
            entry = buy_price(raw_open, costs) if signal.side > 0 else sell_price(raw_open, costs)
        if signal.side > 0 and signal.stop >= entry:
            continue
        if signal.side < 0 and signal.stop <= entry:
            continue
        contracts = _contracts(spec, equity, entry, signal.stop, risk, etf)
        if contracts <= 0:
            continue
        cached = arrays.get(id(frame))
        if cached is None:
            cached = (
                frame["high"].to_numpy(dtype=float),
                frame["low"].to_numpy(dtype=float),
                frame["open"].to_numpy(dtype=float),
                frame["close"].to_numpy(dtype=float),
            )
            arrays[id(frame)] = cached
        exit_price, exit_loc, reason = _walk(
            cached, spec, signal, fill_loc, entry, tick, stop_extra_ticks, etf, costs
        )
        if exit_price is None:
            continue
        if etf:
            pnl = _etf_pnl(signal.side, entry, exit_price, contracts, costs, raw_was_friction=True)
        else:
            pnl = _pnl(spec, signal.side, entry, exit_price, contracts)
        risk_dollars = _risk_dollars(spec, entry, signal.stop, contracts)
        r_mult = pnl / risk_dollars if risk_dollars else 0.0
        exit_time = frame.index[exit_loc]
        day_trades[day] = day_trades.get(day, 0) + 1
        pending.append(
            {"exit_time": exit_time, "symbol": signal.symbol, "pnl": pnl, "r": r_mult, "day": day}
        )
        trades.append(
            {
                "symbol": signal.symbol,
                "side": "long" if signal.side > 0 else "short",
                "entry_time": fill_time,
                "exit_time": exit_time,
                "entry": entry,
                "exit": exit_price,
                "pnl": pnl,
                "r": r_mult,
                "reason": reason,
                "contracts": contracts,
                "hold_bars": int(exit_loc - fill_loc),
            }
        )
    if pending:
        horizon = max(item["exit_time"] for item in pending) + pd.Timedelta(seconds=1)
        _realize(horizon)

    trade_frame = pd.DataFrame(trades)
    result = _result(trade_frame, equity, calendar)
    return result, trade_frame


def _etf_pnl(side: int, entry: float, exit_price: float, shares: int, costs: CostModel, raw_was_friction: bool) -> float:
    del raw_was_friction
    if side > 0:
        return (exit_price - entry) * shares - sell_regulatory_fees(exit_price, shares, costs) - buy_fees(costs)
    return (entry - exit_price) * shares - sell_regulatory_fees(entry, shares, costs) - buy_fees(costs)


def _walk(ohlc, spec, signal: Signal, fill_loc: int, entry: float, tick: float, stop_extra: int, etf: bool, costs: CostModel):
    high, low, open_, close = ohlc
    stop = signal.stop
    target = signal.target
    be_level = None
    if signal.be_r is not None:
        risk = abs(entry - stop)
        be_level = entry + signal.side * signal.be_r * risk
    pending_close_stop = False
    last = min(len(open_) - 1, signal.time_exit_loc if signal.time_exit_loc >= fill_loc else len(open_) - 1)
    for i in range(fill_loc, last + 1):
        if i == signal.time_exit_loc and i != fill_loc:
            return _friction_exit(open_[i], signal.side, etf, costs, tick, is_stop=False, market=True), i, "time"
        if pending_close_stop:
            return _friction_exit(open_[i], signal.side, etf, costs, tick, is_stop=True, market=True), i, "close_stop"
        o, h, l = open_[i], high[i], low[i]
        if signal.side > 0:
            if o <= stop:
                return _friction_exit(o, signal.side, etf, costs, tick, is_stop=True), i, "stop"
            if np.isfinite(target) and o >= target:
                return _friction_exit(o, signal.side, etf, costs, tick, is_stop=False), i, "target"
            if l <= stop:
                fill = stop - (stop_extra + 1) * tick
                return _friction_exit(fill, signal.side, etf, costs, tick, is_stop=True, already_slipped=not etf), i, "stop"
            if np.isfinite(target) and h >= target:
                return float(target), i, "target"
        else:
            if o >= stop:
                return _friction_exit(o, signal.side, etf, costs, tick, is_stop=True), i, "stop"
            if np.isfinite(target) and o <= target:
                return _friction_exit(o, signal.side, etf, costs, tick, is_stop=False), i, "target"
            if h >= stop:
                fill = stop + (stop_extra + 1) * tick
                return _friction_exit(fill, signal.side, etf, costs, tick, is_stop=True, already_slipped=not etf), i, "stop"
            if np.isfinite(target) and l <= target:
                return float(target), i, "target"
        if signal.close_stop is not None and np.isfinite(close[i]):
            if (signal.side > 0 and close[i] < signal.close_stop) or (signal.side < 0 and close[i] > signal.close_stop):
                pending_close_stop = True
        if be_level is not None and i + 1 <= last:
            if (signal.side > 0 and h >= be_level) or (signal.side < 0 and l <= be_level):
                stop = entry
                be_level = None
        if i == signal.time_exit_loc:
            return _friction_exit(close[i], signal.side, etf, costs, tick, is_stop=False, market=True), i, "time"
    return _friction_exit(close[last], signal.side, etf, costs, tick, is_stop=False, market=True), last, "eod"


def _friction_exit(
    price: float,
    side: int,
    etf: bool,
    costs: CostModel,
    tick: float,
    is_stop: bool,
    already_slipped: bool = False,
    market: bool = False,
) -> float:
    del is_stop
    if etf:
        return sell_price(price, costs) if side > 0 else buy_price(price, costs)
    if already_slipped or not market:
        return float(price)
    return float(price - side * tick)


def _result(trades: pd.DataFrame, ending: float, calendar: pd.DatetimeIndex | None) -> BacktestResult:
    if trades.empty:
        empty = pd.Series(dtype=float)
        return BacktestResult(empty, empty, trades, ending_equity=STARTING_EQUITY)
    exits = pd.to_datetime(trades["exit_time"])
    if getattr(exits.dt, "tz", None) is not None:
        days = exits.dt.tz_convert("America/New_York").dt.normalize().dt.tz_localize(None)
    else:
        days = exits.dt.normalize()
    pnl = trades["pnl"].to_numpy(dtype=float)
    by_day = pd.Series(pnl, index=days).groupby(level=0).sum()
    if calendar is not None and len(calendar):
        cal = pd.to_datetime(calendar)
        if getattr(cal, "tz", None) is not None:
            cal = cal.tz_convert("America/New_York").tz_localize(None)
        cal = pd.DatetimeIndex(sorted(set(pd.to_datetime(cal).normalize())))
        by_day = by_day.reindex(cal).fillna(0.0)
    equity = STARTING_EQUITY + by_day.cumsum()
    exposure = pd.Series(0.0, index=equity.index)
    hold_days = days[days.isin(equity.index)] if len(equity) else days
    exposure.loc[hold_days.unique()] = 1.0
    out = trades.copy()
    out["entry_time"] = pd.to_datetime(out["entry_time"])
    return BacktestResult(equity=equity, exposure=exposure, trades=out, ending_equity=float(equity.iloc[-1]) if len(equity) else ending)


def random_signals(bars: dict[str, pd.DataFrame], signals: list[Signal], seed: int = 7) -> list[Signal]:
    """Same stop distance, target distance, and time-exit bar, random side and bar.

    The random bar is drawn from the signal's ``window`` minute-of-day range
    on the same session, excluding the original signal bar. This is the
    baseline that separates a setup from the clock.
    """
    rng = np.random.default_rng(seed)
    out = []
    prepared: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
    for symbol, frame in bars.items():
        index = frame.index
        local = index.tz_convert("America/New_York") if index.tz is not None else index
        minutes = local.hour.to_numpy() * 60 + local.minute.to_numpy()
        days = local.year.to_numpy() * 10000 + local.month.to_numpy() * 100 + local.day.to_numpy()
        prepared[symbol] = (minutes, days, frame["open"].to_numpy(dtype=float))
    for signal in signals:
        pack = prepared.get(signal.symbol)
        if pack is None or signal.window is None:
            continue
        minutes, days, opens = pack
        if signal.signal_loc + 1 >= len(opens):
            continue
        day = int(days[signal.signal_loc])
        start, end = signal.window
        candidates = np.flatnonzero((days == day) & (minutes >= start) & (minutes < end))
        candidates = candidates[candidates != signal.signal_loc]
        if candidates.size == 0:
            continue
        loc = int(rng.choice(candidates))
        side = int(rng.choice(np.array([-1, 1])))
        entry_guess = float(opens[min(loc + 1, len(opens) - 1)])
        risk = abs(float(opens[signal.signal_loc + 1]) - signal.stop)
        reward = abs(signal.target - float(opens[signal.signal_loc + 1])) if np.isfinite(signal.target) else risk
        if risk <= 0:
            continue
        stop = entry_guess - side * risk
        target = entry_guess + side * reward
        out.append(
            Signal(
                symbol=signal.symbol,
                side=side,
                signal_loc=loc,
                stop=stop,
                target=target,
                time_exit_loc=min(len(opens) - 1, loc + max(signal.time_exit_loc - signal.signal_loc, 1)),
                be_r=signal.be_r,
                window=signal.window,
            )
        )
    return out
