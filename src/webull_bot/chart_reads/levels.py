"""Objective support and resistance for the chart-read setups.

These definitions were frozen before the level-set study was scored.
They do not replace the published A-D targets. A research run may ask
which source, used as the profit target, would have improved the
out-of-sample stock book. Meeting that test does not change the gate.

Every value on bar ``t`` uses only information closed by ``t``. Pivot
confirmation waits ``right`` bars. Floor pivots and the prior-day high
and low come from the previous session, not the session in progress.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from webull_bot.indicators import atr
from webull_bot.patterns import (
    _pivot_points,
    confirmed_pivot_high,
    confirmed_pivot_low,
    rising_trendline,
)

# Pivot width matches setups C and D.
PIVOT_LEFT = 4
PIVOT_RIGHT = 4
HORIZONTAL_LOOKBACK = 120
HORIZONTAL_KEEP = 6
FIB_RATIOS = (0.382, 0.500, 0.618)
FIB_MIN_SPAN = 5
FIB_MAX_SPAN = 80
FIB_MAX_AGE = 80
IMPULSE_BODY_ATR = 1.0
IMPULSE_BODY_FRAC = 0.55
BASE_BARS = 4
BASE_RANGE_ATR = 1.25
ZONE_LOOKBACK = 60
ZONE_KEEP = 4
FLIP_LOOKBACK = 120
FLIP_KEEP = 8
CONFLUENCE_ATR = 0.50
# A level is a target only when it sits between these reward multiples.
MIN_TARGET_R = 0.5
MAX_TARGET_R = 4.0
# A variant improves the out-of-sample stock book only when all of these hold.
# The label is a report. It does not select a new default.
IMPROVE_MIN_TRADES = 20
IMPROVE_MIN_LEVEL_SHARE = 0.30
IMPROVE_DD_SLACK = 0.05

SOURCES = (
    "horizontal",
    "floor",
    "prior_day",
    "zone",
    "fib",
    "trendline",
    "flipped",
)
VARIANTS = SOURCES + ("confluence", "any")


def select_target(
    prices,
    direction: str,
    fill: float,
    risk: float,
    *,
    min_r: float = MIN_TARGET_R,
    max_r: float = MAX_TARGET_R,
) -> float:
    """Nearest level on the trade side, between ``min_r`` and ``max_r``.

    Long targets are above the fill. Short targets are below it. No level
    in range returns NaN, and the caller keeps the setup's own 2R fallback.
    """
    if not np.isfinite(fill) or not np.isfinite(risk) or risk <= 0:
        return float("nan")
    if direction == "long":
        floor = fill + min_r * risk
        cap = fill + max_r * risk
        candidates = [float(price) for price in prices if np.isfinite(price) and floor <= float(price) <= cap]
        return float(min(candidates)) if candidates else float("nan")
    floor = fill - max_r * risk
    cap = fill - min_r * risk
    candidates = [float(price) for price in prices if np.isfinite(price) and floor <= float(price) <= cap]
    return float(max(candidates)) if candidates else float("nan")


def cluster_prices(groups: dict[str, list[float]], tolerance: float) -> list[float]:
    """Means of clusters that contain two or more different sources.

    Prices from the same source do not confirm each other. A cluster's
    prices span at most ``tolerance``.
    """
    if not np.isfinite(tolerance) or tolerance <= 0:
        return []
    items: list[tuple[float, str]] = []
    for source, prices in groups.items():
        for price in prices:
            if np.isfinite(price):
                items.append((float(price), source))
    items.sort()
    found: list[float] = []
    for index, (price, source) in enumerate(items):
        members = [price]
        sources = {source}
        for price2, source2 in items[index + 1 :]:
            if price2 - price > tolerance:
                break
            if source2 in sources:
                continue
            sources.add(source2)
            members.append(price2)
        if len(sources) >= 2:
            found.append(sum(members) / len(members))
    found.sort()
    unique: list[float] = []
    for value in found:
        if not unique or abs(value - unique[-1]) > 1e-4:
            unique.append(value)
    return unique


def improves_oos(baseline: dict, variant: dict, level_share: float) -> bool:
    """Pre-registered comparison against the published target on the same signals.

    Higher out-of-sample ending equity, profit factor not lower, drawdown
    not worse by more than five points, at least 20 trades, and the level
    present on at least 30% of the out-of-sample signals. This is a label,
    not a license to replace the default.
    """
    trades = int(variant.get("trades") or 0)
    if trades < IMPROVE_MIN_TRADES or level_share < IMPROVE_MIN_LEVEL_SHARE:
        return False
    base_end = float(baseline.get("ending_equity") or 0.0)
    new_end = float(variant.get("ending_equity") or 0.0)
    if not new_end > base_end:
        return False
    base_pf = baseline.get("profit_factor")
    new_pf = variant.get("profit_factor")
    if base_pf is None or not np.isfinite(base_pf):
        if new_pf is None or not np.isfinite(new_pf) or float(new_pf) <= 1.0:
            return False
    elif new_pf is None or not np.isfinite(new_pf) or float(new_pf) < float(base_pf):
        return False
    base_dd = float(baseline.get("max_drawdown") or 0.0)
    new_dd = float(variant.get("max_drawdown") or 0.0)
    if new_dd < base_dd - IMPROVE_DD_SLACK:
        return False
    return True


@dataclass
class LevelTable:
    """Per-bar prices. Index ``t`` is known at the close of bar ``t``."""

    by_source: dict[str, list[tuple[float, ...]]]
    confluence: list[tuple[float, ...]]
    atr: np.ndarray
    trend_support: np.ndarray
    trend_resistance: np.ndarray

    def prices(self, index: int, source: str) -> tuple[float, ...]:
        if source == "confluence":
            return self.confluence[index]
        if source == "any":
            pooled: list[float] = []
            for name in SOURCES:
                pooled.extend(self.by_source[name][index])
            return tuple(pooled)
        return self.by_source[source][index]

    def target(self, index: int, direction: str, fill: float, risk: float, source: str) -> float:
        return select_target(self.prices(index, source), direction, fill, risk)


def build_levels(frame: pd.DataFrame) -> LevelTable:
    """Levels aligned to ``frame``. One row per bar, causal at that close."""
    open_ = frame["open"].to_numpy(dtype=float)
    high = frame["high"].to_numpy(dtype=float)
    low = frame["low"].to_numpy(dtype=float)
    close = frame["close"].to_numpy(dtype=float)
    width = atr(frame).to_numpy(dtype=float)
    n = len(frame)
    dates = _session_dates(frame.index)
    prior_h, prior_l, prior_c = _prior_session(high, low, close, dates)
    horizontal = _horizontal(high, low)
    floor = _floor(prior_h, prior_l, prior_c)
    prior_day = _prior_day(prior_h, prior_l)
    zones = _zones(open_, high, low, close, width)
    fibs = _fibonacci(high, low)
    support = rising_trendline(frame["low"], PIVOT_LEFT, PIVOT_RIGHT).to_numpy(dtype=float)
    resistance = _falling_trendline(frame["high"])
    trendline = _pair_rows(support, resistance)
    flipped = _flipped(high, low, close)
    by_source = {
        "horizontal": horizontal,
        "floor": floor,
        "prior_day": prior_day,
        "zone": zones,
        "fib": fibs,
        "trendline": trendline,
        "flipped": flipped,
    }
    confluence: list[tuple[float, ...]] = []
    for index in range(n):
        groups = {name: list(rows[index]) for name, rows in by_source.items()}
        tol = CONFLUENCE_ATR * width[index] if np.isfinite(width[index]) else float("nan")
        confluence.append(tuple(cluster_prices(groups, tol)))
    return LevelTable(
        by_source=by_source,
        confluence=confluence,
        atr=width,
        trend_support=support,
        trend_resistance=resistance,
    )


def _session_dates(index) -> np.ndarray:
    stamps = pd.DatetimeIndex(index)
    if stamps.tz is not None:
        stamps = stamps.tz_convert("America/New_York")
    return np.array([stamp.date() for stamp in stamps])


def _one_bar_per_session(dates: np.ndarray) -> bool:
    if len(dates) <= 1:
        return True
    return len(set(dates.tolist())) == len(dates)


def _prior_session(high, low, close, dates: np.ndarray):
    n = len(close)
    prior_h = np.full(n, np.nan)
    prior_l = np.full(n, np.nan)
    prior_c = np.full(n, np.nan)
    if _one_bar_per_session(dates):
        if n > 1:
            prior_h[1:] = high[:-1]
            prior_l[1:] = low[:-1]
            prior_c[1:] = close[:-1]
        return prior_h, prior_l, prior_c
    order: list = []
    session_h: dict = {}
    session_l: dict = {}
    session_c: dict = {}
    for index, day in enumerate(dates):
        if day not in session_h:
            session_h[day] = high[index]
            session_l[day] = low[index]
            order.append(day)
        else:
            session_h[day] = max(session_h[day], high[index])
            session_l[day] = min(session_l[day], low[index])
        session_c[day] = close[index]
    carried = (float("nan"), float("nan"), float("nan"))
    mapped = {}
    for day in order:
        mapped[day] = carried
        carried = (session_h[day], session_l[day], session_c[day])
    for index, day in enumerate(dates):
        prior_h[index], prior_l[index], prior_c[index] = mapped[day]
    return prior_h, prior_l, prior_c


def _floor(prior_h, prior_l, prior_c) -> list[tuple[float, ...]]:
    rows = []
    for high, low, close in zip(prior_h, prior_l, prior_c):
        if not (np.isfinite(high) and np.isfinite(low) and np.isfinite(close)) or high < low:
            rows.append(tuple())
            continue
        pivot = (high + low + close) / 3.0
        span = high - low
        rows.append(
            (
                float(pivot),
                float(2.0 * pivot - low),
                float(2.0 * pivot - high),
                float(pivot + span),
                float(pivot - span),
            )
        )
    return rows


def _prior_day(prior_h, prior_l) -> list[tuple[float, ...]]:
    rows = []
    for high, low in zip(prior_h, prior_l):
        if np.isfinite(high) and np.isfinite(low):
            rows.append((float(high), float(low)))
        else:
            rows.append(tuple())
    return rows


def _recent(points: list[tuple[int, float, int]], index: int, keep: int) -> tuple[float, ...]:
    chosen = []
    for pivot_index, price, _confirm in reversed(points):
        if pivot_index < index - HORIZONTAL_LOOKBACK:
            break
        chosen.append(float(price))
        if len(chosen) >= keep:
            break
    return tuple(chosen)


def _horizontal(high, low) -> list[tuple[float, ...]]:
    highs = _pivot_points(confirmed_pivot_high(pd.Series(high), PIVOT_LEFT, PIVOT_RIGHT), PIVOT_RIGHT)
    lows = _pivot_points(confirmed_pivot_low(pd.Series(low), PIVOT_LEFT, PIVOT_RIGHT), PIVOT_RIGHT)
    n = len(high)
    rows: list[tuple[float, ...]] = []
    high_ptr = 0
    low_ptr = 0
    known_high: list[tuple[int, float, int]] = []
    known_low: list[tuple[int, float, int]] = []
    for index in range(n):
        while high_ptr < len(highs) and highs[high_ptr][2] < index:
            known_high.append(highs[high_ptr])
            high_ptr += 1
        while low_ptr < len(lows) and lows[low_ptr][2] < index:
            known_low.append(lows[low_ptr])
            low_ptr += 1
        rows.append(_recent(known_high, index, HORIZONTAL_KEEP) + _recent(known_low, index, HORIZONTAL_KEEP))
    return rows


def _fibonacci(high, low) -> list[tuple[float, ...]]:
    highs = _pivot_points(confirmed_pivot_high(pd.Series(high), PIVOT_LEFT, PIVOT_RIGHT), PIVOT_RIGHT)
    lows = _pivot_points(confirmed_pivot_low(pd.Series(low), PIVOT_LEFT, PIVOT_RIGHT), PIVOT_RIGHT)
    n = len(high)
    rows: list[tuple[float, ...]] = []
    high_ptr = 0
    low_ptr = 0
    known_high: list[tuple[int, float, int]] = []
    known_low: list[tuple[int, float, int]] = []
    for index in range(n):
        while high_ptr < len(highs) and highs[high_ptr][2] < index:
            known_high.append(highs[high_ptr])
            high_ptr += 1
        while low_ptr < len(lows) and lows[low_ptr][2] < index:
            known_low.append(lows[low_ptr])
            low_ptr += 1
        rows.append(_fib_at(index, known_high, known_low))
    return rows


def _fib_at(index: int, highs, lows) -> tuple[float, ...]:
    if not highs or not lows:
        return tuple()
    last_high = highs[-1]
    last_low = lows[-1]
    if last_high[0] == last_low[0]:
        return tuple()
    if last_high[0] > last_low[0]:
        start, end = last_low, last_high
        upward = True
    else:
        start, end = last_high, last_low
        upward = False
    span = end[0] - start[0]
    if span < FIB_MIN_SPAN or span > FIB_MAX_SPAN or index - end[0] > FIB_MAX_AGE:
        return tuple()
    height = abs(end[1] - start[1])
    if height <= 0:
        return tuple()
    if upward and end[1] <= start[1]:
        return tuple()
    if not upward and end[1] >= start[1]:
        return tuple()
    if upward:
        return tuple(float(end[1] - ratio * height) for ratio in FIB_RATIOS)
    return tuple(float(end[1] + ratio * height) for ratio in FIB_RATIOS)


def _falling_trendline(high: pd.Series) -> np.ndarray:
    """Line through the latest confirmed pivot high and the nearest earlier higher one."""
    points = _pivot_points(confirmed_pivot_high(high, PIVOT_LEFT, PIVOT_RIGHT), PIVOT_RIGHT)
    out = np.full(len(high), np.nan)
    pointer = 0
    known: list[tuple[int, float, int]] = []
    for index in range(len(high)):
        while pointer < len(points) and points[pointer][2] < index:
            known.append(points[pointer])
            pointer += 1
        if len(known) < 2:
            continue
        x2, y2, _confirm = known[-1]
        chosen = None
        for point in reversed(known[:-1]):
            if point[0] < x2 and point[1] > y2:
                chosen = point
                break
        if chosen is None or x2 == chosen[0]:
            continue
        slope = (y2 - chosen[1]) / (x2 - chosen[0])
        if slope >= 0:
            continue
        out[index] = y2 + slope * (index - x2)
    return out


def _pair_rows(support: np.ndarray, resistance: np.ndarray) -> list[tuple[float, ...]]:
    rows = []
    for left, right in zip(support, resistance):
        prices = []
        if np.isfinite(left):
            prices.append(float(left))
        if np.isfinite(right):
            prices.append(float(right))
        rows.append(tuple(prices))
    return rows


def _zones(open_, high, low, close, width) -> list[tuple[float, ...]]:
    n = len(close)
    born: list[tuple[int, float, float, str]] = []
    for index in range(BASE_BARS, n):
        atr_now = width[index]
        if not np.isfinite(atr_now) or atr_now <= 0:
            continue
        body = abs(close[index] - open_[index])
        span = high[index] - low[index]
        if body < IMPULSE_BODY_ATR * atr_now or span <= 0 or body / span < IMPULSE_BODY_FRAC:
            continue
        base_high = float(np.max(high[index - BASE_BARS : index]))
        base_low = float(np.min(low[index - BASE_BARS : index]))
        if not np.isfinite(base_high) or base_high - base_low > BASE_RANGE_ATR * atr_now:
            continue
        if close[index] > open_[index]:
            born.append((index, base_high, base_low, "demand"))
        elif close[index] < open_[index]:
            born.append((index, base_low, base_high, "supply"))
    rows: list[tuple[float, ...]] = [tuple() for _ in range(n)]
    pointer = 0
    active: list[dict] = []
    for index in range(n):
        while pointer < len(born) and born[pointer][0] < index:
            impulse, proximal, distal, kind = born[pointer]
            active.append({"i": impulse, "proximal": proximal, "distal": distal, "kind": kind, "alive": True})
            pointer += 1
        prices: list[float] = []
        still: list[dict] = []
        for zone in active:
            if not zone["alive"] or index - zone["i"] > ZONE_LOOKBACK:
                continue
            if zone["kind"] == "demand" and close[index] < zone["distal"]:
                zone["alive"] = False
                continue
            if zone["kind"] == "supply" and close[index] > zone["distal"]:
                zone["alive"] = False
                continue
            prices.append(float(zone["proximal"]))
            still.append(zone)
        active = still[-ZONE_KEEP:]
        rows[index] = tuple(prices[-ZONE_KEEP:])
    return rows


def _flipped(high, low, close) -> list[tuple[float, ...]]:
    highs = _pivot_points(confirmed_pivot_high(pd.Series(high), PIVOT_LEFT, PIVOT_RIGHT), PIVOT_RIGHT)
    lows = _pivot_points(confirmed_pivot_low(pd.Series(low), PIVOT_LEFT, PIVOT_RIGHT), PIVOT_RIGHT)
    events = [(confirm, pivot_index, price, "resistance") for pivot_index, price, confirm in highs]
    events += [(confirm, pivot_index, price, "support") for pivot_index, price, confirm in lows]
    events.sort()
    n = len(close)
    rows: list[tuple[float, ...]] = []
    pointer = 0
    active: list[dict] = []
    for index in range(n):
        while pointer < len(events) and events[pointer][0] < index:
            _confirm, pivot_index, price, role = events[pointer]
            active.append({"i": pivot_index, "price": float(price), "role": role, "flipped": False})
            pointer += 1
        prices: list[float] = []
        still: list[dict] = []
        for pivot in active:
            if pivot["i"] < index - FLIP_LOOKBACK:
                continue
            if pivot["role"] == "resistance" and close[index] > pivot["price"]:
                pivot["role"] = "support"
                pivot["flipped"] = True
            elif pivot["role"] == "support" and close[index] < pivot["price"]:
                pivot["role"] = "resistance"
                pivot["flipped"] = True
            if pivot["flipped"]:
                prices.append(pivot["price"])
            still.append(pivot)
        active = still
        rows.append(tuple(prices[-FLIP_KEEP:]))
    return rows


# Longer swing memory. Frozen from the request to keep confirmed swings for
# about 250 daily bars and merge prices within about 0.5 ATR, weighted by
# how often price tagged them. This does not replace ``_horizontal``.
HISTORY_BARS = 250
MERGE_ATR = 0.50


def merge_weighted(items: list[tuple[float, int]], tolerance: float) -> list[tuple[float, int]]:
    """Touch-weighted clusters. Two prices merge when they are within ``tolerance``.

    The cluster price is the touch-weighted mean. Touches add. A chain of
    prices stays one cluster only while each new price is within
    ``tolerance`` of the current weighted mean, so distant steps do not
    collapse into one line.
    """
    usable = [(float(price), int(touches)) for price, touches in items if np.isfinite(price) and touches > 0]
    if not usable or not np.isfinite(tolerance) or tolerance <= 0:
        return []
    usable.sort(key=lambda item: item[0])
    clusters: list[list[tuple[float, int]]] = [[usable[0]]]
    for price, touches in usable[1:]:
        weight = sum(count for _, count in clusters[-1])
        mean = sum(level * count for level, count in clusters[-1]) / weight
        if abs(price - mean) <= tolerance:
            clusters[-1].append((price, touches))
        else:
            clusters.append([(price, touches)])
    merged = []
    for group in clusters:
        weight = sum(count for _, count in group)
        mean = sum(level * count for level, count in group) / weight
        merged.append((float(mean), int(weight)))
    return merged


def merged_swings(frame: pd.DataFrame, as_of: int | None = None) -> list[dict]:
    """Confirmed swings in the last 250 bars, merged within 0.5 ATR.

    A pivot is known once its right-hand bars have closed. Touches are
    bars in the lookback whose range reaches the pivot, then recounted
    against the merged price. The list is sorted by price.
    """
    if frame is None or len(frame) < PIVOT_LEFT + PIVOT_RIGHT + 2:
        return []
    index = len(frame) - 1 if as_of is None else int(as_of)
    if index < 0 or index >= len(frame):
        return []
    high = frame["high"].to_numpy(dtype=float)
    low = frame["low"].to_numpy(dtype=float)
    width = atr(frame).to_numpy(dtype=float)
    scale = width[index]
    if not np.isfinite(scale) or scale <= 0:
        return []
    tolerance = MERGE_ATR * scale
    start = max(0, index - HISTORY_BARS)
    highs = _pivot_points(confirmed_pivot_high(frame["high"], PIVOT_LEFT, PIVOT_RIGHT), PIVOT_RIGHT)
    lows = _pivot_points(confirmed_pivot_low(frame["low"], PIVOT_LEFT, PIVOT_RIGHT), PIVOT_RIGHT)
    members: list[tuple[float, int, str]] = []
    for pivot_index, price, confirm in highs:
        if confirm > index or pivot_index < start or pivot_index > index:
            continue
        touches = _touches(high, low, price, max(pivot_index, start), index, tolerance)
        if touches > 0:
            members.append((float(price), touches, "high"))
    for pivot_index, price, confirm in lows:
        if confirm > index or pivot_index < start or pivot_index > index:
            continue
        touches = _touches(high, low, price, max(pivot_index, start), index, tolerance)
        if touches > 0:
            members.append((float(price), touches, "low"))
    merged = merge_weighted([(price, touches) for price, touches, _kind in members], tolerance)
    rows = []
    for price, _weight in merged:
        touches = _touches(high, low, price, start, index, tolerance)
        kinds = [kind for level, _touches, kind in members if abs(level - price) <= tolerance]
        rows.append(
            {
                "price": float(price),
                "touches": int(touches),
                "highs": sum(1 for kind in kinds if kind == "high"),
                "lows": sum(1 for kind in kinds if kind == "low"),
            }
        )
    rows.sort(key=lambda row: row["price"])
    return rows


def _touches(high, low, price: float, start: int, end: int, tolerance: float) -> int:
    count = 0
    for index in range(start, end + 1):
        if low[index] <= price + tolerance and high[index] >= price - tolerance:
            count += 1
    return count
