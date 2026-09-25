"""Transaction costs.

Webull US stock and ETF trades are commission-free. Regulatory fees still
apply on sells and are passed through by brokers:

* SEC Section 31 fee: $20.60 per million dollars of covered sales, effective
  April 4, 2026 (SEC Fee Rate Advisory for Fiscal Year 2026, Feb 27, 2026).
  The rate is $0.00 per million before that date. Backtests use the
  post-April 2026 rate for the whole sample so results are not flattered by
  a temporary zero rate. This is conservative for earlier years.
* FINRA Trading Activity Fee for 2026: $0.000195 per share sold, maximum
  $9.79 per trade (FINRA fee adjustment schedule). FINRA proposed a temporary
  TAF holiday setting the rate to $0.00 for transactions from October 1, 2026
  through December 31, 2026 (SR-FINRA-2026-021). The engine uses the
  statutory 2026 rate by default so a three-month holiday does not inflate
  the backtest. Set ``finra_taf_per_share`` to 0 to model the holiday.

Slippage and half-spread are applied to the fill price, not booked as a
separate fee. They stand in for the gap between a signal price and a fill
on liquid names. They are not a measured Webull execution study.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CostModel:
    commission_per_trade: float = 0.0
    slippage_bps: float = 5.0
    half_spread_bps: float = 1.0
    sec_fee_per_dollar_sold: float = 20.60 / 1_000_000
    finra_taf_per_share: float = 0.000195
    finra_taf_cap: float = 9.79

    @property
    def friction_bps(self) -> float:
        return self.slippage_bps + self.half_spread_bps


def buy_price(raw: float, costs: CostModel) -> float:
    """Price paid, worse than the raw print by slippage plus half-spread."""
    if raw <= 0:
        raise ValueError("raw price must be positive")
    return raw * (1.0 + costs.friction_bps / 10_000.0)


def sell_price(raw: float, costs: CostModel) -> float:
    """Price received, worse than the raw print by slippage plus half-spread."""
    if raw <= 0:
        raise ValueError("raw price must be positive")
    return raw * (1.0 - costs.friction_bps / 10_000.0)


def sell_regulatory_fees(fill_price: float, quantity: float, costs: CostModel) -> float:
    """SEC Section 31 plus FINRA TAF on a sale. Buys are zero."""
    if quantity <= 0 or fill_price <= 0:
        return 0.0
    notional = fill_price * quantity
    sec = notional * costs.sec_fee_per_dollar_sold
    taf = min(quantity * costs.finra_taf_per_share, costs.finra_taf_cap)
    return sec + taf + costs.commission_per_trade


def buy_fees(costs: CostModel) -> float:
    return costs.commission_per_trade
