"""Synthetic checks for the frozen 4-hour rule. These tests do not score a window."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import numpy as np
import pandas as pd

from webull_bot.chart_reads.four_hour import (
    MAG7,
    Book,
    Event,
    catalog,
    completed_blocks,
    find_signals,
    frozen_rules,
    n_trials,
    resolve,
)

NY = "America/New_York"


def _minutes(start: str, count: int) -> np.ndarray:
    index = pd.date_range(start, periods=count, freq="5min", tz=NY)
    return (index.hour * 60 + index.minute).to_numpy(dtype=int)


def _session(day: str, price: float, count: int = 78) -> pd.DataFrame:
    index = pd.date_range(f"{day} 09:30", periods=count, freq="5min", tz=NY)
    frame = pd.DataFrame(
        {
            "open": price,
            "high": price + 0.4,
            "low": price - 0.4,
            "close": price,
            "volume": 1.0,
        },
        index=index,
    )
    return frame


def test_full_session_has_two_four_hour_blocks():
    blocks = completed_blocks(_minutes("2024-01-02 09:30", 78))
    four = [block for block in blocks if block[0] == "h4"]
    assert four == [("h4", 0, 47), ("h4", 48, 77)]
    hours = [block for block in blocks if block[0] == "h1"]
    assert hours[0] == ("h1", 0, 11)
    assert hours[-1] == ("h1", 60, 71)
    assert ("h1", 72, 77) not in hours


def test_morning_block_needs_the_1325_bar():
    minutes = _minutes("2024-01-02 09:30", 78)
    minutes = np.delete(minutes, 47)
    four = [block for block in completed_blocks(minutes) if block[0] == "h4"]
    assert len(four) == 1
    _name, start, end = four[0]
    assert int(minutes[start]) == 13 * 60 + 30
    assert int(minutes[end]) == 15 * 60 + 55


def test_four_hour_direction_waits_for_the_block_to_finish():
    day1 = _session("2024-01-02", 100.0)
    morning = _session("2024-01-03", 100.0)
    # 13:25 is bar 47. Lift the whole morning block into a higher high and higher low.
    morning.iloc[:48, morning.columns.get_loc("open")] = 101.0
    morning.iloc[:48, morning.columns.get_loc("high")] = 102.0
    morning.iloc[:48, morning.columns.get_loc("low")] = 100.6
    morning.iloc[:48, morning.columns.get_loc("close")] = 101.5
    later = _session("2024-01-04", 50.0)
    later["close"] = 1.0
    book = Book(pd.concat([day1, morning, later]), "SPY")
    day2 = np.flatnonzero(book.dates == date(2024, 1, 3))
    before = day2[book.minute[day2] == 13 * 60 + 20][0]
    done = day2[book.minute[day2] == 13 * 60 + 25][0]
    assert int(book.h4_structure[before]) == 0
    assert int(book.h4_structure[done]) == 1
    changed = Book(pd.concat([day1, morning, _session("2024-01-04", 80.0)]), "SPY")
    assert int(changed.h4_structure[done]) == int(book.h4_structure[done])
    assert int(changed.h4_structure[before]) == 0


def _scan_book() -> SimpleNamespace:
    n = 6
    index = pd.date_range("2024-06-03 10:00", periods=n, freq="5min", tz=NY)
    book = SimpleNamespace(
        symbol="SPY",
        index=index,
        open=np.array([100.0, 100.0, 97.0, 98.0, 99.0, 99.0]),
        high=np.array([101.0, 100.0, 98.0, 99.5, 100.0, 100.0]),
        low=np.array([99.0, 96.0, 95.0, 97.5, 98.5, 98.5]),
        close=np.array([100.0, 97.0, 97.2, 99.0, 99.2, 99.2]),
        minute=(index.hour * 60 + index.minute).to_numpy(dtype=int),
        dates=np.asarray(index.date, dtype=object),
        ema9=np.array([94.0, 94.0, 94.0, 96.0, 96.0, 96.0]),
        h4_ema=np.ones(n, dtype=int),
        h4_structure=np.ones(n, dtype=int),
        h1_agree=np.ones(n, dtype=int),
        h1_ema20=np.full(n, 90.0),
        m15_done=np.array([False, False, True, False, False, False]),
        m15_first=np.array([-1, -1, 0, -1, -1, -1]),
        m15_low=np.array([np.nan, np.nan, 95.0, np.nan, np.nan, np.nan]),
        m15_high=np.array([np.nan, np.nan, 101.0, np.nan, np.nan, np.nan]),
        m15_close=np.array([np.nan, np.nan, 97.2, np.nan, np.nan, np.nan]),
        m15_ema20=np.array([np.nan, np.nan, 95.2, np.nan, np.nan, np.nan]),
        m15_atr=np.array([np.nan, np.nan, 10.0, np.nan, np.nan, np.nan]),
        m15_vwap=np.array([np.nan, np.nan, 95.2, np.nan, np.nan, np.nan]),
    )
    return book


def test_entry_is_the_next_open_after_the_pullback():
    events = find_signals(_scan_book(), "ema", "ema20")
    assert len(events) == 1
    event = events[0]
    assert event.direction == "long"
    assert event.signal_i == 3
    assert event.fill_i == 4
    assert event.stop == 95.0 - 0.01


def test_a_close_through_the_hour_average_cancels_the_pullback():
    book = _scan_book()
    book.h1_ema20 = np.full(6, 98.0)
    book.m15_close = np.array([np.nan, np.nan, 97.2, np.nan, np.nan, np.nan])
    assert find_signals(book, "ema", "ema20") == []


def test_short_mirror_stops_above_the_pullback_high():
    book = _scan_book()
    book.h4_ema = -np.ones(6, dtype=int)
    book.h1_agree = -np.ones(6, dtype=int)
    book.h1_ema20 = np.full(6, 110.0)
    book.open = np.array([100.0, 100.0, 103.0, 102.0, 101.0, 101.0])
    book.high = np.array([101.0, 104.0, 105.0, 102.5, 101.5, 101.5])
    book.low = np.array([99.0, 100.0, 102.0, 100.5, 100.0, 100.0])
    book.close = np.array([100.0, 103.0, 102.8, 101.0, 100.8, 100.8])
    book.ema9 = np.array([106.0, 106.0, 106.0, 104.0, 104.0, 104.0])
    book.m15_low = np.array([np.nan, np.nan, 99.0, np.nan, np.nan, np.nan])
    book.m15_high = np.array([np.nan, np.nan, 105.0, np.nan, np.nan, np.nan])
    book.m15_close = np.array([np.nan, np.nan, 102.8, np.nan, np.nan, np.nan])
    book.m15_ema20 = np.array([np.nan, np.nan, 104.8, np.nan, np.nan, np.nan])
    events = find_signals(book, "ema", "ema20")
    assert len(events) == 1
    assert events[0].direction == "short"
    assert events[0].fill_i == 4
    assert events[0].stop == 105.0 + 0.01


def test_flat_is_the_1545_open_when_the_target_is_not_hit():
    index = pd.date_range("2024-06-03 15:30", periods=4, freq="5min", tz=NY)
    frame = pd.DataFrame(
        {
            "open": [100.0, 100.2, 100.3, 100.4],
            "high": [100.3, 100.4, 100.5, 100.6],
            "low": [99.8, 99.9, 100.0, 100.1],
            "close": [100.2, 100.3, 100.4, 100.5],
            "volume": 1.0,
        },
        index=index,
    )
    book = Book(frame, "SPY")
    event = Event("SPY", "long", "ema", "ema20", 0, 0, 99.0)
    rows = resolve(book, [event], "r1")
    assert len(rows) == 1
    assert rows[0]["reason"] == "flat"
    assert rows[0]["exit"] == 100.4
    assert book.index[rows[0]["exit_i"]].time().hour == 15
    assert book.index[rows[0]["exit_i"]].time().minute == 45


def test_family_is_frozen_at_seventy_two_and_leaves_out_the_mag7():
    rules = frozen_rules()
    assert rules["registered_before_score"] is True
    assert rules["n_trials"] == 72
    assert n_trials() == 72
    assert len(catalog()) == len(set(rules["cells"]))
    assert "rolling 240" in rules["bars"]["four_hour"]
    assert rules["daily_cap"] == 5
    blob = " ".join(rules["cells"])
    for symbol in MAG7:
        assert symbol not in blob
    assert "ending_equity" not in rules
