"""Frozen five-contract option scale-out.

The ladder was fixed before the book was scored. It does not change the
gate, and it is not a default exit. The ordinary simulator path is
unchanged when ``fixed_contracts`` is absent and ``exit_style`` is absent.

Buy 5 contracts. Sell 2 at +15% of the premium paid, 1 at +20%, 1 at +30%,
and leave 1 as a runner with a limit at +100%. The break-even stop applies
only to that runner, and only after the +15% tier fills. Until that fill
the runner keeps the initial stop. Contracts 1-4 keep the initial stop for
the whole trade. They do not move to break-even. The initial stop is one
of the frozen premium stops (-20%, -30%, -50%) or the setup's underlying
stop. -20% with 21 DTE is the corrected cell. -30% and the 5 and 35 DTE
edges are sensitivities. The gate does not pick among them.

A limit fills at the limit, not at the overshoot. A stop that gaps through
fills at the worse bid. On a bar that trades both the stop and a target,
the stop fills and the targets do not. The entry bar does not stop out on
the bid at the fill itself; that gap is the spread. Costs are the spread
haircut and the per-contract fees on the buy and on each sell ticket.
Webull's listed options commission is zero. Nothing here calls a broker.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Optional

import numpy as np
import pandas as pd

from webull_bot.backtest.engine import BacktestResult
from webull_bot.backtest.metrics import compute_metrics
from webull_bot.chart_reads.detect import rth
from webull_bot.chart_reads.exits import BRACKET_RS, TRAIL_ATRS, TRAIL_PCTS
from webull_bot.chart_reads.simulate import (
    BookStats,
    _empty,
    _is_last_rth,
    _open,
    _option_bid,
    _realized,
    _session,
    _sessions_held,
)
from webull_bot.costs import CostModel
from webull_bot.options.fees import CONTRACT_MULTIPLIER, option_leg_fees
from webull_bot.risk.pdt import check_day_trade, day_trades_in_window

SCALE_CONTRACTS = 5
SCALE_TIERS = (
    (0.15, 2),
    (0.20, 1),
    (0.30, 1),
    (1.00, 1),
)
PREMIUM_STOPS = (-0.20, -0.30, -0.50)
ALL_OUT_TARGET = 0.30
RISK_FRACTION = 0.02
ANCHOR_STOP = -0.30
FAR_OTM_DELTA = 0.20
CASH_ACCOUNT = 1_000.0
# Frozen before the corrected re-score. 21 is the midpoint of the stated
# 5-35 DTE band. The edges are reported and do not replace this cell.
CORRECTED_DTE = 21
CORRECTED_DTE_BAND = (5, 35)
CORRECTED_STOP = -0.20
CORRECTED_STOP_SENSITIVITY = -0.30
CORRECTED_DELTA = 0.45


def corrected_cells() -> list[tuple[str, dict, str]]:
    """The corrected ladder, frozen before its re-score.

    The first row is the cell the gate reads. A sensitivity or a comparison
    does not replace it.
    """
    return [
        (
            "scale, premium stop -20%, 21 DTE",
            {"mode": "scale", "stop_kind": "premium", "premium_stop": CORRECTED_STOP, "dte": CORRECTED_DTE},
            "gate",
        ),
        (
            "scale, premium stop -30%, 21 DTE",
            {
                "mode": "scale",
                "stop_kind": "premium",
                "premium_stop": CORRECTED_STOP_SENSITIVITY,
                "dte": CORRECTED_DTE,
            },
            "sensitivity",
        ),
        (
            "all-out +30%, premium stop -20%, 21 DTE",
            {"mode": "all_out", "stop_kind": "premium", "premium_stop": CORRECTED_STOP, "dte": CORRECTED_DTE},
            "comparison",
        ),
        (
            "scale, premium stop -20%, 5 DTE",
            {"mode": "scale", "stop_kind": "premium", "premium_stop": CORRECTED_STOP, "dte": CORRECTED_DTE_BAND[0]},
            "sensitivity",
        ),
        (
            "scale, premium stop -20%, 35 DTE",
            {"mode": "scale", "stop_kind": "premium", "premium_stop": CORRECTED_STOP, "dte": CORRECTED_DTE_BAND[1]},
            "sensitivity",
        ),
    ]


def scale_grid() -> list[tuple[str, dict]]:
    """Scale ladder and the all-out +30% comparison, in report order."""
    rows: list[tuple[str, dict]] = []
    for stop in PREMIUM_STOPS:
        rows.append(
            (
                f"scale, premium stop {stop:.0%}",
                {"mode": "scale", "stop_kind": "premium", "premium_stop": float(stop)},
            )
        )
    rows.append(
        (
            "scale, underlying stop",
            {"mode": "scale", "stop_kind": "underlying", "premium_stop": None},
        )
    )
    for stop in PREMIUM_STOPS:
        rows.append(
            (
                f"all-out +30%, premium stop {stop:.0%}",
                {"mode": "all_out", "stop_kind": "premium", "premium_stop": float(stop)},
            )
        )
    rows.append(
        (
            "all-out +30%, underlying stop",
            {"mode": "all_out", "stop_kind": "underlying", "premium_stop": None},
        )
    )
    return rows


def underlying_exit_grid(base: dict) -> list[tuple[str, dict]]:
    """The frozen trail and bracket cells, forced to five option contracts.

    These are the same percents, ATR multiples, and R multiples as the
    earlier exit grid. The level bracket is the next-resistance target.
    """
    rows: list[tuple[str, dict]] = []
    level = dict(base)
    level.pop("exit_style", None)
    level["trail"] = "none"
    level["target_mode"] = "level"
    level["level_source"] = "reference"
    level["fixed_contracts"] = SCALE_CONTRACTS
    level["expression"] = "single"
    rows.append(("bracket, next level", level))
    for pct in TRAIL_PCTS:
        cell = dict(base)
        cell["exit_style"] = "trail_pct"
        cell["trail_pct"] = float(pct)
        cell["trail"] = "none"
        cell["fixed_contracts"] = SCALE_CONTRACTS
        cell["expression"] = "single"
        rows.append((f"trail {pct:.0%}", cell))
    for multiple in TRAIL_ATRS:
        cell = dict(base)
        cell["exit_style"] = "trail_atr"
        cell["trail_atr"] = float(multiple)
        cell["trail"] = "none"
        cell["fixed_contracts"] = SCALE_CONTRACTS
        cell["expression"] = "single"
        rows.append((f"trail {multiple:g} ATR", cell))
    for reward in BRACKET_RS:
        cell = dict(base)
        cell.pop("exit_style", None)
        cell["trail"] = "none"
        cell["target_mode"] = "r"
        cell["reward_r"] = float(reward)
        cell["fixed_contracts"] = SCALE_CONTRACTS
        cell["expression"] = "single"
        rows.append((f"bracket {reward:g}R", cell))
    return rows


def required_capital(ask: float, debit: float, premium_stop: float) -> float:
    """Equity that puts the premium-stop loss at about 2% of the account.

    The loss is the debit minus a sell at the stop limit, after sell fees.
    The account also has to cover the debit.
    """
    exit_px = max(0.0, float(ask) * (1.0 + float(premium_stop)))
    fees = option_leg_fees(SCALE_CONTRACTS, exit_px, sell=True)
    credit = max(0.0, SCALE_CONTRACTS * exit_px * CONTRACT_MULTIPLIER - fees)
    risk = max(0.0, float(debit) - credit)
    return max(float(debit), risk / RISK_FRACTION)


def new_state(ask: float, mode: str, stop_kind: str, premium_stop: Optional[float]) -> dict:
    if mode not in {"scale", "all_out"}:
        raise ValueError("mode must be scale or all_out")
    if stop_kind not in {"premium", "underlying"}:
        raise ValueError("stop_kind must be premium or underlying")
    if stop_kind == "premium":
        if premium_stop not in PREMIUM_STOPS:
            raise ValueError("premium stop is outside the frozen set")
        stop_px = float(ask) * (1.0 + float(premium_stop))
    else:
        stop_px = None
    if mode == "scale":
        tiers = [
            {
                "pct": float(pct),
                "qty": int(qty),
                "limit": float(ask) * (1.0 + float(pct)),
                "role": "runner" if index == len(SCALE_TIERS) - 1 else "fixed",
            }
            for index, (pct, qty) in enumerate(SCALE_TIERS)
        ]
        runner_open = 1
    else:
        tiers = [
            {
                "pct": ALL_OUT_TARGET,
                "qty": SCALE_CONTRACTS,
                "limit": float(ask) * (1.0 + ALL_OUT_TARGET),
                "role": "fixed",
            }
        ]
        runner_open = 0
    return {
        "mode": mode,
        "stop_kind": stop_kind,
        "stop_px": stop_px,
        "entry_ask": float(ask),
        "runner_stop": None,
        "runner_open": runner_open,
        "tiers": tiers,
        "tier_count": len(tiers),
        "remaining": SCALE_CONTRACTS,
        "targets_hit": 0,
        "armed": False,
        "arm_pending": False,
        "armed_flag": 0,
        "credit": 0.0,
        "sell_fees": 0.0,
        "contracts_sold": 0,
        "sold": {},
        "done": False,
        "reason": "",
        "runner": "",
    }


def underlying_stop_hit(
    direction: str,
    open_: float,
    high: float,
    low: float,
    stop: float,
    entry_bar: bool,
) -> tuple[bool, float]:
    """Adverse touch of the setup stop. A later gap fills at the open."""
    if not np.isfinite(stop):
        return False, stop
    if direction == "long":
        if open_ <= stop and not entry_bar:
            return True, open_
        if low <= stop and open_ > stop:
            return True, stop
        return False, stop
    if open_ >= stop and not entry_bar:
        return True, open_
    if high >= stop and open_ < stop:
        return True, stop
    return False, stop


def apply_scale_bar(
    state: dict,
    quotes: dict,
    *,
    entry_bar: bool,
    terminal: Optional[str],
) -> Optional[str]:
    """One bar. Stops first, then limits, then the time stop or expiry.

    The initial stop covers contracts 1-4 for the whole trade, and the
    runner until the +15% tier has filled. After that fill, only the runner
    moves to the entry ask. Break-even is armed at the end of the bar, so
    the same bar's adverse extreme does not scratch the target that just
    filled. A bar that trades through a contract's own stop does not also
    fill that contract's limit.
    """
    if state["done"]:
        return state["reason"] or None
    if state["stop_kind"] == "underlying" and quotes.get("underlying_hit") and not state["armed"]:
        _flatten(state, float(quotes["underlying_bid"]), "initial_stop")
        return "initial_stop"
    if _initial_stop_hit(state, float(quotes["open_bid"]), allow=not entry_bar):
        _flatten(state, float(quotes["open_bid"]), "initial_stop")
        return "initial_stop"
    if _initial_stop_hit(state, float(quotes["adverse_bid"]), allow=True):
        _flatten(state, float(quotes["adverse_bid"]), "initial_stop")
        return "initial_stop"
    if state["stop_kind"] == "underlying" and quotes.get("underlying_hit") and state["armed"]:
        _stop_fixed(state, float(quotes["underlying_bid"]))
    if state["armed"] and int(state.get("runner_open") or 0) > 0:
        if _runner_stop_hit(state, float(quotes["open_bid"]), allow=not entry_bar):
            _stop_runner(state, float(quotes["open_bid"]))
        elif _runner_stop_hit(state, float(quotes["adverse_bid"]), allow=True):
            _stop_runner(state, float(quotes["adverse_bid"]))
    favorable = float(quotes["favorable_bid"])
    while state["tiers"] and favorable + 1e-12 >= float(state["tiers"][0]["limit"]):
        tier = state["tiers"][0]
        if tier.get("role") == "runner" and int(state.get("runner_open") or 0) <= 0:
            state["tiers"].pop(0)
            continue
        tier = state["tiers"].pop(0)
        _sell(state, int(tier["qty"]), float(tier["limit"]), float(tier["pct"]))
        state["targets_hit"] += 1
        if tier.get("role") == "runner":
            state["runner_open"] = 0
            state["runner"] = "target"
        elif state["mode"] == "scale" and float(tier["pct"]) == float(SCALE_TIERS[0][0]):
            state["arm_pending"] = True
    if state["remaining"] <= 0:
        if state.get("runner") == "breakeven":
            return _finish(state, "breakeven")
        return _finish(state, "target")
    if terminal:
        _flatten(state, float(quotes["close_bid"]), terminal)
        return terminal
    if state.get("arm_pending"):
        state["armed"] = True
        state["arm_pending"] = False
        state["armed_flag"] = 1
        state["runner_stop"] = float(state["entry_ask"])
    return None


def quote_entries(
    setups,
    execution: dict[str, pd.DataFrame],
    daily: dict[str, pd.DataFrame],
    params: dict,
    *,
    session_filter: bool,
) -> list[dict]:
    """Price a five-lot at each fill. No exit, so this does not score a book."""
    frames = _prepare(execution, session_filter)
    rv = _realized(daily)
    chosen = _option_params(params)
    rows = []
    for setup in setups:
        fill = pd.Timestamp(setup.fill_time)
        opened = _open(setup, fill, frames, rv, {}, {}, 1.0e12, 1.0e12, chosen, CostModel())
        if opened is None:
            continue
        ask = float(opened["entry"])
        debit = float(opened["debit"])
        row = {
            "symbol": setup.symbol,
            "ask": ask,
            "debit": debit,
            "delta": float(opened["delta"]),
            "fill_time": fill,
        }
        for stop in PREMIUM_STOPS:
            row[f"required_{stop:.2f}"] = required_capital(ask, debit, stop)
        bid = _option_bid(opened, fill, float(setup.stop), chosen)
        fees = option_leg_fees(SCALE_CONTRACTS, bid, sell=True)
        credit = max(0.0, SCALE_CONTRACTS * bid * CONTRACT_MULTIPLIER - fees)
        risk = max(0.0, debit - credit)
        row["required_underlying"] = max(debit, risk / RISK_FRACTION)
        rows.append(row)
    return rows


def simulate_scale(
    setups,
    execution: dict[str, pd.DataFrame],
    daily: dict[str, pd.DataFrame],
    params: dict,
    spec: dict,
    *,
    starting_equity: float,
    session_filter: bool,
    costs: CostModel | None = None,
) -> BookStats:
    """One position. Five contracts. The spec is one frozen scale or all-out cell."""
    del costs  # Option costs are the spread haircut and option_leg_fees, not stock slippage.
    frames = _prepare(execution, session_filter)
    if not frames:
        return _empty(starting_equity)
    rv = _realized(daily)
    chosen = _option_params(params)
    ordered = sorted(setups, key=lambda setup: (pd.Timestamp(setup.fill_time), setup.symbol))
    cash = float(starting_equity)
    day_trades: list = []
    closed: list[dict] = []
    equity_values: list[float] = []
    index: list[pd.Timestamp] = []
    pdt_blocked = 0
    premium_skipped = 0
    overlapped = 0
    busy_until: Optional[pd.Timestamp] = None
    account = str(params.get("account", "margin_pdt"))
    max_sessions = int(params.get("max_hold_sessions", 1))
    flatten_eod = bool(params.get("flatten_eod", False))
    dte = int(chosen.get("dte", params.get("dte", 3)))

    for setup in ordered:
        fill = pd.Timestamp(setup.fill_time)
        if busy_until is not None and fill <= busy_until:
            overlapped += 1
            continue
        session = _session(fill)
        equity_now = cash
        if account == "margin_pdt":
            prospective = bool(params.get("pdt_prospective", True))
            already = day_trades_in_window(day_trades, session, 5)
            decision = check_day_trade(
                as_of=session,
                equity=equity_now,
                trade_days=day_trades,
                opening_same_day=prospective or already >= 3,
                account_type="margin",
                mode="on",
            )
            if not decision.allowed:
                pdt_blocked += 1
                continue
        opened = _open(setup, fill, frames, rv, {}, {}, equity_now, cash, chosen, CostModel())
        if opened is None:
            premium_skipped += 1
            continue
        state = new_state(
            float(opened["entry"]),
            str(spec["mode"]),
            str(spec["stop_kind"]),
            spec.get("premium_stop"),
        )
        cash -= float(opened["debit"])
        frame = frames[setup.symbol]
        start = frame.index.get_loc(fill)
        if isinstance(start, slice):
            start = start.start
        if isinstance(start, np.ndarray):
            start = int(start[0])
        bars = frame.iloc[int(start) :]
        opened_on = _session(fill)
        expiry = opened_on + timedelta(days=dte)
        counted = False
        reason = None
        exit_time = fill
        bars_held = 0
        for ts, row in bars.iterrows():
            ts = pd.Timestamp(ts)
            exit_time = ts
            bars_held += 1
            entry_bar = ts == fill
            held = _sessions_held(opened_on, _session(ts))
            last = _is_last_rth(ts, frame.index)
            expired = _session(ts) >= expiry
            if expired and last:
                terminal = "expiry"
            elif held >= max_sessions and last:
                terminal = "time_stop"
            elif flatten_eod and last:
                terminal = "session_flat"
            else:
                terminal = None
            quotes = _quotes(opened, ts, row, chosen, setup, entry_bar, spec)
            if quotes is None:
                continue
            reason = apply_scale_bar(state, quotes, entry_bar=entry_bar, terminal=terminal)
            if _session(ts) == opened_on and state["contracts_sold"] > 0 and not counted:
                day_trades.append(opened_on)
                counted = True
            mark_bid = float(quotes["close_bid"])
            if reason:
                equity_values.append(cash + state["credit"])
                index.append(ts)
                break
            equity_values.append(cash + state["credit"] + state["remaining"] * mark_bid * CONTRACT_MULTIPLIER)
            index.append(ts)
        if not state["done"]:
            last_ts = pd.Timestamp(bars.index[-1])
            last_row = bars.iloc[-1]
            quotes = _quotes(opened, last_ts, last_row, chosen, setup, False, spec)
            price = float(quotes["close_bid"]) if quotes is not None else 0.0
            _flatten(state, price, "window_end")
            reason = "window_end"
            exit_time = last_ts
            equity_values.append(cash + state["credit"])
            index.append(exit_time)
        cash += state["credit"]
        closed.append(_trade(setup, opened, state, exit_time, bars_held))
        busy_until = exit_time

    extra = _summarize(closed)
    extra["overlapped"] = overlapped
    trades = pd.DataFrame(closed)
    if not index:
        stats = _empty(starting_equity)
        stats.pdt_blocked = pdt_blocked
        stats.premium_skipped = premium_skipped
        stats.extra = extra
        stats.trades = trades
        return stats
    equity = pd.Series(equity_values, index=pd.DatetimeIndex(index), name="equity")
    equity = equity[~equity.index.duplicated(keep="last")]
    exposure = pd.Series(0.0, index=equity.index, name="exposure")
    result = BacktestResult(
        equity=equity,
        exposure=exposure,
        trades=trades,
        ending_equity=float(equity.iloc[-1]),
    )
    metrics = compute_metrics(result, starting_equity)
    return BookStats(
        metrics=metrics,
        trades=trades,
        equity=equity,
        pdt_blocked=pdt_blocked,
        premium_skipped=premium_skipped,
        min_equity=float(equity.min()),
        ending_equity=float(metrics["ending_equity"]),
        extra=extra,
    )


def _option_params(params: dict) -> dict:
    chosen = dict(params)
    chosen.pop("exit_style", None)
    chosen["fixed_contracts"] = SCALE_CONTRACTS
    chosen["expression"] = "single"
    return chosen


def _prepare(execution: dict[str, pd.DataFrame], session_filter: bool) -> dict[str, pd.DataFrame]:
    frames = {}
    for symbol, frame in execution.items():
        if frame is None or len(frame) == 0:
            continue
        frames[symbol] = rth(frame) if session_filter else frame.sort_index()
    return frames


def _initial_stop_hit(state: dict, bid: float, *, allow: bool) -> bool:
    """The frozen premium stop. Contracts 1-4 keep it after the runner arms."""
    if not allow or state["stop_px"] is None or state["stop_kind"] != "premium":
        return False
    if state["remaining"] <= 0:
        return False
    return bid <= float(state["stop_px"])


def _runner_stop_hit(state: dict, bid: float, *, allow: bool) -> bool:
    if not allow or state.get("runner_stop") is None or int(state.get("runner_open") or 0) <= 0:
        return False
    return bid <= float(state["runner_stop"])


def _stop_runner(state: dict, price: float) -> None:
    qty = int(state.get("runner_open") or 0)
    if qty <= 0:
        return
    _sell(state, qty, price, None)
    state["runner_open"] = 0
    state["runner"] = "breakeven"
    state["tiers"] = [tier for tier in state["tiers"] if tier.get("role") != "runner"]


def _stop_fixed(state: dict, price: float) -> None:
    """Sell contracts 1-4. The runner keeps its own stop."""
    qty = sum(int(tier["qty"]) for tier in state["tiers"] if tier.get("role") != "runner")
    state["tiers"] = [tier for tier in state["tiers"] if tier.get("role") == "runner"]
    if qty > 0:
        _sell(state, qty, price, None)


def _premium_hit(state: dict, bid: float, *, allow: bool) -> bool:
    if not allow or state["stop_px"] is None:
        return False
    if state["armed"] or state["stop_kind"] == "premium":
        return bid <= float(state["stop_px"])
    return False


def _sell(state: dict, qty: int, price: float, bucket: Optional[float]) -> None:
    qty = min(int(qty), int(state["remaining"]))
    if qty <= 0:
        return
    fees = option_leg_fees(qty, max(price, 0.0), sell=True)
    state["sell_fees"] += fees
    state["credit"] += qty * max(price, 0.0) * CONTRACT_MULTIPLIER - fees
    state["remaining"] -= qty
    state["contracts_sold"] += qty
    if bucket is not None:
        key = f"{bucket:.2f}"
        state["sold"][key] = int(state["sold"].get(key, 0)) + qty


def _flatten(state: dict, price: float, reason: str) -> str:
    if state["mode"] == "scale" and int(state.get("runner_open") or 0) > 0:
        state["runner"] = reason
        state["runner_open"] = 0
    if state["remaining"] > 0:
        _sell(state, int(state["remaining"]), price, None)
    return _finish(state, reason)


def _finish(state: dict, reason: str) -> str:
    state["done"] = True
    state["reason"] = reason
    if state["mode"] == "scale" and state["targets_hit"] > 0:
        state["armed_flag"] = 1
    if state["mode"] == "all_out":
        state["runner"] = "all_out" if reason == "target" else reason
    elif not state.get("runner"):
        state["runner"] = "target" if reason == "target" else reason
    return reason


def _quotes(pos, ts, row, params, setup, entry_bar: bool, spec: dict) -> Optional[dict]:
    try:
        open_ = float(row["open"])
        high = float(row["high"])
        low = float(row["low"])
        close = float(row["close"])
    except (TypeError, ValueError, KeyError):
        return None
    if not all(np.isfinite(value) and value > 0 for value in (open_, high, low, close)):
        return None
    if pos["direction"] == "long":
        adverse, favorable = low, high
    else:
        adverse, favorable = high, low
    hit, spot = underlying_stop_hit(pos["direction"], open_, high, low, float(setup.stop), entry_bar)
    if str(spec.get("stop_kind")) != "underlying":
        hit = False
    return {
        "open_bid": _option_bid(pos, ts, open_, params),
        "adverse_bid": _option_bid(pos, ts, adverse, params),
        "favorable_bid": _option_bid(pos, ts, favorable, params),
        "close_bid": _option_bid(pos, ts, close, params),
        "underlying_hit": hit,
        "underlying_bid": _option_bid(pos, ts, spot, params) if hit else 0.0,
    }


def _trade(setup, opened, state, exit_time, bars_held: int) -> dict:
    quantity = float(SCALE_CONTRACTS)
    debit = float(opened["debit"])
    return {
        "symbol": setup.symbol,
        "strategy": f"{setup.direction}_scale",
        "quantity": quantity,
        "entry_time": opened["entry_time"],
        "entry_price": float(opened["entry"]),
        "exit_time": exit_time,
        "exit_price": state["credit"] / (quantity * CONTRACT_MULTIPLIER) if quantity else 0.0,
        "pnl": state["credit"] - debit,
        "fees": float(opened["debit"] - quantity * float(opened["entry"]) * CONTRACT_MULTIPLIER) + float(state["sell_fees"]),
        "reason": state["reason"],
        "bars_held": bars_held,
        "targets_hit": int(state["targets_hit"]),
        "runner": state["runner"],
        "armed": int(state["armed_flag"]),
        "entry_delta": float(opened["delta"]),
        "debit": debit,
        "sold_15": int(state["sold"].get("0.15", 0)),
        "sold_20": int(state["sold"].get("0.20", 0)),
        "sold_30": int(state["sold"].get("0.30", 0)),
        "sold_100": int(state["sold"].get("1.00", 0)),
    }


def _summarize(rows: list[dict]) -> dict[str, Any]:
    if not rows:
        return {"targets": {}, "runner": {}, "armed": 0, "mean_delta": None, "mean_capture": None}
    frame = pd.DataFrame(rows)
    debit = frame["entry_price"].astype(float) * frame["quantity"].astype(float) * CONTRACT_MULTIPLIER
    capture = frame["pnl"].astype(float) / debit.where(debit > 0)
    return {
        "targets": {str(int(key)): int(value) for key, value in frame["targets_hit"].value_counts().sort_index().items()},
        "runner": {str(key): int(value) for key, value in frame["runner"].value_counts().items()},
        "armed": int(frame["armed"].sum()),
        "mean_delta": float(frame["entry_delta"].mean()),
        "mean_capture": float(capture.mean()) if capture.notna().any() else None,
    }

