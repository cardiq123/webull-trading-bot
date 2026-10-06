"""Breakout, then a chop pullback that holds the broken level.

Frozen before this book was scored. The chop flag is the one in ``chop.py``.
Nothing here changes that flag, and nothing here places an order.

The sequence, read only from bars that have closed:

* A multi-day shelf. The prior 10 sessions are a range when the high and the
  low are each touched in at least two of those sessions, within the frozen
  0.50 ATR touch, and the height sits inside setup D's frozen ATR bounds.
* A breakout. A strong candle closes through that high, or through that low,
  by the chop study's 0.10 ATR buffer and on the breakout side of session VWAP.
* A rejection. After that close, and no later than the chop zone, a bar tags
  the 2-standard-deviation session VWAP band and closes back inside it.
* A chop pullback. At least six contiguous bars inside the next 5 sessions
  carry the frozen chop flag, and that zone trades back to the broken level.
* A hold. From the bar after the breakout through the signal, no close is
  back through the level, and no wick exceeds the 0.50 ATR touch.
* Resumption. The next strong candle closes out of the chop zone, still on
  the breakout side of VWAP. The fill is the next bar's open. The stop is
  0.10 ATR under the support on a long, or above it on a short. If the
  pullback wicked through the level and still held, the stop is 0.10 ATR
  beyond that wick instead. The reference is the range height measured
  from the broken side.

One attempt per breakout. The next attempt starts when the pullback window
ends, when the hold fails, or after the cooldown that follows a signal.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from webull_bot.chart_reads.chop import (
    BODY,
    BREAK_BUFFER_ATR,
    BREAK_COOLDOWN,
    CLOSE_FRAC,
    MIN_CHOP_BARS,
    features,
)
from webull_bot.chart_reads.detect import Setup, session_bands, strong_candle
from webull_bot.chart_reads.params import BREAKOUT_DEFAULTS, DEFAULTS
from webull_bot.mtf_vwap.detect import rth

RANGE_SESSIONS = 10
PULLBACK_SESSIONS = 5
MIN_TOUCHES = 2
TOUCH_ATR = float(DEFAULTS["touch_atr"])
MIN_HEIGHT_ATR = float(BREAKOUT_DEFAULTS["min_height_atr"])
MAX_HEIGHT_ATR = float(BREAKOUT_DEFAULTS["max_height_atr"])
BAND_STD = float(DEFAULTS["band_std"])
# features() needs the bandwidth rank and the slow volume average.
WARMUP = 120


@dataclass(frozen=True)
class HoldMark:
    setup: Setup
    level: float
    breakout_time: pd.Timestamp
    chop_start: pd.Timestamp
    chop_end: pd.Timestamp


def find_chop_holds(frame: pd.DataFrame, *, symbol: str = "") -> list[Setup]:
    return [mark.setup for mark in scan_chop_holds(frame, symbol=symbol)]


def attempt_counts(frame: pd.DataFrame) -> dict:
    """How often each step of the frozen sequence shows up. Not a new entry."""
    counts = {
        "breakouts": 0,
        "rejected": 0,
        "chop_runs": 0,
        "hold_breaks": 0,
        "signals": 0,
    }
    scan_chop_holds(frame, counts=counts)
    return counts


def scan_chop_holds(frame: pd.DataFrame, *, symbol: str = "", counts: dict | None = None) -> list[HoldMark]:
    """Causal scan. Bar t does not use a later bar, except the next open as the fill."""
    bars = rth(frame)
    if bars is None or len(bars) < WARMUP + 2:
        return []
    feat = features(bars)
    bands = session_bands(bars, BAND_STD).reindex(bars.index)
    index = bars.index
    dates = np.array([ts.date() for ts in index])
    session_starts, session_ends, session_of = _sessions(dates)
    if len(session_starts) <= RANGE_SESSIONS:
        return []
    high = bars["high"].to_numpy(dtype=float)
    low = bars["low"].to_numpy(dtype=float)
    open_ = bars["open"].to_numpy(dtype=float)
    close = bars["close"].to_numpy(dtype=float)
    width = feat["atr"].to_numpy(dtype=float)
    vwap = feat["vwap"].to_numpy(dtype=float)
    chop = feat["chop"].to_numpy(dtype=bool)
    upper = bands["upper"].to_numpy(dtype=float)
    lower = bands["lower"].to_numpy(dtype=float)
    std = bands["std"].to_numpy(dtype=float)
    n = len(bars)
    found: list[HoldMark] = []
    i = WARMUP
    while i < n - 1:
        sid = int(session_of[i])
        if sid < RANGE_SESSIONS:
            i += 1
            continue
        scale = width[i]
        if not np.isfinite(scale) or scale <= 0 or not np.isfinite(vwap[i]):
            i += 1
            continue
        range_lo = int(session_starts[sid - RANGE_SESSIONS])
        range_hi = int(session_starts[sid])
        shelf = _shelf(high, low, close, dates, range_lo, range_hi, scale)
        if shelf is None:
            i += 1
            continue
        range_high, range_low, height = shelf
        direction, level = _break_side(
            open_[i], high[i], low[i], close[i], vwap[i], range_high, range_low, scale
        )
        if direction == "":
            i += 1
            continue
        _bump(counts, "breakouts")
        window_end = int(session_ends[min(sid + PULLBACK_SESSIONS - 1, len(session_ends) - 1)])
        mark, resume = _resolve(
            symbol,
            direction,
            i,
            level,
            height,
            window_end,
            index,
            high,
            low,
            open_,
            close,
            width,
            vwap,
            chop,
            upper,
            lower,
            std,
            counts,
        )
        if mark is not None:
            found.append(mark)
        i = resume
    return found


def _break_side(open_, high, low, close, vwap, range_high, range_low, scale) -> tuple[str, float]:
    buffer = BREAK_BUFFER_ATR * scale
    if close >= range_high + buffer and close > vwap:
        if strong_candle(open_, high, low, close, "long", BODY, CLOSE_FRAC):
            return "long", float(range_high)
    if close <= range_low - buffer and close < vwap:
        if strong_candle(open_, high, low, close, "short", BODY, CLOSE_FRAC):
            return "short", float(range_low)
    return "", float("nan")


def _resolve(
    symbol,
    direction,
    breakout,
    level,
    height,
    window_end,
    index,
    high,
    low,
    open_,
    close,
    width,
    vwap,
    chop,
    upper,
    lower,
    std,
    counts=None,
):
    """Return ``(mark or None, next index)``."""
    n = len(close)
    zone_end = min(int(window_end), n)
    for start, stop in _runs(chop, breakout + 1, zone_end):
        if stop - start < MIN_CHOP_BARS:
            continue
        _bump(counts, "chop_runs")
        if not _retested(direction, low, high, start, stop, level, width[breakout]):
            continue
        if _violates(direction, close, low, high, breakout + 1, stop - 1, level, width[breakout]):
            _bump(counts, "hold_breaks")
            fail = _first_violation(direction, close, low, high, breakout + 1, stop - 1, level, width[breakout])
            return None, fail + 1
        if not _rejected(direction, high, low, close, upper, lower, std, breakout, stop):
            continue
        _bump(counts, "rejected")
        mark, resume = _resume(
            symbol,
            direction,
            breakout,
            level,
            height,
            start,
            stop,
            zone_end,
            index,
            high,
            low,
            open_,
            close,
            width,
            vwap,
        )
        if mark is not None:
            _bump(counts, "signals")
        return mark, resume
    return None, zone_end


def _resume(
    symbol,
    direction,
    breakout,
    level,
    height,
    start,
    stop,
    zone_end,
    index,
    high,
    low,
    open_,
    close,
    width,
    vwap,
):
    n = len(close)
    chop_high = float(np.max(high[start:stop]))
    chop_low = float(np.min(low[start:stop]))
    for entry in range(stop, zone_end):
        if entry + 1 >= n:
            return None, n
        if _violates(direction, close, low, high, entry, entry, level, width[breakout]):
            return None, entry + 1
        scale = width[entry]
        if not np.isfinite(scale) or scale <= 0 or not np.isfinite(vwap[entry]):
            continue
        if not strong_candle(open_[entry], high[entry], low[entry], close[entry], direction, BODY, CLOSE_FRAC):
            continue
        if direction == "long":
            if close[entry] <= chop_high or close[entry] <= vwap[entry]:
                continue
            extreme = min(float(np.min(low[breakout + 1 : entry + 1])), float(level))
            stop_px = extreme - BREAK_BUFFER_ATR * scale
            if not np.isfinite(stop_px) or stop_px >= close[entry]:
                continue
            reference = level + height
        else:
            if close[entry] >= chop_low or close[entry] >= vwap[entry]:
                continue
            extreme = max(float(np.max(high[breakout + 1 : entry + 1])), float(level))
            stop_px = extreme + BREAK_BUFFER_ATR * scale
            if not np.isfinite(stop_px) or stop_px <= close[entry]:
                continue
            reference = level - height
        setup = Setup(
            symbol=symbol,
            direction=direction,
            kind="hold",
            signal_time=pd.Timestamp(index[entry]),
            fill_time=pd.Timestamp(index[entry + 1]),
            anchor_time=pd.Timestamp(index[breakout]),
            stop=float(stop_px),
            atr=float(scale),
            reference=float(reference),
        )
        mark = HoldMark(
            setup=setup,
            level=float(level),
            breakout_time=pd.Timestamp(index[breakout]),
            chop_start=pd.Timestamp(index[start]),
            chop_end=pd.Timestamp(index[stop - 1]),
        )
        return mark, entry + BREAK_COOLDOWN
    return None, zone_end


def _bump(counts: dict | None, key: str) -> None:
    if counts is not None:
        counts[key] = int(counts.get(key, 0)) + 1


def _shelf(high, low, close, dates, start, end, scale):
    if end - start < MIN_TOUCHES:
        return None
    range_high = float(np.max(high[start:end]))
    range_low = float(np.min(low[start:end]))
    height = range_high - range_low
    if not np.isfinite(height) or height < MIN_HEIGHT_ATR * scale or height > MAX_HEIGHT_ATR * scale:
        return None
    band = TOUCH_ATR * scale
    high_sessions = {dates[j] for j in range(start, end) if high[j] >= range_high - band}
    low_sessions = {dates[j] for j in range(start, end) if low[j] <= range_low + band}
    if len(high_sessions) < MIN_TOUCHES or len(low_sessions) < MIN_TOUCHES:
        return None
    if float(np.max(close[start:end])) > range_high or float(np.min(close[start:end])) < range_low:
        return None
    return range_high, range_low, height


def _retested(direction, low, high, start, stop, level, scale) -> bool:
    if not np.isfinite(scale) or scale <= 0:
        return False
    band = TOUCH_ATR * scale
    if direction == "long":
        return float(np.min(low[start:stop])) <= level + band
    return float(np.max(high[start:stop])) >= level - band


def _violates(direction, close, low, high, start, end_inclusive, level, scale) -> bool:
    return _first_violation(direction, close, low, high, start, end_inclusive, level, scale) >= 0


def _first_violation(direction, close, low, high, start, end_inclusive, level, scale) -> int:
    if end_inclusive < start or not np.isfinite(scale) or scale <= 0:
        return -1
    band = TOUCH_ATR * scale
    for j in range(start, end_inclusive + 1):
        if direction == "long":
            if close[j] < level or low[j] < level - band:
                return j
        elif close[j] > level or high[j] > level + band:
            return j
    return -1


def _rejected(direction, high, low, close, upper, lower, std, start, stop) -> bool:
    for j in range(start, stop):
        if not np.isfinite(std[j]) or std[j] <= 0:
            continue
        if direction == "long" and np.isfinite(upper[j]) and high[j] >= upper[j] and close[j] < upper[j]:
            return True
        if direction == "short" and np.isfinite(lower[j]) and low[j] <= lower[j] and close[j] > lower[j]:
            return True
    return False


def _runs(flags: np.ndarray, start: int, end: int) -> list[tuple[int, int]]:
    found = []
    run = None
    for j in range(start, end):
        if flags[j] and run is None:
            run = j
        elif not flags[j] and run is not None:
            found.append((run, j))
            run = None
    if run is not None:
        found.append((run, end))
    return found


def _sessions(dates: np.ndarray):
    starts = [0]
    for i in range(1, len(dates)):
        if dates[i] != dates[i - 1]:
            starts.append(i)
    ends = starts[1:] + [len(dates)]
    session_of = np.empty(len(dates), dtype=int)
    for sid, (start, end) in enumerate(zip(starts, ends)):
        session_of[start:end] = sid
    return starts, ends, session_of
