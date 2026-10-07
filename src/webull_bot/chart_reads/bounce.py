"""Partial reversal bounce. Long only. Frozen before the book was scored.

A low often bounces to the next band, the 20 or 50 EMA, or a descending
trendline and then fails, without the downtrend ending. This entry takes
that bounce. It does not wait for a trend change.

The signal bar has to tag a confirmed pivot low, hold above it, and print
a confirming candle. RSI(14) is oversold or turning up from a weak reading.
Quiet volume into the low is a sensitivity, not the default. The fill is
the next session's open. The stop is under that low.

The partial target is the nearest of the next confirmed pivot high, the
20 EMA, the 50 EMA, and the descending pivot trendline, when that price
is between 0.5R and 4R. Otherwise the target is 1R. The full-reversal
price stored on the setup is the next one of those objectives beyond the
partial target, out to 8R, otherwise 3R. Nothing here places an order.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from webull_bot.chart_reads.detect import Setup, strong_candle
from webull_bot.chart_reads.levels import _falling_trendline
from webull_bot.indicators import atr, ema, rsi
from webull_bot.patterns import _pivot_points, confirmed_pivot_high, confirmed_pivot_low

PIVOT_LEFT = 4
PIVOT_RIGHT = 4
LOOKBACK = 120
MIN_PIVOT_AGE = 5
TOUCH_ATR = 0.50
HOLD_ATR = 0.10
STOP_ATR = 0.25
RSI_WINDOW = 14
RSI_OVERSOLD = 30.0
RSI_TURN_MAX = 45.0
BODY = 0.50
CLOSE_FRAC = 2.0 / 3.0
MIN_TARGET_R = 0.5
MAX_TARGET_R = 4.0
FULL_MAX_R = 8.0
PARTIAL_FALLBACK_R = 1.0
FULL_FALLBACK_R = 3.0
COOLDOWN = 10
QUIET_WINDOW = 20
QUIET_BARS = 3
QUIET_MAX = 1.0
WARMUP = 60

PARTIAL_HOLD = 15
FULL_HOLD = 40


def partial_params() -> dict:
    """Level target, 1R fallback, no EMA trail. The trail would flatten a long still under the 20 EMA."""
    return _params(reward_r=PARTIAL_FALLBACK_R, hold=PARTIAL_HOLD)


def fixed_params() -> dict:
    """Same stop and hold. The target is 1R, not a level."""
    chosen = partial_params()
    chosen["target_mode"] = "r"
    chosen["reward_r"] = PARTIAL_FALLBACK_R
    return chosen


def reversal_params() -> dict:
    """Same entries and stop. Farther target, longer hold, 3R fallback."""
    return _params(reward_r=FULL_FALLBACK_R, hold=FULL_HOLD)


def _params(*, reward_r: float, hold: int) -> dict:
    return {
        "reward_r": float(reward_r),
        "target_mode": "level",
        "level_source": "reference",
        "trail": "none",
        "flatten_eod": False,
        "max_hold_sessions": int(hold),
        "pdt_prospective": False,
        "risk_fraction": 0.20,
        "max_positions": 1,
        "account": "margin_pdt",
        "expression": "stock",
        "delta": 0.45,
        "dte": 45,
        "spread_width": 5.0,
        "spread_dte": 45,
        "iv_premium": 1.15,
        "spread_multiplier": 1.0,
        "band_std": 2.0,
    }


def _nearest(prices: list[float], floor: float, cap: float) -> float:
    if not np.isfinite(floor) or not np.isfinite(cap) or cap < floor:
        return float("nan")
    chosen = [price for price in prices if np.isfinite(price) and floor <= price <= cap]
    return float(min(chosen)) if chosen else float("nan")


def _quiet(volume: np.ndarray, index: int) -> bool:
    if index < QUIET_WINDOW:
        return False
    prior = float(np.mean(volume[index - QUIET_WINDOW : index]))
    recent = float(np.mean(volume[index - QUIET_BARS + 1 : index + 1]))
    if not np.isfinite(prior) or prior <= 0 or not np.isfinite(recent):
        return False
    return recent <= QUIET_MAX * prior


def find_bounces(frame: pd.DataFrame, symbol: str, *, quiet: bool = False) -> list[Setup]:
    """Long bounces. ``quiet`` requires the last three bars to be at or under the prior 20-bar average volume."""
    if frame is None or len(frame) < WARMUP + 2:
        return []
    bars = frame.sort_index()
    open_ = bars["open"].to_numpy(dtype=float)
    high = bars["high"].to_numpy(dtype=float)
    low = bars["low"].to_numpy(dtype=float)
    close = bars["close"].to_numpy(dtype=float)
    volume = bars["volume"].to_numpy(dtype=float) if "volume" in bars.columns else np.ones(len(bars))
    widths = atr(bars).to_numpy(dtype=float)
    momentum = rsi(bars["close"].astype(float), RSI_WINDOW).to_numpy(dtype=float)
    ema20 = ema(bars["close"].astype(float), 20).to_numpy(dtype=float)
    ema50 = ema(bars["close"].astype(float), 50).to_numpy(dtype=float)
    trend = _falling_trendline(bars["high"])
    pivot_lows = _pivot_points(confirmed_pivot_low(bars["low"], PIVOT_LEFT, PIVOT_RIGHT), PIVOT_RIGHT)
    pivot_highs = _pivot_points(confirmed_pivot_high(bars["high"], PIVOT_LEFT, PIVOT_RIGHT), PIVOT_RIGHT)
    index = bars.index
    n = len(bars)
    found: list[Setup] = []
    last = -10_000
    low_ptr = 0
    high_ptr = 0
    known_lows: list[tuple[int, float, int]] = []
    known_highs: list[tuple[int, float, int]] = []
    for t in range(WARMUP, n - 1):
        while low_ptr < len(pivot_lows) and pivot_lows[low_ptr][2] < t:
            known_lows.append(pivot_lows[low_ptr])
            low_ptr += 1
        while high_ptr < len(pivot_highs) and pivot_highs[high_ptr][2] < t:
            known_highs.append(pivot_highs[high_ptr])
            high_ptr += 1
        if t - last < COOLDOWN:
            continue
        width = widths[t]
        if not np.isfinite(width) or width <= 0:
            continue
        if not np.isfinite(momentum[t]) or not np.isfinite(momentum[t - 1]):
            continue
        oversold = momentum[t] <= RSI_OVERSOLD
        turning = momentum[t] > momentum[t - 1] and momentum[t - 1] <= RSI_TURN_MAX
        if not (oversold or turning):
            continue
        if not strong_candle(open_[t], high[t], low[t], close[t], "long", BODY, CLOSE_FRAC):
            continue
        if quiet and not _quiet(volume, t):
            continue
        tagged = _tagged_low(known_lows, t, low[t], close[t], width)
        if tagged is None:
            continue
        pivot_index, _pivot_price = tagged
        stop = float(low[t] - STOP_ATR * width)
        risk = float(close[t] - stop)
        if not np.isfinite(risk) or risk <= 0:
            continue
        overhead = _overhead(known_highs, t, close[t], ema20[t], ema50[t], trend[t])
        partial = _nearest(overhead, close[t] + MIN_TARGET_R * risk, close[t] + MAX_TARGET_R * risk)
        beyond = partial + 0.10 * width if np.isfinite(partial) else close[t] + MIN_TARGET_R * risk
        reversal = _nearest(overhead, beyond, close[t] + FULL_MAX_R * risk)
        if not np.isfinite(reversal):
            reversal = float(close[t] + FULL_FALLBACK_R * risk)
        found.append(
            Setup(
                symbol=symbol,
                direction="long",
                kind="bounce",
                signal_time=pd.Timestamp(index[t]),
                fill_time=pd.Timestamp(index[t + 1]),
                anchor_time=pd.Timestamp(index[pivot_index]),
                stop=stop,
                atr=float(width),
                reference=float(partial) if np.isfinite(partial) else float("nan"),
                reversal=float(reversal),
            )
        )
        last = t
    return found


def _tagged_low(pivots: list[tuple[int, float, int]], index: int, bar_low: float, bar_close: float, width: float):
    """Nearest prior pivot low the bar tags and does not close through."""
    best = None
    best_gap = None
    for pivot_index, price, _confirm in reversed(pivots):
        if pivot_index < index - LOOKBACK:
            break
        if index - pivot_index < MIN_PIVOT_AGE:
            continue
        gap = abs(bar_low - price)
        if gap > TOUCH_ATR * width:
            continue
        if bar_close < price - HOLD_ATR * width:
            continue
        if best_gap is None or gap < best_gap:
            best = (pivot_index, price)
            best_gap = gap
    return best


def _overhead(highs: list[tuple[int, float, int]], index: int, close: float, ema20: float, ema50: float, trend: float) -> list[float]:
    prices = []
    for pivot_index, price, _confirm in highs:
        if pivot_index < index - LOOKBACK:
            continue
        if price > close:
            prices.append(float(price))
    for level in (ema20, ema50, trend):
        if np.isfinite(level) and level > close:
            prices.append(float(level))
    return prices


def as_reversal(setups: list[Setup]) -> list[Setup]:
    """Same entry and stop. The reference becomes the farther reversal price."""
    cloned = []
    for setup in setups:
        cloned.append(
            Setup(
                symbol=setup.symbol,
                direction=setup.direction,
                kind=setup.kind,
                signal_time=setup.signal_time,
                fill_time=setup.fill_time,
                anchor_time=setup.anchor_time,
                stop=setup.stop,
                atr=setup.atr,
                reference=float(setup.reversal),
                reversal=float(setup.reversal),
            )
        )
    return cloned
