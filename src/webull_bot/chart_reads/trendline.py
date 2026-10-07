"""Daily descending-trendline breakout (setup C).

The line at bar t uses only pivot highs confirmed by t. It connects two of
those highs. A third swing that tags the segment is a variant, not the
default. Nothing here places an order. The fill is the next session's open.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from webull_bot.chart_reads.detect import Setup, strong_candle
from webull_bot.chart_reads.params import DAILY_DEFAULTS
from webull_bot.indicators import atr, ema
from webull_bot.patterns import _pivot_points, confirmed_pivot_high, confirmed_pivot_low


@dataclass
class LineChoice:
    x1: int
    y1: float
    x2: int
    y2: float
    confirm: int
    touches: int
    first_break: int


def _params(params: dict | None) -> dict:
    chosen = dict(DAILY_DEFAULTS)
    if params:
        chosen.update(params)
    return chosen


def _level(pair: LineChoice, index: int) -> float:
    span = pair.x2 - pair.x1
    if span == 0:
        return pair.y2
    slope = (pair.y2 - pair.y1) / span
    return pair.y1 + slope * (index - pair.x1)


def _pairs(high: np.ndarray, close: np.ndarray, atrs: np.ndarray, params: dict) -> list[LineChoice]:
    left = int(params["pivot_left"])
    right = int(params["pivot_right"])
    marked = confirmed_pivot_high(pd.Series(high), left, right)
    points = _pivot_points(marked, right)
    touch = float(params["touch_atr"])
    buffer = float(params["break_buffer_atr"])
    min_span = int(params["min_span"])
    max_span = int(params["max_span"])
    n = len(high)
    pairs: list[LineChoice] = []
    for later_i in range(len(points)):
        x2, y2, confirm = points[later_i]
        for earlier_i in range(later_i):
            x1, y1, _c1 = points[earlier_i]
            span = x2 - x1
            if span < min_span or span > max_span or y2 >= y1:
                continue
            slope = (y2 - y1) / span
            broken = False
            touches = 0
            for k in range(x1, x2 + 1):
                level = y1 + slope * (k - x1)
                width = atrs[k]
                if not np.isfinite(width) or width <= 0:
                    continue
                if x1 < k < x2 and close[k] > level + buffer * width:
                    broken = True
                    break
                if high[k] >= level - touch * width and close[k] <= level + buffer * width:
                    touches += 1
            if broken:
                continue
            # An intervening confirmed pivot that closes through the line
            # upward means this pair is not the swings' trendline.
            violated = False
            for mid_i in range(earlier_i + 1, later_i):
                xm, ym, _cm = points[mid_i]
                level = y1 + slope * (xm - x1)
                width = atrs[xm]
                if np.isfinite(width) and width > 0 and ym > level + touch * width:
                    violated = True
                    break
            if violated:
                continue
            first_break = n
            for k in range(x2 + 1, n):
                level = y1 + slope * (k - x1)
                width = atrs[k]
                if not np.isfinite(width) or width <= 0:
                    continue
                if close[k] > level + buffer * width:
                    first_break = k
                    break
            pairs.append(
                LineChoice(
                    x1=int(x1),
                    y1=float(y1),
                    x2=int(x2),
                    y2=float(y2),
                    confirm=int(confirm),
                    touches=int(touches),
                    first_break=int(first_break),
                )
            )
    return pairs


def _choose(pairs: list[LineChoice], t: int, high: np.ndarray, widths: np.ndarray, params: dict) -> LineChoice | None:
    need = 3 if params.get("require_three_touches") else 2
    max_age = int(params.get("max_anchor_age", 80))
    best: LineChoice | None = None
    best_key: tuple | None = None
    price = high[t]
    width = widths[t]
    for pair in pairs:
        if pair.confirm > t or t > pair.first_break:
            continue
        if pair.touches < need:
            continue
        level = _level(pair, t)
        age = t - pair.x2
        near = np.isfinite(width) and width > 0 and abs(level - price) <= 3.0 * width
        if age > max_age and not near:
            continue
        # Prefer the overhead line. A line already under the high is a worse ceiling.
        overhead = level - price
        distance = overhead if overhead >= 0 else 1.0e6 + abs(overhead)
        key = (-pair.touches, distance, -(pair.x2 - pair.x1), -pair.x2)
        if best_key is None or key < best_key:
            best_key = key
            best = pair
    return best


def line_on(frame: pd.DataFrame, params: dict | None = None) -> tuple[pd.Series, list[LineChoice | None]]:
    """Causal line value at each bar, and the pair that produced it."""
    chosen = _params(params)
    high = frame["high"].to_numpy(dtype=float)
    close = frame["close"].to_numpy(dtype=float)
    widths = atr(frame, 14).to_numpy(dtype=float)
    pairs = _pairs(high, close, widths, chosen)
    values = np.full(len(frame), np.nan)
    selected: list[LineChoice | None] = []
    for t in range(len(frame)):
        pair = _choose(pairs, t, high, widths, chosen)
        selected.append(pair)
        if pair is not None:
            values[t] = _level(pair, t)
    return pd.Series(values, index=frame.index), selected


def _resistance(close: float, width: float, points: list[tuple[int, float, int]], t: int, direction: str) -> float:
    if direction == "long":
        above = [price for x, price, confirm in points if confirm <= t and price > close + 0.25 * width]
        return float(min(above)) if above else np.nan
    below = [price for x, price, confirm in points if confirm <= t and price < close - 0.25 * width]
    return float(max(below)) if below else np.nan


def find_trend_setups(frame: pd.DataFrame, params: dict | None = None, *, symbol: str = "") -> list[Setup]:
    """Long breakout-retest, and the rejection-short variant when asked.

    Long: a daily close above the line by the buffer, then within N sessions
    a pullback that tags the line or the breakout close, does not close back
    below the line, and prints a bullish confirming candle. Stop is the
    retest low. The reference is the next confirmed pivot high.

    Short variant: in a 9-under-20 downtrend, a high that tags the line and
    a bearish close back under it. Stop is that high. Cooldown separates
    clustered tags. These are not the default book.
    """
    chosen = _params(params)
    if frame is None or len(frame) < 40:
        return []
    bars = frame.sort_index()
    high = bars["high"].to_numpy(dtype=float)
    low = bars["low"].to_numpy(dtype=float)
    open_ = bars["open"].to_numpy(dtype=float)
    close = bars["close"].to_numpy(dtype=float)
    widths = atr(bars, 14).to_numpy(dtype=float)
    fast = ema(bars["close"].astype(float), 9).to_numpy(dtype=float)
    slow = ema(bars["close"].astype(float), 20).to_numpy(dtype=float)
    line, _selected = line_on(bars, chosen)
    levels = line.to_numpy(dtype=float)
    left = int(chosen["pivot_left"])
    right = int(chosen["pivot_right"])
    pivot_highs = _pivot_points(confirmed_pivot_high(bars["high"], left, right), right)
    pivot_lows = _pivot_points(confirmed_pivot_low(bars["low"], left, right), right)
    index = bars.index
    n = len(bars)
    body = float(chosen["strong_body"])
    close_frac = float(chosen["strong_close_frac"])
    touch = float(chosen["touch_atr"])
    buffer = float(chosen["break_buffer_atr"])
    window = int(chosen["retest_days"])
    cooldown = int(chosen["short_cooldown"])
    want_long = bool(chosen.get("include_long", True))
    want_short = bool(chosen.get("include_short", False))
    setups: list[Setup] = []
    pending: dict | None = None
    last_short = -10_000
    armed_pairs: set[tuple[int, int]] = set()

    for t in range(n):
        width = widths[t]
        level = levels[t]
        if pending is not None:
            frozen = pending["y1"] + pending["slope"] * (t - pending["x1"])
            if t > pending["deadline"] or not np.isfinite(width):
                pending = None
            elif close[t] < frozen:
                pending = None
            else:
                tol = touch * width
                tags = low[t] <= frozen + tol or low[t] <= pending["break_close"] + tol
                if tags:
                    pending["tagged"] = True
                    pending["tag_low"] = min(pending["tag_low"], low[t])
                held = close[t] >= frozen and close[t] >= low[t - 1]
                bullish = strong_candle(open_[t], high[t], low[t], close[t], "long", body, close_frac)
                if pending["tagged"] and bullish and held and t + 1 < n and want_long:
                    setups.append(
                        Setup(
                            symbol=symbol,
                            direction="long",
                            kind="C",
                            signal_time=pd.Timestamp(index[t]),
                            fill_time=pd.Timestamp(index[t + 1]),
                            anchor_time=pd.Timestamp(index[pending["anchor"]]),
                            stop=float(pending["tag_low"]),
                            atr=float(width),
                            reference=_resistance(close[t], width, pivot_highs, t, "long"),
                        )
                    )
                    pending = None
                    continue
        pair = _selected[t]
        fresh = t == 0 or not np.isfinite(levels[t - 1]) or close[t - 1] <= levels[t - 1] + buffer * widths[t - 1]
        if (
            want_long
            and pending is None
            and pair is not None
            and t + 1 < n
            and np.isfinite(width)
            and width > 0
            and close[t] > level + buffer * width
            and fresh
        ):
            span = pair.x2 - pair.x1
            pending = {
                "y1": pair.y1,
                "slope": (pair.y2 - pair.y1) / span,
                "x1": pair.x1,
                "deadline": t + window,
                "break_close": float(close[t]),
                "tagged": False,
                "tag_low": float("inf"),
                "anchor": pair.x2,
            }
        if (
            want_short
            and pending is None
            and pair is not None
            and (pair.x1, pair.x2) not in armed_pairs
            and t == pair.confirm
            and np.isfinite(fast[t])
            and np.isfinite(slow[t])
            and fast[t] < slow[t]
            and t + 1 < n
        ):
            # The later pivot is a failed test of the line. It is knowable on
            # its confirmation bar, which is when this short can be entered.
            armed_pairs.add((pair.x1, pair.x2))
            last_short = t
            setups.append(
                Setup(
                    symbol=symbol,
                    direction="short",
                    kind="R",
                    signal_time=pd.Timestamp(index[t]),
                    fill_time=pd.Timestamp(index[t + 1]),
                    anchor_time=pd.Timestamp(index[pair.x2]),
                    stop=float(pair.y2),
                    atr=float(width) if np.isfinite(width) and width > 0 else float(pair.y2 * 0.01),
                    reference=_resistance(close[t], width if np.isfinite(width) else 1.0, pivot_lows, t, "short"),
                )
            )
        elif (
            want_short
            and pending is None
            and np.isfinite(level)
            and np.isfinite(width)
            and width > 0
            and np.isfinite(fast[t])
            and np.isfinite(slow[t])
            and fast[t] < slow[t]
            and high[t] >= level - touch * width
            and close[t] < level
            and close[t] < open_[t]
            and t - last_short >= cooldown
            and t + 1 < n
        ):
            last_short = t
            setups.append(
                Setup(
                    symbol=symbol,
                    direction="short",
                    kind="R",
                    signal_time=pd.Timestamp(index[t]),
                    fill_time=pd.Timestamp(index[t + 1]),
                    anchor_time=pd.Timestamp(index[t]),
                    stop=float(high[t]),
                    atr=float(width),
                    reference=_resistance(close[t], width, pivot_lows, t, "short"),
                )
            )
    return setups


def describe_line(frame: pd.DataFrame, params: dict | None = None, *, as_of: str | None = None) -> dict:
    """The line selected on ``as_of`` (default: the last bar), projected across the frame.

    Touches are highs within the tolerance that close back at or under the
    projected line. That is the chart check, including swings that became
    anchors only after they confirmed.
    """
    chosen = _params(params)
    bars = frame.sort_index()
    if as_of is not None:
        stamp = pd.Timestamp(as_of)
        bars = bars.loc[:stamp]
    if bars.empty:
        return {"pair": None, "line": pd.Series(dtype=float), "touches": []}
    _values, selected = line_on(bars, chosen)
    pair = selected[-1]
    projected = np.full(len(bars), np.nan)
    if pair is not None:
        for t in range(len(bars)):
            projected[t] = _level(pair, t)
    line = pd.Series(projected, index=bars.index)
    high = bars["high"].to_numpy(dtype=float)
    close = bars["close"].to_numpy(dtype=float)
    widths = atr(bars, 14).to_numpy(dtype=float)
    touch = float(chosen["touch_atr"])
    buffer = float(chosen["break_buffer_atr"])
    touches = []
    for t in range(len(bars)):
        level = projected[t]
        width = widths[t]
        if not np.isfinite(level) or not np.isfinite(width) or width <= 0:
            continue
        # A failed test tags the line. A wick that clears it by more than the
        # tolerance is a different swing, not a test of this line.
        if abs(high[t] - level) <= touch * width and close[t] <= level + buffer * width:
            touches.append(
                {
                    "date": pd.Timestamp(bars.index[t]),
                    "high": float(high[t]),
                    "close": float(close[t]),
                    "line": float(level),
                }
            )
    return {
        "pair": None
        if pair is None
        else {
            "x1": pair.x1,
            "y1": pair.y1,
            "x2": pair.x2,
            "y2": pair.y2,
            "date1": pd.Timestamp(bars.index[pair.x1]),
            "date2": pd.Timestamp(bars.index[pair.x2]),
            "touches": pair.touches,
            "confirm": pd.Timestamp(bars.index[min(pair.confirm, len(bars) - 1)]),
        },
        "line": line,
        "touches": touches,
        "causal": _values,
    }
