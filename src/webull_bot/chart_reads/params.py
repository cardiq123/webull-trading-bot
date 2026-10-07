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


# Daily setup C. Frozen to the UNH June-October 2026 drawing before scoring.
# The line is two confirmed pivot highs. Three touches is a grid variant.
# Rejection shorts are a separate variant, not this default.
DAILY_DEFAULTS: dict = {
    "pivot_left": 4,
    "pivot_right": 4,
    "min_span": 10,
    "max_span": 126,
    # A stale pair stays eligible only when price is still near its line.
    "max_anchor_age": 80,
    "touch_atr": 0.50,
    "break_buffer_atr": 0.25,
    "retest_days": 10,
    "require_three_touches": False,
    "include_long": True,
    "include_short": False,
    "short_cooldown": 5,
    "strong_body": 0.50,
    "strong_close_frac": 2.0 / 3.0,
    "reward_r": 2.0,
    "target_mode": "level",
    "level_source": "reference",
    "trail": "ema20",
    "flatten_eod": False,
    "max_hold_sessions": 30,
    "pdt_prospective": False,
    "risk_fraction": 0.20,
    "max_positions": 1,
    "account": "margin_pdt",
    "expression": "stock",
    "delta": 0.45,
    "dte": 45,
    "spread_width": 5.0,
    "spread_dte": 45,
    "iv_premium": 1.15,
    "spread_multiplier": 1.0,
}

_DAILY_GRID = (
    ("pivot_left", 3, {"pivot_right": 3}),
    ("touch_atr", 0.25, {}),
    ("touch_atr", 1.00, {}),
    ("break_buffer_atr", 0.10, {}),
    ("break_buffer_atr", 0.50, {}),
    ("retest_days", 5, {}),
    ("retest_days", 20, {}),
    ("require_three_touches", True, {}),
)


def daily_grid() -> list[dict]:
    cells = [dict(DAILY_DEFAULTS)]
    for key, value, extra in _DAILY_GRID:
        cell = dict(DAILY_DEFAULTS)
        cell[key] = value
        cell.update(extra)
        cells.append(cell)
    return cells


# Daily setup D, from the three-breakout diagram. Frozen before scoring.
# Descending triangles break down only. Ascending triangles break up only.
# A horizontal range may break either way. Three flat-side touches and a
# retest are grid variants, not the default.
BREAKOUT_DEFAULTS: dict = {
    "pivot_left": 4,
    "pivot_right": 4,
    "min_span": 15,
    "max_span": 80,
    "max_wait": 20,
    "min_flat_touches": 2,
    "min_slope_pivots": 2,
    "touch_atr": 0.50,
    "min_slope_atr": 0.75,
    "min_height_atr": 1.0,
    "max_height_atr": 40.0,
    "break_buffer_atr": 0.25,
    "confirm_bars": 3,
    "require_retest": False,
    "retest_bars": 10,
    "strong_body": 0.50,
    "strong_close_frac": 2.0 / 3.0,
    "reward_r": 2.0,
    "target_mode": "level",
    "level_source": "reference",
    "trail": "ema20",
    "flatten_eod": False,
    "max_hold_sessions": 30,
    "pdt_prospective": False,
    "risk_fraction": 0.20,
    "max_positions": 1,
    "account": "margin_pdt",
    "expression": "stock",
    "delta": 0.45,
    "dte": 45,
    "spread_width": 5.0,
    "spread_dte": 45,
    "iv_premium": 1.15,
    "spread_multiplier": 1.0,
}

_BREAKOUT_GRID = (
    ("pivot_left", 3, {"pivot_right": 3}),
    ("touch_atr", 0.25, {}),
    ("touch_atr", 1.00, {}),
    ("break_buffer_atr", 0.10, {}),
    ("break_buffer_atr", 0.50, {}),
    ("min_flat_touches", 3, {}),
    ("min_span", 10, {}),
    ("min_span", 30, {}),
    ("require_retest", True, {}),
)


def breakout_grid() -> list[dict]:
    cells = [dict(BREAKOUT_DEFAULTS)]
    for key, value, extra in _BREAKOUT_GRID:
        cell = dict(BREAKOUT_DEFAULTS)
        cell[key] = value
        cell.update(extra)
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
