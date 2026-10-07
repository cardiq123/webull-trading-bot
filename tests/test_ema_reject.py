"""9/20 EMA rejection rules. No network and no broker."""

from datetime import time
from pathlib import Path

import numpy as np
import pandas as pd

from webull_bot.chart_reads.ema_reject import (
    FLAT,
    LAST_SIGNAL,
    RANDOM_SEED,
    STOP_PAD,
    TOUCH_ATR,
    Signal,
    classify_bar,
    eligible_fill,
    find_signals,
    frozen_rules,
    indicator_frame,
    passes_gate,
    random_signals,
    simulate,
    swing_targets,
    to_five_minute,
    walk_ema_exit,
)
from webull_bot.chart_reads.vwap_band import metrics_from, walk_exit

NY = "America/New_York"


def _ok(**overrides) -> dict:
    base = dict(
        ema9=100.0,
        ema20=101.0,
        ema9_prev=100.3,
        ema20_prev=101.2,
        close=99.4,
        high=100.0,
        low=99.2,
        width=1.0,
        rel_volume=1.0,
        vwap=100.05,
    )
    base.update(overrides)
    return base


def _day(rows: list[tuple], day: str = "2024-06-03", minutes: int = 5) -> pd.DataFrame:
    stamps = []
    cursor = pd.Timestamp(f"{day} 09:30", tz=NY)
    for _row in rows:
        stamps.append(cursor)
        cursor += pd.Timedelta(minutes=minutes)
    frame = pd.DataFrame(rows, columns=["open", "high", "low", "close", "volume"], index=pd.DatetimeIndex(stamps))
    return frame


def _signal(direction: str = "long", fill: str = "2024-06-03 10:00", stop: float = 99.0, swing: float = 102.0) -> Signal:
    fill_time = pd.Timestamp(fill, tz=NY)
    signal_time = fill_time - pd.Timedelta(minutes=5)
    return Signal("SPY", "vwap", direction, signal_time, fill_time, stop, stop, swing, 100.0)


def test_rules_are_frozen_before_any_score():
    rules = frozen_rules()
    assert "opposite 2 SD" in rules["targets"]["band"]
    assert "sells at the first tag" in rules["targets"]["band200"]
    assert rules["gate_variant"] == "vwap"
    assert rules["touch_atr"] == 0.10
    assert rules["vwap_atr"] == 0.10
    assert rules["spread_floor_atr"] == 0.10
    assert rules["slope_floor_atr"] == 0.05
    assert rules["slope_bars"] == 3
    assert rules["rel_volume_max"] == 0.85
    assert "2022-01-01" in rules["split"]
    assert rules["random"].startswith("Seed 17")
    assert "300" in rules["gate"]
    assert len(rules["gate_books"]) == 2
    assert "0.75" in rules["chop"]
    assert TOUCH_ATR == 0.10
    assert RANDOM_SEED == 17
    assert LAST_SIGNAL == time(15, 35)
    assert FLAT == time(15, 45)


def test_vwap_confluence_is_the_only_extra_gate_filter():
    hit = classify_bar(**_ok())
    assert hit is not None
    assert hit[0] == "short"
    assert hit[1] == ("ema", "vwap", "ema20")
    far = classify_bar(**_ok(vwap=102.0))
    assert far is not None
    assert far[1] == ("ema", "ema20")
    # The high still tags, and it does not reach a 20 EMA that is 1 ATR away.
    tagged = classify_bar(**_ok(high=100.10))
    assert tagged is not None
    assert "ema20" in tagged[1]
    # A high through the 20 EMA is more than 0.10 ATR from the 9 EMA, so it is not a tag.
    assert classify_bar(**_ok(high=101.2)) is None


def test_chop_guard_blocks_a_clean_tag():
    assert classify_bar(**_ok(rel_volume=0.84)) is None
    assert classify_bar(**_ok(ema20=100.05)) is None
    assert classify_bar(**_ok(ema9_prev=100.04)) is None
    assert classify_bar(**_ok(high=100.2)) is None
    assert classify_bar(**_ok(close=100.1)) is None


def test_long_mirror_tags_the_low():
    hit = classify_bar(**_ok(
        ema9=100.0, ema20=99.0, ema9_prev=99.7, ema20_prev=98.8,
        close=100.6, high=100.8, low=100.0, vwap=99.95,
    ))
    assert hit is not None
    assert hit[0] == "long"
    assert "vwap" in hit[1]


def test_five_minute_bins_start_at_the_open():
    stamps = pd.date_range("2024-06-03 09:30", periods=5, freq="1min", tz=NY)
    minutes = pd.DataFrame(
        {"open": 10.0, "high": np.arange(5) + 10, "low": 9.0, "close": 11.0, "volume": 1.0},
        index=stamps,
    )
    bars = to_five_minute(minutes)
    assert bars.index[0].time() == time(9, 30)
    assert float(bars.iloc[0]["high"]) == 14.0
    assert float(bars.iloc[0]["open"]) == 10.0
    assert float(bars.iloc[0]["close"]) == 11.0
    assert len(bars) == 1


def test_swing_is_not_visible_until_two_bars_later():
    low = np.array([5.0, 4.0, 1.0, 4.0, 5.0, 4.5, 4.0])
    high = low + 0.5
    close = low + 0.2
    short_target, _long_target = swing_targets(high, low, close, width=2)
    assert np.isnan(short_target[3])
    assert short_target[4] == 1.0


def test_a_high_on_the_9_ema_signals_and_fills_next_open():
    rows = []
    price = 150.0
    for _i in range(70):
        nxt = price - 0.3
        rows.append((price, max(price, nxt), min(price, nxt), nxt, 2000.0))
        price = nxt
    frame = _day(rows)
    ind = indicator_frame(frame)
    picked = None
    for i in range(30, len(ind) - 2):
        row = ind.iloc[i]
        width = float(row["atr"])
        if not np.isfinite(width) or width <= 0:
            continue
        if float(row["ema9"]) >= float(row["ema20"]):
            continue
        if float(row["close"]) >= float(row["ema9"]) or float(row["close"]) >= float(row["ema20"]):
            continue
        if float(row["ema9"]) >= float(row["ema9_prev"]) or float(row["ema20"]) >= float(row["ema20_prev"]):
            continue
        if (float(row["ema9_prev"]) - float(row["ema9"])) < 0.05 * width:
            continue
        if abs(float(row["ema9"]) - float(row["ema20"])) < 0.10 * width:
            continue
        if float(row["rel_volume"]) < 0.85:
            continue
        picked = i
        break
    assert picked is not None
    ema9 = float(ind.iloc[picked]["ema9"])
    edited = frame.copy()
    edited.iloc[picked, edited.columns.get_loc("high")] = ema9
    signals = [item for item in find_signals(edited, "SPY") if item.signal_time == ind.index[picked]]
    assert signals
    assert any(item.variant == "ema" and item.direction == "short" for item in signals)
    assert all(item.fill_time == ind.index[picked + 1] for item in signals)
    assert all(item.stop_reject == ema9 + STOP_PAD for item in signals)


def test_future_bar_does_not_change_an_earlier_signal():
    rows = []
    price = 120.0
    for i in range(40):
        nxt = price - 0.25
        rows.append((price, price + 0.02, nxt, nxt, 1000.0))
        price = nxt
    # A bounce so a swing low can confirm, then the decline resumes.
    for bounce in (0.4, 0.2, -0.3, -0.5, -0.4):
        nxt = price + bounce
        high = max(price, nxt) + 0.05
        low = min(price, nxt)
        rows.append((price, high, low, nxt, 1000.0))
        price = nxt
    for _i in range(18):
        nxt = price - 0.25
        rows.append((price, price + 0.02, nxt, nxt, 1000.0))
        price = nxt
    frame = _day(rows)
    left = find_signals(frame.iloc[:-1], "SPY")
    changed = frame.copy()
    changed.iloc[-1, changed.columns.get_loc("close")] = 50.0
    changed.iloc[-1, changed.columns.get_loc("high")] = 80.0
    right = find_signals(changed.iloc[:-1], "SPY")
    assert [(item.signal_time, item.variant, item.stop_reject) for item in left] == [
        (item.signal_time, item.variant, item.stop_reject) for item in right
    ]


def test_fill_stops_at_the_last_tradable_bar():
    assert eligible_fill("2024-06-03 15:35", "2024-06-03 15:40")
    assert not eligible_fill("2024-06-03 15:40", "2024-06-03 15:45")
    assert not eligible_fill("2024-06-03 15:35", "2024-06-04 09:30")


def test_stop_wins_when_the_bar_can_reach_both():
    stamps = pd.date_range("2024-06-03 10:00", periods=3, freq="5min", tz=NY)
    session = pd.DataFrame(
        {"open": [100.0, 100.0, 100.0], "high": [101.0, 103.0, 100.0], "low": [99.0, 97.0, 99.0], "close": [100.0, 100.0, 100.0], "volume": 1.0},
        index=stamps,
    )
    reason, price, _stamp = walk_exit(session, 1, "long", 99.5, 102.0)
    assert reason == "stop"
    assert price == 99.5


def test_flat_exit_uses_the_1545_open():
    rows = []
    cursor = pd.Timestamp("2024-06-03 15:30", tz=NY)
    stamps = []
    for price, high, low in ((100.0, 100.2, 99.8), (100.0, 100.2, 99.8), (100.0, 130.0, 70.0), (101.0, 102.0, 100.0)):
        stamps.append(cursor)
        rows.append((price, high, low, price, 1.0))
        cursor += pd.Timedelta(minutes=5)
    session = pd.DataFrame(rows, columns=["open", "high", "low", "close", "volume"], index=pd.DatetimeIndex(stamps))
    # 15:30, 15:35, 15:40, 15:45. Fill at 15:40, which is index 2. Stop and target are far.
    reason, price, stamp = walk_exit(session, 2, "long", 50.0, 200.0)
    assert reason == "flat"
    assert price == 101.0
    assert stamp.time() == time(15, 45)


def test_ema_exit_lets_the_stop_fill_first():
    stamps = pd.date_range("2024-06-03 10:00", periods=2, freq="5min", tz=NY)
    session = pd.DataFrame(
        {"open": [100.0, 100.0], "high": [100.4, 101.5], "low": [99.6, 99.0], "close": [100.0, 99.2], "volume": 1.0},
        index=stamps,
    )
    ema9 = pd.Series([100.2, 100.3], index=stamps)
    reason, price, _stamp = walk_ema_exit(session, 1, "long", 99.5, ema9)
    assert reason == "stop"
    assert price == 99.5
    quiet = session.copy()
    quiet.iloc[1, quiet.columns.get_loc("low")] = 99.8
    reason, price, _stamp = walk_ema_exit(quiet, 1, "long", 99.5, ema9)
    assert reason == "ema"
    assert price == 99.2


def test_cash_book_is_long_only_and_uses_the_next_open():
    stamps = pd.date_range("2024-06-03 09:30", periods=20, freq="5min", tz=NY)
    session = pd.DataFrame(
        {"open": 100.0, "high": 100.4, "low": 99.6, "close": 100.0, "volume": 1000.0},
        index=stamps,
    )
    long_signal = Signal("SPY", "vwap", "long", stamps[2], stamps[3], 99.0, 99.5, 101.5, 100.2)
    short_signal = Signal("SPY", "vwap", "short", stamps[2], stamps[3], 101.0, 100.8, 98.0, 99.8)
    book = simulate(session, [long_signal, short_signal], stop="reject", target="swing", kind="shares", stake=1_000.0, long_only=True)
    assert book["skips"]["short"] == 1
    assert len(book["trades"]) == 1
    assert book["trades"][0]["direction"] == "long"
    assert book["trades"][0]["entry"] == 100.0


def test_no_fill_when_the_swing_is_not_beyond_the_open():
    stamps = pd.date_range("2024-06-03 09:30", periods=8, freq="5min", tz=NY)
    session = pd.DataFrame(
        {"open": [100.0, 100.0, 100.0, 99.0, 99.0, 99.0, 99.0, 99.0], "high": 100.5, "low": 98.5, "close": 99.5, "volume": 1000.0},
        index=stamps,
    )
    # Short target 100 is not below the 99 open.
    signal = Signal("SPY", "vwap", "short", stamps[2], stamps[3], 101.0, 100.5, 100.0, 99.8)
    book = simulate(session, [signal], stop="reject", target="swing", kind="shares", stake=1_000.0, long_only=False)
    assert book["trades"] == []
    assert book["skips"]["swing"] == 1


def test_random_entries_use_the_seed_and_the_same_count():
    frame = _day([(100.0, 101.0, 99.0, 100.0, 1000.0) for _i in range(10)])
    left = random_signals(frame, "SPY", 4, seed=17)
    right = random_signals(frame, "SPY", 4, seed=17)
    other = random_signals(frame, "SPY", 4, seed=18)
    assert len(left) == 4
    assert [item.fill_time for item in left] == [item.fill_time for item in right]
    assert [item.direction for item in left] == [item.direction for item in right]
    assert [item.fill_time for item in left] != [item.fill_time for item in other] or [
        item.direction for item in left
    ] != [item.direction for item in other]
    assert all(item.variant == "random" for item in left)
    assert left[0].stop_reject == (101.0 + STOP_PAD) or left[0].stop_reject == (99.0 - STOP_PAD)


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


def _reversal_day(direction: str) -> tuple[pd.DataFrame, int]:
    """Downtrend or uptrend, then a bar that closes through 9, 20, and VWAP."""
    rows = []
    price = 100.0
    step = -0.15 if direction == "long" else 0.15
    for _i in range(55):
        nxt = price + step
        rows.append((price, max(price, nxt) + 0.02, min(price, nxt) - 0.02, nxt, 3000.0))
        price = nxt
    frame = _day(rows + [(price, price, price, price, 3000.0)] * 4)
    ind = indicator_frame(frame)
    i = 55
    prior = ind.iloc[i - 1]
    if direction == "long":
        assert float(prior["ema9"]) < float(prior["ema20"])
        assert float(prior["close"]) < float(prior["vwap"])
        level = max(float(prior["ema9"]), float(prior["ema20"]), float(prior["vwap"]), float(prior["close"])) + 2.0
        frame.iloc[i] = (float(prior["close"]), level, float(prior["close"]) - 0.2, level, 3000.0)
        frame.iloc[i + 1] = (level - 0.3, level, level - 0.4, level - 0.1, 3000.0)
        frame.iloc[i + 2] = (level - 0.05, level, level - 0.2, level - 0.05, 3000.0)
    else:
        assert float(prior["ema9"]) > float(prior["ema20"])
        assert float(prior["close"]) > float(prior["vwap"])
        level = min(float(prior["ema9"]), float(prior["ema20"]), float(prior["vwap"]), float(prior["close"])) - 2.0
        frame.iloc[i] = (float(prior["close"]), float(prior["close"]) + 0.2, level, level, 3000.0)
        frame.iloc[i + 1] = (level + 0.3, level + 0.4, level, level + 0.1, 3000.0)
        frame.iloc[i + 2] = (level + 0.05, level + 0.2, level, level + 0.05, 3000.0)
    return frame, i


def test_reversal_is_not_the_gate_and_fills_after_confirmation():
    rules = frozen_rules()
    assert rules["gate_variant"] == "vwap"
    assert "reversal" in rules["variants"]
    assert "Not the gate" in rules["variants"]["reversal"]
    frame, breakout = _reversal_day("long")
    ind = indicator_frame(frame)
    signals = [item for item in find_signals(frame, "SPY") if item.variant == "reversal"]
    assert len(signals) == 1
    signal = signals[0]
    assert signal.direction == "long"
    assert signal.signal_time == ind.index[breakout + 1]
    assert signal.fill_time == ind.index[breakout + 2]
    assert signal.stop_reject == float(frame.iloc[breakout]["low"]) - STOP_PAD
    red = frame.copy()
    red.iloc[breakout + 1, red.columns.get_loc("close")] = float(red.iloc[breakout + 1]["open"]) - 0.05
    assert [item for item in find_signals(red, "SPY") if item.variant == "reversal"] == []
    mirror, short_bar = _reversal_day("short")
    shorts = [item for item in find_signals(mirror, "SPY") if item.variant == "reversal"]
    assert len(shorts) == 1
    assert shorts[0].direction == "short"
    assert shorts[0].signal_time == indicator_frame(mirror).index[short_bar + 1]
    assert shorts[0].stop_reject == float(mirror.iloc[short_bar]["high"]) + STOP_PAD


def test_reversal_does_not_confirm_into_the_next_session():
    frame, breakout = _reversal_day("long")
    nxt = frame.copy()
    nxt.index = nxt.index.map(lambda stamp: stamp + pd.Timedelta(days=1) if stamp >= frame.index[breakout + 1] else stamp)
    assert [item for item in find_signals(nxt, "SPY") if item.variant == "reversal"] == []


def test_sources_do_not_touch_the_forward_test():
    root = Path("src/webull_bot/chart_reads")
    for name in ("ema_reject.py", "research_ema_reject.py"):
        text = (root / name).read_text()
        for banned in ("forward_options", "forward_chop", "option_quote", "place_option_order", "mark_options"):
            assert banned not in text
        assert "live_trading_enabled" not in text
