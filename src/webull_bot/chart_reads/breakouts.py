"""Three breakout patterns from confirmed pivots (setup D).

Bar t uses only pivots whose confirmation bar has closed by t. A descending
triangle (lower highs, flat support) breaks down. An ascending triangle
(higher lows, flat resistance) breaks up. A horizontal range breaks either
way. The default trigger is a close beyond the flat level by a buffer on a
confirming candle. A retest that holds is a grid variant. The fill is the
next bar's open. Nothing here places an order.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from webull_bot.chart_reads.detect import Setup, strong_candle
from webull_bot.chart_reads.params import BREAKOUT_DEFAULTS
from webull_bot.indicators import atr
from webull_bot.patterns import _pivot_points, confirmed_pivot_high, confirmed_pivot_low


@dataclass
class Pattern:
    kind: str
    support: float
    resistance: float
    x1: int
    y1: float
    x2: int
    y2: float
    start: int
    end: int
    confirm: int
    flat_touches: int
    slope_touches: int

    @property
    def key(self) -> tuple:
        return (
            self.kind,
            round(self.support, 4),
            round(self.resistance, 4),
            self.start,
            self.end,
        )

    @property
    def touches(self) -> int:
        return self.flat_touches + self.slope_touches


def _params(params: dict | None) -> dict:
    chosen = dict(BREAKOUT_DEFAULTS)
    if params:
        chosen.update(params)
    return chosen


def _line(x1: int, y1: float, x2: int, y2: float, x: int) -> float:
    span = x2 - x1
    if span == 0:
        return y1
    return y1 + (y2 - y1) * ((x - x1) / span)


def _flat_groups(pivots: list[tuple[int, float, int]], width: float, min_touches: int, min_span: int) -> list[list]:
    groups = []
    count = len(pivots)
    for i in range(count):
        for j in range(i + min_touches - 1, count):
            group = pivots[i : j + 1]
            prices = [point[1] for point in group]
            if max(prices) - min(prices) > width:
                continue
            if group[-1][0] - group[0][0] < min_span:
                continue
            groups.append(group)
    return groups


def _monotonic(pivots: list[tuple[int, float, int]], step: int, min_count: int, min_change: float) -> list | None:
    best = None
    for i in range(len(pivots)):
        seq = [pivots[i]]
        for point in pivots[i + 1 :]:
            if step < 0 and point[1] < seq[-1][1]:
                seq.append(point)
            elif step > 0 and point[1] > seq[-1][1]:
                seq.append(point)
            else:
                break
        if len(seq) < min_count:
            continue
        if abs(seq[-1][1] - seq[0][1]) < min_change:
            continue
        rank = (len(seq), seq[-1][0], abs(seq[-1][1] - seq[0][1]))
        if best is None or rank > best[0]:
            best = (rank, seq)
    return None if best is None else best[1]


def _top(groups: list[list], k: int = 4) -> list[list]:
    ranked = sorted(groups, key=lambda group: (len(group), group[-1][0] - group[0][0], group[-1][0]), reverse=True)
    return ranked[:k]


def _clean_closes(close: np.ndarray, atr_values: np.ndarray, start: int, end: int, lo: float, hi: float, buffer: float) -> bool:
    """True when no close inside the pattern has already left the box."""
    last = min(end, len(close) - 1)
    if start > last:
        return False
    segment = close[start : last + 1]
    scale = atr_values[start : last + 1]
    usable = np.isfinite(scale) & (scale > 0)
    under = usable & (segment < lo - buffer * scale)
    over = usable & (segment > hi + buffer * scale)
    return not bool(under.any() or over.any())


def _closes_through_line(
    close: np.ndarray,
    atr_values: np.ndarray,
    x1: int,
    y1: float,
    x2: int,
    y2: float,
    end: int,
    buffer: float,
    *,
    above: bool,
) -> bool:
    """True when a close has already broken the sloped side."""
    if x2 == x1 or x1 > end:
        return False
    xs = np.arange(x1, end + 1)
    line = y1 + (y2 - y1) * ((xs - x1) / (x2 - x1))
    scale = atr_values[xs]
    usable = np.isfinite(scale) & (scale > 0)
    if above:
        return bool((usable & (close[xs] > line + buffer * scale)).any())
    return bool((usable & (close[xs] < line - buffer * scale)).any())


def _geometry(frame: pd.DataFrame, params: dict | None = None) -> list[Pattern | None]:
    chosen = _params(params)
    bars = frame.sort_index()
    high = bars["high"].to_numpy(dtype=float)
    low = bars["low"].to_numpy(dtype=float)
    close = bars["close"].to_numpy(dtype=float)
    n = len(bars)
    out: list[Pattern | None] = [None] * n
    if n < chosen["min_span"] + chosen["pivot_left"] + chosen["pivot_right"] + 2:
        return out
    left = int(chosen["pivot_left"])
    right = int(chosen["pivot_right"])
    highs = _pivot_points(confirmed_pivot_high(bars["high"], left, right), right)
    lows = _pivot_points(confirmed_pivot_low(bars["low"], left, right), right)
    width = atr(bars).to_numpy(dtype=float)
    min_flat = int(chosen["min_flat_touches"])
    min_slope = int(chosen["min_slope_pivots"])
    min_span = int(chosen["min_span"])
    max_span = int(chosen["max_span"])
    touch = float(chosen["touch_atr"])
    slope_atr = float(chosen["min_slope_atr"])
    min_height = float(chosen["min_height_atr"])
    max_height = float(chosen["max_height_atr"])
    buffer = float(chosen["break_buffer_atr"])
    hi_ptr = 0
    lo_ptr = 0
    known_high: list[tuple[int, float, int]] = []
    known_low: list[tuple[int, float, int]] = []
    for t in range(n):
        while hi_ptr < len(highs) and highs[hi_ptr][2] <= t:
            known_high.append(highs[hi_ptr])
            hi_ptr += 1
        while lo_ptr < len(lows) and lows[lo_ptr][2] <= t:
            known_low.append(lows[lo_ptr])
            lo_ptr += 1
        # Prior bar's ATR. The break bar's own range must not redraw the level.
        scale = width[t - 1] if t > 0 else width[t]
        if not np.isfinite(scale) or scale <= 0:
            continue
        window_lo = t - max_span
        use_high = [point for point in known_high if point[0] >= window_lo]
        use_low = [point for point in known_low if point[0] >= window_lo]
        band = touch * scale
        support_groups = _top(_flat_groups(use_low, band, min_flat, min_span))
        resist_groups = _top(_flat_groups(use_high, band, min_flat, min_span))
        patterns: list[Pattern] = []
        change = slope_atr * scale
        for group in support_groups:
            level = float(np.median([point[1] for point in group]))
            eligible = [
                point
                for point in use_high
                if point[1] > level + 0.25 * scale and group[0][0] - max_span <= point[0] <= group[-1][0] + int(chosen["max_wait"])
            ]
            seq = _monotonic(eligible, -1, min_slope, change)
            if seq is None:
                continue
            if seq[-1][0] < group[0][0] or seq[0][0] > group[-1][0]:
                continue
            start = min(seq[0][0], group[0][0])
            end = max(seq[-1][0], group[-1][0])
            if end - start < min_span or end - start > max_span:
                continue
            height = seq[0][1] - level
            if height < min_height * scale or height > max_height * scale:
                continue
            if not _clean_closes(close, width, start, end, level, seq[0][1], buffer):
                continue
            if _closes_through_line(close, width, seq[0][0], seq[0][1], seq[-1][0], seq[-1][1], end, buffer, above=True):
                continue
            confirm = max(point[2] for point in (*group, *seq))
            patterns.append(
                Pattern(
                    "Dd",
                    level,
                    float(seq[0][1]),
                    seq[0][0],
                    float(seq[0][1]),
                    seq[-1][0],
                    float(seq[-1][1]),
                    start,
                    end,
                    confirm,
                    len(group),
                    len(seq),
                )
            )
        for group in resist_groups:
            level = float(np.median([point[1] for point in group]))
            eligible = [
                point
                for point in use_low
                if point[1] < level - 0.25 * scale and group[0][0] - max_span <= point[0] <= group[-1][0] + int(chosen["max_wait"])
            ]
            seq = _monotonic(eligible, 1, min_slope, change)
            if seq is None:
                continue
            if seq[-1][0] < group[0][0] or seq[0][0] > group[-1][0]:
                continue
            start = min(seq[0][0], group[0][0])
            end = max(seq[-1][0], group[-1][0])
            if end - start < min_span or end - start > max_span:
                continue
            height = level - seq[0][1]
            if height < min_height * scale or height > max_height * scale:
                continue
            if not _clean_closes(close, width, start, end, seq[0][1], level, buffer):
                continue
            if _closes_through_line(close, width, seq[0][0], seq[0][1], seq[-1][0], seq[-1][1], end, buffer, above=False):
                continue
            confirm = max(point[2] for point in (*group, *seq))
            patterns.append(
                Pattern(
                    "Da",
                    float(seq[0][1]),
                    level,
                    seq[0][0],
                    float(seq[0][1]),
                    seq[-1][0],
                    float(seq[-1][1]),
                    start,
                    end,
                    confirm,
                    len(group),
                    len(seq),
                )
            )
        for support in support_groups:
            for resist in resist_groups:
                if resist[-1][0] < support[0][0] or support[-1][0] < resist[0][0]:
                    continue
                floor = float(np.median([point[1] for point in support]))
                cap = float(np.median([point[1] for point in resist]))
                height = cap - floor
                if height < min_height * scale or height > max_height * scale:
                    continue
                start = min(support[0][0], resist[0][0])
                end = max(support[-1][0], resist[-1][0])
                if end - start < min_span or end - start > max_span:
                    continue
                if not _clean_closes(close, width, start, end, floor, cap, buffer):
                    continue
                confirm = max(point[2] for point in (*support, *resist))
                patterns.append(
                    Pattern(
                        "Dr",
                        floor,
                        cap,
                        -1,
                        np.nan,
                        -1,
                        np.nan,
                        start,
                        end,
                        confirm,
                        len(support),
                        len(resist),
                    )
                )
        fresh = [
            item
            for item in patterns
            if t >= item.confirm and t - item.confirm <= int(chosen["max_wait"]) and _apex_open(item, t)
        ]
        if not fresh:
            continue
        out[t] = min(
            fresh,
            key=lambda item: (
                abs(close[t] - _near_level(item, close[t])),
                -item.touches,
                0 if item.kind != "Dr" else 1,
            ),
        )
    return out


def _near_level(pattern: Pattern, price: float) -> float:
    if pattern.kind == "Dd":
        return pattern.support
    if pattern.kind == "Da":
        return pattern.resistance
    return pattern.support if abs(price - pattern.support) <= abs(price - pattern.resistance) else pattern.resistance


def _measured(pattern: Pattern, direction: str) -> float:
    height = pattern.resistance - pattern.support
    if direction == "long":
        return pattern.resistance + height
    return pattern.support - height


def _apex_open(pattern: Pattern, t: int) -> bool:
    if pattern.kind == "Dr" or pattern.x1 < 0 or pattern.x2 < 0:
        return True
    line = _line(pattern.x1, pattern.y1, pattern.x2, pattern.y2, t)
    if pattern.kind == "Dd":
        return line > pattern.support
    return line < pattern.resistance


def _prior_scale(width: np.ndarray, t: int) -> float:
    scale = width[t - 1] if t > 0 else width[t]
    if not np.isfinite(scale) or scale <= 0:
        return float("nan")
    return float(scale)


def _broke_slope(pattern: Pattern, t: int, price: float, scale: float, buffer: float) -> bool:
    """A descending triangle that closes through the falling highs is not a short.

    The mirror is an ascending triangle that closes through the rising lows.
    """
    if pattern.kind == "Dr" or pattern.x2 < 0 or pattern.x2 == pattern.x1:
        return False
    line = _line(pattern.x1, pattern.y1, pattern.x2, pattern.y2, t)
    if pattern.kind == "Dd":
        return price > line + buffer * scale
    return price < line - buffer * scale


def find_breakout_setups(frame: pd.DataFrame, params: dict | None = None, symbol: str = "") -> list[Setup]:
    """Causal setup D signals. One signal per pattern, filled on the next open."""
    chosen = _params(params)
    bars = frame.sort_index()
    if bars.empty:
        return []
    geometry = _geometry(bars, chosen)
    open_ = bars["open"].to_numpy(dtype=float)
    high = bars["high"].to_numpy(dtype=float)
    low = bars["low"].to_numpy(dtype=float)
    close = bars["close"].to_numpy(dtype=float)
    width = atr(bars).to_numpy(dtype=float)
    index = bars.index
    buffer = float(chosen["break_buffer_atr"])
    touch = float(chosen["touch_atr"])
    confirm_bars = int(chosen["confirm_bars"])
    retest_bars = int(chosen["retest_bars"])
    max_wait = int(chosen["max_wait"])
    body = float(chosen["strong_body"])
    close_frac = float(chosen["strong_close_frac"])
    want_retest = bool(chosen["require_retest"])
    found: list[Setup] = []
    done: set[tuple] = set()
    held: Pattern | None = None
    breach: int | None = None
    direction = ""
    tagged = False
    extreme = np.nan

    def _clear() -> None:
        nonlocal held, breach, direction, tagged, extreme
        held = None
        breach = None
        direction = ""
        tagged = False
        extreme = np.nan

    for t in range(len(bars) - 1):
        scale = _prior_scale(width, t)
        if not np.isfinite(scale):
            continue
        if held is not None and held.key not in done:
            if t - held.confirm > max_wait or not _apex_open(held, t) or _broke_slope(held, t, close[t], scale, buffer):
                done.add(held.key)
                _clear()
            elif breach is None:
                side, _level = _break_side(held, close[t], scale, buffer)
                if side is not None:
                    breach = t
                    direction = side
                    if not want_retest and _confirmed(open_[t], high[t], low[t], close[t], side, body, close_frac):
                        _emit(found, done, held, t, index, symbol, side, high[t] if side == "short" else low[t], scale)
                        _clear()
                        continue
            else:
                level = held.support if direction == "short" else held.resistance
                if _back_inside(direction, close[t], level):
                    done.add(held.key)
                    _clear()
                else:
                    age = t - breach
                    limit = retest_bars if want_retest else confirm_bars
                    if age > limit:
                        done.add(held.key)
                        _clear()
                    elif want_retest:
                        if _tags(direction, high[t], low[t], level, touch * scale):
                            bar_extreme = high[t] if direction == "short" else low[t]
                            if not tagged:
                                tagged = True
                                extreme = bar_extreme
                            else:
                                extreme = max(extreme, bar_extreme) if direction == "short" else min(extreme, bar_extreme)
                        if (
                            tagged
                            and _confirmed(open_[t], high[t], low[t], close[t], direction, body, close_frac)
                            and _still_beyond(direction, close[t], level)
                        ):
                            _emit(found, done, held, t, index, symbol, direction, float(extreme), scale)
                            _clear()
                            continue
                    elif _still_beyond(direction, close[t], level, buffer * scale) and _confirmed(
                        open_[t], high[t], low[t], close[t], direction, body, close_frac
                    ):
                        _emit(found, done, held, t, index, symbol, direction, high[t] if direction == "short" else low[t], scale)
                        _clear()
                        continue
        if held is not None:
            continue
        pattern = geometry[t]
        if pattern is None or pattern.key in done:
            continue
        if _broke_slope(pattern, t, close[t], scale, buffer):
            done.add(pattern.key)
            continue
        side, _level = _break_side(pattern, close[t], scale, buffer)
        held = pattern
        if side is None:
            continue
        breach = t
        direction = side
        if want_retest:
            continue
        if _confirmed(open_[t], high[t], low[t], close[t], side, body, close_frac):
            _emit(found, done, held, t, index, symbol, side, high[t] if side == "short" else low[t], scale)
            _clear()
    return found


def _break_side(pattern: Pattern, price: float, scale: float, buffer: float) -> tuple[str | None, float]:
    band = buffer * scale
    if pattern.kind == "Dd" and price < pattern.support - band:
        return "short", pattern.support
    if pattern.kind == "Da" and price > pattern.resistance + band:
        return "long", pattern.resistance
    if pattern.kind == "Dr":
        if price > pattern.resistance + band:
            return "long", pattern.resistance
        if price < pattern.support - band:
            return "short", pattern.support
    return None, np.nan


def _back_inside(direction: str, price: float, level: float) -> bool:
    if direction == "short":
        return price > level
    return price < level


def _still_beyond(direction: str, price: float, level: float, band: float = 0.0) -> bool:
    if direction == "short":
        return price < level - band
    return price > level + band


def _tags(direction: str, high: float, low: float, level: float, band: float) -> bool:
    if direction == "short":
        return high >= level - band
    return low <= level + band


def _confirmed(open_: float, high: float, low: float, close: float, direction: str, body: float, close_frac: float) -> bool:
    return strong_candle(open_, high, low, close, direction, body, close_frac)


def _emit(found, done, pattern: Pattern, t: int, index, symbol: str, direction: str, stop: float, scale: float) -> None:
    if not np.isfinite(stop) or stop <= 0:
        return
    found.append(
        Setup(
            symbol=symbol,
            direction=direction,
            kind=pattern.kind,
            signal_time=index[t],
            fill_time=index[t + 1],
            anchor_time=index[pattern.start],
            stop=float(stop),
            atr=float(scale),
            reference=float(_measured(pattern, direction)),
        )
    )
    done.add(pattern.key)


def pattern_at(frame: pd.DataFrame, params: dict | None, at) -> Pattern | None:
    """Pattern selected on ``at``, using only pivots confirmed by that bar."""
    bars = frame.sort_index()
    if at not in bars.index:
        return None
    loc = int(bars.index.get_indexer([at])[0])
    if loc < 0:
        return None
    return _geometry(bars, params)[loc]
