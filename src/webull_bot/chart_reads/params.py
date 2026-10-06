"""Pre-registered chart-read rules.

The gate scores ``DEFAULTS``. Walk-forward may pick another cell in ``grid``
from the training window only. DTE, delta, spread width, risk fraction, IV,
the bid/ask haircut, and the reward multiple are sensitivities. They are
not grid cells. Definitions were frozen to the three annotated sessions
before any P&L was scored.
"""

from __future__ import annotations

# 5-minute is the primary clock, matching the annotated charts.
# 15-minute is the same rules on the slower bar. 60-minute is the long sample.
DEFAULTS: dict = {
    "k_sep": 0.25,
    "require_ema200": False,
    "setup_a": True,
    "setup_b": True,
    "strong_body": 0.50,
    "strong_close_frac": 2.0 / 3.0,
    "touch_atr": 0.50,
    # A retest has to give back at least this many ATRs from the impulse
    # extreme. A one-bar tag of a rising 9 EMA is not the pullback on the charts.
    "min_retrace_atr": 0.50,
    "pullback_bars": 8,
    "breakout_lookback": 6,
    "cross_bars": 12,
    "band_std": 2.0,
    "rsi_filter": False,
    "macd_filter": False,
    "morning_only": False,
    "avoid_extended": False,
    "reward_r": 2.0,
    "trail": "ema20",
    "flatten_eod": True,
    "max_hold_sessions": 1,
    "risk_fraction": 0.20,
    "max_positions": 1,
    "account": "margin_pdt",
    "expression": "single",
    "delta": 0.45,
    "dte": 3,
    "spread_width": 2.0,
    "spread_dte": 10,
    "iv_premium": 1.15,
    "spread_multiplier": 1.0,
    "execution": "5m",
}

# Signal rules only. One change from the default per cell.
_GRID_KEYS = (
    ("k_sep", 0.10),
    ("k_sep", 0.50),
    ("require_ema200", True),
    ("morning_only", True),
    ("rsi_filter", True),  # paired with macd below
    ("avoid_extended", True),
)


def grid() -> list[dict]:
    cells = [dict(DEFAULTS)]
    for key, value in _GRID_KEYS:
        cell = dict(DEFAULTS)
        cell[key] = value
        if key == "rsi_filter":
            cell["macd_filter"] = True
        cells.append(cell)
    return cells


def htf_allows(labels: list[str], direction: str, kind: str) -> bool:
    """Higher-timeframe gate.

    Continuation (A) needs a strict majority of the frames that have a read.
    The failed-breakout cross (B) is allowed unless every one of those frames
    is a clean trend the other way. A mixed frame is not a clean opposite,
    which is what lets the UNH short through while SPY's unanimous uptrend
    would block a short.
    """
    real = [label for label in labels if label in ("up", "down", "mixed")]
    if kind == "B":
        opposite = "down" if direction == "long" else "up"
        if real and all(label == opposite for label in real):
            return False
        return True
    if not real:
        return False
    needed = (len(real) // 2) + 1
    want = "up" if direction == "long" else "down"
    return sum(label == want for label in real) >= needed
