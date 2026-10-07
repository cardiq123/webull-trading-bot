"""Frozen checks for the support and resistance level set."""

import numpy as np
import pandas as pd

from webull_bot.chart_reads.levels import (
    IMPROVE_MIN_LEVEL_SHARE,
    IMPROVE_MIN_TRADES,
    build_levels,
    cluster_prices,
    improves_oos,
    select_target,
)
from webull_bot.chart_reads.params import BREAKOUT_DEFAULTS, DAILY_DEFAULTS, DEFAULTS


def _frame(n, **overrides) -> pd.DataFrame:
    index = pd.bdate_range("2020-01-01", periods=n)
    low = np.full(n, 20.0)
    high = np.full(n, 21.0)
    open_ = np.full(n, 20.4)
    close = np.full(n, 20.5)
    for key, values in overrides.items():
        target = {"low": low, "high": high, "open": open_, "close": close}[key]
        for pos, value in values.items():
            target[pos] = value
    # Keep the bar internally consistent after the overrides.
    high = np.maximum(high, np.maximum(open_, close))
    low = np.minimum(low, np.minimum(open_, close))
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close}, index=index)


def test_floor_pivots_use_the_prior_bar_only():
    frame = _frame(6, high={0: 110.0}, low={0: 90.0}, close={0: 100.0}, open={0: 100.0})
    table = build_levels(frame)
    assert table.prices(0, "floor") == tuple()
    assert table.prices(1, "floor") == (100.0, 110.0, 90.0, 120.0, 80.0)
    assert table.prices(1, "prior_day") == (110.0, 90.0)
    # Changing a later bar does not rewrite yesterday's floor.
    edited = frame.copy()
    edited.iloc[-1, edited.columns.get_loc("high")] = 500.0
    again = build_levels(edited)
    assert again.prices(1, "floor") == table.prices(1, "floor")


def test_intraday_prior_day_is_the_previous_session():
    index = pd.to_datetime(
        [
            "2024-01-02 09:30",
            "2024-01-02 10:30",
            "2024-01-03 09:30",
            "2024-01-03 10:30",
        ]
    )
    frame = pd.DataFrame(
        {
            "open": [9.0, 10.0, 11.0, 11.0],
            "high": [10.0, 12.0, 13.0, 13.0],
            "low": [8.0, 9.0, 10.5, 10.5],
            "close": [9.0, 11.0, 12.0, 12.5],
        },
        index=index,
    )
    table = build_levels(frame)
    assert table.prices(0, "prior_day") == tuple()
    assert table.prices(2, "prior_day") == (12.0, 8.0)
    pivot = (12.0 + 8.0 + 11.0) / 3.0
    span = 4.0
    assert table.prices(3, "floor") == (
        pivot,
        2.0 * pivot - 8.0,
        2.0 * pivot - 12.0,
        pivot + span,
        pivot - span,
    )


def test_fibonacci_and_rising_trendline_on_a_known_swing():
    # Pivot low 10 at bar 5, pivot high 30 at bar 12, later pivot low 14 at bar 22.
    frame = _frame(
        40,
        low={5: 10.0, 22: 14.0},
        high={12: 30.0},
    )
    table = build_levels(frame)
    # Confirmed four bars later, so the line exists from bar 27 (confirm of bar 22 is 26).
    support = table.trend_support[27]
    slope = (14.0 - 10.0) / (22 - 5)
    assert support == 14.0 + slope * (27 - 22)
    # Latest swing at bar 27 is the high at 12 down to the low at 22.
    height = 30.0 - 14.0
    fibs = table.prices(27, "fib")
    assert fibs == (14.0 + 0.382 * height, 14.0 + 0.500 * height, 14.0 + 0.618 * height)
    # The second pivot low confirms on bar 26, so bar 26 itself cannot see it.
    assert table.prices(26, "fib") != fibs
    assert np.isnan(table.trend_support[26])


def test_flip_after_a_close_through_the_pivot():
    frame = _frame(30, high={8: 30.0})
    frame.loc[frame.index[18], "high"] = 32.0
    frame.loc[frame.index[18], "close"] = 31.0
    table = build_levels(frame)
    # Pivot high at 8 confirms at 12, so it is known from bar 13. The close
    # through it is bar 18, which is the first bar that can list it as flipped.
    assert 30.0 not in table.prices(17, "flipped")
    assert 30.0 in table.prices(18, "flipped")


def test_demand_zone_is_the_base_before_the_impulse():
    frame = _frame(40)
    # A long quiet stretch so ATR is about 1, then a tight base and a thrust.
    for pos in range(20, 24):
        frame.iloc[pos, frame.columns.get_loc("open")] = 20.2
        frame.iloc[pos, frame.columns.get_loc("high")] = 20.6
        frame.iloc[pos, frame.columns.get_loc("low")] = 20.0
        frame.iloc[pos, frame.columns.get_loc("close")] = 20.4
    frame.iloc[24, frame.columns.get_loc("open")] = 20.2
    frame.iloc[24, frame.columns.get_loc("low")] = 20.0
    frame.iloc[24, frame.columns.get_loc("close")] = 24.0
    frame.iloc[24, frame.columns.get_loc("high")] = 24.2
    table = build_levels(frame)
    assert 20.6 not in table.prices(24, "zone")
    assert 20.6 in table.prices(25, "zone")


def test_confluence_needs_two_sources():
    assert cluster_prices({"horizontal": [100.0, 100.2]}, 0.5) == []
    assert cluster_prices({"horizontal": [100.0], "floor": [100.2]}, 0.5) == [100.1]
    assert cluster_prices({"horizontal": [100.0], "floor": [103.0]}, 0.5) == []


def test_target_stays_between_half_and_four_r():
    # 0.5R is included, matching the published target filter. 4R is the far cap.
    assert select_target([101.0, 103.0, 110.0], "long", 100.0, 2.0) == 101.0
    assert np.isnan(select_target([100.5], "long", 100.0, 2.0))
    assert np.isnan(select_target([109.0], "long", 100.0, 2.0))
    assert select_target([99.0, 97.0, 90.0], "short", 100.0, 2.0) == 99.0


def test_later_bars_do_not_change_an_earlier_level():
    frame = _frame(40, low={5: 10.0, 15: 12.0}, high={8: 30.0, 16: 28.0})
    original = build_levels(frame)
    edited = frame.copy()
    edited.iloc[-1, edited.columns.get_loc("high")] = 900.0
    edited.iloc[-1, edited.columns.get_loc("close")] = 900.0
    changed = build_levels(edited)
    for source in ("horizontal", "floor", "prior_day", "zone", "fib", "trendline", "flipped", "confluence"):
        assert original.prices(20, source) == changed.prices(20, source)


def test_improvement_rule_does_not_accept_a_thin_or_worse_book():
    baseline = {"trades": 40, "ending_equity": 900.0, "profit_factor": 0.9, "max_drawdown": -0.20}
    better = {"trades": 40, "ending_equity": 980.0, "profit_factor": 1.0, "max_drawdown": -0.22}
    assert improves_oos(baseline, better, IMPROVE_MIN_LEVEL_SHARE)
    assert not improves_oos(baseline, better, IMPROVE_MIN_LEVEL_SHARE - 0.01)
    thin = dict(better)
    thin["trades"] = IMPROVE_MIN_TRADES - 1
    assert not improves_oos(baseline, thin, 1.0)
    deep = dict(better)
    deep["max_drawdown"] = -0.26
    assert not improves_oos(baseline, deep, 1.0)
    weaker = dict(better)
    weaker["profit_factor"] = 0.8
    assert not improves_oos(baseline, weaker, 1.0)


def test_published_defaults_are_unchanged():
    assert "target_mode" not in DEFAULTS
    assert DEFAULTS["reward_r"] == 2.0
    assert DAILY_DEFAULTS["level_source"] == "reference"
    assert DAILY_DEFAULTS["target_mode"] == "level"
    assert BREAKOUT_DEFAULTS["level_source"] == "reference"
    assert BREAKOUT_DEFAULTS["target_mode"] == "level"
