"""Offline tests for the daily descending-trendline setup.

No network and no broker.
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from webull_bot.chart_reads.detect import Setup
from webull_bot.chart_reads.params import DAILY_DEFAULTS
from webull_bot.chart_reads.simulate import simulate
from webull_bot.chart_reads.trendline import describe_line, find_trend_setups
from webull_bot.universe_dow import is_member


def _two_peaks(extra: int = 8) -> pd.DataFrame:
    n = 100 + extra
    index = pd.bdate_range("2021-01-04", periods=n)
    close = np.linspace(90, 30, n)
    high = close + 1.0
    low = close - 1.0
    opened = close + 0.4
    for i, peak, settled, start in ((28, 110.0, 100.0, 108.0), (58, 86.0, 74.0, 84.0)):
        high[i] = peak
        close[i] = settled
        opened[i] = start
        low[i] = settled - 2.0
        for j in range(i - 4, i + 5):
            if j != i and 0 <= j < n:
                high[j] = min(high[j], peak - 8.0)
    return pd.DataFrame(
        {"open": opened, "high": high, "low": low, "close": close, "volume": 1_000_000.0},
        index=index,
    )


def _with_breakout(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    # Bar 78 clears the line. Bar 79 tags it and closes as a strong bull.
    out.iloc[78, out.columns.get_loc("open")] = 72.0
    out.iloc[78, out.columns.get_loc("high")] = 82.0
    out.iloc[78, out.columns.get_loc("low")] = 71.0
    out.iloc[78, out.columns.get_loc("close")] = 80.0
    out.iloc[79, out.columns.get_loc("open")] = 70.0
    out.iloc[79, out.columns.get_loc("high")] = 76.0
    out.iloc[79, out.columns.get_loc("low")] = 69.0
    out.iloc[79, out.columns.get_loc("close")] = 75.0
    return out


def test_two_descending_pivots_define_the_line():
    info = describe_line(_two_peaks())
    pair = info["pair"]
    assert pair is not None
    assert pair["date1"] == pd.Timestamp("2021-02-11")
    assert pair["date2"] == pd.Timestamp("2021-03-25")
    assert pair["y2"] < pair["y1"]
    assert pair["y1"] == 110.0
    assert pair["y2"] == 86.0


def test_three_touch_variant_rejects_a_two_touch_line():
    frame = _two_peaks()
    assert describe_line(frame)["pair"] is not None
    variant = describe_line(frame, {**DAILY_DEFAULTS, "require_three_touches": True})
    assert variant["pair"] is None


def test_rejection_short_uses_the_confirmation_bar():
    shorts = find_trend_setups(_two_peaks(), {**DAILY_DEFAULTS, "include_long": False, "include_short": True}, symbol="X")
    assert len(shorts) == 1
    assert shorts[0].direction == "short"
    assert shorts[0].signal_time == pd.Timestamp("2021-03-31")
    assert shorts[0].fill_time == pd.Timestamp("2021-04-01")
    assert shorts[0].stop == 86.0


def test_a_close_through_the_segment_removes_the_line_and_the_short():
    frame = _two_peaks()
    # Several equal closes through the segment. None of them is a unique pivot,
    # and the pair between the two peaks is no longer a clean line.
    for i in range(40, 47):
        frame.iloc[i, frame.columns.get_loc("open")] = 100.0
        frame.iloc[i, frame.columns.get_loc("high")] = 105.0
        frame.iloc[i, frame.columns.get_loc("low")] = 99.0
        frame.iloc[i, frame.columns.get_loc("close")] = 104.0
    assert describe_line(frame)["pair"] is None
    shorts = find_trend_setups(frame, {**DAILY_DEFAULTS, "include_long": False, "include_short": True}, symbol="X")
    assert shorts == []


def test_long_retest_fills_next_open_and_ignores_a_close_back_under():
    frame = _with_breakout(_two_peaks(extra=5))
    longs = find_trend_setups(frame, DAILY_DEFAULTS, symbol="X")
    assert len(longs) == 1
    assert longs[0].direction == "long"
    assert longs[0].kind == "C"
    assert longs[0].signal_time == pd.Timestamp("2021-04-23")
    assert longs[0].fill_time == pd.Timestamp("2021-04-26")
    assert longs[0].stop == 69.0
    truncated = frame.loc[: longs[0].fill_time]
    again = find_trend_setups(truncated, DAILY_DEFAULTS, symbol="X")
    assert [(row.signal_time, row.fill_time, row.stop) for row in again] == [
        (longs[0].signal_time, longs[0].fill_time, longs[0].stop)
    ]
    failed = _with_breakout(_two_peaks(extra=5))
    failed.iloc[79, failed.columns.get_loc("close")] = 60.0
    failed.iloc[79, failed.columns.get_loc("open")] = 74.0
    assert find_trend_setups(failed, DAILY_DEFAULTS, symbol="X") == []


def test_forty_five_dte_contract_is_skipped_when_it_does_not_fit():
    index = pd.bdate_range("2024-01-02", periods=40)
    close = 800.0 + np.linspace(0.0, 4.0, 40)
    frame = pd.DataFrame(
        {"open": close, "high": close + 1.0, "low": close - 1.0, "close": close, "volume": 1_000_000.0},
        index=index,
    )
    setup = Setup(
        symbol="SPY",
        direction="long",
        kind="C",
        signal_time=index[29],
        fill_time=index[30],
        anchor_time=index[20],
        stop=760.0,
        atr=5.0,
        reference=860.0,
    )
    params = dict(DAILY_DEFAULTS)
    params["expression"] = "single"
    params["dte"] = 45
    stats = simulate([setup], {"SPY": frame}, {"SPY": frame}, params, session_filter=False)
    assert stats.metrics["trades"] == 0
    assert stats.premium_skipped == 1
    params["expression"] = "spread"
    params["risk_fraction"] = 0.05
    params["spread_width"] = 5.0
    setup.symbol = "AMD"
    spread = simulate([setup], {"AMD": frame}, {"AMD": frame}, params, session_filter=False)
    assert spread.metrics["trades"] == 0
    assert spread.premium_skipped == 1


def test_unh_is_not_a_dow_member_before_it_was_added():
    assert is_member("UNH", date(2012, 9, 21)) is False
    assert is_member("UNH", date(2012, 9, 24)) is True
