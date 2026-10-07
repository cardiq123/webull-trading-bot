"""Caps, quality filters, and confirmation. No network and no broker."""

from datetime import date, time
from pathlib import Path

import numpy as np
import pandas as pd

from webull_bot.chart_reads.vwap_band import find_signals, simulate
from webull_bot.chart_reads.vwap_quality import (
    pending_extensions,
    EARLY_CUTOFF,
    FAMILY,
    FDR_Q,
    Feature,
    Priced,
    Signal,
    _hourly_agrees,
    agrees_ema_vwap,
    apply_early_15m,
    build_features,
    confirm_15m,
    confirm_5m,
    confirmation_marks,
    first_n,
    freeze_cuts,
    frozen_rules,
    in_lunch,
    is_early,
    price_signals,
    qqq_covers,
    run_account,
    scored_family,
    select_signals,
    to_rth_bars,
)

NY = "America/New_York"
DAY = date(2024, 1, 3)


def _session(rows: list[tuple], day: str = "2024-01-03") -> pd.DataFrame:
    stamps = []
    data = []
    cursor = pd.Timestamp(f"{day} 09:30", tz=NY)
    for row in rows:
        stamps.append(cursor)
        data.append(row)
        cursor += pd.Timedelta(minutes=15)
    return pd.DataFrame(data, columns=["open", "high", "low", "close", "volume"], index=pd.DatetimeIndex(stamps))


def _bars(quiet: int, extra: list[tuple], prior: float = 1000.0) -> pd.DataFrame:
    rows = []
    for i in range(quiet):
        price = 100.0 + (0.4 if i % 2 == 0 else -0.2)
        rows.append((price, price + 0.05, price - 0.05, price, prior))
    rows.extend(extra)
    while len(rows) < 26:
        rows.append((100.0, 100.1, 99.9, 100.0, 1000.0))
    return _session(rows[:26])


def _extensions(frame: pd.DataFrame) -> list[Signal]:
    return [item for item in find_signals(frame, "SPY", 2.0) if item.mode == "extension"]


def _signal(clock: str, direction: str = "long", day: str = "2024-01-03") -> Signal:
    stamp = pd.Timestamp(f"{day} {clock}", tz=NY)
    return Signal("SPY", "extension", direction, stamp, stamp + pd.Timedelta(minutes=15), 99.0, 100.0, 99.5, 2.0)


def _feature(signal: Signal, **overrides) -> Feature:
    values = dict(
        signal=signal,
        stretch=1.0,
        rel_volume=1.0,
        stop_atr=0.5,
        ema_stack=True,
        ema_vwap=True,
        htf60=True,
        qqq_known=True,
        qqq_confirm=True,
        lunch=False,
        early=False,
    )
    values.update(overrides)
    return Feature(**values)


def _priced(clock: str, exit_clock: str, pnl: float, day: str = "2024-01-03") -> Priced:
    signal = _signal(clock, day=day)
    fill = signal.fill_time
    exit_time = pd.Timestamp(f"{day} {exit_clock}", tz=NY)
    debit = 100.0
    credit = debit + pnl
    return Priced(signal, 100.0, 101.0, exit_time, "target" if pnl > 0 else "stop", debit, credit, pnl, 102.0, 1.0, 100.0, "")


def _frame_for(day: str = "2024-01-03") -> pd.DataFrame:
    stamps = pd.date_range(f"{day} 09:30", periods=4, freq="15min", tz=NY)
    return pd.DataFrame(
        {"open": 100.0, "high": 100.2, "low": 99.8, "close": 100.0, "volume": 1.0},
        index=stamps,
    )


def test_rules_freeze_the_family_before_the_score():
    rules = frozen_rules()
    assert rules["family"] == list(FAMILY)
    assert "cap3" in FAMILY and "confirm_5m" in FAMILY and "early_15m" in FAMILY
    assert not any(name.startswith("top") for name in FAMILY)
    assert "end-of-day top-N" in rules["lookahead"] or "end-of-day" in rules["lookahead"]
    assert "look ahead" in rules["lookahead"]
    assert "10:30" in rules["early_15m"]
    assert "not early" in rules["early_15m"]
    assert "median on training" in rules["stretch"]
    assert "11:30" in rules["lunch"] and "13:30" in rules["lunch"]
    assert "own 2 SD" in rules["confirm_15m"]
    assert "frozen 2 SD" in rules["confirm_5m"]
    assert f"{FDR_Q:.2f}" in rules["fdr"]
    assert "Seed 17" in rules["random"]
    assert len(FAMILY) == 23
    text = Path("src/webull_bot/chart_reads/vwap_quality.py").read_text()
    research = Path("src/webull_bot/chart_reads/research_vwap_quality.py").read_text()
    for banned in ("forward_options", "forward_chop", "option_quote", "place_option_order", "mark_options", "live_trading_enabled"):
        assert banned not in text
        assert banned not in research


def test_ten_thirty_is_not_early_and_lunch_includes_both_edges():
    assert EARLY_CUTOFF == time(10, 30)
    assert is_early(pd.Timestamp("2024-01-03 10:15", tz=NY))
    assert not is_early(pd.Timestamp("2024-01-03 10:30", tz=NY))
    assert in_lunch(pd.Timestamp("2024-01-03 11:30", tz=NY))
    assert in_lunch(pd.Timestamp("2024-01-03 13:30", tz=NY))
    assert not in_lunch(pd.Timestamp("2024-01-03 11:15", tz=NY))
    assert not in_lunch(pd.Timestamp("2024-01-03 13:45", tz=NY))


def test_ema_vwap_needs_the_stack_and_the_same_side_of_vwap():
    assert agrees_ema_vwap("short", 10.0, 11.0, 99.0, 100.0)
    assert not agrees_ema_vwap("long", 10.0, 11.0, 101.0, 100.0)
    assert agrees_ema_vwap("long", 12.0, 11.0, 101.0, 100.0)
    assert not agrees_ema_vwap("short", 10.0, 11.0, 101.0, 100.0)


def test_first_n_keeps_the_earliest_signals_and_not_a_later_one():
    signals = [
        _signal("11:00"),
        _signal("10:00"),
        _signal("10:45"),
        _signal("10:15"),
        _signal("10:00", day="2024-01-04"),
    ]
    kept = first_n(signals, 3)
    times = [item.signal_time.strftime("%H:%M") for item in kept if item.signal_time.day == 3]
    assert times == ["10:00", "10:15", "10:45"]
    assert any(item.signal_time.day == 4 for item in kept)
    assert len(kept) == 4


def test_train_median_ignores_a_holdout_bar():
    train = [
        _feature(_signal("10:00", day="2021-06-01"), stretch=1.0, rel_volume=1.0, stop_atr=0.2),
        _feature(_signal("10:15", day="2021-06-01"), stretch=4.0, rel_volume=3.0, stop_atr=0.8),
    ]
    holdout = [_feature(_signal("10:00", day="2024-06-03"), stretch=2.0, rel_volume=100.0, stop_atr=50.0)]
    cuts = freeze_cuts(train + holdout)
    assert cuts["stretch"] == 2.5
    assert cuts["relvol"] == 2.0
    assert cuts["stop_atr"] == 0.5
    assert cuts["train_signals"] == 2
    chosen, clock = select_signals("stretch", train + holdout, cuts, _frame_for())
    assert clock == "15m"
    assert [item.signal_time.strftime("%Y-%m-%d %H:%M") for item in chosen] == ["2021-06-01 10:15"]


def test_path_stops_count_only_closed_trades():
    frame = _frame_for()
    two_losses = run_account(
        frame,
        [
            _priced("10:00", "10:15", -10.0),
            _priced("10:30", "10:45", -8.0),
            _priced("11:00", "11:15", 25.0),
        ],
        stake=1000.0,
        path="two_losses",
    )
    assert len(two_losses["trades"]) == 2
    assert two_losses["skips"]["path"] == 1
    assert two_losses["metrics"]["ending_equity"] == 982.0

    still_open = run_account(
        frame,
        [
            _priced("10:00", "12:00", -10.0),
            _priced("11:00", "11:15", -50.0),
            _priced("12:15", "12:30", -4.0),
            _priced("13:00", "13:15", 20.0),
        ],
        stake=1000.0,
        path="two_losses",
    )
    assert [trade["fill_time"].strftime("%H:%M") for trade in still_open["trades"]] == ["10:15", "12:30"]
    assert still_open["skips"]["overlap"] == 1
    assert still_open["skips"]["path"] == 1

    first_win = run_account(
        frame,
        [
            _priced("10:00", "10:30", 12.0),
            _priced("10:15", "10:20", -100.0),
            _priced("11:00", "11:15", 5.0),
        ],
        stake=1000.0,
        path="first_win",
    )
    assert len(first_win["trades"]) == 1
    assert first_win["trades"][0]["pnl"] == 12.0
    assert first_win["skips"]["overlap"] == 1
    assert first_win["skips"]["path"] == 1


def test_fifteen_minute_follow_through_delays_the_fill_and_keeps_the_stop():
    # Low volume on the confirmation bar keeps the session band from swallowing the close.
    frame = _bars(8, [(100.0, 130.0, 100.0, 130.0, 5000.0), (132.0, 132.2, 131.8, 132.0, 1.0), (132.0, 132.1, 131.9, 132.0, 1000.0)])
    signals = _extensions(frame)
    assert signals
    original = signals[0]
    confirmed = confirm_15m(frame, signals)
    assert confirmed
    assert confirmed[0].signal_time == original.signal_time
    assert confirmed[0].stop == original.stop
    assert confirmed[0].fill_time == original.signal_time + pd.Timedelta(minutes=30)
    assert confirmed[0].fill_time != original.fill_time

    inside = frame.copy()
    confirm_at = original.signal_time + pd.Timedelta(minutes=15)
    inside.loc[confirm_at, ["open", "high", "low", "close"]] = [100.0, 100.05, 99.95, 100.0]
    assert _extensions(inside)
    assert confirm_15m(inside, _extensions(inside)) == []

    changed_fill = frame.copy()
    fill_at = original.signal_time + pd.Timedelta(minutes=30)
    changed_fill.loc[fill_at, ["open", "high", "low", "close"]] = [1.0, 1.0, 1.0, 1.0]
    again = confirm_15m(changed_fill, _extensions(changed_fill))
    assert again[0].fill_time == confirmed[0].fill_time
    assert again[0].stop == confirmed[0].stop


def test_five_minute_follow_through_uses_the_signal_band_and_the_next_open():
    frame = _bars(8, [(100.0, 100.2, 70.0, 70.0, 5000.0), (70.0, 71.0, 69.0, 70.5, 1000.0)])
    signals = _extensions(frame)
    assert signals and signals[0].direction == "short"
    signal = signals[0]
    five_index = pd.date_range(signal.signal_time, periods=4, freq="5min", tz=NY)
    # The bar that starts when the 15-minute bar ends, then the fill bar after it.
    confirm_at = signal.signal_time + pd.Timedelta(minutes=15)
    assert five_index[3] == confirm_at + pd.Timedelta(minutes=5) or confirm_at in five_index
    band_close = 70.0
    five = pd.DataFrame(
        {"open": 80.0, "high": 80.0, "low": 60.0, "close": band_close, "volume": 1.0},
        index=pd.date_range("2024-01-03 09:30", periods=40, freq="5min", tz=NY),
    )
    five.loc[confirm_at, "close"] = 60.0
    passed = confirm_5m(frame, five, [signal])
    assert passed
    assert passed[0].stop == signal.stop
    assert passed[0].fill_time == confirm_at + pd.Timedelta(minutes=5)

    five.loc[confirm_at, "close"] = 100.0
    assert confirm_5m(frame, five, [signal]) == []
    # The original scanner still emits the unconfirmed short.
    assert _extensions(frame)[0].signal_time == signal.signal_time


def test_early_rule_drops_a_failed_1000_and_keeps_an_unconfirmed_1030():
    early = _bars(2, [(90.0, 90.1, 89.9, 90.0, 1.0), (100.0, 100.1, 99.9, 100.0, 100000.0)], prior=100000.0)
    early_signals = _extensions(early)
    assert early_signals
    assert early_signals[0].signal_time.time() < time(10, 30)
    assert confirm_15m(early, early_signals) == []
    assert apply_early_15m(early, early_signals) == []

    later = _bars(4, [(90.0, 90.1, 89.9, 90.0, 1.0), (100.0, 100.1, 99.9, 100.0, 100000.0)], prior=100000.0)
    later_signals = _extensions(later)
    assert later_signals
    assert later_signals[0].signal_time.time() == time(10, 30)
    assert confirm_15m(later, later_signals) == []
    kept = apply_early_15m(later, later_signals)
    assert kept[0].signal_time == later_signals[0].signal_time
    assert kept[0].fill_time == later_signals[0].fill_time


def test_hourly_bins_start_at_the_open_and_qqq_coverage_ignores_profit():
    stamps = pd.date_range("2024-01-03 09:30", periods=40, freq="1min", tz=NY)
    minutes = pd.DataFrame(
        {"open": 10.0, "high": 11.0, "low": 9.0, "close": 10.5, "volume": 1.0},
        index=stamps,
    )
    hourly = to_rth_bars(minutes, "60min")
    assert list(hourly.index.time) == [time(9, 30)]
    five = to_rth_bars(minutes, "5min")
    assert five.index[0].time() == time(9, 30)
    assert five.index[1].time() == time(9, 35)
    forming = pd.Timestamp("2024-01-03 10:30", tz=NY)
    ends = np.array([forming.value])
    assert _hourly_agrees(_signal("10:00"), ends, np.array([True]), np.array([False])) is False
    assert _hourly_agrees(_signal("10:30"), ends, np.array([True]), np.array([False])) is True
    assert qqq_covers(date(2017, 2, 16), 0.90)
    assert not qqq_covers(date(2019, 1, 2), 0.99)
    assert not qqq_covers(date(2017, 2, 16), 0.89)
    assert "qqq" not in scored_family(False)
    assert scored_family(True) == FAMILY


def test_fast_account_matches_simulate_on_the_same_signals():
    frame = _bars(8, [(100.0, 130.0, 100.0, 130.0, 5000.0), (130.0, 131.0, 120.0, 125.0, 1000.0)])
    signals = _extensions(frame)
    assert signals
    iv = {DAY: (20.0, "test")}
    priced = price_signals(frame, signals, iv)
    fast = run_account(frame, priced, stake=1000.0)
    slow = simulate(frame, signals, target="r", kind="0dte", stake=1000.0, long_only=False, iv_points=iv)
    assert len(fast["trades"]) == len(slow["trades"])
    assert fast["metrics"]["trades"] == slow["metrics"]["trades"]
    if slow["trades"]:
        assert np.isclose(fast["trades"][0]["pnl"], slow["trades"][0]["pnl"])
        assert np.isclose(fast["metrics"]["ending_equity"], slow["metrics"]["ending_equity"])
        assert fast["trades"][0]["fill_time"] == slow["trades"][0]["fill_time"]


def test_a_holdout_feature_does_not_move_the_stack_cap():
    features = [
        _feature(_signal("10:00", day="2021-06-01"), ema_stack=True, htf60=True, lunch=False),
        _feature(_signal("10:15", day="2021-06-01"), ema_stack=True, htf60=False, lunch=False),
        _feature(_signal("10:30", day="2021-06-01"), ema_stack=True, htf60=True, lunch=True),
        _feature(_signal("10:45", day="2021-06-01"), ema_stack=True, htf60=True, lunch=False),
        _feature(_signal("11:00", day="2021-06-01"), ema_stack=True, htf60=True, lunch=False),
        _feature(_signal("11:15", day="2021-06-01"), ema_stack=True, htf60=True, lunch=False),
    ]
    chosen, _clock = select_signals("stack_cap3", features, freeze_cuts(features), _frame_for())
    clocks = [item.signal_time.strftime("%H:%M") for item in chosen]
    assert clocks == ["10:00", "10:45", "11:00"]


def test_signal_features_do_not_read_the_fill_bar():
    frame = _bars(22, [(100.0, 130.0, 100.0, 130.0, 5000.0), (50.0, 50.0, 50.0, 50.0, 1.0)])
    signals = _extensions(frame)
    before = build_features(frame, signals)
    changed = frame.copy()
    changed.loc[signals[0].fill_time, ["open", "high", "low", "close", "volume"]] = [1.0, 1.0, 1.0, 1.0, 1.0]
    after = build_features(changed, _extensions(changed))
    assert np.isfinite(before[0].stretch)
    assert np.isfinite(before[0].rel_volume)
    assert after[0].stretch == before[0].stretch
    assert after[0].ema_vwap == before[0].ema_vwap
    assert after[0].rel_volume == before[0].rel_volume
    assert after[0].signal.stop == before[0].signal.stop


def test_a_bar_with_no_next_fill_is_still_judged_for_confirmation():
    rows = []
    for i in range(8):
        price = 100.0 + (0.4 if i % 2 == 0 else -0.2)
        rows.append((price, price + 0.05, price - 0.05, price, 1000.0))
    rows.append((100.0, 130.0, 100.0, 130.0, 5000.0))
    frame = _session(rows)
    assert _extensions(frame) == []
    pending = pending_extensions(frame, DAY)
    assert len(pending) == 1
    assert pending[0].direction == "long"
    assert confirm_15m(frame, pending) == []
    five = pd.DataFrame(
        {"open": 100.0, "high": 100.0, "low": 100.0, "close": 100.0, "volume": 1.0},
        index=pd.date_range("2024-01-03 09:30", periods=40, freq="5min", tz=NY),
    )
    confirm_at = pending[0].signal_time + pd.Timedelta(minutes=15)
    five.loc[confirm_at, "close"] = 140.0
    marks = confirmation_marks(frame, five, DAY)
    assert marks[0]["awaiting_fill"] is True
    assert marks[0]["confirm_15m"] is False
    assert marks[0]["confirm_5m"] is True
