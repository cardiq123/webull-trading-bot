"""Dow wedge, triangle, and horizontal-range breakouts.

Pre-registered before the out-of-sample run. The grid is the six variants
in ``param_grid``. The breakout buffer stays 0.25 ATR except where a
variant says otherwise, and it does not: buffer, hold time, and the option
contract (DTE, delta, 30% target, 50% premium stop) are fixed. Walk-forward
may switch pattern family, volume, lookback, or long-only. It may not
retune the option.

Default:

* Point-in-time Dow 30, both directions.
* A falling wedge, rising wedge, or symmetrical triangle: least-squares
  lines through at least two confirmed 3/3 pivots each, pivots inside the
  last 40 bars, span at least 15 bars, and the gap at least 20% tighter
  than at the start of the span.
* Entry when the close clears the line by 0.25 ATR and the candle body is
  at least 60% of the range, with the close in the extreme quarter.
* Bullish breaks are long stock / long calls. Bearish breaks are short
  stock / long puts in the research books. The engine only buys the longs.
* Invalidation is a later close back inside the extended line. The hard
  stop is the far side of the pattern minus or plus 0.25 ATR. Target is
  the pattern height measured at the start of the span. Time stop is 10
  sessions. Fill is the next open.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from webull_bot.indicators import atr, sma
from webull_bot.patterns import prior_range, strong_breakout_candle, wedge_lines
from webull_bot.strategies.base import Strategy
from webull_bot.strategies.bluechip_reversal import member_mask
from webull_bot.strategies.signals import blank, limit_symbols
from webull_bot.universe_dow import all_dow_tickers


class WedgeBreakout(Strategy):
    name = "wedge_breakout"
    citation = (
        "Point-in-time Dow 30. Breakout from a converging wedge or triangle, "
        "or from a prior-window horizontal range, confirmed by a wide-body "
        "candle. Puts and short stock are research baselines. Option P&L is "
        "a Black-Scholes estimate with a 30% premium target."
    )
    style = "swing"
    holds_overnight = True
    survivorship_sensitive = False
    custom_universe = True
    short_sample = False
    trail_pct = None
    default_params = {
        "pattern": "wedge",
        "lookback": 40,
        "buffer_atr": 0.25,
        "volume_filter": False,
        "long_only": False,
        "pivot_left": 3,
        "pivot_right": 3,
        "min_span": 15,
        "contraction": 0.80,
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
            {"pattern": "horizontal"},
            {"volume_filter": True},
            {"lookback": 25},
            {"lookback": 60},
            {"long_only": True},
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
        for symbol, frame in limit_symbols(bars, params).items():
            if len(frame) < int(params["lookback"]) + 10:
                continue
            signals = _signals(symbol, frame, params)
            if signals is not None:
                out[symbol] = signals
        return out


def _signals(symbol: str, frame: pd.DataFrame, params: dict) -> pd.DataFrame | None:
    close = frame["close"].to_numpy(dtype=float)
    high = frame["high"]
    low = frame["low"]
    width = atr(frame, 14).to_numpy(dtype=float)
    lookback = int(params["lookback"])
    if params["pattern"] == "horizontal":
        levels = prior_range(high, low, lookback)
        upper = levels["upper"].to_numpy(dtype=float)
        lower = levels["lower"].to_numpy(dtype=float)
        up_slope = np.zeros(len(frame))
        down_slope = np.zeros(len(frame))
        start = np.full(len(frame), np.nan)
        start[:] = np.arange(len(frame)) - lookback
    else:
        lines = wedge_lines(
            high,
            low,
            int(params["pivot_left"]),
            int(params["pivot_right"]),
            lookback=lookback,
            min_span=int(params["min_span"]),
            contraction=float(params["contraction"]),
        )
        upper = lines["upper"].to_numpy(dtype=float)
        lower = lines["lower"].to_numpy(dtype=float)
        up_slope = lines["upper_slope"].to_numpy(dtype=float)
        down_slope = lines["lower_slope"].to_numpy(dtype=float)
        start = lines["start"].to_numpy(dtype=float)
    bull_candle = strong_breakout_candle(frame, side="bull").to_numpy(dtype=bool)
    bear_candle = strong_breakout_candle(frame, side="bear").to_numpy(dtype=bool)
    buffer = float(params["buffer_atr"])
    bull = np.zeros(len(frame), dtype=bool)
    bear = np.zeros(len(frame), dtype=bool)
    for t in range(len(frame)):
        if not np.isfinite(width[t]) or width[t] <= 0:
            continue
        if not np.isfinite(upper[t]) or not np.isfinite(lower[t]):
            continue
        if bull_candle[t] and close[t] > upper[t] + buffer * width[t]:
            bull[t] = True
        elif bear_candle[t] and close[t] < lower[t] - buffer * width[t]:
            bear[t] = True
    if params["volume_filter"]:
        volume_ok = (frame["volume"] > sma(frame["volume"], 20)).fillna(False).to_numpy(dtype=bool)
        bull &= volume_ok
        bear &= volume_ok
    if params["long_only"]:
        bear[:] = False
    member = member_mask(symbol, frame.index).fillna(False).to_numpy(dtype=bool)
    bull &= member
    bear &= member
    stop = np.full(len(frame), np.nan)
    target = np.full(len(frame), np.nan)
    inv_level = np.full(len(frame), np.nan)
    inv_slope = np.zeros(len(frame))
    stop_pad = float(params["stop_atr"])
    for t in range(len(frame)):
        if not (bull[t] or bear[t]):
            continue
        if params["pattern"] == "horizontal":
            height = upper[t] - lower[t]
        else:
            origin = int(start[t]) if np.isfinite(start[t]) else t
            origin = min(max(origin, 0), len(frame) - 1)
            up_then = upper[origin] if np.isfinite(upper[origin]) else upper[t]
            down_then = lower[origin] if np.isfinite(lower[origin]) else lower[t]
            height = up_then - down_then
            if not np.isfinite(height) or height <= 0:
                height = upper[t] - lower[t]
        if bull[t]:
            stop[t] = lower[t] - stop_pad * width[t]
            target[t] = close[t] + height
            inv_level[t] = upper[t]
            inv_slope[t] = up_slope[t] if np.isfinite(up_slope[t]) else 0.0
        else:
            stop[t] = upper[t] + stop_pad * width[t]
            target[t] = close[t] - height
            inv_level[t] = lower[t]
            inv_slope[t] = down_slope[t] if np.isfinite(down_slope[t]) else 0.0
    max_hold = int(params["max_hold"])
    exit_inside = _back_inside(bull, bear, close, inv_level, inv_slope, max_hold)
    was_member = member_mask(symbol, frame.index).shift(1).fillna(False).to_numpy(dtype=bool)
    left_index = was_member & ~member
    signals = blank(frame.index)
    signals["entry_next_open"] = bull
    signals["short_next_open"] = bear
    signals["exit_next_open"] = exit_inside | left_index
    signals["stop_price"] = np.where(bull, stop, np.nan)
    signals["take_profit"] = np.where(bull, target, np.nan)
    signals["max_hold"] = max_hold
    signals["inv_level"] = inv_level
    signals["inv_slope"] = inv_slope
    signals["short_stop"] = np.where(bear, stop, np.nan)
    signals["short_target"] = np.where(bear, target, np.nan)
    return signals


def _back_inside(
    bull: np.ndarray,
    bear: np.ndarray,
    close: np.ndarray,
    level: np.ndarray,
    slope: np.ndarray,
    max_hold: int,
) -> np.ndarray:
    """Close back through the broken line while that breakout is still the active one."""
    exit_flag = np.zeros(len(close), dtype=bool)
    side = 0
    until = -1
    origin = 0
    base = np.nan
    line_slope = 0.0
    for t in range(len(close)):
        if side != 0 and t <= until and np.isfinite(close[t]) and np.isfinite(base):
            line = base + line_slope * (t - origin)
            if (side == 1 and close[t] < line) or (side == -1 and close[t] > line):
                exit_flag[t] = True
                side = 0
        if bull[t] and np.isfinite(level[t]):
            side = 1
            until = t + max_hold
            origin = t
            base = level[t]
            line_slope = slope[t]
        elif bear[t] and np.isfinite(level[t]):
            side = -1
            until = t + max_hold
            origin = t
            base = level[t]
            line_slope = slope[t]
    return exit_flag
