"""The 2026-10-07 SPY 5-minute reclaim, frozen before the score.

Steps, in order, for a long. The short is the mirror.

1. Bearish stack: 9 EMA under the 20 EMA, both lower than 3 bars ago, close under session VWAP,
   and at least two bars in that stack whose high reaches the 9 EMA (within 0.10 ATR) and whose close is back under it.
2. Crack: a green bar that closes above the prior red bar's high and above the 9 and the 20.
   The body variant accepts a close above that red bar's body instead of its high.
3. Pullback: a later bar whose low reaches the 9 EMA and whose close holds at or above it.
4. Trigger: a later green bar that closes above the 9, the 20, and session VWAP.
5. Confirmation: the next bar closes green. The fill is the open after that bar.

Dropping step 2 or step 3 is a named variant. It does not replace this order.
A 9 EMA reclaim with the same confirmation, and no stack, is the feature-study population.
Nothing here places an order.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from datetime import date, time
from typing import Optional

import numpy as np
import pandas as pd

from webull_bot.calendar import next_trading_day
from webull_bot.chart_reads.candles import detect
from webull_bot.chart_reads.vwap_band import (
    DIVIDEND,
    HALF_SPREAD_FLOOR,
    HALF_SPREAD_PCT,
    RATE,
    VOL_CAP,
    VOL_FLOOR,
    metrics_from,
)
from webull_bot.costs import CostModel, buy_fees, buy_price, sell_price, sell_regulatory_fees
from webull_bot.indicators import atr, ema, rsi
from webull_bot.mtf_vwap.detect import rth, session_vwap
from webull_bot.options.fees import CONTRACT_MULTIPLIER, option_leg_fees
from webull_bot.options.pricing import listed_strike, option_price

NY = "America/New_York"
FLAT = time(15, 30)
LAST_CONFIRM = time(15, 20)
SLOPE_BARS = 3
TOUCH_ATR = 0.10
STOP_PAD = 0.01
RISK_FRACTION = 0.01
MIN_REJECTIONS = 2
STRETCH_SD = 2.0
VOLUME_EXPAND = 1.5
OR_BARS = 6
PIVOT = 2
RSI_WASH = 30.0
RSI_RECOVER = 45.0
RSI_HOT = 70.0
RSI_FAIL = 55.0
FEATURE_MIN = 30
FEATURE_Q = 0.10
HOLDOUT_START = date(2022, 1, 1)
TRAIN_END = date(2021, 12, 31)
CHART_DAY = date(2026, 10, 7)
RANDOM_SEED = 17

VARIANTS = (
    "strict",
    "body",
    "no_crack",
    "no_pullback",
    "no_crack_no_pullback",
    "reclaim9",
)
FEATURES = (
    "macd_hist_turn",
    "macd_cross_zero",
    "rsi_divergence",
    "rsi_recover",
    "trendline_break",
    "volume_fade",
    "volume_expand",
    "vwap_stretch",
    "higher_low",
    "below_opening_range",
    "above_opening_range",
    "morning",
    "midday",
    "afternoon",
    "gap_against",
    "gap_with",
    "vix_rising",
    "qqq_reclaim",
    "prior_day_against",
    "hammer_at_low",
    "engulfing_at_low",
    "star_at_low",
)


def frozen_rules() -> dict:
    """Written down before the result is scored. The score does not edit this."""
    return {
        "name": "spy_5m_reclaim_2026_10_07",
        "clock": (
            "5-minute regular-hours bars, left-labeled. Confirmation must be at or before 15:20 ET "
            "so the fill is before 15:30. Still open at 15:30 is sold at that bar's open."
        ),
        "stack": (
            "Long context: 9 EMA below the 20 EMA, both lower than 3 bars ago, and the close below session VWAP. "
            "At least two such bars, earlier in the same session, tag the 9 EMA: the high reaches it within 0.10 ATR "
            "and the close finishes back under it. Short is the mirror."
        ),
        "crack": (
            "A green bar closes above the prior red bar's high and above the 9 EMA and the 20 EMA. "
            "The body variant closes above that red bar's body (the higher of its open and close) instead of its high. "
            "The crack, the pullback, and the trigger are three different bars, in that order."
        ),
        "pullback": "A bar after the crack whose low reaches the 9 EMA within 0.10 ATR and whose close holds on the near side of it.",
        "trigger": "A later green bar closes above the 9 EMA, the 20 EMA, and session VWAP. Short is a red bar closing under all three.",
        "confirmation": "The next 5-minute bar closes the same color. The fill is the following open. One position at a time.",
        "variants": {
            "strict": "Steps 1 through 5, crack through the prior high.",
            "body": "The same order, with the crack measured off the prior body.",
            "no_crack": "Drop step 2. Rejections, then a pullback, then the trigger and confirmation.",
            "no_pullback": "Drop step 3. Rejections, then a crack. The crack may be the trigger bar.",
            "no_crack_no_pullback": "Drop steps 2 and 3. Rejections, then the trigger and confirmation.",
            "reclaim9": (
                "Not the five-step setup. The prior close is on the far side of the 9 EMA and this bar closes back across it, "
                "in the trade color, then the next bar confirms. This is the feature-study population."
            ),
        },
        "stop": (
            "One cent beyond the trigger bar: under its low for a long, over its high for a short. "
            "A later close back across the 9 EMA exits at that close. If that bar also trades through the price stop, the stop fills."
        ),
        "ema200": (
            "The 5-minute 200 EMA is a profit target when it is beyond the fill. "
            "Shares sell half when that bar's high or low tags it, and the rest gets a stop at the raw fill. "
            "The break-even stop starts on the next bar. One option contract cannot be split, so the 0 DTE book sells the contract there. "
            "A 200 EMA that is not beyond the fill never scales the trade out."
        ),
        "premium": "0 DTE only. Exit when the model bid is 50% or 100% above the entry ask. A gap through the target fills at the open bid. Otherwise the limit.",
        "flat": "15:30 ET open. No overnight hold.",
        "shares": "Cash book is long only. Size risks 1% of equity to the trigger stop and cannot spend more settled cash than is on hand.",
        "options": "One at-the-money contract. Calls for longs, puts for shorts. Black-Scholes, prior-session VIX1D or else prior VIX. Both directions.",
        "feature_outcome": (
            "Each feature is scored on non-overlapping structure exits, both directions, as an after-cost R-multiple of one share. "
            "The family is the 22 features on the 9 EMA reclaim population. "
            "A feature survives only when the holdout q is at or under 0.10, train and holdout each have at least 30 trades with the feature on, "
            "the feature's mean R is above the base mean in both windows, and that mean is above zero in both windows. "
            "The best combo is the AND of those survivors. Its holdout dollar score uses the same window that selected it."
        ),
        "features": list(FEATURES),
        "chart_day": (
            "2026-10-07 is the illustration. The first bar that meets a step is the one that is marked. "
            "The rule is not moved onto a later print. That day is not in the Dukascopy score."
        ),
        "not_live": "Not a live strategy. Nothing is added to the optional or selected lists.",
    }


@dataclass(frozen=True)
class Setup:
    symbol: str
    variant: str
    direction: str
    trigger_i: int
    confirm_i: int
    fill_i: int
    crack_i: int
    pull_i: int
    stop: float
    features: tuple[str, ...] = ()

    @property
    def trigger_time(self) -> pd.Timestamp:
        raise RuntimeError("use the prepared index")


@dataclass
class Prepared:
    index: pd.DatetimeIndex
    open: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray
    volume: np.ndarray
    ema9: np.ndarray
    ema20: np.ndarray
    ema200: np.ndarray
    atr: np.ndarray
    vwap: np.ndarray
    std: np.ndarray
    macd_line: np.ndarray
    macd_signal: np.ndarray
    macd_hist: np.ndarray
    rsi: np.ndarray
    hammer: np.ndarray
    engulf_bull: np.ndarray
    morning: np.ndarray
    shooting: np.ndarray
    engulf_bear: np.ndarray
    evening: np.ndarray
    dates: list[date]
    times: list[time]


def _finite(*values: float) -> bool:
    return all(np.isfinite(value) for value in values)


def _macd(close: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
    line = ema(close, 12) - ema(close, 26)
    signal = ema(line, 9)
    return line, signal, line - signal


def prepare(frame: pd.DataFrame) -> Prepared:
    """Causal indicators. Bar i does not use a later close."""
    bars = rth(frame)
    if bars.empty:
        empty = np.array([], dtype=float)
        return Prepared(
            index=pd.DatetimeIndex([], tz=NY),
            open=empty, high=empty, low=empty, close=empty, volume=empty,
            ema9=empty, ema20=empty, ema200=empty, atr=empty, vwap=empty, std=empty,
            macd_line=empty, macd_signal=empty, macd_hist=empty, rsi=empty,
            hammer=empty.astype(bool), engulf_bull=empty.astype(bool), morning=empty.astype(bool),
            shooting=empty.astype(bool), engulf_bear=empty.astype(bool), evening=empty.astype(bool),
            dates=[], times=[],
        )
    close = bars["close"].astype(float)
    volume = bars["volume"].astype(float) if "volume" in bars.columns else pd.Series(np.nan, index=bars.index)
    bands = session_vwap(bars)
    std = (bands["upper"] - bands["vwap"]).reindex(bars.index)
    line, signal, hist = _macd(close)
    shapes = detect(bars)
    index = pd.DatetimeIndex(bars.index)

    def _bool(name: str) -> np.ndarray:
        if name not in shapes.columns:
            return np.zeros(len(bars), dtype=bool)
        return shapes[name].fillna(False).to_numpy(dtype=bool)

    return Prepared(
        index=index,
        open=bars["open"].to_numpy(dtype=float),
        high=bars["high"].to_numpy(dtype=float),
        low=bars["low"].to_numpy(dtype=float),
        close=close.to_numpy(dtype=float),
        volume=volume.to_numpy(dtype=float),
        ema9=ema(close, 9).to_numpy(dtype=float),
        ema20=ema(close, 20).to_numpy(dtype=float),
        ema200=ema(close, 200).to_numpy(dtype=float),
        atr=atr(bars, 14).to_numpy(dtype=float),
        vwap=bands["vwap"].reindex(bars.index).to_numpy(dtype=float),
        std=std.to_numpy(dtype=float),
        macd_line=line.to_numpy(dtype=float),
        macd_signal=signal.to_numpy(dtype=float),
        macd_hist=hist.to_numpy(dtype=float),
        rsi=rsi(close, 14).to_numpy(dtype=float),
        hammer=_bool("hammer"),
        engulf_bull=_bool("bullish_engulfing"),
        morning=_bool("morning_star"),
        shooting=_bool("shooting_star"),
        engulf_bear=_bool("bearish_engulfing"),
        evening=_bool("evening_star"),
        dates=[stamp.date() for stamp in index],
        times=[stamp.time() for stamp in index],
    )


def _bear(prep: Prepared, i: int) -> bool:
    if i < SLOPE_BARS:
        return False
    return _finite(prep.ema9[i], prep.ema20[i], prep.ema9[i - SLOPE_BARS], prep.ema20[i - SLOPE_BARS], prep.close[i], prep.vwap[i]) and (
        prep.ema9[i] < prep.ema20[i]
        and prep.ema9[i] < prep.ema9[i - SLOPE_BARS]
        and prep.ema20[i] < prep.ema20[i - SLOPE_BARS]
        and prep.close[i] < prep.vwap[i]
    )


def _bull(prep: Prepared, i: int) -> bool:
    if i < SLOPE_BARS:
        return False
    return _finite(prep.ema9[i], prep.ema20[i], prep.ema9[i - SLOPE_BARS], prep.ema20[i - SLOPE_BARS], prep.close[i], prep.vwap[i]) and (
        prep.ema9[i] > prep.ema20[i]
        and prep.ema9[i] > prep.ema9[i - SLOPE_BARS]
        and prep.ema20[i] > prep.ema20[i - SLOPE_BARS]
        and prep.close[i] > prep.vwap[i]
    )


def _reject_long(prep: Prepared, i: int) -> bool:
    width = prep.atr[i]
    return _bear(prep, i) and _finite(width, prep.high[i], prep.close[i], prep.ema9[i]) and width > 0 and (
        prep.high[i] >= prep.ema9[i] - TOUCH_ATR * width and prep.close[i] < prep.ema9[i]
    )


def _reject_short(prep: Prepared, i: int) -> bool:
    width = prep.atr[i]
    return _bull(prep, i) and _finite(width, prep.low[i], prep.close[i], prep.ema9[i]) and width > 0 and (
        prep.low[i] <= prep.ema9[i] + TOUCH_ATR * width and prep.close[i] > prep.ema9[i]
    )


def _crack_long(prep: Prepared, i: int, start: int, *, body: bool) -> bool:
    if i <= start:
        return False
    prev = i - 1
    if not _finite(prep.open[i], prep.close[i], prep.open[prev], prep.close[prev], prep.high[prev], prep.ema9[i], prep.ema20[i]):
        return False
    if not (prep.close[i] > prep.open[i] and prep.close[prev] < prep.open[prev]):
        return False
    if not (prep.close[i] > prep.ema9[i] and prep.close[i] > prep.ema20[i]):
        return False
    level = max(prep.open[prev], prep.close[prev]) if body else prep.high[prev]
    return prep.close[i] > level


def _crack_short(prep: Prepared, i: int, start: int, *, body: bool) -> bool:
    if i <= start:
        return False
    prev = i - 1
    if not _finite(prep.open[i], prep.close[i], prep.open[prev], prep.close[prev], prep.low[prev], prep.ema9[i], prep.ema20[i]):
        return False
    if not (prep.close[i] < prep.open[i] and prep.close[prev] > prep.open[prev]):
        return False
    if not (prep.close[i] < prep.ema9[i] and prep.close[i] < prep.ema20[i]):
        return False
    level = min(prep.open[prev], prep.close[prev]) if body else prep.low[prev]
    return prep.close[i] < level


def _pull_long(prep: Prepared, i: int) -> bool:
    width = prep.atr[i]
    return _finite(width, prep.low[i], prep.close[i], prep.ema9[i]) and width > 0 and (
        prep.low[i] <= prep.ema9[i] + TOUCH_ATR * width and prep.close[i] >= prep.ema9[i]
    )


def _pull_short(prep: Prepared, i: int) -> bool:
    width = prep.atr[i]
    return _finite(width, prep.high[i], prep.close[i], prep.ema9[i]) and width > 0 and (
        prep.high[i] >= prep.ema9[i] - TOUCH_ATR * width and prep.close[i] <= prep.ema9[i]
    )


def _trigger_long(prep: Prepared, i: int) -> bool:
    return _finite(prep.open[i], prep.close[i], prep.ema9[i], prep.ema20[i], prep.vwap[i]) and (
        prep.close[i] > prep.open[i]
        and prep.close[i] > prep.ema9[i]
        and prep.close[i] > prep.ema20[i]
        and prep.close[i] > prep.vwap[i]
    )


def _trigger_short(prep: Prepared, i: int) -> bool:
    return _finite(prep.open[i], prep.close[i], prep.ema9[i], prep.ema20[i], prep.vwap[i]) and (
        prep.close[i] < prep.open[i]
        and prep.close[i] < prep.ema9[i]
        and prep.close[i] < prep.ema20[i]
        and prep.close[i] < prep.vwap[i]
    )


def _reclaim_long(prep: Prepared, i: int, start: int) -> bool:
    if i <= start:
        return False
    prev = i - 1
    return _finite(prep.close[i], prep.open[i], prep.ema9[i], prep.close[prev], prep.ema9[prev]) and (
        prep.close[prev] < prep.ema9[prev] and prep.close[i] > prep.ema9[i] and prep.close[i] > prep.open[i]
    )


def _reclaim_short(prep: Prepared, i: int, start: int) -> bool:
    if i <= start:
        return False
    prev = i - 1
    return _finite(prep.close[i], prep.open[i], prep.ema9[i], prep.close[prev], prep.ema9[prev]) and (
        prep.close[prev] > prep.ema9[prev] and prep.close[i] < prep.ema9[i] and prep.close[i] < prep.open[i]
    )


def _clock_ok(prep: Prepared, i: int) -> bool:
    return prep.times[i + 1] <= LAST_CONFIRM and prep.times[i + 2] < FLAT


def _next_green(prep: Prepared, i: int) -> bool:
    return _finite(prep.close[i + 1], prep.open[i + 1]) and prep.close[i + 1] > prep.open[i + 1]


def _next_red(prep: Prepared, i: int) -> bool:
    return _finite(prep.close[i + 1], prep.open[i + 1]) and prep.close[i + 1] < prep.open[i + 1]


def _emit(found: list[Setup], symbol: str, variant: str, direction: str, t: int, crack: int, pull: int, prep: Prepared) -> None:
    stop = float(prep.low[t] - STOP_PAD) if direction == "long" else float(prep.high[t] + STOP_PAD)
    if not np.isfinite(stop):
        return
    found.append(Setup(symbol, variant, direction, t, t + 1, t + 2, crack, pull, stop))


def find_setups(prep: Prepared, symbol: str) -> list[Setup]:
    """Every variant that fires. Books pick one variant."""
    count = len(prep.close)
    if count < 4:
        return []
    found: list[Setup] = []
    start = 0
    while start < count:
        end = start + 1
        while end < count and prep.dates[end] == prep.dates[start]:
            end += 1
        if end - start >= 4:
            _scan_session(prep, start, end, symbol, found)
        start = end
    return found


def _scan_session(prep: Prepared, start: int, end: int, symbol: str, found: list[Setup]) -> None:
    rejects_long = 0
    rejects_short = 0
    crack_long = -1
    crack_short = -1
    body_long = -1
    body_short = -1
    pull_long = -1
    pull_short = -1
    body_pull_long = -1
    body_pull_short = -1
    any_pull_long = -1
    any_pull_short = -1
    used_long = 0
    used_short = 0
    for t in range(start, end - 2):
        spent_crack_long = False
        spent_body_long = False
        spent_pull_long = False
        spent_crack_short = False
        spent_body_short = False
        spent_pull_short = False
        if _clock_ok(prep, t) and _trigger_long(prep, t) and _next_green(prep, t):
            # Snapshot first. Emitting a variant uses up the crack or the pullback,
            # so the next signal has to rebuild that step instead of repeating on every later green bar.
            had_crack = crack_long
            had_pull = pull_long
            had_body = body_long
            had_body_pull = body_pull_long
            had_any = any_pull_long
            crack_now = _crack_long(prep, t, start, body=False) and rejects_long >= MIN_REJECTIONS
            if had_crack >= start and had_pull > had_crack:
                _emit(found, symbol, "strict", "long", t, had_crack, had_pull, prep)
                crack_long = -1
                pull_long = -1
                spent_crack_long = True
            if had_body >= start and had_body_pull > had_body:
                _emit(found, symbol, "body", "long", t, had_body, had_body_pull, prep)
                body_long = -1
                body_pull_long = -1
                spent_body_long = True
            if had_crack >= start or crack_now:
                crack_at = had_crack if had_crack >= start else t
                _emit(found, symbol, "no_pullback", "long", t, crack_at, -1, prep)
                crack_long = -1
                pull_long = -1
                spent_crack_long = True
            if had_any >= start:
                _emit(found, symbol, "no_crack", "long", t, -1, had_any, prep)
                any_pull_long = -1
                spent_pull_long = True
            if rejects_long >= MIN_REJECTIONS and rejects_long > used_long:
                _emit(found, symbol, "no_crack_no_pullback", "long", t, -1, -1, prep)
                used_long = rejects_long
        if _clock_ok(prep, t) and _trigger_short(prep, t) and _next_red(prep, t):
            had_crack = crack_short
            had_pull = pull_short
            had_body = body_short
            had_body_pull = body_pull_short
            had_any = any_pull_short
            crack_now = _crack_short(prep, t, start, body=False) and rejects_short >= MIN_REJECTIONS
            if had_crack >= start and had_pull > had_crack:
                _emit(found, symbol, "strict", "short", t, had_crack, had_pull, prep)
                crack_short = -1
                pull_short = -1
                spent_crack_short = True
            if had_body >= start and had_body_pull > had_body:
                _emit(found, symbol, "body", "short", t, had_body, had_body_pull, prep)
                body_short = -1
                body_pull_short = -1
                spent_body_short = True
            if had_crack >= start or crack_now:
                crack_at = had_crack if had_crack >= start else t
                _emit(found, symbol, "no_pullback", "short", t, crack_at, -1, prep)
                crack_short = -1
                pull_short = -1
                spent_crack_short = True
            if had_any >= start:
                _emit(found, symbol, "no_crack", "short", t, -1, had_any, prep)
                any_pull_short = -1
                spent_pull_short = True
            if rejects_short >= MIN_REJECTIONS and rejects_short > used_short:
                _emit(found, symbol, "no_crack_no_pullback", "short", t, -1, -1, prep)
                used_short = rejects_short
        if _clock_ok(prep, t) and _reclaim_long(prep, t, start) and _next_green(prep, t):
            _emit(found, symbol, "reclaim9", "long", t, -1, -1, prep)
        if _clock_ok(prep, t) and _reclaim_short(prep, t, start) and _next_red(prep, t):
            _emit(found, symbol, "reclaim9", "short", t, -1, -1, prep)
        if _pull_long(prep, t):
            if crack_long >= start and t > crack_long:
                pull_long = t
            if body_long >= start and t > body_long:
                body_pull_long = t
            if rejects_long >= MIN_REJECTIONS and not spent_pull_long:
                any_pull_long = t
        if _pull_short(prep, t):
            if crack_short >= start and t > crack_short:
                pull_short = t
            if body_short >= start and t > body_short:
                body_pull_short = t
            if rejects_short >= MIN_REJECTIONS and not spent_pull_short:
                any_pull_short = t
        if not spent_crack_long and _crack_long(prep, t, start, body=False) and rejects_long >= MIN_REJECTIONS:
            crack_long = t
            pull_long = -1
        if not spent_crack_short and _crack_short(prep, t, start, body=False) and rejects_short >= MIN_REJECTIONS:
            crack_short = t
            pull_short = -1
        if not spent_body_long and _crack_long(prep, t, start, body=True) and rejects_long >= MIN_REJECTIONS:
            body_long = t
            body_pull_long = -1
        if not spent_body_short and _crack_short(prep, t, start, body=True) and rejects_short >= MIN_REJECTIONS:
            body_short = t
            body_pull_short = -1
        if _reject_long(prep, t):
            rejects_long += 1
        if _reject_short(prep, t):
            rejects_short += 1


def long_roles(prep: Prepared, i: int, start: int) -> list[str]:
    """Step labels for the chart. A bar can wear more than one."""
    roles: list[str] = []
    if _reject_long(prep, i):
        roles.append("rejection")
    if _crack_long(prep, i, start, body=False):
        roles.append("crack")
    elif _crack_long(prep, i, start, body=True):
        roles.append("body_crack")
    if _pull_long(prep, i):
        roles.append("pullback")
    if _trigger_long(prep, i):
        roles.append("trigger")
    if i > start and _trigger_long(prep, i - 1) and _next_green(prep, i - 1):
        roles.append("confirmation")
    return roles


def _session_start(prep: Prepared, i: int) -> int:
    start = i
    while start > 0 and prep.dates[start - 1] == prep.dates[i]:
        start -= 1
    return start


def _pivot_indexes(values: np.ndarray, start: int, stop: int, *, kind: str) -> list[int]:
    """Pivots confirmed by ``stop`` inclusive. ``stop`` is the trigger bar."""
    found = []
    for k in range(start + PIVOT, stop - PIVOT + 1):
        window = values[k - PIVOT : k + PIVOT + 1]
        if not np.isfinite(window).all():
            continue
        center = values[k]
        if kind == "low" and center == window.min() and np.sum(window == center) == 1:
            found.append(k)
        if kind == "high" and center == window.max() and np.sum(window == center) == 1:
            found.append(k)
    return found


def _slope(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    x = np.arange(len(values), dtype=float)
    y = np.asarray(values, dtype=float)
    return float(np.polyfit(x, y, 1)[0])


def feature_names(prep: Prepared, i: int, direction: str, extra: dict | None = None) -> tuple[str, ...]:
    """Flags known at the trigger close. The fill bar is not read."""
    side = extra or {}
    start = _session_start(prep, i)
    names: list[str] = []
    hist = prep.macd_hist
    line = prep.macd_line
    signal = prep.macd_signal
    if i > 0 and _finite(hist[i], hist[i - 1]):
        if direction == "long" and hist[i] > hist[i - 1] and hist[i] < 0:
            names.append("macd_hist_turn")
        if direction == "short" and hist[i] < hist[i - 1] and hist[i] > 0:
            names.append("macd_hist_turn")
    if i > 0 and _finite(line[i], line[i - 1], signal[i], signal[i - 1]):
        cross_up = line[i - 1] <= signal[i - 1] and line[i] > signal[i] and line[i] < 0
        cross_down = line[i - 1] >= signal[i - 1] and line[i] < signal[i] and line[i] > 0
        if (direction == "long" and cross_up) or (direction == "short" and cross_down):
            names.append("macd_cross_zero")
    pivots = _pivot_indexes(prep.low if direction == "long" else prep.high, start, i, kind="low" if direction == "long" else "high")
    if len(pivots) >= 2 and _finite(prep.rsi[pivots[-1]], prep.rsi[pivots[-2]]):
        earlier, later = pivots[-2], pivots[-1]
        if direction == "long" and prep.low[later] < prep.low[earlier] and prep.rsi[later] > prep.rsi[earlier]:
            names.append("rsi_divergence")
        if direction == "short" and prep.high[later] > prep.high[earlier] and prep.rsi[later] < prep.rsi[earlier]:
            names.append("rsi_divergence")
    window_rsi = prep.rsi[start : i + 1]
    finite_rsi = window_rsi[np.isfinite(window_rsi)]
    if len(finite_rsi) and np.isfinite(prep.rsi[i]):
        if direction == "long" and float(finite_rsi.min()) < RSI_WASH and prep.rsi[i] > RSI_RECOVER:
            names.append("rsi_recover")
        if direction == "short" and float(finite_rsi.max()) > RSI_HOT and prep.rsi[i] < RSI_FAIL:
            names.append("rsi_recover")
    if direction == "long":
        highs = _pivot_indexes(prep.high, start, i, kind="high")
        if len(highs) >= 2:
            a, b = highs[-2], highs[-1]
            if prep.high[b] < prep.high[a] and b != a:
                level = prep.high[a] + (prep.high[b] - prep.high[a]) / (b - a) * (i - a)
                if _finite(prep.close[i], level) and prep.close[i] > level:
                    names.append("trendline_break")
    else:
        lows = _pivot_indexes(prep.low, start, i, kind="low")
        if len(lows) >= 2:
            a, b = lows[-2], lows[-1]
            if prep.low[b] > prep.low[a] and b != a:
                level = prep.low[a] + (prep.low[b] - prep.low[a]) / (b - a) * (i - a)
                if _finite(prep.close[i], level) and prep.close[i] < level:
                    names.append("trendline_break")
    left = max(start, i - 6)
    if direction == "long":
        vols = [float(prep.volume[k]) for k in range(left, i) if prep.close[k] < prep.open[k] and np.isfinite(prep.volume[k])]
    else:
        vols = [float(prep.volume[k]) for k in range(left, i) if prep.close[k] > prep.open[k] and np.isfinite(prep.volume[k])]
    if len(vols) >= 3 and _slope(vols) < 0:
        names.append("volume_fade")
    if i >= 20 and np.isfinite(prep.volume[i]):
        base = float(np.nanmean(prep.volume[i - 20 : i]))
        if base > 0 and prep.volume[i] >= VOLUME_EXPAND * base:
            names.append("volume_expand")
    stretched = False
    for k in range(start, i + 1):
        if not _finite(prep.std[k], prep.vwap[k]):
            continue
        if direction == "long" and prep.low[k] <= prep.vwap[k] - STRETCH_SD * prep.std[k]:
            stretched = True
            break
        if direction == "short" and prep.high[k] >= prep.vwap[k] + STRETCH_SD * prep.std[k]:
            stretched = True
            break
    if stretched:
        names.append("vwap_stretch")
    if i - start >= 6:
        earlier = prep.low[start : i - 5] if direction == "long" else prep.high[start : i - 5]
        recent = prep.low[i - 5 : i + 1] if direction == "long" else prep.high[i - 5 : i + 1]
        if len(earlier) and np.isfinite(earlier).any() and np.isfinite(recent).any():
            if direction == "long" and np.nanmin(recent) > np.nanmin(earlier):
                names.append("higher_low")
            if direction == "short" and np.nanmax(recent) < np.nanmax(earlier):
                names.append("higher_low")
    if i >= start + OR_BARS - 1:
        or_high = float(np.nanmax(prep.high[start : start + OR_BARS]))
        or_low = float(np.nanmin(prep.low[start : start + OR_BARS]))
        if prep.close[i] < or_low:
            names.append("below_opening_range")
        if prep.close[i] > or_high:
            names.append("above_opening_range")
    clock = prep.times[i]
    if clock < time(11, 0):
        names.append("morning")
    elif clock < time(14, 0):
        names.append("midday")
    else:
        names.append("afternoon")
    if start > 0:
        gap = float(prep.open[start] - prep.close[start - 1])
        if direction == "long" and gap < 0:
            names.append("gap_against")
        if direction == "long" and gap > 0:
            names.append("gap_with")
        if direction == "short" and gap > 0:
            names.append("gap_against")
        if direction == "short" and gap < 0:
            names.append("gap_with")
        prev = start - 1
        while prev > 0 and prep.dates[prev - 1] == prep.dates[start - 1]:
            prev -= 1
        if _finite(prep.open[prev], prep.close[start - 1]):
            down = prep.close[start - 1] < prep.open[prev]
            up = prep.close[start - 1] > prep.open[prev]
            if (direction == "long" and down) or (direction == "short" and up):
                names.append("prior_day_against")
    day = prep.dates[i]
    vix = side.get("vix_rising", {})
    if vix.get(day):
        names.append("vix_rising")
    qqq = side.get("qqq_long" if direction == "long" else "qqq_short", {})
    if qqq.get(prep.index[i]):
        names.append("qqq_reclaim")
    low_slice = prep.low[start : i + 1] if direction == "long" else prep.high[start : i + 1]
    if len(low_slice) and np.isfinite(low_slice).any():
        extreme = start + int(np.nanargmin(low_slice) if direction == "long" else np.nanargmax(low_slice))
        last = min(i, extreme + 2)
        if direction == "long":
            if any(bool(prep.hammer[k]) for k in range(extreme, last + 1)):
                names.append("hammer_at_low")
            if any(bool(prep.engulf_bull[k]) for k in range(extreme, last + 1)):
                names.append("engulfing_at_low")
            if any(bool(prep.morning[k]) for k in range(extreme, last + 1)):
                names.append("star_at_low")
        else:
            if any(bool(prep.shooting[k]) for k in range(extreme, last + 1)):
                names.append("hammer_at_low")
            if any(bool(prep.engulf_bear[k]) for k in range(extreme, last + 1)):
                names.append("engulfing_at_low")
            if any(bool(prep.evening[k]) for k in range(extreme, last + 1)):
                names.append("star_at_low")
    return tuple(names)


def attach_features(prep: Prepared, setups: list[Setup], extra: dict | None = None) -> list[Setup]:
    marked = []
    for setup in setups:
        marked.append(replace(setup, features=feature_names(prep, setup.trigger_i, setup.direction, extra)))
    return marked


def _session_end(prep: Prepared, i: int) -> int:
    end = i + 1
    while end < len(prep.dates) and prep.dates[end] == prep.dates[i]:
        end += 1
    return end


def walk(prep: Prepared, setup: Setup, mode: str, iv: float | None = None, *, split_half: bool = False) -> dict | None:
    """Underlying path from the fill. Premium modes need ``iv`` and exit the whole contract."""
    fill_i = setup.fill_i
    if fill_i >= len(prep.close):
        return None
    fill = float(prep.open[fill_i])
    stop = float(setup.stop)
    if fill <= 0 or not np.isfinite(stop):
        return None
    if setup.direction == "long" and not stop < fill:
        return None
    if setup.direction == "short" and not stop > fill:
        return None
    right = "call" if setup.direction == "long" else "put"
    strike = listed_strike(fill, fill) if mode.startswith("prem") else None
    entry_ask = None
    if mode.startswith("prem"):
        if iv is None or strike is None:
            return None
        entry_mid = _option_mid(right, fill, strike, prep.index[fill_i], iv)
        entry_ask = entry_mid + _half_spread(entry_mid)
        if entry_ask <= 0:
            return None
    target_mult = 1.5 if mode == "prem50" else 2.0 if mode == "prem100" else None
    scaled = False
    scale_spot = None
    scale_time = None
    active = stop
    end = _session_end(prep, fill_i)
    last_spot = fill
    last_time = prep.index[fill_i]
    for j in range(fill_i, end):
        opened = float(prep.open[j])
        high = float(prep.high[j])
        low = float(prep.low[j])
        closed = float(prep.close[j])
        stamp = prep.index[j]
        level = float(prep.ema9[j])
        if prep.times[j] >= FLAT:
            return _path(setup, fill, "flat", opened, stamp, scaled, scale_spot, scale_time, None)
        if setup.direction == "long" and (opened <= active or low <= active):
            price = opened if opened <= active else active
            return _path(setup, fill, "stop", price, stamp, scaled, scale_spot, scale_time, None)
        if setup.direction == "short" and (opened >= active or high >= active):
            price = opened if opened >= active else active
            return _path(setup, fill, "stop", price, stamp, scaled, scale_spot, scale_time, None)
        if mode.startswith("prem") and entry_ask is not None and strike is not None and iv is not None:
            mult = float(target_mult)
            open_bid = _bid(right, opened, strike, stamp, iv)
            extreme = high if setup.direction == "long" else low
            extreme_bid = _bid(right, extreme, strike, stamp, iv)
            if open_bid >= mult * entry_ask:
                return _path(setup, fill, mode, opened, stamp, False, None, None, open_bid)
            if extreme_bid >= mult * entry_ask:
                return _path(setup, fill, mode, extreme, stamp, False, None, None, mult * entry_ask)
        if mode == "ema200" and not scaled:
            ema_level = float(prep.ema200[j])
            tagged = False
            tag_price = None
            if setup.direction == "long" and _finite(ema_level) and ema_level > fill and (opened >= ema_level or high >= ema_level):
                tag_price = opened if opened >= ema_level else ema_level
                tagged = True
            if setup.direction == "short" and _finite(ema_level) and ema_level < fill and (opened <= ema_level or low <= ema_level):
                tag_price = opened if opened <= ema_level else ema_level
                tagged = True
            if tagged and tag_price is not None:
                if not split_half:
                    return _path(setup, fill, "ema200", tag_price, stamp, False, None, None, None)
                scale_spot = tag_price
                scale_time = stamp
                scaled = True
                active = fill
        if _finite(level):
            if setup.direction == "long" and closed < level:
                return _path(setup, fill, "ema", closed, stamp, scaled, scale_spot, scale_time, None)
            if setup.direction == "short" and closed > level:
                return _path(setup, fill, "ema", closed, stamp, scaled, scale_spot, scale_time, None)
        last_spot = closed
        last_time = stamp
    return _path(setup, fill, "last", last_spot, last_time, scaled, scale_spot, scale_time, None)


def _path(setup, fill, reason, spot, stamp, scaled, scale_spot, scale_time, premium) -> dict:
    return {
        "direction": setup.direction,
        "fill": float(fill),
        "stop": float(setup.stop),
        "reason": reason,
        "exit_spot": float(spot),
        "exit_time": stamp,
        "scaled": bool(scaled),
        "scale_spot": None if scale_spot is None else float(scale_spot),
        "scale_time": scale_time,
        "premium": None if premium is None else float(premium),
        "trigger_i": setup.trigger_i,
        "fill_i": setup.fill_i,
        "features": setup.features,
        "variant": setup.variant,
    }


def _half_spread(mid: float) -> float:
    return max(HALF_SPREAD_FLOOR, HALF_SPREAD_PCT * max(mid, 0.0))


def _years(when: pd.Timestamp) -> float:
    clock = pd.Timestamp(when)
    if clock.tzinfo is None:
        clock = clock.tz_localize(NY)
    else:
        clock = clock.tz_convert(NY)
    expiry = clock.normalize() + pd.Timedelta(hours=16)
    minutes = max(1.0, (expiry - clock).total_seconds() / 60.0)
    return minutes / (365.0 * 24.0 * 60.0)


def _option_mid(right: str, spot: float, strike: float, when: pd.Timestamp, iv: float) -> float:
    if spot <= 0 or strike <= 0 or iv <= 0:
        return 0.0
    return float(option_price(right, spot, strike, _years(when), iv, RATE, DIVIDEND))


def _bid(right: str, spot: float, strike: float, when: pd.Timestamp, iv: float) -> float:
    mid = _option_mid(right, spot, strike, when, iv)
    return max(0.0, mid - _half_spread(mid))


def _iv_on(day: date, iv_points: dict) -> Optional[float]:
    point = iv_points.get(day)
    if point is None:
        return None
    raw = float(point[0])
    if not np.isfinite(raw) or raw <= 0:
        return None
    return min(VOL_CAP, max(VOL_FLOOR, raw / 100.0))


def underlying_r(path: dict, costs: CostModel | None = None) -> float | None:
    """After-cost R of one share. Half the shares leave at the 200 EMA when that scale happened."""
    model = costs or CostModel()
    fill = float(path["fill"])
    distance = abs(fill - float(path["stop"]))
    if distance <= 0 or fill <= 0:
        return None
    pnl = _one_share_pnl(path, model)
    if pnl is None:
        return None
    return pnl / distance


def _one_share_pnl(path: dict, costs: CostModel) -> float | None:
    fill = float(path["fill"])
    direction = path["direction"]
    legs = []
    if path["scaled"] and path["scale_spot"] is not None:
        legs.append((0.5, float(path["scale_spot"])))
        legs.append((0.5, float(path["exit_spot"])))
    else:
        legs.append((1.0, float(path["exit_spot"])))
    if direction == "long":
        entry = buy_price(fill, costs)
        debit = entry + buy_fees(costs)
        credit = 0.0
        for fraction, raw in legs:
            if raw <= 0:
                return None
            px = sell_price(raw, costs)
            credit += fraction * px - sell_regulatory_fees(px, fraction, costs)
        return credit - debit
    entry = sell_price(fill, costs)
    credit = entry - sell_regulatory_fees(entry, 1.0, costs)
    debit = buy_fees(costs)
    for fraction, raw in legs:
        if raw <= 0:
            return None
        debit += fraction * buy_price(raw, costs)
    return credit - debit


def r_records(prep: Prepared, setups: list[Setup], *, start: date | None = None, end: date | None = None) -> list[dict]:
    """Non-overlapping structure R, both directions. This is the feature sample."""
    chosen = [
        item for item in setups
        if (start is None or prep.dates[item.fill_i] >= start) and (end is None or prep.dates[item.fill_i] <= end)
    ]
    chosen.sort(key=lambda item: item.fill_i)
    busy = None
    rows = []
    for setup in chosen:
        fill_time = prep.index[setup.fill_i]
        if busy is not None and fill_time <= busy:
            continue
        path = walk(prep, setup, "structure")
        if path is None:
            continue
        multiple = underlying_r(path)
        if multiple is None or not np.isfinite(multiple):
            continue
        rows.append({"r": float(multiple), "features": set(setup.features), "setup": setup, "path": path})
        busy = path["exit_time"]
    return rows


def _bh(p_values: list[float]) -> np.ndarray:
    count = len(p_values)
    order = np.argsort(np.asarray(p_values, dtype=float))
    ranked = np.asarray(p_values, dtype=float)[order]
    adjusted = np.empty(count)
    running = 1.0
    for index in range(count - 1, -1, -1):
        running = min(running, ranked[index] * count / (index + 1))
        adjusted[index] = running
    out = np.empty(count)
    out[order] = adjusted
    return np.clip(out, 0.0, 1.0)


def _welch(on: np.ndarray, off: np.ndarray) -> float | None:
    if len(on) < 2 or len(off) < 2:
        return None
    var_on = float(on.var(ddof=1))
    var_off = float(off.var(ddof=1))
    se = np.sqrt(var_on / len(on) + var_off / len(off))
    if not np.isfinite(se) or se <= 0:
        return None
    return float((on.mean() - off.mean()) / se)


def _p_one_sided(stat: float | None) -> float | None:
    if stat is None or not np.isfinite(stat):
        return None
    return float(0.5 * math.erfc(stat / math.sqrt(2.0)))


def _cohen(on: np.ndarray, off: np.ndarray) -> float | None:
    if len(on) < 2 or len(off) < 2:
        return None
    pooled_num = (len(on) - 1) * float(on.var(ddof=1)) + (len(off) - 1) * float(off.var(ddof=1))
    pooled_den = len(on) + len(off) - 2
    if pooled_den <= 0:
        return None
    pooled = np.sqrt(pooled_num / pooled_den)
    if not np.isfinite(pooled) or pooled <= 0:
        return None
    return float((on.mean() - off.mean()) / pooled)


def analyze_features(train: list[dict], holdout: list[dict]) -> dict:
    """Benjamini-Hochberg on the holdout. Survivors also have to help in training."""
    def _mean(rows: list[dict]) -> float | None:
        if not rows:
            return None
        return float(np.mean([row["r"] for row in rows]))

    base_train = _mean(train)
    base_hold = _mean(holdout)
    tested = []
    rows = []
    for name in FEATURES:
        tr_on = np.array([row["r"] for row in train if name in row["features"]], dtype=float)
        tr_off = np.array([row["r"] for row in train if name not in row["features"]], dtype=float)
        ho_on = np.array([row["r"] for row in holdout if name in row["features"]], dtype=float)
        ho_off = np.array([row["r"] for row in holdout if name not in row["features"]], dtype=float)
        stat = _welch(ho_on, ho_off) if len(ho_on) >= FEATURE_MIN and len(ho_off) >= FEATURE_MIN else None
        item = {
            "name": name,
            "train_n": int(len(tr_on)),
            "train_mean": None if len(tr_on) == 0 else float(tr_on.mean()),
            "train_lift": None if len(tr_on) == 0 or base_train is None else float(tr_on.mean() - base_train),
            "hold_n": int(len(ho_on)),
            "hold_off": int(len(ho_off)),
            "hold_mean": None if len(ho_on) == 0 else float(ho_on.mean()),
            "hold_lift": None if len(ho_on) == 0 or base_hold is None else float(ho_on.mean() - base_hold),
            "t": stat,
            "d": _cohen(ho_on, ho_off),
            "p": _p_one_sided(stat),
            "q": None,
            "survives": False,
        }
        rows.append(item)
        if item["p"] is not None:
            tested.append(item)
    if tested:
        adjusted = _bh([float(item["p"]) for item in tested])
        for item, q_value in zip(tested, adjusted):
            item["q"] = float(q_value)
    survivors = []
    for item in rows:
        train_mean = item["train_mean"]
        hold_mean = item["hold_mean"]
        q_value = item["q"]
        item["survives"] = bool(
            q_value is not None
            and q_value <= FEATURE_Q
            and item["train_n"] >= FEATURE_MIN
            and item["hold_n"] >= FEATURE_MIN
            and train_mean is not None
            and hold_mean is not None
            and base_train is not None
            and base_hold is not None
            and train_mean > base_train
            and hold_mean > base_hold
            and train_mean > 0.0
            and hold_mean > 0.0
        )
        if item["survives"]:
            survivors.append(item["name"])
    return {
        "base_train": base_train,
        "base_hold": base_hold,
        "train_n": len(train),
        "hold_n": len(holdout),
        "rows": rows,
        "survivors": survivors,
    }


def simulate(
    prep: Prepared,
    setups: list[Setup],
    *,
    mode: str,
    kind: str,
    stake: float,
    long_only: bool,
    iv_points: dict | None = None,
    start: date | None = None,
    end: date | None = None,
    costs: CostModel | None = None,
) -> dict:
    """Fresh account. ``mode`` is structure, ema200, prem50, or prem100. ``kind`` is shares or 0dte."""
    if kind not in ("shares", "0dte"):
        raise ValueError("kind must be shares or 0dte")
    if mode not in ("structure", "ema200", "prem50", "prem100"):
        raise ValueError("unknown exit")
    if kind == "shares" and mode.startswith("prem"):
        raise ValueError("premium targets are option exits")
    model = costs or CostModel()
    points = iv_points or {}
    days: list[date] = []
    for day in prep.dates:
        if days and days[-1] == day:
            continue
        if start is not None and day < start:
            continue
        if end is not None and day > end:
            continue
        days.append(day)
    chosen = []
    for setup in setups:
        day = prep.dates[setup.fill_i]
        if start is not None and day < start:
            continue
        if end is not None and day > end:
            continue
        if long_only and setup.direction != "long":
            continue
        chosen.append(setup)
    chosen.sort(key=lambda item: item.fill_i)
    settled = float(stake)
    unsettled: list[tuple[date, float]] = []
    equity = float(stake)
    curve: list[tuple[pd.Timestamp, float]] = []
    trades: list[dict] = []
    skips = {"short": 0, "overlap": 0, "no_bar": 0, "iv": 0, "premium": 0, "dust": 0, "bust": 0}
    if long_only:
        skips["short"] = sum(
            1 for setup in setups
            if (start is None or prep.dates[setup.fill_i] >= start)
            and (end is None or prep.dates[setup.fill_i] <= end)
            and setup.direction != "long"
        )
    busy = None
    cursor = 0
    stopped = False
    for day in days:
        if not stopped:
            still = []
            for available_on, amount in unsettled:
                if available_on <= day:
                    settled += amount
                else:
                    still.append((available_on, amount))
            unsettled = still
            equity = settled + sum(amount for _when, amount in unsettled)
        while cursor < len(chosen) and prep.dates[chosen[cursor].fill_i] == day:
            setup = chosen[cursor]
            cursor += 1
            if stopped or equity <= 1.0:
                skips["bust"] += 1
                continue
            fill_time = prep.index[setup.fill_i]
            if busy is not None and fill_time <= busy:
                skips["overlap"] += 1
                continue
            iv = _iv_on(day, points) if kind == "0dte" else None
            if kind == "0dte" and iv is None:
                skips["iv"] += 1
                continue
            path = walk(prep, setup, mode, iv, split_half=(kind == "shares" and mode == "ema200"))
            if path is None:
                skips["dust"] += 1
                continue
            if kind == "shares":
                trade = _share_trade(setup, path, settled, equity, model)
            else:
                trade = _option_trade(setup, path, iv, settled, prep)
            if trade is None:
                skips["premium" if kind == "0dte" else "dust"] += 1
                continue
            if trade["debit"] > settled + 1e-9:
                skips["premium" if kind == "0dte" else "dust"] += 1
                continue
            settled -= trade["debit"]
            unsettled.append((next_trading_day(day), trade["credit"]))
            equity = settled + sum(amount for _when, amount in unsettled)
            trade["equity"] = equity
            trades.append(trade)
            busy = path["exit_time"]
            if equity <= 1.0:
                stopped = True
        curve.append((pd.Timestamp(day.isoformat()), equity))
    equity_series = pd.Series(
        [value for _stamp, value in curve],
        index=pd.DatetimeIndex([stamp for stamp, _value in curve]),
        dtype=float,
    )
    pnls = [float(trade["pnl"]) for trade in trades]
    stats = metrics_from(equity_series, pnls, float(stake))
    return {
        "equity": equity_series,
        "trades": trades,
        "skips": skips,
        "metrics": stats,
        "under_one_share": sum(1 for trade in trades if trade.get("quantity", 1) < 1.0 - 1e-9),
    }


def _share_trade(setup: Setup, path: dict, settled: float, equity: float, costs: CostModel) -> dict | None:
    fill = float(path["fill"])
    distance = abs(fill - float(path["stop"]))
    if distance <= 0:
        return None
    risk_dollars = RISK_FRACTION * equity
    if setup.direction != "long":
        return None
    entry_px = buy_price(fill, costs)
    room = settled / entry_px if entry_px > 0 else 0.0
    quantity = min(room, risk_dollars / distance)
    if quantity <= 1e-8:
        return None
    legs = _legs(path)
    debit = quantity * entry_px + buy_fees(costs)
    credit = 0.0
    for fraction, raw in legs:
        px = sell_price(raw, costs)
        qty = quantity * fraction
        credit += qty * px - sell_regulatory_fees(px, qty, costs)
    return _row(setup, path, quantity, debit, credit, credit - debit, None)


def _option_trade(setup: Setup, path: dict, iv: float, settled: float, prep: Prepared) -> dict | None:
    fill = float(path["fill"])
    right = "call" if setup.direction == "long" else "put"
    strike = listed_strike(fill, fill)
    when = prep.index[setup.fill_i]
    entry_mid = _option_mid(right, fill, strike, when, iv)
    entry_ask = entry_mid + _half_spread(entry_mid)
    debit = entry_ask * CONTRACT_MULTIPLIER + option_leg_fees(1, entry_ask, sell=False)
    if debit <= 0 or debit > settled + 1e-9:
        return None
    if path["premium"] is not None:
        bid = float(path["premium"])
    else:
        bid = _bid(right, float(path["exit_spot"]), strike, path["exit_time"], iv)
    credit = bid * CONTRACT_MULTIPLIER - option_leg_fees(1, bid, sell=True)
    return _row(setup, path, 1.0, debit, credit, credit - debit, strike)


def _legs(path: dict) -> list[tuple[float, float]]:
    if path["scaled"] and path["scale_spot"] is not None:
        return [(0.5, float(path["scale_spot"])), (0.5, float(path["exit_spot"]))]
    return [(1.0, float(path["exit_spot"]))]


def _row(setup: Setup, path: dict, quantity: float, debit: float, credit: float, pnl: float, strike: float | None) -> dict:
    return {
        "symbol": setup.symbol,
        "variant": setup.variant,
        "direction": setup.direction,
        "trigger_i": setup.trigger_i,
        "fill_i": setup.fill_i,
        "exit_time": path["exit_time"],
        "entry": path["fill"],
        "exit": path["exit_spot"],
        "stop": path["stop"],
        "reason": path["reason"],
        "scaled": path["scaled"],
        "quantity": quantity,
        "debit": debit,
        "credit": credit,
        "pnl": pnl,
        "strike": strike,
        "features": setup.features,
    }


def random_setups(prep: Prepared, count: int, seed: int = RANDOM_SEED, *, start: date | None = None, end: date | None = None) -> list[Setup]:
    """Same count of coin-flip entries on eligible bars. The book applies the structure exit."""
    if count <= 0:
        return []
    eligible = []
    for i in range(len(prep.close) - 2):
        day = prep.dates[i + 2]
        if start is not None and day < start:
            continue
        if end is not None and day > end:
            continue
        if prep.dates[i] != prep.dates[i + 2]:
            continue
        if not _clock_ok(prep, i):
            continue
        if not _finite(prep.low[i], prep.high[i]) or prep.low[i] <= 0 or prep.high[i] <= 0:
            continue
        eligible.append(i)
    if not eligible:
        return []
    rng = np.random.default_rng(seed)
    picks = rng.choice(len(eligible), size=count, replace=count > len(eligible))
    sides = rng.integers(0, 2, size=count)
    found = []
    for pick, side in zip(picks, sides):
        i = int(eligible[int(pick)])
        direction = "long" if int(side) == 0 else "short"
        stop = float(prep.low[i] - STOP_PAD) if direction == "long" else float(prep.high[i] + STOP_PAD)
        found.append(Setup("SPY", "random", direction, i, i + 1, i + 2, -1, -1, stop))
    found.sort(key=lambda item: item.fill_i)
    return found


def signals_per_month(prep: Prepared, setups: list[Setup], start: date, end: date) -> float | None:
    count = sum(1 for setup in setups if start <= prep.dates[setup.fill_i] <= end)
    months = (end.year - start.year) * 12 + (end.month - start.month) + 1
    if months <= 0:
        return None
    return count / months
