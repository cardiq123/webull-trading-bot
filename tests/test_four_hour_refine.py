"""Mechanics for the pre-registered 4hr refinements. These tests do not score a window."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import numpy as np
import pandas as pd

from webull_bot.chart_reads.four_hour import Book, Event, catalog, find_signals, frozen_rules, n_trials, resolve
from webull_bot.chart_reads.four_hour_refine import (
    PRIOR_TRIALS,
    REFINEMENT_IDS,
    SLOPE_MIN,
    apply_filters,
    dead_print_dates,
    dead_trade_days,
    frozen_refine_rules,
    selected_rule,
    train_winners,
    variant_spec,
)

NY = "America/New_York"


def _scan_book():
    n = 6
    index = pd.date_range("2024-06-03 10:00", periods=n, freq="5min", tz=NY)
    return SimpleNamespace(
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


def _event_book(fill_minute: int = 10 * 60):
    index = pd.date_range("2024-06-03 10:00", periods=4, freq="5min", tz=NY)
    minutes = (index.hour * 60 + index.minute).to_numpy(dtype=int)
    minutes[1] = fill_minute
    book = SimpleNamespace(
        minute=minutes,
        dates=np.asarray(index.date, dtype=object),
        ema9=np.array([100.0, 100.0, 100.0, 100.0]),
        ema20=np.array([100.0, 100.02, 100.0, 100.0]),
        atr14=np.array([1.0, 1.0, 1.0, 1.0]),
        rsi14=np.array([50.0, 50.0, 50.0, 50.0]),
        volume=np.array([1.0, 1.0, 5.0, 1.0]),
        h4_slope=np.array([0.0, 0.002, 0.0, 0.0]),
    )
    event = Event("QQQ", "long", "ema", "vwap", 1, 1, 99.0)
    return book, event


def test_original_family_stays_seventy_two():
    rules = frozen_rules()
    assert n_trials() == 72
    assert len(catalog()) == 72
    assert rules["n_trials"] == 72
    assert "be15" not in rules["exits"]


def test_refine_rules_are_frozen_before_any_score():
    rules = frozen_refine_rules()
    assert rules["registered_before_score"] is True
    assert rules["base_cell"] == "QQQ_ema_vwap_r1_1dte"
    assert [item["id"] for item in rules["refinements"]] == list(REFINEMENT_IDS)
    assert len(REFINEMENT_IDS) == 8
    assert rules["slope_min"] == 0.0015
    assert SLOPE_MIN == 0.0015
    assert rules["family"]["prior_trials"] == PRIOR_TRIALS == 72
    assert "ending_equity" not in rules
    assert "holdout" not in rules["selection"]["winner"]
    assert "VIX is not a substitute" in rules["refinements"][5]["change"]


def test_vwap_hold_is_off_unless_asked():
    book = _scan_book()
    book.m15_vwap = np.array([np.nan, np.nan, 98.0, np.nan, np.nan, np.nan])
    assert len(find_signals(book, "ema", "ema20")) == 1
    assert find_signals(book, "ema", "ema20", hold_vwap=True) == []


def test_a_close_on_vwap_still_holds():
    book = _scan_book()
    book.m15_close = np.array([np.nan, np.nan, 98.0, np.nan, np.nan, np.nan])
    book.m15_vwap = np.array([np.nan, np.nan, 98.0, np.nan, np.nan, np.nan])
    assert len(find_signals(book, "ema", "ema20", hold_vwap=True)) == 1


def test_chop_needs_both_the_emas_and_the_rsi():
    book, event = _event_book()
    book.ema9 = np.array([100.0, 100.0, 100.0, 100.0])
    book.ema20 = np.array([100.0, 100.04, 100.0, 100.0])
    book.atr14 = np.array([1.0, 1.0, 1.0, 1.0])
    book.rsi14 = np.array([50.0, 50.0, 50.0, 50.0])
    assert apply_filters(book, [event], ["chop"]) == []
    book.rsi14 = np.array([50.0, 60.0, 50.0, 50.0])
    assert len(apply_filters(book, [event], ["chop"])) == 1
    book.rsi14 = np.array([50.0, 50.0, 50.0, 50.0])
    book.ema20 = np.array([100.0, 100.2, 100.0, 100.0])
    assert len(apply_filters(book, [event], ["chop"])) == 1


def test_time_filter_uses_the_fill_and_keeps_the_boundaries():
    book, event = _event_book(9 * 60 + 40)
    assert apply_filters(book, [event], ["time"]) == []
    book, event = _event_book(9 * 60 + 45)
    assert len(apply_filters(book, [event], ["time"])) == 1
    book, event = _event_book(11 * 60 + 30)
    assert apply_filters(book, [event], ["time"]) == []
    book, event = _event_book(13 * 60 + 25)
    assert apply_filters(book, [event], ["time"]) == []
    book, event = _event_book(13 * 60 + 30)
    assert len(apply_filters(book, [event], ["time"])) == 1


def test_volume_uses_the_prior_twenty_bars():
    book, event = _event_book()
    book.volume = np.concatenate([np.ones(20), np.array([2.0, 1.0, 1.0])])
    event = Event("QQQ", "long", "ema", "vwap", 20, 21, 99.0)
    book.minute = np.zeros(23, dtype=int)
    book.dates = np.asarray([date(2024, 6, 3)] * 23, dtype=object)
    book.ema9 = np.ones(23)
    book.ema20 = np.ones(23) * 2
    book.atr14 = np.ones(23)
    book.rsi14 = np.full(23, 70.0)
    book.h4_slope = np.full(23, 0.01)
    assert len(apply_filters(book, [event], ["volume"])) == 1
    book.volume[20] = 0.5
    assert apply_filters(book, [event], ["volume"]) == []


def test_slope_threshold_is_fifteen_basis_points():
    book, event = _event_book()
    book.h4_slope = np.array([0.0, 0.0015, 0.0, 0.0])
    assert len(apply_filters(book, [event], ["slope"])) == 1
    book.h4_slope = np.array([0.0, 0.0014, 0.0, 0.0])
    assert apply_filters(book, [event], ["slope"]) == []
    short = Event("QQQ", "short", "ema", "vwap", 1, 1, 101.0)
    book.h4_slope = np.array([0.0, -0.0015, 0.0, 0.0])
    assert len(apply_filters(book, [short], ["slope"])) == 1
    book.h4_slope = np.array([0.0, np.nan, 0.0, 0.0])
    assert apply_filters(book, [event], ["slope"]) == []


def test_dead_tape_waits_for_two_hundred_fifty_two_priors():
    index = pd.bdate_range("2023-04-24", periods=260)
    values = np.full(260, 20.0)
    values[-1] = 1.0
    series = pd.Series(values, index=index)
    dead = dead_print_dates(series)
    assert index[251].date() not in dead
    assert index[-1].date() in dead
    trade_day = (index[-1] + pd.Timedelta(days=1)).date()
    skipped = dead_trade_days(series, [trade_day, index[10].date()])
    assert trade_day in skipped
    assert index[10].date() not in skipped


def test_selection_uses_the_walk_forward_mean_and_ignores_holdout():
    rows = [
        {"id": "chop", "mean_yearly_sharpe": 1.2, "wf_trades": 90, "holdout_sharpe": 0.1},
        {"id": "time", "mean_yearly_sharpe": 0.9, "wf_trades": 500, "holdout_sharpe": 9.0},
        {"id": "volume", "mean_yearly_sharpe": 2.0, "wf_trades": 79, "holdout_sharpe": 9.0},
    ]
    assert train_winners(1.0, rows) == ["chop"]
    assert selected_rule(["chop"])["extra_trial"] is False
    assert selected_rule(["chop", "time"]) == {
        "id": "combo",
        "kind": "combination",
        "parts": ["chop", "time"],
        "extra_trial": True,
    }
    assert selected_rule([])["id"] == "base"
    spec = variant_spec(["vwap_hold", "be15", "cap2", "chop"])
    assert spec == {
        "hold_vwap": True,
        "event_filters": ["chop"],
        "exit": "be15",
        "cap": 2,
    }


def _be_book(rows: list[tuple[float, float, float, float]], start: str = "2024-06-03 10:00") -> Book:
    index = pd.date_range(start, periods=len(rows), freq="5min", tz=NY)
    frame = pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=index)
    frame["volume"] = 1.0
    return Book(frame, "QQQ")


def test_breakeven_stop_does_not_apply_on_the_arming_bar():
    # R = 2. Trigger 101. Target 103. This bar trades the stop and +0.5R, so the stop wins.
    both = _be_book([(100.0, 101.5, 97.5, 100.0), (100.0, 100.2, 99.8, 100.0)])
    event = Event("QQQ", "long", "ema", "vwap", 0, 0, 98.0)
    stopped = resolve(both, [event], "be15")
    assert stopped[0]["reason"] == "stop"
    assert stopped[0]["exit"] == 98.0

    # +0.5R and 1.5R on the fill bar, original stop untouched: take 1.5R.
    target = _be_book([(100.0, 104.0, 99.5, 103.0), (100.0, 100.2, 99.8, 100.0)])
    hit = resolve(target, [event], "be15")
    assert hit[0]["reason"] == "target"
    assert hit[0]["exit"] == 103.0

    # Arm on bar 0. Bar 1 trades back through the fill but not a fresh low at the old stop price.
    armed = _be_book(
        [
            (100.0, 101.5, 99.5, 101.2),
            (101.2, 101.3, 99.5, 100.0),
        ]
    )
    faded = resolve(armed, [event], "be15")
    assert faded[0]["reason"] == "stop"
    assert faded[0]["exit"] == 100.0

    # Armed, then the next bar reaches 1.5R without touching the fill.
    runner = _be_book(
        [
            (100.0, 101.5, 99.5, 101.2),
            (101.2, 103.4, 100.4, 103.0),
        ]
    )
    ran = resolve(runner, [event], "be15")
    assert ran[0]["reason"] == "target"
    assert ran[0]["exit"] == 103.0


def test_one_r_path_is_unchanged_by_the_breakeven_walker():
    book = _be_book([(100.0, 101.5, 99.5, 101.2), (101.2, 103.4, 100.4, 103.0)])
    event = Event("QQQ", "long", "ema", "vwap", 0, 0, 98.0)
    rows = resolve(book, [event], "r1")
    assert rows[0]["reason"] == "target"
    assert rows[0]["exit"] == 102.0
