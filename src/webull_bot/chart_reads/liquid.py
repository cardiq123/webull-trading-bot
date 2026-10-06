"""Pre-registered option universe.

Registered before the ATM universe re-score. Do not add or drop a name
after seeing P&L.

``LIQUID_BLUE_CHIPS`` is a 2026 snapshot of single stocks with tight option
markets, plus SPY and QQQ as index references. It is survivorship-biased:
names that failed, were acquired, or were never this liquid are absent.
The pass/fail gate does not use this list. The gate is point-in-time Dow
membership (``universe_dow.is_member`` on the signal day). This repository
has no point-in-time S&P 500 file, so a name that was never in the Dow can
be reported on the liquid list and cannot pass the gate by itself.
"""

from __future__ import annotations

from datetime import date, timedelta

from webull_bot.universe_dow import members_on

# Order is the registration order: the three named stocks, the rest of the
# liquid single-stock list, then the two index references.
LIQUID_BLUE_CHIPS: tuple[str, ...] = (
    "NVDA",
    "AAPL",
    "UNH",
    "MSFT",
    "AMZN",
    "META",
    "GOOGL",
    "JPM",
    "AMD",
    "TSLA",
    "AVGO",
    "COST",
    "V",
    "MA",
    "LLY",
    "XOM",
    "SPY",
    "QQQ",
)

REFERENCES: tuple[str, ...] = ("SPY", "QQQ")


def dow_members_between(start: date, end: date) -> list[str]:
    """Names that were in the Dow on at least one weekly sample in the span."""
    if end < start:
        return []
    found: set[str] = set()
    day = start
    while day <= end:
        found.update(members_on(day))
        day += timedelta(days=7)
    found.update(members_on(end))
    return sorted(found)
