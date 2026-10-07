"""Each candlestick shape fires on a hand-built bar and stays quiet on a plain bar."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from webull_bot.chart_reads.candles import (
    CATALOG,
    CONTINUATION_LONG,
    CONTINUATION_SHORT,
    HOLDOUT_START,
    INDECISION,
    RANDOM_SEED,
    REVERSAL_LONG,
    REVERSAL_SHORT,
    SAMPLE_END,
    TRAIN_END,
    catalog_markdown,
    confirms,
    detect,
    draw_reference,
    forward_returns,
    pattern_ids,
)
from webull_bot.costs import CostModel
from webull_bot.chart_reads.ema_reject import HOLDOUT_START as EMA_HOLDOUT
from webull_bot.chart_reads.ema_reject import RANDOM_SEED as EMA_SEED
from webull_bot.chart_reads.ema_reject import SAMPLE_END as EMA_END
from webull_bot.chart_reads.ema_reject import TRAIN_END as EMA_TRAIN
from webull_bot.indicators import atr

BANNED = (
    "forward_options",
    "forward_chop",
    "option_quote",
    "place_option_order",
    "mark_options",
    "live_trading_enabled",
)


def _frame(n: int = 70, step: float = 0.0, start: float = 100.0) -> pd.DataFrame:
    index = pd.date_range("2024-06-03 09:30", periods=n, freq="5min", tz="America/New_York")
    price = start
    rows = []
    for _ in range(n):
        opened = price
        closed = price + 0.45
        high = closed + 0.25
        low = opened - 0.30
        rows.append((opened, high, low, closed, 1000.0))
        price += step
    return pd.DataFrame(rows, columns=["open", "high", "low", "close", "volume"], index=index)


def _put(frame: pd.DataFrame, offset: int, opened: float, high: float, low: float, closed: float) -> None:
    frame.iloc[offset, 0] = opened
    frame.iloc[offset, 1] = high
    frame.iloc[offset, 2] = low
    frame.iloc[offset, 3] = closed


def _anchor(frame: pd.DataFrame, span: int) -> float:
    return float(frame.iloc[-span - 1]["close"])


def _doji(frame: pd.DataFrame) -> None:
    base = _anchor(frame, 1)
    _put(frame, -1, base, base + 0.25, base - 0.20, base + 0.04)


def _long_legged(frame: pd.DataFrame) -> None:
    base = _anchor(frame, 1)
    _put(frame, -1, base, base + 0.55, base - 0.55, base + 0.03)


def _dragonfly(frame: pd.DataFrame) -> None:
    base = _anchor(frame, 1)
    _put(frame, -1, base, base + 0.05, base - 0.90, base + 0.03)


def _gravestone(frame: pd.DataFrame) -> None:
    base = _anchor(frame, 1)
    _put(frame, -1, base, base + 0.90, base - 0.04, base + 0.03)


def _hammer(frame: pd.DataFrame) -> None:
    base = _anchor(frame, 1)
    _put(frame, -1, base, base + 0.35, base - 1.00, base + 0.30)


def _inverted(frame: pd.DataFrame) -> None:
    base = _anchor(frame, 1)
    _put(frame, -1, base, base + 1.30, base - 0.05, base + 0.30)


def _spinning(frame: pd.DataFrame) -> None:
    base = _anchor(frame, 1)
    _put(frame, -1, base, base + 0.42, base - 0.22, base + 0.18)


def _maru_bull(frame: pd.DataFrame) -> None:
    base = _anchor(frame, 1)
    _put(frame, -1, base, base + 0.92, base - 0.02, base + 0.90)


def _maru_bear(frame: pd.DataFrame) -> None:
    base = _anchor(frame, 1)
    _put(frame, -1, base + 0.90, base + 0.92, base - 0.02, base)


def _engulf_bull(frame: pd.DataFrame) -> None:
    base = _anchor(frame, 2)
    _put(frame, -2, base + 0.10, base + 0.15, base - 0.50, base - 0.45)
    _put(frame, -1, base - 0.55, base + 0.30, base - 0.60, base + 0.25)


def _engulf_bear(frame: pd.DataFrame) -> None:
    base = _anchor(frame, 2)
    _put(frame, -2, base - 0.10, base + 0.50, base - 0.15, base + 0.45)
    _put(frame, -1, base + 0.55, base + 0.60, base - 0.30, base - 0.25)


def _harami_bull(frame: pd.DataFrame) -> None:
    base = _anchor(frame, 2)
    opened = base + 0.20
    closed = opened - 0.80
    _put(frame, -2, opened, opened + 0.04, closed - 0.04, closed)
    _put(frame, -1, closed + 0.20, opened - 0.18, closed + 0.16, opened - 0.20)


def _harami_bear(frame: pd.DataFrame) -> None:
    base = _anchor(frame, 2)
    opened = base - 0.20
    closed = opened + 0.80
    _put(frame, -2, opened, closed + 0.04, opened - 0.04, closed)
    _put(frame, -1, closed - 0.20, closed - 0.16, opened + 0.18, opened + 0.20)


def _harami_cross_bull(frame: pd.DataFrame) -> None:
    base = _anchor(frame, 2)
    opened = base + 0.20
    closed = opened - 0.80
    middle = (opened + closed) / 2.0
    _put(frame, -2, opened, opened + 0.04, closed - 0.04, closed)
    _put(frame, -1, middle, middle + 0.12, middle - 0.12, middle)


def _harami_cross_bear(frame: pd.DataFrame) -> None:
    base = _anchor(frame, 2)
    opened = base - 0.20
    closed = opened + 0.80
    middle = (opened + closed) / 2.0
    _put(frame, -2, opened, closed + 0.04, opened - 0.04, closed)
    _put(frame, -1, middle, middle + 0.12, middle - 0.12, middle)


def _piercing(frame: pd.DataFrame) -> None:
    base = _anchor(frame, 2)
    opened = base
    closed = opened - 0.80
    low = closed - 0.08
    midpoint = (opened + closed) / 2.0
    _put(frame, -2, opened, opened + 0.04, low, closed)
    second_open = low - 0.05
    second_close = midpoint + 0.08
    _put(frame, -1, second_open, second_close + 0.02, second_open - 0.02, second_close)


def _dark_cloud(frame: pd.DataFrame) -> None:
    base = _anchor(frame, 2)
    opened = base
    closed = opened + 0.80
    high = closed + 0.08
    midpoint = (opened + closed) / 2.0
    _put(frame, -2, opened, high, opened - 0.04, closed)
    second_open = high + 0.05
    second_close = midpoint - 0.08
    _put(frame, -1, second_open, second_open + 0.02, second_close - 0.02, second_close)


def _tweezer_bottom(frame: pd.DataFrame) -> None:
    base = _anchor(frame, 2)
    opened = base
    closed = opened - 0.45
    low = closed - 0.10
    _put(frame, -2, opened, opened + 0.04, low, closed)
    second_open = low + 0.40
    _put(frame, -1, second_open, second_open + 0.18, low, second_open + 0.16)


def _tweezer_top(frame: pd.DataFrame) -> None:
    base = _anchor(frame, 2)
    opened = base
    closed = opened + 0.45
    high = closed + 0.10
    _put(frame, -2, opened, high, opened - 0.04, closed)
    second_open = high - 0.40
    _put(frame, -1, second_open, high, second_open - 0.18, second_open - 0.16)


def _kicker_bull(frame: pd.DataFrame) -> None:
    base = _anchor(frame, 2)
    _put(frame, -2, base + 0.70, base + 0.72, base - 0.02, base)
    _put(frame, -1, base + 0.95, base + 1.70, base + 0.90, base + 1.65)


def _kicker_bear(frame: pd.DataFrame) -> None:
    base = _anchor(frame, 2)
    _put(frame, -2, base, base + 0.72, base - 0.02, base + 0.70)
    _put(frame, -1, base - 0.95, base - 0.90, base - 1.70, base - 1.65)


def _morning(frame: pd.DataFrame, doji: bool) -> None:
    base = _anchor(frame, 3)
    opened = base
    closed = opened - 0.75
    _put(frame, -3, opened, opened + 0.04, closed - 0.04, closed)
    if doji:
        middle = closed - 0.20
        _put(frame, -2, middle, closed - 0.05, middle - 0.12, middle)
        third_open = middle
    else:
        middle_close = closed - 0.25
        middle_open = middle_close + 0.12
        _put(frame, -2, middle_open, closed - 0.04, middle_close - 0.04, middle_close)
        third_open = middle_close
    midpoint = (opened + closed) / 2.0
    third_close = midpoint + 0.20
    _put(frame, -1, third_open, third_close + 0.03, third_open - 0.03, third_close)


def _evening(frame: pd.DataFrame, doji: bool) -> None:
    base = _anchor(frame, 3)
    opened = base
    closed = opened + 0.75
    _put(frame, -3, opened, closed + 0.04, opened - 0.04, closed)
    if doji:
        middle = closed + 0.20
        _put(frame, -2, middle, middle + 0.12, closed + 0.05, middle)
        third_open = middle
    else:
        middle_close = closed + 0.25
        middle_open = middle_close - 0.12
        _put(frame, -2, middle_open, middle_close + 0.04, closed + 0.04, middle_close)
        third_open = middle_close
    midpoint = (opened + closed) / 2.0
    third_close = midpoint - 0.20
    _put(frame, -1, third_open, third_open + 0.03, third_close - 0.03, third_close)


def _soldiers(frame: pd.DataFrame) -> None:
    base = _anchor(frame, 3)
    opened = base - 0.30
    closed = opened + 0.50
    _put(frame, -3, opened, closed + 0.05, opened - 0.04, closed)
    opened = opened + 0.20
    closed = closed + 0.25
    _put(frame, -2, opened, closed + 0.05, opened - 0.04, closed)
    opened = opened + 0.15
    closed = closed + 0.30
    _put(frame, -1, opened, closed + 0.05, opened - 0.04, closed)


def _crows(frame: pd.DataFrame) -> None:
    base = _anchor(frame, 3)
    opened = base + 0.30
    closed = opened - 0.50
    _put(frame, -3, opened, opened + 0.04, closed - 0.05, closed)
    opened = opened - 0.20
    closed = closed - 0.25
    _put(frame, -2, opened, opened + 0.04, closed - 0.05, closed)
    opened = opened - 0.15
    closed = closed - 0.30
    _put(frame, -1, opened, opened + 0.04, closed - 0.05, closed)


def _shift_last(frame: pd.DataFrame, count: int) -> None:
    """Move the last ``count`` edited bars one row earlier so a third bar can complete."""
    block = frame.iloc[-count:].copy()
    frame.iloc[-count - 1 : -1] = block.to_numpy()


def _inside_up(frame: pd.DataFrame) -> None:
    _harami_bull(frame)
    _shift_last(frame, 2)
    high = float(frame.iloc[-3]["high"])
    opened = float(frame.iloc[-2]["close"])
    closed = max(opened + 0.40, high + 0.15)
    _put(frame, -1, opened, closed + 0.03, opened - 0.03, closed)


def _inside_down(frame: pd.DataFrame) -> None:
    _harami_bear(frame)
    _shift_last(frame, 2)
    low = float(frame.iloc[-3]["low"])
    opened = float(frame.iloc[-2]["close"])
    closed = min(opened - 0.40, low - 0.15)
    _put(frame, -1, opened, opened + 0.03, closed - 0.03, closed)


def _outside_up(frame: pd.DataFrame) -> None:
    _engulf_bull(frame)
    _shift_last(frame, 2)
    opened = float(frame.iloc[-2]["close"]) - 0.10
    closed = float(frame.iloc[-2]["close"]) + 0.35
    _put(frame, -1, opened, closed + 0.03, opened - 0.03, closed)


def _outside_down(frame: pd.DataFrame) -> None:
    _engulf_bear(frame)
    _shift_last(frame, 2)
    opened = float(frame.iloc[-2]["close"]) + 0.10
    closed = float(frame.iloc[-2]["close"]) - 0.35
    _put(frame, -1, opened, opened + 0.03, closed - 0.03, closed)


def _abandoned_bull(frame: pd.DataFrame) -> None:
    base = _anchor(frame, 3)
    opened = base
    closed = opened - 0.80
    low = closed - 0.05
    _put(frame, -3, opened, opened + 0.03, low, closed)
    middle = low - 0.40
    _put(frame, -2, middle, middle + 0.12, middle - 0.12, middle)
    third_open = middle + 0.30
    third_close = max(third_open + 0.45, (opened + closed) / 2.0 + 0.20)
    _put(frame, -1, third_open, third_close + 0.03, third_open + 0.02, third_close)


def _abandoned_bear(frame: pd.DataFrame) -> None:
    base = _anchor(frame, 3)
    opened = base
    closed = opened + 0.80
    high = closed + 0.05
    _put(frame, -3, opened, high, opened - 0.03, closed)
    middle = high + 0.40
    _put(frame, -2, middle, middle + 0.12, middle - 0.12, middle)
    third_open = middle - 0.30
    third_close = min(third_open - 0.45, (opened + closed) / 2.0 - 0.20)
    _put(frame, -1, third_open, third_open - 0.02, third_close - 0.03, third_close)


def _rising(frame: pd.DataFrame) -> None:
    base = _anchor(frame, 5)
    opened = base
    closed = opened + 0.90
    high = closed + 0.08
    low = opened - 0.08
    _put(frame, -5, opened, high, low, closed)
    _put(frame, -4, closed - 0.05, closed - 0.02, closed - 0.22, closed - 0.18)
    _put(frame, -3, closed - 0.20, closed - 0.16, closed - 0.38, closed - 0.34)
    _put(frame, -2, closed - 0.30, closed - 0.26, low + 0.05, closed - 0.42)
    last_open = closed - 0.20
    last_close = closed + 0.20
    _put(frame, -1, last_open, last_close + 0.04, last_open - 0.04, last_close)


def _falling(frame: pd.DataFrame) -> None:
    base = _anchor(frame, 5)
    opened = base + 0.90
    closed = base
    high = opened + 0.08
    low = closed - 0.08
    _put(frame, -5, opened, high, low, closed)
    _put(frame, -4, closed + 0.08, closed + 0.30, closed + 0.05, closed + 0.25)
    _put(frame, -3, closed + 0.20, closed + 0.45, closed + 0.16, closed + 0.40)
    _put(frame, -2, closed + 0.28, closed + 0.40, closed + 0.22, closed + 0.32)
    last_open = closed + 0.25
    last_close = closed - 0.25
    _put(frame, -1, last_open, last_open + 0.04, last_close - 0.04, last_close)


def _tasuki_up(frame: pd.DataFrame) -> None:
    base = _anchor(frame, 3)
    _put(frame, -3, base, base + 0.62, base - 0.02, base + 0.60)
    second_open = base + 0.85
    second_close = second_open + 0.55
    _put(frame, -2, second_open, second_close + 0.02, second_open - 0.02, second_close)
    third_open = second_open + 0.20
    third_close = base + 0.70
    _put(frame, -1, third_open, third_open + 0.03, third_close - 0.03, third_close)


def _tasuki_down(frame: pd.DataFrame) -> None:
    base = _anchor(frame, 3)
    _put(frame, -3, base + 0.60, base + 0.62, base - 0.02, base)
    second_open = base - 0.25
    second_close = second_open - 0.55
    _put(frame, -2, second_open, second_open + 0.02, second_close - 0.02, second_close)
    third_open = second_open - 0.20
    third_close = base - 0.10
    _put(frame, -1, third_open, third_close + 0.03, third_open - 0.03, third_close)


BUILDERS = {
    "doji": (_doji, 0.0),
    "long_legged_doji": (_long_legged, 0.0),
    "dragonfly_doji": (_dragonfly, 0.0),
    "gravestone_doji": (_gravestone, 0.0),
    "hammer": (_hammer, 0.0),
    "hanging_man": (_hammer, 0.25),
    "inverted_hammer": (_inverted, 0.0),
    "shooting_star": (_inverted, 0.25),
    "spinning_top": (_spinning, 0.0),
    "marubozu_bull": (_maru_bull, 0.0),
    "marubozu_bear": (_maru_bear, 0.0),
    "bullish_engulfing": (_engulf_bull, 0.0),
    "bearish_engulfing": (_engulf_bear, 0.0),
    "bullish_harami": (_harami_bull, 0.0),
    "bearish_harami": (_harami_bear, 0.0),
    "bullish_harami_cross": (_harami_cross_bull, 0.0),
    "bearish_harami_cross": (_harami_cross_bear, 0.0),
    "piercing_line": (_piercing, 0.0),
    "dark_cloud_cover": (_dark_cloud, 0.0),
    "tweezer_bottom": (_tweezer_bottom, 0.0),
    "tweezer_top": (_tweezer_top, 0.0),
    "bullish_kicker": (_kicker_bull, 0.0),
    "bearish_kicker": (_kicker_bear, 0.0),
    "morning_star": (lambda frame: _morning(frame, False), 0.0),
    "evening_star": (lambda frame: _evening(frame, False), 0.0),
    "morning_doji_star": (lambda frame: _morning(frame, True), 0.0),
    "evening_doji_star": (lambda frame: _evening(frame, True), 0.0),
    "three_white_soldiers": (_soldiers, 0.0),
    "three_black_crows": (_crows, 0.0),
    "three_inside_up": (_inside_up, 0.0),
    "three_inside_down": (_inside_down, 0.0),
    "three_outside_up": (_outside_up, 0.0),
    "three_outside_down": (_outside_down, 0.0),
    "abandoned_baby_bull": (_abandoned_bull, 0.0),
    "abandoned_baby_bear": (_abandoned_bear, 0.0),
    "rising_three_methods": (_rising, 0.0),
    "falling_three_methods": (_falling, 0.0),
    "upside_tasuki_gap": (_tasuki_up, 0.0),
    "downside_tasuki_gap": (_tasuki_down, 0.0),
}


def _built(pid: str) -> pd.DataFrame:
    builder, step = BUILDERS[pid]
    frame = _frame(step=step)
    builder(frame)
    return frame


def test_every_pattern_id_has_a_builder():
    assert set(BUILDERS) == set(pattern_ids())
    assert len(pattern_ids()) == 39


def test_plain_bars_match_nothing():
    flags = detect(_frame())
    for pid in pattern_ids():
        assert not bool(flags[pid].iloc[-1]), pid


def test_each_pattern_fires():
    missed = []
    for pid in pattern_ids():
        frame = _built(pid)
        flags = detect(frame)
        if not bool(flags[pid].iloc[-1]):
            missed.append(f"{pid} atr={float(atr(frame).iloc[-1]):.3f}")
    assert not missed, missed


def test_hammer_without_an_uptrend_is_not_a_hanging_man():
    flags = detect(_built("hammer"))
    assert bool(flags["hammer"].iloc[-1])
    assert not bool(flags["hanging_man"].iloc[-1])
    assert not bool(flags["uptrend_1"].iloc[-1])


def test_hanging_man_is_the_hammer_shape_after_an_uptrend():
    flags = detect(_built("hanging_man"))
    assert bool(flags["hammer"].iloc[-1])
    assert bool(flags["hanging_man"].iloc[-1])
    assert bool(flags["uptrend_1"].iloc[-1])
    assert bool(flags["context_hanging_man"].iloc[-1]) == bool(flags["located_bear"].iloc[-1])


def test_shooting_star_needs_the_uptrend():
    quiet = detect(_built("inverted_hammer"))
    assert bool(quiet["inverted_hammer"].iloc[-1])
    assert not bool(quiet["shooting_star"].iloc[-1])
    starred = detect(_built("shooting_star"))
    assert bool(starred["shooting_star"].iloc[-1])
    assert bool(starred["inverted_hammer"].iloc[-1])


def test_downtrend_and_uptrend_flags():
    down = detect(_frame(step=-0.25))
    up = detect(_frame(step=0.25))
    flat = detect(_frame())
    assert bool(down["downtrend_1"].iloc[-1])
    assert not bool(down["uptrend_1"].iloc[-1])
    assert bool(up["uptrend_1"].iloc[-1])
    assert not bool(up["downtrend_1"].iloc[-1])
    assert not bool(flat["downtrend_1"].iloc[-1])
    assert not bool(flat["uptrend_1"].iloc[-1])


def test_at_vwap_when_the_bar_covers_the_session_price():
    flags = detect(_frame())
    assert bool(flags["at_vwap"].iloc[-1])
    assert bool(flags["located_bull"].iloc[-1])


def test_daily_bars_leave_vwap_false():
    index = pd.date_range("2020-01-02", periods=40, freq="B")
    price = 100.0
    rows = []
    for _ in range(40):
        rows.append((price, price + 0.70, price - 0.30, price + 0.45, 1000.0))
        price += 0.1
    frame = pd.DataFrame(rows, columns=["open", "high", "low", "close", "volume"], index=index)
    flags = detect(frame)
    assert not bool(flags["at_vwap"].any())
    assert not bool(flags["at_lower_band"].any())
    assert not bool(flags["at_upper_band"].any())
    assert bool(flags["at_ema9"].iloc[-1])


def test_context_requires_trend_and_location():
    frame = _frame(step=-0.25)
    _hammer(frame)
    flags = detect(frame)
    assert bool(flags["hammer"].iloc[-1])
    assert bool(flags["downtrend_1"].iloc[-1])
    assert bool(flags["context_hammer"].iloc[-1]) == bool(flags["located_bull"].iloc[-1])
    assert bool(flags["reversal_long"].iloc[-1])


def test_no_lookahead_when_the_last_bar_changes():
    frame = _frame()
    _hammer(frame)
    # The hammer completes on the second-to-last row. The last row stays a plain bar.
    hammer = frame.iloc[-1].copy()
    plain = _frame().iloc[-1]
    _put(frame, -2, hammer["open"], hammer["high"], hammer["low"], hammer["close"])
    _put(frame, -1, plain["open"], plain["high"], plain["low"], plain["close"])
    before = detect(frame)
    _put(frame, -1, 50.0, 80.0, 40.0, 70.0)
    after = detect(frame)
    pd.testing.assert_series_equal(before.iloc[-2], after.iloc[-2])


def test_sketches_match_the_span():
    for item in CATALOG:
        assert len(item.sketch) == item.span, item.id


def test_families_are_the_registered_split():
    assert REVERSAL_LONG == (
        "dragonfly_doji",
        "hammer",
        "inverted_hammer",
        "bullish_engulfing",
        "bullish_harami",
        "bullish_harami_cross",
        "piercing_line",
        "tweezer_bottom",
        "bullish_kicker",
        "morning_star",
        "morning_doji_star",
        "three_white_soldiers",
        "three_inside_up",
        "three_outside_up",
        "abandoned_baby_bull",
    )
    assert REVERSAL_SHORT == (
        "gravestone_doji",
        "hanging_man",
        "shooting_star",
        "bearish_engulfing",
        "bearish_harami",
        "bearish_harami_cross",
        "dark_cloud_cover",
        "tweezer_top",
        "bearish_kicker",
        "evening_star",
        "evening_doji_star",
        "three_black_crows",
        "three_inside_down",
        "three_outside_down",
        "abandoned_baby_bear",
    )
    assert CONTINUATION_LONG == ("marubozu_bull", "rising_three_methods", "upside_tasuki_gap")
    assert CONTINUATION_SHORT == ("marubozu_bear", "falling_three_methods", "downside_tasuki_gap")
    assert INDECISION == ("doji", "long_legged_doji", "spinning_top")


def test_dates_match_the_ema_study():
    assert HOLDOUT_START == EMA_HOLDOUT
    assert TRAIN_END == EMA_TRAIN
    assert SAMPLE_END == EMA_END
    assert RANDOM_SEED == EMA_SEED == 17


def test_doc_lists_every_pattern():
    text = Path("docs/CANDLESTICK_PATTERNS.md").read_text()
    assert text == catalog_markdown()
    for pid in pattern_ids():
        assert f"`{pid}`" in text


def test_confirms_uses_the_family_column():
    flags = detect(_built("bullish_engulfing"))
    assert bool(confirms(flags, "long", "reversal", False).iloc[-1])
    assert not bool(confirms(flags, "short", "reversal", False).iloc[-1])
    assert not bool(confirms(flags, "long", "continuation", False).iloc[-1])


def test_reference_sheet_writes(tmp_path):
    path = tmp_path / "candlestick_patterns.png"
    draw_reference(path)
    assert path.stat().st_size > 1000


def test_one_bar_return_matches_the_cost_model():
    frame = _frame(n=20)
    long_ret, short_ret = forward_returns(frame, 1, True)
    costs = CostModel()
    bump = costs.friction_bps / 10_000.0
    opened = float(frame.iloc[11]["open"])
    closed = float(frame.iloc[11]["close"])
    entry = opened * (1.0 + bump)
    exit_ = closed * (1.0 - bump)
    fee = exit_ * costs.sec_fee_per_dollar_sold + min(costs.finra_taf_per_share, costs.finra_taf_cap)
    assert long_ret[10] == (exit_ - entry - fee) / entry
    entry = opened * (1.0 - bump)
    exit_ = closed * (1.0 + bump)
    fee = entry * costs.sec_fee_per_dollar_sold + min(costs.finra_taf_per_share, costs.finra_taf_cap)
    assert short_ret[10] == (entry - exit_ - fee) / entry
    assert np.isnan(long_ret[-1])


def test_sources_do_not_touch_the_forward_test():
    root = Path("src/webull_bot/chart_reads")
    for name in ("candles.py", "research_candles.py"):
        text = (root / name).read_text()
        for banned in BANNED:
            assert banned not in text
