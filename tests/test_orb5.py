"""First-candle opening range. The range is only 09:30-09:35."""

from datetime import date

import numpy as np
import pandas as pd

from webull_bot.chart_reads.orb5 import (
    CASH_ACCOUNT,
    DTE_PRIMARY,
    ENTRY_PRIMARY,
    LADDER_STOP,
    PRIMARY_STOP,
    PRIMARY_TARGET,
    STOP_PRIMARY,
    find_orb,
    frozen_rules,
    opening_bounds,
    range_stop,
    simulate_ladder,
    simulate_shares,
    theoretical_breakeven,
)
from webull_bot.chart_reads.pullback import PremiumPath


def _frame(rows, freq="5min"):
    index = pd.DatetimeIndex([pd.Timestamp(stamp, tz="America/New_York") for stamp, *_rest in rows])
    if freq:
        pass
    return pd.DataFrame(
        {
            "open": [row[1] for row in rows],
            "high": [row[2] for row in rows],
            "low": [row[3] for row in rows],
            "close": [row[4] for row in rows],
            "volume": [1_000.0] * len(rows),
        },
        index=index,
    )


def _day(day, later):
    """09:30 range 10/9, then the caller's later bars, then a quiet last bar."""
    rows = [(f"{day} 09:30", 9.4, 10.0, 9.0, 9.5)]
    rows.extend(later)
    return rows


def test_rules_are_the_first_candle_and_the_named_exits():
    rules = frozen_rules()
    assert rules["entry"] == ENTRY_PRIMARY
    assert rules["stop"] == STOP_PRIMARY
    assert rules["dte"] == DTE_PRIMARY == 0
    assert rules["premium_target"] == PRIMARY_TARGET == 0.15
    assert rules["premium_stop"] == PRIMARY_STOP == -0.30
    assert rules["breakeven_before_costs"] == 0.30 / (0.15 + 0.30)
    assert theoretical_breakeven(0.15, -0.30) == 0.30 / (0.15 + 0.30)
    assert LADDER_STOP == -0.30
    assert CASH_ACCOUNT == 1_000.0


def test_five_minute_range_ignores_the_rest_of_the_open():
    rows = _day(
        "2026-10-06",
        [
            ("2026-10-06 09:35", 9.6, 20.0, 9.4, 9.8),
            ("2026-10-06 09:40", 9.8, 10.4, 9.7, 10.2),
            ("2026-10-06 09:45", 10.2, 10.3, 10.0, 10.1),
        ],
    )
    frame = _frame(rows)
    high, low, anchor = opening_bounds(frame.iloc[:1], "5m")
    assert (high, low) == (10.0, 9.0)
    assert anchor.hour == 9 and anchor.minute == 30
    found = find_orb(frame, "SPY", "5m", "close")
    assert len(found) == 1
    assert found[0].direction == "long"
    assert found[0].signal_time == pd.Timestamp("2026-10-06 09:40", tz="America/New_York")
    assert found[0].fill_time == pd.Timestamp("2026-10-06 09:45", tz="America/New_York")
    assert found[0].reference == 10.0
    assert found[0].reversal == 9.0
    assert found[0].stop == 9.0
    assert range_stop(found[0], "mid") == 9.5


def test_a_close_that_only_touches_the_high_is_not_a_break():
    rows = _day(
        "2026-10-06",
        [
            ("2026-10-06 09:35", 9.6, 10.0, 9.4, 10.0),
            ("2026-10-06 09:40", 10.0, 10.1, 9.8, 9.9),
        ],
    )
    assert find_orb(_frame(rows), "SPY", "5m", "close") == []


def test_one_minute_range_is_the_five_bars_before_09_35():
    rows = []
    for minute, high, low in (
        (30, 10.0, 9.6),
        (31, 10.2, 9.4),
        (32, 10.5, 9.7),
        (33, 10.1, 9.3),
        (34, 10.0, 9.5),
        (35, 11.0, 10.4),
    ):
        rows.append((f"2026-10-06 09:{minute:02d}", 9.8, high, low, 10.6 if minute == 35 else 9.8))
    rows.append(("2026-10-06 09:36", 10.6, 10.7, 10.5, 10.6))
    frame = _frame(rows, freq=None)
    high, low, anchor = opening_bounds(frame, "1m")
    assert (high, low) == (10.5, 9.3)
    assert anchor.minute == 34
    found = find_orb(frame, "SPY", "1m", "close")
    assert len(found) == 1
    assert found[0].signal_time.minute == 35
    assert found[0].reference == 10.5


def test_missing_open_is_skipped():
    rows = [
        ("2026-10-06 09:35", 9.6, 11.0, 9.4, 10.5),
        ("2026-10-06 09:40", 10.5, 10.6, 10.4, 10.5),
    ]
    assert find_orb(_frame(rows), "SPY", "5m", "close") == []


def test_confirm_waits_for_a_candle_in_the_break_direction():
    rows = _day(
        "2026-10-06",
        [
            ("2026-10-06 09:35", 10.4, 10.8, 9.9, 10.1),
            ("2026-10-06 09:40", 10.0, 11.0, 9.95, 10.8),
            ("2026-10-06 09:45", 10.8, 10.9, 10.6, 10.7),
        ],
    )
    frame = _frame(rows)
    plain = find_orb(frame, "SPY", "5m", "close")
    confirm = find_orb(frame, "SPY", "5m", "confirm")
    assert plain[0].signal_time.minute == 35
    assert confirm[0].signal_time.minute == 40


def test_retest_holds_the_broken_level_and_rejects_a_break_of_the_other_side():
    rows = _day(
        "2026-10-06",
        [
            ("2026-10-06 09:35", 10.0, 11.0, 10.1, 10.8),
            ("2026-10-06 09:40", 10.7, 10.8, 8.5, 8.8),
            ("2026-10-06 09:45", 8.8, 9.2, 8.6, 9.0),
        ],
    )
    assert find_orb(_frame(rows), "SPY", "5m", "retest") == []
    held = _day(
        "2026-10-06",
        [
            ("2026-10-06 09:35", 10.0, 11.0, 10.1, 10.8),
            ("2026-10-06 09:40", 10.7, 10.9, 9.95, 10.2),
            ("2026-10-06 09:45", 10.1, 10.6, 10.0, 10.5),
            ("2026-10-06 09:50", 10.5, 10.6, 10.4, 10.5),
        ],
    )
    found = find_orb(_frame(held), "SPY", "5m", "retest")
    assert len(found) == 1
    assert found[0].signal_time.minute == 45
    assert found[0].direction == "long"


def test_short_is_the_mirror():
    rows = _day(
        "2026-10-06",
        [
            ("2026-10-06 09:35", 9.4, 9.6, 8.4, 8.6),
            ("2026-10-06 09:40", 8.6, 8.7, 8.5, 8.55),
        ],
    )
    found = find_orb(_frame(rows), "SPY", "5m", "close")
    assert found[0].direction == "short"
    assert found[0].stop == 10.0


def test_share_target_fills_at_1r_and_a_gap_stop_fills_at_the_open():
    target_rows = _day(
        "2026-10-06",
        [
            ("2026-10-06 09:35", 10.0, 10.5, 9.8, 10.4),
            ("2026-10-06 09:40", 11.0, 14.0, 10.8, 13.5),
        ],
    )
    book = simulate_shares(find_orb(_frame(target_rows), "SPY", "5m"), {"SPY": _frame(target_rows)}, target_r=1.0, starting_equity=1_000.0, pdt=False)
    assert book["trades"][0]["reason"] == "target"
    assert book["trades"][0]["exit"] == 13.0
    gap_rows = _day(
        "2026-10-06",
        [
            ("2026-10-06 09:35", 10.0, 10.5, 9.8, 10.4),
            ("2026-10-06 09:40", 8.5, 8.6, 8.2, 8.4),
        ],
    )
    gap = simulate_shares(find_orb(_frame(gap_rows), "SPY", "5m"), {"SPY": _frame(gap_rows)}, target_r=1.0, starting_equity=1_000.0, pdt=False)
    assert gap["trades"][0]["reason"] == "stop"
    assert gap["trades"][0]["exit"] == 8.5


def test_same_bar_stop_beats_the_target_and_the_session_close_is_the_time_stop():
    rows = _day(
        "2026-10-06",
        [
            ("2026-10-06 09:35", 10.0, 10.5, 9.8, 10.4),
            ("2026-10-06 09:40", 11.0, 14.0, 8.0, 12.0),
        ],
    )
    frame = _frame(rows)
    book = simulate_shares(find_orb(frame, "SPY", "5m"), {"SPY": frame}, target_r=1.0, starting_equity=1_000.0, pdt=False)
    assert book["trades"][0]["reason"] == "stop"
    assert book["trades"][0]["exit"] == 9.0
    quiet = _day(
        "2026-10-06",
        [
            ("2026-10-06 09:35", 10.0, 10.5, 9.8, 10.4),
            ("2026-10-06 09:40", 10.5, 10.7, 10.2, 10.4),
            ("2026-10-06 09:45", 10.4, 10.5, 10.3, 10.35),
        ],
    )
    frame = _frame(quiet)
    book = simulate_shares(find_orb(frame, "SPY", "5m"), {"SPY": frame}, target_r=None, starting_equity=1_000.0, pdt=False)
    assert book["trades"][0]["reason"] == "eod"
    assert book["trades"][0]["exit"] == 10.35


def test_pdt_blocks_the_fourth_day_trade_on_a_1000_account():
    rows = []
    for day in ("2026-10-01", "2026-10-02", "2026-10-05", "2026-10-06"):
        rows.extend(
            [
                (f"{day} 09:30", 9.4, 10.0, 9.0, 9.5),
                (f"{day} 09:35", 10.0, 10.4, 9.8, 10.3),
                (f"{day} 09:40", 10.3, 10.5, 10.1, 10.2),
            ]
        )
    frame = _frame(rows)
    book = simulate_shares(find_orb(frame, "SPY", "5m"), {"SPY": frame}, target_r=1.0, starting_equity=1_000.0, pdt=True)
    assert book["metrics"]["trades"] == 3
    assert book["pdt_blocked"] == 1


def _path(**overrides) -> PremiumPath:
    base = dict(
        symbol="SPY",
        direction="long",
        fill=pd.Timestamp("2026-10-06 09:40", tz="America/New_York"),
        fill_date=date(2026, 10, 6),
        signal_date=date(2026, 10, 6),
        ok=True,
        ask=1.0,
        delta=0.50,
        strike=780.0,
        right="call",
        expiry=date(2026, 10, 6),
        open_bid=np.array([1.05, 1.05, 1.05, 1.05]),
        adverse_bid=np.array([1.02, 1.02, 1.02, 1.02]),
        favorable_bid=np.array([1.15, 1.20, 1.30, 2.00]),
        close_bid=np.array([1.05, 1.10, 1.20, 1.80]),
        expired=np.array([False, False, False, True]),
        stamps=[
            pd.Timestamp("2026-10-06 09:40", tz="America/New_York"),
            pd.Timestamp("2026-10-06 09:45", tz="America/New_York"),
            pd.Timestamp("2026-10-06 09:50", tz="America/New_York"),
            pd.Timestamp("2026-10-06 09:55", tz="America/New_York"),
        ],
    )
    base.update(overrides)
    return PremiumPath(**base)


def test_ladder_sells_the_tiers_at_the_limits_and_a_gap_at_the_open():
    book = simulate_ladder([_path()], starting_equity=10_000.0, mode="sized", pdt=False)
    assert book["trades"][0]["reason"] == "target"
    assert book["trades"][0]["pnl"] > 0
    stopped = _path(
        open_bid=np.array([1.0, 0.40]),
        adverse_bid=np.array([0.90, 0.40]),
        favorable_bid=np.array([1.05, 0.50]),
        close_bid=np.array([1.00, 0.45]),
        expired=np.array([False, True]),
        stamps=[
            pd.Timestamp("2026-10-06 09:40", tz="America/New_York"),
            pd.Timestamp("2026-10-06 09:45", tz="America/New_York"),
        ],
    )
    book = simulate_ladder([stopped], starting_equity=10_000.0, mode="sized", pdt=False)
    assert book["trades"][0]["reason"] == "initial_stop"
    assert book["trades"][0]["pnl"] < 0


def test_module_does_not_touch_the_forward_test():
    source = open("src/webull_bot/chart_reads/orb5.py", encoding="utf-8").read()
    research = open("src/webull_bot/chart_reads/research_orb5.py", encoding="utf-8").read()
    for name in ("forward_options", "forward_chop", "option_quote", "place_option_order", "mark_options"):
        assert name not in source
        assert name not in research
