"""Option fee model for a US Webull equity-option ticket.

Sources, checked September 2026:

* Webull US pricing (webull.com/pricing): $0 commission on options listed
  on US exchanges. Index options are $0.50 and are not used here. The same
  page says regulatory fees are passed through. It prints the equity TAF
  and SEC formulas; it does not itemize the options-exchange ORF.
* Options regulatory fee: $0.02 per contract, the exchange ORF also printed
  on Webull's non-US options schedules as a pass-through.
* OCC clearing fee: $0.02 per contract.
* FINRA trading-activity fee on options: $0.00279 per contract on sales,
  with a $0.01 minimum, consistent with the minimum on Webull's regulatory
  line. Equity TAF in this repo stays $0.000195 per share and is not
  applied to contracts.
* SEC Section 31: $20.60 per $1,000,000 of option premium sold, the same
  rate the stock backtest uses, applied to the premium notional.
* CAT: $0.000003 per share equivalent. One contract is 100 shares, so
  $0.0003 per contract, charged on buys and sells.

These are research assumptions. A live ticket can differ by a cent.
"""

from __future__ import annotations

ORF_PER_CONTRACT = 0.02
OCC_PER_CONTRACT = 0.02
TAF_PER_CONTRACT = 0.00279
TAF_MIN = 0.01
SEC_PER_DOLLAR = 0.0000206
CAT_PER_CONTRACT = 0.0003
CONTRACT_MULTIPLIER = 100


def option_leg_fees(contracts: int, premium_per_share: float, *, sell: bool) -> float:
    if contracts <= 0:
        return 0.0
    exchange = (ORF_PER_CONTRACT + OCC_PER_CONTRACT + CAT_PER_CONTRACT) * contracts
    if not sell:
        return exchange
    notional = max(premium_per_share, 0.0) * CONTRACT_MULTIPLIER * contracts
    taf = max(TAF_PER_CONTRACT * contracts, TAF_MIN)
    sec = SEC_PER_DOLLAR * notional
    return exchange + taf + sec
