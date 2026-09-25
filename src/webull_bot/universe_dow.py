"""Point-in-time Dow Jones Industrial Average membership.

The lists follow the effective dates in Wikipedia's "Historical components
of the Dow Jones Industrial Average" (summary of changes since 1991, checked
against the component tables). A name can be traded only while it is in the
index. Names that were removed (GE, Exxon Mobil, Intel, Walgreens, and the
others below) stay in the file for the dates they were members, which is
the point of a point-in-time universe.

This is not a 2026 survivor snapshot. It is still not the whole market:
the Dow is a 30-name committee index, Yahoo's adjusted history can splice
mergers (DD, DWDP, UTX/RTX, KFT), and a ticker with no Yahoo history is
simply missing for its window.
"""

from __future__ import annotations

from datetime import date

# Effective 2009-06-08, after Travelers and Cisco replaced GM and Citigroup.
_BASE_DATE = date(2009, 6, 8)
_BASE = (
    "MMM", "AA", "AXP", "T", "BAC", "BA", "CAT", "CVX", "CSCO", "KO",
    "DD", "XOM", "GE", "HPQ", "HD", "INTC", "IBM", "JNJ", "JPM", "KFT",
    "MCD", "MRK", "MSFT", "PFE", "PG", "TRV", "UTX", "VZ", "WMT", "DIS",
)

# (effective date, added, removed). Applied at the start of that session.
_CHANGES: tuple[tuple[date, tuple[str, ...], tuple[str, ...]], ...] = (
    (date(2012, 9, 24), ("UNH",), ("KFT",)),
    (date(2013, 9, 23), ("GS", "NKE", "V"), ("AA", "BAC", "HPQ")),
    (date(2015, 3, 19), ("AAPL",), ("T",)),
    (date(2017, 9, 1), ("DWDP",), ("DD",)),
    (date(2018, 6, 26), ("WBA",), ("GE",)),
    (date(2019, 4, 2), ("DOW",), ("DWDP",)),
    (date(2020, 4, 6), ("RTX",), ("UTX",)),
    (date(2020, 8, 31), ("AMGN", "HON", "CRM"), ("XOM", "PFE", "RTX")),
    (date(2024, 2, 26), ("AMZN",), ("WBA",)),
    (date(2024, 11, 8), ("NVDA", "SHW"), ("INTC", "DOW")),
    (date(2026, 6, 29), ("GOOGL",), ("VZ",)),
)

DOW_SECTORS: dict[str, str] = {
    "MMM": "industrials", "AA": "materials", "AXP": "financials", "T": "communication",
    "BAC": "financials", "BA": "industrials", "CAT": "industrials", "CVX": "energy",
    "CSCO": "technology", "KO": "staples", "DD": "materials", "XOM": "energy",
    "GE": "industrials", "HPQ": "technology", "HD": "discretionary", "INTC": "technology",
    "IBM": "technology", "JNJ": "health", "JPM": "financials", "KFT": "staples",
    "MCD": "discretionary", "MRK": "health", "MSFT": "technology", "PFE": "health",
    "PG": "staples", "TRV": "financials", "UTX": "industrials", "VZ": "communication",
    "WMT": "staples", "DIS": "communication", "UNH": "health", "GS": "financials",
    "NKE": "discretionary", "V": "financials", "AAPL": "technology", "DWDP": "materials",
    "WBA": "staples", "DOW": "materials", "RTX": "industrials", "AMGN": "health",
    "HON": "industrials", "CRM": "technology", "AMZN": "discretionary",
    "NVDA": "technology", "SHW": "materials", "GOOGL": "communication",
}

# end is exclusive
_INTERVALS: dict[str, list[tuple[date, date]]] = {}


def _build() -> None:
    current = set(_BASE)
    opened = {symbol: _BASE_DATE for symbol in current}
    intervals: dict[str, list[tuple[date, date]]] = {symbol: [] for symbol in DOW_SECTORS}
    for day, added, removed in _CHANGES:
        for symbol in removed:
            intervals.setdefault(symbol, []).append((opened[symbol], day))
            current.remove(symbol)
        for symbol in added:
            opened[symbol] = day
            current.add(symbol)
    for symbol in current:
        intervals.setdefault(symbol, []).append((opened[symbol], date(2100, 1, 1)))
    _INTERVALS.clear()
    _INTERVALS.update(intervals)


_build()


def all_dow_tickers() -> list[str]:
    return sorted(_INTERVALS)


def members_on(day: date) -> list[str]:
    return sorted(
        symbol
        for symbol, spans in _INTERVALS.items()
        if any(start <= day < stop for start, stop in spans)
    )


def is_member(symbol: str, day: date) -> bool:
    return any(start <= day < stop for start, stop in _INTERVALS.get(symbol, ()))
