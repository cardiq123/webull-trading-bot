"""Signal-frame helpers. Columns are the contract with the backtester."""

from __future__ import annotations

import numpy as np
import pandas as pd

from webull_bot.calendar import next_trading_day

COLUMNS = [
    "entry_next_open",
    "entry_this_open",
    "exit_next_open",
    "exit_this_close",
    "stop_price",
    "take_profit",
    "max_hold",
]


def blank(index: pd.Index) -> pd.DataFrame:
    frame = pd.DataFrame(index=index)
    frame["entry_next_open"] = False
    frame["entry_this_open"] = False
    frame["exit_next_open"] = False
    frame["exit_this_close"] = False
    frame["stop_price"] = np.nan
    frame["take_profit"] = np.nan
    frame["max_hold"] = np.nan
    return frame


def limit_symbols(bars: dict[str, pd.DataFrame], params: dict) -> dict[str, pd.DataFrame]:
    """Keep only the symbols the caller named.

    Regime inputs such as ``^VIX`` stay out of the trade loop when they are
    not listed. Callers that need a hurdle series (BIL) put it in the list.
    """
    allowed = params.get("symbols")
    if not allowed:
        return {symbol: frame for symbol, frame in bars.items() if not str(symbol).startswith("^")}
    allow = set(allowed)
    return {symbol: bars[symbol] for symbol in sorted(allow) if symbol in bars}


def month_end_mask(index: pd.DatetimeIndex) -> pd.Series:
    """True on the last NYSE session of each calendar month.

    Uses the exchange calendar, not the next row in the file, so a truncated
    sample cannot relabel today's date by peeking at a future bar.
    """
    flags = []
    for ts in index:
        day = pd.Timestamp(ts).date()
        nxt = next_trading_day(day)
        flags.append((nxt.year, nxt.month) != (day.year, day.month))
    return pd.Series(flags, index=index)
