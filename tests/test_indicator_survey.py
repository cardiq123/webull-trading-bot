"""The indicator survey grid stays frozen, causal, and out of the holdout."""

import inspect
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from webull_bot.chart_reads.indicator_survey import (
    CATALOG,
    CATALOG_BY_ID,
    DAILY_CAP,
    DSR_MIN,
    FDR_Q,
    GATE_DRAWDOWN,
    GATE_PF,
    GATE_SHARPE,
    HOLDOUT_END,
    HOLDOUT_START,
    LIQUID_GROWTH,
    LIQUID_TECH,
    MAG7,
    PRIOR_END,
    PRIOR_MIN_TRADES,
    PRIOR_START,
    SELECT_END,
    SELECT_MIN_TRADES,
    SELECT_START,
    UNIVERSE,
    Prepared,
    Trade,
    assert_window_visible,
    behavior_key,
    exit_params,
    is_pre_holiday,
    option_report,
    pick_near_misses,
    plan_round3,
    prepare,
    run_search,
    simulate,
    walk,
)

ROOT = Path(__file__).resolve().parents[1]
SURVEY = ROOT / "src" / "webull_bot" / "chart_reads" / "indicator_survey.py"
FORBIDDEN = (
    "forward_options",
    "forward_chop",
    "forward_vwap",
    "place_option_order",
    "live_trading_enabled",
    "option_quote",
)


def test_windows_and_gates_are_frozen():
    assert PRIOR_START < PRIOR_END < SELECT_START < SELECT_END < HOLDOUT_START <= HOLDOUT_END
    assert SELECT_END == date(2026, 7, 6)
    assert HOLDOUT_START == date(2026, 7, 7)
    assert HOLDOUT_END == date(2026, 10, 6)
    assert GATE_PF == 1.10
    assert GATE_SHARPE == 0.40
    assert GATE_DRAWDOWN == -0.30
    assert SELECT_MIN_TRADES == 20
    assert PRIOR_MIN_TRADES == 80
    assert FDR_Q == 0.10
    assert DSR_MIN == 0.95
    assert DAILY_CAP == 3
    with pytest.raises(RuntimeError):
        assert_window_visible(HOLDOUT_START, allow_holdout=False)


def test_universe_was_frozen_before_scoring():
    assert LIQUID_GROWTH == ("PLTR", "MSTR", "HOOD")
    assert LIQUID_TECH == ("MU", "AMD", "AVGO")
    assert "GOOGL" in MAG7 and "GOOG" not in UNIVERSE
    assert set(LIQUID_GROWTH).isdisjoint(MAG7)
    assert set(LIQUID_TECH).isdisjoint(MAG7)
    assert UNIVERSE[0] == "SPY"
    assert len(UNIVERSE) == 14


def test_catalog_is_the_frozen_grid():
    ids = [rule.id for rule in CATALOG]
    assert len(ids) == len(set(ids)) == 63
    assert not any(rule.timeframe == "15m" for rule in CATALOG)
    hourly = [rule for rule in CATALOG if rule.timeframe == "60m"]
    assert [rule.id for rule in hourly] == ["h_ema9_20", "h_session_vwap", "h_orb", "h_1030"]
    assert all(not rule.prior_years_complete for rule in hourly)
    assert {rule.id for rule in CATALOG if rule.short} == {"double_top", "head_shoulders"}
    for month in range(1, 13):
        assert f"month_{month}" in CATALOG_BY_ID
    for name in ("dow_mon", "dow_tue", "dow_wed", "dow_thu", "dow_fri", "tom", "pre_holiday", "opex"):
        assert CATALOG_BY_ID[name].exit_style == "seasonality"
    for name in ("bb_reentry", "rsi2_200", "vwap20_reclaim", "bb_rsi2"):
        assert CATALOG_BY_ID[name].exit_style == "mean_reversion"
    sma = {rule.id for rule in CATALOG if rule.requires_sma200}
    assert sma == {
        "adx_200",
        "sma200_pullback",
        "rsi2_200",
        "sma200_break",
        "sma200_rel_candle",
        "cup_sma200",
        "macd_sma200",
        "tom_sma200",
    }


def test_exit_variants_follow_the_round_plan():
    trend = exit_params(CATALOG_BY_ID["ema9_20"], ())
    assert (trend.target, trend.time_bars, trend.stop_atr, trend.cap) == ("r2", 15, 1.0, 3)
    assert exit_params(CATALOG_BY_ID["ema9_20"], ("exit",)).target == "r1"
    mean = exit_params(CATALOG_BY_ID["bb_reentry"], ())
    assert (mean.target, mean.time_bars, mean.stop_from) == ("sma20", 5, "fill")
    assert exit_params(CATALOG_BY_ID["bb_reentry"], ("exit",)).time_bars == 3
    assert exit_params(CATALOG_BY_ID["tom"], ()).target == "none"
    assert exit_params(CATALOG_BY_ID["tom"], ("exit",)).target == "r1"
    assert exit_params(CATALOG_BY_ID["adx_200"], ("half_stop",)).stop_atr == 0.5
    assert exit_params(CATALOG_BY_ID["ema9_20"], ("spy",)).universe == "spy"
    assert exit_params(CATALOG_BY_ID["ema9_20"], ("cap5",)).cap == 5
    # Stacking an SMA filter onto a rule that already requires it is not a new behavior.
    assert behavior_key(CATALOG_BY_ID["adx_200"], ("exit", "sma200")) == behavior_key(CATALOG_BY_ID["adx_200"], ("exit",))


def test_pre_holiday_ignores_a_plain_weekend():
    assert is_pre_holiday(date(2026, 7, 2)) is True
    assert is_pre_holiday(date(2026, 7, 6)) is False
    assert is_pre_holiday(date(2026, 7, 10)) is False


def test_search_source_cannot_score_the_holdout():
    source = inspect.getsource(run_search)
    assert "score_holdout" not in source
    assert "HOLDOUT" not in source
    assert "allow_holdout=True" not in source
    text = SURVEY.read_text()
    research = (ROOT / "src" / "webull_bot" / "chart_reads" / "research_indicator_survey.py").read_text()
    for name in FORBIDDEN:
        assert name not in text
        assert name not in research


def _frame(seed=17, rows=320):
    rng = np.random.default_rng(seed)
    close = 100.0 * np.exp(np.cumsum(rng.normal(0.0002, 0.012, rows)))
    noise = rng.uniform(0.002, 0.015, rows)
    high = close * (1.0 + noise)
    low = close * (1.0 - noise)
    open_ = np.r_[close[0], close[:-1]]
    volume = rng.integers(1_000_000, 5_000_000, rows).astype(float)
    index = pd.bdate_range("2018-01-02", periods=rows)
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": volume}, index=index)


def test_masks_do_not_use_the_next_bar():
    frame = _frame()
    original = prepare(frame, "SPY")
    changed = frame.copy()
    changed.iloc[-1, changed.columns.get_loc("open")] *= 1.4
    changed.iloc[-1, changed.columns.get_loc("high")] *= 1.8
    changed.iloc[-1, changed.columns.get_loc("low")] *= 0.5
    changed.iloc[-1, changed.columns.get_loc("close")] *= 0.55
    changed.iloc[-1, changed.columns.get_loc("volume")] *= 8
    mutated = prepare(changed, "SPY")
    for name, mask in original.masks.items():
        assert np.array_equal(mask[:-1], mutated.masks[name][:-1]), name
    for name, exits in original.season_exit.items():
        assert np.array_equal(exits[:-1], mutated.season_exit[name][:-1]), name


def _hand(mask_at, open_, high, low, close, atr, end_dates=None):
    dates = [date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 4), date(2024, 1, 5), date(2024, 1, 8), date(2024, 1, 9)]
    n = len(dates)
    mask = np.zeros(n, dtype=bool)
    mask[mask_at] = True
    return Prepared(
        symbol="SPY",
        timeframe="1d",
        dates=dates,
        session_dates=list(dates),
        date_last={day: i for i, day in enumerate(dates)},
        open=np.array(open_, dtype=float),
        high=np.array(high, dtype=float),
        low=np.array(low, dtype=float),
        close=np.array(close, dtype=float),
        volume=np.full(n, 1_000_000.0),
        atr=np.array(atr, dtype=float),
        sma20=np.full(n, 11.0),
        sma200=np.full(n, 9.0),
        dollar_vol=np.full(n, 1e9),
        minutes=np.zeros(n, dtype=int),
        masks={"ema9_20": mask, "double_top": np.ones(n, dtype=bool)},
        season_exit={},
    )


def test_stop_wins_when_the_bar_can_reach_both_and_a_gap_fills_at_the_open():
    prep = _hand(1, [10, 10, 10, 10, 10, 10], [10, 10, 13, 10, 10, 10], [10, 10, 8, 10, 10, 10], [10, 10, 10, 10, 10, 10], [1, 1, 1, 1, 1, 1])
    params = exit_params(CATALOG_BY_ID["ema9_20"], ())
    trade = walk(prep, "ema9_20", params, date(2024, 1, 2), date(2024, 1, 9))[0]
    assert trade.reason == "stop"
    assert trade.exit_raw == pytest.approx(9.0)
    gapped = _hand(1, [10, 10, 10, 8, 10, 10], [10, 10, 10.5, 8, 10, 10], [10, 10, 9.5, 7, 10, 10], [10, 10, 10, 8, 10, 10], [1, 1, 1, 1, 1, 1])
    gap = walk(gapped, "ema9_20", params, date(2024, 1, 2), date(2024, 1, 9))[0]
    assert gap.reason == "stop"
    assert gap.exit_raw == pytest.approx(8.0)


def test_window_end_does_not_read_the_next_bar():
    prep = _hand(
        1,
        [10, 10, 10, 10, 10, 10],
        [10, 10, 11, 11, 11, 40],
        [10, 10, 9.5, 9.5, 9.5, 9.5],
        [10, 10, 10.2, 10.2, 10.5, 30],
        [1, 1, 1, 1, 1, 1],
    )
    params = exit_params(CATALOG_BY_ID["ema9_20"], ())
    clipped = walk(prep, "ema9_20", params, date(2024, 1, 2), date(2024, 1, 8))[0]
    assert clipped.reason == "window"
    assert clipped.exit_i == 4
    assert clipped.exit_raw == pytest.approx(10.5)
    full = walk(prep, "ema9_20", params, date(2024, 1, 2), date(2024, 1, 9))[0]
    assert full.reason == "target"
    assert full.exit_raw == pytest.approx(12.0)


def test_short_patterns_do_not_buy_shares():
    prep = _hand(1, [10] * 6, [11] * 6, [9] * 6, [10] * 6, [1] * 6)
    trades = walk(prep, "double_top", exit_params(CATALOG_BY_ID["double_top"], ()), date(2024, 1, 2), date(2024, 1, 9))
    assert trades == []


class _Mark:
    def __init__(self, days, close):
        self.session_dates = list(days)
        self.date_last = {day: i for i, day in enumerate(days)}
        self.close = np.array(close, dtype=float)


def _trade(symbol, priority, fill, stop, exit_raw, day, exit_day):
    return Trade(symbol, 0, 1, 2, day, exit_day, fill, exit_raw, stop, priority, "stop", True)


def test_cap_skips_a_name_that_does_not_fit_and_stops_at_three():
    day = date(2024, 1, 2)
    nxt = date(2024, 1, 3)
    later = date(2024, 1, 4)
    trades = [
        _trade("BIG", 100, 5000, 4900, 5000, day, nxt),
        _trade("A", 50, 10, 9, 11, day, nxt),
        _trade("B", 40, 10, 9, 11, day, nxt),
        _trade("C", 30, 10, 9, 11, day, nxt),
        _trade("D", 20, 10, 9, 11, day, nxt),
    ]
    preps = {symbol: _Mark([day, nxt, later], [10, 11, 11]) for symbol in ("BIG", "A", "B", "C", "D")}
    book = simulate(trades, preps, [day, nxt, later], 1000.0, 3)
    taken = [row["symbol"] for row in book["trades"]]
    assert taken == ["A", "B", "C"]
    assert all(isinstance(row["qty"], int) and row["qty"] >= 1 for row in book["trades"])


def test_whole_shares_and_next_day_settlement():
    day = date(2024, 1, 2)
    nxt = date(2024, 1, 3)
    trades = [_trade("SPY", 1, 600, 598, 600, day, nxt)]
    book = simulate(trades, {"SPY": _Mark([day, nxt], [600, 600])}, [day, nxt], 1000.0, 3)
    assert len(book["trades"]) == 1
    assert book["trades"][0]["qty"] == 1
    same = [_trade("SPY", 1, 100, 99, 99, day, day)]
    settled = simulate(same, {"SPY": _Mark([day, nxt], [100, 100])}, [day, nxt], 1000.0, 3)
    row = settled["trades"][0]
    assert isinstance(row["qty"], int) and row["qty"] >= 1
    # The sale is not spendable until the next session.
    assert settled["settled"][0] == pytest.approx(1000.0 - row["debit"])
    assert settled["settled"][0] < settled["equity"].iloc[0]
    assert settled["settled"][1] == pytest.approx(settled["equity"].iloc[0])


def test_near_misses_are_ranked_on_prior_sharpe_and_round_3_stacks_the_modal_variant():
    def cell(name, round_no, prior, selection_pf, trades, sharpe, dd, parent, variant, tokens, selection_pass=False, prior_pass=False, timeframe="1d"):
        rule = CATALOG_BY_ID[parent]
        return {
            "id": name,
            "rule_id": parent,
            "parent_id": parent,
            "round": round_no,
            "timeframe": timeframe,
            "variant": variant,
            "tokens": list(tokens),
            "behavior": list(behavior_key(rule, tokens)),
            "selection_pass": selection_pass,
            "prior_pass": prior_pass,
            "selection": {"trades": trades, "profit_factor": selection_pf, "sharpe": sharpe, "max_drawdown": dd},
            "prior": {"sharpe": prior},
        }

    passed = cell("passed", 1, 1.0, 1.4, 30, 0.8, -0.1, "ema9_20", "base", (), True, True)
    rich_selection = cell("rich", 1, -0.2, 1.3, 25, 1.2, -0.1, "sma50_200", "base", ())
    better_prior = cell("better", 1, 0.3, 1.05, 22, 0.1, -0.2, "donchian20", "base", ())
    weak = cell("weak", 1, 2.0, 0.4, 40, 0.5, -0.1, "macd_cross", "base", ())
    hourly = cell("h_ema9_20", 1, 3.0, 2.0, 40, 1.0, -0.05, "h_ema9_20", "base", (), timeframe="60m")
    picked = [row["id"] for row in pick_near_misses([passed, rich_selection, better_prior, weak, hourly])]
    assert picked == ["better", "rich"]
    parent = cell("ema9_20", 1, 0.1, 1.2, 20, 0.2, -0.1, "ema9_20", "base", ())
    spy = cell("ema9_20__spy", 2, 0.4, 1.1, 12, 0.2, -0.1, "ema9_20", "spy", ("spy",))
    exit_only = cell("ema9_20__exit", 2, 0.05, 1.2, 12, 0.2, -0.1, "ema9_20", "exit", ("exit",))
    assert plan_round3([parent, spy, exit_only]) == [("ema9_20", ("exit", "spy"))]
    exit_better = cell("ema9_20__exit", 2, 0.5, 1.2, 12, 0.2, -0.1, "ema9_20", "exit", ("exit",))
    assert plan_round3([parent, exit_better]) == []
    adx = cell("adx_200", 1, 0.1, 1.0, 20, 0.0, -0.2, "adx_200", "base", ())
    adx_exit = cell("adx_200__exit", 2, 0.0, 1.0, 10, 0.0, -0.2, "adx_200", "exit", ("exit",))
    redundant = cell("adx_200__sma200", 2, 0.4, 1.1, 10, 0.0, -0.2, "adx_200", "sma200", ("sma200",))
    assert plan_round3([adx, adx_exit, redundant]) == []


def test_option_report_prices_a_call_and_skips_zero_dte_on_a_multi_day_hold():
    days = [date(2024, 6, 3) + timedelta(days=i) for i in range(12)]
    close = np.linspace(100, 110, len(days))
    prep = Prepared(
        symbol="SPY",
        timeframe="1d",
        dates=days,
        session_dates=list(days),
        date_last={day: i for i, day in enumerate(days)},
        open=close.copy(),
        high=close + 1,
        low=close - 1,
        close=close,
        volume=np.full(len(days), 1e6),
        atr=np.ones(len(days)),
        sma20=close.copy(),
        sma200=close.copy(),
        dollar_vol=np.full(len(days), 1e9),
        minutes=np.zeros(len(days), dtype=int),
        masks={},
        season_exit={},
    )
    trades = [{"symbol": "SPY", "fill_date": "2024-06-03", "exit_date": "2024-06-10", "fill_raw": 100.0, "exit_raw": 108.0}]
    vix = {date(2024, 6, 2): 20.0}
    report = option_report(trades, {"SPY": prep}, vix, 1000.0)
    assert report["call_0"]["applicable"] is False
    assert report["call_7"]["trades"] == 1
    assert report["vertical_7"]["trades"] == 1
    assert np.isfinite(report["call_7"]["pnl"])
