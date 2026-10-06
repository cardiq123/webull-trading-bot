"""Chop v2, frozen from the qualitative description before any score.

The v1 flag in ``chop.py`` is unchanged. This one drops the tangled-EMA
requirement. A bar is chop when three readings are true together at that
close:

* volume is quiet: this bar is under 0.85 times the prior 20-bar average,
  or the prior 20-bar average is below the prior 60-bar average and this
  bar is still at most 1.20 times its own 20-bar average. The second clause
  is a declining volume regime. An expanding bar is not quiet.
* the range is narrow: ATR is at most 0.85 times its prior 120-bar average,
  or Bollinger bandwidth is in the bottom 20% of the last 120 bars, or the
  last N bars sit inside 1.5 ATR. N is 10.
* price is rotating or coiling: close has crossed session VWAP, or the
  midpoint of that box, at least three times in 20 bars, or the 9 and 20
  EMAs are stacked and tight under price (a bull flag) or tight above price
  (the short mirror). Stacked means the fast EMA leads the slow one, both
  sit on the trend side of the close, the close is within 1.5 ATR of the
  fast EMA, and the two EMAs are within 0.75 ATR of each other.

The grid changes one of those round numbers at a time. The default is the
qualitative reading above. A later book may choose another cell from data
before the holdout. It does not change this default, and nothing here
places an order.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from webull_bot.chart_reads.chop import (
    BODY,
    BREAK_BUFFER_ATR,
    BREAK_COOLDOWN,
    CLOSE_FRAC,
    MAX_HEIGHT_ATR,
    MIN_CHOP_BARS,
    MIN_HEIGHT_ATR,
    _bandwidth,
    _cross_count,
    _dates,
    _percentile_rank,
    _vwap,
)
from webull_bot.chart_reads.detect import Setup, strong_candle
from webull_bot.chart_reads.hold import scan_chop_holds
from webull_bot.indicators import atr, ema
from webull_bot.mtf_vwap.detect import rth

REL_VOLUME_MAX = 0.85
VOLUME_WINDOW = 20
VOLUME_REGIME = 60
REGIME_BAR_MAX = 1.20
NARROW_LOOKBACK = 120
ATR_CONTRACTION = 0.85
BANDWIDTH_PERCENTILE = 0.20
BB_WINDOW = 20
BOX_BARS = 10
BOX_ATR = 1.5
BOX_CHOICES = (6, 10, 20)
CROSS_BARS = 20
MIN_CROSSES = 3
EMA_FAST = 9
EMA_SLOW = 20
STACK_SEP_ATR = 0.75
STACK_EXT_ATR = 1.5
EXPAND_VOLUME = 1.5

DEFAULTS: dict = {
    "rel_volume_max": REL_VOLUME_MAX,
    "regime_bar_max": REGIME_BAR_MAX,
    "atr_contraction": ATR_CONTRACTION,
    "bandwidth_percentile": BANDWIDTH_PERCENTILE,
    "box_bars": BOX_BARS,
    "box_atr": BOX_ATR,
    "min_crosses": MIN_CROSSES,
    "stack_sep_atr": STACK_SEP_ATR,
    "stack_ext_atr": STACK_EXT_ATR,
}

# One change from the default. The order is the tie-break order.
_GRID = (
    {"rel_volume_max": 0.75},
    {"rel_volume_max": 1.00},
    {"box_bars": 6},
    {"box_bars": 20},
    {"box_atr": 1.0},
    {"box_atr": 2.0},
    {"min_crosses": 2},
    {"stack_sep_atr": 0.50},
    {"stack_sep_atr": 1.00},
)


def grid() -> list[dict]:
    cells = [dict(DEFAULTS)]
    for change in _GRID:
        cell = dict(DEFAULTS)
        cell.update(change)
        cells.append(cell)
    return cells


def cell_label(cell: dict) -> str:
    changes = []
    for key, value in DEFAULTS.items():
        if cell.get(key) != value:
            changes.append(f"{key} {cell.get(key)}")
    return "default" if not changes else ", ".join(changes)


def components(frame: pd.DataFrame) -> pd.DataFrame:
    """Raw readings. Thresholds are applied in ``mask_from``."""
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
    atr_base = width.shift(1).rolling(NARROW_LOOKBACK, min_periods=NARROW_LOOKBACK).mean()
    rank = _percentile_rank(_bandwidth(close).to_numpy(dtype=float), NARROW_LOOKBACK)
    vwap = _vwap(frame, dates, one_bar)
    columns = {
        "rel_volume": volume / prior_20,
        "vol20": prior_20,
        "vol60": prior_60,
        "atr": width,
        "atr_base": atr_base,
        "bandwidth_rank": pd.Series(rank, index=frame.index),
        "vwap_crosses": _cross_count(close - vwap, CROSS_BARS),
        "ema9": fast,
        "ema20": slow,
        "close": close,
        "vwap": vwap,
    }
    for bars in BOX_CHOICES:
        height = high.rolling(bars, min_periods=bars).max() - low.rolling(bars, min_periods=bars).min()
        midline = (high.rolling(bars, min_periods=bars).max() + low.rolling(bars, min_periods=bars).min()) / 2.0
        columns[f"box_{bars}"] = height
        columns[f"mid_cross_{bars}"] = _cross_count(close - midline, CROSS_BARS)
    return pd.DataFrame(columns, index=frame.index)


def mask_from(comp: pd.DataFrame, cell: dict | None = None) -> pd.Series:
    """Boolean chop flag. Bar t uses only columns already closed at t."""
    chosen = dict(DEFAULTS)
    if cell:
        chosen.update(cell)
    rel = comp["rel_volume"]
    quiet = (rel < float(chosen["rel_volume_max"])) | (
        (comp["vol20"] < comp["vol60"]) & (rel <= float(chosen["regime_bar_max"]))
    )
    box_key = f"box_{int(chosen['box_bars'])}"
    mid_key = f"mid_cross_{int(chosen['box_bars'])}"
    if box_key not in comp.columns:
        raise KeyError(box_key)
    width = comp["atr"]
    narrow = (
        (width <= float(chosen["atr_contraction"]) * comp["atr_base"])
        | (comp["bandwidth_rank"] <= float(chosen["bandwidth_percentile"]))
        | (comp[box_key] <= float(chosen["box_atr"]) * width)
    )
    crosses = int(chosen["min_crosses"])
    rotating = (comp["vwap_crosses"] >= crosses) | (comp[mid_key] >= crosses)
    sep = float(chosen["stack_sep_atr"]) * width
    ext = float(chosen["stack_ext_atr"]) * width
    fast = comp["ema9"]
    slow = comp["ema20"]
    close = comp["close"]
    bull = (fast > slow) & (close > fast) & ((close - fast) <= ext) & ((fast - slow) <= sep)
    bear = (fast < slow) & (close < fast) & ((fast - close) <= ext) & ((slow - fast) <= sep)
    chop = quiet.fillna(False) & narrow.fillna(False) & (rotating.fillna(False) | bull.fillna(False) | bear.fillna(False))
    return chop.fillna(False)


def features(frame: pd.DataFrame, cell: dict | None = None) -> pd.DataFrame:
    """One row per bar. ``chop`` on bar t uses only bars through t."""
    comp = components(frame)
    out = comp.copy()
    out["chop"] = mask_from(comp, cell).to_numpy(dtype=bool)
    out["narrow"] = _narrow(comp, cell).to_numpy(dtype=bool)
    out["quiet"] = _quiet(comp, cell).to_numpy(dtype=bool)
    out["stacked"] = _stacked(comp, cell).to_numpy(dtype=bool)
    return out


def _quiet(comp: pd.DataFrame, cell: dict | None) -> pd.Series:
    chosen = dict(DEFAULTS)
    if cell:
        chosen.update(cell)
    rel = comp["rel_volume"]
    return (rel < float(chosen["rel_volume_max"])) | (
        (comp["vol20"] < comp["vol60"]) & (rel <= float(chosen["regime_bar_max"]))
    )


def _narrow(comp: pd.DataFrame, cell: dict | None) -> pd.Series:
    chosen = dict(DEFAULTS)
    if cell:
        chosen.update(cell)
    width = comp["atr"]
    box_key = f"box_{int(chosen['box_bars'])}"
    return (
        (width <= float(chosen["atr_contraction"]) * comp["atr_base"])
        | (comp["bandwidth_rank"] <= float(chosen["bandwidth_percentile"]))
        | (comp[box_key] <= float(chosen["box_atr"]) * width)
    )


def _stacked(comp: pd.DataFrame, cell: dict | None) -> pd.Series:
    chosen = dict(DEFAULTS)
    if cell:
        chosen.update(cell)
    width = comp["atr"]
    sep = float(chosen["stack_sep_atr"]) * width
    ext = float(chosen["stack_ext_atr"]) * width
    fast = comp["ema9"]
    slow = comp["ema20"]
    close = comp["close"]
    bull = (fast > slow) & (close > fast) & ((close - fast) <= ext) & ((fast - slow) <= sep)
    bear = (fast < slow) & (close < fast) & ((fast - close) <= ext) & ((slow - fast) <= sep)
    return bull.fillna(False) | bear.fillna(False)


def time_in_chop(frame: pd.DataFrame, cell: dict | None = None) -> dict:
    feat = features(frame, cell)
    ready = feat["rel_volume"].notna() & feat["ema20"].notna() & feat["vwap"].notna() & feat["atr"].notna()
    usable = feat.loc[ready]
    bars = int(len(usable))
    if bars == 0:
        return {"bars": 0, "chop_bars": 0, "share": 0.0}
    return {"bars": bars, "chop_bars": int(usable["chop"].sum()), "share": float(usable["chop"].mean())}


def find_chop_breakouts(
    frame: pd.DataFrame,
    *,
    symbol: str = "",
    cell: dict | None = None,
    feat: pd.DataFrame | None = None,
) -> list[Setup]:
    """Close out of a chop-v2 box on relative volume above 1.5 and a confirming candle.

    The box is the prior N bars of the cell (10 by default). At least 6 of
    them are chop. The fill is the next bar's open. The stop is the signal
    bar's low on a long and its high on a short. The reference is the box
    height measured from the broken side.
    """
    chosen = dict(DEFAULTS)
    if cell:
        chosen.update(cell)
    box = int(chosen["box_bars"])
    if frame is None or len(frame) < box + VOLUME_WINDOW + 2:
        return []
    if feat is None:
        feat = features(frame, chosen)
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
    for t in range(box + VOLUME_WINDOW, len(frame) - 1):
        if t - last < BREAK_COOLDOWN:
            continue
        if int(flags[t - box : t].sum()) < MIN_CHOP_BARS:
            continue
        scale = width[t]
        if not np.isfinite(scale) or scale <= 0:
            continue
        box_high = float(np.nanmax(high[t - box : t]))
        box_low = float(np.nanmin(low[t - box : t]))
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
        if direction == "long" and stop >= close[t]:
            continue
        if direction == "short" and stop <= close[t]:
            continue
        found.append(
            Setup(
                symbol=symbol,
                direction=direction,
                kind="chop_v2",
                signal_time=index[t],
                fill_time=index[t + 1],
                anchor_time=index[t - box],
                stop=float(stop),
                atr=float(scale),
                reference=float(reference),
            )
        )
        last = t
    return found


def scan_holds(frame: pd.DataFrame, *, symbol: str = "", counts: dict | None = None, cell: dict | None = None):
    """The frozen hold sequence, with this module's flag as the pullback."""
    bars = rth(frame)
    if bars is None or len(bars) < 2:
        return []
    feat = features(bars, cell)
    return scan_chop_holds(frame, symbol=symbol, counts=counts, chop=feat["chop"])
