"""Pattern day trader and intraday-margin checks.

Regulatory status as of September 2026
--------------------------------------
FINRA Regulatory Notice 26-10 (April 20, 2026) adopted amendments to Rule
4210 that replace the day-trading margin requirements. The SEC approved the
change. Effective June 4, 2026, the pattern day trader designation, the
four-day-trades-in-five-business-days test, and the $25,000 minimum equity
requirement are eliminated. Firms that need more time may phase the change
in until October 20, 2027.

What replaces it is an intraday margin standard: on a day with activity that
reduces the intraday margin level, the member must determine whether the
account has an intraday margin deficit. The $2,000 minimum equity to use
margin (the older Rule 4210 / Regulation T floor) was not repealed by this
notice.

This module does not know whether Webull has finished that migration. The
default ``mode="auto"`` therefore:

* before 2026-06-04, enforces the legacy count and $25,000 test;
* from 2026-06-04 through 2027-10-20, enforces the legacy test when
  ``enforce_legacy_during_transition`` is true (the default), because a
  broker may still be on the old rule during the phase-in;
* after 2027-10-20, does not enforce the legacy test.

The intraday-margin approximation always runs for margin accounts. It is a
conservative retail stand-in, not Webull's official intraday margin level:
required margin is ``intraday_margin_ratio`` times gross long market value,
and a new order is blocked when that requirement would exceed equity or when
margin equity is below ``min_margin_equity`` (default $2,000).

Cash accounts are not pattern day traders. They are blocked from buying with
unsettled sale proceeds (T+1). That check lives with the cash ledger in the
backtester and the paper broker.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from webull_bot.calendar import previous_trading_days

LEGACY_EFFECTIVE = date(2026, 6, 4)
TRANSITION_ENDS = date(2027, 10, 20)


@dataclass(frozen=True)
class PdtDecision:
    allowed: bool
    reason: str
    legacy_applies: bool
    day_trades_in_window: int


def legacy_rule_applies(
    day: date,
    *,
    mode: str = "auto",
    enforce_legacy_during_transition: bool = True,
    account_type: str = "margin",
) -> bool:
    if account_type != "margin":
        return False
    if mode == "off":
        return False
    if mode == "on":
        return True
    if mode != "auto":
        raise ValueError(f"Unknown PDT mode: {mode}")
    if day < LEGACY_EFFECTIVE:
        return True
    if day <= TRANSITION_ENDS:
        return enforce_legacy_during_transition
    return False


def day_trades_in_window(
    trade_days: list[date],
    as_of: date,
    window: int,
) -> int:
    sessions = set(previous_trading_days(as_of, window, include_self=True))
    return sum(1 for traded_on in trade_days if traded_on in sessions)


def check_day_trade(
    *,
    as_of: date,
    equity: float,
    trade_days: list[date],
    opening_same_day: bool,
    account_type: str,
    mode: str = "auto",
    enforce_legacy_during_transition: bool = True,
    legacy_equity_threshold: float = 25_000.0,
    legacy_max_day_trades: int = 3,
    legacy_window_business_days: int = 5,
) -> PdtDecision:
    """Decide whether a same-day round trip may be closed (or opened to close).

    ``opening_same_day`` is true when the close would complete a round trip
    that was opened on ``as_of``. Entries that are not day trades are not
    blocked by the count. The count includes this prospective trade.
    """
    applies = legacy_rule_applies(
        as_of,
        mode=mode,
        enforce_legacy_during_transition=enforce_legacy_during_transition,
        account_type=account_type,
    )
    count = day_trades_in_window(trade_days, as_of, legacy_window_business_days)
    if not applies or not opening_same_day:
        return PdtDecision(True, "legacy PDT not applicable to this order", applies, count)
    if equity >= legacy_equity_threshold:
        return PdtDecision(True, "equity at or above the legacy PDT threshold", applies, count)
    prospective = count + 1
    if prospective > legacy_max_day_trades:
        return PdtDecision(
            False,
            (
                f"legacy PDT: this would be day trade {prospective} in "
                f"{legacy_window_business_days} sessions with equity "
                f"{equity:.2f} below {legacy_equity_threshold:.0f}"
            ),
            applies,
            count,
        )
    return PdtDecision(True, "within the legacy day-trade count", applies, count)


def intraday_margin_ok(
    *,
    equity: float,
    gross_exposure: float,
    new_exposure: float,
    margin_ratio: float,
    min_margin_equity: float,
    account_type: str,
) -> tuple[bool, str]:
    """Block orders that would create a simplified intraday margin deficit.

    ``gross_exposure`` and ``new_exposure`` are absolute market values of
    open risk and the proposed order. Short exposure is included in the
    gross figure by the caller. Cash accounts skip this check.
    """
    if account_type != "margin":
        return True, "cash account is not checked against intraday margin"
    if equity < min_margin_equity and new_exposure > 0:
        return False, (
            f"margin equity {equity:.2f} is below the {min_margin_equity:.0f} "
            "floor required to add exposure"
        )
    required = (gross_exposure + new_exposure) * margin_ratio
    if required > equity + 1e-6:
        return False, (
            f"intraday margin deficit: required {required:.2f} exceeds equity {equity:.2f} "
            f"at ratio {margin_ratio:.2f}"
        )
    return True, "intraday margin approximation is satisfied"
