"""Frozen checks for the chop combination. These do not score a book."""

import numpy as np
import pytest
import pandas as pd

from webull_bot.chart_reads.chop import features, filter_helps, find_chop_breakouts, time_in_chop

CHOP_DATES = [
    "2020-07-17",
    "2020-07-20",
    "2020-07-21",
    "2020-07-22",
    "2020-07-23",
    "2020-07-24",
    "2020-07-27",
    "2020-07-28",
    "2020-07-29",
    "2020-07-30",
    "2020-07-31",
    "2020-08-03",
    "2020-08-04",
    "2020-08-05",
    "2020-08-06",
    "2020-08-07",
    "2020-08-10",
    "2020-08-11",
    "2020-08-12",
    "2020-08-14",
    "2020-08-17",
    "2020-08-18",
    "2020-08-19",
    "2020-08-21",
    "2020-08-24",
    "2020-08-26",
    "2020-08-27",
]


def _base() -> pd.DataFrame:
    """A trending open, then a dry sine around the last close. Frozen before the score."""
    count = 260
    index = pd.bdate_range("2020-01-01", periods=count)
    close = np.empty(count)
    high = np.empty(count)
    low = np.empty(count)
    open_ = np.empty(count)
    volume = np.empty(count)
    for i in range(count):
        if i < 120:
            close[i] = 80 + i * 0.15 + np.sin(i / 2) * 6
            high[i] = close[i] + 4
            low[i] = close[i] - 4
            open_[i] = close[i] - 1
            volume[i] = 1_000_000
        else:
            turn = (i - 120) * np.pi / 4
            anchor = 80 + 119 * 0.15 + np.sin(119 / 2) * 6
            close[i] = anchor + np.sin(turn) * 2
            high[i] = close[i] + 0.6
            low[i] = close[i] - 0.6
            open_[i] = anchor + np.sin(turn - 0.8) * 2
            volume[i] = 350_000
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=index,
    )


def test_dry_base_is_chop_and_the_trend_is_not():
    feat = features(_base())
    flagged = [stamp.date().isoformat() for stamp in feat.index[feat["chop"].to_numpy()]]
    assert flagged == CHOP_DATES
    assert int(feat["chop"].iloc[:120].sum()) == 0
    row = feat.loc[pd.Timestamp("2020-07-17")]
    assert bool(row["narrow"])
    assert bool(row["tangled"])
    assert float(row["vwap_crosses"]) >= 3
    assert float(row["rel_volume"]) <= 1.20
    spent = time_in_chop(_base())
    assert spent["chop_bars"] == 27
    assert 0.0 < spent["share"] < 1.0


def test_expanding_volume_is_not_chop():
    frame = _base()
    feat = features(frame)
    pos = int(np.flatnonzero(feat["chop"].to_numpy())[9])
    assert frame.index[pos] == pd.Timestamp("2020-07-30")
    spiked = frame.copy()
    spiked.iloc[pos, spiked.columns.get_loc("volume")] = 3_000_000
    again = features(spiked)
    assert bool(again["chop"].iloc[pos]) is False
    assert float(again["rel_volume"].iloc[pos]) == np.float64(3_000_000 / 350_000)


def test_later_close_does_not_rewrite_an_earlier_bar():
    frame = _base()
    before = features(frame)
    edited = frame.copy()
    edited.iloc[-1, edited.columns.get_loc("close")] = 500.0
    after = features(edited)
    columns = ["rel_volume", "atr", "vwap", "ema9", "ema20", "bandwidth_rank", "adx", "choppiness"]
    assert np.allclose(before.iloc[160][columns].astype(float), after.iloc[160][columns].astype(float), equal_nan=True)
    assert bool(before["chop"].iloc[160]) == bool(after["chop"].iloc[160])
    assert bool((before["chop"].iloc[:-1] == after["chop"].iloc[:-1]).all())


def test_breakout_from_the_box_on_expanding_volume():
    frame = _base()
    assert find_chop_breakouts(frame, symbol="TEST") == []
    loc = int(frame.index.get_loc(pd.Timestamp("2020-08-03")))
    box_high = float(frame["high"].iloc[loc - 10 : loc].max())
    edited = frame.copy()
    edited.iloc[loc, edited.columns.get_loc("open")] = box_high + 0.2
    edited.iloc[loc, edited.columns.get_loc("close")] = box_high + 1.5
    edited.iloc[loc, edited.columns.get_loc("high")] = box_high + 1.7
    edited.iloc[loc, edited.columns.get_loc("low")] = box_high + 0.15
    edited.iloc[loc, edited.columns.get_loc("volume")] = 3_000_000
    found = find_chop_breakouts(edited, symbol="TEST")
    assert [(setup.direction, pd.Timestamp(setup.signal_time).date().isoformat(), setup.kind) for setup in found] == [
        ("long", "2020-08-03", "chop")
    ]
    setup = found[0]
    assert setup.fill_time == frame.index[loc + 1]
    assert setup.stop == pytest.approx(box_high + 0.15)
    assert setup.stop < float(edited.iloc[loc]["close"])
    height = box_high - float(frame["low"].iloc[loc - 10 : loc].min())
    assert setup.reference == pytest.approx(box_high + height)
    assert bool(features(edited)["chop"].iloc[loc]) is False


def test_filter_helps_is_the_pre_registered_reading_only():
    baseline = {"expectancy": 1.0, "trades": 40}
    assert filter_helps(baseline, {"expectancy": 2.0, "trades": 19}, 10, 4) is False
    assert filter_helps(baseline, {"expectancy": 1.0, "trades": 30}, 10, 4) is False
    assert filter_helps(baseline, {"expectancy": 2.0, "trades": 30}, 4, 4) is False
    assert filter_helps(baseline, {"expectancy": 2.0, "trades": 30}, 10, 4) is True
    assert filter_helps(baseline, {"expectancy": float("nan"), "trades": 30}, 10, 4) is False
