"""NYSE session calendar, America/New_York, holiday aware.

Holidays follow the standard NYSE full-day closures: New Year's Day,
Martin Luther King Jr. Day, Washington's Birthday, Good Friday, Memorial Day,
Juneteenth, Independence Day, Labor Day, Thanksgiving, and Christmas.
Saturday holidays are observed Friday; Sunday holidays are observed Monday.
This does not model early closes (for example the day after Thanksgiving).
Those afternoons are treated as full sessions, which is a small bias for
intraday strategies and irrelevant for daily bars.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from functools import lru_cache
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
RTH_OPEN = time(9, 30)
RTH_CLOSE = time(16, 0)
# Swing scan window after the cash close.
AFTER_CLOSE_START = time(16, 5)
AFTER_CLOSE_END = time(18, 0)


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """weekday: Monday=0. n is 1-based."""
    first = date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return first + timedelta(days=offset + 7 * (n - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    if month == 12:
        cursor = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        cursor = date(year, month + 1, 1) - timedelta(days=1)
    while cursor.weekday() != weekday:
        cursor -= timedelta(days=1)
    return cursor


def easter_sunday(year: int) -> date:
    """Anonymous Gregorian computus."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def _observe(day: date) -> date:
    if day.weekday() == 5:  # Saturday
        return day - timedelta(days=1)
    if day.weekday() == 6:  # Sunday
        return day + timedelta(days=1)
    return day


@lru_cache(maxsize=64)
def nyse_holidays(year: int) -> frozenset[date]:
    holidays = {
        _observe(date(year, 1, 1)),
        _nth_weekday(year, 1, 0, 3),  # MLK, third Monday
        _nth_weekday(year, 2, 0, 3),  # Washington's Birthday, third Monday
        easter_sunday(year) - timedelta(days=2),  # Good Friday
        _last_weekday(year, 5, 0),  # Memorial Day
        _observe(date(year, 6, 19)),  # Juneteenth
        _observe(date(year, 7, 4)),
        _nth_weekday(year, 9, 0, 1),  # Labor Day
        _nth_weekday(year, 11, 3, 4),  # Thanksgiving, fourth Thursday
        _observe(date(year, 12, 25)),
    }
    # If New Year's Day falls on Saturday, the Friday observance is in the
    # prior year. If it falls on Sunday, Monday Jan 2 is in this year via
    # _observe. Also include Jan 1 of next year observed back into this year.
    next_new_year = date(year + 1, 1, 1)
    if next_new_year.weekday() == 5:
        holidays.add(date(year, 12, 31))
    return frozenset(holidays)


def is_trading_day(day: date) -> bool:
    if day.weekday() >= 5:
        return False
    return day not in nyse_holidays(day.year)


def session_bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, RTH_OPEN, tzinfo=NY)
    end = datetime.combine(day, RTH_CLOSE, tzinfo=NY)
    return start, end


def to_ny(moment: datetime) -> datetime:
    if moment.tzinfo is None:
        return moment.replace(tzinfo=NY)
    return moment.astimezone(NY)


def is_regular_hours(moment: datetime) -> bool:
    local = to_ny(moment)
    if not is_trading_day(local.date()):
        return False
    return RTH_OPEN <= local.time() < RTH_CLOSE


def is_after_close_scan(moment: datetime) -> bool:
    local = to_ny(moment)
    if not is_trading_day(local.date()):
        return False
    return AFTER_CLOSE_START <= local.time() < AFTER_CLOSE_END


def next_trading_day(day: date) -> date:
    cursor = day + timedelta(days=1)
    while not is_trading_day(cursor):
        cursor += timedelta(days=1)
    return cursor


def previous_trading_days(day: date, count: int, include_self: bool = True) -> list[date]:
    """Return up to ``count`` sessions ending at ``day`` (or the prior session)."""
    found: list[date] = []
    cursor = day if include_self else day - timedelta(days=1)
    # Walk back far enough to cover weekends and holiday clusters.
    guard = 0
    while len(found) < count and guard < count * 5 + 14:
        if is_trading_day(cursor):
            found.append(cursor)
        cursor -= timedelta(days=1)
        guard += 1
    found.reverse()
    return found


def trading_days_between(start: date, end: date) -> list[date]:
    days: list[date] = []
    cursor = start
    while cursor <= end:
        if is_trading_day(cursor):
            days.append(cursor)
        cursor += timedelta(days=1)
    return days
