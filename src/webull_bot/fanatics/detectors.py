"""Causal detectors for the Chart Fanatics specs.

A value at bar ``t`` uses bars at or before ``t``. Swings are confirmed
``right`` bars later. Nothing here places an order.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def value_area(prices: np.ndarray, volumes: np.ndarray, coverage: float = 0.70) -> tuple[float, float, float]:
    """Return ``(poc, vah, val)`` for bins already aggregated by price.

    Expansion starts at the maximum-volume bin and grows toward the
    heavier neighbor until ``coverage`` of the volume is inside. Empty
    input returns NaNs.
    """
    if len(prices) == 0 or float(np.nansum(volumes)) <= 0:
        return (np.nan, np.nan, np.nan)
    order = np.argsort(prices)
    prices = np.asarray(prices, dtype=float)[order]
    volumes = np.asarray(volumes, dtype=float)[order]
    total = float(volumes.sum())
    poc_i = int(np.argmax(volumes))
    lo = hi = poc_i
    filled = float(volumes[poc_i])
    while filled < coverage * total and (lo > 0 or hi < len(prices) - 1):
        left = float(volumes[lo - 1]) if lo > 0 else -1.0
        right = float(volumes[hi + 1]) if hi < len(prices) - 1 else -1.0
        if left > right:
            lo -= 1
            filled += float(volumes[lo])
        elif right > left:
            hi += 1
            filled += float(volumes[hi])
        else:
            if lo > 0:
                lo -= 1
                filled += float(volumes[lo])
            if hi < len(prices) - 1:
                hi += 1
                filled += float(volumes[hi])
    return float(prices[poc_i]), float(prices[hi]), float(prices[lo])


def bullish_fvg(high: np.ndarray, low: np.ndarray) -> np.ndarray:
    """True on the third bar of a bullish three-bar fair-value gap.

    Bar ``t`` completes the gap when ``high[t-2] < low[t]``. The zone is
    ``(high[t-2], low[t])``.
    """
    out = np.zeros(len(high), dtype=bool)
    if len(high) < 3:
        return out
    out[2:] = high[:-2] < low[2:]
    return out


def bearish_fvg(high: np.ndarray, low: np.ndarray) -> np.ndarray:
    """True on the third bar when ``low[t-2] > high[t]``."""
    out = np.zeros(len(high), dtype=bool)
    if len(high) < 3:
        return out
    out[2:] = low[:-2] > high[2:]
    return out


def fvg_bounds(high: np.ndarray, low: np.ndarray, t: int, side: int) -> tuple[float, float, float]:
    """``(low, high, midpoint)`` of the gap that completed on bar ``t``."""
    if side > 0:
        zone_low = float(high[t - 2])
        zone_high = float(low[t])
    else:
        zone_low = float(high[t])
        zone_high = float(low[t - 2])
    return zone_low, zone_high, (zone_low + zone_high) / 2.0


def doji_mask(open_: np.ndarray, high: np.ndarray, low: np.ndarray, close: np.ndarray, body_frac: float) -> np.ndarray:
    """True when the body is at most ``body_frac`` of the range."""
    span = high - low
    body = np.abs(close - open_)
    valid = np.isfinite(span) & (span > 0)
    return valid & (body <= body_frac * span)


def shooting_star(open_: np.ndarray, high: np.ndarray, low: np.ndarray, close: np.ndarray, body_frac: float = 0.35) -> np.ndarray:
    """Upper wick at least twice the body, body at most ``body_frac`` of the range."""
    span = high - low
    body = np.abs(close - open_)
    upper = high - np.maximum(open_, close)
    valid = np.isfinite(span) & (span > 0) & (body > 0)
    return valid & (upper >= 2.0 * body) & (body <= body_frac * span)


def hammer(open_: np.ndarray, high: np.ndarray, low: np.ndarray, close: np.ndarray, body_frac: float = 0.35) -> np.ndarray:
    """Lower wick at least twice the body, body at most ``body_frac`` of the range."""
    span = high - low
    body = np.abs(close - open_)
    lower = np.minimum(open_, close) - low
    valid = np.isfinite(span) & (span > 0) & (body > 0)
    return valid & (lower >= 2.0 * body) & (body <= body_frac * span)


def opening_range(high: np.ndarray, low: np.ndarray, start: int, bars: int) -> tuple[float, float]:
    """High and low of ``bars`` bars beginning at ``start``. Inclusive."""
    stop = start + bars
    if start < 0 or stop > len(high) or bars < 1:
        return (np.nan, np.nan)
    return float(np.max(high[start:stop])), float(np.min(low[start:stop]))


def minute_of_day(index: pd.DatetimeIndex) -> np.ndarray:
    local = index.tz_convert("America/New_York") if index.tz is not None else index
    return local.hour.to_numpy() * 60 + local.minute.to_numpy()


def session_key(index: pd.DatetimeIndex) -> np.ndarray:
    """RTH session date. A bar at or after 18:00 ET belongs to the next session.

    Friday evening belongs to Monday. Sunday evening belongs to Monday.
    """
    local = index.tz_convert("America/New_York") if index.tz is not None else index
    dates = pd.Series(pd.DatetimeIndex(local).normalize())
    late = np.asarray(local.hour) >= 18
    jump = np.where(np.asarray(local.dayofweek) == 4, 3, 1)
    nxt = dates + pd.to_timedelta(jump, unit="D")
    chosen = dates.where(~late, nxt)
    return chosen.dt.strftime("%Y-%m-%d").to_numpy()
