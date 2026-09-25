"""Black-Scholes calls. No SciPy. This is a model, not a historical chain.

IV in the backtest is trailing realized volatility times a premium. There
is no listed bid, no earnings jump, and no early exercise. Call prices are
estimates.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd


def norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def call_price(spot: float, strike: float, t_years: float, sigma: float, rate: float, dividend: float) -> float:
    if spot <= 0 or strike <= 0:
        return 0.0
    if t_years <= 0 or sigma <= 0:
        return max(0.0, spot - strike)
    vol = sigma * math.sqrt(t_years)
    d1 = (math.log(spot / strike) + (rate - dividend + 0.5 * sigma * sigma) * t_years) / vol
    d2 = d1 - vol
    return math.exp(-dividend * t_years) * spot * norm_cdf(d1) - math.exp(-rate * t_years) * strike * norm_cdf(d2)


def call_delta(spot: float, strike: float, t_years: float, sigma: float, rate: float, dividend: float) -> float:
    if spot <= 0 or strike <= 0 or t_years <= 0 or sigma <= 0:
        return 1.0 if spot > strike else 0.0
    vol = sigma * math.sqrt(t_years)
    d1 = (math.log(spot / strike) + (rate - dividend + 0.5 * sigma * sigma) * t_years) / vol
    return math.exp(-dividend * t_years) * norm_cdf(d1)


def put_price(spot: float, strike: float, t_years: float, sigma: float, rate: float, dividend: float) -> float:
    """Put from put-call parity. Same model limits as ``call_price``."""
    if spot <= 0 or strike <= 0:
        return 0.0
    if t_years <= 0 or sigma <= 0:
        return max(0.0, strike - spot)
    call = call_price(spot, strike, t_years, sigma, rate, dividend)
    return call - math.exp(-dividend * t_years) * spot + math.exp(-rate * t_years) * strike


def put_delta(spot: float, strike: float, t_years: float, sigma: float, rate: float, dividend: float) -> float:
    if spot <= 0 or strike <= 0 or t_years <= 0 or sigma <= 0:
        return -1.0 if spot < strike else 0.0
    return call_delta(spot, strike, t_years, sigma, rate, dividend) - math.exp(-dividend * t_years)


def option_price(right: str, spot: float, strike: float, t_years: float, sigma: float, rate: float, dividend: float) -> float:
    if right == "put":
        return put_price(spot, strike, t_years, sigma, rate, dividend)
    return call_price(spot, strike, t_years, sigma, rate, dividend)


def option_delta(right: str, spot: float, strike: float, t_years: float, sigma: float, rate: float, dividend: float) -> float:
    if right == "put":
        return put_delta(spot, strike, t_years, sigma, rate, dividend)
    return call_delta(spot, strike, t_years, sigma, rate, dividend)


def strike_for_delta(
    spot: float,
    t_years: float,
    sigma: float,
    target_delta: float,
    rate: float,
    dividend: float,
) -> float:
    """Higher strikes have lower call deltas. Returns a raw (unrounded) strike."""
    lo = spot * 0.2
    hi = spot * 3.0
    for _ in range(48):
        mid = 0.5 * (lo + hi)
        delta = call_delta(spot, mid, t_years, sigma, rate, dividend)
        if delta > target_delta:
            lo = mid
        else:
            hi = mid
    return hi


def strike_for_put_delta(
    spot: float,
    t_years: float,
    sigma: float,
    target_abs_delta: float,
    rate: float,
    dividend: float,
) -> float:
    """Strike whose put delta is about ``-target_abs_delta``. Higher strikes are more negative."""
    lo = spot * 0.2
    hi = spot * 3.0
    target = -abs(target_abs_delta)
    for _ in range(48):
        mid = 0.5 * (lo + hi)
        delta = put_delta(spot, mid, t_years, sigma, rate, dividend)
        if delta > target:
            lo = mid
        else:
            hi = mid
    return hi


def listed_strike(spot: float, raw: float) -> float:
    step = 1.0 if spot >= 25.0 else 0.5
    return max(step, round(raw / step) * step)


def realized_vol(close: pd.Series, window: int = 20) -> pd.Series:
    log_ret = np.log(close / close.shift(1))
    return log_ret.rolling(window, min_periods=window).std() * math.sqrt(252)
