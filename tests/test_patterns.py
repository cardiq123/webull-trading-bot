"""Detectors for support, trendlines, candles, and wedges."""

import numpy as np
import pandas as pd
import pytest

from webull_bot.options.premium_exit import simulate_premium_book
from webull_bot.options.pricing import call_price, put_price
from webull_bot.patterns import (
    bullish_reversal_candle,
    fit_line,
    horizontal_support,
    prior_month_reference_low,
    rising_trendline,
    strong_breakout_candle,
    wedge_lines,
)
from webull_bot.strategies.support_reversal import SupportReversal
from webull_bot.strategies.wedge_breakout import WedgeBreakout


def _flat(index, price=20.0):
    return pd.DataFrame(
        {
            "open": price,
            "high": price + 0.4,
            "low": price - 0.4,
            "close": price,
            "volume": 1_000_000,
        },
        index=index,
    )


def test_grids_are_the_six_preregistered_variants():
    support = SupportReversal().param_grid()
    wedge = WedgeBreakout().param_grid()
    assert len(support) == 6
    assert support[0]["low_mode"] == "d20"
    assert support[0]["support"] == "horizontal"
    assert support[0]["rsi_filter"] is False
    assert support[1]["low_mode"] == "ytd" and support[1]["support"] == "horizontal"
    assert support[3]["support"] == "trendline" and support[3]["low_mode"] == "d20"
    assert support[4]["rsi_filter"] is True
    assert support[5]["ema_filter"] is True
    assert len(wedge) == 6
    assert wedge[0]["pattern"] == "wedge"
    assert wedge[0]["buffer_atr"] == 0.25
    assert wedge[0]["volume_filter"] is False
    assert wedge[1]["pattern"] == "horizontal" and wedge[1]["lookback"] == 40
    assert wedge[2]["volume_filter"] is True and wedge[2]["pattern"] == "wedge"
    assert wedge[5]["long_only"] is True and wedge[5]["pattern"] == "wedge"


def test_horizontal_support_needs_two_nearby_pivots_and_ignores_the_future():
    index = pd.bdate_range("2020-01-01", periods=40)
    low = pd.Series(20.0, index=index)
    low.iloc[8] = 10.0
    low.iloc[16] = 10.2
    atr = pd.Series(1.0, index=index)
    zone = horizontal_support(low, atr, left=2, right=2, zone_atr=1.25, lookback=30, min_touches=2)
    # Both pivots are confirmed by bar 18 (16+2). A later low near 10 is in the zone.
    low.iloc[22] = 10.1
    zone = horizontal_support(low, atr, left=2, right=2, zone_atr=1.25, lookback=30, min_touches=2)
    assert bool(zone.iloc[22])
    assert not bool(zone.iloc[10])
    # A far-away low is not support.
    low.iloc[22] = 16.0
    far = horizontal_support(low, atr, left=2, right=2, zone_atr=1.25, lookback=30, min_touches=2)
    assert not bool(far.iloc[22])
    # Truncating after the touch does not change the touch.
    full = horizontal_support(low.iloc[:23].copy(), atr.iloc[:23], left=2, right=2, zone_atr=1.25, lookback=30)
    # restore the near low for the comparison above; the far test is separate.
    low.iloc[22] = 10.1
    full = horizontal_support(low, atr, left=2, right=2, zone_atr=1.25, lookback=30, min_touches=2)
    part = horizontal_support(low.iloc[:23], atr.iloc[:23], left=2, right=2, zone_atr=1.25, lookback=30, min_touches=2)
    pd.testing.assert_series_equal(full.iloc[:23].astype(bool), part.astype(bool), check_names=False)


def test_rising_trendline_uses_only_confirmed_pivots():
    index = pd.bdate_range("2020-01-01", periods=40)
    low = pd.Series(30.0, index=index)
    low.iloc[6] = 10.0
    low.iloc[16] = 14.0
    line = rising_trendline(low, left=2, right=2)
    # Confirmed after bar 18. Slope (14-10)/(16-6) = 0.4. At bar 22: 14 + 0.4*6 = 16.4.
    assert line.iloc[20] == pytest.approx(14.0 + 0.4 * (20 - 16))
    assert pd.isna(line.iloc[17])
    low.iloc[30] = 1.0
    again = rising_trendline(low, left=2, right=2)
    assert again.iloc[20] == pytest.approx(line.iloc[20])
    prefix = rising_trendline(low.iloc[:23], left=2, right=2)
    assert prefix.iloc[20] == pytest.approx(again.iloc[20])


def test_chart_anchors_match_the_rising_trendline():
    from webull_bot.patterns import _pivot_points, confirmed_pivot_low
    from webull_bot.research_patterns import _trendline_anchors

    index = pd.bdate_range("2020-01-01", periods=40)
    low = pd.Series(30.0, index=index)
    low.iloc[6] = 10.0
    low.iloc[16] = 14.0
    points = _pivot_points(confirmed_pivot_low(low, 2, 2), 2)
    anchors = _trendline_anchors(points, 20)
    assert anchors is not None
    earlier, later, slope = anchors
    assert earlier == (6, 10.0)
    assert later == (16, 14.0)
    assert slope == pytest.approx(0.4)
    assert _trendline_anchors(points, 17) is None


def test_prior_month_low_does_not_use_the_rest_of_this_month():
    index = pd.bdate_range("2020-01-02", periods=45)
    low = pd.Series(np.linspace(20, 19, len(index)), index=index)
    low.iloc[-1] = 1.0
    level = prior_month_reference_low(low)
    # A day in January cannot see the final crash if that crash is later in January
    # and we cut the series before it.
    cut = index[20]
    full = prior_month_reference_low(low)
    part = prior_month_reference_low(low.loc[:cut])
    pd.testing.assert_series_equal(full.loc[:cut], part, check_names=False)


def test_bullish_candle_rules():
    index = pd.bdate_range("2020-01-01", periods=4)
    frame = pd.DataFrame(
        {
            "open": [10, 9, 10, 8],
            "high": [11, 12, 11, 12],
            "low": [8, 9.5, 6, 7.5],
            "close": [9, 11.5, 10.2, 11.8],
            "volume": 1,
        },
        index=index,
    )
    # Bar 1 engulfs bar 0. Bar 2 is a hammer (lower wick 4, body 0.2). Bar 3 closes in the top quarter through the prior high.
    flags = bullish_reversal_candle(frame)
    assert bool(flags.iloc[1])
    assert bool(flags.iloc[2])
    assert bool(flags.iloc[3])
    doji = pd.DataFrame(
        {
            "open": [10.0, 10.0, 10.0, 10.0],
            "high": [10.2, 10.2, 10.2, 10.2],
            "low": [9.8, 9.8, 9.8, 9.8],
            "close": [10.0, 10.0, 10.0, 10.0],
            "volume": 1,
        },
        index=index,
    )
    assert not bool(bullish_reversal_candle(doji).any())


def test_breakout_candle_requires_a_wide_body_in_the_extreme_quarter():
    index = pd.bdate_range("2020-01-01", periods=2)
    strong = pd.DataFrame(
        {"open": [10.0, 10.0], "high": [11.0, 12.0], "low": [9.0, 10.0], "close": [10.2, 11.8], "volume": 1},
        index=index,
    )
    weak = strong.copy()
    weak.iloc[1, weak.columns.get_loc("close")] = 10.4
    weak.iloc[1, weak.columns.get_loc("open")] = 10.2
    assert bool(strong_breakout_candle(strong, side="bull").iloc[1])
    assert not bool(strong_breakout_candle(weak, side="bull").iloc[1])
    bear = pd.DataFrame(
        {"open": [10.0], "high": [10.2], "low": [8.0], "close": [8.2], "volume": 1},
        index=index[:1],
    )
    assert bool(strong_breakout_candle(bear, side="bear").iloc[0])


def test_fit_line_and_a_constructed_falling_wedge():
    slope, intercept = fit_line([0, 10], [0, 10])
    assert slope == pytest.approx(1.0)
    assert intercept == pytest.approx(0.0)
    index = pd.bdate_range("2021-01-04", periods=48)
    high = pd.Series(20.0, index=index)
    low = pd.Series(40.0, index=index)
    # Unique pivot highs stepping down and pivot lows stepping down more slowly.
    for i, price in ((6, 40.0), (18, 36.0), (30, 33.0)):
        high.iloc[i - 2 : i + 3] = price - 3
        high.iloc[i] = price
    for i, price in ((12, 24.0), (24, 22.0), (36, 21.0)):
        low.iloc[i - 2 : i + 3] = price + 3
        low.iloc[i] = price
    lines = wedge_lines(high, low, left=2, right=2, lookback=40, min_span=15, contraction=0.95)
    kinds = set(lines.loc[lines["kind"] != "", "kind"])
    assert "falling" in kinds
    # A pivot that is not confirmed yet cannot change an earlier line.
    high.iloc[44] = 100
    low.iloc[44] = 1
    again = wedge_lines(high, low, left=2, right=2, lookback=40, min_span=15, contraction=0.95)
    pd.testing.assert_series_equal(lines["upper"].iloc[:40], again["upper"].iloc[:40], check_names=False)


def test_put_call_parity_and_premium_target_rules():
    call = call_price(100, 100, 0.5, 0.2, 0.02, 0.018)
    put = put_price(100, 100, 0.5, 0.2, 0.02, 0.018)
    parity = call - np.exp(-0.018 * 0.5) * 100 + np.exp(-0.02 * 0.5) * 100
    assert put == pytest.approx(parity)

    index = pd.bdate_range("2020-01-02", periods=40)
    rng = np.random.default_rng(2)
    spot = 100 * np.exp(np.cumsum(rng.normal(0.0, 0.01, len(index))))
    spot[30:] = spot[29]
    frame = pd.DataFrame(
        {"open": spot, "high": spot * 1.01, "low": spot * 0.99, "close": spot, "volume": 1_000_000.0},
        index=index,
    )
    # One session later the high is far enough that a call's bid clears +30%.
    jump = frame.copy()
    jump.iloc[31, jump.columns.get_loc("high")] = spot[31] * 1.35
    entries = [_entry(index, 30, "call")]
    hit = simulate_premium_book(entries, {"MSFT": jump, "SPY": jump}, path="extreme")
    assert hit["metrics"]["trades"] == 1
    assert hit["trades"].iloc[0]["reason"] == "premium_target"
    assert hit["metrics"]["target_hit_rate"] == pytest.approx(1.0)

    both = frame.copy()
    both.iloc[31, both.columns.get_loc("high")] = spot[31] * 1.8
    both.iloc[31, both.columns.get_loc("low")] = spot[31] * 0.4
    stopped = simulate_premium_book(entries, {"MSFT": both, "SPY": both}, path="extreme")
    assert stopped["trades"].iloc[0]["reason"] == "premium_stop"

    quiet = simulate_premium_book(entries, {"MSFT": frame, "SPY": frame}, path="close", max_hold=3)
    assert quiet["metrics"]["trades"] == 1
    assert quiet["trades"].iloc[0]["reason"] in {"time_stop", "premium_stop", "premium_target", "invalidation"}


def _entry(index, signal_i, right):
    level = np.full(len(index), np.nan)
    level[signal_i] = 1.0
    return {
        "symbol": "MSFT",
        "signal_index": signal_i,
        "fill_time": index[signal_i + 1],
        "right": right,
        "inv_level": 1.0,
        "inv_slope": 0.0,
        "exit_flags": np.zeros(len(index), dtype=bool),
        "index": index,
    }
