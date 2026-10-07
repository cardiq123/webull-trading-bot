"""Frozen exit grid for the bounce and for setups A-D.

The cells were fixed before the book was scored. A row that beats the
level-target baseline is a label. It does not change the gate, and it is
not added to the strategy registry. Nothing here places an order.
"""

from __future__ import annotations

TRAIL_PCTS = (0.05, 0.10, 0.15)
TRAIL_ATRS = (1.5, 2.0, 3.0)
BRACKET_RS = (1.5, 2.0, 3.0)
HYBRID_FALLBACK_R = 1.0
HYBRID_ATR = 2.0
WINS_MIN_TRADES = 20
WINS_DD_SLACK = 0.05


def exit_grid(base: dict) -> list[tuple[str, dict]]:
    """Level baseline, then the trail, bracket, and hybrid cells, in tie-break order.

    ``base`` supplies the hold, the account, and the book's fallback reward.
    The hybrid cell replaces that fallback with 1R. A missing level still
    uses the simulator's 0.5R floor before that fallback.
    """
    rows: list[tuple[str, dict]] = []
    level = dict(base)
    level.pop("exit_style", None)
    level["trail"] = "none"
    level["target_mode"] = "level"
    level["level_source"] = "reference"
    rows.append(("level target", level))
    for pct in TRAIL_PCTS:
        cell = dict(base)
        cell["exit_style"] = "trail_pct"
        cell["trail_pct"] = float(pct)
        cell["trail"] = "none"
        rows.append((f"trail {pct:.0%}", cell))
    for multiple in TRAIL_ATRS:
        cell = dict(base)
        cell["exit_style"] = "trail_atr"
        cell["trail_atr"] = float(multiple)
        cell["trail"] = "none"
        rows.append((f"trail {multiple:g} ATR", cell))
    for reward in BRACKET_RS:
        cell = dict(base)
        cell.pop("exit_style", None)
        cell["trail"] = "none"
        cell["target_mode"] = "r"
        cell["reward_r"] = float(reward)
        rows.append((f"bracket {reward:g}R", cell))
    hybrid = dict(base)
    hybrid["exit_style"] = "hybrid"
    hybrid["trail"] = "none"
    hybrid["target_mode"] = "level"
    hybrid["level_source"] = "reference"
    hybrid["reward_r"] = HYBRID_FALLBACK_R
    hybrid["trail_atr"] = HYBRID_ATR
    rows.append(("hybrid half at level, trail 2 ATR", hybrid))
    return rows


def _profit_factor(metrics: dict) -> float:
    value = metrics.get("profit_factor")
    if value is None:
        return float("inf")
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float("inf")
    if number != number:
        return float("inf")
    return number


def beats_baseline(baseline: dict, candidate: dict) -> bool:
    """Out-of-sample stock rule. Options do not call this.

    The candidate needs a strictly higher expectancy, a profit factor that
    is not lower, a max drawdown no more than five points worse, and at
    least 20 trades.
    """
    trades = int(candidate.get("trades") or 0)
    if trades < WINS_MIN_TRADES:
        return False
    if float(candidate.get("expectancy") or 0.0) <= float(baseline.get("expectancy") or 0.0):
        return False
    if _profit_factor(candidate) < _profit_factor(baseline):
        return False
    base_dd = float(baseline.get("max_drawdown") or 0.0)
    cand_dd = float(candidate.get("max_drawdown") or 0.0)
    if cand_dd < base_dd - WINS_DD_SLACK:
        return False
    return True


def select_winner(rows: list[tuple[str, dict]]) -> str:
    """Highest out-of-sample expectancy among rows that beat the first row.

    Ties keep the earlier cell. If none beat the level target, that label
    stays. ``rows`` must be the stock book, in ``exit_grid`` order.
    """
    if not rows:
        return "level target"
    baseline_label, baseline = rows[0]
    chosen = baseline_label
    best = None
    for label, metrics in rows[1:]:
        if not beats_baseline(baseline, metrics):
            continue
        expectancy = float(metrics.get("expectancy") or 0.0)
        if best is None or expectancy > best:
            best = expectancy
            chosen = label
    return chosen
