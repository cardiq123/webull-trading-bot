"""9 EMA wick continuation. No network and no broker."""

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from webull_bot.chart_reads.ema_reclaim import Prepared
from webull_bot.chart_reads.reentry import simulate, walk_reentry
from webull_bot.chart_reads.wick import find_wicks, frozen_rules

NY = "America/New_York"


def _prep(n: int = 8, **columns) -> Prepared:
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
        ema9=col("ema9", np.linspace(99.0, 100.4, n)),
        ema20=col("ema20", np.linspace(97.0, 98.4, n)),
        ema200=col("ema200", np.full(n, 90.0)),
        atr=col("atr", np.ones(n)),
        vwap=col("vwap", np.full(n, 96.0)),
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


def _only(prep: Prepared, variant: str, direction: str = "long"):
    return [item for item in find_wicks(prep, "SPY") if item.variant == variant and item.direction == direction]


def _long_wick() -> Prepared:
    # Bar 4 is a red wick into the 9 EMA. Bar 5 closes green above the 9. Bar 6 is the fill.
    return _prep(
        open=[101, 101, 101, 101, 102.0, 101.4, 101.6, 101.6],
        high=[101, 101, 101, 101, 102.1, 101.9, 101.8, 101.8],
        low=[100.8, 100.8, 100.8, 100.8, 100.4, 101.2, 101.4, 101.4],
        close=[101, 101, 101, 101, 101.5, 101.8, 101.7, 101.7],
        ema9=np.array([99.0, 99.4, 99.8, 100.1, 100.5, 100.6, 100.7, 100.8]),
        ema20=np.array([97.0, 97.3, 97.6, 97.9, 98.2, 98.4, 98.6, 98.8]),
    )


def test_rules_are_frozen_and_the_sources_stay_off_the_live_path():
    rules = frozen_rules()
    assert "1.5 times the body" in rules["filter"]
    assert "50% of the range" in rules["filter"]
    assert "0.10 ATR" in rules["wick"]
    assert "upper wick" in rules["wick"]
    assert "bullish stack" in rules["stack"]
    assert "not a substitute wick" in rules["chart_day"]
    assert "Not a live strategy" in rules["not_live"]
    root = Path("src/webull_bot/chart_reads")
    for name in ("wick.py", "research_wick.py"):
        text = (root / name).read_text()
        for banned in ("forward_options", "forward_chop", "option_quote", "place_option_order", "mark_options"):
            assert banned not in text
        assert "live_trading_enabled" not in text


def test_a_red_wick_waits_for_the_green_close_and_a_shallow_wick_is_the_other_book():
    prep = _long_wick()
    filtered = _only(prep, "filtered")
    assert len(filtered) == 1
    assert filtered[0].tag_i == 4
    assert filtered[0].signal_i == 5
    assert filtered[0].fill_i == 6
    shallow = _long_wick()
    shallow.open = shallow.open.copy()
    shallow.high = shallow.high.copy()
    shallow.low = shallow.low.copy()
    shallow.close = shallow.close.copy()
    shallow.open[4] = 102.0
    shallow.high[4] = 102.2
    shallow.low[4] = 100.55
    shallow.close[4] = 100.8
    assert _only(shallow, "filtered") == []
    plain = _only(shallow, "plain")
    assert len(plain) == 1 and plain[0].tag_i == 4 and plain[0].fill_i == 6


def test_a_green_wick_fills_the_next_open_and_a_close_through_the_9_cancels():
    prep = _long_wick()
    prep.open = prep.open.copy()
    prep.close = prep.close.copy()
    prep.open[4] = 100.9
    prep.close[4] = 101.2
    prep.high[4] = 101.25
    green = _only(prep, "filtered")
    assert len(green) == 1 and green[0].signal_i == 4 and green[0].fill_i == 5
    failed = _long_wick()
    failed.close = failed.close.copy()
    failed.close[5] = 100.0
    assert _only(failed, "filtered") == []


def test_a_later_bar_does_not_change_the_signal_and_the_9_ema_stop_fills_at_the_close():
    prep = _long_wick()
    before = [(item.tag_i, item.signal_i, item.fill_i) for item in _only(prep, "filtered")]
    prep.close = prep.close.copy()
    prep.close[7] = 50.0
    after = [(item.tag_i, item.signal_i, item.fill_i) for item in _only(prep, "filtered")]
    assert before == after
    item = _only(prep, "filtered")[0]
    path = walk_reentry(prep, item, "band", "ema9")
    assert path is not None and path["reason"] == "stop" and path["exit_spot"] == 50.0


def test_the_short_is_an_upper_wick_in_a_bearish_stack():
    prep = _prep(
        open=[99, 99, 99, 99, 98.0, 98.6, 98.4, 98.4],
        high=[100, 100, 100, 100, 99.6, 98.8, 98.6, 98.6],
        low=[99, 99, 99, 99, 97.9, 98.1, 98.2, 98.2],
        close=[99, 99, 99, 99, 98.5, 98.2, 98.3, 98.3],
        ema9=np.array([101.0, 100.6, 100.2, 99.9, 99.5, 99.4, 99.3, 99.2]),
        ema20=np.array([103.0, 102.7, 102.4, 102.1, 101.8, 101.6, 101.4, 101.2]),
        vwap=np.full(8, 104.0),
    )
    shorts = _only(prep, "filtered", "short")
    assert len(shorts) == 1
    assert shorts[0].tag_i == 4 and shorts[0].signal_i == 5 and shorts[0].fill_i == 6
    path = walk_reentry(prep, shorts[0], "band", "ema9")
    assert path is not None and path["stop"] > path["fill"]


def test_the_share_book_is_long_only():
    prep = _long_wick()
    book = simulate(
        prep, find_wicks(prep, "SPY"), target="band", stop_name="ema9", kind="shares",
        stake=1000.0, long_only=True, start=date(2024, 6, 3), end=date(2024, 6, 3),
    )
    assert book["metrics"]["trades"] == 1
    assert book["trades"][0]["direction"] == "long"
