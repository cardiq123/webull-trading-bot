"""Objective chop, frozen before the chop study was scored.

A bar is chop only when four things are true together at that close:

* volume is quiet: this bar is below 0.80 times the prior 20-bar average,
  or that 20-bar average is below 0.80 times the prior 60-bar average and this
  bar is still at most 1.20 times its own 20-bar average. The second clause
  keeps the middle of a dry base. An expanding bar is not quiet.
* the range is narrow: Bollinger bandwidth is in the bottom 20% of the
  last 120 bars, or the bar's range is under 0.75 times the prior 20-bar
  average range
* the 9 and 20 EMAs are close, flat, and have crossed at least three times
  in 20 bars
* close has crossed VWAP at least three times in 20 bars

ADX below 20 or a choppiness index above 61.8 is an optional stricter
reading. It is not required for the default flag. Nothing here places orders.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from webull_bot.chart_reads.detect import Setup, strong_candle
from webull_bot.indicators import atr, ema

REL_VOLUME_MAX = 0.80
VOLUME_WINDOW = 20
VOLUME_REGIME = 60
# A bar inside an already-quiet regime can sit near its own 20-bar average.
# Above this multiple it is no longer the dry-up, even if the regime is quiet.
REGIME_BAR_MAX = 1.20
NARROW_LOOKBACK = 120
NARROW_PERCENTILE = 0.20
RANGE_CONTRACTION = 0.75
BB_WINDOW = 20
EMA_FAST = 9
EMA_SLOW = 20
EMA_SEP_ATR = 0.35
EMA_SLOPE_BARS = 10
EMA_SLOPE_ATR = 0.50
CROSS_BARS = 20
MIN_CROSSES = 3
ADX_WINDOW = 14
ADX_MAX = 20.0
CHOP_WINDOW = 14
CHOP_MIN = 61.8
# Breakout from a chop box. Ties to setup D's confirming candle and measured move.
BOX_BARS = 10
MIN_CHOP_BARS = 6
MIN_HEIGHT_ATR = 0.40
MAX_HEIGHT_ATR = 6.0
BREAK_BUFFER_ATR = 0.10
EXPAND_VOLUME = 1.5
BREAK_COOLDOWN = 10
BODY = 0.50
CLOSE_FRAC = 2.0 / 3.0
FILTER_MIN_TRADES = 20


def filter_helps(baseline: dict, variant: dict, base_losers: int, variant_losers: int) -> bool:
    """Pre-registered reading of the no-trade filter. Not a new gate.

    Out-of-sample expectancy is higher, the book took fewer losing trades,
    and at least 20 trades remain.
    """
    trades = int(variant.get("trades") or 0)
    if trades < FILTER_MIN_TRADES:
        return False
    base_exp = baseline.get("expectancy")
    new_exp = variant.get("expectancy")
    if base_exp is None or new_exp is None:
        return False
    if not np.isfinite(base_exp) or not np.isfinite(new_exp):
        return False
    if not float(new_exp) > float(base_exp):
        return False
    return int(variant_losers) < int(base_losers)


def features(frame: pd.DataFrame) -> pd.DataFrame:
    """One row per bar. ``chop`` on bar t uses only bars through t."""
    close = frame["close"].astype(float)
    high = frame["high"].astype(float)
    low = frame["low"].astype(float)
    volume = frame["volume"].astype(float) if "volume" in frame.columns else pd.Series(np.nan, index=frame.index)
    width = atr(frame)
    dates = _dates(frame.index)
    one_bar = len(set(dates.tolist())) == len(dates)
    fast = ema(close, EMA_FAST)
    slow = ema(close, EMA_SLOW)
    prior_20 = volume.shift(1).rolling(VOLUME_WINDOW, min_periods=VOLUME_WINDOW).mean()
    prior_60 = volume.shift(1).rolling(VOLUME_REGIME, min_periods=VOLUME_REGIME).mean()
    rel = volume / prior_20
    regime = prior_20 < REL_VOLUME_MAX * prior_60
    bar_range = high - low
    avg_range = bar_range.shift(1).rolling(VOLUME_WINDOW, min_periods=VOLUME_WINDOW).mean()
    contracted = bar_range < RANGE_CONTRACTION * avg_range
    bandwidth = _bandwidth(close)
    rank = _percentile_rank(bandwidth.to_numpy(dtype=float), NARROW_LOOKBACK)
    narrow = contracted.fillna(False).to_numpy() | (rank <= NARROW_PERCENTILE)
    sep = (fast - slow).abs() <= EMA_SEP_ATR * width
    slope = (slow - slow.shift(EMA_SLOPE_BARS)).abs() <= EMA_SLOPE_ATR * width
    ema_crosses = _cross_count(fast - slow, CROSS_BARS)
    tangled = sep.fillna(False) & slope.fillna(False) & (ema_crosses >= MIN_CROSSES)
    vwap = _vwap(frame, dates, one_bar)
    vwap_crosses = _cross_count(close - vwap, CROSS_BARS)
    oscillating = vwap_crosses >= MIN_CROSSES
    quiet = (rel < REL_VOLUME_MAX) | (regime.fillna(False) & (rel <= REGIME_BAR_MAX))
    adx_value = _adx(frame)
    choppiness = _choppiness(frame)
    chop = quiet.fillna(False).to_numpy() & narrow & tangled.fillna(False).to_numpy() & oscillating.fillna(False).to_numpy()
    soft = (adx_value < ADX_MAX) | (choppiness > CHOP_MIN)
    strict = chop & soft.fillna(False).to_numpy()
    return pd.DataFrame(
        {
            "rel_volume": rel.to_numpy(dtype=float),
            "narrow": narrow,
            "tangled": tangled.fillna(False).to_numpy(),
            "vwap_crosses": vwap_crosses.to_numpy(dtype=float),
            "adx": adx_value.to_numpy(dtype=float),
            "choppiness": choppiness.to_numpy(dtype=float),
            "chop": chop,
            "strict": strict,
            "atr": width.to_numpy(dtype=float),
            "vwap": vwap.to_numpy(dtype=float),
            "ema9": fast.to_numpy(dtype=float),
            "ema20": slow.to_numpy(dtype=float),
            "bandwidth_rank": rank,
        },
        index=frame.index,
    )


def chop_mask(frame: pd.DataFrame) -> pd.Series:
    return features(frame)["chop"].astype(bool)


def time_in_chop(frame: pd.DataFrame) -> dict:
    """Share of bars where the chop decision is defined."""
    feat = features(frame)
    ready = feat["rel_volume"].notna() & feat["ema20"].notna() & feat["vwap"].notna() & feat["atr"].notna()
    usable = feat.loc[ready]
    bars = int(len(usable))
    if bars == 0:
        return {"bars": 0, "chop_bars": 0, "share": 0.0, "strict_share": 0.0}
    return {
        "bars": bars,
        "chop_bars": int(usable["chop"].sum()),
        "share": float(usable["chop"].mean()),
        "strict_share": float(usable["strict"].mean()),
    }


def find_chop_breakouts(frame: pd.DataFrame, *, symbol: str = "") -> list[Setup]:
    """Close out of a low-volume chop box on expanding volume and a confirming candle.

    The box is the prior 10 bars. At least 6 of them are chop. The fill is the
    next bar's open. The stop is the signal bar's low on a long and its high
    on a short. The reference is the box height measured from the broken side.
    """
    if frame is None or len(frame) < BOX_BARS + VOLUME_WINDOW + 2:
        return []
    feat = features(frame)
    flags = feat["chop"].to_numpy(dtype=bool)
    width = feat["atr"].to_numpy(dtype=float)
    high = frame["high"].to_numpy(dtype=float)
    low = frame["low"].to_numpy(dtype=float)
    open_ = frame["open"].to_numpy(dtype=float)
    close = frame["close"].to_numpy(dtype=float)
    volume = frame["volume"].to_numpy(dtype=float) if "volume" in frame.columns else np.full(len(frame), np.nan)
    index = frame.index
    found: list[Setup] = []
    last = -BREAK_COOLDOWN
    for t in range(BOX_BARS + VOLUME_WINDOW, len(frame) - 1):
        if t - last < BREAK_COOLDOWN:
            continue
        if int(flags[t - BOX_BARS : t].sum()) < MIN_CHOP_BARS:
            continue
        scale = width[t]
        if not np.isfinite(scale) or scale <= 0:
            continue
        box_high = float(np.nanmax(high[t - BOX_BARS : t]))
        box_low = float(np.nanmin(low[t - BOX_BARS : t]))
        height = box_high - box_low
        if not np.isfinite(height) or height < MIN_HEIGHT_ATR * scale or height > MAX_HEIGHT_ATR * scale:
            continue
        prior = volume[t - VOLUME_WINDOW : t]
        baseline = float(np.nanmean(prior)) if np.isfinite(prior).any() else float("nan")
        if not np.isfinite(baseline) or baseline <= 0 or not np.isfinite(volume[t]):
            continue
        if volume[t] / baseline <= EXPAND_VOLUME:
            continue
        direction = ""
        level = float("nan")
        if close[t] >= box_high + BREAK_BUFFER_ATR * scale:
            direction = "long"
            level = box_high
            stop = low[t]
            reference = level + height
        elif close[t] <= box_low - BREAK_BUFFER_ATR * scale:
            direction = "short"
            level = box_low
            stop = high[t]
            reference = level - height
        else:
            continue
        if not strong_candle(open_[t], high[t], low[t], close[t], direction, BODY, CLOSE_FRAC):
            continue
        if not np.isfinite(stop):
            continue
        if direction == "long" and stop >= close[t]:
            continue
        if direction == "short" and stop <= close[t]:
            continue
        found.append(
            Setup(
                symbol=symbol,
                direction=direction,
                kind="chop",
                signal_time=index[t],
                fill_time=index[t + 1],
                anchor_time=index[t - BOX_BARS],
                stop=float(stop),
                atr=float(scale),
                reference=float(reference),
            )
        )
        last = t
    return found


def _dates(index) -> np.ndarray:
    stamps = pd.DatetimeIndex(index)
    if stamps.tz is not None:
        stamps = stamps.tz_convert("America/New_York")
    return np.array([stamp.date() for stamp in stamps])


def _bandwidth(close: pd.Series) -> pd.Series:
    mid = close.rolling(BB_WINDOW, min_periods=BB_WINDOW).mean()
    std = close.rolling(BB_WINDOW, min_periods=BB_WINDOW).std(ddof=0)
    return (4.0 * std) / mid.replace(0.0, np.nan)


def _percentile_rank(values: np.ndarray, lookback: int) -> np.ndarray:
    """Share of the last ``lookback`` readings at or below the current value."""
    out = np.full(len(values), np.nan)
    for index in range(lookback - 1, len(values)):
        window = values[index - lookback + 1 : index + 1]
        current = values[index]
        finite = window[np.isfinite(window)]
        if not np.isfinite(current) or len(finite) < lookback // 2:
            continue
        out[index] = float(np.mean(finite <= current))
    return out


def _cross_count(spread: pd.Series, window: int) -> pd.Series:
    sign = np.sign(spread.to_numpy(dtype=float))
    last = 0.0
    for index, value in enumerate(sign):
        if not np.isfinite(value) or value == 0.0:
            sign[index] = last if last != 0.0 else np.nan
        else:
            last = float(value)
            sign[index] = last
    series = pd.Series(sign, index=spread.index)
    changed = series.ne(series.shift(1)) & series.notna() & series.shift(1).notna()
    return changed.astype(float).rolling(window, min_periods=window).sum()


def _vwap(frame: pd.DataFrame, dates: np.ndarray, one_bar: bool) -> pd.Series:
    typical = (frame["high"].astype(float) + frame["low"].astype(float) + frame["close"].astype(float)) / 3.0
    volume = frame["volume"].astype(float).clip(lower=0.0) if "volume" in frame.columns else pd.Series(1.0, index=frame.index)
    if one_bar:
        vol = volume.where(volume > 0.0)
        traded = (typical * vol).rolling(VOLUME_WINDOW, min_periods=VOLUME_WINDOW).sum()
        weight = vol.rolling(VOLUME_WINDOW, min_periods=VOLUME_WINDOW).sum()
        return traded / weight.replace(0.0, np.nan)
    vol = volume.where(volume > 0.0, 1.0)
    day = pd.Series(list(dates), index=frame.index)
    weight = vol.groupby(day).cumsum()
    traded = (typical * vol).groupby(day).cumsum()
    return traded / weight.replace(0.0, np.nan)


def _adx(frame: pd.DataFrame) -> pd.Series:
    high = frame["high"].astype(float)
    low = frame["low"].astype(float)
    up = high.diff()
    down = -low.diff()
    plus_dm = up.where((up > down) & (up > 0.0), 0.0)
    minus_dm = down.where((down > up) & (down > 0.0), 0.0)
    width = atr(frame, ADX_WINDOW)
    plus_di = 100.0 * _wilder(plus_dm, ADX_WINDOW) / width
    minus_di = 100.0 * _wilder(minus_dm, ADX_WINDOW) / width
    denom = plus_di + minus_di
    dx = 100.0 * (plus_di - minus_di).abs() / denom.replace(0.0, np.nan)
    return _wilder(dx, ADX_WINDOW)


def _choppiness(frame: pd.DataFrame) -> pd.Series:
    high = frame["high"].astype(float)
    low = frame["low"].astype(float)
    prev = frame["close"].astype(float).shift(1)
    tr = pd.concat([(high - low), (high - prev).abs(), (low - prev).abs()], axis=1).max(axis=1)
    span = high.rolling(CHOP_WINDOW, min_periods=CHOP_WINDOW).max() - low.rolling(CHOP_WINDOW, min_periods=CHOP_WINDOW).min()
    total = tr.rolling(CHOP_WINDOW, min_periods=CHOP_WINDOW).sum()
    ratio = total / span.replace(0.0, np.nan)
    return 100.0 * np.log10(ratio) / np.log10(CHOP_WINDOW)


def _wilder(series: pd.Series, window: int) -> pd.Series:
    return series.ewm(alpha=1.0 / window, adjust=False, min_periods=window).mean()
