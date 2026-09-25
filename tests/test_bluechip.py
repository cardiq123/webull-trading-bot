"""Signal, membership, and option-model tests for the Dow reversal."""

from datetime import date

import numpy as np
import pytest
import pandas as pd

from webull_bot.options.fees import option_leg_fees
from webull_bot.options.overlay import simulate_overlay
from webull_bot.options.pricing import call_delta, call_price
from webull_bot.strategies.bluechip_reversal import (
    BluechipReversal,
    anchored_vwap,
    bullish_divergence,
    confirmed_pivot_low,
    reclaims,
)
from webull_bot.universe_dow import is_member, members_on


def test_dow_membership_stays_at_thirty_and_follows_effective_dates():
    for day in (
        date(2009, 6, 8),
        date(2012, 9, 24),
        date(2013, 9, 23),
        date(2015, 3, 19),
        date(2019, 4, 2),
        date(2020, 4, 6),
        date(2020, 8, 31),
        date(2024, 2, 26),
        date(2024, 11, 8),
        date(2026, 6, 29),
        date(2026, 9, 25),
    ):
        assert len(members_on(day)) == 30
    assert "GS" in members_on(date(2014, 6, 1))
    assert "AAPL" not in members_on(date(2014, 6, 1))
    assert "T" in members_on(date(2015, 3, 18))
    assert "AAPL" not in members_on(date(2015, 3, 18))
    assert "AAPL" in members_on(date(2015, 3, 19))
    assert "T" not in members_on(date(2015, 3, 19))
    april = set(members_on(date(2019, 4, 2)))
    for symbol in ("AAPL", "GS", "NKE", "V", "UNH", "WBA", "DOW"):
        assert symbol in april
    for symbol in ("KFT", "AA", "BAC", "HPQ", "T", "DD", "GE"):
        assert symbol not in april
    assert "NVDA" in members_on(date(2024, 11, 8))
    assert "SHW" in members_on(date(2024, 11, 8))
    assert "INTC" not in members_on(date(2024, 11, 8))
    assert "DOW" not in members_on(date(2024, 11, 8))
    assert "GOOGL" in members_on(date(2026, 9, 25))
    assert "VZ" not in members_on(date(2026, 9, 25))
    assert is_member("AAPL", date(2011, 6, 1)) is False


def test_pivot_low_is_confirmed_only_after_the_right_bars():
    low = pd.Series([10.0] * 21)
    low.iloc[10] = 5.0
    confirmed = confirmed_pivot_low(low, left=5, right=5)
    assert confirmed.iloc[:15].isna().all()
    assert confirmed.iloc[15] == 5.0
    # A later lower print cannot move the confirmation that already happened.
    extended = pd.concat([low, pd.Series([1.0])])
    again = confirmed_pivot_low(extended, left=5, right=5)
    assert again.iloc[15] == 5.0


def test_bullish_divergence_needs_a_lower_low_and_a_higher_rsi():
    low = pd.Series([10.0] * 30)
    low.iloc[10] = 8.0
    low.iloc[20] = 7.0
    rsi = pd.Series([50.0] * 30)
    rsi.iloc[10] = 20.0
    rsi.iloc[20] = 30.0
    flag = bullish_divergence(low, rsi, 5, 5)
    assert bool(flag.iloc[25])
    assert not bool(flag.iloc[15])
    rsi.iloc[20] = 10.0
    lower_rsi = bullish_divergence(low, rsi, 5, 5)
    assert not bool(lower_rsi.iloc[25])


def test_reclaim_is_false_when_price_was_already_above_the_level():
    close = pd.Series([10.0, 11.0, 12.0, 13.0])
    level = pd.Series([9.0, 10.0, 11.0, 12.0])
    assert not bool(reclaims(close, level).any())
    crossed = reclaims(pd.Series([10.0, 9.0, 11.0]), pd.Series([10.0, 10.0, 10.0]))
    assert list(crossed.astype(bool)) == [False, False, True]


def test_param_grid_is_the_six_preregistered_variants():
    grid = BluechipReversal().param_grid()
    assert len(grid) == 6
    assert grid[0]["rsi_length"] == 2
    assert grid[0]["trigger"] == "ema10"
    assert grid[0]["require_divergence"] is True
    assert grid[0]["trend_filter"] is False
    assert grid[1]["rsi_length"] == 14 and grid[1]["trigger"] == "ema10"
    assert grid[3]["trigger"] == "avwap" and grid[3]["rsi_length"] == 2
    assert grid[4]["trend_filter"] is True and grid[4]["rsi_length"] == 2
    assert grid[5]["require_divergence"] is False


def test_non_member_has_no_entries_and_signals_ignore_future_bars():
    rng = np.random.default_rng(3)
    index = pd.bdate_range("2010-01-04", periods=400)
    price = 100 * np.exp(np.cumsum(rng.normal(0.0002, 0.01, len(index))))
    frame = pd.DataFrame(
        {
            "open": price,
            "high": price * 1.01,
            "low": price * 0.99,
            "close": price,
            "volume": rng.integers(1_000_000, 2_000_000, len(index)),
        },
        index=index,
    )
    strategy = BluechipReversal()
    params = dict(strategy.default_params)
    params["symbols"] = ["AAPL"]
    early = strategy.generate({"AAPL": frame.iloc[:300]}, None, params)["AAPL"]
    assert not bool(early["entry_next_open"].any())

    member_index = pd.bdate_range("2016-01-04", periods=500)
    member_price = 100 * np.exp(np.cumsum(rng.normal(0.0002, 0.012, len(member_index))))
    member = pd.DataFrame(
        {
            "open": member_price,
            "high": member_price * 1.01,
            "low": member_price * 0.99,
            "close": member_price,
            "volume": rng.integers(1_000_000, 2_000_000, len(member_index)),
        },
        index=member_index,
    )
    params["symbols"] = ["MSFT"]
    cut = member_index[400]
    full = strategy.generate({"MSFT": member}, None, params)["MSFT"]
    part = strategy.generate({"MSFT": member.loc[:cut]}, None, params)["MSFT"]
    pd.testing.assert_series_equal(
        full.loc[:cut, "entry_next_open"].astype(bool),
        part["entry_next_open"].astype(bool),
        check_names=False,
    )


def test_anchored_vwap_resets_at_the_confirmed_pivot():
    index = pd.bdate_range("2020-01-01", periods=6)
    frame = pd.DataFrame(
        {
            "high": [10, 10, 10, 12, 12, 12],
            "low": [10, 10, 8, 12, 12, 12],
            "close": [10, 10, 8, 12, 12, 12],
            "volume": [1, 1, 1, 1, 1, 1],
        },
        index=index,
    )
    pivot = pd.Series([np.nan, np.nan, np.nan, np.nan, 8.0, np.nan], index=index)
    vwap = anchored_vwap(frame, pivot, right=2)
    # Anchor is bar 2. Typical price there is (10+8+8)/3, then two 12s.
    expected = (((10 + 8 + 8) / 3) + 12 + 12) / 3
    assert abs(vwap.iloc[4] - expected) < 1e-9


def test_black_scholes_call_matches_the_textbook_case():
    price = call_price(100, 100, 1.0, 0.2, 0.0, 0.0)
    assert abs(price - 7.965567) < 1e-3
    near = call_delta(100, 90, 1.0, 0.2, 0.02, 0.018)
    far = call_delta(100, 120, 1.0, 0.2, 0.02, 0.018)
    assert near > far


def test_option_sell_fee_includes_taf_minimum_and_sec():
    sold = option_leg_fees(1, 2.0, sell=True)
    bought = option_leg_fees(1, 2.0, sell=False)
    assert bought == pytest.approx(0.02 + 0.02 + 0.0003)
    assert sold == pytest.approx(bought + 0.01 + 0.0000206 * 200)


def test_options_overlay_prices_a_call_and_a_spread_from_one_stock_trade():
    index = pd.bdate_range("2020-01-02", periods=80)
    rng = np.random.default_rng(1)
    spot = 100 * np.exp(np.cumsum(rng.normal(0.0, 0.01, len(index))))
    frame = pd.DataFrame(
        {
            "open": spot,
            "high": spot * 1.01,
            "low": spot * 0.99,
            "close": spot,
            "volume": np.full(len(index), 1_000_000),
        },
        index=index,
    )
    trades = pd.DataFrame(
        [
            {
                "symbol": "MSFT",
                "entry_time": index[40],
                "exit_time": index[50],
                "entry_price": float(spot[40]),
                "exit_price": float(spot[50]),
                "reason": "target",
                "bars_held": 10,
            }
        ]
    )
    bars = {"MSFT": frame, "SPY": frame}
    call = simulate_overlay(trades, bars, structure="call")
    spread = simulate_overlay(trades, bars, structure="spread")
    assert call["metrics"]["trades"] == 1
    assert spread["metrics"]["trades"] == 1
    assert np.isfinite(call["metrics"]["total_return"])
    assert np.isfinite(spread["metrics"]["total_return"])
    # A debit spread cannot lose much more than the premium paid, plus fees.
    spread_trade = spread["trades"].iloc[0]
    assert spread_trade["pnl"] > -spread_trade["entry_price"] * 100 * spread_trade["quantity"] * 1.05
