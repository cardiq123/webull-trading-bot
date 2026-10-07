"""Trendline and support bounce. No network and no broker."""

from pathlib import Path

import numpy as np
import pandas as pd

from webull_bot.chart_reads.ema_reclaim import Prepared
from webull_bot.chart_reads.reentry import simulate_paths
from webull_bot.chart_reads.trendline_bounce import Bounce, find_bounces, frozen_rules, walk_bounce

NY = "America/New_York"


def _prep(n: int = 14, **columns) -> Prepared:
    stamps = pd.date_range("2024-06-03 10:00", periods=n, freq="5min", tz=NY)
    zeros = np.zeros(n, dtype=float)

    def col(name: str, default: np.ndarray) -> np.ndarray:
        if name not in columns:
            return default
        return np.asarray(columns[name], dtype=float)

    close = col("close", np.full(n, 104.0))
    return Prepared(
        index=pd.DatetimeIndex(stamps),
        open=col("open", np.full(n, 103.0)),
        high=col("high", close + 0.4),
        low=col("low", np.full(n, 103.0)),
        close=close,
        volume=col("volume", np.full(n, 1000.0)),
        ema9=col("ema9", np.full(n, 102.0)),
        ema20=col("ema20", np.full(n, 100.0)),
        ema200=col("ema200", np.full(n, 90.0)),
        atr=col("atr", np.ones(n)),
        vwap=col("vwap", np.full(n, 100.0)),
        std=col("std", np.ones(n)),
        macd_line=zeros.copy(),
        macd_signal=zeros.copy(),
        macd_hist=zeros.copy(),
        rsi=np.full(n, 50.0),
        hammer=np.zeros(n, dtype=bool),
        engulf_bull=np.zeros(n, dtype=bool),
        morning=np.zeros(n, dtype=bool),
        shooting=np.zeros(n, dtype=bool),
        engulf_bear=np.zeros(n, dtype=bool),
        evening=np.zeros(n, dtype=bool),
        dates=[stamp.date() for stamp in stamps],
        times=[stamp.time() for stamp in stamps],
    )


def _of(prep: Prepared, variant: str, direction: str = "long") -> list[Bounce]:
    return [item for item in find_bounces(prep, "SPY") if item.variant == variant and item.direction == direction]


def _hold() -> Prepared:
    # Bar 2 and bar 8 are rising pivot lows. Bar 11 wicks through both and closes green back above the line.
    low = np.array([102, 101, 100, 101, 102, 103, 102, 101.5, 101, 102, 103, 100.8, 104, 104], dtype=float)
    close = np.full(14, 104.0)
    close[11] = 102.0
    opened = np.full(14, 103.0)
    opened[11] = 101.0
    opened[12] = 102.2
    return _prep(low=low, close=close, open=opened)


def test_rules_are_frozen_and_the_sources_stay_off_the_live_path():
    rules = frozen_rules()
    assert "0.10 ATR" in rules["tag"]
    assert "Two higher-low touches" in rules["trendline"]
    assert "not required" in rules["trendline"]
    assert "latest confirmed 2-bar pivot low" in rules["support"]
    assert "round number" in rules["support"]
    assert "lower of those two" in rules["stop"]
    assert "200 EMA" in rules["target"]
    assert "Support alone" in rules["tag"]
    assert "trendline alone" in rules["tag"]
    assert "776.2" in rules["chart_day"]
    assert "10:50" in rules["chart_day"]
    assert "Not a live strategy" in rules["not_live"]
    assert "confluence band 0 DTE" in rules["compare"]
    root = Path("src/webull_bot/chart_reads")
    for name in ("trendline_bounce.py", "research_trendline_bounce.py"):
        text = (root / name).read_text()
        for banned in ("forward_options", "forward_chop", "option_quote", "place_option_order", "mark_options"):
            assert banned not in text
        assert "live_trading_enabled" not in text


def test_confluence_needs_both_levels_and_fills_the_next_open():
    prep = _hold()
    both = _of(prep, "confluence")
    assert len(both) == 1
    item = both[0]
    assert item.anchor1 == 2 and item.anchor2 == 8
    assert item.y1 == 100.0 and item.y2 == 101.0
    assert item.shelf == 101.0
    assert item.signal_i == 11 and item.fill_i == 12
    assert prep.open[item.fill_i] == 102.2
    line_only = _hold()
    line_only.low = line_only.low.copy()
    line_only.low[11] = 101.4
    assert _of(line_only, "confluence") == []
    assert len(_of(line_only, "trendline")) == 1
    assert len(_of(line_only, "support")) == 0
    red = _hold()
    red.close = red.close.copy()
    red.close[11] = 100.5
    assert _of(red, "confluence") == []


def test_an_unconfirmed_swing_is_not_the_line_and_a_later_bar_does_not_move_the_signal():
    prep = _hold()
    before = [(item.signal_i, item.anchor2, item.shelf) for item in _of(prep, "confluence")]
    prep.low = prep.low.copy()
    prep.low[10] = 100.9
    assert _of(prep, "confluence") == []
    prep = _hold()
    prep.close = prep.close.copy()
    prep.close[13] = 1.0
    after = [(item.signal_i, item.anchor2, item.shelf) for item in _of(prep, "confluence")]
    assert before == after


def test_a_close_through_the_segment_invalidates_the_pair_and_a_downtrend_does_not_buy():
    broken = _hold()
    broken.close = broken.close.copy()
    broken.close[5] = 100.0
    assert _of(broken, "confluence") == []
    assert _of(broken, "trendline") == []
    down = _hold()
    down.ema9 = np.full(14, 99.0)
    assert _of(down, "confluence") == []


def test_the_target_fills_before_the_close_stop_and_a_flat_uses_the_1530_open():
    prep = _hold()
    item = _of(prep, "confluence")[0]
    prep.high = prep.high.copy()
    prep.low = prep.low.copy()
    prep.close = prep.close.copy()
    prep.vwap = np.full(14, 101.0)
    prep.std = np.ones(14)
    prep.high[12] = 103.5
    prep.close[12] = 100.0
    path = walk_bounce(prep, item, "band")
    assert path is not None and path["reason"] == "band" and path["exit_spot"] == 103.0
    gapped = _hold()
    held = _of(gapped, "confluence")[0]
    gapped.open = gapped.open.copy()
    gapped.vwap = np.full(14, 110.0)
    gapped.std = np.ones(14)
    gapped.open[13] = 100.5
    gap = walk_bounce(gapped, held, "band")
    assert gap is not None and gap["reason"] == "stop" and gap["exit_spot"] == 100.5
    skipped = _hold()
    held = _of(skipped, "confluence")[0]
    skipped.vwap = np.full(14, 90.0)
    skipped.std = np.ones(14)
    skipped.ema200 = np.full(14, 90.0)
    assert walk_bounce(skipped, held, "band") is None
    flat = _prep(3)
    stamps = pd.to_datetime(["2024-06-03 15:20", "2024-06-03 15:25", "2024-06-03 15:30"]).tz_localize(NY)
    flat.index = pd.DatetimeIndex(stamps)
    flat.dates = [stamp.date() for stamp in stamps]
    flat.times = [stamp.time() for stamp in stamps]
    flat.open = np.array([105.0, 105.0, 105.4])
    flat.high = np.array([105.2, 105.2, 105.5])
    flat.low = np.array([104.5, 104.6, 104.8])
    flat.close = np.array([105.0, 105.1, 105.2])
    flat.vwap = np.array([104.0, 104.0, 104.0])
    flat.std = np.ones(3)
    item = Bounce("SPY", "support", "long", -1, -1, 0, 1, float("nan"), float("nan"), 104.0)
    path = walk_bounce(flat, item, "band")
    assert path is not None and path["reason"] == "flat" and path["exit_spot"] == 105.4


def test_the_short_is_a_red_close_back_under_a_falling_line():
    high = np.array([98, 99, 100, 99, 98, 97, 98, 98.5, 99, 98, 97, 99.2, 96, 96], dtype=float)
    close = np.full(14, 96.0)
    close[11] = 98.0
    opened = np.full(14, 97.0)
    opened[11] = 99.0
    opened[12] = 97.8
    prep = _prep(
        high=high,
        close=close,
        open=opened,
        low=np.full(14, 95.0),
        ema9=np.full(14, 98.0),
        ema20=np.full(14, 100.0),
        vwap=np.full(14, 90.0),
    )
    found = _of(prep, "confluence", "short")
    assert len(found) == 1
    item = found[0]
    assert item.anchor1 == 2 and item.anchor2 == 8
    assert item.y1 == 100.0 and item.y2 == 99.0
    assert item.shelf == 99.0
    assert item.signal_i == 11 and item.fill_i == 12
    path = walk_bounce(prep, item, "band")
    assert path is not None and path["stop"] > path["fill"]


def test_one_position_skips_the_overlap():
    prep = _prep(6)
    prep.open = np.full(6, 100.0)
    prep.close = np.full(6, 101.0)
    first = {
        "direction": "long",
        "variant": "confluence",
        "fill": 100.0,
        "stop": 99.0,
        "reason": "band",
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
