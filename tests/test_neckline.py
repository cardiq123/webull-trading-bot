"""Synthetic checks for the frozen neckline rule. These tests do not score the holdout."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from webull_bot.chart_reads.neckline import (
    HOLDOUT_START,
    MAX_SEP_BARS,
    MAX_TRADES_PER_DAY,
    MIN_SEP_BARS,
    STAKE,
    STOP_PAD,
    SWING_WIDTH,
    TOL_ATR,
    TOL_PCT,
    TRAIN_END,
    TRAIN_START,
    Cell,
    Event,
    assert_window_visible,
    catalog,
    frozen_rules,
    n_trials,
    prepare,
    random_exit,
    select_events,
    simulate,
)

NY = "America/New_York"


def _frame(day: str, open_, high, low, close) -> pd.DataFrame:
    index = pd.date_range(f"{day} 09:30", periods=len(close), freq="5min", tz=NY)
    return pd.DataFrame(
        {
            "open": np.asarray(open_, dtype=float),
            "high": np.asarray(high, dtype=float),
            "low": np.asarray(low, dtype=float),
            "close": np.asarray(close, dtype=float),
            "volume": np.full(len(close), 1000.0),
        },
        index=index,
    )


def _double_bottom():
    """One session: two swing lows, a red pullback, then a neckline close."""
    n = 78
    mid = np.zeros(n)
    for i in range(23):
        mid[i] = 104.0 - (104.0 - 96.2) * i / 22
    for i in range(23, 33):
        mid[i] = mid[22] + (98.6 - mid[22]) * (i - 22) / 10
    for i in range(33, 43):
        mid[i] = mid[32] + (96.3 - mid[32]) * (i - 32) / 10
    for i in range(43, n):
        mid[i] = mid[42] + (103.0 - mid[42]) * (i - 42) / (n - 43)
    opened = mid.copy()
    closed = mid.copy()
    high = mid + 0.12
    low = mid - 0.12
    low[22] = 96.00
    low[42] = 96.05
    high[32] = 99.20
    opened[52] = mid[52] + 0.30
    closed[52] = mid[52] - 0.25
    opened[64] = mid[64] + 0.20
    closed[64] = mid[64] - 0.15
    high = np.maximum(high, np.maximum(opened, closed))
    low = np.minimum(low, np.minimum(opened, closed))
    low[22] = min(float(low[22]), 96.00)
    low[42] = min(float(low[42]), 96.05)
    return _frame("2020-06-15", opened, high, low, closed)


def _poke_without_both_emas():
    """A close through the neckline that is still under the 20 EMA, then a red bar."""
    n = 78
    opened = np.full(n, 100.0)
    closed = np.full(n, 100.0)
    high = np.full(n, 100.08)
    low = np.full(n, 99.92)
    for i in range(48, 70):
        opened[i] = closed[i] = 99.35
        high[i] = 99.44
        low[i] = 99.22
    opened[50] = 99.40
    closed[50] = 99.15
    high[50] = 99.40
    low[50] = 99.00
    for i in (48, 49, 51, 52):
        opened[i] = closed[i] = 99.40
        high[i] = 99.44
        low[i] = 99.25
    high[54] = 99.46
    opened[58] = 99.35
    closed[58] = 99.16
    high[58] = 99.40
    low[58] = 99.04
    for i in (56, 57, 59, 60):
        opened[i] = closed[i] = 99.36
        high[i] = 99.44
        low[i] = 99.22
    opened[61] = 99.28
    closed[61] = 99.40
    high[61] = 99.44
    low[61] = 99.22
    opened[63] = 99.36
    closed[63] = 99.470
    high[63] = 99.48
    low[63] = 99.30
    opened[65] = 99.50
    closed[65] = 99.43
    high[65] = 99.50
    low[65] = 99.28
    for i in range(70, n):
        opened[i] = closed[i] = 101.0
        high[i] = 101.1
        low[i] = 100.85
    return _frame("2020-06-17", opened, high, low, closed)


def test_catalog_counts_the_scalp_in_the_family():
    cells = catalog()
    assert n_trials() == 68
    assert len(cells) == 68
    assert len({cell.id for cell in cells}) == 68
    scalps = [cell for cell in cells if cell.family == "scalp"]
    assert len(scalps) == 8
    assert {cell.exit for cell in scalps} == {"neckline", "r2"}
    assert all(cell.filter == "scalp" for cell in scalps)
    rules = frozen_rules()
    assert rules["n_trials"] == 68
    assert "before any close above the neckline" in rules["scalp"]
    assert "fall back to 1R" in rules["random"]
    assert TOL_PCT == 0.0015
    assert TOL_ATR == 0.5
    assert MIN_SEP_BARS == 6
    assert MAX_SEP_BARS == 30
    assert SWING_WIDTH == 2
    assert MAX_TRADES_PER_DAY == 3
    assert STAKE == 2500.0
    assert TRAIN_START == date(2017, 2, 16)
    assert TRAIN_END == date(2023, 12, 31)
    assert HOLDOUT_START == date(2024, 1, 1)


def test_random_exit_uses_one_r_when_the_bar_has_no_neckline():
    assert random_exit("r1") == "r1"
    assert random_exit("r2") == "r2"
    assert random_exit("vwap2") == "vwap2"
    assert random_exit("neckline") == "r1"
    assert random_exit("measured") == "r1"


def test_holdout_stays_closed_until_the_score():
    with pytest.raises(RuntimeError, match="holdout"):
        assert_window_visible(HOLDOUT_START, allow_holdout=False)


def test_confirmed_entry_is_the_next_open_after_the_swing_is_known():
    frame = _double_bottom()
    book = prepare(frame, "SPY")
    confirmed = [event for event in book.events if event.family == "confirmed" and event.direction == "long"]
    assert len(confirmed) == 1
    event = confirmed[0]
    assert book.index[event.signal_i].strftime("%H:%M") == "14:20"
    assert book.index[event.fill_i].strftime("%H:%M") == "14:25"
    assert event.signal_i >= 42 + SWING_WIDTH
    assert event.stop == pytest.approx(96.05 - STOP_PAD)
    assert event.neckline == pytest.approx(99.20)
    cell = Cell("SPY", "confirmed", "base", "r1", "shares")
    picked = select_events(book.events, cell)
    assert picked == confirmed


def test_scalp_buys_the_red_pullback_and_stops_under_that_low():
    frame = _double_bottom()
    book = prepare(frame, "SPY")
    scalps = [event for event in book.events if event.family == "scalp"]
    assert len(scalps) == 1
    event = scalps[0]
    assert event.direction == "long"
    assert book.index[event.signal_i].strftime("%H:%M") == "13:50"
    assert book.index[event.fill_i].strftime("%H:%M") == "13:55"
    assert event.signal_i >= 42 + SWING_WIDTH
    assert event.stop == pytest.approx(float(book.low[event.signal_i]) - STOP_PAD)
    assert float(book.close[event.signal_i]) < float(book.open[event.signal_i])
    assert event.stop < float(book.low[event.signal_i])
    confirmed = next(item for item in book.events if item.family == "confirmed")
    assert event.signal_i < confirmed.signal_i
    iv = {book.dates[0]: (16.0, "VIX")}
    neck = simulate(
        book,
        select_events(book.events, Cell("SPY", "scalp", "scalp", "neckline", "shares")),
        exit_name="neckline",
        kind="shares",
        stake=STAKE,
        iv_points=iv,
        start=book.dates[0],
        end=book.dates[0],
        allow_holdout=False,
    )
    assert len(neck["trades"]) == 1
    trade = neck["trades"][0]
    assert trade["reason"] == "target"
    assert trade["target"] == pytest.approx(99.20)
    assert trade["stop"] == pytest.approx(event.stop)
    two_r = simulate(
        book,
        select_events(book.events, Cell("SPY", "scalp", "scalp", "r2", "shares")),
        exit_name="r2",
        kind="shares",
        stake=STAKE,
        iv_points=iv,
        start=book.dates[0],
        end=book.dates[0],
        allow_holdout=False,
    )
    assert two_r["trades"][0]["planned_rr"] == pytest.approx(2.0)
    assert two_r["trades"][0]["target"] != pytest.approx(99.20)


def test_a_neckline_close_without_both_emas_blocks_a_later_scalp():
    frame = _poke_without_both_emas()
    book = prepare(frame, "SPY")
    poke = 63
    assert float(book.close[poke]) > 99.46
    assert float(book.close[poke]) > float(book.ema9[poke])
    assert float(book.close[poke]) < float(book.ema20[poke])
    assert not any(event.family == "scalp" for event in book.events)
    assert all(event.signal_i != poke for event in book.events)
    assert all(event.signal_i != 65 for event in book.events)
    assert any(event.family == "confirmed" and event.signal_i > poke for event in book.events)


def test_the_short_mirror_is_the_flipped_double_bottom():
    frame = _double_bottom()
    flipped = frame.copy()
    flipped["open"] = 200.0 - frame["open"]
    flipped["close"] = 200.0 - frame["close"]
    flipped["high"] = 200.0 - frame["low"]
    flipped["low"] = 200.0 - frame["high"]
    book = prepare(flipped, "SPY")
    shorts = select_events(book.events, Cell("SPY", "confirmed", "short", "r1", "shares"))
    assert shorts
    assert all(event.direction == "short" for event in shorts)
    assert shorts[0].stop == pytest.approx(shorts[0].second + STOP_PAD)


def test_the_account_takes_at_most_three_trades_in_a_day():
    n = 78
    index = pd.date_range("2020-07-01 09:30", periods=n, freq="5min", tz=NY)
    close = np.full(n, 100.0)
    frame = pd.DataFrame(
        {
            "open": close,
            "high": close + 0.20,
            "low": np.full(n, 79.0),
            "close": close,
            "volume": np.full(n, 1000.0),
        },
        index=index,
    )
    book = prepare(frame, "SPY")
    events = []
    for signal in (10, 20, 30, 40):
        events.append(
            Event(
                symbol="SPY",
                direction="long",
                family="confirmed",
                signal_i=signal,
                fill_i=signal + 1,
                stop=80.0,
                neckline=101.0,
                extreme=79.0,
                second=80.0,
                above_vwap=True,
                above_ema200=True,
                macd_pos=True,
            )
        )
    out = simulate(
        book,
        events,
        exit_name="r1",
        kind="shares",
        stake=STAKE,
        iv_points={},
        start=date(2020, 7, 1),
        end=date(2020, 7, 1),
        allow_holdout=False,
    )
    assert len(out["trades"]) == 3
    assert out["skips"]["cap"] == 1


def test_sources_do_not_touch_the_forward_books():
    root = Path("src/webull_bot/chart_reads")
    banned = (
        "forward_options",
        "forward_chop",
        "forward_vwap",
        "forward_trapdoor",
        "place_option_order",
        "live_trading_enabled",
        "option_quote",
    )
    for name in ("neckline.py", "research_neckline.py"):
        text = (root / name).read_text()
        for token in banned:
            assert token not in text
