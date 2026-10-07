"""Chop v2 and the longer swing list. The frozen v1 flag is not retuned."""

from __future__ import annotations

import numpy as np
import pandas as pd

from webull_bot.chart_reads.chop import REL_VOLUME_MAX, features as features_v1
from webull_bot.chart_reads.chop_v2 import (
    BOX_ATR,
    BOX_BARS,
    DEFAULTS,
    REL_VOLUME_MAX as REL_V2,
    STACK_SEP_ATR,
    features,
    grid,
    mask_from,
)
from webull_bot.chart_reads.levels import HISTORY_BARS, MERGE_ATR, HORIZONTAL_LOOKBACK, merge_weighted, merged_swings


def test_v2_constants_come_from_the_description_and_v1_stays():
    assert REL_V2 == 0.85
    assert DEFAULTS["rel_volume_max"] == 0.85
    assert DEFAULTS["box_atr"] == 1.5
    assert DEFAULTS["box_bars"] == 10
    assert DEFAULTS["min_crosses"] == 3
    assert DEFAULTS["stack_sep_atr"] == 0.75
    assert DEFAULTS["atr_contraction"] == 0.85
    assert "tangled" not in DEFAULTS
    assert REL_VOLUME_MAX == 0.80
    assert BOX_ATR == 1.5 and BOX_BARS == 10 and STACK_SEP_ATR == 0.75
    labels = [cell["rel_volume_max"] for cell in grid()]
    assert labels[0] == 0.85
    assert 0.75 in labels and 1.00 in labels
    assert HISTORY_BARS == 250
    assert MERGE_ATR == 0.50
    assert HORIZONTAL_LOOKBACK == 120


def test_a_tight_flag_is_chop_without_tangled_emas():
    index = pd.bdate_range("2020-01-01", periods=180)
    close = 100.0 + np.arange(len(index)) * 0.05
    # Wide early ranges keep ATR large. The last 15 bars are a tight flag.
    high = close + 1.0
    low = close - 1.0
    high[-15:] = close[-15:] + 0.15
    low[-15:] = close[-15:] - 0.15
    volume = np.full(len(index), 1_000_000.0)
    volume[-15:] = 100_000.0
    frame = pd.DataFrame({"open": close, "high": high, "low": low, "close": close, "volume": volume}, index=index)
    feat = features(frame)
    v1 = features_v1(frame)
    assert bool(feat["chop"].iloc[-1])
    assert bool(feat["stacked"].iloc[-1])
    assert not bool(v1["chop"].iloc[-1])
    assert not bool(v1["tangled"].iloc[-1])


def test_a_loud_wide_bar_is_not_chop():
    index = pd.bdate_range("2020-01-01", periods=180)
    close = np.full(len(index), 100.0)
    high = close + 0.2
    low = close - 0.2
    volume = np.full(len(index), 100_000.0)
    close[-1] = 110.0
    high[-1] = 112.0
    low[-1] = 99.0
    volume[-1] = 5_000_000.0
    frame = pd.DataFrame(
        {"open": np.r_[close[:-1], 100.0], "high": high, "low": low, "close": close, "volume": volume},
        index=index,
    )
    feat = features(frame)
    assert not bool(feat["chop"].iloc[-1])
    assert not bool(feat["quiet"].iloc[-1])


def test_mask_uses_only_the_cell_thresholds():
    index = pd.bdate_range("2020-01-01", periods=40)
    comp = pd.DataFrame(
        {
            "rel_volume": np.full(40, 0.90),
            "vol20": np.full(40, 1.0),
            "vol60": np.full(40, 2.0),
            "atr": np.full(40, 1.0),
            "atr_base": np.full(40, 2.0),
            "bandwidth_rank": np.full(40, 0.50),
            "vwap_crosses": np.full(40, 1.0),
            "ema9": np.full(40, 100.0),
            "ema20": np.full(40, 99.5),
            "close": np.full(40, 100.4),
            "vwap": np.full(40, 100.0),
            "box_6": np.full(40, 1.2),
            "box_10": np.full(40, 1.2),
            "box_20": np.full(40, 1.2),
            "mid_cross_6": np.full(40, 0.0),
            "mid_cross_10": np.full(40, 0.0),
            "mid_cross_20": np.full(40, 0.0),
        },
        index=index,
    )
    # Relative volume 0.90 fails the 0.85 test, but the 20-bar average is declining
    # and the bar is under 1.20, the box is inside 1.5 ATR, and the EMAs are stacked.
    assert bool(mask_from(comp).iloc[-1])
    assert not bool(mask_from(comp, {"regime_bar_max": 0.50}).iloc[-1])


def test_merge_weights_by_touches_and_does_not_chain_distant_steps():
    merged = merge_weighted([(100.0, 1), (100.4, 3), (110.0, 2)], tolerance=0.5)
    assert len(merged) == 2
    assert abs(merged[0][0] - (100.0 + 100.4 * 3) / 4) < 1e-9
    assert merged[0][1] == 4
    assert merged[1] == (110.0, 2)


def _spike(high, low, at, price, kind):
    if kind == "high":
        high[at] = price
        low[at] = price - 0.2
    else:
        low[at] = price
        high[at] = price + 0.2


def test_older_swings_inside_250_bars_survive_and_near_prices_merge():
    n = 400
    index = pd.bdate_range("2018-01-01", periods=n)
    close = np.full(n, 100.0)
    high = close + 0.2
    low = close - 0.2
    volume = np.full(n, 1_000_000.0)
    # Outside the 250-bar window measured from the last bar.
    _spike(high, low, 40, 140.0, "high")
    # Inside the window, two highs close enough to merge, and one distant low.
    _spike(high, low, 200, 130.0, "high")
    _spike(high, low, 230, 130.15, "high")
    _spike(high, low, 300, 80.0, "low")
    frame = pd.DataFrame({"open": close, "high": high, "low": low, "close": close, "volume": volume}, index=index)
    rows = merged_swings(frame)
    prices = [row["price"] for row in rows]
    assert not any(abs(price - 140.0) < 2.0 for price in prices)
    assert any(abs(price - 130.0) < 1.0 for price in prices)
    near = [row for row in rows if abs(row["price"] - 130.0) < 1.0]
    assert len(near) == 1
    assert near[0]["touches"] >= 2
    assert any(abs(price - 80.0) < 1.0 for price in prices)


def test_chop_v2_is_not_in_the_registry_and_live_stays_off():
    config = open("config/default.yaml", encoding="utf-8").read()
    optional = open("config/optional_strategies.json", encoding="utf-8").read()
    live = open("src/webull_bot/execution/live.py", encoding="utf-8").read()
    assert "live_trading_enabled: false" in config
    assert "chop_v2" not in optional
    assert "scan_holds" not in live
    assert "merged_swings" not in live
