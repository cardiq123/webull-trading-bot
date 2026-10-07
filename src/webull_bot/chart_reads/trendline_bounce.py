"""Trendline and horizontal-support bounce. Backtests only. Does not place an order.

In an uptrend, a rising line through the last two confirmed higher lows and the
last swing low are each a shelf. The confluence book needs a green close back
above both. Support alone and the trendline alone are the comparison. A
downtrend with a falling line through lower highs is the put.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import numpy as np

from webull_bot.chart_reads.band_exit import opposite_band
from webull_bot.chart_reads.ema_reclaim import FLAT, LAST_CONFIRM, PIVOT, RANDOM_SEED, TOUCH_ATR, Prepared
from webull_bot.chart_reads.reentry import _session_end, _sessions

VARIANTS = ("confluence", "trendline", "support")


def frozen_rules() -> dict:
    """Written down before the result is scored. The score does not edit this."""
    return {
        "name": "spy_5m_trendline_support_bounce",
        "clock": (
            "5-minute regular-hours bars, left-labeled. The signal bar is at or before 15:20 ET "
            "so the fill is before 15:30. Still open at 15:30 is sold at that bar's open."
        ),
        "trend": "Uptrend means the 9 EMA is above the 20 EMA. The short mirror is the 9 EMA under the 20 EMA.",
        "trendline": (
            "A rising support line joins the latest confirmed 2-bar pivot low to the latest earlier confirmed pivot low that is strictly lower. "
            "The pivot is strictly beyond the two bars on each side, and the right-hand bars have to have closed by the signal. "
            "A close below that segment, between the two anchors, invalidates the pair and the next earlier anchor is tried. "
            "Two higher-low touches are enough to draw the line. A third confirmed pivot on the same line is not required. "
            "The line is extended to the signal. The falling mirror joins lower highs."
        ),
        "support": (
            "Horizontal support is the latest confirmed 2-bar pivot low in the session. "
            "It is not the lowest wick of the pullback, and it is not moved onto a round number. "
            "The short mirror uses the latest confirmed pivot high."
        ),
        "tag": (
            "The low comes within 0.10 ATR of the level, or through it, and the close finishes back above the level. "
            "The bar is green. Confluence has to do that on the trendline and on the horizontal support on the same bar. "
            "Support alone ignores the line. The trendline alone ignores the shelf. "
            "The short mirror is a red bar whose high tags the level and whose close finishes back under it."
        ),
        "entry": "The fill is the next open. One position at a time. A stop that is not beyond the fill is skipped.",
        "stop": (
            "A close back through the level exits at that close. A gap through it at the open fills at the open. "
            "The trendline book uses the line extended to that bar. The support book uses the frozen swing. "
            "The confluence book uses the lower of those two for a long, and the higher of the two for a short, so the trade stays open while either level holds. "
            "A target traded during the bar fills before that close."
        ),
        "target": (
            "The opposite 2 SD session VWAP band and the 200 EMA are separate books. One contract cannot scale out of both. "
            "A book takes the trade only when that level, read on the fill bar, is beyond the fill. "
            "The band and the 200 EMA are that bar's values."
        ),
        "compare": (
            "Confluence, the trendline alone, and support alone are scored apart, each with the band target and the 200 EMA target. "
            "The confluence band 0 DTE book is the primary and is also run from $5,000. Nothing is promoted from this score."
        ),
        "flat": "15:30 ET open. No overnight hold. CPI, NFP, and FOMC are not skipped.",
        "shares": "Cash book is long only. Size risks 1% of equity to the stop level on the fill bar.",
        "options": "One at-the-money 0 DTE contract. Calls for longs, puts for shorts. Both directions.",
        "chart_day": (
            "2026-10-07 is the illustration. The active line is the latest rising pair, not a fit forced through the 10:50 low. "
            "Horizontal support is the last confirmed swing low. The 12:00 close and the 12:05 low sit near 776.2, and the 12:00 wick is lower. "
            "Neither print replaces the swing. A bounce that fails the rule is left unmarked."
        ),
        "not_live": "Not a live strategy. Nothing is added to the optional or selected lists.",
    }


@dataclass(frozen=True)
class Bounce:
    symbol: str
    variant: str
    direction: str
    anchor1: int
    anchor2: int
    signal_i: int
    fill_i: int
    y1: float
    y2: float
    shelf: float


def find_bounces(prep: Prepared, symbol: str) -> list[Bounce]:
    """Confluence, trendline, and support. Longs and the short mirror."""
    found: list[Bounce] = []
    for start, end in _sessions(prep):
        found.extend(_scan(prep, symbol, start, end, "long"))
        found.extend(_scan(prep, symbol, start, end, "short"))
    return found


def illustrate(prep: Prepared, day: date) -> dict:
    """Long confluence bounces on one session. A missing hold stays missing."""
    indexes = [i for i, stamp in enumerate(prep.dates) if stamp == day]
    if not indexes:
        return {"found": False, "signals": []}
    signals = [
        item
        for item in find_bounces(prep, "SPY")
        if item.variant == "confluence" and item.direction == "long" and prep.dates[item.signal_i] == day
    ]
    return {"found": True, "signals": signals}


def walk_bounce(prep: Prepared, item: Bounce, target: str) -> dict | None:
    """Close through the shelf or the line. The band or the 200 EMA is the target."""
    if target not in ("band", "ema200"):
        raise ValueError("unknown bounce target")
    fill_i = item.fill_i
    if fill_i >= len(prep.close):
        return None
    fill = float(prep.open[fill_i])
    stop = _stop_at(item, fill_i)
    if fill <= 0 or stop is None or not _stop_beyond(item.direction, stop, fill):
        return None
    if _target_at(prep, fill_i, item.direction, fill, target) is None:
        return None
    end = _session_end(prep, fill_i)
    last_spot = fill
    last_time = prep.index[fill_i]
    for j in range(fill_i, end):
        opened = float(prep.open[j])
        high = float(prep.high[j])
        low = float(prep.low[j])
        closed = float(prep.close[j])
        stamp = prep.index[j]
        if prep.times[j] >= FLAT:
            return _path(item, fill, stop, "flat", opened, stamp, target)
        level = _stop_at(item, j)
        if level is not None and _gapped_stop(item.direction, opened, level):
            return _path(item, fill, stop, "stop", opened, stamp, target)
        goal = _target_at(prep, j, item.direction, fill, target)
        if goal is not None and _tagged_target(item.direction, opened, high, low, goal):
            price = opened if _gapped_target(item.direction, opened, goal) else goal
            return _path(item, fill, stop, target, price, stamp, target)
        if level is not None and _through_close(item.direction, closed, level):
            return _path(item, fill, stop, "stop", closed, stamp, target)
        if np.isfinite(closed):
            last_spot = closed
            last_time = stamp
    return _path(item, fill, stop, "last", last_spot, last_time, target)


def random_bounces(
    prep: Prepared,
    count: int,
    seed: int = RANDOM_SEED,
    *,
    start: date | None = None,
    end: date | None = None,
) -> list[Bounce]:
    """Coin-flip entries that still have a confluence stop. The bar does not have to tag. Seed 17."""
    if count <= 0:
        return []
    structures = _structures(prep)
    eligible = [i for i in range(len(prep.close) - 1) if _eligible(prep, i, start, end)]
    if not eligible:
        return []
    rng = np.random.default_rng(seed)
    found: list[Bounce] = []
    guard = 0
    limit = max(count * 40, 1)
    while len(found) < count and guard < limit:
        guard += 1
        i = int(eligible[int(rng.integers(0, len(eligible)))])
        direction = "long" if int(rng.integers(0, 2)) == 0 else "short"
        base = structures.get((direction, i))
        if base is None:
            continue
        anchor1, anchor2, y1, y2, shelf = base
        found.append(Bounce("SPY", "random", direction, anchor1, anchor2, i, i + 1, y1, y2, shelf))
    found.sort(key=lambda item: item.fill_i)
    return found


def _scan(prep: Prepared, symbol: str, start: int, end: int, direction: str) -> list[Bounce]:
    found: list[Bounce] = []
    pivots: list[int] = []
    for i in range(start, end - 1):
        p = i - PIVOT
        if p >= start + PIVOT and _is_pivot(prep, p, direction):
            pivots.append(p)
        if not _trend(prep, i, direction) or not _color(prep, i, direction):
            continue
        width = float(prep.atr[i])
        if not np.isfinite(width) or width <= 0:
            continue
        fill = i + 1
        if not _clock_ok(prep, i, fill):
            continue
        shelf = float(_extreme(prep, pivots[-1], direction)) if pivots else None
        pair = _pair(prep, pivots, direction)
        line = _segment(pair, i) if pair else None
        tag_line = pair is not None and line is not None and _tag(prep, i, direction, line, width)
        tag_shelf = shelf is not None and np.isfinite(shelf) and _tag(prep, i, direction, shelf, width)
        if tag_line and tag_shelf and pair is not None and shelf is not None:
            _emit(found, prep, symbol, "confluence", direction, pair, i, fill, shelf)
        if tag_line and pair is not None:
            _emit(found, prep, symbol, "trendline", direction, pair, i, fill, float("nan"))
        if tag_shelf and shelf is not None:
            _emit(found, prep, symbol, "support", direction, None, i, fill, shelf)
    return found


def _emit(found, prep, symbol, variant, direction, pair, signal, fill, shelf) -> None:
    if pair is None:
        found.append(Bounce(symbol, variant, direction, -1, -1, signal, fill, float("nan"), float("nan"), float(shelf)))
        return
    anchor1, anchor2, y1, y2 = pair
    found.append(Bounce(symbol, variant, direction, anchor1, anchor2, signal, fill, y1, y2, float(shelf)))


def _pair(prep: Prepared, pivots: list[int], direction: str):
    if len(pivots) < 2:
        return None
    latest = pivots[-1]
    y2 = _extreme(prep, latest, direction)
    for earlier in range(len(pivots) - 2, -1, -1):
        anchor = pivots[earlier]
        y1 = _extreme(prep, anchor, direction)
        if direction == "long" and not y2 > y1:
            continue
        if direction == "short" and not y2 < y1:
            continue
        if _segment_broken(prep, anchor, latest, y1, y2, direction):
            continue
        return anchor, latest, y1, y2
    return None


def _segment(pair, t: int) -> float:
    anchor1, anchor2, y1, y2 = pair
    return y1 + (y2 - y1) / (anchor2 - anchor1) * (t - anchor1)


def _segment_broken(prep: Prepared, anchor1: int, anchor2: int, y1: float, y2: float, direction: str) -> bool:
    span = anchor2 - anchor1
    for k in range(anchor1 + 1, anchor2):
        level = y1 + (y2 - y1) / span * (k - anchor1)
        closed = float(prep.close[k])
        if not np.isfinite(closed) or not np.isfinite(level):
            continue
        if direction == "long" and closed < level:
            return True
        if direction == "short" and closed > level:
            return True
    return False


def _is_pivot(prep: Prepared, p: int, direction: str) -> bool:
    if p < PIVOT or p + PIVOT >= len(prep.close):
        return False
    if direction == "long":
        center = float(prep.low[p])
        others = [float(prep.low[p + k]) for k in (-2, -1, 1, 2)]
        return _finite(center, *others) and all(center < other for other in others)
    center = float(prep.high[p])
    others = [float(prep.high[p + k]) for k in (-2, -1, 1, 2)]
    return _finite(center, *others) and all(center > other for other in others)


def _extreme(prep: Prepared, i: int, direction: str) -> float:
    return float(prep.low[i] if direction == "long" else prep.high[i])


def _trend(prep: Prepared, i: int, direction: str) -> bool:
    ema9 = float(prep.ema9[i])
    ema20 = float(prep.ema20[i])
    if not _finite(ema9, ema20):
        return False
    if direction == "long":
        return ema9 > ema20
    return ema9 < ema20


def _color(prep: Prepared, i: int, direction: str) -> bool:
    opened = float(prep.open[i])
    closed = float(prep.close[i])
    if not _finite(opened, closed):
        return False
    if direction == "long":
        return closed > opened
    return closed < opened


def _tag(prep: Prepared, i: int, direction: str, level: float, width: float) -> bool:
    closed = float(prep.close[i])
    if not _finite(closed, level):
        return False
    if direction == "long":
        return float(prep.low[i]) <= level + TOUCH_ATR * width and closed > level
    return float(prep.high[i]) >= level - TOUCH_ATR * width and closed < level


def _clock_ok(prep: Prepared, signal: int, fill: int) -> bool:
    return prep.dates[fill] == prep.dates[signal] and prep.times[signal] <= LAST_CONFIRM and prep.times[fill] < FLAT


def _line_at(item: Bounce, t: int) -> float | None:
    if item.anchor1 < 0 or item.anchor2 <= item.anchor1:
        return None
    if not _finite(item.y1, item.y2):
        return None
    return item.y1 + (item.y2 - item.y1) / (item.anchor2 - item.anchor1) * (t - item.anchor1)


def _stop_at(item: Bounce, t: int) -> float | None:
    line = _line_at(item, t)
    shelf = float(item.shelf) if np.isfinite(item.shelf) else None
    if item.variant == "trendline":
        return line
    if item.variant == "support":
        return shelf
    if line is None or shelf is None:
        return None
    if item.direction == "long":
        return min(line, shelf)
    return max(line, shelf)


def _structures(prep: Prepared) -> dict:
    """Line and shelf at each bar, including bars that do not tag."""
    found = {}
    for start, end in _sessions(prep):
        for direction in ("long", "short"):
            pivots: list[int] = []
            for i in range(start, end):
                p = i - PIVOT
                if p >= start + PIVOT and _is_pivot(prep, p, direction):
                    pivots.append(p)
                if not pivots:
                    continue
                pair = _pair(prep, pivots, direction)
                if pair is None:
                    continue
                found[(direction, i)] = (*pair, float(_extreme(prep, pivots[-1], direction)))
    return found


def _eligible(prep: Prepared, i: int, start: date | None, end: date | None) -> bool:
    day = prep.dates[i + 1]
    if start is not None and day < start:
        return False
    if end is not None and day > end:
        return False
    if prep.dates[i] != prep.dates[i + 1]:
        return False
    return prep.times[i] <= LAST_CONFIRM and prep.times[i + 1] < FLAT


def _target_at(prep: Prepared, i: int, direction: str, fill: float, target: str) -> float | None:
    if target == "band":
        return opposite_band(direction, float(prep.vwap[i]), float(prep.std[i]), fill)
    return _beyond(direction, float(prep.ema200[i]), fill)


def _beyond(direction: str, level: float, fill: float) -> float | None:
    if not _finite(level, fill):
        return None
    if direction == "long" and level > fill:
        return float(level)
    if direction == "short" and level < fill:
        return float(level)
    return None


def _stop_beyond(direction: str, stop: float, fill: float) -> bool:
    if not _finite(stop, fill):
        return False
    if direction == "long":
        return stop < fill
    return stop > fill


def _gapped_stop(direction: str, opened: float, level: float) -> bool:
    if not _finite(opened, level):
        return False
    if direction == "long":
        return opened <= level
    return opened >= level


def _gapped_target(direction: str, opened: float, goal: float) -> bool:
    if not _finite(opened, goal):
        return False
    if direction == "long":
        return opened >= goal
    return opened <= goal


def _tagged_target(direction: str, opened: float, high: float, low: float, goal: float) -> bool:
    if _gapped_target(direction, opened, goal):
        return True
    if direction == "long":
        return _finite(high, goal) and high >= goal
    return _finite(low, goal) and low <= goal


def _through_close(direction: str, closed: float, level: float) -> bool:
    if not _finite(closed, level):
        return False
    if direction == "long":
        return closed < level
    return closed > level


def _finite(*values: float) -> bool:
    return all(np.isfinite(value) for value in values)


def _path(item: Bounce, fill: float, stop: float, reason: str, spot: float, stamp, target: str) -> dict:
    return {
        "direction": item.direction,
        "variant": item.variant,
        "fill": float(fill),
        "stop": float(stop),
        "reason": reason,
        "exit_spot": float(spot),
        "exit_time": stamp,
        "fill_i": item.fill_i,
        "signal_i": item.signal_i,
    }
