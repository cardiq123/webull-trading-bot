"""Offline tests for the three breakout patterns.

The fixtures are the rules. No network and no broker.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from webull_bot.chart_reads.breakouts import find_breakout_setups, pattern_at
from webull_bot.chart_reads.params import BREAKOUT_DEFAULTS
from webull_bot.chart_reads.simulate import simulate


def _quiet(n: int = 90) -> pd.DataFrame:
    index = pd.bdate_range("2021-01-04", periods=n)
    close = np.full(n, 105.0)
    return pd.DataFrame(
        {
            "open": close,
            "high": close + 0.5,
            "low": close - 0.5,
            "close": close,
            "volume": np.full(n, 1_000_000.0),
        },
        index=index,
    )


def _low(frame: pd.DataFrame, i: int, price: float) -> None:
    frame.iloc[i, frame.columns.get_loc("low")] = price
    frame.iloc[i, frame.columns.get_loc("open")] = price + 1.5
    frame.iloc[i, frame.columns.get_loc("close")] = price + 1.0
    frame.iloc[i, frame.columns.get_loc("high")] = price + 2.0


def _high(frame: pd.DataFrame, i: int, price: float) -> None:
    frame.iloc[i, frame.columns.get_loc("high")] = price
    frame.iloc[i, frame.columns.get_loc("open")] = price - 1.5
    frame.iloc[i, frame.columns.get_loc("close")] = price - 1.0
    frame.iloc[i, frame.columns.get_loc("low")] = price - 2.0


def _descending() -> tuple[pd.DataFrame, int]:
    frame = _quiet()
    _high(frame, 16, 112.0)
    _low(frame, 24, 100.0)
    _high(frame, 40, 109.0)
    _low(frame, 50, 100.0)
    return frame, 64


def _breakdown(frame: pd.DataFrame, i: int) -> None:
    frame.iloc[i, frame.columns.get_loc("open")] = 101.0
    frame.iloc[i, frame.columns.get_loc("high")] = 102.0
    frame.iloc[i, frame.columns.get_loc("low")] = 96.0
    frame.iloc[i, frame.columns.get_loc("close")] = 97.0


def _ascending() -> tuple[pd.DataFrame, int]:
    frame = _quiet()
    frame["open"] = 112.0
    frame["high"] = 112.5
    frame["low"] = 111.5
    frame["close"] = 112.0
    _low(frame, 16, 100.0)
    _high(frame, 24, 120.0)
    _low(frame, 40, 104.0)
    _high(frame, 50, 120.0)
    return frame, 64


def _breakout(frame: pd.DataFrame, i: int) -> None:
    frame.iloc[i, frame.columns.get_loc("open")] = 119.0
    frame.iloc[i, frame.columns.get_loc("high")] = 126.0
    frame.iloc[i, frame.columns.get_loc("low")] = 118.0
    frame.iloc[i, frame.columns.get_loc("close")] = 124.0


def _range() -> tuple[pd.DataFrame, int]:
    frame = _quiet()
    _low(frame, 20, 100.0)
    _high(frame, 30, 108.0)
    _low(frame, 48, 100.0)
    _high(frame, 58, 108.0)
    return frame, 72


def test_descending_triangle_breaks_down_on_a_confirming_close():
    frame, at = _descending()
    _breakdown(frame, at)
    shorts = [row for row in find_breakout_setups(frame, BREAKOUT_DEFAULTS, symbol="X") if row.direction == "short"]
    assert len(shorts) == 1
    setup = shorts[0]
    assert setup.kind == "Dd"
    assert setup.signal_time == frame.index[at]
    assert setup.fill_time == frame.index[at + 1]
    assert setup.stop == 102.0
    assert setup.reference < 100.0
    assert [row.direction for row in find_breakout_setups(frame, BREAKOUT_DEFAULTS, symbol="X")] == ["short"]
    pattern = pattern_at(frame, BREAKOUT_DEFAULTS, frame.index[at - 1])
    assert pattern is not None
    assert pattern.kind == "Dd"
    assert pattern.flat_touches >= 2
    assert pattern.slope_touches >= 2


def test_three_flat_touches_reject_a_two_touch_base():
    frame, at = _descending()
    _breakdown(frame, at)
    variant = dict(BREAKOUT_DEFAULTS, min_flat_touches=3)
    assert find_breakout_setups(frame, variant, symbol="X") == []


def test_a_weak_close_through_support_is_not_a_signal():
    frame, at = _descending()
    frame.iloc[at, frame.columns.get_loc("open")] = 99.6
    frame.iloc[at, frame.columns.get_loc("high")] = 100.2
    frame.iloc[at, frame.columns.get_loc("low")] = 96.0
    frame.iloc[at, frame.columns.get_loc("close")] = 99.4
    assert find_breakout_setups(frame, BREAKOUT_DEFAULTS, symbol="X") == []


def test_breaking_the_falling_highs_does_not_create_a_long():
    frame, at = _descending()
    frame.iloc[at, frame.columns.get_loc("open")] = 108.0
    frame.iloc[at, frame.columns.get_loc("high")] = 116.0
    frame.iloc[at, frame.columns.get_loc("low")] = 107.0
    frame.iloc[at, frame.columns.get_loc("close")] = 115.0
    setups = find_breakout_setups(frame, BREAKOUT_DEFAULTS, symbol="X")
    assert [row.direction for row in setups] == []


def test_ascending_triangle_breaks_up_only():
    frame, at = _ascending()
    _breakout(frame, at)
    longs = find_breakout_setups(frame, BREAKOUT_DEFAULTS, symbol="X")
    assert len(longs) == 1
    assert longs[0].kind == "Da"
    assert longs[0].direction == "long"
    assert longs[0].signal_time == frame.index[at]
    assert longs[0].fill_time == frame.index[at + 1]
    assert longs[0].stop == 118.0
    assert longs[0].reference > 120.0


def test_range_breaks_either_way_and_a_retest_can_confirm():
    down, at = _range()
    _breakdown(down, at)
    shorts = find_breakout_setups(down, BREAKOUT_DEFAULTS, symbol="X")
    assert len(shorts) == 1
    assert shorts[0].kind == "Dr"
    assert shorts[0].direction == "short"
    assert shorts[0].stop == 102.0

    up, at = _range()
    _breakout(up, at)
    # The box top is 108, so a close at 124 is through it. Rebuild a box-scaled long.
    up.iloc[at, up.columns.get_loc("open")] = 107.0
    up.iloc[at, up.columns.get_loc("high")] = 112.0
    up.iloc[at, up.columns.get_loc("low")] = 106.5
    up.iloc[at, up.columns.get_loc("close")] = 111.0
    longs = find_breakout_setups(up, BREAKOUT_DEFAULTS, symbol="X")
    assert len(longs) == 1
    assert longs[0].kind == "Dr"
    assert longs[0].direction == "long"
    assert longs[0].stop == 106.5

    retest, at = _descending()
    retest.iloc[at, retest.columns.get_loc("open")] = 100.2
    retest.iloc[at, retest.columns.get_loc("high")] = 101.0
    retest.iloc[at, retest.columns.get_loc("low")] = 95.0
    retest.iloc[at, retest.columns.get_loc("close")] = 99.2
    for j in range(at + 1, at + 4):
        retest.iloc[j, retest.columns.get_loc("open")] = 98.8
        retest.iloc[j, retest.columns.get_loc("high")] = 99.2
        retest.iloc[j, retest.columns.get_loc("low")] = 97.5
        retest.iloc[j, retest.columns.get_loc("close")] = 98.4
    hold = at + 4
    retest.iloc[hold, retest.columns.get_loc("open")] = 99.4
    retest.iloc[hold, retest.columns.get_loc("high")] = 100.1
    retest.iloc[hold, retest.columns.get_loc("low")] = 96.5
    retest.iloc[hold, retest.columns.get_loc("close")] = 97.2
    params = dict(BREAKOUT_DEFAULTS, require_retest=True)
    setups = find_breakout_setups(retest, params, symbol="X")
    assert len(setups) == 1
    assert setups[0].signal_time == retest.index[hold]
    assert setups[0].fill_time == retest.index[hold + 1]
    assert setups[0].stop == 100.1
    truncated = retest.loc[: setups[0].fill_time]
    again = find_breakout_setups(truncated, params, symbol="X")
    assert [(row.signal_time, row.fill_time, row.stop) for row in again] == [
        (setups[0].signal_time, setups[0].fill_time, setups[0].stop)
    ]
    failed = retest.copy()
    failed.iloc[at + 2, failed.columns.get_loc("close")] = 101.0
    failed.iloc[at + 2, failed.columns.get_loc("open")] = 99.0
    assert find_breakout_setups(failed, params, symbol="X") == []


def test_a_contract_that_does_not_fit_is_skipped():
    index = pd.bdate_range("2024-01-02", periods=40)
    close = 800.0 + np.linspace(0.0, 4.0, 40)
    frame = pd.DataFrame(
        {"open": close, "high": close + 1.0, "low": close - 1.0, "close": close, "volume": 1_000_000.0},
        index=index,
    )
    from webull_bot.chart_reads.detect import Setup

    setup = Setup(
        symbol="SPY",
        direction="long",
        kind="Da",
        signal_time=index[29],
        fill_time=index[30],
        anchor_time=index[20],
        stop=760.0,
        atr=5.0,
        reference=860.0,
    )
    params = dict(BREAKOUT_DEFAULTS, expression="single", dte=45)
    stats = simulate([setup], {"SPY": frame}, {"SPY": frame}, params, session_filter=False)
    assert stats.metrics["trades"] == 0
    assert stats.premium_skipped == 1
