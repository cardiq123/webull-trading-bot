"""CSV bars for offline tests and for data the owner already has.

Each file is named ``{SYMBOL}.csv`` (use ``_VIX.csv`` for ``^VIX``) with a
timestamp index and open, high, low, close, volume columns.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd

from webull_bot.data.base import DataProvider, normalize_frame


class CSVProvider(DataProvider):
    def __init__(self, directory: str | Path) -> None:
        self.directory = Path(directory)

    def history(
        self,
        symbols: Iterable[str],
        start: str,
        end: str,
        interval: str = "1d",
    ) -> dict[str, pd.DataFrame]:
        frames: dict[str, pd.DataFrame] = {}
        start_ts = pd.Timestamp(start)
        end_ts = pd.Timestamp(end)
        for symbol in symbols:
            safe = symbol.replace("^", "_")
            path = self.directory / f"{safe}.csv"
            if not path.exists():
                path = self.directory / f"{symbol}.csv"
            if not path.exists():
                continue
            frame = pd.read_csv(path, index_col=0, parse_dates=True)
            frame = normalize_frame(frame, interval)
            if interval == "1d":
                frame = frame.loc[(frame.index >= start_ts) & (frame.index <= end_ts)]
            frames[symbol] = frame
        return frames
