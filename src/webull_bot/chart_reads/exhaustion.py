"""Trend-exhaustion break of a pullback shelf. Backtests only. Does not place an order.

After an intraday uptrend tags the upper 2 SD VWAP band, support is the lowest
low that prints after that tag. A 5-minute close below that shelf and the 9 EMA,
with a fading MACD histogram and RSI rolling down from 70, buys the put. The
long is the mirror.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import numpy as np

from webull_bot.chart_reads.ema_reclaim import (
    FLAT,
    LAST_CONFIRM,
    PIVOT,
    RANDOM_SEED,
    STOP_PAD,
    Prepared,
)
from webull_bot.chart_reads.reentry import _session_end, _sessions

RSI_HOT = 70.0
RSI_WASH = 30.0
FADE_BARS = 3


def frozen_rules() -> dict:
    """Written down before the result is scored. The score does not edit this."""
    return {
        "name": "spy_5m_trend_exhaustion",
        "clock": (
            "5-minute regular-hours bars, left-labeled. The signal bar is at or before 15:20 ET "
            "so the fill is before 15:30. Still open at 15:30 is sold at that bar's open."
        ),
        "tag": (
            "The first bar of the session that trades the upper 2 SD session VWAP band while the 9 EMA is above the 20 EMA. "
            "The band width is twice the session standard deviation, and a zero-width open is not a tag. "
            "A later tag in the same session does not move the anchor. "
            "The long mirror is the first lower-band tag while the 9 EMA is below the 20 EMA."
        ),
        "support": (
            "Horizontal support is the lowest low of the bars after that tag and before the signal bar. "
            "The signal bar's own low is not part of the shelf it has to break. "
            "The long mirror marks resistance at the highest high after the lower-band tag."
        ),
        "signal": (
            "A 5-minute close strictly below that support and strictly below the 9 EMA, while the 9 EMA is still above the 20 EMA. "
            "The fill is the next open. One position at a time. "
            "The long closes strictly above the resistance and strictly above the 9 EMA, while the 9 EMA is still below the 20 EMA."
        ),
        "macd": (
            "The MACD histogram has shrunk on three bars: this bar is below the prior bar, which is below the bar before that, "
            "which is below the bar three back, and the bar three back is still positive. "
            "A histogram that is only getting more negative is not a fade. "
            "The long mirror rises for three bars off a negative print."
        ),
        "rsi": (
            "RSI printed at least 70 on a bar after the tag and before this close. "
            "This bar's RSI is below the prior bar and below that 70 print. "
            "The long mirror printed 30 or below and is rolling up."
        ),
        "stop": (
            "One cent above the last 2-bar swing high whose two right-hand bars have already closed by the signal. "
            "The swing high is strictly above the two bars on each side. A swing that is not confirmed yet is not the stop. "
            "The swing is looked up inside the session. If that stop is not above the fill, the trade is skipped. "
            "The long stop is one cent under the last confirmed swing low, and it has to be under the fill. "
            "A gap through the stop at the open fills at the open."
        ),
        "target": (
            "The 20 EMA and VWAP are separate books. One contract cannot scale out of both. "
            "A book takes the trade only when that level, read on the fill bar, is beyond the fill: under it for a short, over it for a long. "
            "The target on a later bar is that bar's 20 EMA or that bar's VWAP, and only while it is still beyond the fill. "
            "If the stop and the target both trade in one bar, the stop fills. A gap through the target at the open fills at the open."
        ),
        "flat": "15:30 ET open. No overnight hold. CPI, NFP, and FOMC are not skipped.",
        "shares": "Cash book is long only. Size risks 1% of equity to the swing stop and cannot spend more settled cash than is on hand.",
        "options": "One at-the-money 0 DTE contract. Calls for longs, puts for shorts. Both directions.",
        "books": (
            "The 20 EMA book and the VWAP book are scored apart, shares and 0 DTE. "
            "The 20 EMA 0 DTE book is the primary and is also run from $5,000. Nothing is promoted from this score."
        ),
        "chart_day": (
            "2026-10-07 is the illustration. Support is the lowest low after the first uptrend upper-band tag. "
            "The 12:00 close and the 12:05 low sit near 776.2. That print is not the support line. "
            "A short that has not closed below the support and the 9 EMA is left unmarked."
        ),
        "not_live": "Not a live strategy. Nothing is added to the optional or selected lists.",
    }


@dataclass(frozen=True)
class Exhaustion:
    symbol: str
    direction: str
    tag_i: int
    signal_i: int
    fill_i: int
    support: float
    support_i: int
    stop: float


def find_exhaustions(prep: Prepared, symbol: str) -> list[Exhaustion]:
    """Shorts after an upper-band tag, and the long mirror. Each session stands alone."""
    found: list[Exhaustion] = []
    for start, end in _sessions(prep):
        found.extend(_scan(prep, symbol, start, end, "short"))
        found.extend(_scan(prep, symbol, start, end, "long"))
    return found


def illustrate(prep: Prepared, day: date) -> dict:
    """The short shelf on one session. A missing breakdown stays missing."""
    indexes = [i for i, stamp in enumerate(prep.dates) if stamp == day]
    if not indexes:
        return {"found": False, "tag_i": None, "support": None, "support_i": None, "signals": []}
    start, end = indexes[0], indexes[-1] + 1
    tag_i, support, support_i = _shelf(prep, start, end, "short")
    signals = [
        item
        for item in find_exhaustions(prep, "SPY")
        if item.direction == "short" and prep.dates[item.signal_i] == day
    ]
    return {"found": True, "tag_i": tag_i, "support": support, "support_i": support_i, "signals": signals}


def walk_exhaustion(prep: Prepared, item: Exhaustion, target: str) -> dict | None:
    """Fixed swing stop. The 20 EMA or VWAP is the target. Flat at 15:30."""
    if target not in ("ema20", "vwap"):
        raise ValueError("unknown exhaustion target")
    fill_i = item.fill_i
    if fill_i >= len(prep.close):
        return None
    fill = float(prep.open[fill_i])
    stop = float(item.stop)
    if fill <= 0 or not np.isfinite(stop):
        return None
    if _beyond(item.direction, _level(prep, fill_i, target), fill) is None:
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
        goal = _beyond(item.direction, _level(prep, j, target), fill)
        if _gapped_stop(item.direction, opened, stop):
            return _path(item, fill, stop, "stop", opened, stamp, target)
        stop_hit = _traded_stop(item.direction, high, low, stop)
        target_hit = goal is not None and _traded_target(item.direction, high, low, goal)
        if stop_hit and target_hit:
            return _path(item, fill, stop, "stop", stop, stamp, target)
        if goal is not None and _gapped_target(item.direction, opened, goal):
            return _path(item, fill, stop, target, opened, stamp, target)
        if target_hit:
            return _path(item, fill, stop, target, goal, stamp, target)
        if stop_hit:
            return _path(item, fill, stop, "stop", stop, stamp, target)
        if np.isfinite(closed):
            last_spot = closed
            last_time = stamp
    return _path(item, fill, stop, "last", last_spot, last_time, target)


def random_exhaustions(
    prep: Prepared,
    count: int,
    seed: int = RANDOM_SEED,
    *,
    start: date | None = None,
    end: date | None = None,
) -> list[Exhaustion]:
    """Same count of coin-flip entries that have a confirmed swing stop. Seed 17."""
    if count <= 0:
        return []
    eligible = []
    for i in range(len(prep.close) - 1):
        day = prep.dates[i + 1]
        if start is not None and day < start:
            continue
        if end is not None and day > end:
            continue
        if prep.dates[i] != prep.dates[i + 1]:
            continue
        if prep.times[i] > LAST_CONFIRM or prep.times[i + 1] >= FLAT:
            continue
        eligible.append(i)
    if not eligible:
        return []
    rng = np.random.default_rng(seed)
    found: list[Exhaustion] = []
    guard = 0
    limit = max(count * 40, 1)
    while len(found) < count and guard < limit:
        guard += 1
        i = int(eligible[int(rng.integers(0, len(eligible)))])
        direction = "long" if int(rng.integers(0, 2)) == 0 else "short"
        stop = _swing_stop(prep, i, direction, _session_start(prep, i))
        fill = float(prep.open[i + 1])
        if stop is None or not np.isfinite(fill):
            continue
        if direction == "short" and not stop > fill:
            continue
        if direction == "long" and not stop < fill:
            continue
        found.append(Exhaustion("SPY", direction, i, i, i + 1, float("nan"), i, float(stop)))
    found.sort(key=lambda item: item.fill_i)
    return found


def _scan(prep: Prepared, symbol: str, start: int, end: int, direction: str) -> list[Exhaustion]:
    found: list[Exhaustion] = []
    anchor = None
    level = None
    level_i = None
    hot = None
    for i in range(start, end - 1):
        if anchor is None:
            if _is_anchor(prep, i, direction):
                anchor = i
            continue
        if level is not None and _is_signal(prep, i, direction, level, hot):
            stop = _swing_stop(prep, i, direction, start)
            fill = i + 1
            opened = float(prep.open[fill])
            if (
                stop is not None
                and _clock_ok(prep, i, fill)
                and _stop_beyond(direction, stop, opened)
            ):
                found.append(
                    Exhaustion(symbol, direction, anchor, i, fill, float(level), int(level_i), float(stop))
                )
        if i > anchor:
            level, level_i, hot = _extend(prep, i, direction, level, level_i, hot)
    return found


def _shelf(prep: Prepared, start: int, end: int, direction: str) -> tuple[int | None, float | None, int | None]:
    """Anchor and the extreme through the last bar of the session, including a bar that cannot fill."""
    anchor = None
    level = None
    level_i = None
    for i in range(start, end):
        if anchor is None:
            if _is_anchor(prep, i, direction):
                anchor = i
            continue
        if i > anchor:
            level, level_i, _hot = _extend(prep, i, direction, level, level_i, None)
    return anchor, None if level is None else float(level), level_i


def _is_anchor(prep: Prepared, i: int, direction: str) -> bool:
    return _tagged(prep, i, direction) and _trend(prep, i, direction)


def _tagged(prep: Prepared, i: int, direction: str) -> bool:
    vwap = float(prep.vwap[i])
    std = float(prep.std[i])
    if not _finite(vwap, std) or std <= 0:
        return False
    if direction == "short":
        return float(prep.high[i]) >= vwap + 2.0 * std
    return float(prep.low[i]) <= vwap - 2.0 * std


def _trend(prep: Prepared, i: int, direction: str) -> bool:
    ema9 = float(prep.ema9[i])
    ema20 = float(prep.ema20[i])
    if not _finite(ema9, ema20):
        return False
    if direction == "short":
        return ema9 > ema20
    return ema9 < ema20


def _is_signal(prep: Prepared, i: int, direction: str, level: float, hot: float | None) -> bool:
    if i < 1 or hot is None or not _trend(prep, i, direction) or not _fade(prep, i, direction):
        return False
    closed = float(prep.close[i])
    ema9 = float(prep.ema9[i])
    rsi_now = float(prep.rsi[i])
    rsi_prior = float(prep.rsi[i - 1])
    if not _finite(closed, ema9, rsi_now, rsi_prior, level):
        return False
    if direction == "short":
        return closed < level and closed < ema9 and hot >= RSI_HOT and rsi_now < rsi_prior and rsi_now < hot
    return closed > level and closed > ema9 and hot <= RSI_WASH and rsi_now > rsi_prior and rsi_now > hot


def _fade(prep: Prepared, i: int, direction: str) -> bool:
    if i < FADE_BARS:
        return False
    values = [float(prep.macd_hist[i - k]) for k in range(FADE_BARS, -1, -1)]
    if not _finite(*values):
        return False
    shrinking = all(values[k + 1] < values[k] for k in range(FADE_BARS))
    if direction == "short":
        return values[0] > 0.0 and shrinking
    rising = all(values[k + 1] > values[k] for k in range(FADE_BARS))
    return values[0] < 0.0 and rising


def _extend(prep, i: int, direction: str, level, level_i, hot):
    price = float(prep.low[i] if direction == "short" else prep.high[i])
    if _finite(price) and (level is None or (price < level if direction == "short" else price > level)):
        level = price
        level_i = i
    rsi_now = float(prep.rsi[i])
    if _finite(rsi_now):
        if hot is None:
            hot = rsi_now
        elif direction == "short":
            hot = max(hot, rsi_now)
        else:
            hot = min(hot, rsi_now)
    return level, level_i, hot


def _swing_stop(prep: Prepared, i: int, direction: str, session_start: int) -> float | None:
    last = i - PIVOT
    first = session_start + PIVOT
    if last < first:
        return None
    for p in range(last, first - 1, -1):
        if not _is_pivot(prep, p, direction):
            continue
        if direction == "short":
            return float(prep.high[p]) + STOP_PAD
        return float(prep.low[p]) - STOP_PAD
    return None


def _is_pivot(prep: Prepared, p: int, direction: str) -> bool:
    if p < PIVOT or p + PIVOT >= len(prep.close):
        return False
    if direction == "short":
        center = float(prep.high[p])
        others = [float(prep.high[p + k]) for k in (-2, -1, 1, 2)]
    else:
        center = float(prep.low[p])
        others = [float(prep.low[p + k]) for k in (-2, -1, 1, 2)]
    if not _finite(center, *others):
        return False
    if direction == "short":
        return all(center > other for other in others)
    return all(center < other for other in others)


def _clock_ok(prep: Prepared, signal: int, fill: int) -> bool:
    return prep.dates[fill] == prep.dates[signal] and prep.times[signal] <= LAST_CONFIRM and prep.times[fill] < FLAT


def _stop_beyond(direction: str, stop: float, fill: float) -> bool:
    if not _finite(stop, fill):
        return False
    if direction == "short":
        return stop > fill
    return stop < fill


def _session_start(prep: Prepared, i: int) -> int:
    start = i
    while start > 0 and prep.dates[start - 1] == prep.dates[i]:
        start -= 1
    return start


def _level(prep: Prepared, i: int, name: str) -> float | None:
    value = float(prep.ema20[i] if name == "ema20" else prep.vwap[i])
    if not np.isfinite(value):
        return None
    return value


def _beyond(direction: str, level: float | None, fill: float) -> float | None:
    if level is None or not _finite(level, fill):
        return None
    if direction == "short" and level < fill:
        return float(level)
    if direction == "long" and level > fill:
        return float(level)
    return None


def _gapped_stop(direction: str, opened: float, stop: float) -> bool:
    if not _finite(opened, stop):
        return False
    if direction == "short":
        return opened >= stop
    return opened <= stop


def _gapped_target(direction: str, opened: float, goal: float) -> bool:
    if not _finite(opened, goal):
        return False
    if direction == "short":
        return opened <= goal
    return opened >= goal


def _traded_stop(direction: str, high: float, low: float, stop: float) -> bool:
    if direction == "short":
        return _finite(high, stop) and high >= stop
    return _finite(low, stop) and low <= stop


def _traded_target(direction: str, high: float, low: float, goal: float) -> bool:
    if direction == "short":
        return _finite(low, goal) and low <= goal
    return _finite(high, goal) and high >= goal


def _finite(*values: float) -> bool:
    return all(np.isfinite(value) for value in values)


def _path(item: Exhaustion, fill: float, stop: float, reason: str, spot: float, stamp, target: str) -> dict:
    return {
        "direction": item.direction,
        "variant": target,
        "fill": float(fill),
        "stop": float(stop),
        "reason": reason,
        "exit_spot": float(spot),
        "exit_time": stamp,
        "fill_i": item.fill_i,
        "tag_i": item.tag_i,
        "signal_i": item.signal_i,
    }
