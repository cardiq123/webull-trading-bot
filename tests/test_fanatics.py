"""Detectors and fill rules for the Chart Fanatics specs."""

import numpy as np
import pandas as pd
import pytest

from webull_bot.fanatics.detectors import (
    bullish_fvg,
    doji_mask,
    fvg_bounds,
    hammer,
    opening_range,
    session_key,
    shooting_star,
    value_area,
)
from webull_bot.fanatics.simulate import Signal, simulate
from webull_bot.fanatics.specs import generate


def test_value_area_expands_from_the_heaviest_bin():
    prices = np.array([10.0, 11.0, 12.0, 13.0])
    volumes = np.array([1.0, 5.0, 1.0, 1.0])
    poc, vah, val = value_area(prices, volumes, coverage=0.70)
    assert poc == 11.0
    assert val <= poc <= vah
    assert vah - val >= 1.0


def test_bullish_fvg_and_midpoint_use_only_the_three_bars():
    high = np.array([10.0, 12.0, 14.0, 11.0])
    low = np.array([9.0, 11.0, 12.5, 10.0])
    mask = bullish_fvg(high, low)
    assert not mask[1]
    assert mask[2]
    zone_low, zone_high, mid = fvg_bounds(high, low, 2, 1)
    assert zone_low == 10.0
    assert zone_high == 12.5
    assert mid == pytest.approx(11.25)
    # A later bar cannot create the gap earlier.
    assert not bullish_fvg(high[:2], low[:2])[1] if len(high[:2]) else True


def test_doji_shooting_star_and_hammer():
    open_ = np.array([10.0, 10.0, 10.0])
    high = np.array([10.3, 14.0, 10.4])
    low = np.array([9.0, 9.5, 6.0])
    close = np.array([10.2, 10.4, 10.2])
    assert bool(doji_mask(open_, high, low, close, 0.30)[0])
    assert bool(shooting_star(open_, high, low, close)[1])
    assert not bool(shooting_star(open_, high, low, close)[0])
    assert bool(hammer(open_, high, low, close)[2])


def test_opening_range_is_the_first_window_only():
    high = np.array([5.0, 6.0, 9.0])
    low = np.array([4.0, 5.5, 8.0])
    or_high, or_low = opening_range(high, low, 0, 2)
    assert or_high == 6.0
    assert or_low == 4.0


def test_session_key_maps_friday_evening_to_monday():
    index = pd.DatetimeIndex(
        [
            "2024-01-05 19:00",
            "2024-01-08 09:30",
        ],
        tz="America/New_York",
    )
    keys = session_key(index)
    assert keys[0] == "2024-01-08"
    assert keys[1] == "2024-01-08"


def _bars(rows):
    index = pd.date_range("2024-01-08 09:30", periods=len(rows), freq="5min", tz="America/New_York")
    return pd.DataFrame(rows, index=index, columns=["open", "high", "low", "close", "volume"])


def test_stop_fills_before_target_on_the_same_bar():
    frame = _bars(
        [
            [100, 101, 99, 100, 1],
            [100, 100.2, 99.8, 100, 1],
            [100, 110, 90, 100, 1],
        ]
    )
    signal = Signal("NQ=F", 1, 0, stop=99.0, target=105.0, time_exit_loc=10)
    _result, trades = simulate(
        {"NQ=F": frame},
        [signal],
        risk=0.5,
        max_consecutive_losses=9,
        day_loss_r=99,
        day_win_r=99,
    )
    assert len(trades) == 1
    assert trades.iloc[0]["reason"] == "stop"
    assert trades.iloc[0]["pnl"] < 0


def test_prior_day_low_sweep_and_reclaim_is_a_long():
    index = pd.date_range("2024-01-08 09:30", "2024-01-09 12:00", freq="5min", tz="America/New_York")
    index = index[index.indexer_between_time("09:30", "15:55")]
    rows = []
    for stamp in index:
        if stamp.date().isoformat() == "2024-01-08":
            rows.append([110.0, 120.0, 100.0, 115.0, 10.0])
        elif stamp.hour == 10 and stamp.minute <= 10:
            rows.append([102.0, 103.0, 99.0, 101.0, 20.0])
        else:
            rows.append([106.0, 107.0, 105.0, 106.5, 10.0])
    frame = pd.DataFrame(rows, index=index, columns=["open", "high", "low", "close", "volume"])
    signals, _frames = generate(1, {"NQ=F": frame}, {"symbols": ["NQ=F"]})
    longs = [signal for signal in signals if signal.side > 0]
    assert longs
    assert longs[0].stop < 100
    assert longs[0].target > longs[0].stop


def test_gap_through_the_stop_fills_at_the_open():
    frame = _bars(
        [
            [100, 101, 99, 100, 1],
            [100, 100.5, 99.5, 100, 1],
            [90, 91, 89, 90, 1],
        ]
    )
    signal = Signal("NQ=F", 1, 0, stop=99.0, target=110.0, time_exit_loc=10)
    _result, trades = simulate(
        {"NQ=F": frame},
        [signal],
        risk=0.5,
        max_consecutive_losses=9,
        day_loss_r=99,
        day_win_r=99,
    )
    assert trades.iloc[0]["reason"] == "stop"
    assert trades.iloc[0]["exit"] == pytest.approx(90.0)
