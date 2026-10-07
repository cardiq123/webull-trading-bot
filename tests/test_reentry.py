"""Band-tag re-entry. No network and no broker."""

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from webull_bot.chart_reads.ema_reclaim import Prepared
from webull_bot.chart_reads.reentry import (
    Reentry,
    addons,
    find_reentries,
    frozen_rules,
    simulate,
    walk_reentry,
)

NY = "America/New_York"


def _prep(n: int = 9, **columns) -> Prepared:
    stamps = pd.date_range("2024-06-03 09:30", periods=n, freq="5min", tz=NY)
    zeros = np.zeros(n, dtype=float)

    def col(name: str, default: np.ndarray) -> np.ndarray:
        if name not in columns:
            return default
        return np.asarray(columns[name], dtype=float)

    close = col("close", np.full(n, 100.0))
    return Prepared(
        index=pd.DatetimeIndex(stamps),
        open=col("open", close.copy()),
        high=col("high", close + 0.2),
        low=col("low", close - 0.2),
        close=close,
        volume=col("volume", np.full(n, 1000.0)),
        ema9=col("ema9", np.full(n, 100.0)),
        ema20=col("ema20", np.full(n, 100.0)),
        ema200=col("ema200", np.full(n, 110.0)),
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


def _long_day() -> Prepared:
    # Bar 4 tags the upper band and closes above it. Bar 5 is the red rejection.
    # Bar 6 tests the 20 EMA and closes back above it, green. Bar 7 is the fill.
    return _prep(
        open=[100, 100, 100, 100, 101.0, 101.8, 100.70, 101.2, 101.0],
        high=[100, 100, 100, 100, 103.0, 101.9, 101.20, 101.4, 101.0],
        low=[99, 99, 99, 99, 100.8, 101.2, 100.55, 100.9, 100.8],
        close=[100, 100, 100, 100, 102.5, 101.5, 101.00, 101.1, 101.0],
        ema20=np.full(9, 100.5),
        atr=np.ones(9),
        vwap=np.full(9, 100.0),
        std=np.ones(9),
    )


def _only(prep: Prepared, variant: str, direction: str = "long") -> list[Reentry]:
    return [item for item in find_reentries(prep, "SPY") if item.variant == variant and item.direction == direction]


def test_rules_are_frozen_and_the_sources_stay_off_the_live_path():
    rules = frozen_rules()
    assert "positive" in rules["tag"]
    assert "0.10 ATR" in rules["pullback"]
    assert "does not need a position" in rules["standalone"]
    assert "same bar" in rules["addon"]
    assert "missing 20 EMA test is left missing" in rules["chart_day"]
    assert "Not a live strategy" in rules["not_live"]
    root = Path("src/webull_bot/chart_reads")
    for name in ("reentry.py", "research_reentry.py"):
        text = (root / name).read_text()
        for banned in ("forward_options", "forward_chop", "option_quote", "place_option_order", "mark_options"):
            assert banned not in text
        assert "live_trading_enabled" not in text


def test_green_hold_fills_the_next_open_and_a_red_hold_is_the_looser_variant():
    prep = _long_day()
    green = _only(prep, "green")
    assert len(green) == 1
    assert green[0].tag_i == 4
    assert green[0].reject_i == 5
    assert green[0].signal_i == 6
    assert green[0].fill_i == 7
    hold = _only(prep, "hold")
    assert [item.signal_i for item in hold] == [6]
    red = _long_day()
    red.open[6] = 101.2
    red.close[6] = 101.0
    assert _only(red, "green") == []
    assert [item.signal_i for item in _only(red, "hold")] == [6]
    missed = _long_day()
    missed.close[6] = 100.2
    assert _only(missed, "hold") == []


def test_a_later_bar_does_not_change_the_signal_or_the_exit():
    prep = _long_day()
    before = [(item.tag_i, item.reject_i, item.signal_i, item.fill_i) for item in _only(prep, "green")]
    prep.close = prep.close.copy()
    prep.close[8] = 50.0
    prep.high = prep.high.copy()
    prep.high[8] = 80.0
    after = [(item.tag_i, item.reject_i, item.signal_i, item.fill_i) for item in _only(prep, "green")]
    assert before == after
    # Bar 8 is still inside the trade. A close through the 20 EMA is the stop.
    # Rewriting that bar's band so it is not beyond the fill leaves the stop in place.
    path = walk_reentry(prep, _only(prep, "green")[0], "band", "ema20")
    prep.high[8] = 200.0
    prep.vwap = prep.vwap.copy()
    prep.vwap[8] = 1.0
    again = walk_reentry(prep, _only(prep, "green")[0], "band", "ema20")
    assert path is not None and again is not None
    assert path["reason"] == again["reason"] == "stop"
    assert path["exit_spot"] == again["exit_spot"] == 50.0


def test_the_band_fills_before_a_close_through_the_20_and_the_stop_fills_at_the_close():
    prep = _long_day()
    item = _only(prep, "green")[0]
    tagged = _long_day()
    tagged.high = tagged.high.copy()
    tagged.close = tagged.close.copy()
    tagged.high[7] = 104.0
    tagged.close[7] = 99.0
    tagged.ema20 = tagged.ema20.copy()
    tagged.ema20[7] = 100.2
    hit = walk_reentry(tagged, item, "band", "ema20")
    assert hit is not None and hit["reason"] == "band" and hit["exit_spot"] == 102.0
    stopped = _long_day()
    stopped.close = stopped.close.copy()
    stopped.close[7] = 100.0
    stopped.ema20 = np.full(9, 100.4)
    # The hold bar still has to close above its own 20 EMA. Keep bar 6 valid.
    stopped.ema20[6] = 100.5
    stopped.low = stopped.low.copy()
    stopped.low[6] = 100.55
    item = _only(stopped, "green")[0]
    path = walk_reentry(stopped, item, "band", "ema20")
    assert path is not None and path["reason"] == "stop" and path["exit_spot"] == 100.0


def test_the_short_is_the_mirror_and_the_addon_needs_the_base_exit_bar():
    prep = _prep(
        open=[100, 100, 100, 100, 99.0, 98.2, 98.90, 98.6, 98.6],
        high=[100, 100, 100, 100, 99.2, 98.7, 98.95, 98.8, 98.8],
        low=[99, 99, 99, 99, 97.5, 98.1, 98.40, 98.4, 98.4],
        close=[100, 100, 100, 100, 98.4, 98.6, 98.70, 98.5, 98.5],
        ema20=np.array([99, 99, 99, 99, 99.0, 99.0, 99.00, 99.2, 99.2]),
    )
    shorts = _only(prep, "green", "short")
    assert len(shorts) == 1
    assert shorts[0].tag_i == 4 and shorts[0].reject_i == 5 and shorts[0].fill_i == 7
    path = walk_reentry(prep, shorts[0], "band", "ema20")
    assert path is not None and path["stop"] < path["fill"] or path["stop"] > path["fill"]
    assert path["stop"] > path["fill"]
    long = _only(_long_day(), "green")[0]
    day = _long_day().dates[long.tag_i]
    assert addons(_long_day(), [long], {(day, "long", _long_day().index[long.tag_i])}) == [long]
    assert addons(_long_day(), [long], set()) == []


def test_a_zero_width_open_is_not_a_tag_and_the_chart_marks_the_hold():
    from webull_bot.chart_reads.reentry import illustrate

    quiet = _long_day()
    quiet.std = np.zeros(9)
    assert _only(quiet, "green") == []
    marked = illustrate(_long_day(), date(2024, 6, 3))
    assert marked["steps"][0]["tag"] == 4
    assert marked["steps"][0]["reject"] == 5
    assert marked["steps"][0]["hold"] == 6
    assert marked["pending_tag"] is None


def test_the_share_book_is_long_only():
    prep = _long_day()
    book = simulate(prep, find_reentries(prep, "SPY"), target="band", stop_name="ema20", kind="shares", stake=1000.0, long_only=True, start=date(2024, 6, 3), end=date(2024, 6, 3))
    assert book["metrics"]["trades"] == 1
    assert book["trades"][0]["direction"] == "long"
