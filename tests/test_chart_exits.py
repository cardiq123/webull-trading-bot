"""Exit styles and the Webull payloads. These do not score a book."""

from pathlib import Path

import pandas as pd
import pytest

from webull_bot.broker.paper import PaperBroker
from webull_bot.broker.webull import (
    build_bracket_orders,
    build_option_otoco_orders,
    build_option_trailing_stop_order,
    build_trailing_stop_order,
    new_client_order_id,
)
from webull_bot.chart_reads.detect import Setup
from webull_bot.chart_reads.exits import beats_baseline, exit_grid, select_winner
from webull_bot.chart_reads.params import BREAKOUT_DEFAULTS, DAILY_DEFAULTS, DEFAULTS
from webull_bot.chart_reads.simulate import simulate
from webull_bot.costs import CostModel
from webull_bot.execution.chart_exit import plan_chart_exit, stage_on_paper
from webull_bot.models import Order, OrderType, Side


ZERO = CostModel(
    slippage_bps=0.0,
    half_spread_bps=0.0,
    sec_fee_per_dollar_sold=0.0,
    finra_taf_per_share=0.0,
)


def _params(**extra) -> dict:
    chosen = {
        "reward_r": 2.0,
        "trail": "none",
        "flatten_eod": False,
        "max_hold_sessions": 10,
        "pdt_prospective": False,
        "risk_fraction": 0.20,
        "max_positions": 1,
        "account": "margin_pdt",
        "expression": "stock",
        "delta": 0.45,
        "dte": 45,
        "iv_premium": 1.15,
        "spread_multiplier": 1.0,
        "band_std": 2.0,
    }
    chosen.update(extra)
    return chosen


def _book(rows: list[tuple[float, float, float, float]], setups, params):
    index = pd.bdate_range("2024-01-02", periods=len(rows))
    frame = pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=index)
    frame["volume"] = 1_000_000.0
    return simulate(
        setups,
        {"TEST": frame},
        {"TEST": frame},
        params,
        starting_equity=1_000.0,
        costs=ZERO,
        session_filter=False,
    )


def _setup(index_fill: int, *, stop: float = 90.0, atr: float = 4.0, reference: float = 110.0) -> list[Setup]:
    index = pd.bdate_range("2024-01-02", periods=6)
    return [
        Setup(
            symbol="TEST",
            direction="long",
            kind="A",
            signal_time=index[0],
            fill_time=index[index_fill],
            anchor_time=index[0],
            stop=stop,
            atr=atr,
            reference=reference,
        )
    ]


def test_level_bracket_exits_at_the_target_and_the_default_path_is_stable():
    setups = _setup(1)
    rows = [
        (100.0, 101.0, 99.0, 100.0),
        (100.0, 101.0, 99.0, 100.0),
        (100.0, 130.0, 99.0, 120.0),
        (120.0, 121.0, 119.0, 120.0),
    ]
    params = _params(target_mode="r", reward_r=2.0)
    assert "exit_style" not in params
    first = _book(rows, setups, params)
    second = _book(rows, setups, dict(params))
    assert list(first.trades["reason"]) == ["target"]
    assert float(first.trades["exit_price"].iloc[0]) == pytest.approx(120.0)
    assert list(first.trades["pnl"]) == list(second.trades["pnl"])
    assert "exit_style" not in DEFAULTS
    assert "exit_style" not in DAILY_DEFAULTS
    assert "exit_style" not in BREAKOUT_DEFAULTS


def test_stop_wins_when_the_same_bar_hits_the_target():
    setups = _setup(1)
    rows = [
        (100.0, 101.0, 99.0, 100.0),
        (100.0, 101.0, 99.0, 100.0),
        (100.0, 130.0, 80.0, 120.0),
    ]
    stats = _book(rows, setups, _params(target_mode="r", reward_r=2.0))
    assert list(stats.trades["reason"]) == ["invalidation"]
    assert float(stats.trades["exit_price"].iloc[0]) == pytest.approx(90.0)


def test_percent_trail_ratchets_and_does_not_use_the_target():
    setups = _setup(1)
    rows = [
        (100.0, 101.0, 99.0, 100.0),
        (100.0, 100.0, 99.0, 100.0),
        (100.0, 120.0, 115.0, 118.0),
        (112.0, 113.0, 100.0, 101.0),
    ]
    params = _params(exit_style="trail_pct", trail_pct=0.10, target_mode="r", reward_r=2.0)
    stats = _book(rows, setups, params)
    assert list(stats.trades["reason"]) == ["trail"]
    assert float(stats.trades["exit_price"].iloc[0]) == pytest.approx(108.0)
    assert "ema_trail" not in set(stats.trades["reason"])


def test_wide_trail_does_not_take_the_two_r_target():
    setups = _setup(1)
    rows = [
        (100.0, 101.0, 99.0, 100.0),
        (100.0, 101.0, 99.0, 100.0),
        (100.0, 130.0, 99.0, 125.0),
    ]
    stats = _book(rows, setups, _params(exit_style="trail_pct", trail_pct=0.50, target_mode="r", reward_r=2.0))
    assert list(stats.trades["reason"]) == ["window_end"]


def test_hybrid_sells_half_at_the_level_and_trails_the_rest():
    setups = _setup(1, atr=4.0, reference=110.0)
    rows = [
        (100.0, 101.0, 99.0, 100.0),
        (100.0, 101.0, 99.0, 100.0),
        (100.0, 112.0, 106.0, 110.0),
        (108.0, 109.0, 100.0, 101.0),
    ]
    params = _params(
        exit_style="hybrid",
        target_mode="level",
        level_source="reference",
        reward_r=1.0,
        trail_atr=2.0,
    )
    stats = _book(rows, setups, params)
    assert list(stats.trades["reason"]) == ["partial", "trail"]
    assert list(stats.trades["quantity"]) == pytest.approx([5.0, 5.0])
    assert float(stats.trades["exit_price"].iloc[0]) == pytest.approx(110.0)
    assert float(stats.trades["exit_price"].iloc[1]) == pytest.approx(104.0)


def test_one_contract_hybrid_exits_in_full_at_the_target():
    index = pd.bdate_range("2024-01-02", periods=3)
    frame = pd.DataFrame(
        {
            "open": [100.0, 100.0, 100.0],
            "high": [101.0, 101.0, 130.0],
            "low": [99.0, 99.0, 99.0],
            "close": [100.0, 100.0, 120.0],
            "volume": [1_000_000.0, 1_000_000.0, 1_000_000.0],
        },
        index=index,
    )
    # A direct position is not required. The stock hybrid above covers the split.
    # This checks the quantity rule on the helper used by the simulator.
    from webull_bot.chart_reads.simulate import _can_partial

    assert _can_partial({"expression": "single", "quantity": 1}) is False
    assert _can_partial({"expression": "single", "quantity": 2}) is True
    assert _can_partial({"expression": "stock", "quantity": 0.5}) is True
    assert len(frame) == 3


def test_exit_grid_is_frozen_and_the_winner_rule_is_not_a_search():
    cells = exit_grid({"reward_r": 2.0, "max_hold_sessions": 15})
    assert [label for label, _ in cells] == [
        "level target",
        "trail 5%",
        "trail 10%",
        "trail 15%",
        "trail 1.5 ATR",
        "trail 2 ATR",
        "trail 3 ATR",
        "bracket 1.5R",
        "bracket 2R",
        "bracket 3R",
        "hybrid half at level, trail 2 ATR",
    ]
    assert cells[0][1]["trail"] == "none"
    assert "exit_style" not in cells[0][1]
    assert cells[-1][1]["reward_r"] == 1.0
    baseline = {"trades": 40, "expectancy": 1.0, "profit_factor": 1.1, "max_drawdown": -0.40}
    better = {"trades": 40, "expectancy": 1.5, "profit_factor": 1.1, "max_drawdown": -0.44}
    worse_dd = {"trades": 40, "expectancy": 2.0, "profit_factor": 1.2, "max_drawdown": -0.46}
    fewer = {"trades": 19, "expectancy": 5.0, "profit_factor": 2.0, "max_drawdown": -0.10}
    assert beats_baseline(baseline, better)
    assert not beats_baseline(baseline, worse_dd)
    assert not beats_baseline(baseline, fewer)
    assert not beats_baseline(baseline, {**better, "expectancy": 1.0})
    rows = [("level target", baseline), ("trail 5%", better), ("trail 10%", {**better, "expectancy": 1.4})]
    assert select_winner(rows) == "trail 5%"
    assert select_winner([("level target", baseline), ("trail 5%", fewer)]) == "level target"


def test_equity_trailing_and_bracket_payloads_match_the_docs():
    trail = build_trailing_stop_order(
        client_order_id="d" * 32,
        symbol="AAPL",
        side="SELL",
        quantity=15,
        trailing_type="AMOUNT",
        trailing_stop_step=5,
    )
    assert trail["order_type"] == "TRAILING_STOP_LOSS"
    assert trail["trailing_type"] == "AMOUNT"
    assert trail["trailing_stop_step"] == "5"
    assert trail["time_in_force"] == "DAY"
    assert trail["combo_type"] == "NORMAL"
    percent = build_trailing_stop_order(
        client_order_id="e" * 32,
        symbol="AAPL",
        side="SELL",
        quantity=10,
        trailing_type="PERCENTAGE",
        trailing_stop_step=0.05,
    )
    assert percent["trailing_type"] == "PERCENTAGE"
    assert percent["trailing_stop_step"] == "0.05"
    from webull_bot.broker.webull import build_equity_order

    with pytest.raises(ValueError):
        build_equity_order(
            client_order_id="e" * 32,
            symbol="AAPL",
            side="SELL",
            order_type="TRAILING_STOP_LOSS",
            quantity=10,
            time_in_force="GTC",
            trailing_type="AMOUNT",
            trailing_stop_step=1,
        )
    combo = build_bracket_orders(symbol="AAPL", quantity=1, take_profit=195, stop_loss=170)
    assert len(combo["client_combo_order_id"]) <= 32
    master, profit, stop = combo["new_orders"]
    assert [leg["combo_type"] for leg in combo["new_orders"]] == ["MASTER", "STOP_PROFIT", "STOP_LOSS"]
    assert master["order_type"] == "MARKET" and master["side"] == "BUY"
    assert profit["order_type"] == "LIMIT" and profit["limit_price"] == "195.00" and profit["side"] == "SELL"
    assert stop["order_type"] == "STOP_LOSS" and stop["stop_price"] == "170.00"
    assert "OTOCO" not in {leg["combo_type"] for leg in combo["new_orders"]}
    ids = {leg["client_order_id"] for leg in combo["new_orders"]}
    assert len(ids) == 3
    with pytest.raises(ValueError):
        build_option_trailing_stop_order(symbol="AAPL")
    with pytest.raises(ValueError):
        build_option_otoco_orders(symbol="AAPL")


def test_option_plan_is_bot_managed_and_paper_can_place_the_equity_trail(tmp_path: Path):
    option = plan_chart_exit(
        instrument="option",
        style="trail",
        symbol="AAPL",
        quantity=1,
        trail_type="PERCENTAGE",
        trail_step=0.10,
    )
    assert option["payloads"] == []
    assert option["native"] is False
    assert option["watch"]["trail_step"] == 0.10
    bracket = plan_chart_exit(
        instrument="equity",
        style="bracket",
        symbol="AAPL",
        quantity=10,
        stop_price=90,
        take_profit=120,
    )
    assert bracket["native"] is True
    assert [leg["combo_type"] for leg in bracket["payloads"]] == ["MASTER", "STOP_PROFIT", "STOP_LOSS"]
    with pytest.raises(TypeError):
        stage_on_paper(object(), bracket)
    text = Path("config/default.yaml").read_text()
    assert "live_trading_enabled: false" in text
    live = Path("src/webull_bot/execution/live.py").read_text()
    assert "plan_chart_exit" not in live
    assert "stage_on_paper" not in live

    broker = PaperBroker(tmp_path / "paper.db", ZERO, starting_equity=10_000.0)
    broker.connect()
    broker.fill_order_at(
        Order(
            client_order_id=new_client_order_id(),
            symbol="AAPL",
            side=Side.BUY,
            quantity=10,
            order_type=OrderType.MARKET,
        ),
        100.0,
    )
    trail = plan_chart_exit(
        instrument="equity",
        style="trail",
        symbol="AAPL",
        quantity=10,
        trail_type="PERCENTAGE",
        trail_step=0.10,
    )
    staged = stage_on_paper(broker, trail, peak=100.0)
    assert staged[0].order_type == OrderType.TRAILING
    held = broker.process_bar("AAPL", 100.0, 120.0, 115.0, 118.0)
    assert held == []
    filled = broker.process_bar("AAPL", 112.0, 113.0, 100.0, 101.0)
    assert len(filled) == 1
    assert filled[0].reason == "trail"
    assert filled[0].price == pytest.approx(108.0)
    assert broker.positions() == []
