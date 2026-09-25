"""Static research universe.

The stock list is a 2026 snapshot of liquid names that have been listed for
most of the sample. It is survivorship-biased: names that failed, were
acquired, or left the large-cap set are absent. ETF results are the cleaner
evidence. Sector tags are used only for concentration limits.
"""

from __future__ import annotations

# Sector ETFs and macro ETFs. These are the preferred research universe.
ETF_UNIVERSE: dict[str, str] = {
    "SPY": "broad",
    "QQQ": "broad",
    "IWM": "broad",
    "EFA": "international",
    "EEM": "international",
    "TLT": "bonds",
    "GLD": "metals",
    "BIL": "cash",
    "XLK": "technology",
    "XLF": "financials",
    "XLE": "energy",
    "XLV": "health",
    "XLY": "discretionary",
    "XLP": "staples",
    "XLI": "industrials",
    "XLB": "materials",
    "XLU": "utilities",
}

# Liquid survivors. Treat any edge that appears only here as suspect.
STOCK_UNIVERSE: dict[str, str] = {
    "AAPL": "technology",
    "MSFT": "technology",
    "NVDA": "technology",
    "AVGO": "technology",
    "AMD": "technology",
    "CRM": "technology",
    "AMZN": "discretionary",
    "TSLA": "discretionary",
    "HD": "discretionary",
    "NFLX": "discretionary",
    "GOOGL": "communication",
    "META": "communication",
    "JPM": "financials",
    "BAC": "financials",
    "V": "financials",
    "UNH": "health",
    "JNJ": "health",
    "XOM": "energy",
    "PG": "staples",
    "COST": "staples",
}

VIX_SYMBOL = "^VIX"

DUAL_MOMENTUM_SYMBOLS = ["SPY", "QQQ", "IWM", "EFA", "EEM", "TLT", "GLD", "BIL"]

INTRADAY_SYMBOLS = ["SPY", "QQQ", "AAPL", "MSFT", "NVDA", "AMD", "TSLA", "AMZN"]


def all_sectors() -> dict[str, str]:
    from webull_bot.universe_dow import DOW_SECTORS

    merged = dict(ETF_UNIVERSE)
    merged.update(STOCK_UNIVERSE)
    for symbol, sector in DOW_SECTORS.items():
        merged.setdefault(symbol, sector)
    return merged


def research_symbols() -> list[str]:
    symbols = list(dict.fromkeys([*ETF_UNIVERSE, *STOCK_UNIVERSE, VIX_SYMBOL]))
    return symbols
