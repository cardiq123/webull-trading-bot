"""Pre-registered default and the small grid.

The gate scores ``DEFAULTS`` only. Walk-forward may pick another cell in
``GRID`` from the training window. DTE, delta, the premium target, and the
premium stop are sensitivities. They are not grid cells.
"""

from __future__ import annotations

# Execution is 15m in the short sample and 60m in the long sample.
# Trend frames for 15m: weekly, daily, 60m, 15m, 5m.
# Trend frames for 60m: weekly, daily, 60m. 15m and 5m are not in that file.
DEFAULTS: dict = {
    "alignment": "all",
    "ema_intraday": 20,
    "ema_daily": 20,
    "pivot_left": 2,
    "pivot_right": 2,
    "zone_atr": 0.5,
    "require_zone": True,
    "use_trendline": False,
    "vwap_tolerance_atr": 0.15,
    "touch_atr": 0.05,
    "use_bands": False,
    "confirm": "next",
    "require_5m_reclaim": False,
    "delta": 0.50,
    "dte": 14,
    "flatten_eod": False,
    "premium_stop": -0.50,
    "premium_target": 0.50,
    "use_level_target": True,
    "max_hold_sessions": 2,
    "premium_cap": 0.25,
    "max_positions": 1,
    "account": "margin_pdt",
    "iv_premium": 1.15,
    "spread_multiplier": 1.0,
    "execution": "15m",
}


def grid() -> list[dict]:
    """One change from the default per cell, plus the default."""
    cells = [dict(DEFAULTS)]
    for key, value in (
        ("alignment", "majority"),
        ("ema_daily", 10),
        ("require_zone", False),
        ("use_trendline", True),
        ("confirm", "same"),
        ("use_bands", True),
    ):
        cell = dict(DEFAULTS)
        cell[key] = value
        cells.append(cell)
    return cells


def majority_needed(n_frames: int) -> int:
    """4 of 5 when every timeframe is present, otherwise a strict majority."""
    if n_frames >= 5:
        return 4
    return (n_frames // 2) + 1
