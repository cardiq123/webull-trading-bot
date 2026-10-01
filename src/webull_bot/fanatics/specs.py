"""Pre-registered signal rules for specs 1–7.

Fills are not decided here. Each signal points at the bar that completed
the pattern. The simulator buys or sells the next bar's open, except for
the explicit limit-entry variant.
"""

from __future__ import annotations

import bisect

import numpy as np
import pandas as pd

from webull_bot.fanatics.data import INSTRUMENTS
from webull_bot.fanatics.detectors import (
    bearish_fvg,
    bullish_fvg,
    doji_mask,
    fvg_bounds,
    hammer,
    minute_of_day,
    session_key,
    shooting_star,
)
from webull_bot.fanatics.simulate import Signal
from webull_bot.indicators import atr, ema
from webull_bot.patterns import _pivot_points, confirmed_pivot_high, confirmed_pivot_low

INDEX = ("USATECHIDXUSD", "USA500IDXUSD")
FX = ("XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "USDCAD", "NZDUSD")


def resample(frame: pd.DataFrame, rule: str) -> pd.DataFrame:
    out = (
        frame.resample(rule, label="left", closed="left")
        .agg(
            open=("open", "first"),
            high=("high", "max"),
            low=("low", "min"),
            close=("close", "last"),
            volume=("volume", "sum"),
        )
        .dropna(subset=["close"])
    )
    return out


def four_hour(frame: pd.DataFrame) -> pd.DataFrame:
    """4-hour bars anchored at 18:00 ET, so 10:00 and 14:00 are boundaries."""
    local = frame.index.tz_convert("America/New_York")
    origin = pd.Timestamp("2000-01-03 18:00", tz="America/New_York")
    minutes = ((local - origin) / pd.Timedelta(minutes=1)).astype(np.int64)
    bucket = minutes // (4 * 60)
    frame = frame.copy()
    frame["_bucket"] = bucket.to_numpy()
    grouped = frame.groupby("_bucket", sort=True)
    out = grouped.agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
    )
    stamps = [origin + pd.Timedelta(minutes=int(key) * 240) for key in out.index]
    out.index = pd.DatetimeIndex(stamps)
    out = out.dropna(subset=["close"])
    return out


def _clock(frame: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    local = frame.index.tz_convert("America/New_York") if frame.index.tz is not None else frame.index
    minutes = (local.hour * 60 + local.minute).to_numpy(dtype=int)
    dates = np.array([stamp.strftime("%Y-%m-%d") for stamp in local])
    return minutes, dates


def _exit_loc(minutes: np.ndarray, dates: np.ndarray, signal_i: int, exit_minute: int) -> int:
    day = dates[signal_i]
    last = signal_i
    for j in range(signal_i + 1, len(minutes)):
        if dates[j] != day:
            return last
        last = j
        if minutes[j] >= exit_minute:
            return j
    return last


def session_table(frame: pd.DataFrame) -> pd.DataFrame:
    """Prior-day and overnight levels known before the 09:30 cash open."""
    minutes = minute_of_day(frame.index)
    work = pd.DataFrame(
        {
            "high": frame["high"].to_numpy(dtype=float),
            "low": frame["low"].to_numpy(dtype=float),
            "open": frame["open"].to_numpy(dtype=float),
            "minute": minutes,
            "session": session_key(frame.index),
        }
    )
    rows = []
    for key, chunk in work.groupby("session", sort=True):
        rth = chunk[(chunk["minute"] >= 9 * 60 + 30) & (chunk["minute"] < 16 * 60)]
        if rth.empty:
            continue
        overnight = chunk[(chunk["minute"] >= 18 * 60) | (chunk["minute"] < 9 * 60 + 30)]
        asia = chunk[(chunk["minute"] >= 18 * 60) | (chunk["minute"] < 2 * 60)]
        london = chunk[(chunk["minute"] >= 2 * 60) & (chunk["minute"] < 5 * 60)]
        pre_ny = chunk[(chunk["minute"] >= 5 * 60) & (chunk["minute"] < 9 * 60 + 30)]
        asia_low = float(asia["low"].min()) if len(asia) else np.nan
        london_low = float(london["low"].min()) if len(london) else np.nan
        rows.append(
            {
                "session": key,
                "rth_high": float(rth["high"].max()),
                "rth_low": float(rth["low"].min()),
                "rth_open": float(rth["open"].iloc[0]),
                "onh": float(overnight["high"].max()) if len(overnight) else np.nan,
                "onl": float(overnight["low"].min()) if len(overnight) else np.nan,
                "asia_low": asia_low,
                "asia_high": float(asia["high"].max()) if len(asia) else np.nan,
                "london_low": london_low,
                "london_high": float(london["high"].max()) if len(london) else np.nan,
                "asia_taken": bool(np.isfinite(asia_low) and len(pre_ny) and float(pre_ny["low"].min()) < asia_low),
                "london_taken": bool(np.isfinite(london_low) and len(pre_ny) and float(pre_ny["low"].min()) < london_low),
            }
        )
    table = pd.DataFrame(rows)
    if table.empty:
        return table
    table["pdh"] = table["rth_high"].shift(1)
    table["pdl"] = table["rth_low"].shift(1)
    table["prev_onh"] = table["onh"]
    table["prev_onl"] = table["onl"]
    return table.set_index("session")


def _tick(symbol: str) -> float:
    return float(INSTRUMENTS[symbol]["tick"])


def spec1(bars: dict[str, pd.DataFrame], params: dict) -> list[Signal]:
    """PDH/PDL sweep and reclaim. Default N=4, 15-minute bars, exit 12:00."""
    signals: list[Signal] = []
    EXEC.clear()
    rule = {15: "15min", 5: "5min", 60: "1h"}[int(params.get("timeframe", 15))]
    n_bars = int(params.get("n_bars", 4))
    window_end = int(params.get("window_end", 11 * 60 + 30))
    time_exit = int(params.get("time_exit", 12 * 60))
    stop_atr = float(params.get("stop_atr", 1.5))
    target_mode = params.get("target", "pdh")
    bias = bool(params.get("bias", False))
    for symbol in params.get("symbols", INDEX):
        frame = bars.get(symbol)
        if frame is None or frame.empty:
            continue
        view = frame if rule == "5min" else resample(frame, rule)
        EXEC[symbol] = view
        levels = session_table(frame)
        if levels.empty:
            continue
        level_rows = {key: row for key, row in levels.iterrows()}
        minutes, dates = _clock(view)
        high = view["high"].to_numpy(dtype=float)
        low = view["low"].to_numpy(dtype=float)
        close = view["close"].to_numpy(dtype=float)
        width = atr(view, 14).to_numpy(dtype=float)
        tick = _tick(symbol)
        swept_long: set[str] = set()
        swept_short: set[str] = set()
        for i in range(20, len(view)):
            if not (9 * 60 + 30 <= minutes[i] < window_end):
                continue
            row = level_rows.get(dates[i])
            if row is None or not np.isfinite(row["pdh"]) or not np.isfinite(row["pdl"]):
                continue
            if bias and not (bool(row["asia_taken"]) or bool(row["london_taken"])):
                continue
            # Long: first breach of PDL, then a later close back above within N bars.
            if dates[i] not in swept_long and low[i] < row["pdl"] - tick:
                swept_long.add(dates[i])
                end = min(len(view) - 1, i + n_bars)
                for j in range(i, end + 1):
                    if dates[j] != dates[i] or minutes[j] >= window_end:
                        break
                    if close[j] > row["pdl"]:
                        stop = float(np.min(low[i : j + 1]) - tick)
                        entry_proxy = close[j]
                        risk = entry_proxy - stop
                        if risk <= 0 or not np.isfinite(width[j]) or risk > stop_atr * width[j]:
                            break
                        target = float(row["pdh"]) if target_mode == "pdh" else entry_proxy + float(target_mode) * risk
                        if (target - entry_proxy) / risk < 2:
                            break
                        signals.append(
                            Signal(symbol, 1, j, stop, target, _exit_loc(minutes, dates, j, time_exit), window=(9 * 60 + 30, window_end))
                        )
                        break
            if dates[i] not in swept_short and high[i] > row["pdh"] + tick:
                swept_short.add(dates[i])
                end = min(len(view) - 1, i + n_bars)
                for j in range(i, end + 1):
                    if dates[j] != dates[i] or minutes[j] >= window_end:
                        break
                    if close[j] < row["pdh"]:
                        stop = float(np.max(high[i : j + 1]) + tick)
                        entry_proxy = close[j]
                        risk = stop - entry_proxy
                        if risk <= 0 or not np.isfinite(width[j]) or risk > stop_atr * width[j]:
                            break
                        target = float(row["pdl"]) if target_mode == "pdh" else entry_proxy - float(target_mode) * risk
                        if (entry_proxy - target) / risk < 2:
                            break
                        signals.append(
                            Signal(symbol, -1, j, stop, target, _exit_loc(minutes, dates, j, time_exit), window=(9 * 60 + 30, window_end))
                        )
                        break
    return signals


def spec2(bars: dict[str, pd.DataFrame], params: dict) -> list[Signal]:
    """London-killzone FVG, doji, and stacked EMAs. Long-only unless mirrored."""
    signals: list[Signal] = []
    EXEC.clear()
    body_frac = float(params.get("body_frac", 0.30))
    allow_above = bool(params.get("allow_above", False))
    force_hard = bool(params.get("hard_stop", False))
    target_r = params.get("target_r")
    mirror = bool(params.get("mirror", False))
    time_exit = int(params.get("time_exit", 10 * 60))
    for symbol in params.get("symbols", FX):
        frame = bars.get(symbol)
        if frame is None or len(frame) < 100:
            continue
        view = resample(frame, "30min")
        EXEC[symbol] = view
        minutes, dates = _clock(view)
        high = view["high"].to_numpy(dtype=float)
        low = view["low"].to_numpy(dtype=float)
        open_ = view["open"].to_numpy(dtype=float)
        close = view["close"].to_numpy(dtype=float)
        day_high = pd.Series(high, index=view.index).groupby(pd.Index(dates)).cummax().shift(1)
        # Prior completed ET day's high, not the running high.
        by_day = pd.Series(high, index=pd.Index(dates)).groupby(level=0).max().shift(1)
        prior_high = np.array([by_day.get(day, np.nan) for day in dates], dtype=float)
        prior_low = pd.Series(low, index=pd.Index(dates)).groupby(level=0).min().shift(1)
        prior_low = np.array([prior_low.get(day, np.nan) for day in dates], dtype=float)
        del day_high
        e5, e9, e13, e21 = (ema(view["close"], n).to_numpy(dtype=float) for n in (5, 9, 13, 21))
        bull = bullish_fvg(high, low)
        bear = bearish_fvg(high, low)
        doji = doji_mask(open_, high, low, close, body_frac)
        tick = _tick(symbol)
        gold_close = symbol == "XAUUSD" and not force_hard
        for i in range(30, len(view) - 2):
            if not (150 <= minutes[i - 1] <= 180):
                continue
            side = 1 if bull[i] else (-1 if mirror and bear[i] else 0)
            if side == 0:
                continue
            zone_low, zone_high, mid = fvg_bounds(high, low, i, side)
            formation_high = float(np.max(high[i - 2 : i + 1]))
            formation_low = float(np.min(low[i - 2 : i + 1]))
            for d in range(i + 1, min(len(view) - 1, i + 7)):
                if not doji[d]:
                    continue
                if side > 0 and low[d] > mid:
                    continue
                if side < 0 and high[d] < mid:
                    continue
                c = d + 1
                if not (3 * 60 <= minutes[c] < 6 * 60 + 30):
                    continue
                body_low = min(open_[d], close[d])
                body_high = max(open_[d], close[d])
                if side > 0 and close[c] < body_low:
                    continue
                if side < 0 and close[c] > body_high:
                    continue
                if not allow_above:
                    if side > 0 and close[c] > formation_high:
                        continue
                    if side < 0 and close[c] < formation_low:
                        continue
                stack = all(
                    e5[k] > e9[k] > e13[k] > e21[k] if side > 0 else e5[k] < e9[k] < e13[k] < e21[k]
                    for k in range(c - 2, c + 1)
                    if k >= 0 and np.isfinite(e21[k])
                )
                rising = e21[c] > e21[c - 3] if side > 0 else e21[c] < e21[c - 3]
                if not stack or not rising or not np.isfinite(e21[c]):
                    continue
                entry_proxy = close[c]
                if gold_close:
                    stop = entry_proxy - side * max(10 * tick, 0.002 * entry_proxy)
                    close_stop = float(low[d] if side > 0 else high[d])
                else:
                    stop = float((low[d] - tick) if side > 0 else (high[d] + tick))
                    close_stop = None
                risk = side * (entry_proxy - stop)
                if risk <= 0:
                    continue
                if target_r is None:
                    target = float(prior_high[c] if side > 0 else prior_low[c])
                    reward = side * (target - entry_proxy)
                    if not np.isfinite(target) or reward / risk < 3:
                        continue
                else:
                    target = entry_proxy + side * float(target_r) * risk
                signals.append(
                    Signal(
                        symbol,
                        side,
                        c,
                        stop,
                        target,
                        _exit_loc(minutes, dates, c, time_exit),
                        close_stop=close_stop,
                        window=(3 * 60, 6 * 60 + 30),
                    )
                )
                break
    return signals


def spec3(bars: dict[str, pd.DataFrame], areas: dict[str, pd.DataFrame], params: dict) -> list[Signal]:
    """Failed auction back inside the prior session's value area. Volume is a proxy."""
    signals: list[Signal] = []
    EXEC.clear()
    k_bars = int(params.get("k_bars", 3))
    vol_mult = float(params.get("vol_mult", 1.5))
    stop_ticks = int(params.get("stop_ticks", 40))
    target_mode = params.get("target", "poc")
    london = bool(params.get("london", False))
    for symbol in params.get("symbols", INDEX):
        frame = bars.get(symbol)
        area = areas.get(symbol)
        if frame is None or area is None or area.empty:
            continue
        view = frame
        EXEC[symbol] = view
        minutes, dates = _clock(view)
        area = area.sort_values("date")
        shifted = area.copy()
        shifted["vah"] = area["vah"].shift(1)
        shifted["val"] = area["val"].shift(1)
        shifted["poc"] = area["poc"].shift(1)
        shifted = shifted.drop_duplicates("date").set_index("date")
        high = view["high"].to_numpy(dtype=float)
        low = view["low"].to_numpy(dtype=float)
        close = view["close"].to_numpy(dtype=float)
        volume = view["volume"].to_numpy(dtype=float)
        tick = _tick(symbol)
        used: set[tuple] = set()
        for i in range(25, len(view) - 1):
            if london:
                inside = 3 * 60 <= minutes[i] < 8 * 60 + 30
            else:
                inside = (9 * 60 + 45 <= minutes[i] < 11 * 60 + 30) or (13 * 60 + 30 <= minutes[i] < 15 * 60 + 30)
            if not inside or dates[i] not in shifted.index:
                continue
            row = shifted.loc[dates[i]]
            vah, val, poc = float(row["vah"]), float(row["val"]), float(row["poc"])
            if not (np.isfinite(vah) and np.isfinite(val) and np.isfinite(poc)):
                continue
            avg = float(np.mean(volume[i - 20 : i])) if i >= 20 else np.nan
            # Short: a prior bar closed above VAH, this bar closes back inside.
            if (dates[i], "s") not in used and close[i] <= vah:
                for b in range(max(0, i - k_bars), i):
                    if close[b] > vah + 2 * tick and dates[b] == dates[i]:
                        if not np.isfinite(avg) or volume[i] < vol_mult * avg:
                            break
                        extreme = float(np.max(high[b : i + 1]))
                        stop = extreme + tick
                        entry_proxy = close[i]
                        risk = stop - entry_proxy
                        if risk <= 0 or risk > stop_ticks * tick:
                            break
                        target = poc if target_mode == "poc" else val
                        if (entry_proxy - target) / risk < 1.5:
                            break
                        signals.append(
                            Signal(symbol, -1, i, stop, float(target), _exit_loc(minutes, dates, i, 16 * 60), be_r=1.0, window=_window(london))
                        )
                        used.add((dates[i], "s"))
                        break
            if (dates[i], "l") not in used and close[i] >= val:
                for b in range(max(0, i - k_bars), i):
                    if close[b] < val - 2 * tick and dates[b] == dates[i]:
                        if not np.isfinite(avg) or volume[i] < vol_mult * avg:
                            break
                        extreme = float(np.min(low[b : i + 1]))
                        stop = extreme - tick
                        entry_proxy = close[i]
                        risk = entry_proxy - stop
                        if risk <= 0 or risk > stop_ticks * tick:
                            break
                        target = poc if target_mode == "poc" else vah
                        if (target - entry_proxy) / risk < 1.5:
                            break
                        signals.append(
                            Signal(symbol, 1, i, stop, float(target), _exit_loc(minutes, dates, i, 16 * 60), be_r=1.0, window=_window(london))
                        )
                        used.add((dates[i], "l"))
                        break
    return signals


def _window(london: bool) -> tuple[int, int]:
    if london:
        return (3 * 60, 8 * 60 + 30)
    return (9 * 60 + 45, 15 * 60 + 30)


def _edge_frame(frame: pd.DataFrame, kind: str) -> pd.DataFrame:
    if kind == "4h":
        return four_hour(frame)
    if kind == "30m":
        return resample(frame, "30min")
    if kind == "1h":
        return resample(frame, "1h")
    raise ValueError(kind)


def spec4(bars: dict[str, pd.DataFrame], params: dict) -> list[Signal]:
    """Edge sweep plus a higher-volume rejection candle."""
    signals: list[Signal] = []
    EXEC.clear()
    kind = params.get("bar", "1h")
    clocks = params.get("clocks")
    break_entry = bool(params.get("break_entry", False))
    overnight = bool(params.get("overnight", False))
    for symbol in params.get("symbols", INDEX):
        frame = bars.get(symbol)
        if frame is None or frame.empty:
            continue
        levels = session_table(frame)
        view = _edge_frame(frame, kind)
        EXEC[symbol] = view
        minutes, dates = _clock(view)
        high = view["high"].to_numpy(dtype=float)
        low = view["low"].to_numpy(dtype=float)
        open_ = view["open"].to_numpy(dtype=float)
        close = view["close"].to_numpy(dtype=float)
        volume = view["volume"].to_numpy(dtype=float)
        star = shooting_star(open_, high, low, close)
        pin = hammer(open_, high, low, close)
        tick = _tick(symbol)
        for i in range(2, len(view) - 1):
            if kind == "1h" and not (10 * 60 <= minutes[i] < 16 * 60):
                continue
            if clocks is not None and minutes[i] not in clocks:
                continue
            if dates[i] not in levels.index:
                continue
            row = levels.loc[dates[i]]
            if volume[i] <= volume[i - 1]:
                continue
            if star[i]:
                for edge, target in ((row["pdh"], row["pdl"]), (row["onh"], row["onl"])):
                    if not (np.isfinite(edge) and np.isfinite(target)):
                        continue
                    if high[i] > edge and close[i] < edge:
                        stop = float(high[i] + tick)
                        _add_edge(signals, symbol, -1, i, close[i], stop, float(target), minutes, dates, break_entry, low, high, overnight, tick)
                        break
            if pin[i]:
                for edge, target in ((row["pdl"], row["pdh"]), (row["onl"], row["onh"])):
                    if not (np.isfinite(edge) and np.isfinite(target)):
                        continue
                    if low[i] < edge and close[i] > edge:
                        stop = float(low[i] - tick)
                        _add_edge(signals, symbol, 1, i, close[i], stop, float(target), minutes, dates, break_entry, low, high, overnight, tick)
                        break
    return signals


def _add_edge(signals, symbol, side, i, entry_proxy, stop, target, minutes, dates, break_entry, low, high, overnight, tick):
    risk = side * (entry_proxy - stop)
    reward = side * (target - entry_proxy)
    if risk <= 0 or reward / risk < 1.5:
        return
    exit_minute = 20 * 60 if overnight else 16 * 60
    if break_entry:
        trigger = (low[i] - tick) if side < 0 else (high[i] + tick)
        for j in range(i + 1, min(len(low), i + 4)):
            if dates[j] != dates[i]:
                return
            traded = low[j] <= trigger if side < 0 else high[j] >= trigger
            if traded:
                signals.append(
                    Signal(
                        symbol, side, j, stop, target, _exit_loc(minutes, dates, j, exit_minute),
                        window=(minutes[i], exit_minute), limit_entry=trigger,
                    )
                )
                return
        return
    signals.append(
        Signal(symbol, side, i, stop, target, _exit_loc(minutes, dates, i, exit_minute), window=(9 * 60 + 30, 16 * 60))
    )


def spec5(bars: dict[str, pd.DataFrame], params: dict) -> list[Signal]:
    """Engineered-liquidity sweep. Swings are confirmed before they are used."""
    signals: list[Signal] = []
    EXEC.clear()
    left = int(params.get("left", 2))
    right = int(params.get("right", 2))
    use_pct = bool(params.get("use_pct", False))
    limit = bool(params.get("limit", False))
    use_hour = bool(params.get("use_hour", False))
    for symbol in params.get("symbols", ("USATECHIDXUSD",)):
        frame = bars.get(symbol)
        if frame is None or len(frame) < 200:
            continue
        view = frame
        EXEC[symbol] = view
        minutes, dates = _clock(view)
        high = view["high"].to_numpy(dtype=float)
        low = view["low"].to_numpy(dtype=float)
        close = view["close"].to_numpy(dtype=float)
        width = atr(view, 14).to_numpy(dtype=float)
        tick = _tick(symbol)
        highs = _pivot_points(confirmed_pivot_high(view["high"], left, right), right)
        lows = _pivot_points(confirmed_pivot_low(view["low"], left, right), right)
        hour = resample(frame, "1h") if use_hour else None
        hour_highs = _pivot_points(confirmed_pivot_high(hour["high"], 2, 2), 2) if hour is not None else []
        hour_lows = _pivot_points(confirmed_pivot_low(hour["low"], 2, 2), 2) if hour is not None else []
        tol = (lambda price: price * 0.0005) if use_pct else (lambda price: 4 * tick)
        for side, swings, other in ((1, highs, lows), (-1, lows, highs)):
            hour_pool = _hour_pool(hour, hour_highs if side > 0 else hour_lows, view.index, len(view)) if use_hour else []
            other_pivots = [item[0] for item in other]
            for index, (pivot_i, price, confirm_i) in enumerate(swings):
                earlier = None
                if use_hour:
                    source = [item for item in hour_pool if item[2] < confirm_i][-8:]
                else:
                    source = []
                    for prev in reversed(swings[max(0, index - 40) : index]):
                        if prev[0] < pivot_i - 300:
                            break
                        if prev[0] <= pivot_i - 10:
                            source.append(prev)
                for prev_i, prev_price, prev_confirm in source:
                    del prev_i, prev_confirm
                    if abs(prev_price - price) <= tol(price) and (
                        (side > 0 and close[pivot_i] < prev_price) or (side < 0 and close[pivot_i] > prev_price)
                    ):
                        earlier = prev_price
                        break
                if earlier is None:
                    continue
                # The digest uses the first confirmed swing after the engineered pivot.
                # A miss on that swing is not a reason to shop for a later one.
                start_at = bisect.bisect_right(other_pivots, pivot_i)
                for low_i, low_price, low_confirm in other[start_at:]:
                    if low_confirm <= confirm_i:
                        continue
                    if low_confirm + 1 >= len(view):
                        break
                    sweep_at = None
                    for t in range(low_confirm + 1, min(len(view), low_confirm + 40)):
                        if (side > 0 and low[t] < low_price - tick) or (side < 0 and high[t] > low_price + tick):
                            sweep_at = t
                            break
                    if sweep_at is None:
                        break
                    if limit:
                        if not (9 * 60 + 45 <= minutes[sweep_at] < 11 * 60 + 30):
                            break
                        pad = max(4 * tick, 0.25 * width[sweep_at] if np.isfinite(width[sweep_at]) else 4 * tick)
                        stop = low_price - pad if side > 0 else low_price + pad
                        entry = low_price - tick if side > 0 else low_price + tick
                        target = earlier
                        risk = side * (entry - stop)
                        reward = side * (target - entry)
                        if risk <= 0 or reward / risk < 3:
                            continue
                        signals.append(
                            Signal(
                                symbol, side, sweep_at, float(stop), float(target),
                                _exit_loc(minutes, dates, sweep_at, 11 * 60 + 30),
                                window=(9 * 60 + 45, 11 * 60 + 30), limit_entry=float(entry),
                            )
                        )
                        break
                    closes_beyond = 0
                    for t in range(sweep_at, min(len(view) - 1, sweep_at + 20)):
                        beyond = close[t] < low_price if side > 0 else close[t] > low_price
                        if beyond:
                            closes_beyond += 1
                            if closes_beyond >= 2:
                                break
                            continue
                        closes_beyond = 0
                        reclaimed = close[t] > low_price if side > 0 else close[t] < low_price
                        if not reclaimed:
                            continue
                        if not (9 * 60 + 45 <= minutes[t] < 11 * 60 + 30):
                            continue
                        extreme = float(np.min(low[sweep_at : t + 1]) if side > 0 else np.max(high[sweep_at : t + 1]))
                        stop = extreme - tick if side > 0 else extreme + tick
                        entry_proxy = close[t]
                        risk = side * (entry_proxy - stop)
                        reward = side * (earlier - entry_proxy)
                        if risk <= 0 or reward / risk < 3:
                            continue
                        signals.append(
                            Signal(
                                symbol, side, t, float(stop), float(earlier),
                                _exit_loc(minutes, dates, t, 11 * 60 + 30),
                                window=(9 * 60 + 45, 11 * 60 + 30),
                            )
                        )
                        break
                    break
    return signals


def _hour_pool(hour, points, exec_index, confirm_i):
    """Map hourly pivot confirmation times onto the 5-minute index."""
    out = []
    for pivot_i, price, confirm_i_h in points:
        if confirm_i_h >= len(hour.index):
            continue
        stamp = hour.index[confirm_i_h]
        loc = int(exec_index.searchsorted(stamp))
        if loc < confirm_i:
            out.append((pivot_i, price, loc))
    return out


def spec6(bars: dict[str, pd.DataFrame], params: dict) -> list[Signal]:
    """10:00 sweep. Each symbol is scanned; SMT still needs the ES symbol in the book."""
    symbols = list(params.get("symbols") or ["USATECHIDXUSD"])
    if len(symbols) == 1:
        return _spec6_symbol(bars, params)
    signals: list[Signal] = []
    frames: dict[str, pd.DataFrame] = {}
    for symbol in symbols:
        child = dict(params)
        child["symbols"] = [symbol]
        signals.extend(_spec6_symbol(bars, child))
        frames.update(EXEC)
    EXEC.clear()
    EXEC.update(frames)
    return signals


def _spec6_symbol(bars: dict[str, pd.DataFrame], params: dict) -> list[Signal]:
    """10:00 sweep back through the 09:00 hour, target the 10:00 open."""
    signals: list[Signal] = []
    stop_ticks = int(params.get("stop_ticks", 40))
    target_mode = params.get("target", "open")
    use_smt = bool(params.get("smt", False))
    context = bool(params.get("context", False))
    be = bool(params.get("be", True))
    EXEC.clear()
    symbol = (params.get("symbols") or ["USATECHIDXUSD"])[0]
    es_name = params.get("es_symbol", "USA500IDXUSD")
    nq = bars.get(symbol)
    es = bars.get(es_name) if use_smt else None
    if nq is None:
        return signals
    EXEC[symbol] = nq
    minutes, dates = _clock(nq)
    high = nq["high"].to_numpy(dtype=float)
    low = nq["low"].to_numpy(dtype=float)
    open_ = nq["open"].to_numpy(dtype=float)
    close = nq["close"].to_numpy(dtype=float)
    tick = _tick(symbol)
    es_high, es_minutes, es_dates = _aligned_high(es, nq.index) if es is not None else (None, None, None)
    levels = session_table(nq) if context else None
    # Group bars by day once.
    day_starts = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    day_starts = np.append(day_starts, len(dates))
    for a, b in zip(day_starts[:-1], day_starts[1:]):
        day_min = minutes[a:b]
        h9_mask = (day_min >= 9 * 60) & (day_min < 10 * 60)
        if not np.any(h9_mask):
            continue
        h9 = float(np.max(high[a:b][h9_mask]))
        l9 = float(np.min(low[a:b][h9_mask]))
        ten = np.flatnonzero(day_min == 10 * 60)
        if ten.size == 0:
            continue
        o10 = float(open_[a + int(ten[0])])
        es_h9 = None
        if use_smt and es_high is not None:
            es_h9 = _es_hour_high(es, dates[a])
        swept_high = False
        swept_low = False
        es_swept = False
        for i in range(a, b):
            if not (10 * 60 <= minutes[i] < 10 * 60 + 45):
                continue
            if high[i] > h9:
                swept_high = True
            if low[i] < l9:
                swept_low = True
            if es_h9 is not None and es_high is not None and i < len(es_high) and es_high[i] > es_h9:
                es_swept = True
            if context and levels is not None and dates[i] in levels.index:
                row = levels.loc[dates[i]]
                span = row["pdh"] - row["pdl"]
                top = np.isfinite(span) and span > 0 and row["rth_open"] >= row["pdl"] + 0.5 * span
                bottom = np.isfinite(span) and span > 0 and row["rth_open"] <= row["pdl"] + 0.5 * span
            else:
                top = bottom = True
            if swept_high and close[i] < h9 and close[i] < open_[i] and top:
                if use_smt and es_swept:
                    continue
                extreme = float(np.max(high[a + int(ten[0]) : i + 1]))
                stop = extreme + 2 * tick
                entry_proxy = close[i]
                risk = stop - entry_proxy
                if risk <= 0 or risk > stop_ticks * tick:
                    swept_high = False
                    continue
                target = o10 if target_mode == "open" else entry_proxy - 2 * risk
                if entry_proxy - target <= 0:
                    continue
                signals.append(
                    Signal(
                        symbol, -1, i, stop, float(target), _exit_loc(minutes, dates, i, 11 * 60 + 30),
                        be_r=1.0 if be else None, window=(10 * 60, 10 * 60 + 45),
                    )
                )
                break
            if swept_low and close[i] > l9 and close[i] > open_[i] and bottom:
                if use_smt and es_h9 is not None and _es_held_low(es, dates[a], l9_time=dates[a]):
                    # Mirror SMT: skip the long if ES also swept its 09:00 low.
                    if _es_swept_low(es, dates[a]):
                        continue
                extreme = float(np.min(low[a + int(ten[0]) : i + 1]))
                stop = extreme - 2 * tick
                entry_proxy = close[i]
                risk = entry_proxy - stop
                if risk <= 0 or risk > stop_ticks * tick:
                    swept_low = False
                    continue
                target = o10 if target_mode == "open" else entry_proxy + 2 * risk
                if target - entry_proxy <= 0:
                    continue
                signals.append(
                    Signal(
                        symbol, 1, i, stop, float(target), _exit_loc(minutes, dates, i, 11 * 60 + 30),
                        be_r=1.0 if be else None, window=(10 * 60, 10 * 60 + 45),
                    )
                )
                break
    return signals


def _es_hour_high(es: pd.DataFrame, day: str) -> float | None:
    minutes, dates = _clock(es)
    mask = (dates == day) & (minutes >= 9 * 60) & (minutes < 10 * 60)
    if not np.any(mask):
        return None
    return float(np.max(es["high"].to_numpy(dtype=float)[mask]))


def _es_swept_low(es: pd.DataFrame, day: str) -> bool:
    minutes, dates = _clock(es)
    high = es["low"].to_numpy(dtype=float)
    mask9 = (dates == day) & (minutes >= 9 * 60) & (minutes < 10 * 60)
    mask10 = (dates == day) & (minutes >= 10 * 60) & (minutes < 10 * 60 + 45)
    if not np.any(mask9) or not np.any(mask10):
        return False
    l9 = float(np.min(high[mask9]))
    return bool(np.any(high[mask10] < l9))


def _aligned_high(es: pd.DataFrame, index: pd.DatetimeIndex):
    aligned = es["high"].reindex(index, method=None)
    return aligned.to_numpy(dtype=float), None, None


def _es_held_low(*_args, **_kwargs) -> bool:
    return True


def spec7(bars: dict[str, pd.DataFrame], params: dict) -> list[Signal]:
    """Opening-range breakout. Delta is unavailable, so the volume rule is a proxy."""
    signals: list[Signal] = []
    EXEC.clear()
    or_minutes = int(params.get("or_minutes", 5))
    target_r = float(params.get("target_r", 2.0))
    opposite = bool(params.get("opposite_stop", False))
    atr_filter = bool(params.get("atr_filter", True))
    or_bars = max(or_minutes // 5, 1)
    for symbol in params.get("symbols", INDEX):
        frame = bars.get(symbol)
        if frame is None or frame.empty:
            continue
        view = frame
        EXEC[symbol] = view
        minutes, dates = _clock(view)
        high = view["high"].to_numpy(dtype=float)
        low = view["low"].to_numpy(dtype=float)
        close = view["close"].to_numpy(dtype=float)
        volume = view["volume"].to_numpy(dtype=float)
        width = atr(view, 14).to_numpy(dtype=float)
        tick = _tick(symbol)
        day_starts = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
        day_starts = np.append(day_starts, len(dates))
        for a, b in zip(day_starts[:-1], day_starts[1:]):
            opens = np.flatnonzero(minutes[a:b] == 9 * 60 + 30)
            if opens.size == 0:
                continue
            start = a + int(opens[0])
            stop = start + or_bars
            if stop >= b:
                continue
            or_high = float(np.max(high[start:stop]))
            or_low = float(np.min(low[start:stop]))
            or_range = or_high - or_low
            if atr_filter and np.isfinite(width[stop]):
                if or_range > 1.5 * width[stop] or or_range < 0.3 * width[stop]:
                    continue
            taken = False
            for i in range(stop, b):
                if minutes[i] >= 11 * 60 + 30:
                    break
                avg = float(np.mean(volume[i - 20 : i])) if i >= 20 else np.nan
                if not np.isfinite(avg) or volume[i] < 1.5 * avg:
                    continue
                side = 0
                if close[i] > or_high:
                    side = 1
                elif close[i] < or_low:
                    side = -1
                if side == 0:
                    continue
                if opposite:
                    stop_price = or_low - tick if side > 0 else or_high + tick
                else:
                    mid = (or_high + or_low) / 2.0
                    stop_price = mid
                entry_proxy = close[i]
                risk = side * (entry_proxy - stop_price)
                if risk <= 0 or risk > 40 * tick:
                    continue
                target = entry_proxy + side * target_r * risk
                signals.append(
                    Signal(
                        symbol, side, i, float(stop_price), float(target),
                        _exit_loc(minutes, dates, i, 11 * 60 + 30), be_r=1.0,
                        window=(9 * 60 + 30, 11 * 60 + 30),
                    )
                )
                taken = True
                break
            del taken
    return signals


EXEC: dict[str, pd.DataFrame] = {}


GRIDS = {
    1: [
        {},
        {"n_bars": 1},
        {"n_bars": 8},
        {"window_end": 10 * 60 + 30},
        {"time_exit": 11 * 60},
        {"bias": True},
    ],
    2: [
        {},
        {"body_frac": 0.20},
        {"allow_above": True},
        {"hard_stop": True},
        {"target_r": 5},
        {"target_r": 20},
    ],
    3: [
        {},
        {"k_bars": 1},
        {"k_bars": 6},
        {"stop_ticks": 20},
        {"stop_ticks": 60},
        {"london": True},
    ],
    4: [
        {},
        {"bar": "4h", "clocks": (10 * 60, 14 * 60)},
        {"bar": "4h"},
        {"bar": "30m"},
        {"break_entry": True},
        {"overnight": True},
    ],
    5: [
        {},
        {"left": 1, "right": 1},
        {"use_pct": True},
        {"limit": True},
        {"use_hour": True},
        {"left": 3, "right": 3},
    ],
    6: [
        {},
        {"smt": True},
        {"context": True},
        {"target": "2r"},
        {"stop_ticks": 20},
        {"be": False},
    ],
    7: [
        {},
        {"or_minutes": 15},
        {"or_minutes": 30},
        {"opposite_stop": True},
        {"target_r": 1.5},
        {"atr_filter": False},
    ],
}

SIM = {
    1: {"risk": 0.005, "max_trades_per_day": 2},
    2: {"risk": 0.005, "max_trades_per_day": 1, "day_win_r": 100.0},
    3: {"risk": 0.0025, "max_consecutive_losses": 3, "max_trades_per_day": 3, "day_win_r": 5.0},
    4: {"risk": 0.005, "max_trades_per_day": 2},
    # 0.5% risk and a 3R day stop is a 1.5% equity day-loss limit. That limit is fixed.
    5: {"risk": 0.005, "max_trades_per_day": 2},
    6: {"risk": 0.005, "max_trades_per_day": 2, "day_win_r": 2.0},
    7: {"risk": 0.005, "max_trades_per_day": 1},
}


def generate(spec_id: int, bars: dict[str, pd.DataFrame], params: dict, areas: dict | None = None):
    """Return ``(signals, execution_frames)``. Locs index the execution frames."""
    merged = dict(params)
    if spec_id == 1:
        signals = spec1(bars, merged)
    elif spec_id == 2:
        signals = spec2(bars, merged)
    elif spec_id == 3:
        signals = spec3(bars, areas or {}, merged)
    elif spec_id == 4:
        signals = spec4(bars, merged)
    elif spec_id == 5:
        signals = spec5(bars, merged)
    elif spec_id == 6:
        signals = spec6(bars, merged)
    elif spec_id == 7:
        signals = spec7(bars, merged)
    else:
        raise KeyError(spec_id)
    return signals, dict(EXEC)
