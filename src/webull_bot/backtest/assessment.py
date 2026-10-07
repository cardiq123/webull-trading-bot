"""Rules for calling a backtest an edge.

A strategy is selectable only when the published default parameters make
money out of sample, the walk-forward parameter choices do not flip the
sign, the parameter grid is not fragile, the free-data sample is long
enough, and the test is not dominated by survivorship. These gates are
deliberately strict. Failing them is a result, not a bug.
"""

from __future__ import annotations

from typing import Any, Optional


def profit_factor_value(metrics: dict[str, Any]) -> float:
    value = metrics.get("profit_factor")
    if value is None:
        return 999.0 if metrics.get("trades", 0) and metrics.get("expectancy", 0) > 0 else 0.0
    return float(value)


def fragile_grid(train_sharpes: list[float]) -> bool:
    """True when the in-sample grid does not agree with itself."""
    if len(train_sharpes) < 2:
        return False
    positive = sum(1 for value in train_sharpes if value > 0.0)
    if positive / len(train_sharpes) < 0.5:
        return True
    ordered = sorted(train_sharpes)
    median = ordered[len(ordered) // 2]
    best = max(train_sharpes)
    # A single spike far above the median is a classic overfit shape.
    if best > 0.5 and median <= 0:
        return True
    if median > 0 and best > max(1.0, median * 3.0):
        return True
    return False


def overfit_flags(
    *,
    default_oos: dict[str, Any],
    walk_forward: dict[str, Any],
    train_sharpes: list[float],
    survivorship_sensitive: bool,
    short_sample: bool,
    min_trades: int = 20,
) -> list[str]:
    flags: list[str] = []
    if short_sample:
        flags.append("short_sample")
    if survivorship_sensitive:
        flags.append("survivorship_bias")
    if fragile_grid(train_sharpes):
        flags.append("parameter_fragile")
    if default_oos.get("trades", 0) < min_trades:
        flags.append("insufficient_trades")
    profit_factor = profit_factor_value(default_oos)
    if profit_factor < 1.0:
        flags.append("oos_profit_factor_below_1")
    elif profit_factor < 1.10:
        flags.append("oos_profit_factor_below_1_10")
    sharpe = float(default_oos.get("sharpe") or 0.0)
    if sharpe < 0:
        flags.append("oos_sharpe_negative")
    elif sharpe < 0.40:
        flags.append("oos_sharpe_below_0_40")
    if float(default_oos.get("max_drawdown") or 0.0) < -0.30:
        flags.append("oos_drawdown_beyond_30")
    if walk_forward.get("sharpe", 0.0) < 0 < default_oos.get("sharpe", 0.0):
        flags.append("walk_forward_sign_flip")
    is_sharpe = max(train_sharpes) if train_sharpes else 0.0
    oos_sharpe = float(default_oos.get("sharpe") or 0.0)
    if is_sharpe > 1.0 and oos_sharpe < 0.25 * is_sharpe:
        flags.append("sharpe_decay")
    return flags


def is_selectable(flags: list[str], default_oos: dict[str, Any], *, min_trades: int = 20) -> bool:
    blocking = {
        "short_sample",
        "survivorship_bias",
        "parameter_fragile",
        "insufficient_trades",
        "oos_profit_factor_below_1",
        "oos_profit_factor_below_1_10",
        "oos_sharpe_negative",
        "oos_sharpe_below_0_40",
        "oos_drawdown_beyond_30",
        "walk_forward_sign_flip",
        "sharpe_decay",
        "cost_fragile",
    }
    if any(flag in blocking for flag in flags):
        return False
    if default_oos.get("trades", 0) < min_trades:
        return False
    if profit_factor_value(default_oos) < 1.10:
        return False
    if float(default_oos.get("sharpe") or 0.0) < 0.40:
        return False
    if float(default_oos.get("max_drawdown") or 0.0) < -0.30:
        return False
    return True


def pick_params(rows: list[dict[str, Any]], default: dict[str, Any], min_trades: int = 15) -> dict[str, Any]:
    """Choose parameters from in-sample rows only.

    Each row needs ``params``, ``sharpe``, ``profit_factor``, and ``trades``.
    """
    eligible = [row for row in rows if int(row.get("trades") or 0) >= min_trades]
    pool = eligible or rows
    if not pool:
        return dict(default)

    def sort_key(row: dict[str, Any]) -> tuple[float, float]:
        sharpe = float(row.get("sharpe") or 0.0)
        profit_factor = row.get("profit_factor")
        pf = float(profit_factor) if profit_factor is not None else 0.0
        return (sharpe, pf)

    best = max(pool, key=sort_key)
    if int(best.get("trades") or 0) < min_trades:
        return dict(default)
    return dict(best["params"])
