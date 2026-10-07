"""Dow reversal off a low that is sitting on support.

Pre-registered before the out-of-sample run. The grid is the six variants
in ``param_grid``. Bullish divergence, anchored VWAP, and the 8-day EMA
were not searched. The option expression (30% premium target, 21/30/45
DTE, 0.50/0.65 delta) is not part of this grid and is not chosen by
walk-forward.

Default:

* Point-in-time Dow 30.
* The bar makes or tags the prior 20-day low, within 0.25 ATR.
* That low is inside a horizontal zone: at least two confirmed 3/3 pivot
  lows within 1.25 ATR and the last 180 sessions.
* A bullish candle on one of the next two bars: engulfing, a hammer/pin
  whose lower wick is at least twice the body, or a close in the top
  quarter of the range through the prior high.
* Stop is the setup low minus 0.25 ATR. Target is the last confirmed
  swing high when it is above the close. Time stop is 10 sessions.
* Fill is the next open.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from webull_bot.indicators import atr, ema, rsi
from webull_bot.patterns import (
    confirmed_pivot_high,
    horizontal_support,
    prior_month_reference_low,
    prior_n_day_low,
    prior_ytd_low,
    rising_trendline,
    tags_level,
    trendline_touch,
    bullish_reversal_candle,
)
from webull_bot.strategies.base import Strategy
from webull_bot.strategies.bluechip_reversal import member_mask
from webull_bot.strategies.signals import blank, limit_symbols
from webull_bot.universe_dow import all_dow_tickers


class SupportReversal(Strategy):
    name = "support_reversal"
    citation = (
        "Point-in-time Dow 30. Reversal off a 20-day, monthly, or year-to-date "
        "low that tags horizontal pivot support or a rising pivot trendline, "
        "confirmed by a bullish candle. Option P&L is a Black-Scholes estimate "
        "with a 30% premium target."
    )
    style = "swing"
    holds_overnight = True
    survivorship_sensitive = False
    custom_universe = True
    short_sample = False
    trail_pct = None
    default_params = {
        "low_mode": "d20",
        "support": "horizontal",
        "zone_atr": 1.25,
        "tag_atr": 0.25,
        "line_atr": 0.50,
        "confirm_bars": 2,
        "pivot_left": 3,
        "pivot_right": 3,
        "rsi_filter": False,
        "ema_filter": False,
        "stop_atr": 0.25,
        "max_hold": 10,
    }

    def universe(self, mode: str) -> list[str]:
        if mode == "dow":
            return all_dow_tickers()
        return []

    def param_grid(self) -> list[dict[str, Any]]:
        """Six pre-registered variants. Not a cartesian product."""
        variants = [
            {},
            {"low_mode": "ytd"},
            {"low_mode": "month"},
            {"support": "trendline"},
            {"rsi_filter": True},
            {"ema_filter": True},
        ]
        grid = []
        for update in variants:
            params = dict(self.default_params)
            params.update(update)
            grid.append(params)
        return grid

    def generate(self, bars, regime, params):
        del regime
        out: dict[str, pd.DataFrame] = {}
        left = int(params["pivot_left"])
        right = int(params["pivot_right"])
        for symbol, frame in limit_symbols(bars, params).items():
            if len(frame) < 60:
                continue
            signals = _signals(symbol, frame, params, left, right)
            if signals is not None:
                out[symbol] = signals
        return out


def _signals(symbol: str, frame: pd.DataFrame, params: dict, left: int, right: int) -> pd.DataFrame | None:
    close = frame["close"]
    low = frame["low"]
    width = atr(frame, 14)
    if params["low_mode"] == "ytd":
        level = prior_ytd_low(low)
    elif params["low_mode"] == "month":
        level = prior_month_reference_low(low)
    else:
        level = prior_n_day_low(low, 20)
    tagged = tags_level(low, level, width, float(params["tag_atr"]))
    if params["support"] == "trendline":
        line = rising_trendline(low, left, right)
        supported = trendline_touch(low, line, width, float(params["line_atr"]))
    else:
        supported = horizontal_support(
            low, width, left, right, zone_atr=float(params["zone_atr"])
        )
    setup = tagged & supported
    if params["rsi_filter"]:
        setup = setup & (rsi(close, 14) < 30)
    candle = bullish_reversal_candle(frame)
    if params["ema_filter"]:
        average = ema(close, 10)
        candle = candle & (close > average) & (close.shift(1) <= average.shift(1))
    member = member_mask(symbol, frame.index)
    setup = setup & member
    entry, stop, invalidation = _confirm_stops(
        setup.fillna(False).to_numpy(dtype=bool),
        candle.fillna(False).to_numpy(dtype=bool),
        low.to_numpy(dtype=float),
        width.to_numpy(dtype=float),
        float(params["stop_atr"]),
        int(params["confirm_bars"]),
    )
    entry = entry & member.fillna(False).to_numpy(dtype=bool)
    max_hold = int(params["max_hold"])
    exit_inside = _close_through_level(entry, close.to_numpy(dtype=float), invalidation, max_hold)
    swing_high = confirmed_pivot_high(frame["high"], left, right).ffill()
    target = swing_high.where(swing_high > close)
    was_member = member.shift(1).fillna(False)
    left_index = (was_member & ~member).fillna(False).to_numpy(dtype=bool)
    signals = blank(frame.index)
    signals["entry_next_open"] = entry
    signals["short_next_open"] = False
    signals["exit_next_open"] = exit_inside | left_index
    signals["stop_price"] = stop
    signals["take_profit"] = target.to_numpy()
    signals["max_hold"] = max_hold
    signals["inv_level"] = invalidation
    signals["inv_slope"] = 0.0
    return signals


def _confirm_stops(
    setup: np.ndarray,
    candle: np.ndarray,
    low: np.ndarray,
    width: np.ndarray,
    stop_atr: float,
    within: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    entry = np.zeros(len(setup), dtype=bool)
    stop = np.full(len(setup), np.nan)
    invalidation = np.full(len(setup), np.nan)
    for t in range(len(setup)):
        if not setup[t] or not np.isfinite(low[t]) or not np.isfinite(width[t]):
            continue
        for step in range(1, within + 1):
            j = t + step
            if j >= len(setup):
                break
            if entry[j]:
                break
            if candle[j]:
                entry[j] = True
                invalidation[j] = low[t]
                stop[j] = low[t] - stop_atr * width[t]
                break
    return entry, stop, invalidation


def _close_through_level(entry: np.ndarray, close: np.ndarray, level: np.ndarray, max_hold: int) -> np.ndarray:
    """Close back through the setup low during the hold. Causal."""
    exit_flag = np.zeros(len(entry), dtype=bool)
    active_until = -1
    invalid = np.nan
    for t in range(len(entry)):
        if active_until >= t and np.isfinite(invalid) and np.isfinite(close[t]) and close[t] < invalid:
            exit_flag[t] = True
            active_until = -1
        if entry[t] and np.isfinite(level[t]):
            active_until = t + max_hold
            invalid = level[t]
    return exit_flag
