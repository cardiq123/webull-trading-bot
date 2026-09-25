"""Reprice the stock strategy's trades as calls and bull call spreads.

The entry and exit dates come from the stock backtest, so the timing is
the same trade. The premium path is Black-Scholes with trailing realized
volatility times ``iv_premium``. Bid/ask is a percent of the mid, wider
when the strike is below 0.50 delta. Nothing here reads an option chain.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from webull_bot.backtest.engine import BacktestResult
from webull_bot.backtest.metrics import compute_metrics
from webull_bot.options.fees import CONTRACT_MULTIPLIER, option_leg_fees
from webull_bot.options.pricing import call_delta, call_price, listed_strike, realized_vol, strike_for_delta

RATE = 0.02
DIVIDEND = 0.018
DTE_DAYS = 45
LONG_DELTA = 0.65
SHORT_DELTA = 0.40
# Half the quoted spread, as a fraction of the mid. OTM (delta under 0.50)
# pays the wider one. ``spread_multiplier`` scales both for the sensitivity.
HALF_SPREAD_ATM = 0.04
HALF_SPREAD_OTM = 0.08
MIN_MID = 0.05
VOL_FLOOR = 0.10
VOL_CAP = 1.50


def _half_spread(delta: float, multiplier: float) -> float:
    base = HALF_SPREAD_ATM if delta >= 0.50 else HALF_SPREAD_OTM
    return base * multiplier


def _buy(mid: float, delta: float, multiplier: float) -> float:
    return mid * (1.0 + _half_spread(delta, multiplier))


def _sell(mid: float, delta: float, multiplier: float) -> float:
    return mid * (1.0 - _half_spread(delta, multiplier))


def _vol_at(rv: pd.Series, ts: pd.Timestamp, iv_premium: float) -> float | None:
    if rv.empty:
        return None
    value = rv.asof(ts)
    if value is None or pd.isna(value):
        return None
    scaled = float(value) * iv_premium
    if scaled != scaled:  # NaN
        return None
    return min(VOL_CAP, max(VOL_FLOOR, scaled))


def _years_left(expiry: pd.Timestamp, ts: pd.Timestamp) -> float:
    days = (expiry.normalize() - pd.Timestamp(ts).normalize()).days
    return max(0.0, days / 365.0)


def simulate_overlay(
    stock_trades: pd.DataFrame,
    bars: dict[str, pd.DataFrame],
    *,
    structure: str,
    iv_premium: float = 1.15,
    spread_multiplier: float = 1.0,
    risk_fraction: float = 0.015,
    starting_equity: float = 100_000.0,
    clock: pd.DatetimeIndex | None = None,
) -> dict[str, Any]:
    """``structure`` is ``call`` or ``spread``.

    Sizing risks ``risk_fraction`` of equity as the debit. A contract that
    cannot be paid for in cash is skipped.
    """
    if structure not in {"call", "spread"}:
        raise ValueError(structure)
    empty = _empty(starting_equity)
    if stock_trades is None or stock_trades.empty:
        return empty
    trades = stock_trades.copy()
    trades["entry_time"] = pd.to_datetime(trades["entry_time"])
    trades["exit_time"] = pd.to_datetime(trades["exit_time"])
    trades = trades.sort_values(["entry_time", "symbol"])
    if clock is None:
        if "SPY" not in bars:
            return empty
        clock = bars["SPY"].index
    clock = pd.DatetimeIndex(clock)
    start = trades["entry_time"].min()
    stop = trades["exit_time"].max()
    clock = clock[(clock >= start) & (clock <= stop)]
    if len(clock) == 0:
        return empty

    rv_cache: dict[str, pd.Series] = {}
    scheduled: list[dict[str, Any]] = []
    for row in trades.itertuples(index=False):
        frame = bars.get(row.symbol)
        if frame is None or frame.empty:
            continue
        if row.symbol not in rv_cache:
            rv_cache[row.symbol] = realized_vol(frame["close"]).shift(1)
        spec = _spec_from_trade(
            row,
            rv_cache[row.symbol],
            structure=structure,
            iv_premium=iv_premium,
            spread_multiplier=spread_multiplier,
        )
        if spec is not None:
            scheduled.append(spec)
    if not scheduled:
        return empty

    by_entry: dict[pd.Timestamp, list[dict[str, Any]]] = {}
    for spec in scheduled:
        by_entry.setdefault(pd.Timestamp(spec["entry_time"]), []).append(spec)

    cash = float(starting_equity)
    open_positions: list[dict[str, Any]] = []
    closed: list[dict[str, Any]] = []
    equity_values: list[float] = []
    exposure_values: list[float] = []
    index: list[pd.Timestamp] = []

    for ts in clock:
        ts = pd.Timestamp(ts)
        still: list[dict[str, Any]] = []
        for pos in open_positions:
            if pd.Timestamp(pos["exit_time"]) <= ts:
                credit = _exit_cash(pos, ts, iv_premium, spread_multiplier, bars)
                cash += credit
                closed.append(
                    {
                        "symbol": pos["symbol"],
                        "strategy": structure,
                        "quantity": pos["contracts"],
                        "entry_time": pos["entry_time"],
                        "entry_price": pos["debit_per_share"],
                        "exit_time": ts,
                        "exit_price": credit / (pos["contracts"] * CONTRACT_MULTIPLIER) if pos["contracts"] else 0.0,
                        "pnl": credit - pos["debit_cash"],
                        "fees": pos["entry_fees"] + pos.get("exit_fees", 0.0),
                        "reason": pos["reason"],
                        "bars_held": pos["bars_held"],
                    }
                )
            else:
                still.append(pos)
        open_positions = still

        equity_now = cash + _mark(open_positions, ts, iv_premium, bars)
        for spec in by_entry.get(ts, []):
            contracts, debit_cash, entry_fees = _size(
            spec, equity_now, cash, spread_multiplier, risk_fraction
        )
            if contracts < 1:
                continue
            cash -= debit_cash
            spec = dict(spec)
            spec["contracts"] = contracts
            spec["debit_cash"] = debit_cash
            spec["entry_fees"] = entry_fees
            open_positions.append(spec)
            equity_now = cash + _mark(open_positions, ts, iv_premium, bars)

        at_risk = sum(pos["debit_cash"] for pos in open_positions)
        equity_values.append(equity_now)
        exposure_values.append(at_risk / equity_now if equity_now else 0.0)
        index.append(ts)

    # Force-flat anything still open on the last bar so the curve realizes.
    if open_positions and index:
        ts = index[-1]
        for pos in open_positions:
            credit = _exit_cash(pos, ts, iv_premium, spread_multiplier, bars)
            cash += credit
            closed.append(
                {
                    "symbol": pos["symbol"],
                    "strategy": structure,
                    "quantity": pos["contracts"],
                    "entry_time": pos["entry_time"],
                    "entry_price": pos["debit_per_share"],
                    "exit_time": ts,
                    "exit_price": 0.0,
                    "pnl": credit - pos["debit_cash"],
                    "fees": pos["entry_fees"],
                    "reason": "window_end",
                    "bars_held": pos["bars_held"],
                }
            )
        equity_values[-1] = cash
        exposure_values[-1] = 0.0

    equity = pd.Series(equity_values, index=pd.DatetimeIndex(index), name="equity")
    exposure = pd.Series(exposure_values, index=equity.index, name="exposure")
    frame = pd.DataFrame(closed)
    result = BacktestResult(
        equity=equity,
        exposure=exposure,
        trades=frame,
        ending_equity=float(equity.iloc[-1]) if len(equity) else starting_equity,
    )
    metrics = compute_metrics(result, starting_equity)
    metrics["avg_hold_sessions"] = float(frame["bars_held"].mean()) if len(frame) else 0.0
    return {"metrics": metrics, "equity": result.daily_equity(), "trades": frame}


def _empty(starting_equity: float) -> dict[str, Any]:
    result = BacktestResult(pd.Series(dtype=float), pd.Series(dtype=float), pd.DataFrame(), ending_equity=starting_equity)
    metrics = compute_metrics(result, starting_equity)
    metrics["avg_hold_sessions"] = 0.0
    return {"metrics": metrics, "equity": result.daily_equity(), "trades": pd.DataFrame()}


def _spec_from_trade(row, rv: pd.Series, *, structure: str, iv_premium: float, spread_multiplier: float) -> dict[str, Any] | None:
    spot = float(row.entry_price)
    sigma = _vol_at(rv, pd.Timestamp(row.entry_time), iv_premium)
    if sigma is None or spot <= 0:
        return None
    t_years = DTE_DAYS / 365.0
    expiry = pd.Timestamp(row.entry_time).normalize() + pd.Timedelta(days=DTE_DAYS)
    long_raw = strike_for_delta(spot, t_years, sigma, LONG_DELTA, RATE, DIVIDEND)
    long_strike = listed_strike(spot, long_raw)
    long_mid = call_price(spot, long_strike, t_years, sigma, RATE, DIVIDEND)
    long_delta = call_delta(spot, long_strike, t_years, sigma, RATE, DIVIDEND)
    if long_mid < MIN_MID:
        return None
    short_strike = None
    short_mid = 0.0
    short_delta = 0.0
    if structure == "spread":
        short_raw = strike_for_delta(spot, t_years, sigma, SHORT_DELTA, RATE, DIVIDEND)
        short_strike = listed_strike(spot, short_raw)
        if short_strike <= long_strike:
            short_strike = listed_strike(spot, long_strike + (1.0 if spot >= 25 else 0.5))
        short_mid = call_price(spot, short_strike, t_years, sigma, RATE, DIVIDEND)
        short_delta = call_delta(spot, short_strike, t_years, sigma, RATE, DIVIDEND)
        debit = _buy(long_mid, long_delta, spread_multiplier) - _sell(short_mid, short_delta, spread_multiplier)
    else:
        debit = _buy(long_mid, long_delta, spread_multiplier)
    if debit <= 0.05:
        return None
    return {
        "symbol": row.symbol,
        "entry_time": pd.Timestamp(row.entry_time),
        "exit_time": pd.Timestamp(row.exit_time),
        "entry_spot": spot,
        "exit_spot": float(row.exit_price),
        "expiry": expiry,
        "sigma_entry": sigma,
        "long_strike": long_strike,
        "short_strike": short_strike,
        "long_delta": long_delta,
        "short_delta": short_delta,
        "debit_per_share": debit,
        "structure": structure,
        "reason": getattr(row, "reason", ""),
        "bars_held": int(getattr(row, "bars_held", 0) or 0),
        "long_mid_entry": long_mid,
        "short_mid_entry": short_mid,
        "rv": rv,
    }


def _size(
    spec: dict[str, Any],
    equity: float,
    cash: float,
    spread_multiplier: float,
    risk_fraction: float,
) -> tuple[int, float, float]:
    per_share = spec["debit_per_share"]
    # Fees scale with contracts except the $0.01 TAF minimum on a short leg.
    unit_fees = _entry_fees(spec, 1, spread_multiplier)
    unit = per_share * CONTRACT_MULTIPLIER + unit_fees
    if unit <= 0 or equity <= 0 or cash <= 0:
        return 0, 0.0, 0.0
    budget = min(equity * risk_fraction, cash)
    contracts = int(budget // unit)
    if contracts < 1:
        return 0, 0.0, 0.0
    fees = _entry_fees(spec, contracts, spread_multiplier)
    debit_cash = per_share * CONTRACT_MULTIPLIER * contracts + fees
    while contracts > 0 and debit_cash > cash:
        contracts -= 1
        fees = _entry_fees(spec, contracts, spread_multiplier)
        debit_cash = per_share * CONTRACT_MULTIPLIER * contracts + fees
    if contracts < 1:
        return 0, 0.0, 0.0
    return contracts, debit_cash, fees


def _entry_fees(spec: dict[str, Any], contracts: int, spread_multiplier: float) -> float:
    long_ask = _buy(spec["long_mid_entry"], spec["long_delta"], spread_multiplier)
    fees = option_leg_fees(contracts, long_ask, sell=False)
    if spec["structure"] == "spread" and spec["short_strike"] is not None:
        short_bid = _sell(spec["short_mid_entry"], spec["short_delta"], spread_multiplier)
        fees += option_leg_fees(contracts, short_bid, sell=True)
    return fees


def _exit_cash(pos: dict[str, Any], ts: pd.Timestamp, iv_premium: float, spread_multiplier: float, bars) -> float:
    frame = bars[pos["symbol"]]
    rv = pos.get("rv")
    if rv is None:
        rv = realized_vol(frame["close"]).shift(1)
    sigma = _vol_at(rv, ts, iv_premium) or pos["sigma_entry"]
    # The stock backtest's exit price is the underlying fill.
    spot = pos["exit_spot"] if pd.Timestamp(pos["exit_time"]) <= ts else float(frame["close"].asof(ts))
    if spot != spot or spot <= 0:
        spot = pos["entry_spot"]
    t_left = _years_left(pos["expiry"], ts)
    long_mid = call_price(spot, pos["long_strike"], t_left, sigma, RATE, DIVIDEND)
    long_delta = call_delta(spot, pos["long_strike"], t_left, sigma, RATE, DIVIDEND) if t_left > 0 else (1.0 if spot > pos["long_strike"] else 0.0)
    contracts = pos["contracts"]
    if t_left <= 0:
        long_cash = max(0.0, spot - pos["long_strike"]) * CONTRACT_MULTIPLIER * contracts
        fees = option_leg_fees(contracts, max(0.0, spot - pos["long_strike"]), sell=True)
        credit = long_cash - fees
        if pos["structure"] == "spread" and pos["short_strike"] is not None:
            short_intr = max(0.0, spot - pos["short_strike"])
            credit -= short_intr * CONTRACT_MULTIPLIER * contracts
            credit -= option_leg_fees(contracts, short_intr, sell=False)
        pos["exit_fees"] = fees
        return credit
    long_bid = _sell(long_mid, max(long_delta, 0.0), spread_multiplier)
    fees = option_leg_fees(contracts, long_bid, sell=True)
    credit = long_bid * CONTRACT_MULTIPLIER * contracts - fees
    if pos["structure"] == "spread" and pos["short_strike"] is not None:
        short_mid = call_price(spot, pos["short_strike"], t_left, sigma, RATE, DIVIDEND)
        short_delta = call_delta(spot, pos["short_strike"], t_left, sigma, RATE, DIVIDEND)
        short_ask = _buy(short_mid, short_delta, spread_multiplier)
        short_fees = option_leg_fees(contracts, short_ask, sell=False)
        credit -= short_ask * CONTRACT_MULTIPLIER * contracts
        credit -= short_fees
        fees += short_fees
    pos["exit_fees"] = fees
    return credit


def _mark(positions: list[dict[str, Any]], ts: pd.Timestamp, iv_premium: float, bars) -> float:
    total = 0.0
    for pos in positions:
        frame = bars.get(pos["symbol"])
        if frame is None:
            continue
        spot = frame["close"].asof(ts)
        if spot is None or pd.isna(spot) or float(spot) <= 0:
            continue
        rv = pos.get("rv")
        if rv is None:
            rv = realized_vol(frame["close"]).shift(1)
        sigma = _vol_at(rv, ts, iv_premium) or pos["sigma_entry"]
        t_left = _years_left(pos["expiry"], ts)
        long_mid = call_price(float(spot), pos["long_strike"], t_left, sigma, RATE, DIVIDEND)
        value = long_mid
        if pos["structure"] == "spread" and pos["short_strike"] is not None:
            short_mid = call_price(float(spot), pos["short_strike"], t_left, sigma, RATE, DIVIDEND)
            value = long_mid - short_mid
        total += value * CONTRACT_MULTIPLIER * pos["contracts"]
    return total
