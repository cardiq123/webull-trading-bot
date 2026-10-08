"""Dip and rip definitions stay frozen, causal, and out of the holdout."""

import inspect
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from webull_bot.chart_reads.tendency import (
    FDR_Q,
    HOLDOUT_END,
    HOLDOUT_START,
    INTRADAY_GATE,
    MIN_EVENTS,
    SYMBOLS,
    TRAIN_END,
    TRAIN_START,
    assert_window_visible,
    benjamini_hochberg,
    event_mask,
    n_trials,
    prepare,
    run_search,
    welch_p,
    _forward_indexes,
    _trade_orders,
)

FORBIDDEN = (
    "forward_options",
    "forward_chop",
    "forward_vwap",
    "place_option_order",
    "live_trading_enabled",
    "option_quote",
)


def test_universe_windows_and_trial_count_are_frozen():
    assert "UNH" in SYMBOLS and "JPM" in SYMBOLS and "NFLX" in SYMBOLS
    assert "GOOGL" in SYMBOLS and "GOOG" not in SYMBOLS
    assert INTRADAY_GATE == ("SPY", "QQQ")
    assert TRAIN_START < TRAIN_END < HOLDOUT_START <= HOLDOUT_END
    assert HOLDOUT_START == date(2026, 7, 7)
    assert HOLDOUT_END == date(2026, 10, 6)
    assert FDR_Q == 0.10
    assert MIN_EVENTS == 30
    assert n_trials() == 22 * 8 * 3 + 2 * 2 * 10 * 6
    with pytest.raises(RuntimeError):
        assert_window_visible(HOLDOUT_START, allow_holdout=False)


def test_search_cannot_see_the_holdout():
    source = inspect.getsource(run_search)
    assert "score_holdout" not in source
    assert "allow_holdout=True" not in source
    for path in (
        "src/webull_bot/chart_reads/tendency.py",
        "src/webull_bot/chart_reads/research_tendency.py",
    ):
        text = open(path, encoding="utf-8").read()
        for name in FORBIDDEN:
            assert name not in text


def test_a_band_break_that_stays_outside_is_one_event():
    index = pd.date_range("2024-06-03 09:30", periods=6, freq="5min", tz="America/New_York")
    frame = pd.DataFrame(
        {
            "close": [100, 90, 89, 100, 110, 111],
            "vwap": [100, 100, 100, 100, 100, 100],
            "band": [2, 2, 2, 2, 2, 2],
            "rsi": [50, 50, 50, 50, 50, 50],
            "prior_atr": [1, 1, 1, 1, 1, 1],
            "prior_close": [100, 100, 100, 100, 100, 100],
            "open": [100, 100, 100, 100, 100, 100],
            "run_high": [100, 100, 100, 100, 100, 100],
            "run_low": [100, 100, 100, 100, 100, 100],
            "is_first": [True, False, False, False, False, False],
            "move3": [0, 0, 0, 0, 0, 0],
        },
        index=index,
    )
    dips = event_mask(frame, "vwap_dip")
    rips = event_mask(frame, "vwap_rip")
    assert list(dips) == [False, True, False, False, False, False]
    assert list(rips) == [False, False, False, False, True, False]


def test_thirty_minutes_is_two_fifteen_minute_bars():
    index = pd.date_range("2024-06-03 09:30", periods=8, freq="15min", tz="America/New_York")
    frame = pd.DataFrame({"close": np.arange(8)}, index=index)
    frame.attrs["timeframe"] = "15m"
    forward = _forward_indexes(frame, "m30", "15m")
    assert int(forward[0]) == 2
    assert int(forward[6]) == -1


def test_later_prices_do_not_change_an_earlier_event():
    index = pd.bdate_range("2024-01-02", periods=40)
    close = np.full(40, 100.0)
    close[25] = 70.0
    frame = pd.DataFrame(
        {
            "open": close,
            "high": close + 1,
            "low": close - 1,
            "close": close,
            "volume": np.full(40, 1_000_000.0),
        },
        index=index,
    )
    prepared = prepare(frame, frame, "1d")
    changed = frame.copy()
    changed.loc[changed.index[-1], "close"] = 1.0
    later = prepare(changed, changed, "1d")
    left = event_mask(prepared, "rsi_dip")[:-1]
    right = event_mask(later, "rsi_dip")[:-1]
    assert np.array_equal(left, right)


def test_welch_refuses_a_short_sample():
    assert welch_p(np.ones(10), np.ones(10)) == 1.0
    noisy = np.concatenate([np.full(40, 0.02), np.full(40, 0.0)])
    base = np.zeros(80)
    assert welch_p(noisy, base) < 0.05


def test_confirmation_is_required_and_a_gap_through_the_stop_is_skipped():
    index = pd.bdate_range("2024-01-02", periods=6)
    frame = pd.DataFrame(
        {
            "open": [10, 10, 9, 8, 11, 11],
            "high": [10, 10, 10, 12, 11, 11],
            "low": [9, 7, 7, 8, 10, 10],
            "close": [10, 7.5, 9.5, 11, 11, 11],
            "volume": [100, 100, 100, 100, 100, 100],
            "vwap": [10, 10, 10, 10, 10, 10],
            "band": [1, 1, 1, 1, 1, 1],
            "rsi": [50, 20, 25, 40, 50, 50],
            "sma20": [10, 10, 10, 10, 10, 10],
            "prior_atr": [1, 1, 1, 1, 1, 1],
            "prior_close": [10, 10, 10, 10, 10, 10],
            "run_high": [10, 10, 10, 12, 11, 11],
            "run_low": [9, 8, 7, 8, 10, 10],
            "is_first": [True, False, False, False, False, False],
            "move3": [0, 0, 0, 0, 0, 0],
        },
        index=index,
    )
    frame.attrs["timeframe"] = "1d"
    orders = _trade_orders(frame, "vwap_dip")
    assert orders
    assert orders[0].side == "long"
    frame.loc[frame.index[3], "open"] = 7.0
    skipped = _trade_orders(frame, "vwap_dip")
    assert skipped == []


def test_empty_search_counts_every_cell():
    result = run_search({})
    assert result["n_combos"] == n_trials()
    assert all(row["label"] == "inconsistent" for row in result["cells"])
    q = benjamini_hochberg([0.01, 0.2, 0.5])
    assert q[0] <= q[1] <= q[2]
