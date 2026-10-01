"""Fixed-fractional position sizing from stop distance.

Shares = floor(equity * risk_per_trade / (entry - stop)), then capped so the
position is at most ``max_position_pct`` of equity. If the cap binds, the
trade risks less than the budget, never more. A non-positive stop distance
is rejected. Fractional shares are off unless requested; sub-one-share
results are skipped rather than rounded up into a larger risk.
"""

from __future__ import annotations

import math


def shares_for_risk(
    equity: float,
    entry_price: float,
    stop_price: float,
    risk_per_trade: float,
    max_position_pct: float,
    *,
    allow_fractional: bool = False,
    cash_available: float | None = None,
) -> float:
    if equity <= 0 or entry_price <= 0 or risk_per_trade <= 0 or max_position_pct <= 0:
        return 0.0
    distance = entry_price - stop_price
    if distance <= 0:
        return 0.0
    risk_dollars = equity * risk_per_trade
    raw = risk_dollars / distance
    notional_cap = equity * max_position_pct
    capped = min(raw, notional_cap / entry_price)
    if cash_available is not None:
        if cash_available <= 0:
            return 0.0
        capped = min(capped, cash_available / entry_price)
    if allow_fractional:
        qty = math.floor(capped * 10_000) / 10_000
        if qty * entry_price < 1.0:
            return 0.0
        return qty
    qty = math.floor(capped + 1e-9)
    if qty < 1:
        return 0.0
    return float(qty)


def position_risk_dollars(entry_price: float, stop_price: float, quantity: float) -> float:
    return max(0.0, entry_price - stop_price) * quantity
