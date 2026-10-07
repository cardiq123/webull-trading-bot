"""Data provider interface.

Bars are a DataFrame indexed by timestamp with columns
open, high, low, close, volume. Daily indexes are timezone-naive dates.
Intraday indexes are timezone-aware America/New_York.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable

import pandas as pd


class DataProvider(ABC):
    @abstractmethod
    def history(
        self,
        symbols: Iterable[str],
        start: str,
        end: str,
        interval: str = "1d",
    ) -> dict[str, pd.DataFrame]:
        """Return historical bars. Missing symbols are omitted."""

    def latest(
        self,
        symbols: Iterable[str],
        interval: str = "1d",
        lookback_days: int = 400,
    ) -> dict[str, pd.DataFrame]:
        end = pd.Timestamp.utcnow().tz_localize(None) + pd.Timedelta(days=1)
        start = end - pd.Timedelta(days=lookback_days)
        return self.history(symbols, start.date().isoformat(), end.date().isoformat(), interval)


def normalize_frame(frame: pd.DataFrame, interval: str) -> pd.DataFrame:
    renamed = frame.copy()
    renamed.columns = [str(column).lower().replace(" ", "_") for column in renamed.columns]
    needed = ["open", "high", "low", "close", "volume"]
    missing = [column for column in needed if column not in renamed.columns]
    if missing:
        raise ValueError(f"Bars missing columns {missing}")
    out = renamed[needed].apply(pd.to_numeric, errors="coerce")
    out = out.dropna(subset=["close"])
    if isinstance(out.index, pd.DatetimeIndex):
        index = out.index
    else:
        index = pd.to_datetime(out.index, utc=interval != "1d")
    if interval == "1d":
        if getattr(index, "tz", None) is not None:
            index = index.tz_convert("America/New_York").tz_localize(None)
        out.index = index.normalize()
    else:
        if getattr(index, "tz", None) is None:
            index = index.tz_localize("America/New_York")
        else:
            index = index.tz_convert("America/New_York")
        out.index = index
        minutes = out.index.hour * 60 + out.index.minute
        # Regular session, 09:30 inclusive through 16:00 exclusive.
        keep = (minutes >= 9 * 60 + 30) & (minutes < 16 * 60)
        out = out.loc[keep]
    out = out[~out.index.duplicated(keep="last")].sort_index()
    return out
