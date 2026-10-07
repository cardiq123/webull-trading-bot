"""The pullback rules stay fixed. These tests do not score a book."""

from datetime import date

import numpy as np
import pandas as pd

from webull_bot.chart_reads.pullback import (
    ADX_MIN,
    DTE_DEFAULT,
    DTE_SENSITIVITIES,
    PRIMARY_STOP,
    PRIMARY_TARGET,
    TIME_BARS,
    PremiumPath,
    after_cost_breakeven,
    atm_strike,
    choose_contracts,
    find_pullbacks,
    qualifies_long,
    qualifies_short,
    replay_exit,
    theoretical_breakeven,
)


def _long(**overrides):
    base = dict(
        stack=True,
        rising=True,
        above=True,
        adx=30.0,
        higher_structure=False,
        low=100.0,
        close=101.0,
        open_=100.4,
        prev_close=100.2,
        width=2.0,
        swing=99.0,
        vwap=100.2,
        ema_fast=100.1,
        ema_mid=99.5,
    )
    base.update(overrides)
    return qualifies_long(**base)


def test_primary_exit_breakeven_is_two_thirds():
    assert PRIMARY_TARGET == 0.15
    assert PRIMARY_STOP == -0.30
    assert DTE_DEFAULT == 14
    assert DTE_SENSITIVITIES == (7, 30)
    assert TIME_BARS == {"15m": 16, "60m": 8, "1d": 5}
    assert ADX_MIN == 25.0
    assert theoretical_breakeven(0.15, -0.30) == 0.30 / (0.15 + 0.30)


def test_after_cost_breakeven_uses_the_realized_payoffs():
    assert after_cost_breakeven(10.0, -30.0) == 0.75
    assert after_cost_breakeven(0.0, 0.0) is None


def test_cash_book_buys_one_or_two_contracts():
    assert choose_contracts(2.0, 1_000.0, "cash") == 2
    assert choose_contracts(6.0, 1_000.0, "cash") == 1
    assert choose_contracts(12.0, 1_000.0, "cash") == 0
    assert choose_contracts(2.0, 50_000.0, "sized") == 1


def test_nearest_listed_strike():
    assert atm_strike(200.4) == 200.0
    assert atm_strike(200.6) == 201.0


def test_long_holds_the_touch_and_the_swing():
    assert _long()
    assert not _long(close=100.2, open_=100.0, prev_close=99.5, vwap=100.8, ema_fast=100.8, ema_mid=100.8)
    assert not _long(low=98.0)
    assert not _long(close=100.4, open_=100.6)
    assert not _long(stack=False, higher_structure=True)
    assert _long(adx=10.0, higher_structure=True)


def test_short_is_the_mirror():
    assert qualifies_short(
        stack=True,
        falling=True,
        below=True,
        adx=30.0,
        lower_structure=False,
        high=100.0,
        close=99.0,
        open_=99.6,
        prev_close=99.8,
        width=2.0,
        swing=101.0,
        vwap=99.8,
        ema_fast=99.9,
        ema_mid=100.4,
    )
    assert not qualifies_short(
        stack=True,
        falling=True,
        below=True,
        adx=30.0,
        lower_structure=False,
        high=102.0,
        close=99.0,
        open_=99.6,
        prev_close=99.8,
        width=2.0,
        swing=101.0,
        vwap=99.8,
        ema_fast=99.9,
        ema_mid=100.4,
    )


def _path(**overrides) -> PremiumPath:
    stamp = pd.Timestamp("2024-06-03 10:00", tz="America/New_York")
    base = dict(
        symbol="AAPL",
        direction="long",
        fill=stamp,
        fill_date=date(2024, 6, 3),
        signal_date=date(2024, 6, 3),
        ok=True,
        ask=1.0,
        delta=0.51,
        strike=190.0,
        right="call",
        expiry=date(2024, 6, 17),
        open_bid=np.array([1.00, 1.00, 1.00]),
        adverse_bid=np.array([0.95, 0.90, 0.90]),
        favorable_bid=np.array([1.05, 1.10, 1.10]),
        close_bid=np.array([1.00, 1.02, 1.04]),
        expired=np.array([False, False, True]),
        stamps=[stamp, stamp + pd.Timedelta(hours=1), stamp + pd.Timedelta(hours=2)],
    )
    base.update(overrides)
    return PremiumPath(**base)


def test_target_fills_at_the_limit_and_a_gap_stop_uses_the_open():
    path = _path(favorable_bid=np.array([1.40, 1.10, 1.10]))
    price, reason, index = replay_exit(path, 0.15, -0.30, None)
    assert (price, reason, index) == (1.15, "target", 0)
    gap = _path(open_bid=np.array([1.00, 0.40, 1.00]), adverse_bid=np.array([0.95, 0.30, 0.90]))
    price, reason, index = replay_exit(gap, 0.15, -0.30, None)
    assert (price, reason, index) == (0.40, "stop", 1)


def test_same_bar_stop_beats_the_target():
    path = _path(
        open_bid=np.array([0.90, 1.00, 1.00]),
        adverse_bid=np.array([0.50, 0.90, 0.90]),
        favorable_bid=np.array([1.40, 1.10, 1.10]),
    )
    price, reason, index = replay_exit(path, 0.15, -0.30, None)
    assert (price, reason, index) == (0.70, "stop", 0)


def test_time_stop_exits_at_the_close_of_bar_n():
    price, reason, index = replay_exit(_path(), None, -0.30, 2)
    assert (price, reason, index) == (1.02, "time", 1)


def test_short_history_has_no_signal():
    index = pd.date_range("2024-01-02 09:30", periods=30, freq="15min", tz="America/New_York")
    frame = pd.DataFrame(
        {
            "open": np.linspace(100, 103, len(index)),
            "high": np.linspace(100.2, 103.2, len(index)),
            "low": np.linspace(99.8, 102.8, len(index)),
            "close": np.linspace(100.1, 103.1, len(index)),
            "volume": np.full(len(index), 1_000.0),
        },
        index=index,
    )
    assert find_pullbacks(frame, "AAPL", "15m") == []


def test_pullback_module_does_not_touch_the_forward_test():
    source = open("src/webull_bot/chart_reads/pullback.py", encoding="utf-8").read()
    research = open("src/webull_bot/chart_reads/research_pullback.py", encoding="utf-8").read()
    for name in ("forward_options", "forward_chop", "option_quote", "place_option_order", "mark_options"):
        assert name not in source
        assert name not in research
