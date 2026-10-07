"""Trend-exhaustion shelf. No network and no broker."""

from pathlib import Path

import numpy as np
import pandas as pd

from webull_bot.chart_reads.ema_reclaim import Prepared
from webull_bot.chart_reads.exhaustion import Exhaustion, find_exhaustions, frozen_rules, walk_exhaustion
from webull_bot.chart_reads.reentry import simulate_paths

NY = "America/New_York"


def _prep(n: int = 12, **columns) -> Prepared:
    stamps = pd.date_range("2024-06-03 10:00", periods=n, freq="5min", tz=NY)
    zeros = np.zeros(n, dtype=float)

    def col(name: str, default: np.ndarray) -> np.ndarray:
        if name not in columns:
            return default
        return np.asarray(columns[name], dtype=float)

    close = col("close", np.full(n, 101.0))
    return Prepared(
        index=pd.DatetimeIndex(stamps),
        open=col("open", close.copy()),
        high=col("high", close + 0.2),
        low=col("low", close - 0.2),
        close=close,
        volume=col("volume", np.full(n, 1000.0)),
        ema9=col("ema9", np.full(n, 104.0)),
        ema20=col("ema20", np.full(n, 98.0)),
        ema200=col("ema200", np.full(n, 90.0)),
        atr=col("atr", np.ones(n)),
        vwap=col("vwap", np.full(n, 100.0)),
        std=col("std", np.full(n, 10.0)),
        macd_line=zeros.copy(),
        macd_signal=zeros.copy(),
        macd_hist=col("macd_hist", zeros),
        rsi=col("rsi", np.full(n, 50.0)),
        hammer=np.zeros(n, dtype=bool),
        engulf_bull=np.zeros(n, dtype=bool),
        morning=np.zeros(n, dtype=bool),
        shooting=np.zeros(n, dtype=bool),
        engulf_bear=np.zeros(n, dtype=bool),
        evening=np.zeros(n, dtype=bool),
        dates=[stamp.date() for stamp in stamps],
        times=[stamp.time() for stamp in stamps],
    )


def _shorts(prep: Prepared) -> list[Exhaustion]:
    return [item for item in find_exhaustions(prep, "SPY") if item.direction == "short"]


def _longs(prep: Prepared) -> list[Exhaustion]:
    return [item for item in find_exhaustions(prep, "SPY") if item.direction == "long"]


def _short_break() -> Prepared:
    # Bar 2 is the swing high. Bar 5 tags the upper band. Bar 6 prints the shelf. Bar 7 breaks it.
    hist = np.zeros(12)
    hist[4:8] = [0.40, 0.30, 0.20, 0.10]
    rsi = np.full(12, 50.0)
    rsi[6] = 75.0
    rsi[7] = 60.0
    high = np.array([105, 106, 110, 107, 106, 121, 102, 101, 100.5, 100, 100, 100], dtype=float)
    low = np.array([108, 108, 108, 108, 108, 108, 100.0, 99.4, 99.0, 99, 99, 99], dtype=float)
    close = np.full(12, 109.0)
    close[6] = 101.2
    close[7] = 99.5
    opened = close.copy()
    opened[8] = 99.4
    ema9 = np.full(12, 104.0)
    ema9[7] = 102.0
    return _prep(open=opened, high=high, low=low, close=close, ema9=ema9, macd_hist=hist, rsi=rsi)


def test_rules_are_frozen_and_the_sources_stay_off_the_live_path():
    rules = frozen_rules()
    assert "lowest low" in rules["support"]
    assert "does not move the anchor" in rules["tag"]
    assert "zero-width" in rules["tag"]
    assert "more negative" in rules["macd"]
    assert "three bars" in rules["macd"]
    assert "at least 70" in rules["rsi"]
    assert "rolling up" in rules["rsi"]
    assert "2-bar swing high" in rules["stop"]
    assert "one cent" in rules["stop"].lower()
    assert "20 EMA and VWAP" in rules["target"]
    assert "separate books" in rules["target"]
    assert "776.2" in rules["chart_day"]
    assert "left unmarked" in rules["chart_day"]
    assert "Not a live strategy" in rules["not_live"]
    assert "20 EMA 0 DTE" in rules["books"]
    root = Path("src/webull_bot/chart_reads")
    for name in ("exhaustion.py", "research_exhaustion.py"):
        text = (root / name).read_text()
        for banned in ("forward_options", "forward_chop", "option_quote", "place_option_order", "mark_options"):
            assert banned not in text
        assert "live_trading_enabled" not in text


def test_the_break_uses_the_pullback_low_and_fills_the_next_open():
    prep = _short_break()
    found = _shorts(prep)
    assert len(found) == 1
    item = found[0]
    assert item.tag_i == 5
    assert item.support_i == 6
    assert item.support == 100.0
    assert item.signal_i == 7
    assert item.fill_i == 8
    assert item.stop == 121.01
    assert prep.open[item.fill_i] == 99.4


def test_a_close_has_to_clear_both_the_shelf_and_the_9_and_the_fade_has_to_be_positive():
    above_shelf = _short_break()
    above_shelf.close = above_shelf.close.copy()
    above_shelf.close[7] = 100.5
    assert _shorts(above_shelf) == []
    above_ema = _short_break()
    above_ema.ema9 = above_ema.ema9.copy()
    above_ema.ema9[7] = 99.0
    assert _shorts(above_ema) == []
    negative = _short_break()
    negative.macd_hist = negative.macd_hist.copy()
    negative.macd_hist[4:8] = [-0.10, -0.20, -0.30, -0.40]
    assert _shorts(negative) == []
    two_shrinks = _short_break()
    two_shrinks.macd_hist = two_shrinks.macd_hist.copy()
    two_shrinks.macd_hist[4:8] = [0.20, 0.40, 0.20, 0.10]
    assert _shorts(two_shrinks) == []
    cool = _short_break()
    cool.rsi = np.full(12, 60.0)
    cool.rsi[7] = 55.0
    assert _shorts(cool) == []


def test_a_later_band_tag_does_not_reset_the_shelf_and_a_downtrend_tag_is_not_the_anchor():
    hist = np.zeros(8)
    hist[3:7] = [0.40, 0.30, 0.20, 0.10]
    rsi = np.full(8, 50.0)
    rsi[4] = 80.0
    rsi[5] = 78.0
    rsi[6] = 60.0
    high = np.array([105, 110, 106, 121, 128, 125, 104, 100], dtype=float)
    low = np.array([108, 108, 108, 108, 100.0, 110.0, 101.2, 99.0], dtype=float)
    close = np.full(8, 109.0)
    close[6] = 100.6
    opened = close.copy()
    opened[7] = 100.4
    prep = _prep(
        n=8,
        open=opened,
        high=high,
        low=low,
        close=close,
        macd_hist=hist,
        rsi=rsi,
    )
    assert _shorts(prep) == []
    prep.close = prep.close.copy()
    prep.low = prep.low.copy()
    prep.close[6] = 99.0
    prep.low[6] = 98.5
    found = _shorts(prep)
    assert len(found) == 1
    assert found[0].tag_i == 3
    assert found[0].support == 100.0
    early = _short_break()
    early.ema9 = early.ema9.copy()
    early.ema20 = early.ema20.copy()
    early.high = early.high.copy()
    early.low = early.low.copy()
    early.ema9[2] = 90.0
    early.ema20[2] = 95.0
    early.high[2] = 130.0
    early.low[3] = 90.0
    found = _shorts(early)
    assert len(found) == 1
    assert found[0].tag_i == 5
    assert found[0].support == 100.0


def test_an_unconfirmed_swing_is_not_the_stop_and_a_later_bar_does_not_move_the_signal():
    prep = _short_break()
    prep.high = prep.high.copy()
    prep.high[6] = 130.0
    item = _shorts(prep)[0]
    assert item.stop == 110.01
    before = [(row.tag_i, row.signal_i, row.support, row.stop) for row in _shorts(prep)]
    prep.close = prep.close.copy()
    prep.high = prep.high.copy()
    prep.close[11] = 1.0
    prep.high[11] = 200.0
    after = [(row.tag_i, row.signal_i, row.support, row.stop) for row in _shorts(prep)]
    assert before == after


def test_the_stop_fills_before_the_target_and_a_level_that_is_not_beyond_the_fill_is_skipped():
    prep = _short_break()
    item = _shorts(prep)[0]
    prep.low = prep.low.copy()
    prep.low[8] = 97.0
    targeted = walk_exhaustion(prep, item, "ema20")
    assert targeted is not None and targeted["reason"] == "ema20" and targeted["exit_spot"] == 98.0
    prep.high = prep.high.copy()
    prep.high[8] = 122.0
    stopped = walk_exhaustion(prep, item, "ema20")
    assert stopped is not None and stopped["reason"] == "stop" and stopped["exit_spot"] == 121.01
    gapped = _short_break()
    held = _shorts(gapped)[0]
    gapped.open = gapped.open.copy()
    gapped.open[8] = 122.0
    gap = walk_exhaustion(gapped, held, "ema20")
    assert gap is not None and gap["reason"] == "stop" and gap["exit_spot"] == 122.0
    skipped = _short_break()
    held = _shorts(skipped)[0]
    skipped.ema20 = np.full(12, 101.0)
    assert walk_exhaustion(skipped, held, "ema20") is None


def test_flat_at_the_1530_open():
    prep = _prep(3)
    stamps = pd.to_datetime(["2024-06-03 15:20", "2024-06-03 15:25", "2024-06-03 15:30"]).tz_localize(NY)
    prep.index = pd.DatetimeIndex(stamps)
    prep.dates = [stamp.date() for stamp in stamps]
    prep.times = [stamp.time() for stamp in stamps]
    prep.open = np.array([100.0, 100.0, 100.4])
    prep.high = np.array([100.2, 100.2, 100.5])
    prep.low = np.array([99.5, 99.6, 99.8])
    prep.close = np.array([100.0, 100.1, 100.2])
    prep.ema20 = np.array([99.0, 99.0, 99.0])
    item = Exhaustion("SPY", "short", 0, 0, 1, 99.0, 0, 101.0)
    path = walk_exhaustion(prep, item, "ema20")
    assert path is not None
    assert path["reason"] == "flat"
    assert path["exit_spot"] == 100.4


def test_a_signal_after_1520_does_not_fill_and_a_zero_width_band_is_not_a_tag():
    prep = _short_break()
    start = pd.Timestamp("2024-06-03 14:50", tz=NY)
    stamps = pd.date_range(start, periods=len(prep.close), freq="5min")
    prep.index = pd.DatetimeIndex(stamps)
    prep.dates = [stamp.date() for stamp in stamps]
    prep.times = [stamp.time() for stamp in stamps]
    assert _shorts(prep) == []
    quiet = _short_break()
    quiet.std = np.zeros(12)
    assert _shorts(quiet) == []


def test_the_long_is_the_mirror():
    hist = np.zeros(12)
    hist[4:8] = [-0.40, -0.30, -0.20, -0.10]
    rsi = np.full(12, 50.0)
    rsi[6] = 25.0
    rsi[7] = 40.0
    high = np.array([90, 90, 90, 90, 90, 90, 100.0, 102.0, 111, 103, 103, 103], dtype=float)
    low = np.array([88, 87, 85, 86, 89, 79, 90, 95, 96, 96, 96, 96], dtype=float)
    close = np.full(12, 90.0)
    close[6] = 96.0
    close[7] = 101.0
    opened = close.copy()
    opened[8] = 101.5
    prep = _prep(
        open=opened,
        high=high,
        low=low,
        close=close,
        ema9=np.full(12, 90.0),
        ema20=np.full(12, 110.0),
        macd_hist=hist,
        rsi=rsi,
    )
    found = _longs(prep)
    assert len(found) == 1
    item = found[0]
    assert item.tag_i == 5
    assert item.support == 100.0
    assert item.support_i == 6
    assert item.signal_i == 7
    assert item.fill_i == 8
    assert item.stop == 78.99
    path = walk_exhaustion(prep, item, "ema20")
    assert path is not None and path["reason"] == "ema20" and path["exit_spot"] == 110.0


def test_one_position_skips_the_overlap():
    prep = _prep(6)
    prep.open = np.array([100, 100, 100, 100, 100, 100], dtype=float)
    prep.close = np.array([101, 101, 102, 102, 102, 102], dtype=float)
    first = {
        "direction": "long",
        "variant": "ema20",
        "fill": 100.0,
        "stop": 99.0,
        "reason": "ema20",
        "exit_spot": 102.0,
        "exit_time": prep.index[4],
        "fill_i": 1,
    }
    second = dict(first)
    second["fill_i"] = 2
    second["exit_time"] = prep.index[5]
    book = simulate_paths(prep, [first, second], kind="shares", stake=1000.0, long_only=True)
    assert book["metrics"]["trades"] == 1
    assert book["skips"]["overlap"] == 1
