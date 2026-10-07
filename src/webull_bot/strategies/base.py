"""Strategy interface.

``generate`` may use the full frame it is given. Callers cut the frame at
the end of the evaluation window so the future is not in the file. Every
indicator inside a strategy must be causal: a value on date t depends only
on rows at or before t. Tests truncate the frame and require the overlapping
signals to match.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import pandas as pd


class Strategy(ABC):
    name: str
    citation: str
    style: str  # "day" or "swing"
    holds_overnight: bool
    survivorship_sensitive: bool
    # Free hourly history is about two years. Those tests cannot support a
    # durable-edge claim even when the numbers are positive.
    short_sample: bool = False
    # Set when the strategy brings its own point-in-time universe and must
    # not be scored on the ETF book or the 2026 survivor stock list.
    custom_universe: bool = False
    trail_pct: float | None = None
    default_params: dict[str, Any]

    @abstractmethod
    def universe(self, mode: str) -> list[str]:
        """Symbols this strategy wants. ``mode`` is ``etf`` or ``stock``."""

    @abstractmethod
    def generate(
        self,
        bars: dict[str, pd.DataFrame],
        regime: pd.DataFrame,
        params: dict[str, Any],
    ) -> dict[str, pd.DataFrame]:
        """Return a signal frame per symbol."""

    def param_grid(self) -> list[dict[str, Any]]:
        return [dict(self.default_params)]
