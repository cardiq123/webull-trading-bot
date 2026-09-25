"""Causal price-pattern detectors for the Dow swing studies.

A value on bar ``t`` uses only bars at or before ``t``. Pivot confirmation
waits ``right`` bars, so the pivot bar itself is not a signal. These
functions do not place orders.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def confirmed_pivots(series: pd.Series, left: int, right: int, *, kind: str) -> pd.Series:
    """Price of a unique swing extreme, written on the confirmation bar."""
    values = series.to_numpy(dtype=float)
    out = np.full(len(values), np.nan)
    want_min = kind == "low"
    for t in range(left + right, len(values)):
        i = t - right
        window = values[i - left : t + 1]
        pivot = values[i]
        if not np.isfinite(pivot):
            continue
        extreme = np.nanmin(window) if want_min else np.nanmax(window)
        if pivot == extreme and int(np.sum(window == pivot)) == 1:
            out[t] = pivot
    return pd.Series(out, index=series.index)


def confirmed_pivot_low(low: pd.Series, left: int, right: int) -> pd.Series:
    return confirmed_pivots(low, left, right, kind="low")


def confirmed_pivot_high(high: pd.Series, left: int, right: int) -> pd.Series:
    return confirmed_pivots(high, left, right, kind="high")


def _pivot_points(marked: pd.Series, right: int) -> list[tuple[int, float, int]]:
    """(pivot index, price, confirmation index) for each finite mark."""
    values = marked.to_numpy(dtype=float)
    points = []
    for confirm_i, price in enumerate(values):
        if np.isfinite(price):
            points.append((confirm_i - right, float(price), confirm_i))
    return points


def fit_line(xs: list[float], ys: list[float]) -> tuple[float, float] | None:
    """Ordinary least squares. Returns ``(slope, intercept)`` for ``y = intercept + slope * x``."""
    x = np.asarray(xs, dtype=float)
    y = np.asarray(ys, dtype=float)
    if len(x) < 2:
        return None
    x_mean = float(x.mean())
    y_mean = float(y.mean())
    var = float(((x - x_mean) ** 2).sum())
    if var <= 0:
        return None
    slope = float(((x - x_mean) * (y - y_mean)).sum() / var)
    return slope, y_mean - slope * x_mean


def prior_n_day_low(low: pd.Series, window: int) -> pd.Series:
    """Lowest low of the prior ``window`` bars. Today's low is not included."""
    return low.rolling(window, min_periods=window).min().shift(1)


def prior_ytd_low(low: pd.Series) -> pd.Series:
    """Lowest low from January 1 through yesterday, resetting each calendar year."""
    values = low.to_numpy(dtype=float)
    years = pd.DatetimeIndex(low.index).year.to_numpy()
    out = np.full(len(values), np.nan)
    running = np.nan
    year = None
    for i, this_year in enumerate(years):
        if this_year != year:
            year = this_year
            running = np.nan
        out[i] = running
        price = values[i]
        if np.isfinite(price):
            running = price if not np.isfinite(running) else min(running, price)
    return pd.Series(out, index=low.index)


def prior_month_reference_low(low: pd.Series) -> pd.Series:
    """Min of last calendar month's low and this month's low through yesterday.

    Last month's low is known once that month is over. This month's future
    bars are not used.
    """
    values = low.to_numpy(dtype=float)
    periods = pd.DatetimeIndex(low.index).to_period("M")
    month_min: dict = {}
    for i, period in enumerate(periods):
        price = values[i]
        if not np.isfinite(price):
            continue
        month_min[period] = price if period not in month_min else min(month_min[period], price)
    out = np.full(len(values), np.nan)
    running = np.nan
    current = None
    previous_low = np.nan
    for i, period in enumerate(periods):
        if period != current:
            current = period
            running = np.nan
            previous_low = month_min.get(period - 1, np.nan)
        choices = [price for price in (previous_low, running) if np.isfinite(price)]
        out[i] = min(choices) if choices else np.nan
        price = values[i]
        if np.isfinite(price):
            running = price if not np.isfinite(running) else min(running, price)
    return pd.Series(out, index=low.index)


def tags_level(low: pd.Series, level: pd.Series, atr: pd.Series, tolerance_atr: float) -> pd.Series:
    """True when today's low makes or tags ``level`` within ``tolerance_atr`` ATR."""
    return level.notna() & atr.notna() & (atr > 0) & (low <= level + tolerance_atr * atr)


def horizontal_support(
    low: pd.Series,
    atr: pd.Series,
    left: int,
    right: int,
    *,
    zone_atr: float = 1.25,
    lookback: int = 180,
    min_touches: int = 2,
) -> pd.Series:
    """True when at least ``min_touches`` prior confirmed pivot lows sit near today's low."""
    marked = confirmed_pivot_low(low, left, right)
    points = _pivot_points(marked, right)
    lows = low.to_numpy(dtype=float)
    atrs = atr.to_numpy(dtype=float)
    out = np.zeros(len(lows), dtype=bool)
    pointer = 0
    active: list[tuple[int, float]] = []
    for t in range(len(lows)):
        while pointer < len(points) and points[pointer][2] < t:
            active.append((points[pointer][2], points[pointer][1]))
            pointer += 1
        cutoff = t - lookback
        while active and active[0][0] < cutoff:
            active.pop(0)
        width = atrs[t]
        price = lows[t]
        if not np.isfinite(width) or width <= 0 or not np.isfinite(price):
            continue
        tol = zone_atr * width
        touches = sum(1 for _confirm, pivot in active if abs(pivot - price) <= tol)
        out[t] = touches >= min_touches
    return pd.Series(out, index=low.index)


def rising_trendline(low: pd.Series, left: int, right: int) -> pd.Series:
    """Line through the latest confirmed pivot low and the nearest earlier lower one.

    The value is the line extended to today. It is NaN unless the two pivots
    are rising. Both pivots are confirmed strictly before today.
    """
    points = _pivot_points(confirmed_pivot_low(low, left, right), right)
    out = np.full(len(low), np.nan)
    pointer = 0
    known: list[tuple[int, float, int]] = []
    for t in range(len(low)):
        while pointer < len(points) and points[pointer][2] < t:
            known.append(points[pointer])
            pointer += 1
        if len(known) < 2:
            continue
        x2, y2, _confirm = known[-1]
        chosen = None
        for point in reversed(known[:-1]):
            if point[0] < x2 and point[1] < y2:
                chosen = point
                break
        if chosen is None or x2 == chosen[0]:
            continue
        slope = (y2 - chosen[1]) / (x2 - chosen[0])
        if slope <= 0:
            continue
        out[t] = y2 + slope * (t - x2)
    return pd.Series(out, index=low.index)


def trendline_touch(low: pd.Series, line: pd.Series, atr: pd.Series, tolerance_atr: float) -> pd.Series:
    distance = (low - line).abs()
    return line.notna() & atr.notna() & (atr > 0) & (distance <= tolerance_atr * atr)


def bullish_reversal_candle(frame: pd.DataFrame) -> pd.Series:
    """Engulfing, hammer/pin, or a close in the top quarter through the prior high."""
    open_ = frame["open"].to_numpy(dtype=float)
    high = frame["high"].to_numpy(dtype=float)
    low = frame["low"].to_numpy(dtype=float)
    close = frame["close"].to_numpy(dtype=float)
    out = np.zeros(len(close), dtype=bool)
    for t in range(1, len(close)):
        span = high[t] - low[t]
        body = abs(close[t] - open_[t])
        if not np.isfinite(span) or span <= 0:
            continue
        upper = high[t] - max(open_[t], close[t])
        lower = min(open_[t], close[t]) - low[t]
        prior_bear = close[t - 1] < open_[t - 1]
        engulfs = (
            close[t] > open_[t]
            and prior_bear
            and open_[t] <= close[t - 1]
            and close[t] >= open_[t - 1]
        )
        hammer = body > 0 and lower >= 2.0 * body and lower >= 2.0 * max(upper, 0.0)
        thrust = close[t] >= low[t] + 0.75 * span and close[t] > high[t - 1]
        out[t] = bool(engulfs or hammer or thrust)
    return pd.Series(out, index=frame.index)


def strong_breakout_candle(frame: pd.DataFrame, *, side: str) -> pd.Series:
    """Body at least 60% of the range, close in the extreme quarter, in ``side``'s direction."""
    open_ = frame["open"].to_numpy(dtype=float)
    high = frame["high"].to_numpy(dtype=float)
    low = frame["low"].to_numpy(dtype=float)
    close = frame["close"].to_numpy(dtype=float)
    out = np.zeros(len(close), dtype=bool)
    for t in range(len(close)):
        span = high[t] - low[t]
        if not np.isfinite(span) or span <= 0:
            continue
        body = abs(close[t] - open_[t])
        if body < 0.60 * span:
            continue
        if side == "bull":
            out[t] = close[t] > open_[t] and close[t] >= low[t] + 0.75 * span
        else:
            out[t] = close[t] < open_[t] and close[t] <= low[t] + 0.25 * span
    return pd.Series(out, index=frame.index)


def first_confirmation(setup: pd.Series, candle: pd.Series, within: int) -> pd.Series:
    """First bullish candle 1..``within`` bars after a setup. The setup bar does not count."""
    setup_flags = setup.fillna(False).to_numpy(dtype=bool)
    candles = candle.fillna(False).to_numpy(dtype=bool)
    out = np.zeros(len(setup_flags), dtype=bool)
    for t in range(len(setup_flags)):
        if not setup_flags[t]:
            continue
        for step in range(1, within + 1):
            j = t + step
            if j >= len(setup_flags):
                break
            if candles[j]:
                out[j] = True
                break
    return pd.Series(out, index=setup.index)


def wedge_lines(
    high: pd.Series,
    low: pd.Series,
    left: int,
    right: int,
    *,
    lookback: int,
    min_span: int = 15,
    contraction: float = 0.80,
) -> pd.DataFrame:
    """Upper and lower lines of a converging wedge or triangle, evaluated at each bar.

    Pivots are confirmed strictly before the bar and lie inside ``lookback``.
    ``kind`` is ``falling``, ``rising``, ``symmetrical``, or an empty string.
    ``start`` is the earlier pivot index used in the fit.
    """
    high_points = _pivot_points(confirmed_pivot_high(high, left, right), right)
    low_points = _pivot_points(confirmed_pivot_low(low, left, right), right)
    n = len(high)
    upper = np.full(n, np.nan)
    lower = np.full(n, np.nan)
    upper_slope = np.full(n, np.nan)
    lower_slope = np.full(n, np.nan)
    kinds = np.array([""] * n, dtype=object)
    starts = np.full(n, np.nan)
    hi_ptr = 0
    lo_ptr = 0
    known_high: list[tuple[int, float, int]] = []
    known_low: list[tuple[int, float, int]] = []
    for t in range(n):
        while hi_ptr < len(high_points) and high_points[hi_ptr][2] < t:
            known_high.append(high_points[hi_ptr])
            hi_ptr += 1
        while lo_ptr < len(low_points) and low_points[lo_ptr][2] < t:
            known_low.append(low_points[lo_ptr])
            lo_ptr += 1
        cutoff = t - lookback
        highs = [point for point in known_high if point[0] >= cutoff]
        lows = [point for point in known_low if point[0] >= cutoff]
        if len(highs) < 2 or len(lows) < 2:
            continue
        span_start = min(highs[0][0], lows[0][0])
        span_end = max(highs[-1][0], lows[-1][0])
        if span_end - span_start < min_span:
            continue
        up = fit_line([point[0] for point in highs], [point[1] for point in highs])
        down = fit_line([point[0] for point in lows], [point[1] for point in lows])
        if up is None or down is None:
            continue
        up_now = up[1] + up[0] * t
        down_now = down[1] + down[0] * t
        up_then = up[1] + up[0] * span_start
        down_then = down[1] + down[0] * span_start
        gap_now = up_now - down_now
        gap_then = up_then - down_then
        if gap_now <= 0 or gap_then <= 0 or gap_now >= gap_then * contraction:
            continue
        up_slope, down_slope = up[0], down[0]
        if up_slope < 0 and down_slope < 0 and up_slope < down_slope:
            kind = "falling"
        elif up_slope > 0 and down_slope > 0 and down_slope > up_slope:
            kind = "rising"
        elif up_slope < 0 < down_slope:
            kind = "symmetrical"
        else:
            continue
        upper[t] = up_now
        lower[t] = down_now
        upper_slope[t] = up_slope
        lower_slope[t] = down_slope
        kinds[t] = kind
        starts[t] = span_start
    return pd.DataFrame(
        {
            "upper": upper,
            "lower": lower,
            "upper_slope": upper_slope,
            "lower_slope": lower_slope,
            "kind": kinds,
            "start": starts,
        },
        index=high.index,
    )


def prior_range(high: pd.Series, low: pd.Series, window: int) -> pd.DataFrame:
    """Prior-window high and low. Today is excluded."""
    return pd.DataFrame(
        {
            "upper": high.rolling(window, min_periods=window).max().shift(1),
            "lower": low.rolling(window, min_periods=window).min().shift(1),
        },
        index=high.index,
    )
