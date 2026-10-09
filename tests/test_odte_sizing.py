"""Sizing clock and the 1-minute exit. No market data and no orders."""

from datetime import date

import pandas as pd

from webull_bot.chart_reads.odte_calibration import (
    expiry_after,
    price_structures,
    years_left,
    years_until_expiry,
)
from webull_bot.chart_reads.odte_sizing import retime


def test_one_and_two_dte_are_the_next_sessions():
    friday = date(2024, 1, 5)
    assert expiry_after(friday, 1) == date(2024, 1, 8)
    assert expiry_after(friday, 2) == date(2024, 1, 9)
    when = pd.Timestamp("2024-01-05 15:45", tz="America/New_York")
    assert years_until_expiry(when, expiry_after(friday, 1)) > years_left(when, 0)


def test_a_longer_expiry_keeps_time_value_at_the_same_exit():
    day = date(2024, 1, 3)
    when = pd.Timestamp("2024-01-03 10:00", tz="America/New_York")
    item = {
        "day": day,
        "due": date(2024, 1, 4),
        "fill_i": 1,
        "exit_i": 2,
        "fill": 100.0,
        "exit": 101.0,
        "fill_time": when,
        "exit_time": when + pd.Timedelta(minutes=30),
        "right": "call",
    }
    iv = {day: (20.0, "VIX")}
    same_day = price_structures([item], iv, 1.0, "0.01", dte=0)
    next_day = price_structures([item], iv, 1.0, "0.01", dte=1)
    assert same_day and next_day
    assert same_day[0][4] < next_day[0][4]


def test_one_minute_exit_takes_the_target_that_prints_before_the_stop():
    index = pd.date_range("2024-01-03 10:00", periods=6, freq="min", tz="America/New_York")
    minutes = pd.DataFrame(
        {
            "open": [100.0, 100.2, 101.1, 100.5, 99.5, 98.0],
            "high": [100.3, 101.2, 101.2, 100.6, 99.6, 98.2],
            "low": [99.8, 100.1, 100.8, 100.2, 98.4, 97.5],
            "close": [100.2, 101.1, 100.9, 100.4, 98.5, 97.8],
            "volume": [1, 1, 1, 1, 1, 1],
        },
        index=index,
    )
    item = {
        "day": date(2024, 1, 3),
        "due": date(2024, 1, 4),
        "fill_time": index[0],
        "fill": 100.0,
        "exit": 99.0,
        "stop": 99.0,
        "direction": "long",
        "right": "call",
        "reason": "stop",
    }
    found, stats = retime([item], minutes)
    assert len(found) == 1
    assert found[0]["reason"] == "target"
    assert found[0]["exit"] == 101.0
    assert found[0]["exit_time"] == index[1]
    assert stats["exit_reason_changed"] == 1
    assert stats["entry_changed"] == 0


def test_an_open_through_the_stop_is_not_taken_on_a_later_minute():
    index = pd.date_range("2024-01-03 10:00", periods=3, freq="min", tz="America/New_York")
    minutes = pd.DataFrame(
        {
            "open": [98.0, 100.0, 100.2],
            "high": [98.2, 100.4, 100.5],
            "low": [97.5, 99.8, 100.0],
            "close": [98.1, 100.2, 100.3],
            "volume": [1, 1, 1],
        },
        index=index,
    )
    item = {
        "day": date(2024, 1, 3),
        "due": date(2024, 1, 4),
        "fill_time": index[0],
        "fill": 98.0,
        "exit": 99.0,
        "stop": 99.0,
        "direction": "long",
        "right": "call",
        "reason": "stop",
    }
    found, stats = retime([item], minutes)
    assert found == []
    assert stats["through_stop"] == 1
