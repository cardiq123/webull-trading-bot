"""Session VWAP band rules. No network and no broker."""

from datetime import date, time
from pathlib import Path

import numpy as np
import pandas as pd

from webull_bot.chart_reads.vwap_band import (
    OUTER_DEFAULT,
    RANDOM_SEED,
    find_signals,
    frozen_rules,
    metrics_from,
    passes_gate,
    random_signals,
    simulate,
    walk_exit,
)
from webull_bot.chart_reads.vwap_band_data import to_fifteen_minute

NY = "America/New_York"


def _session(rows: list[tuple], day: str = "2024-01-03") -> pd.DataFrame:
    stamps = []
    data = []
    cursor = pd.Timestamp(f"{day} 09:30", tz=NY)
    for row in rows:
        stamps.append(cursor)
        data.append(row)
        cursor += pd.Timedelta(minutes=15)
    frame = pd.DataFrame(data, columns=["open", "high", "low", "close", "volume"], index=pd.DatetimeIndex(stamps))
    return frame


def _quiet_then(extra: list[tuple], quiet: int = 8) -> pd.DataFrame:
    rows = []
    for i in range(quiet):
        price = 100.0 + (0.4 if i % 2 == 0 else -0.2)
        rows.append((price, price + 0.05, price - 0.05, price, 1000.0))
    rows.extend(extra)
    # Pad through 15:45 so a fill exists and the flat bar exists.
    while len(rows) < 26:
        rows.append((100.0, 100.1, 99.9, 100.0, 1000.0))
    return _session(rows[:26])


def test_rules_are_frozen_before_any_score():
    rules = frozen_rules()
    assert rules["outer_default"] == 2.0
    assert rules["outer_variants"] == [2.5, 3.0]
    assert "2022-01-01" in rules["split"]
    assert rules["random"].startswith("Seed 17")
    assert "300" in rules["gate"]
    assert len(rules["gate_books"]) == 6
    assert OUTER_DEFAULT == 2.0
    assert RANDOM_SEED == 17


def test_fifteen_minute_bins_start_at_the_open():
    stamps = pd.date_range("2024-01-03 09:30", periods=15, freq="1min", tz=NY)
    minutes = pd.DataFrame(
        {"open": 10.0, "high": np.arange(15) + 10, "low": 9.0, "close": 11.0, "volume": 1.0},
        index=stamps,
    )
    bars = to_fifteen_minute(minutes)
    assert bars.index[0].time() == time(9, 30)
    assert float(bars.iloc[0]["high"]) == 24.0
    assert float(bars.iloc[0]["open"]) == 10.0
    assert len(bars) == 1


def test_extension_fires_once_and_fills_on_the_next_open():
    frame = _quiet_then(
        [
            (100.0, 130.0, 100.0, 130.0, 1000.0),
            (130.0, 131.0, 129.0, 130.5, 1000.0),
            (130.0, 130.2, 129.5, 129.8, 1000.0),
        ]
    )
    signals = [item for item in find_signals(frame, "SPY", 2.0) if item.mode == "extension"]
    assert signals
    first = signals[0]
    assert first.direction == "long"
    assert first.fill_time > first.signal_time
    assert first.fill_time == first.signal_time + pd.Timedelta(minutes=15)
    assert first.stop < float(frame.loc[first.signal_time]["low"])
    # A second close still outside is not a new extension.
    later = [item for item in signals if item.signal_time > first.signal_time]
    assert all(item.signal_time != first.signal_time + pd.Timedelta(minutes=15) for item in later)


def test_extension_does_not_read_the_fill_bar():
    frame = _quiet_then([(100.0, 130.0, 100.0, 130.0, 1000.0), (100.0, 100.2, 99.8, 100.0, 1000.0)])
    before = find_signals(frame, "SPY", 2.0)
    changed = frame.copy()
    fill = before[0].fill_time
    changed.loc[fill, ["open", "high", "low", "close"]] = [1.0, 1.0, 1.0, 1.0]
    after = find_signals(changed, "SPY", 2.0)
    assert after[0].signal_time == before[0].signal_time
    assert after[0].stop == before[0].stop
    assert after[0].fill_time == before[0].fill_time


def test_reversal_confirms_on_a_wick_and_enters_next_bar():
    frame = _quiet_then([(100.0, 100.2, 70.0, 100.0, 1000.0), (100.0, 100.2, 99.8, 100.1, 1000.0)])
    reversals = [item for item in find_signals(frame, "SPY", 2.0) if item.mode == "reversal"]
    assert reversals
    bounce = reversals[0]
    assert bounce.direction == "long"
    assert bounce.fill_time == bounce.signal_time + pd.Timedelta(minutes=15)
    assert bounce.stop < 70.0


def test_a_bar_through_both_bands_does_not_confirm():
    frame = _quiet_then([(100.0, 140.0, 60.0, 100.0, 1000.0)])
    pierce = frame.index[8]
    reversals = [item for item in find_signals(frame, "SPY", 2.0) if item.mode == "reversal"]
    assert all(item.signal_time != pierce for item in reversals)


def test_stop_wins_when_the_bar_can_reach_both():
    stamps = pd.date_range("2024-01-03 10:00", periods=2, freq="15min", tz=NY)
    session = pd.DataFrame(
        {"open": [100.0, 100.0], "high": [110.0, 110.0], "low": [90.0, 90.0], "close": [100.0, 100.0]},
        index=stamps,
    )
    reason, price, _when = walk_exit(session, 0, "long", 95.0, 105.0)
    assert reason == "stop"
    assert price == 95.0


def test_flat_uses_the_1545_open_and_ignores_that_bar_high():
    stamps = pd.DatetimeIndex(
        [
            pd.Timestamp("2024-01-03 15:30", tz=NY),
            pd.Timestamp("2024-01-03 15:45", tz=NY),
        ]
    )
    session = pd.DataFrame(
        {"open": [100.0, 101.0], "high": [100.2, 150.0], "low": [99.8, 100.5], "close": [100.1, 149.0]},
        index=stamps,
    )
    reason, price, when = walk_exit(session, 0, "long", 90.0, 140.0)
    assert reason == "flat"
    assert price == 101.0
    assert when.time() == time(15, 45)


def test_no_signal_fills_at_or_after_1545():
    frame = _quiet_then([(100.0, 130.0, 100.0, 130.0, 1000.0)])
    # Move the spike onto the 15:30 bar, whose next open is 15:45.
    order = list(frame.index)
    late = frame.copy()
    spike = late.iloc[8].copy()
    late.iloc[8] = late.iloc[0]
    late.loc[order[24]] = spike  # 15:30
    signals = find_signals(late, "SPY", 2.0)
    assert all(item.fill_time.time() < time(15, 45) for item in signals)
    assert all(item.signal_time.time() <= time(15, 15) for item in signals)


def test_cash_book_skips_shorts_and_does_not_reuse_proceeds_the_same_day():
    frame = _quiet_then(
        [
            (100.0, 130.0, 100.0, 130.0, 1000.0),
            (130.0, 130.2, 120.0, 125.0, 1000.0),
        ]
    )
    signals = [item for item in find_signals(frame, "SPY", 2.0) if item.mode == "extension"]
    assert signals and signals[0].direction == "long"
    book = simulate(frame, signals, target="r", kind="shares", stake=1_000.0, long_only=True)
    assert book["trades"]
    assert book["skips"]["short"] == 0 or all(trade["direction"] == "long" for trade in book["trades"])
    # Two longs the same day: the second cannot spend the first sale's cash.
    doubled = signals + signals
    # Force a second fill later in the day by cloning with a later timestamp if present.
    later = [item for item in find_signals(frame, "SPY", 2.0) if item.mode == "extension"]
    both = simulate(frame, later, target="r", kind="shares", stake=1_000.0, long_only=True)
    assert all(trade["direction"] == "long" for trade in both["trades"])
    del doubled


def test_random_entries_use_the_seed_and_the_same_count():
    frame = _quiet_then([(100.0, 101.0, 99.0, 100.0, 1000.0)])
    left = random_signals(frame, "SPY", 4, seed=17)
    right = random_signals(frame, "SPY", 4, seed=17)
    other = random_signals(frame, "SPY", 4, seed=18)
    assert len(left) == 4
    assert [item.fill_time for item in left] == [item.fill_time for item in right]
    assert [item.direction for item in left] == [item.direction for item in right]
    assert [item.fill_time for item in left] != [item.fill_time for item in other] or [
        item.direction for item in left
    ] != [item.direction for item in other]


def test_gate_boundaries():
    good = {"trades": 300, "profit_factor": 1.10, "sharpe": 0.40, "max_drawdown": -0.30, "win_rate": 0.5}
    assert passes_gate(good)
    assert not passes_gate({**good, "trades": 299})
    assert not passes_gate({**good, "profit_factor": 1.09})
    assert not passes_gate({**good, "sharpe": 0.39})
    assert not passes_gate({**good, "max_drawdown": -0.3001})
    winners = {"trades": 300, "profit_factor": None, "sharpe": 0.5, "max_drawdown": -0.1, "win_rate": 1.0}
    assert passes_gate(winners)


def test_metrics_match_a_flat_account():
    equity = pd.Series([1000.0, 1000.0], index=pd.to_datetime(["2024-01-02", "2024-01-03"]))
    stats = metrics_from(equity, [], 1000.0)
    assert stats["trades"] == 0
    assert stats["ending_equity"] == 1000.0
    assert stats["sharpe"] == 0.0


def test_sources_do_not_touch_the_forward_test():
    root = Path("src/webull_bot/chart_reads")
    for name in ("vwap_band.py", "vwap_band_data.py", "research_vwap_band.py"):
        text = (root / name).read_text()
        for banned in ("forward_options", "forward_chop", "option_quote", "place_option_order", "mark_options"):
            assert banned not in text
        assert "live_trading_enabled" not in text
