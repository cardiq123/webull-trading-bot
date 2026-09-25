"""Performance statistics from an equity curve and a trade list.

Sharpe and Sortino use session-close equity returns, annualized with
sqrt(252), and a zero risk-free rate. They describe the path that was
tested. They are not a forecast.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from webull_bot.backtest.engine import BacktestResult


def _finite(value: float) -> float | None:
    if value is None or not math.isfinite(value):
        return None
    return float(value)


def compute_metrics(result: BacktestResult, starting_equity: float) -> dict[str, Any]:
    daily = result.daily_equity()
    empty = {
        "starting_equity": starting_equity,
        "ending_equity": starting_equity,
        "total_return": 0.0,
        "cagr": 0.0,
        "sharpe": 0.0,
        "sortino": 0.0,
        "max_drawdown": 0.0,
        "exposure": 0.0,
        "trades": 0,
        "win_rate": 0.0,
        "avg_win": 0.0,
        "avg_loss": 0.0,
        "profit_factor": None,
        "expectancy": 0.0,
        "years": 0.0,
    }
    if daily.empty:
        return empty
    # daily_equity's first point is the first session close, which already
    # includes that session's P&L. Prefix the starting capital so return
    # math has a base.
    curve = pd.concat(
        [pd.Series([starting_equity], index=[daily.index[0] - pd.Timedelta(days=1)]), daily]
    )
    ending = float(curve.iloc[-1])
    elapsed_days = max((curve.index[-1] - curve.index[0]).days, 1)
    years = elapsed_days / 365.25
    total_return = ending / starting_equity - 1.0
    cagr = (ending / starting_equity) ** (1.0 / years) - 1.0 if ending > 0 else -1.0
    rets = curve.pct_change().dropna()
    std = float(rets.std(ddof=0)) if len(rets) else 0.0
    sharpe = float(rets.mean() / std * math.sqrt(252)) if std > 0 else 0.0
    downside = rets.clip(upper=0.0)
    down_dev = float(math.sqrt(float((downside ** 2).mean()))) if len(rets) else 0.0
    sortino = float(rets.mean() / down_dev * math.sqrt(252)) if down_dev > 0 else 0.0
    peak = curve.cummax()
    drawdown = curve / peak - 1.0
    max_dd = float(drawdown.min()) if len(drawdown) else 0.0
    exposure = float(result.exposure.mean()) if len(result.exposure) else 0.0

    trades = result.trades
    count = int(len(trades)) if trades is not None else 0
    win_rate = 0.0
    avg_win = 0.0
    avg_loss = 0.0
    profit_factor: float | None = None
    expectancy = 0.0
    if count:
        pnl = trades["pnl"].astype(float)
        wins = pnl[pnl > 0]
        losses = pnl[pnl < 0]
        win_rate = float(len(wins) / count)
        avg_win = float(wins.mean()) if len(wins) else 0.0
        avg_loss = float(losses.mean()) if len(losses) else 0.0
        gross_loss = float(-losses.sum()) if len(losses) else 0.0
        gross_win = float(wins.sum()) if len(wins) else 0.0
        if gross_loss > 0:
            profit_factor = gross_win / gross_loss
        elif gross_win > 0:
            profit_factor = None
        else:
            profit_factor = 0.0
        expectancy = float(pnl.mean())

    return {
        "starting_equity": starting_equity,
        "ending_equity": ending,
        "total_return": total_return,
        "cagr": cagr,
        "sharpe": sharpe,
        "sortino": sortino,
        "max_drawdown": max_dd,
        "exposure": exposure,
        "trades": count,
        "win_rate": win_rate,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "profit_factor": _finite(profit_factor) if profit_factor is not None else None,
        "expectancy": expectancy,
        "years": years,
    }


def buy_and_hold_metrics(
    close: pd.Series,
    open_: pd.Series,
    *,
    starting_equity: float,
    trade_start: pd.Timestamp,
    trade_end: pd.Timestamp,
    slippage_bps: float,
) -> dict[str, Any]:
    """Buy the first open on or after ``trade_start`` and sell the last close."""
    window_open = open_.loc[(open_.index >= trade_start) & (open_.index <= trade_end)].dropna()
    window_close = close.loc[(close.index >= trade_start) & (close.index <= trade_end)].dropna()
    if window_open.empty or window_close.empty:
        return compute_metrics(
            BacktestResult(pd.Series(dtype=float), pd.Series(dtype=float), pd.DataFrame()),
            starting_equity,
        )
    bump = slippage_bps / 10_000.0
    entry = float(window_open.iloc[0]) * (1.0 + bump)
    exit_ = float(window_close.iloc[-1]) * (1.0 - bump)
    shares = math.floor(starting_equity / entry)
    if shares < 1:
        shares = starting_equity / entry
    cash = starting_equity - shares * entry
    equity = window_close.astype(float) * shares + cash
    # Mark the entry session at the fill, then the closes.
    equity.iloc[0] = cash + shares * entry
    exposure = pd.Series(1.0, index=equity.index)
    trades = pd.DataFrame(
        [
            {
                "symbol": "SPY",
                "strategy": "buy_and_hold",
                "quantity": shares,
                "entry_time": window_open.index[0],
                "entry_price": entry,
                "exit_time": window_close.index[-1],
                "exit_price": exit_,
                "pnl": (exit_ - entry) * shares,
                "fees": 0.0,
                "reason": "window_end",
                "bars_held": len(window_close),
            }
        ]
    )
    # Rebuild the last point at the exited price so the curve matches the trade.
    equity.iloc[-1] = cash + shares * exit_
    result = BacktestResult(equity=equity, exposure=exposure, trades=trades, ending_equity=float(equity.iloc[-1]))
    return compute_metrics(result, starting_equity)
