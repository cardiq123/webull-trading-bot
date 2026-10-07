"""Causal multi-timeframe trend and session-VWAP test.

A value on bar t uses only bars that have closed by t. Pivot confirmation
waits ``pivot_right`` bars. Weekly and daily trends use the last completed
session, not the session still in progress. The setup fills at the next
bar's open after the confirmation bar.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from typing import Optional

import numpy as np
import pandas as pd

from webull_bot.indicators import atr, ema
from webull_bot.mtf_vwap.params import DEFAULTS, majority_needed
from webull_bot.patterns import (
    _pivot_points,
    confirmed_pivot_high,
    confirmed_pivot_low,
    rising_trendline,
)

NY = "America/New_York"
RTH_OPEN = time(9, 30)
RTH_CLOSE = time(16, 0)


@dataclass
class Setup:
    symbol: str
    direction: str
    test_time: pd.Timestamp
    confirm_time: pd.Timestamp
    fill_time: pd.Timestamp
    vwap: float
    zone: Optional[float]
    stop: float
    target: Optional[float]
    atr: float


def to_ny(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    index = pd.DatetimeIndex(out.index)
    if index.tz is None:
        index = index.tz_localize(NY)
    else:
        index = index.tz_convert(NY)
    out.index = index
    return out.sort_index()


def rth(frame: pd.DataFrame) -> pd.DataFrame:
    ny = to_ny(frame)
    clock = ny.index.time
    kept = ny[(clock >= RTH_OPEN) & (clock < RTH_CLOSE)]
    return kept[kept["close"].notna()]


def session_vwap(frame: pd.DataFrame) -> pd.DataFrame:
    """Session VWAP and a volume-weighted 1-standard-deviation band.

    The session resets at 9:30 ET. Rows outside regular hours are dropped.
    """
    bars = rth(frame)
    if bars.empty:
        return pd.DataFrame(columns=["vwap", "upper", "lower"])
    typical = (bars["high"] + bars["low"] + bars["close"]) / 3.0
    volume = bars["volume"].astype(float).clip(lower=0.0)
    volume = volume.where(volume > 0.0, 1.0)
    day = pd.Series(bars.index.date, index=bars.index)
    sum_v = volume.groupby(day).cumsum()
    sum_pv = (typical * volume).groupby(day).cumsum()
    sum_p2 = ((typical ** 2) * volume).groupby(day).cumsum()
    vwap = sum_pv / sum_v
    var = (sum_p2 / sum_v - vwap ** 2).clip(lower=0.0)
    std = np.sqrt(var)
    return pd.DataFrame({"vwap": vwap, "upper": vwap + std, "lower": vwap - std}, index=bars.index)


def trend_flags(frame: pd.DataFrame, ema_window: int, left: int, right: int) -> pd.DataFrame:
    """Up is a rising EMA with the close above it and higher highs and higher lows.

    Down is the mirror. The pivot is stored on its confirmation bar, so the
    structure on bar t does not use a pivot that is still unconfirmed.
    """
    close = frame["close"].astype(float)
    average = ema(close, ema_window)
    rising = (average > average.shift(1)).fillna(False).to_numpy()
    falling = (average < average.shift(1)).fillna(False).to_numpy()
    highs = confirmed_pivot_high(frame["high"].astype(float), left, right).to_numpy()
    lows = confirmed_pivot_low(frame["low"].astype(float), left, right).to_numpy()
    closes = close.to_numpy()
    averages = average.to_numpy()
    up = np.zeros(len(frame), dtype=bool)
    down = np.zeros(len(frame), dtype=bool)
    last_highs: list[float] = []
    last_lows: list[float] = []
    for i in range(len(frame)):
        if np.isfinite(highs[i]):
            last_highs.append(float(highs[i]))
            last_highs = last_highs[-2:]
        if np.isfinite(lows[i]):
            last_lows.append(float(lows[i]))
            last_lows = last_lows[-2:]
        if len(last_highs) < 2 or len(last_lows) < 2 or not np.isfinite(averages[i]):
            continue
        higher_high = last_highs[-1] > last_highs[-2]
        higher_low = last_lows[-1] > last_lows[-2]
        lower_high = last_highs[-1] < last_highs[-2]
        lower_low = last_lows[-1] < last_lows[-2]
        if rising[i] and closes[i] > averages[i] and higher_high and higher_low:
            up[i] = True
        if falling[i] and closes[i] < averages[i] and lower_high and lower_low:
            down[i] = True
    return pd.DataFrame({"up": up, "down": down}, index=frame.index)


def _close_stamp(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Mark a daily or weekly bar known at 16:00 ET on its session."""
    ny = index.tz_convert(NY) if index.tz is not None else index.tz_localize(NY)
    midnight = ny.normalize()
    return midnight + pd.Timedelta(hours=16)


def _labels(flags: pd.DataFrame) -> pd.Series:
    label = np.array(["none"] * len(flags), dtype=object)
    up = flags["up"].to_numpy()
    down = flags["down"].to_numpy()
    label[up] = "up"
    label[down] = "down"
    return pd.Series(label, index=flags.index)


def _same_unit(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """merge_asof rejects mixed second and microsecond resolutions."""
    idx = pd.DatetimeIndex(index)
    if hasattr(idx, "as_unit"):
        idx = idx.as_unit("ns")
    return idx


def direction_asof(flags: pd.DataFrame, when: pd.DatetimeIndex) -> pd.Series:
    """Last completed higher-timeframe label at each execution timestamp."""
    if flags.empty or len(when) == 0:
        return pd.Series(["none"] * len(when), index=when)
    labels = _labels(flags).sort_index()
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


def resample_ohlc(frame: pd.DataFrame, rule: str) -> pd.DataFrame:
    bars = rth(frame)
    if bars.empty:
        return bars
    grouped = bars.resample(rule, label="right", closed="right", origin="start_day", offset="30min")
    out = grouped.agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
    ).dropna(subset=["close"])
    return out


def daily_from_intraday(frame: pd.DataFrame) -> pd.DataFrame:
    bars = rth(frame)
    if bars.empty:
        return bars
    day = bars.groupby(bars.index.date)
    out = day.agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
    )
    out.index = pd.to_datetime(out.index).tz_localize(NY) + pd.Timedelta(hours=16)
    return out


def _naive_ny(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Drop the zone after converting to New York, so a period group is local."""
    idx = pd.DatetimeIndex(index)
    if idx.tz is not None:
        idx = idx.tz_convert(NY).tz_localize(None)
    return idx


def weekly_from_daily(daily: pd.DataFrame) -> pd.DataFrame:
    """One bar per week, known at the last session's 16:00 ET."""
    bars = to_ny(daily).sort_index()
    if bars.empty:
        return bars
    period = _naive_ny(bars.index).to_period("W-FRI")
    rows = []
    stamps = []
    for _key, chunk in bars.groupby(period):
        if chunk.empty:
            continue
        end = pd.Timestamp(chunk.index[-1])
        if end.tzinfo is None:
            end = end.tz_localize(NY)
        stamps.append(end.normalize() + pd.Timedelta(hours=16))
        rows.append(
            {
                "open": float(chunk["open"].iloc[0]),
                "high": float(chunk["high"].max()),
                "low": float(chunk["low"].min()),
                "close": float(chunk["close"].iloc[-1]),
                "volume": float(chunk["volume"].sum()),
            }
        )
    if not rows:
        return bars.iloc[0:0]
    return pd.DataFrame(rows, index=pd.DatetimeIndex(stamps))


def falling_trendline(high: pd.Series, left: int, right: int) -> pd.Series:
    """Line through the latest confirmed pivot high and the nearest earlier higher one.

    The mirror of ``rising_trendline``. NaN unless the two pivots are falling.
    Both pivots are confirmed strictly before today.
    """
    points = _pivot_points(confirmed_pivot_high(high, left, right), right)
    out = np.full(len(high), np.nan)
    pointer = 0
    known: list[tuple[int, float, int]] = []
    for t in range(len(high)):
        while pointer < len(points) and points[pointer][2] < t:
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
        out[t] = y2 + slope * (t - x2)
    return pd.Series(out, index=high.index)


def _stamp_daily(daily: pd.DataFrame) -> pd.DataFrame:
    bars = to_ny(daily)
    bars = bars.copy()
    bars.index = _close_stamp(pd.DatetimeIndex(bars.index))
    return bars


def _confirmation(window: pd.DataFrame, i: int, direction: str) -> bool:
    if i <= 0 or i >= len(window):
        return False
    row = window.iloc[i]
    prev = window.iloc[i - 1]
    high = float(row["high"])
    low = float(row["low"])
    close = float(row["close"])
    opened = float(row["open"])
    span = high - low
    if not np.isfinite(span) or span <= 0:
        return False
    body = abs(close - opened)
    if direction == "long":
        lower = min(opened, close) - low
        upper = high - max(opened, close)
        pin = lower >= 2.0 * max(body, 1e-9) and close > opened and lower > upper
        engulf = (
            close > opened
            and float(prev["close"]) < float(prev["open"])
            and close >= float(prev["open"])
            and opened <= float(prev["close"])
        )
        thrust = (close - low) / span >= 0.75 and close > float(prev["high"])
        return bool(pin or engulf or thrust)
    upper = high - max(opened, close)
    lower = min(opened, close) - low
    pin = upper >= 2.0 * max(body, 1e-9) and close < opened and upper > lower
    engulf = (
        close < opened
        and float(prev["close"]) > float(prev["open"])
        and close <= float(prev["open"])
        and opened >= float(prev["close"])
    )
    thrust = (high - close) / span >= 0.75 and close < float(prev["low"])
    return bool(pin or engulf or thrust)


def _near(price: float, levels: list[float], width: float) -> Optional[float]:
    found = None
    best = width
    for level in levels:
        gap = abs(price - level)
        if gap <= best:
            best = gap
            found = level
    return found


def _next_level(price: float, levels: list[float], direction: str) -> Optional[float]:
    if direction == "long":
        above = [level for level in levels if level > price]
        return min(above) if above else None
    below = [level for level in levels if level < price]
    return max(below) if below else None


def _reclaim(m5: pd.DataFrame, vwap5: pd.Series, start: pd.Timestamp, end: pd.Timestamp, direction: str) -> bool:
    window = vwap5[(vwap5.index > start) & (vwap5.index <= end)]
    if window.empty:
        return False
    closes = m5["close"].reindex(window.index)
    if direction == "long":
        return bool((closes > window).any())
    return bool((closes < window).any())


def find_setups(
    bundle: dict[str, pd.DataFrame],
    params: dict | None = None,
    *,
    symbol: str = "",
) -> list[Setup]:
    """``bundle`` holds the execution frame and any higher frames already built.

    Recognized keys: ``15m``, ``5m``, ``60m``, ``daily``. Weekly is built
    from daily. Missing 60m is resampled from 15m. The execution key is
    ``params['execution']``.
    """
    chosen = dict(DEFAULTS)
    if params:
        chosen.update(params)
    execution = str(chosen["execution"])
    if execution not in bundle or bundle[execution] is None or bundle[execution].empty:
        return []
    exec_bars = rth(bundle[execution])
    if len(exec_bars) < 30:
        return []
    left = int(chosen["pivot_left"])
    right = int(chosen["pivot_right"])
    intraday_ema = int(chosen["ema_intraday"])
    daily_ema = int(chosen["ema_daily"])

    daily = bundle.get("daily")
    if daily is None or daily.empty:
        daily = daily_from_intraday(exec_bars)
    else:
        daily = _stamp_daily(daily)
    weekly = weekly_from_daily(daily)
    m60 = bundle.get("60m")
    if execution == "60m":
        m60 = exec_bars
    elif m60 is None or m60.empty:
        m60 = resample_ohlc(exec_bars, "60min")
    else:
        m60 = rth(m60)
    m5 = bundle.get("5m")
    if m5 is not None and not m5.empty:
        m5 = rth(m5)

    frames: dict[str, tuple[pd.DataFrame, int]] = {}
    if execution == "15m":
        frames = {
            "weekly": (weekly, daily_ema),
            "daily": (daily, daily_ema),
            "60m": (m60, intraday_ema),
            "15m": (exec_bars, intraday_ema),
        }
        if m5 is not None and not m5.empty:
            frames["5m"] = (m5, intraday_ema)
    else:
        frames = {
            "weekly": (weekly, daily_ema),
            "daily": (daily, daily_ema),
            "60m": (exec_bars, intraday_ema),
        }
    trends = {
        name: trend_flags(frame, window, left, right)
        for name, (frame, window) in frames.items()
        if frame is not None and len(frame) > window + left + right
    }
    if execution not in trends:
        return []
    when = pd.DatetimeIndex(exec_bars.index)
    aligned = {name: direction_asof(flags, when) for name, flags in trends.items()}

    vwap = session_vwap(exec_bars).reindex(exec_bars.index)
    width = atr(exec_bars, 14)
    vwap5 = session_vwap(m5)["vwap"] if m5 is not None and not m5.empty else None

    support_marks = {
        "weekly": confirmed_pivot_low(weekly["low"], left, right) if len(weekly) else pd.Series(dtype=float),
        "daily": confirmed_pivot_low(daily["low"], left, right) if len(daily) else pd.Series(dtype=float),
        "60m": confirmed_pivot_low(m60["low"], left, right) if len(m60) else pd.Series(dtype=float),
        "exec": confirmed_pivot_low(exec_bars["low"], left, right),
    }
    resist_marks = {
        "weekly": confirmed_pivot_high(weekly["high"], left, right) if len(weekly) else pd.Series(dtype=float),
        "daily": confirmed_pivot_high(daily["high"], left, right) if len(daily) else pd.Series(dtype=float),
        "60m": confirmed_pivot_high(m60["high"], left, right) if len(m60) else pd.Series(dtype=float),
        "exec": confirmed_pivot_high(exec_bars["high"], left, right),
    }
    trendline = rising_trendline(exec_bars["low"], left, right) if chosen["use_trendline"] else None
    ceiling = falling_trendline(exec_bars["high"], left, right) if chosen["use_trendline"] else None
    prior = _prior_day(daily)

    confirm_mode = str(chosen["confirm"])
    need = majority_needed(len(aligned)) if chosen["alignment"] == "majority" else len(aligned)
    setups: list[Setup] = []
    opens = exec_bars["open"].to_numpy(dtype=float)
    highs = exec_bars["high"].to_numpy(dtype=float)
    lows = exec_bars["low"].to_numpy(dtype=float)
    closes = exec_bars["close"].to_numpy(dtype=float)
    vwaps = vwap["vwap"].to_numpy(dtype=float)
    lowers = vwap["lower"].to_numpy(dtype=float)
    uppers = vwap["upper"].to_numpy(dtype=float)
    atrs = width.to_numpy(dtype=float)
    dates = list(exec_bars.index.date)

    for i in range(1, len(exec_bars) - 2):
        if not np.isfinite(atrs[i]) or atrs[i] <= 0 or not np.isfinite(vwaps[i]):
            continue
        level = lowers[i] if chosen["use_bands"] else vwaps[i]
        level_short = uppers[i] if chosen["use_bands"] else vwaps[i]
        if not np.isfinite(level) or not np.isfinite(level_short):
            continue
        tolerance = float(chosen["vwap_tolerance_atr"]) * atrs[i]
        touch = float(chosen["touch_atr"]) * atrs[i]
        long_touch = _touch(opens[i], closes[i - 1], lows[i], closes[i], level, tolerance, touch, side="long")
        short_touch = _touch(opens[i], closes[i - 1], highs[i], closes[i], level_short, tolerance, touch, side="short")
        if not long_touch and not short_touch:
            continue
        confirm_i = i if confirm_mode == "same" else i + 1
        fill_i = confirm_i + 1
        if fill_i >= len(exec_bars):
            continue
        for direction, touched in (("long", long_touch), ("short", short_touch)):
            if not touched:
                continue
            if not _aligned(aligned, i, direction, str(chosen["alignment"]), need):
                continue
            if not _confirmation(exec_bars, confirm_i, direction):
                continue
            if chosen["require_5m_reclaim"]:
                if vwap5 is None or not _reclaim(
                    m5, vwap5, exec_bars.index[i], exec_bars.index[confirm_i], direction
                ):
                    continue
            zone_width = float(chosen["zone_atr"]) * atrs[i]
            if direction == "long":
                levels = _levels_at(support_marks, exec_bars.index[i], right)
                levels.extend(_prior_levels(prior, dates[i], ("low", "close")))
                if trendline is not None and np.isfinite(trendline.iloc[i]):
                    levels.append(float(trendline.iloc[i]))
                zone = _near(lows[i], levels, zone_width)
                if chosen["require_zone"] and zone is None:
                    continue
                resist = _levels_at(resist_marks, exec_bars.index[i], right)
                resist.extend(_prior_levels(prior, dates[i], ("high",)))
                target = _next_level(closes[confirm_i], resist, "long") if chosen["use_level_target"] else None
                stop = float(min(lows[i], lows[confirm_i]))
            else:
                levels = _levels_at(resist_marks, exec_bars.index[i], right)
                levels.extend(_prior_levels(prior, dates[i], ("high", "close")))
                if ceiling is not None and np.isfinite(ceiling.iloc[i]):
                    levels.append(float(ceiling.iloc[i]))
                zone = _near(highs[i], levels, zone_width)
                if chosen["require_zone"] and zone is None:
                    continue
                support = _levels_at(support_marks, exec_bars.index[i], right)
                support.extend(_prior_levels(prior, dates[i], ("low",)))
                target = _next_level(closes[confirm_i], support, "short") if chosen["use_level_target"] else None
                stop = float(max(highs[i], highs[confirm_i]))
            setups.append(
                Setup(
                    symbol=symbol,
                    direction=direction,
                    test_time=exec_bars.index[i],
                    confirm_time=exec_bars.index[confirm_i],
                    fill_time=exec_bars.index[fill_i],
                    vwap=float(vwaps[i]),
                    zone=zone,
                    stop=stop,
                    target=target,
                    atr=float(atrs[i]),
                )
            )
    return setups


def _touch(opened, prior_close, extreme, close, level, tolerance, touch, *, side: str) -> bool:
    if not all(np.isfinite(value) for value in (opened, prior_close, extreme, close, level)):
        return False
    came = opened > level or prior_close > level if side == "long" else opened < level or prior_close < level
    if side == "long":
        reached = extreme <= level + touch
        held = extreme >= level - tolerance
        reclaimed = close > level
    else:
        reached = extreme >= level - touch
        held = extreme <= level + tolerance
        reclaimed = close < level
    return bool(came and reached and held and reclaimed)


def _aligned(states: dict[str, pd.Series], i: int, direction: str, mode: str, need: int) -> bool:
    labels = []
    for series in states.values():
        value = series.iloc[i]
        labels.append("none" if value is None or (isinstance(value, float) and not np.isfinite(value)) else str(value))
    matches = sum(label == ("up" if direction == "long" else "down") for label in labels)
    if mode == "all":
        return matches == len(labels) and len(labels) > 0
    opposite = "down" if direction == "long" else "up"
    if any(label == opposite for label in labels):
        return False
    return matches >= need


def _prior_day(daily: pd.DataFrame) -> dict:
    """Map a session date to the prior completed day's high, low, and close."""
    if daily.empty:
        return {}
    rows = []
    for ts, row in daily.iterrows():
        rows.append((pd.Timestamp(ts).date(), float(row["high"]), float(row["low"]), float(row["close"])))
    out = {}
    for i in range(1, len(rows)):
        out[rows[i][0]] = {"high": rows[i - 1][1], "low": rows[i - 1][2], "close": rows[i - 1][3]}
    return out


def _prior_levels(prior: dict, day, fields: tuple[str, ...]) -> list[float]:
    row = prior.get(day)
    if not row:
        return []
    return [float(row[field]) for field in fields if np.isfinite(row[field])]


def _levels_at(marks: dict[str, pd.Series], when: pd.Timestamp, right: int) -> list[float]:
    levels = []
    for series in marks.values():
        if series is None or series.empty:
            continue
        known = series[series.index < when]
        values = known.to_numpy(dtype=float)
        finite = values[np.isfinite(values)]
        if len(finite):
            levels.extend(float(value) for value in finite[-8:])
    return levels
