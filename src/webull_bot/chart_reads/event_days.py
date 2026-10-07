"""CPI, jobs-report, and FOMC decision days for the SPY opening-range study.

The dates are the release day or the decision day, copied before the score.
CPI and the Employment Situation are the Bureau of Labor Statistics 2026
schedule (bls.gov/schedule/2026 and the CPI and Employment Situation release
tables), 8:30 AM ET. FOMC dates are the second day of each 2026 meeting on
the Federal Reserve's calendar, which is the day the statement is published.
The first day of a two-day meeting is not skipped.

This set covers 2026 only. Yahoo's free 5-minute history does not reach
earlier years. A session outside 2026 is left unmarked on purpose so the
scorer can refuse it instead of trading through an unknown release.
"""

from __future__ import annotations

from datetime import date

CALENDAR_YEARS = frozenset({2026})

# BLS, Consumer Price Index release dates for reference months Dec 2025-Nov 2026.
CPI_DATES = frozenset(
    {
        date(2026, 1, 13),
        date(2026, 2, 13),
        date(2026, 3, 11),
        date(2026, 4, 10),
        date(2026, 5, 12),
        date(2026, 6, 10),
        date(2026, 7, 14),
        date(2026, 8, 12),
        date(2026, 9, 11),
        date(2026, 10, 14),
        date(2026, 11, 10),
        date(2026, 12, 10),
    }
)

# BLS, Employment Situation. Not always the first Friday (January 2026 printed on Feb 11).
NFP_DATES = frozenset(
    {
        date(2026, 1, 9),
        date(2026, 2, 11),
        date(2026, 3, 6),
        date(2026, 4, 3),
        date(2026, 5, 8),
        date(2026, 6, 5),
        date(2026, 7, 2),
        date(2026, 8, 7),
        date(2026, 9, 4),
        date(2026, 10, 2),
        date(2026, 11, 6),
        date(2026, 12, 4),
    }
)

# Federal Reserve, 2026 FOMC statement days.
FOMC_DATES = frozenset(
    {
        date(2026, 1, 28),
        date(2026, 3, 18),
        date(2026, 4, 29),
        date(2026, 6, 17),
        date(2026, 7, 29),
        date(2026, 9, 16),
        date(2026, 10, 28),
        date(2026, 12, 9),
    }
)

EVENT_DATES = CPI_DATES | NFP_DATES | FOMC_DATES


def event_kind(day: date) -> str | None:
    """Which release falls on ``day``, or None. A day can carry more than one name."""
    names = []
    if day in CPI_DATES:
        names.append("CPI")
    if day in NFP_DATES:
        names.append("NFP")
    if day in FOMC_DATES:
        names.append("FOMC")
    if not names:
        return None
    return "+".join(names)
