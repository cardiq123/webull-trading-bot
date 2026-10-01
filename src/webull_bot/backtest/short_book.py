"""Research-only short stock book.

The live and paper paths stay long-only. This simulator is the short-stock
baseline for bearish breakouts. It does not send orders. No borrow fee is
charged, which flatters the short book slightly. Opening a short pays the
stock sale friction and regulatory fees. Covering pays the buy friction.
If the bar touches both the stop and the target, the stop fills. A gap
through the stop fills at the open.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from webull_bot.backtest.engine import BacktestResult
from webull_bot.backtest.metrics import compute_metrics
from webull_bot.costs import CostModel, buy_price, sell_price, sell_regulatory_fees


def simulate_shorts(
    signals: dict[str, pd.DataFrame],
    bars: dict[str, pd.DataFrame],
    *,
    costs: CostModel,
    trade_start: pd.Timestamp,
    trade_end: pd.Timestamp,
    starting_equity: float = 100_000.0,
    risk_per_trade: float = 0.0075,
    max_position_pct: float = 0.20,
    max_positions: int = 5,
) -> BacktestResult:
    if "SPY" not in bars:
        return BacktestResult(pd.Series(dtype=float), pd.Series(dtype=float), pd.DataFrame(), ending_equity=starting_equity)
    clock = bars["SPY"].index
    clock = clock[(clock >= pd.Timestamp(trade_start)) & (clock <= pd.Timestamp(trade_end))]
    pending: dict[pd.Timestamp, list[dict[str, Any]]] = {}
    start = pd.Timestamp(trade_start)
    end = pd.Timestamp(trade_end)
    for symbol in sorted(signals):
        frame = signals[symbol]
        if frame is None or "short_next_open" not in frame.columns:
            continue
        flags = frame["short_next_open"].fillna(False).to_numpy(dtype=bool)
        index = frame.index
        for i in range(len(frame) - 1):
            if not flags[i]:
                continue
            fill_time = pd.Timestamp(index[i + 1])
            if fill_time < start or fill_time > end:
                continue
            stop = float(frame["short_stop"].iloc[i]) if "short_stop" in frame.columns else np.nan
            target = float(frame["short_target"].iloc[i]) if "short_target" in frame.columns else np.nan
            pending.setdefault(fill_time, []).append(
                {
                    "symbol": symbol,
                    "stop": stop,
                    "target": target if np.isfinite(target) else None,
                    "max_hold": int(frame["max_hold"].iloc[i]) if "max_hold" in frame.columns else 10,
                    "exit_flags": frame["exit_next_open"].fillna(False).to_numpy(dtype=bool),
                    "signal_i": i,
                    "index": index,
                }
            )
    cash = float(starting_equity)
    positions: list[dict[str, Any]] = []
    trades: list[dict[str, Any]] = []
    equity_values: list[float] = []
    exposure_values: list[float] = []
    index_out: list[pd.Timestamp] = []
    peak = cash
    halted = False

    def mark_to(field: str, ts: pd.Timestamp) -> float:
        total = cash
        for pos in positions:
            frame = bars.get(pos["symbol"])
            if frame is None or ts not in frame.index:
                price = pos["entry_price"]
            else:
                price = float(frame.loc[ts, field])
            total += pos["reserved"] + (pos["entry_price"] - price) * pos["quantity"]
        return total

    for ts in clock:
        ts = pd.Timestamp(ts)
        equity_open = mark_to("open", ts)
        if peak > 0 and (1.0 - equity_open / peak) >= 0.15:
            halted = True
        if not halted:
            for spec in pending.get(ts, []):
                if len(positions) >= max_positions:
                    break
                if any(pos["symbol"] == spec["symbol"] for pos in positions):
                    continue
                frame = bars.get(spec["symbol"])
                if frame is None or ts not in frame.index:
                    continue
                raw = float(frame.loc[ts, "open"])
                stop = spec["stop"]
                if not np.isfinite(raw) or raw <= 0 or not np.isfinite(stop) or stop <= raw:
                    continue
                fill = sell_price(raw, costs)
                if fill >= stop:
                    continue
                distance = stop - fill
                if distance <= 0 or equity_open <= 0 or cash <= 0:
                    continue
                qty = int(min(equity_open * risk_per_trade / distance, equity_open * max_position_pct / fill, cash / fill))
                if qty < 1:
                    continue
                fees = sell_regulatory_fees(fill, qty, costs)
                reserved = fill * qty
                if reserved + fees > cash:
                    continue
                cash -= reserved + fees
                locate = frame.index.get_loc(ts)
                positions.append(
                    {
                        "symbol": spec["symbol"],
                        "quantity": qty,
                        "entry_price": fill,
                        "entry_time": ts,
                        "stop": stop,
                        "target": spec["target"],
                        "max_hold": spec["max_hold"],
                        "entry_fees": fees,
                        "reserved": reserved,
                        "fill_i": int(locate),
                        "exit_flags": spec["exit_flags"],
                        "signal_i": spec["signal_i"],
                        "index": spec["index"],
                        "bars_held": 0,
                    }
                )
                equity_open = mark_to("open", ts)
        still = []
        for pos in positions:
            frame = bars.get(pos["symbol"])
            if frame is None or ts not in frame.index:
                still.append(pos)
                continue
            row = frame.loc[ts]
            bar_open = float(row["open"])
            bar_high = float(row["high"])
            bar_low = float(row["low"])
            bar_close = float(row["close"])
            locate = pos["index"].get_loc(ts) if ts in pos["index"] else pos["fill_i"]
            bar_i = int(locate) if isinstance(locate, (int, np.integer)) else pos["fill_i"]
            reason = None
            raw = None
            if np.isfinite(bar_open) and bar_open >= pos["stop"]:
                reason, raw = "stop", bar_open
            elif np.isfinite(bar_high) and bar_high >= pos["stop"]:
                reason, raw = "stop", pos["stop"]
            elif pos["target"] is not None and np.isfinite(bar_open) and bar_open <= pos["target"]:
                reason, raw = "target", bar_open
            elif pos["target"] is not None and np.isfinite(bar_low) and bar_low <= pos["target"]:
                reason, raw = "target", pos["target"]
            elif bar_i > pos["fill_i"] and bar_i < len(pos["exit_flags"]) and bool(pos["exit_flags"][bar_i]):
                reason, raw = "invalidation", bar_close
            else:
                pos["bars_held"] = bar_i - pos["fill_i"] + 1
                if pos["bars_held"] >= pos["max_hold"]:
                    reason, raw = "max_hold", bar_close
            if reason is None or raw is None or not np.isfinite(raw) or raw <= 0:
                still.append(pos)
                continue
            cover = buy_price(raw, costs)
            cash += pos["reserved"]
            cash -= cover * pos["quantity"]
            pnl = (pos["entry_price"] - cover) * pos["quantity"] - pos["entry_fees"]
            trades.append(
                {
                    "symbol": pos["symbol"],
                    "strategy": "short",
                    "quantity": pos["quantity"],
                    "entry_time": pos["entry_time"],
                    "entry_price": pos["entry_price"],
                    "exit_time": ts,
                    "exit_price": cover,
                    "pnl": pnl,
                    "fees": pos["entry_fees"],
                    "reason": reason,
                    "bars_held": max(pos["bars_held"], 1),
                }
            )
        positions = still
        equity_now = mark_to("close", ts)
        if equity_open > 0 and equity_now <= equity_open * 0.98:
            for pos in list(positions):
                frame = bars.get(pos["symbol"])
                raw = float(frame.loc[ts, "close"]) if frame is not None and ts in frame.index else pos["entry_price"]
                cover = buy_price(raw, costs)
                cash += pos["reserved"] - cover * pos["quantity"]
                trades.append(
                    {
                        "symbol": pos["symbol"],
                        "strategy": "short",
                        "quantity": pos["quantity"],
                        "entry_time": pos["entry_time"],
                        "entry_price": pos["entry_price"],
                        "exit_time": ts,
                        "exit_price": cover,
                        "pnl": (pos["entry_price"] - cover) * pos["quantity"] - pos["entry_fees"],
                        "fees": pos["entry_fees"],
                        "reason": "daily_loss_breaker",
                        "bars_held": max(pos["bars_held"], 1),
                    }
                )
            positions = []
            equity_now = cash
        peak = max(peak, equity_now)
        if peak > 0 and (1.0 - equity_now / peak) >= 0.15:
            halted = True
        gross = sum(pos["reserved"] for pos in positions)
        equity_values.append(equity_now)
        exposure_values.append(gross / equity_now if equity_now else 0.0)
        index_out.append(ts)

    if positions and index_out:
        ts = index_out[-1]
        for pos in positions:
            frame = bars.get(pos["symbol"])
            raw = float(frame.loc[ts, "close"]) if frame is not None and ts in frame.index else pos["entry_price"]
            cover = buy_price(max(raw, 0.01), costs)
            cash += pos["reserved"] - cover * pos["quantity"]
            trades.append(
                {
                    "symbol": pos["symbol"],
                    "strategy": "short",
                    "quantity": pos["quantity"],
                    "entry_time": pos["entry_time"],
                    "entry_price": pos["entry_price"],
                    "exit_time": ts,
                    "exit_price": cover,
                    "pnl": (pos["entry_price"] - cover) * pos["quantity"] - pos["entry_fees"],
                    "fees": pos["entry_fees"],
                    "reason": "window_end",
                    "bars_held": max(pos["bars_held"], 1),
                }
            )
        equity_values[-1] = cash
        exposure_values[-1] = 0.0
    equity = pd.Series(equity_values, index=pd.DatetimeIndex(index_out), name="equity")
    exposure = pd.Series(exposure_values, index=equity.index, name="exposure")
    return BacktestResult(
        equity=equity,
        exposure=exposure,
        trades=pd.DataFrame(trades),
        ending_equity=float(equity.iloc[-1]) if len(equity) else starting_equity,
    )
