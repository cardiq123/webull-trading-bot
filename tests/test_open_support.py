"""The open-versus-support grid stays frozen, causal, and out of the holdout."""

import inspect
from datetime import date

import numpy as np
import pandas as pd
import pytest

from webull_bot.chart_reads.open_support import (
    CATALOG,
    CATALOG_BY_ID,
    DAILY_CAP,
    DSR_MIN,
    FDR_Q,
    GATE_DRAWDOWN,
    GATE_MIN_TRADES,
    GATE_PF,
    GATE_SHARPE,
    GATE_SYMBOLS,
    HEADLINE_ID,
    HOLDOUT_END,
    HOLDOUT_START,
    TRAIN_END,
    TRAIN_START,
    Cell,
    DayView,
    assert_window_visible,
    build_views,
    feature_frame,
    make_signal,
    option_report,
    run_search,
    simulate,
    walk_exit,
)

ROOT_FILES = (
    "src/webull_bot/chart_reads/open_support.py",
    "src/webull_bot/chart_reads/research_open_support.py",
)
FORBIDDEN = (
    "forward_options",
    "forward_chop",
    "forward_vwap",
    "place_option_order",
    "live_trading_enabled",
    "option_quote",
)


def _view(
    symbol: str,
    session: date,
    *,
    first_open: float,
    first_close: float,
    entry: float,
    high: float,
    low: float,
    close: float,
    support: float = 99.0,
    resistance: float = 110.0,
    trend: str = "up",
    volume: float = 1.0,
    prior_close: float = 100.0,
    prior_vwap: float = 100.0,
    atr: float = 2.0,
    first_high: float | None = None,
    first_low: float | None = None,
    extra: list[tuple[float, float, float, float]] | None = None,
) -> DayView:
    bars = [(entry, high, low, close)]
    if extra:
        bars.extend(extra)
    return DayView(
        symbol=symbol,
        day=session,
        first_open=first_open,
        first_high=first_high if first_high is not None else max(first_open, first_close),
        first_low=first_low if first_low is not None else min(first_open, first_close),
        first_close=first_close,
        entry_open=entry,
        bars_open=np.array([row[0] for row in bars], dtype=float),
        bars_high=np.array([row[1] for row in bars], dtype=float),
        bars_low=np.array([row[2] for row in bars], dtype=float),
        bars_close=np.array([row[3] for row in bars], dtype=float),
        bar_minutes=np.array([9 * 60 + 35 + 5 * index for index in range(len(bars))], dtype=int),
        support={"prior_day": support, "swing3": support, "swing5": support, "swing10": support},
        resistance={"prior_day": resistance, "swing3": resistance, "swing5": resistance, "swing10": resistance},
        trend={"ema20": trend, "ema50": trend, "structure": trend},
        prior_close=prior_close,
        prior_vwap=prior_vwap,
        atr=atr,
        dollar_volume=volume,
    )


def _cell(**kwargs) -> Cell:
    base = dict(id="test", mode="both_support", level="prior_day", trend="ema20", stop="level", exit="eod", cap=3)
    base.update(kwargs)
    return Cell(**base)


def test_windows_catalog_and_gate_are_frozen():
    assert TRAIN_START < TRAIN_END < HOLDOUT_START <= HOLDOUT_END
    assert TRAIN_END == date(2026, 7, 6)
    assert HOLDOUT_START == date(2026, 7, 7)
    assert HOLDOUT_END == date(2026, 10, 6)
    assert GATE_MIN_TRADES == 80
    assert GATE_PF == 1.10
    assert GATE_SHARPE == 0.40
    assert GATE_DRAWDOWN == -0.30
    assert FDR_Q == 0.10
    assert DSR_MIN == 0.95
    assert DAILY_CAP == 3
    assert GATE_SYMBOLS == ("SPY", "QQQ")
    assert len(CATALOG) == 141
    assert len({cell.id for cell in CATALOG}) == 141
    assert HEADLINE_ID in CATALOG_BY_ID
    assert CATALOG_BY_ID["both_prior_day_ema20_level_r1_cap5"].cap == 5
    with pytest.raises(RuntimeError):
        assert_window_visible(HOLDOUT_START, allow_holdout=False)


def test_search_cannot_see_the_holdout_and_imports_stay_research_only():
    source = inspect.getsource(run_search)
    assert "score_holdout" not in source
    assert "HOLDOUT" not in source
    assert "allow_holdout=True" not in source
    for path in ROOT_FILES:
        text = open(path, encoding="utf-8").read()
        for name in FORBIDDEN:
            assert name not in text


def test_swing_and_prior_low_are_known_only_after_confirmation():
    lows = np.full(20, 10.0)
    highs = np.full(20, 12.0)
    closes = np.full(20, 11.0)
    lows[5] = 1.0
    frame = pd.DataFrame({"open": closes, "high": highs, "low": lows, "close": closes, "vwap": closes})
    features = feature_frame(frame)
    # Width 3 confirms on bar 8 and is usable at the open of bar 9.
    assert not np.isfinite(features["swing3_low"].iloc[8])
    assert features["swing3_low"].iloc[9] == pytest.approx(1.0)
    changed = frame.copy()
    changed.loc[19, "low"] = 0.1
    changed.loc[19, "close"] = 0.2
    later = feature_frame(changed)
    for column in ("prior_low", "swing3_low", "swing5_low", "trend_ema20", "trend_structure"):
        left = features[column].iloc[:-1]
        right = later[column].iloc[:-1]
        if str(column).startswith("trend"):
            assert list(left) == list(right)
        else:
            assert np.allclose(left.to_numpy(dtype=float), right.to_numpy(dtype=float), equal_nan=True)


def test_short_needs_a_down_close_below_support_and_long_is_the_mirror():
    cell = _cell()
    short = _view(
        "INTC",
        date(2024, 6, 3),
        first_open=98.0,
        first_close=97.0,
        entry=97.5,
        high=98.0,
        low=97.0,
        close=97.2,
        support=99.0,
        trend="down",
    )
    signal = make_signal(short, cell)
    assert signal is not None and signal["side"] == "short"
    green = _view(
        "INTC",
        date(2024, 6, 3),
        first_open=98.0,
        first_close=98.5,
        entry=98.4,
        high=99.0,
        low=97.5,
        close=98.4,
        support=99.0,
        trend="down",
    )
    assert make_signal(green, cell) is None
    reclaimed = _view(
        "INTC",
        date(2024, 6, 3),
        first_open=98.0,
        first_close=97.0,
        entry=99.2,
        high=100.0,
        low=99.0,
        close=99.5,
        support=99.0,
        trend="down",
    )
    assert make_signal(reclaimed, _cell(stop="level")) is None
    long = _view(
        "SPY",
        date(2024, 6, 3),
        first_open=100.0,
        first_close=101.0,
        entry=101.0,
        high=102.0,
        low=100.5,
        close=101.4,
        support=99.0,
        trend="up",
    )
    assert make_signal(long, cell)["side"] == "long"
    resistance = _cell(mode="long_resistance")
    assert make_signal(short, resistance) is None
    above = _view(
        "SPY",
        date(2024, 6, 3),
        first_open=111.0,
        first_close=112.0,
        entry=112.0,
        high=113.0,
        low=111.5,
        close=112.4,
        resistance=110.0,
        trend="up",
    )
    assert make_signal(above, resistance)["side"] == "long"


def test_stop_wins_when_both_are_touched_and_a_later_gap_fills_at_the_open():
    view = _view(
        "SPY",
        date(2024, 6, 3),
        first_open=100,
        first_close=101,
        entry=100,
        high=103,
        low=98,
        close=102,
        support=99,
        trend="up",
    )
    raw, reason, index = walk_exit(view, "long", 99, 102, True, None)
    assert (raw, reason, index) == (99, "stop", 0)
    gap = _view(
        "SPY",
        date(2024, 6, 3),
        first_open=100,
        first_close=101,
        entry=100,
        high=100.4,
        low=99.5,
        close=100.2,
        extra=[(98.0, 98.0, 97.0, 97.5)],
    )
    raw, reason, index = walk_exit(gap, "long", 99, 110, True, None)
    assert (raw, reason, index) == (98.0, "stop", 1)
    eod = _view(
        "SPY",
        date(2024, 6, 3),
        first_open=100,
        first_close=101,
        entry=100,
        high=100.4,
        low=99.6,
        close=100.2,
        extra=[(100.2, 100.5, 100.0, 100.4)],
    )
    raw, reason, _index = walk_exit(eod, "long", 99, None, True, None)
    assert raw == pytest.approx(100.4)
    assert reason == "eod"


def test_cap_keeps_the_three_most_liquid_names_and_whole_shares():
    session = date(2024, 6, 3)
    books = {
        symbol: [
            _view(
                symbol,
                session,
                first_open=21,
                first_close=22,
                entry=22,
                high=22.5,
                low=19,
                close=22.2,
                support=14,
                trend="up",
                volume=volume,
            )
        ]
        for symbol, volume in (("AAA", 4.0), ("BBB", 3.0), ("CCC", 2.0), ("DDD", 1.0))
    }
    book = simulate(books, _cell(cap=3), session, session, 1000.0)
    assert [row["symbol"] for row in book["trades"]] == ["AAA", "BBB", "CCC"]
    assert all(row["qty"] == 1 for row in book["trades"])
    expensive = {
        "SPY": [
            _view(
                "SPY",
                session,
                first_open=601,
                first_close=602,
                entry=600,
                high=601,
                low=599,
                close=600.5,
                support=598,
                trend="up",
                volume=5,
            )
        ],
        "QQQ": [
            _view(
                "QQQ",
                session,
                first_open=601,
                first_close=602,
                entry=600,
                high=601,
                low=599,
                close=600.5,
                support=598,
                trend="up",
                volume=4,
            )
        ],
    }
    sized = simulate(expensive, _cell(), session, session, 1000.0)
    assert len(sized["trades"]) == 1
    assert sized["trades"][0]["qty"] == 1
    assert sized["trades"][0]["symbol"] == "SPY"


def test_same_day_credit_does_not_fund_the_same_open():
    session = date(2024, 6, 3)
    books = {
        "SPY": [
            _view(
                "SPY",
                session,
                first_open=101,
                first_close=102,
                entry=100,
                high=101,
                low=99.5,
                close=100.5,
                support=99,
                trend="up",
                volume=5,
            )
        ],
        "QQQ": [
            _view(
                "QQQ",
                session,
                first_open=101,
                first_close=102,
                entry=100,
                high=101,
                low=99.5,
                close=100.5,
                support=99,
                trend="up",
                volume=4,
            )
        ],
    }
    book = simulate(books, _cell(), session, session, 150.0)
    assert [row["symbol"] for row in book["trades"]] == ["SPY"]


def test_option_report_buys_one_contract():
    trade = {
        "day": date(2024, 6, 4),
        "side": "long",
        "fill": 100.0,
        "exit": 101.0,
        "entry_minute": 9 * 60 + 35,
        "exit_minute": 10 * 60,
    }
    short = dict(trade, side="short", exit=99.0)
    vix = {date(2024, 6, 3): 20.0}
    call = option_report([trade], vix, 1000.0, 0)
    put = option_report([short], vix, 1000.0, 7)
    assert call["trades"] == 1
    assert put["trades"] == 1
    assert call["ending"] != 1000.0


def test_empty_search_counts_every_cell_and_passes_none():
    result = run_search({})
    assert result["n_combos"] == 141
    assert result["survivor_ids"] == []
    assert all(row["q"] is not None for row in result["cells"])
