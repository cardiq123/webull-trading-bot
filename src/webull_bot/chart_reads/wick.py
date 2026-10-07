"""9 EMA wick continuation. Backtests only. Does not place an order.

In an established bullish stack, a bar wicks into the 9 EMA and closes back
above it. A long lower wick is the filter. The fill is the open after the
green close. A bearish stack with an upper wick is the put.
"""

from __future__ import annotations

from datetime import date

import numpy as np

from webull_bot.chart_reads.ema_reclaim import FLAT, LAST_CONFIRM, SLOPE_BARS, TOUCH_ATR, Prepared
from webull_bot.chart_reads.reentry import Reentry, _sessions

WICK_BODY = 1.5
WICK_RANGE = 0.50


def frozen_rules() -> dict:
    """Written down before the result is scored. The score does not edit this."""
    return {
        "name": "spy_5m_ema9_wick",
        "stack": (
            "An established bullish stack: the 9 EMA is above the 20 EMA, both are higher than they were 3 bars ago, "
            "and the close is above the 9 EMA, the 20 EMA, and session VWAP. The bearish stack is the mirror."
        ),
        "wick": (
            "The bar's low comes within 0.10 ATR of the 9 EMA and the close is back above the 9 EMA. "
            "The candle may be red. The short mirror is an upper wick into the 9 EMA and a close back below it."
        ),
        "filter": (
            "With the filter on, the lower wick is at least 1.5 times the body, or at least 50% of the range. "
            "A zero body uses the range test only. The filter off keeps the touch and the close, and drops the wick size. "
            "The two books are scored separately."
        ),
        "entry": (
            "A green wick bar is the green close, and the fill is the next open. "
            "A red wick bar waits for a later bar that closes green and still above the 9 EMA, then the fill is the open after that close. "
            "A close back through the 9 EMA before that green close cancels the wick. "
            "The confirmation bar is at or before 15:20 ET so the fill is before 15:30."
        ),
        "stop": (
            "The primary stop is a close back through the 9 EMA. A close back through the 20 EMA is the other stop, "
            "the same stop as the 20 EMA continuation. A gap through the stop at the open fills at the open. "
            "The target is the opposite 2 SD band. The two stops are scored separately."
        ),
        "compare": (
            "The 9 EMA wick is scored against the 20 EMA continuation already scored, and the wick filter is scored on and off. "
            "Each book is its own account. One position at a time."
        ),
        "flat": "15:30 ET open. No overnight hold.",
        "shares": "Cash book is long only. Size risks 1% of equity to the stop level on the fill bar.",
        "options": "One at-the-money 0 DTE contract. Calls for longs, puts for shorts. Both directions.",
        "chart_day": (
            "2026-10-07 is the illustration. The stamp is the bar's open. "
            "The red wick stays on the bar that prints it. A later green bar is the continuation, not a substitute wick."
        ),
        "not_live": "Not a live strategy. Nothing is added to the optional or selected lists.",
    }


def find_wicks(prep: Prepared, symbol: str) -> list[Reentry]:
    """Filtered and unfiltered wicks. Each pass is its own book."""
    found: list[Reentry] = []
    for start, end in _sessions(prep):
        for direction in ("long", "short"):
            found.extend(_scan(prep, symbol, start, end, direction, "filtered", True))
            found.extend(_scan(prep, symbol, start, end, direction, "plain", False))
    return found


def illustrate(prep: Prepared, day: date) -> dict:
    """Filtered long wicks on one session. A missing wick stays missing."""
    steps = [
        item for item in find_wicks(prep, "SPY")
        if item.variant == "filtered" and item.direction == "long" and prep.dates[item.signal_i] == day
    ]
    return {
        "found": any(stamp == day for stamp in prep.dates),
        "steps": [{"wick": item.tag_i, "confirm": item.signal_i, "fill": item.fill_i} for item in steps],
    }


def _scan(prep: Prepared, symbol: str, start: int, end: int, direction: str, variant: str, need_filter: bool) -> list[Reentry]:
    found: list[Reentry] = []
    pending = None
    last = end - 1
    for i in range(start, last):
        if _is_wick(prep, i, direction, need_filter):
            pending = i
            if _confirms(prep, i, direction):
                _emit(prep, found, symbol, variant, direction, i, i)
                pending = None
            continue
        if pending is None:
            continue
        if _invalidated(prep, i, direction):
            pending = None
            continue
        if _confirms(prep, i, direction):
            _emit(prep, found, symbol, variant, direction, pending, i)
            pending = None
    return found


def _emit(prep: Prepared, found: list[Reentry], symbol: str, variant: str, direction: str, wick: int, confirm: int) -> None:
    fill = confirm + 1
    if prep.dates[fill] != prep.dates[confirm] or prep.times[confirm] > LAST_CONFIRM or prep.times[fill] >= FLAT:
        return
    found.append(Reentry(symbol, variant, direction, wick, confirm, confirm, fill))


def _is_wick(prep: Prepared, i: int, direction: str, need_filter: bool) -> bool:
    if direction == "long":
        if not _bullish(prep, i) or not _touch_long(prep, i):
            return False
        if not need_filter:
            return True
        body, rng, lower, _upper = _parts(prep, i)
        return _wick_ok(body, rng, lower)
    if not _bearish(prep, i) or not _touch_short(prep, i):
        return False
    if not need_filter:
        return True
    body, rng, _lower, upper = _parts(prep, i)
    return _wick_ok(body, rng, upper)


def _bullish(prep: Prepared, i: int) -> bool:
    if i < SLOPE_BARS:
        return False
    ema9 = float(prep.ema9[i])
    ema20 = float(prep.ema20[i])
    closed = float(prep.close[i])
    return _finite(ema9, ema20, prep.ema9[i - SLOPE_BARS], prep.ema20[i - SLOPE_BARS], closed, prep.vwap[i]) and (
        ema9 > ema20
        and ema9 > float(prep.ema9[i - SLOPE_BARS])
        and ema20 > float(prep.ema20[i - SLOPE_BARS])
        and closed > ema9
        and closed > ema20
        and closed > float(prep.vwap[i])
    )


def _bearish(prep: Prepared, i: int) -> bool:
    if i < SLOPE_BARS:
        return False
    ema9 = float(prep.ema9[i])
    ema20 = float(prep.ema20[i])
    closed = float(prep.close[i])
    return _finite(ema9, ema20, prep.ema9[i - SLOPE_BARS], prep.ema20[i - SLOPE_BARS], closed, prep.vwap[i]) and (
        ema9 < ema20
        and ema9 < float(prep.ema9[i - SLOPE_BARS])
        and ema20 < float(prep.ema20[i - SLOPE_BARS])
        and closed < ema9
        and closed < ema20
        and closed < float(prep.vwap[i])
    )


def _touch_long(prep: Prepared, i: int) -> bool:
    width = float(prep.atr[i])
    ema9 = float(prep.ema9[i])
    if not _finite(width, ema9, prep.low[i], prep.close[i]) or width <= 0:
        return False
    return float(prep.low[i]) <= ema9 + TOUCH_ATR * width and float(prep.close[i]) > ema9


def _touch_short(prep: Prepared, i: int) -> bool:
    width = float(prep.atr[i])
    ema9 = float(prep.ema9[i])
    if not _finite(width, ema9, prep.high[i], prep.close[i]) or width <= 0:
        return False
    return float(prep.high[i]) >= ema9 - TOUCH_ATR * width and float(prep.close[i]) < ema9


def _confirms(prep: Prepared, i: int, direction: str) -> bool:
    opened = float(prep.open[i])
    closed = float(prep.close[i])
    ema9 = float(prep.ema9[i])
    if not _finite(opened, closed, ema9):
        return False
    if direction == "long":
        return closed > opened and closed > ema9
    return closed < opened and closed < ema9


def _invalidated(prep: Prepared, i: int, direction: str) -> bool:
    closed = float(prep.close[i])
    ema9 = float(prep.ema9[i])
    if not _finite(closed, ema9):
        return False
    if direction == "long":
        return closed < ema9
    return closed > ema9


def _parts(prep: Prepared, i: int) -> tuple[float, float, float, float]:
    opened = float(prep.open[i])
    high = float(prep.high[i])
    low = float(prep.low[i])
    closed = float(prep.close[i])
    body = abs(closed - opened)
    rng = high - low
    lower = min(opened, closed) - low
    upper = high - max(opened, closed)
    return body, rng, lower, upper


def _wick_ok(body: float, rng: float, wick: float) -> bool:
    if not _finite(body, rng, wick) or rng <= 0 or wick <= 0:
        return False
    range_ok = wick >= WICK_RANGE * rng
    body_ok = body > 0 and wick >= WICK_BODY * body
    return body_ok or range_ok


def _finite(*values: float) -> bool:
    return all(np.isfinite(float(value)) for value in values)
