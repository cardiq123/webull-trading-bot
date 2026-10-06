"""Five-contract scale-out. These tests do not score a book."""

from pathlib import Path

import pandas as pd
import pytest

from webull_bot.broker.paper import PaperBroker
from webull_bot.chart_reads.detect import Setup
from webull_bot.chart_reads.premium_scale import (
    ALL_OUT_TARGET,
    PREMIUM_STOPS,
    SCALE_CONTRACTS,
    SCALE_TIERS,
    apply_scale_bar,
    new_state,
    scale_grid,
    simulate_scale,
    underlying_exit_grid,
    underlying_stop_hit,
)
from webull_bot.chart_reads.simulate import simulate
from webull_bot.costs import CostModel
from webull_bot.execution.chart_exit import plan_option_scale, stage_on_paper
from webull_bot.options.fees import CONTRACT_MULTIPLIER, option_leg_fees

ZERO = CostModel(
    slippage_bps=0.0,
    half_spread_bps=0.0,
    sec_fee_per_dollar_sold=0.0,
    finra_taf_per_share=0.0,
)


def _state_quotes(**overrides):
    quotes = {
        "open_bid": 1.0,
        "adverse_bid": 1.0,
        "favorable_bid": 1.0,
        "close_bid": 1.0,
        "underlying_hit": False,
        "underlying_bid": 0.0,
    }
    quotes.update(overrides)
    return quotes


def test_ladder_is_frozen_before_any_score():
    assert SCALE_CONTRACTS == 5
    assert SCALE_TIERS == ((0.15, 2), (0.20, 1), (0.30, 1), (1.00, 1))
    assert sum(qty for _pct, qty in SCALE_TIERS) == 5
    assert PREMIUM_STOPS == (-0.20, -0.30, -0.50)
    assert ALL_OUT_TARGET == 0.30
    labels = [label for label, _spec in scale_grid()]
    assert labels[:4] == [
        "scale, premium stop -20%",
        "scale, premium stop -30%",
        "scale, premium stop -50%",
        "scale, underlying stop",
    ]
    assert "all-out +30%, premium stop -30%" in labels
    underlying = [label for label, _cell in underlying_exit_grid({"reward_r": 2.0})]
    assert underlying[0] == "bracket, next level"
    assert "trail 15%" in underlying
    assert "trail 2 ATR" in underlying
    assert "bracket 1.5R" in underlying
    assert "bracket 3R" in underlying
    assert all(cell["fixed_contracts"] == 5 for _label, cell in underlying_exit_grid({"reward_r": 2.0}))


def test_stop_wins_when_the_same_bar_also_reaches_a_target():
    state = new_state(1.0, "scale", "premium", -0.30)
    reason = apply_scale_bar(
        state,
        _state_quotes(open_bid=0.95, adverse_bid=0.60, favorable_bid=2.50),
        entry_bar=False,
        terminal=None,
    )
    assert reason == "initial_stop"
    assert state["targets_hit"] == 0
    assert state["remaining"] == 0
    assert state["runner"] == "initial_stop"
    fees = option_leg_fees(5, 0.60, sell=True)
    assert state["credit"] == pytest.approx(5 * 0.60 * CONTRACT_MULTIPLIER - fees)


def test_entry_bar_does_not_stop_on_the_spread_at_the_fill():
    state = new_state(1.0, "scale", "premium", -0.20)
    reason = apply_scale_bar(
        state,
        _state_quotes(open_bid=0.70, adverse_bid=0.90, favorable_bid=1.05),
        entry_bar=True,
        terminal=None,
    )
    assert reason is None
    assert state["remaining"] == 5
    assert state["targets_hit"] == 0


def test_first_target_arms_break_even_on_the_runner_only():
    state = new_state(1.0, "scale", "premium", -0.50)
    first = apply_scale_bar(
        state,
        _state_quotes(open_bid=1.0, adverse_bid=0.90, favorable_bid=1.18, close_bid=1.10),
        entry_bar=False,
        terminal=None,
    )
    assert first is None
    assert state["targets_hit"] == 1
    assert state["remaining"] == 3
    assert state["sold"]["0.15"] == 2
    assert state["armed"] is True
    assert state["stop_px"] == pytest.approx(0.50)
    assert state["runner_stop"] == pytest.approx(1.0)
    first_fees = option_leg_fees(2, 1.15, sell=True)
    assert state["credit"] == pytest.approx(2 * 1.15 * CONTRACT_MULTIPLIER - first_fees)
    second = apply_scale_bar(
        state,
        _state_quotes(open_bid=1.05, adverse_bid=0.97, favorable_bid=1.10),
        entry_bar=False,
        terminal=None,
    )
    assert second is None
    assert state["runner"] == "breakeven"
    assert state["runner_open"] == 0
    assert state["remaining"] == 2
    assert state["targets_hit"] == 1
    assert state["done"] is False
    runner_fees = option_leg_fees(1, 0.97, sell=True)
    assert state["credit"] == pytest.approx(
        2 * 1.15 * CONTRACT_MULTIPLIER - first_fees + 1 * 0.97 * CONTRACT_MULTIPLIER - runner_fees
    )
    third = apply_scale_bar(
        state,
        _state_quotes(open_bid=0.90, adverse_bid=0.40, favorable_bid=0.70),
        entry_bar=False,
        terminal=None,
    )
    assert third == "initial_stop"
    assert state["runner"] == "breakeven"
    assert state["remaining"] == 0
    fixed_fees = option_leg_fees(2, 0.40, sell=True)
    assert state["credit"] == pytest.approx(
        2 * 1.15 * CONTRACT_MULTIPLIER
        - first_fees
        + 1 * 0.97 * CONTRACT_MULTIPLIER
        - runner_fees
        + 2 * 0.40 * CONTRACT_MULTIPLIER
        - fixed_fees
    )


def test_a_rally_through_every_limit_sells_the_runner_at_double():
    state = new_state(1.0, "scale", "premium", -0.30)
    reason = apply_scale_bar(
        state,
        _state_quotes(favorable_bid=3.0, adverse_bid=0.90, open_bid=1.0),
        entry_bar=False,
        terminal=None,
    )
    assert reason == "target"
    assert state["targets_hit"] == 4
    assert state["runner"] == "target"
    assert state["sold"]["1.00"] == 1
    assert state["remaining"] == 0
    credit = 0.0
    for pct, qty in SCALE_TIERS:
        price = 1.0 * (1.0 + pct)
        credit += qty * price * CONTRACT_MULTIPLIER - option_leg_fees(qty, price, sell=True)
    assert state["credit"] == pytest.approx(credit)


def test_underlying_stop_is_the_setup_stop_until_the_first_target():
    assert underlying_stop_hit("long", 100, 101, 90, 95, True) == (True, 95)
    assert underlying_stop_hit("long", 94, 96, 93, 95, False) == (True, 94)
    assert underlying_stop_hit("short", 100, 110, 99, 105, True) == (True, 105)
    state = new_state(1.0, "scale", "underlying", None)
    reason = apply_scale_bar(
        state,
        _state_quotes(underlying_hit=True, underlying_bid=0.40, favorable_bid=2.0),
        entry_bar=False,
        terminal=None,
    )
    assert reason == "initial_stop"
    assert state["targets_hit"] == 0
    assert state["credit"] == pytest.approx(5 * 0.40 * CONTRACT_MULTIPLIER - option_leg_fees(5, 0.40, sell=True))


def test_all_out_sells_every_contract_at_thirty_percent():
    state = new_state(2.0, "all_out", "premium", -0.30)
    reason = apply_scale_bar(
        state,
        _state_quotes(open_bid=2.0, adverse_bid=1.8, favorable_bid=4.0),
        entry_bar=False,
        terminal=None,
    )
    assert reason == "target"
    assert state["runner"] == "all_out"
    assert state["targets_hit"] == 1
    assert state["remaining"] == 0
    price = 2.0 * 1.30
    assert state["credit"] == pytest.approx(5 * price * CONTRACT_MULTIPLIER - option_leg_fees(5, price, sell=True))


def _frame(rows):
    index = pd.bdate_range("2024-01-02", periods=len(rows))
    frame = pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=index)
    frame["volume"] = 1_000_000.0
    return frame


def _flat(n=40, price=100.0):
    return [(price, price, price, price) for _ in range(n)]


def _setup(frame, slot: int) -> Setup:
    return Setup(
        symbol="TEST",
        direction="long",
        kind="bounce",
        signal_time=frame.index[slot - 1],
        fill_time=frame.index[slot],
        anchor_time=frame.index[slot - 1],
        stop=50.0,
        atr=2.0,
        reference=120.0,
    )


def _params(**extra):
    chosen = {
        "reward_r": 1.0,
        "trail": "none",
        "flatten_eod": False,
        "max_hold_sessions": 10,
        "pdt_prospective": False,
        "risk_fraction": 1.0,
        "max_positions": 1,
        "account": "margin_pdt",
        "expression": "single",
        "delta": 0.45,
        "dte": 45,
        "iv_premium": 1.15,
        "spread_multiplier": 1.0,
        "band_std": 2.0,
        "target_mode": "r",
    }
    chosen.update(extra)
    return chosen


def test_fixed_contract_count_is_opt_in_and_the_default_path_stays_budget_sized():
    frame = _frame(_flat())
    setup = [_setup(frame, 30)]
    params = _params()
    budget = simulate(
        setup,
        {"TEST": frame},
        {"TEST": frame},
        params,
        starting_equity=1_000_000.0,
        costs=ZERO,
        session_filter=False,
    )
    assert int(budget.trades["quantity"].iloc[0]) > 5
    fixed = dict(params)
    fixed["fixed_contracts"] = 5
    five = simulate(
        setup,
        {"TEST": frame},
        {"TEST": frame},
        fixed,
        starting_equity=1_000_000.0,
        costs=ZERO,
        session_filter=False,
    )
    assert int(five.trades["quantity"].iloc[0]) == 5
    broke = simulate(
        setup,
        {"TEST": frame},
        {"TEST": frame},
        fixed,
        starting_equity=1.0,
        costs=ZERO,
        session_filter=False,
    )
    assert broke.trades.empty
    assert broke.premium_skipped == 1


def test_modeled_rally_reaches_the_runner_and_a_crash_stops_first():
    calm = _flat(36)
    # The low stays at the fill. A one-dollar dip is enough to stop this cheap premium.
    rally = calm + [(100.0, 180.0, 100.0, 170.0), (170.0, 175.0, 170.0, 172.0)]
    frame = _frame(rally)
    stats = simulate_scale(
        [_setup(frame, 34)],
        {"TEST": frame},
        {"TEST": frame},
        _params(),
        {"mode": "scale", "stop_kind": "premium", "premium_stop": -0.50},
        starting_equity=100_000.0,
        session_filter=False,
    )
    assert len(stats.trades) == 1
    assert int(stats.trades["targets_hit"].iloc[0]) == 4
    assert stats.trades["runner"].iloc[0] == "target"
    assert float(stats.trades["pnl"].iloc[0]) > 0
    crash = _flat(36) + [(100.0, 101.0, 40.0, 45.0)]
    crashed = _frame(crash)
    stopped = simulate_scale(
        [_setup(crashed, 34)],
        {"TEST": crashed},
        {"TEST": crashed},
        _params(),
        {"mode": "scale", "stop_kind": "premium", "premium_stop": -0.30},
        starting_equity=100_000.0,
        session_filter=False,
    )
    assert stopped.trades["runner"].iloc[0] == "initial_stop"
    assert int(stopped.trades["targets_hit"].iloc[0]) == 0
    assert float(stopped.trades["pnl"].iloc[0]) < 0


def test_option_scale_plan_is_four_limit_sells_and_a_bot_stop(tmp_path: Path):
    plan = plan_option_scale(
        symbol="AAPL",
        premium=1.0,
        strike=190,
        expiry="2026-11-20",
        right="call",
        stop_kind="premium",
        premium_stop=-0.30,
        underlying_stop=180.0,
    )
    assert plan["limits_are_native"] is True
    assert plan["management"] == "bot"
    assert plan["payloads"]
    assert [payload["order_type"] for payload in plan["payloads"]] == ["LIMIT"] * 4
    assert [payload["quantity"] for payload in plan["payloads"]] == ["2", "1", "1", "1"]
    assert [payload["limit_price"] for payload in plan["payloads"]] == ["1.15", "1.20", "1.30", "2.00"]
    assert {payload["instrument_type"] for payload in plan["payloads"]} == {"OPTION"}
    assert {payload["position_intent"] for payload in plan["payloads"]} == {"SELL_TO_CLOSE"}
    assert plan["watch"]["breakeven_premium"] == pytest.approx(1.0)
    assert plan["watch"]["breakeven_applies_to"] == "runner"
    assert plan["watch"]["premium_stop"] == pytest.approx(0.70)
    assert "only the runner" in plan["note"]
    assert "OTOCO" in plan["note"]
    broker = PaperBroker(tmp_path / "paper.db", ZERO, starting_equity=10_000.0)
    broker.connect()
    assert stage_on_paper(broker, plan) == []
    with pytest.raises(ValueError):
        plan_option_scale(symbol="AAPL", premium=1.0, strike=190, expiry="2026-11-20", right="call", stop_kind="premium", premium_stop=0.10)
    text = Path("config/default.yaml").read_text()
    assert "live_trading_enabled: false" in text
    live = Path("src/webull_bot/execution/live.py").read_text()
    assert "plan_option_scale" not in live
    assert "plan_chart_exit" not in live
    assert "stage_on_paper" not in live
