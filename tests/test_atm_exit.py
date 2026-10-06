"""ATM 14 DTE exit grid. These tests do not score a holdout."""

from datetime import date

import numpy as np
import pandas as pd
import pytest

from webull_bot.chart_reads.atm_exit import (
    ALL_OUT_TARGETS,
    ATM_DELTA,
    ATM_DTE,
    DAILY_TIME_STOPS,
    FALLBACK_TRAIN_TRADES,
    HOURLY_TIME_STOPS,
    HOLDS_UP_MIN_TRADES,
    MIN_TRAIN_TRADES,
    REFERENCE_RUNGS,
    REFERENCE_RUNNER,
    REFERENCE_STOP,
    RUNG_TARGETS,
    RUNNER_TARGETS,
    STOPS,
    TRAIL_PCTS,
    Cell,
    beats,
    choose,
    deflated_sharpe,
    frozen_grid,
    holds_up,
    neighbors,
    run_quotes,
    sell_fee,
    _norm_ppf,
)
from webull_bot.chart_reads.detect import Setup
from webull_bot.chart_reads.premium_scale import (
    SCALE_TIERS,
    apply_scale_bar,
    new_state,
    simulate_scale,
)
from webull_bot.chart_reads.simulate import simulate
from webull_bot.costs import CostModel
from webull_bot.options.fees import CONTRACT_MULTIPLIER, option_leg_fees

ZERO = CostModel(
    slippage_bps=0.0,
    half_spread_bps=0.0,
    sec_fee_per_dollar_sold=0.0,
    finra_taf_per_share=0.0,
)


def _quotes(**overrides):
    row = {
        "open_bid": 1.0,
        "adverse_bid": 1.0,
        "favorable_bid": 1.0,
        "close_bid": 1.0,
        "entry_bar": False,
        "is_last": False,
        "held": 2,
        "expired": False,
    }
    row.update(overrides)
    return row


def _frozen_scale(stop: float) -> Cell:
    return Cell(
        "A",
        "frozen",
        float(stop),
        tuple(pct for pct, _qty in SCALE_TIERS),
        tuple(qty for _pct, qty in SCALE_TIERS),
        (False, False, False, True),
        0.0,
        None,
        1,
    )


def _replay(cell: Cell, ask: float, rows: list[dict], *, mode: str, stop_kind: str, premium_stop: float):
    state = new_state(ask, mode, stop_kind, premium_stop)
    reason = None
    for index, row in enumerate(rows):
        terminal = None
        if row.get("expired") and row.get("is_last"):
            terminal = "expiry"
        elif int(row.get("held", 1)) >= 99 and row.get("is_last"):
            terminal = "time_stop"
        reason = apply_scale_bar(
            state,
            {
                "open_bid": row["open_bid"],
                "adverse_bid": row["adverse_bid"],
                "favorable_bid": row["favorable_bid"],
                "close_bid": row["close_bid"],
                "underlying_hit": False,
                "underlying_bid": 0.0,
            },
            entry_bar=bool(row.get("entry_bar")),
            terminal=terminal,
        )
        if reason:
            break
    ours = run_quotes(cell, ask, rows, max_hold=99)
    return state, reason, ours


def test_grid_is_the_preregistered_enumeration():
    assert ATM_DTE == 14
    assert ATM_DELTA == 0.50
    assert STOPS == (-0.10, -0.15, -0.20, -0.25, -0.30, -0.40)
    assert RUNG_TARGETS == (0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50)
    assert RUNNER_TARGETS == (0.50, 0.75, 1.00, 1.50)
    assert ALL_OUT_TARGETS == (0.15, 0.25, 0.30, 0.50, 0.75, 1.00)
    assert TRAIL_PCTS == (0.10, 0.15, 0.25)
    assert HOURLY_TIME_STOPS == (2, 5, 10)
    assert DAILY_TIME_STOPS == (3, 7, 14)
    assert REFERENCE_RUNGS == (0.15, 0.25, 0.40)
    assert REFERENCE_RUNNER == 1.00
    assert REFERENCE_STOP == -0.20
    assert MIN_TRAIN_TRADES == 30
    assert FALLBACK_TRAIN_TRADES == 15
    assert HOLDS_UP_MIN_TRADES == 20

    hourly = frozen_grid("hourly")
    daily = frozen_grid("daily")
    assert len({cell.label for cell in hourly}) == len(hourly)
    assert len({cell.label for cell in daily}) == len(daily)
    families = {cell.family for cell in hourly}
    assert families == {"A", "B", "C", "D", "E"}
    for cell in hourly:
        assert cell.stop in STOPS
        assert sum(cell.qtys) + (0 if any(cell.runner_tier) else cell.runner_contracts) == 5
        if cell.family in {"A", "B"}:
            fixed = [pct for pct, flag in zip(cell.pcts, cell.runner_tier) if not flag]
            assert fixed == sorted(fixed)
            assert all(right > left for left, right in zip(fixed, fixed[1:]))
            assert cell.pcts[-1] > fixed[-1]
            assert cell.trail == 0.0
            assert cell.max_hold is None
        if cell.family == "C":
            assert cell.runner_contracts == 0
            assert cell.pcts[0] in ALL_OUT_TARGETS
        if cell.family == "D":
            assert cell.max_hold in HOURLY_TIME_STOPS
            assert cell.stop == REFERENCE_STOP
    for cell in daily:
        if cell.family == "D":
            assert cell.max_hold in DAILY_TIME_STOPS
    shared = {cell.label for cell in hourly if cell.family != "D"}
    assert shared == {cell.label for cell in daily if cell.family != "D"}
    # Count locked before any holdout score. Do not grow the grid to chase a profit.
    assert len(hourly) == 1293
    assert len(daily) == 1293


def test_frozen_premium_stop_still_rejects_the_search_stops():
    with pytest.raises(ValueError):
        new_state(1.0, "scale", "premium", -0.10)


def test_sell_fee_matches_the_listed_option_schedule():
    for qty, price in ((1, 0.05), (2, 1.15), (5, 0.40), (1, 0.0)):
        assert sell_fee(qty, price) == pytest.approx(option_leg_fees(qty, price, sell=True))


def test_stop_wins_when_the_same_bar_also_reaches_a_target():
    cell = _frozen_scale(-0.30)
    rows = [_quotes(open_bid=0.95, adverse_bid=0.60, favorable_bid=2.50, close_bid=0.60)]
    state, reason, ours = _replay(cell, 1.0, rows, mode="scale", stop_kind="premium", premium_stop=-0.30)
    assert reason == "initial_stop"
    assert ours["reason"] == "initial_stop"
    assert ours["targets_hit"] == 0
    assert ours["remaining"] == 0
    assert ours["runner"] == "initial_stop"
    assert ours["credit"] == pytest.approx(state["credit"])


def test_entry_bar_does_not_stop_on_the_open_bid():
    cell = _frozen_scale(-0.20)
    rows = [
        _quotes(open_bid=0.70, adverse_bid=0.90, favorable_bid=1.05, close_bid=0.95, entry_bar=True, held=1),
        _quotes(open_bid=0.95, adverse_bid=0.75, favorable_bid=0.96, close_bid=0.80, held=2),
    ]
    state, reason, ours = _replay(cell, 1.0, rows, mode="scale", stop_kind="premium", premium_stop=-0.20)
    assert reason == "initial_stop"
    assert ours["reason"] == "initial_stop"
    fees = option_leg_fees(5, 0.75, sell=True)
    assert ours["credit"] == pytest.approx(5 * 0.75 * CONTRACT_MULTIPLIER - fees)
    assert ours["credit"] == pytest.approx(state["credit"])


def test_first_target_arms_break_even_on_the_runner_only():
    cell = _frozen_scale(-0.50)
    rows = [
        _quotes(open_bid=1.0, adverse_bid=0.90, favorable_bid=1.18, close_bid=1.10),
        _quotes(open_bid=1.05, adverse_bid=0.97, favorable_bid=1.10, close_bid=1.02),
        _quotes(open_bid=0.90, adverse_bid=0.40, favorable_bid=0.70, close_bid=0.45),
    ]
    state, reason, ours = _replay(cell, 1.0, rows, mode="scale", stop_kind="premium", premium_stop=-0.50)
    assert reason == "initial_stop"
    assert ours["reason"] == "initial_stop"
    assert ours["runner"] == "breakeven"
    assert ours["targets_hit"] == 1
    assert ours["sold"]["0.15"] == 2
    assert ours["armed"] == 1
    assert ours["credit"] == pytest.approx(state["credit"])
    assert state["runner"] == "breakeven"
    assert state["stop_px"] == pytest.approx(0.50)


def test_a_gap_through_the_initial_stop_flattens_the_armed_runner():
    cell = _frozen_scale(-0.20)
    rows = [
        _quotes(open_bid=1.0, adverse_bid=0.95, favorable_bid=1.20, close_bid=1.16),
        _quotes(open_bid=0.50, adverse_bid=0.40, favorable_bid=0.55, close_bid=0.45),
    ]
    state, reason, ours = _replay(cell, 1.0, rows, mode="scale", stop_kind="premium", premium_stop=-0.20)
    assert reason == "initial_stop"
    assert ours["reason"] == "initial_stop"
    assert ours["runner"] == "initial_stop"
    assert ours["targets_hit"] == 2
    assert ours["sold"]["0.15"] == 2
    assert ours["sold"]["0.20"] == 1
    assert "1.00" not in ours["sold"]
    assert ours["credit"] == pytest.approx(state["credit"])


def test_a_rally_through_every_limit_matches_the_frozen_ladder():
    cell = _frozen_scale(-0.30)
    rows = [_quotes(open_bid=1.0, adverse_bid=0.90, favorable_bid=3.0, close_bid=2.5)]
    state, reason, ours = _replay(cell, 1.0, rows, mode="scale", stop_kind="premium", premium_stop=-0.30)
    assert reason == "target"
    assert ours["reason"] == "target"
    assert ours["targets_hit"] == 4
    assert ours["runner"] == "target"
    assert ours["sold"]["1.00"] == 1
    assert ours["credit"] == pytest.approx(state["credit"])


def test_between_break_even_and_the_initial_stop_only_the_runner_sells():
    cell = _frozen_scale(-0.50)
    rows = [
        _quotes(open_bid=1.0, adverse_bid=0.90, favorable_bid=1.18, close_bid=1.10),
        _quotes(open_bid=1.05, adverse_bid=0.97, favorable_bid=1.25, close_bid=1.15),
    ]
    state, reason, ours = _replay(cell, 1.0, rows, mode="scale", stop_kind="premium", premium_stop=-0.50)
    assert reason is None or state["done"] is False or ours["reason"] in {"breakeven", "window_end", "target"}
    assert ours["sold"].get("0.15") == 2
    assert ours["sold"].get("0.20") == 1
    assert "0.30" not in ours["sold"]
    assert "1.00" not in ours["sold"]
    assert ours["runner"] == "breakeven"


def test_all_out_sells_every_contract_at_the_single_target():
    cell = Cell("C", "all-out", -0.30, (0.30,), (5,), (False,), 0.0, None, 0)
    rows = [_quotes(open_bid=2.0, adverse_bid=1.8, favorable_bid=4.0, close_bid=3.0)]
    state, reason, ours = _replay(cell, 2.0, rows, mode="all_out", stop_kind="premium", premium_stop=-0.30)
    assert reason == "target"
    assert ours["reason"] == "target"
    assert ours["runner"] == "all_out"
    assert ours["targets_hit"] == 1
    assert ours["credit"] == pytest.approx(state["credit"])


def test_runner_trail_ratchets_and_does_not_fill_the_same_bar_limit():
    cell = Cell(
        "E",
        "trail",
        -0.50,
        (0.15, 0.25, 0.40, 1.00),
        (2, 1, 1, 1),
        (False, False, False, True),
        0.10,
        None,
        1,
    )
    rows = [
        _quotes(open_bid=1.0, adverse_bid=0.90, favorable_bid=1.20, close_bid=1.16),
        _quotes(open_bid=1.15, adverse_bid=1.05, favorable_bid=2.50, close_bid=1.40),
    ]
    ours = run_quotes(cell, 1.0, rows, max_hold=99)
    assert ours["sold"]["0.15"] == 2
    assert ours["runner"] == "trail"
    assert "1.00" not in ours["sold"]
    runner_fees = option_leg_fees(1, 1.05, sell=True)
    first_fees = option_leg_fees(2, 1.15, sell=True)
    # The +25% and +40% limits are reachable on the second bar after the runner stops.
    third = option_leg_fees(1, 1.25, sell=True) + option_leg_fees(1, 1.40, sell=True)
    assert ours["sold"]["0.25"] == 1
    assert ours["sold"]["0.40"] == 1
    assert ours["credit"] == pytest.approx(
        2 * 1.15 * CONTRACT_MULTIPLIER
        - first_fees
        + 1.05 * CONTRACT_MULTIPLIER
        - runner_fees
        + 1.25 * CONTRACT_MULTIPLIER
        + 1.40 * CONTRACT_MULTIPLIER
        - third
    )


def test_time_stop_exits_the_open_contracts_at_the_close():
    cell = Cell(
        "D",
        "time",
        -0.20,
        (0.15, 0.25, 0.40, 1.00),
        (2, 1, 1, 1),
        (False, False, False, True),
        0.0,
        2,
        1,
    )
    rows = [
        _quotes(open_bid=1.0, adverse_bid=0.95, favorable_bid=1.05, close_bid=1.02, held=1, is_last=True, entry_bar=True),
        _quotes(open_bid=1.02, adverse_bid=0.95, favorable_bid=1.08, close_bid=1.04, held=2, is_last=True),
    ]
    ours = run_quotes(cell, 1.0, rows, max_hold=99)
    assert ours["reason"] == "time_stop"
    assert ours["runner"] == "time_stop"
    assert ours["targets_hit"] == 0
    fees = option_leg_fees(5, 1.04, sell=True)
    assert ours["credit"] == pytest.approx(5 * 1.04 * CONTRACT_MULTIPLIER - fees)


def test_choose_reads_training_sharpe_only():
    rows = [
        {"label": "weak", "sharpe": 0.2, "expectancy": 50.0, "max_drawdown": -0.05, "trades": 40, "holdout_sharpe": 9.0},
        {"label": "strong", "sharpe": 0.8, "expectancy": 1.0, "max_drawdown": -0.40, "trades": 40, "holdout_sharpe": -9.0},
        {"label": "thin", "sharpe": 5.0, "expectancy": 100.0, "max_drawdown": 0.0, "trades": 10, "holdout_sharpe": 9.0},
    ]
    picked = choose(rows)
    assert picked["label"] == "strong"
    assert picked["fallback"] is False
    assert picked["rule"].startswith("highest training Sharpe")
    thin = [dict(row) for row in rows]
    thin[0]["trades"] = 16
    thin[1]["trades"] = 10
    thin[2]["trades"] = 10
    fallback = choose(thin)
    assert fallback["fallback"] is True
    assert fallback["label"] == "weak"
    assert choose([{"label": "none", "sharpe": 1.0, "expectancy": 1.0, "max_drawdown": 0.0, "trades": 3}])["label"] is None


def test_neighbors_stay_inside_the_frozen_grid():
    hourly = frozen_grid("hourly")
    cell = next(item for item in hourly if item.family == "A" and item.stop == -0.20 and item.trail == 0.0)
    adjacent = neighbors(cell, hourly, "hourly")
    assert adjacent
    assert len(adjacent) <= 8
    labels = {item.label for item in hourly}
    assert cell.label not in {item.label for item in adjacent}
    assert {item.label for item in adjacent} <= labels
    stops = {item.stop for item in adjacent if item.pcts == cell.pcts and item.trail == cell.trail}
    assert -0.15 in stops or -0.25 in stops


def test_deflated_sharpe_hurdle_rises_with_the_number_of_trials():
    assert _norm_ppf(0.975) == pytest.approx(1.95996398454, abs=1e-6)
    rng = np.random.default_rng(17)
    sample = rng.normal(0.01, 0.02, size=252)
    few = deflated_sharpe(sample, 2)
    many = deflated_sharpe(sample, 500)
    assert few["dsr"] is not None and many["dsr"] is not None
    assert many["sr_star_annual"] > few["sr_star_annual"]
    assert many["trials"] == 500


def test_holds_up_requires_the_preregistered_bars():
    good = {
        "expectancy": 1.0,
        "ending_equity": 1100.0,
        "starting_equity": 1000.0,
        "trades": 25,
        "sharpe": 0.4,
        "max_drawdown": -0.10,
    }
    random_row = {"trades": 25, "sharpe": 0.1, "max_drawdown": -0.20}
    ok, reasons = holds_up(good, random_row, 0.5)
    assert ok and reasons == []
    bad, reasons = holds_up(good, random_row, -0.1)
    assert not bad
    assert any("walk-forward" in item for item in reasons)
    assert beats(good, random_row)
    worse = dict(good, max_drawdown=-0.50)
    assert not beats(worse, random_row)


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
        "delta": 0.50,
        "dte": 14,
        "iv_premium": 1.15,
        "spread_multiplier": 1.0,
        "target_mode": "r",
    }
    chosen.update(extra)
    return chosen


def test_path_replay_matches_simulate_scale_on_the_frozen_ladder():
    from webull_bot.chart_reads.atm_exit import build_paths, score_cell

    prices = []
    for index in range(40):
        price = 100.0 + index * 0.4
        prices.append((price, price + 1.0, price - 0.5, price + 0.2))
    frame = _frame(prices)
    setup = [_setup(frame, 30)]
    params = _params()
    stats = simulate_scale(
        setup,
        {"TEST": frame},
        {"TEST": frame},
        params,
        {"mode": "scale", "stop_kind": "premium", "premium_stop": -0.20},
        starting_equity=1_000_000.0,
        session_filter=False,
    )
    paths = build_paths(setup, {"TEST": frame}, {"TEST": frame}, params, session_filter=False)
    assert sum(path.ok for path in paths) == 1
    cell = _frozen_scale(-0.20)
    scored = score_cell(
        paths,
        cell,
        starting_equity=1_000_000.0,
        max_hold=10,
        pdt_prospective=False,
        keep_trades=True,
    )
    assert scored["trades"] == int(stats.metrics["trades"])
    assert scored["trade_rows"][0]["pnl"] == pytest.approx(float(stats.trades["pnl"].iloc[0]), abs=0.02)
    assert scored["trade_rows"][0]["reason"] == str(stats.trades["reason"].iloc[0])


def test_default_option_path_is_unchanged_when_the_search_module_is_imported():
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
    assert date(2024, 1, 2).year == 2024
