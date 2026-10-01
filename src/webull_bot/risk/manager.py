"""Portfolio risk checks applied before any new entry.

Circuit breakers:

* Daily loss: once equity is down ``daily_max_loss_pct`` from the session's
  starting equity, new entries stop. If ``flatten_on_daily_loss`` is set,
  the caller flattens.
* Max drawdown: once equity is down ``max_drawdown_pct`` from its peak, new
  entries halt until the halt is cleared. Flattening is optional.

Other limits: concurrent positions, single-name notional (via sizing), sector
notional, and pairwise return correlation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import pandas as pd

from webull_bot.models import Position
from webull_bot.risk.pdt import check_day_trade, intraday_margin_ok
from webull_bot.risk.sizing import shares_for_risk


@dataclass
class RiskLimits:
    risk_per_trade: float = 0.0075
    max_position_pct: float = 0.20
    max_concurrent_positions: int = 5
    max_sector_pct: float = 0.35
    max_correlation: float = 0.85
    correlation_lookback: int = 60
    daily_max_loss_pct: float = 0.02
    max_drawdown_pct: float = 0.15
    flatten_on_daily_loss: bool = True
    flatten_on_max_drawdown: bool = False
    intraday_margin_ratio: float = 0.25
    min_margin_equity: float = 2000.0
    allow_fractional: bool = False
    pdt_mode: str = "auto"
    enforce_legacy_during_transition: bool = True
    legacy_equity_threshold: float = 25_000.0
    legacy_max_day_trades: int = 3
    legacy_window_business_days: int = 5


@dataclass
class RiskState:
    equity: float
    cash: float
    peak_equity: float
    day_start_equity: float
    positions: list[Position] = field(default_factory=list)
    day_trade_dates: list[date] = field(default_factory=list)
    halted: bool = False
    halt_reason: str = ""
    drawdown_halt: bool = False
    account_type: str = "margin"


@dataclass
class EntryPlan:
    accepted: bool
    quantity: float
    reason: str
    flatten_now: bool = False
    halt_kind: str = ""


def circuit_update(state: RiskState, limits: RiskLimits) -> RiskState:
    """Refresh halt flags from the current equity. Does not mutate inputs.

    The daily-loss halt is recomputed from today's starting equity, so it
    clears on the next session once the caller resets ``day_start_equity``.
    The drawdown halt sticks until a human clears ``drawdown_halt``, even
    if equity bounces.
    """
    peak = max(state.peak_equity, state.equity)
    drawdown_halt = state.drawdown_halt
    daily_halt = False
    reason = ""
    if state.day_start_equity > 0:
        daily_dd = 1.0 - (state.equity / state.day_start_equity)
        if daily_dd >= limits.daily_max_loss_pct - 1e-12:
            daily_halt = True
            reason = (
                f"daily loss {daily_dd:.2%} reached the {limits.daily_max_loss_pct:.2%} breaker"
            )
    if peak > 0:
        dd = 1.0 - (state.equity / peak)
        if dd >= limits.max_drawdown_pct - 1e-12:
            drawdown_halt = True
            reason = f"drawdown {dd:.2%} reached the {limits.max_drawdown_pct:.2%} breaker"
    halted = drawdown_halt or daily_halt
    if not halted:
        reason = ""
    return RiskState(
        equity=state.equity,
        cash=state.cash,
        peak_equity=peak,
        day_start_equity=state.day_start_equity,
        positions=list(state.positions),
        day_trade_dates=list(state.day_trade_dates),
        halted=halted,
        halt_reason=reason,
        drawdown_halt=drawdown_halt,
        account_type=state.account_type,
    )


def _sector_notional(positions: list[Position], prices: dict[str, float], sector: str) -> float:
    total = 0.0
    for pos in positions:
        if pos.sector == sector:
            total += abs(pos.quantity) * prices.get(pos.symbol, pos.avg_price)
    return total


def _max_corr(
    symbol: str,
    positions: list[Position],
    returns: pd.DataFrame,
    lookback: int,
) -> float:
    if returns.empty or symbol not in returns.columns:
        return 0.0
    window = returns.tail(lookback)
    if symbol not in window.columns or len(window) < 10:
        return 0.0
    worst = 0.0
    left = window[symbol]
    for pos in positions:
        if pos.symbol not in window.columns or pos.symbol == symbol:
            continue
        pair = pd.concat([left, window[pos.symbol]], axis=1).dropna()
        if len(pair) < 10:
            continue
        corr = float(pair.iloc[:, 0].corr(pair.iloc[:, 1]))
        if pd.isna(corr):
            continue
        worst = max(worst, corr)
    return worst


def plan_entry(
    state: RiskState,
    limits: RiskLimits,
    *,
    symbol: str,
    entry_price: float,
    stop_price: float,
    sector: str,
    as_of: date,
    prices: dict[str, float],
    returns: pd.DataFrame | None = None,
    would_day_trade_on_close: bool = False,
) -> EntryPlan:
    """Size and accept or reject one new long."""
    state = circuit_update(state, limits)
    if state.halted:
        flatten = False
        kind = "drawdown" if state.drawdown_halt else "daily"
        if kind == "daily" and limits.flatten_on_daily_loss:
            flatten = True
        if state.drawdown_halt and limits.flatten_on_max_drawdown:
            flatten = True
            kind = "drawdown"
        return EntryPlan(False, 0.0, state.halt_reason, flatten_now=flatten, halt_kind=kind)
    if any(pos.symbol == symbol for pos in state.positions):
        return EntryPlan(False, 0.0, "already in a position")
    if len(state.positions) >= limits.max_concurrent_positions:
        return EntryPlan(False, 0.0, "max concurrent positions reached")

    quantity = shares_for_risk(
        state.equity,
        entry_price,
        stop_price,
        limits.risk_per_trade,
        limits.max_position_pct,
        allow_fractional=limits.allow_fractional,
        cash_available=state.cash,
    )
    if quantity <= 0:
        return EntryPlan(False, 0.0, "position size rounded to zero")

    notional = quantity * entry_price
    sector_after = _sector_notional(state.positions, prices, sector) + notional
    if state.equity > 0 and sector_after / state.equity > limits.max_sector_pct + 1e-12:
        return EntryPlan(False, 0.0, f"sector {sector} would exceed {limits.max_sector_pct:.0%}")

    if returns is not None and state.positions:
        corr = _max_corr(symbol, state.positions, returns, limits.correlation_lookback)
        if corr > limits.max_correlation:
            return EntryPlan(
                False,
                0.0,
                f"correlation {corr:.2f} exceeds {limits.max_correlation:.2f}",
            )

    gross = 0.0
    for pos in state.positions:
        gross += abs(pos.quantity) * prices.get(pos.symbol, pos.avg_price)
    ok, why = intraday_margin_ok(
        equity=state.equity,
        gross_exposure=gross,
        new_exposure=notional,
        margin_ratio=limits.intraday_margin_ratio,
        min_margin_equity=limits.min_margin_equity,
        account_type=state.account_type,
    )
    if not ok:
        return EntryPlan(False, 0.0, why)

    if would_day_trade_on_close:
        decision = check_day_trade(
            as_of=as_of,
            equity=state.equity,
            trade_days=state.day_trade_dates,
            opening_same_day=True,
            account_type=state.account_type,
            mode=limits.pdt_mode,
            enforce_legacy_during_transition=limits.enforce_legacy_during_transition,
            legacy_equity_threshold=limits.legacy_equity_threshold,
            legacy_max_day_trades=limits.legacy_max_day_trades,
            legacy_window_business_days=limits.legacy_window_business_days,
        )
        if not decision.allowed:
            return EntryPlan(False, 0.0, decision.reason)

    return EntryPlan(True, quantity, "accepted")
