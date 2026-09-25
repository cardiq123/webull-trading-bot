from datetime import date

import numpy as np
import pandas as pd

from webull_bot.models import Position
from webull_bot.risk.manager import RiskLimits, RiskState, plan_entry


def _state(**kwargs) -> RiskState:
    base = dict(
        equity=100_000,
        cash=100_000,
        peak_equity=100_000,
        day_start_equity=100_000,
        account_type="margin",
    )
    base.update(kwargs)
    return RiskState(**base)


def _limits(**kwargs) -> RiskLimits:
    base = dict(
        risk_per_trade=0.01,
        max_position_pct=0.50,
        max_concurrent_positions=2,
        max_sector_pct=0.30,
        max_correlation=0.80,
        daily_max_loss_pct=0.02,
        max_drawdown_pct=0.15,
        flatten_on_daily_loss=True,
        intraday_margin_ratio=0.25,
        min_margin_equity=2_000,
        pdt_mode="off",
    )
    base.update(kwargs)
    return RiskLimits(**base)


def test_daily_loss_breaker_blocks_and_requests_flatten():
    plan = plan_entry(
        _state(equity=97_000, day_start_equity=100_000),
        _limits(),
        symbol="XLK",
        entry_price=100,
        stop_price=95,
        sector="technology",
        as_of=date(2026, 9, 25),
        prices={},
    )
    assert plan.accepted is False
    assert plan.flatten_now is True
    assert "daily loss" in plan.reason


def test_drawdown_breaker_sticks_after_equity_recovers():
    state = _state(equity=100_000, peak_equity=100_000, drawdown_halt=True)
    # circuit_update keeps a sticky halt even though equity is back at the peak.
    plan = plan_entry(
        state,
        _limits(flatten_on_max_drawdown=False),
        symbol="XLK",
        entry_price=100,
        stop_price=95,
        sector="technology",
        as_of=date(2026, 9, 25),
        prices={},
    )
    assert plan.accepted is False
    assert "drawdown" in plan.reason or state.drawdown_halt


def test_drawdown_trips_at_the_threshold():
    plan = plan_entry(
        _state(equity=84_000, peak_equity=100_000),
        _limits(),
        symbol="XLK",
        entry_price=100,
        stop_price=95,
        sector="technology",
        as_of=date(2026, 9, 25),
        prices={},
    )
    assert plan.accepted is False
    assert "drawdown" in plan.reason


def test_concurrent_sector_and_correlation_limits():
    held = [
        Position(symbol="AAPL", quantity=10, avg_price=100, sector="technology"),
        Position(symbol="MSFT", quantity=10, avg_price=100, sector="technology"),
    ]
    crowded = plan_entry(
        _state(positions=held),
        _limits(),
        symbol="NVDA",
        entry_price=100,
        stop_price=95,
        sector="technology",
        as_of=date(2026, 9, 25),
        prices={"AAPL": 100, "MSFT": 100, "NVDA": 100},
    )
    assert crowded.accepted is False
    assert "concurrent" in crowded.reason

    one = [Position(symbol="AAPL", quantity=200, avg_price=100, sector="technology")]
    sector = plan_entry(
        _state(positions=one),
        _limits(max_concurrent_positions=5),
        symbol="MSFT",
        entry_price=100,
        stop_price=98,
        sector="technology",
        as_of=date(2026, 9, 25),
        prices={"AAPL": 100, "MSFT": 100},
    )
    assert sector.accepted is False
    assert "sector" in sector.reason

    index = pd.bdate_range("2024-01-01", periods=40)
    series = pd.Series(np.linspace(100, 140, 40), index=index, dtype=float)
    returns = pd.DataFrame({"AAA": series.pct_change(), "BBB": series.pct_change()})
    corr = plan_entry(
        _state(positions=[Position(symbol="AAA", quantity=1, avg_price=10, sector="broad")]),
        _limits(max_sector_pct=1, max_concurrent_positions=5),
        symbol="BBB",
        entry_price=50,
        stop_price=45,
        sector="other",
        as_of=date(2026, 9, 25),
        prices={"AAA": 10, "BBB": 50},
        returns=returns,
    )
    assert corr.accepted is False
    assert "correlation" in corr.reason
