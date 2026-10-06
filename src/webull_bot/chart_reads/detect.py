"""Causal chart-read detector.

Bar t uses only information closed by t. The fill is the next bar's open,
and a signal on the last bar of a session is dropped instead of carried
overnight. Session VWAP uses a 2-standard-deviation band and resets at
9:30 ET. The 1-standard-deviation helper in the earlier VWAP study is
left alone.

Setup A is the breakout-retest continuation. Setup B is the failed
breakout followed by a 9/20 cross. Short is the mirror of long.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from typing import Optional

import numpy as np
import pandas as pd

from webull_bot.chart_reads.params import DEFAULTS, htf_allows
from webull_bot.indicators import atr, ema, rsi
from webull_bot.mtf_vwap.detect import rth, to_ny, weekly_from_daily

NY = "America/New_York"
RTH_OPEN = time(9, 30)
MORNING_END = time(11, 30)


@dataclass
class Setup:
    symbol: str
    direction: str
    kind: str
    signal_time: pd.Timestamp
    fill_time: pd.Timestamp
    anchor_time: pd.Timestamp
    stop: float
    atr: float
    reference: float
    # Farther objective used by the partial-bounce study. Other setups leave it unset.
    reversal: float = float("nan")


def session_bands(frame: pd.DataFrame, deviations: float = 2.0) -> pd.DataFrame:
    """Session VWAP and a volume-weighted standard-deviation band.

    ``deviations`` is 2 to match the annotated ±2 SD bands. The session
    resets at 9:30 ET. Rows outside regular hours are dropped by ``rth``.
    """
    bars = rth(frame)
    empty = pd.DataFrame(columns=["vwap", "upper", "lower", "std"])
    if bars.empty:
        return empty
    typical = (bars["high"] + bars["low"] + bars["close"]) / 3.0
    volume = bars["volume"].astype(float).clip(lower=0.0)
    volume = volume.where(volume > 0.0, 1.0)
    day = pd.Series([ts.date() for ts in bars.index], index=bars.index)
    sum_v = volume.groupby(day).cumsum()
    sum_pv = (typical * volume).groupby(day).cumsum()
    sum_p2 = ((typical ** 2) * volume).groupby(day).cumsum()
    vwap = sum_pv / sum_v
    var = (sum_p2 / sum_v - vwap ** 2).clip(lower=0.0)
    std = np.sqrt(var.to_numpy())
    width = deviations * std
    return pd.DataFrame(
        {
            "vwap": vwap.to_numpy(),
            "upper": vwap.to_numpy() + width,
            "lower": vwap.to_numpy() - width,
            "std": std,
        },
        index=bars.index,
    )


def trend_labels(frame: pd.DataFrame) -> pd.Series:
    """Up when the 9 EMA is above the 20 and both are rising. Down is the mirror.

    Anything warm but not a clean trend is ``mixed``. Bars before the 20 EMA
    exists are ``none`` and do not vote.
    """
    close = frame["close"].astype(float)
    fast = ema(close, 9)
    slow = ema(close, 20)
    up = (fast > slow) & (fast > fast.shift(1)) & (slow > slow.shift(1))
    down = (fast < slow) & (fast < fast.shift(1)) & (slow < slow.shift(1))
    label = np.full(len(frame), "mixed", dtype=object)
    label[up.fillna(False).to_numpy()] = "up"
    label[down.fillna(False).to_numpy()] = "down"
    warm = (fast.notna() & slow.notna()).to_numpy()
    label[~warm] = "none"
    return pd.Series(label, index=frame.index)


def macd_hist(close: pd.Series) -> pd.Series:
    line = ema(close, 12) - ema(close, 26)
    signal = ema(line, 9)
    return line - signal


def strong_candle(open_: float, high: float, low: float, close: float, direction: str, body: float, close_frac: float) -> bool:
    span = high - low
    if not np.isfinite(span) or span <= 0:
        return False
    if abs(close - open_) / span + 1e-12 < body:
        return False
    if direction == "long":
        return close > open_ and (close - low) / span + 1e-12 >= close_frac
    return close < open_ and (high - close) / span + 1e-12 >= close_frac


def _same_unit(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    idx = pd.DatetimeIndex(index)
    if hasattr(idx, "as_unit"):
        idx = idx.as_unit("ns")
    return idx


def _bar_minutes(index: pd.DatetimeIndex) -> int:
    if len(index) < 3:
        return 5
    diffs = np.diff(index.asi8) / 1e9 / 60.0
    diffs = diffs[(diffs > 0) & (diffs <= 120)]
    if len(diffs) == 0:
        return 5
    return int(np.median(diffs))


def _stamp_daily(daily: pd.DataFrame) -> pd.DataFrame:
    bars = to_ny(daily).sort_index()
    bars = bars.copy()
    idx = pd.DatetimeIndex(bars.index)
    if idx.tz is not None:
        idx = idx.tz_convert(NY)
    else:
        idx = idx.tz_localize(NY)
    bars.index = idx.normalize() + pd.Timedelta(hours=16)
    return bars[~bars.index.duplicated(keep="last")]


def label_asof(labels: pd.Series, when: pd.DatetimeIndex) -> pd.Series:
    """Last label whose bar had closed by ``when``."""
    if labels.empty or len(when) == 0:
        return pd.Series(["none"] * len(when), index=when)
    labels = labels.sort_index()
    labels = labels[~labels.index.duplicated(keep="last")]
    labels.index = _same_unit(pd.DatetimeIndex(labels.index))
    when_ns = _same_unit(pd.DatetimeIndex(when))
    left = pd.DataFrame({"when": when_ns}).sort_values("when")
    right = labels.rename("direction").reset_index()
    right.columns = ["known_at", "direction"]
    merged = pd.merge_asof(left, right, left_on="when", right_on="known_at", direction="backward")
    out = merged["direction"].fillna("none")
    out.index = pd.DatetimeIndex(left["when"])
    restored = out.reindex(when_ns)
    restored.index = pd.DatetimeIndex(when)
    return restored


def _known(frame: pd.DataFrame, minutes: int) -> pd.Series:
    labels = trend_labels(frame)
    labels.index = pd.DatetimeIndex(labels.index) + pd.Timedelta(minutes=minutes)
    return labels


def _votes(bundle: dict[str, pd.DataFrame], execution: str, when: pd.DatetimeIndex) -> list[pd.Series]:
    """Frames that vote, aligned to the execution bar's close."""
    votes: list[pd.Series] = []
    daily = bundle.get("daily")
    if daily is not None and len(daily):
        stamped = _stamp_daily(daily)
        votes.append(label_asof(trend_labels(stamped), when))
    if execution == "60m":
        if daily is not None and len(daily):
            weekly = weekly_from_daily(_stamp_daily(daily))
            if len(weekly):
                votes.append(label_asof(trend_labels(weekly), when))
        return votes
    hourly = bundle.get("60m")
    if hourly is not None and len(hourly):
        votes.append(label_asof(_known(rth(hourly), _bar_minutes(rth(hourly).index)), when))
    if execution == "5m":
        slow = bundle.get("15m")
        if slow is not None and len(slow):
            votes.append(label_asof(_known(rth(slow), _bar_minutes(rth(slow).index)), when))
    return votes


def _features(frame: pd.DataFrame, deviations: float) -> pd.DataFrame:
    bars = rth(frame)
    if bars.empty:
        return bars
    close = bars["close"].astype(float)
    out = bars.copy()
    out["ema9"] = ema(close, 9)
    out["ema20"] = ema(close, 20)
    out["ema200"] = ema(close, 200)
    out["atr"] = atr(bars, 14)
    out["rsi"] = rsi(close, 14)
    out["macd_hist"] = macd_hist(close)
    bands = session_bands(bars, deviations)
    out["vwap"] = bands["vwap"]
    out["upper"] = bands["upper"]
    out["lower"] = bands["lower"]
    out["std"] = bands["std"]
    return out


def _filters(row_ok: bool, direction: str, i: int, cols: dict, params: dict) -> bool:
    if not row_ok:
        return False
    if params.get("morning_only"):
        clock = cols["clock"][i]
        if clock < RTH_OPEN or clock >= MORNING_END:
            return False
    if params.get("require_ema200"):
        ema200 = cols["ema200"][i]
        if not np.isfinite(ema200):
            return False
        if direction == "long" and cols["close"][i] <= ema200:
            return False
        if direction == "short" and cols["close"][i] >= ema200:
            return False
    if params.get("rsi_filter"):
        value = cols["rsi"][i]
        if not np.isfinite(value):
            return False
        if direction == "long" and value > 70.0:
            return False
        if direction == "short" and value < 30.0:
            return False
    if params.get("macd_filter"):
        value = cols["macd"][i]
        if not np.isfinite(value):
            return False
        if direction == "long" and value <= 0.0:
            return False
        if direction == "short" and value >= 0.0:
            return False
    if params.get("avoid_extended"):
        if direction == "long":
            upper = cols["upper"][i]
            if not np.isfinite(upper) or cols["close"][i] > upper:
                return False
        else:
            lower = cols["lower"][i]
            if not np.isfinite(lower) or cols["close"][i] < lower:
                return False
    return True


def _trend(direction: str, i: int, cols: dict, k_sep: float) -> bool:
    if i < 1:
        return False
    fast = cols["ema9"][i]
    slow = cols["ema20"][i]
    prev_fast = cols["ema9"][i - 1]
    prev_slow = cols["ema20"][i - 1]
    width = cols["atr"][i]
    if not all(np.isfinite(value) for value in (fast, slow, prev_fast, prev_slow, width)) or width <= 0:
        return False
    if abs(fast - slow) + 1e-12 < k_sep * width:
        return False
    if direction == "long":
        return fast > slow and fast > prev_fast and slow > prev_slow and cols["close"][i] > cols["vwap"][i]
    return fast < slow and fast < prev_fast and slow < prev_slow and cols["close"][i] < cols["vwap"][i]


def _touched(direction: str, start: int, end: int, cols: dict, touch: float, level: float) -> bool:
    for j in range(start, end + 1):
        width = cols["atr"][j]
        if not np.isfinite(width) or width <= 0:
            continue
        band = touch * width
        price = cols["low"][j] if direction == "long" else cols["high"][j]
        levels = (cols["ema9"][j], cols["ema20"][j], cols["vwap"][j], level)
        for candidate in levels:
            if np.isfinite(candidate) and abs(price - candidate) <= band:
                return True
    return False


def _pullback_clean(direction: str, start: int, end: int, cols: dict) -> bool:
    slow = cols["ema20"]
    close = cols["close"]
    for j in range(start, end + 1):
        if not np.isfinite(slow[j]) or not np.isfinite(close[j]):
            return False
        if direction == "long" and close[j] < slow[j]:
            return False
        if direction == "short" and close[j] > slow[j]:
            return False
    return True


def find_setups(bundle: dict[str, pd.DataFrame], params: dict | None = None, *, symbol: str = "") -> list[Setup]:
    """Scan one symbol. ``bundle`` holds the execution frame plus higher timeframes."""
    chosen = dict(DEFAULTS)
    if params:
        chosen.update(params)
    execution = str(chosen.get("execution", "5m"))
    frame = bundle.get(execution)
    if frame is None or len(frame) < 30:
        return []
    feat = _features(frame, float(chosen["band_std"]))
    if len(feat) < 30:
        return []
    minutes = _bar_minutes(feat.index)
    closed_at = pd.DatetimeIndex(feat.index) + pd.Timedelta(minutes=minutes)
    vote_series = _votes(bundle, execution, closed_at)
    if execution != "5m":
        # The execution bar votes with its own 9/20 read. On 5-minute that
        # read is the local trend gate, not a fourth higher-timeframe vote.
        own = trend_labels(feat)
        own.index = closed_at
        vote_series.append(label_asof(own, closed_at))

    index = feat.index
    dates = np.array([ts.date() for ts in index])
    clock = np.array([ts.timetz().replace(tzinfo=None) for ts in index])
    cols = {
        "open": feat["open"].to_numpy(dtype=float),
        "high": feat["high"].to_numpy(dtype=float),
        "low": feat["low"].to_numpy(dtype=float),
        "close": feat["close"].to_numpy(dtype=float),
        "ema9": feat["ema9"].to_numpy(dtype=float),
        "ema20": feat["ema20"].to_numpy(dtype=float),
        "ema200": feat["ema200"].to_numpy(dtype=float),
        "atr": feat["atr"].to_numpy(dtype=float),
        "rsi": feat["rsi"].to_numpy(dtype=float),
        "macd": feat["macd_hist"].to_numpy(dtype=float),
        "vwap": feat["vwap"].to_numpy(dtype=float),
        "upper": feat["upper"].to_numpy(dtype=float),
        "lower": feat["lower"].to_numpy(dtype=float),
        "std": feat["std"].to_numpy(dtype=float),
        "clock": clock,
    }
    vote_labels = [series.to_numpy() for series in vote_series]
    n = len(feat)
    lookback = int(chosen["breakout_lookback"])
    pullback_bars = int(chosen["pullback_bars"])
    cross_bars = int(chosen["cross_bars"])
    k_sep = float(chosen["k_sep"])
    touch = float(chosen["touch_atr"])
    body = float(chosen["strong_body"])
    close_frac = float(chosen["strong_close_frac"])
    setups: list[Setup] = []
    used_cross: set[int] = set()

    def votes_at(i: int) -> list[str]:
        return [str(series[i]) for series in vote_labels]

    def emit(direction: str, kind: str, i: int, stop: float, reference: float, anchor: int) -> None:
        if i + 1 >= n or dates[i + 1] != dates[i]:
            return
        width = cols["atr"][i]
        if not np.isfinite(width) or width <= 0 or not np.isfinite(stop):
            return
        setups.append(
            Setup(
                symbol=symbol,
                direction=direction,
                kind=kind,
                signal_time=pd.Timestamp(index[i]),
                fill_time=pd.Timestamp(index[i + 1]),
                anchor_time=pd.Timestamp(index[anchor]),
                stop=float(stop),
                atr=float(width),
                reference=float(reference) if np.isfinite(reference) else float("nan"),
            )
        )

    impulse = {"long": -1, "short": -1}
    impulse_level = {"long": np.nan, "short": np.nan}
    signaled = {"long": -1, "short": -1}
    session_high = -np.inf
    session_low = np.inf
    bars_in_session = 0
    current = None

    for i in range(n):
        if dates[i] != current:
            current = dates[i]
            session_high = -np.inf
            session_low = np.inf
            bars_in_session = 0
            impulse = {"long": -1, "short": -1}
            impulse_level = {"long": np.nan, "short": np.nan}
            signaled = {"long": -1, "short": -1}

        if chosen.get("setup_a", True):
            for direction, anchor in (("long", "low"), ("short", "high")):
                start = impulse[direction]
                if start < 0 or start == signaled[direction]:
                    continue
                if i <= start or i > start + pullback_bars:
                    continue
                if not _pullback_clean(direction, start + 1, i, cols):
                    signaled[direction] = start
                    continue
                level = impulse_level[direction]
                if not _touched(direction, start + 1, i, cols, touch, level):
                    continue
                if not strong_candle(
                    cols["open"][i], cols["high"][i], cols["low"][i], cols["close"][i], direction, body, close_frac
                ):
                    continue
                if direction == "long" and cols["close"][i] < cols["low"][i - 1]:
                    continue
                if direction == "short" and cols["close"][i] > cols["high"][i - 1]:
                    continue
                if not _trend(direction, i, cols, k_sep):
                    continue
                retrace = float(chosen["min_retrace_atr"]) * cols["atr"][i]
                if direction == "long":
                    depth = cols["high"][start] - float(np.min(cols["low"][start + 1 : i + 1]))
                else:
                    depth = float(np.max(cols["high"][start + 1 : i + 1])) - cols["low"][start]
                if not np.isfinite(depth) or depth + 1e-12 < retrace:
                    continue
                if not htf_allows(votes_at(i), direction, "A"):
                    continue
                if not _filters(True, direction, i, cols, chosen):
                    continue
                if direction == "long":
                    stop = float(np.min(cols["low"][start + 1 : i + 1]))
                else:
                    stop = float(np.max(cols["high"][start + 1 : i + 1]))
                emit(direction, "A", i, stop, level, start)
                signaled[direction] = start

        prior_high = np.max(cols["high"][max(0, i - lookback) : i]) if i > 0 else np.nan
        prior_low = np.min(cols["low"][max(0, i - lookback) : i]) if i > 0 else np.nan
        std_ok = bars_in_session >= 2 and np.isfinite(cols["std"][i]) and cols["std"][i] > 0
        new_high = bars_in_session >= 1 and cols["high"][i] > session_high
        new_low = bars_in_session >= 1 and cols["low"][i] < session_low
        tag_upper = std_ok and cols["high"][i] >= cols["upper"][i]
        tag_lower = std_ok and cols["low"][i] <= cols["lower"][i]
        if (new_high or tag_upper) and cols["close"][i] > cols["open"][i] and cols["close"][i] > cols["vwap"][i]:
            impulse["long"] = i
            if new_high and np.isfinite(prior_high):
                impulse_level["long"] = float(prior_high)
            elif tag_upper:
                impulse_level["long"] = float(cols["upper"][i])
            else:
                impulse_level["long"] = float(session_high) if np.isfinite(session_high) else np.nan
        if (new_low or tag_lower) and cols["close"][i] < cols["open"][i] and cols["close"][i] < cols["vwap"][i]:
            impulse["short"] = i
            if new_low and np.isfinite(prior_low):
                impulse_level["short"] = float(prior_low)
            elif tag_lower:
                impulse_level["short"] = float(cols["lower"][i])
            else:
                impulse_level["short"] = float(session_low) if np.isfinite(session_low) else np.nan

        session_high = max(session_high, cols["high"][i])
        session_low = min(session_low, cols["low"][i])
        bars_in_session += 1

    if chosen.get("setup_b", True):
        highs = cols["high"]
        lows = cols["low"]
        for i in range(lookback, n - 1):
            if dates[i + 1] != dates[i]:
                continue
            prior_high = float(np.max(highs[i - lookback : i]))
            prior_low = float(np.min(lows[i - lookback : i]))
            short_level = None
            if highs[i] > prior_high and cols["close"][i] > prior_high:
                short_level = prior_high
            elif np.isfinite(cols["upper"][i]) and highs[i] > cols["upper"][i] and cols["close"][i] > cols["upper"][i]:
                short_level = float(cols["upper"][i])
            long_level = None
            if lows[i] < prior_low and cols["close"][i] < prior_low:
                long_level = prior_low
            elif np.isfinite(cols["lower"][i]) and lows[i] < cols["lower"][i] and cols["close"][i] < cols["lower"][i]:
                long_level = float(cols["lower"][i])
            if short_level is not None and cols["close"][i + 1] < short_level:
                _arm_cross(
                    "short", i, short_level, dates, cols, chosen, votes_at, emit, used_cross, cross_bars
                )
            if long_level is not None and cols["close"][i + 1] > long_level:
                _arm_cross(
                    "long", i, long_level, dates, cols, chosen, votes_at, emit, used_cross, cross_bars
                )
    setups.sort(key=lambda setup: (pd.Timestamp(setup.fill_time), setup.kind, setup.direction))
    return setups


def _arm_cross(direction, i, level, dates, cols, params, votes_at, emit, used_cross, cross_bars) -> None:
    """After a failed break, wait for a fresh 9/20 cross and a VWAP close."""
    last = min(len(cols["close"]) - 1, i + 1 + cross_bars - 1)
    failed_high = max(float(cols["high"][i]), float(cols["high"][i + 1]))
    failed_low = min(float(cols["low"][i]), float(cols["low"][i + 1]))
    for k in range(i + 1, last + 1):
        if dates[k] != dates[i]:
            return
        if k in used_cross or k < 1:
            continue
        if direction == "short":
            if cols["high"][k] > failed_high and k > i + 1:
                return
            if cols["close"][k] > level and k > i + 1:
                return
            crossed = cols["ema9"][k] < cols["ema20"][k] and cols["ema9"][k - 1] >= cols["ema20"][k - 1]
            lost = np.isfinite(cols["vwap"][k]) and cols["close"][k] < cols["vwap"][k]
            stop = failed_high
        else:
            if cols["low"][k] < failed_low and k > i + 1:
                return
            if cols["close"][k] < level and k > i + 1:
                return
            crossed = cols["ema9"][k] > cols["ema20"][k] and cols["ema9"][k - 1] <= cols["ema20"][k - 1]
            lost = np.isfinite(cols["vwap"][k]) and cols["close"][k] > cols["vwap"][k]
            stop = failed_low
        if not (crossed and lost):
            continue
        if not all(np.isfinite(cols["ema9"][j]) and np.isfinite(cols["ema20"][j]) for j in (k, k - 1)):
            continue
        if not htf_allows(votes_at(k), direction, "B"):
            continue
        if not _filters(True, direction, k, cols, params):
            continue
        emit(direction, "B", k, stop, float(level), i)
        used_cross.add(k)
        return
