"""Hourly chop-v2 box breakout, frozen to the scored 60-minute book.

The signal is ``find_chop_breakouts`` with no cell override: relative volume
strictly above 1.5, a confirming candle, and the default chop-v2 box. The
exit scored on that row is a 15% trail and the 60-minute precursor hold:
five sessions, not flattened at the cash close. This module does not place
an order. The sandbox forward test does that, and only there.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from webull_bot.chart_reads.chop import EXPAND_VOLUME
from webull_bot.chart_reads.chop_v2 import find_chop_breakouts
from webull_bot.chart_reads.detect import Setup
from webull_bot.chart_reads.liquid import LIQUID_BLUE_CHIPS
from webull_bot.chart_reads.research import SYMBOLS
from webull_bot.mtf_vwap.detect import rth
from webull_bot.strategies.base import Strategy

# The 60-minute precursor in research_chop._precursor_params. Not a new grid.
TRAIL_PCT = 0.15
MAX_HOLD_SESSIONS = 5
FLATTEN_EOD = False


class ChopBreakout60m(Strategy):
    name = "chop_breakout_60m"
    citation = (
        "Chop-v2 box breakout on 60-minute bars. Frozen default from the "
        "qualitative chop reading. The scored exit is a 15% trail."
    )
    style = "swing"
    holds_overnight = True
    survivorship_sensitive = True
    short_sample = True
    forward_only = True
    custom_universe = False
    trail_pct = TRAIL_PCT
    default_params: dict[str, Any] = {
        "exit_style": "trail_pct",
        "trail_pct": TRAIL_PCT,
        "trail": "none",
        "expression": "stock",
        "flatten_eod": FLATTEN_EOD,
        "max_hold_sessions": MAX_HOLD_SESSIONS,
        "expand_volume": EXPAND_VOLUME,
        "symbols": list(SYMBOLS),
    }

    def universe(self, mode: str) -> list[str]:
        return list(SYMBOLS)

    def generate(
        self,
        bars: dict[str, pd.DataFrame],
        regime: pd.DataFrame,
        params: dict[str, Any],
    ) -> dict[str, pd.DataFrame]:
        """The daily live loop does not trade this book. The forward cycle calls ``scan``."""
        return {}

    def scan(self, frames: dict[str, pd.DataFrame]) -> list[Setup]:
        """Share-book breakouts. The named list stays the frozen share universe."""
        return _scan_symbols(frames, SYMBOLS)

    def scan_options(self, frames: dict[str, pd.DataFrame]) -> list[Setup]:
        """Option-book breakouts on the pre-registered liquid list."""
        return scan_option_breakouts(frames)


def _scan_symbols(frames: dict[str, pd.DataFrame], symbols: tuple[str, ...] | list[str]) -> list[Setup]:
    """Breakouts on the frames as given. The caller keeps the forming bar.

    ``find_chop_breakouts`` needs the next bar in the frame, and it uses
    the frozen default cell when ``cell`` is omitted.
    """
    found: list[Setup] = []
    for symbol in symbols:
        frame = frames.get(symbol)
        if frame is None or frame.empty:
            continue
        bars = rth(frame)
        if bars is None or len(bars) < 3:
            continue
        found.extend(find_chop_breakouts(bars, symbol=symbol))
    found.sort(key=lambda setup: (pd.Timestamp(setup.signal_time), setup.symbol, setup.direction))
    return found


def scan_option_breakouts(frames: dict[str, pd.DataFrame]) -> list[Setup]:
    """Chop-v2 box breakouts on ``LIQUID_BLUE_CHIPS`` only."""
    return _scan_symbols(frames, LIQUID_BLUE_CHIPS)
