"""ATM 14 DTE option-exit search. The grid is frozen before any holdout score.

Longs buy calls and shorts buy puts, delta 0.50, 14 calendar days. The
exit grid below is the whole search. It is not enlarged after a result.
``choose`` reads training metrics only.

Families, fixed before the run:

* A. Three fixed rungs, quantities 2, 1, 1, plus a 1-lot runner. The three
  targets are a strictly increasing triple from +10, +15, +20, +25, +30,
  +40, +50. The runner is +50, +75, +100, or +150, and it has to sit
  strictly above the third rung.
* B. Two fixed rungs, quantities 2 and 2, plus a 1-lot runner. Same target
  set, same runner rule, runner strictly above the second rung.
* C. All-out. One target for all five contracts, from +15, +25, +30, +50,
  +75, +100. No break-even.
* D. One reference ladder, not crossed with the others: 2 at +15, 1 at +25,
  1 at +40, runner +100, stop -20%. The time stop is 2, 5, or 10 sessions
  on an hourly book and 3, 7, or 14 sessions on a daily book. Expiry at
  14 DTE still applies. The earlier exit wins.
* E. The same reference rungs, every frozen stop, and a runner trail of
  10%, 15%, or 25% of the peak premium after the first rung. The runner
  either keeps a +100% limit or has no limit. Break-even is the floor.

Stops for A, B, C, and E are -10, -15, -20, -25, -30, and -40% of the
premium. Contracts 1-4 keep that stop for the whole trade. The runner
keeps it until the first rung fills. Break-even is armed at the end of
that bar, so the same bar's adverse extreme does not scratch the runner.
A stop that gaps through fills at the worse bid. A limit fills at the
limit. A contract whose own stop is touched does not also fill its limit.
Other families keep the book's existing session hold, and expiry.

Selection, also frozen: among cells with at least 30 training trades, the
highest training Sharpe, then higher expectancy, then a milder drawdown,
then the label. If none has 30 trades, the same order among cells with at
least 15. If none has 15, that book has no cell. Nothing here calls a broker.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

import numpy as np
import pandas as pd

from webull_bot.calendar import previous_trading_days
from webull_bot.chart_reads.premium_scale import _prepare, required_capital
from webull_bot.chart_reads.simulate import (
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

ATM_DTE = 14
ATM_DELTA = 0.50
STOPS = (-0.10, -0.15, -0.20, -0.25, -0.30, -0.40)
RUNG_TARGETS = (0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50)
RUNNER_TARGETS = (0.50, 0.75, 1.00, 1.50)
ALL_OUT_TARGETS = (0.15, 0.25, 0.30, 0.50, 0.75, 1.00)
TRAIL_PCTS = (0.10, 0.15, 0.25)
HOURLY_TIME_STOPS = (2, 5, 10)
DAILY_TIME_STOPS = (3, 7, 14)
REFERENCE_RUNGS = (0.15, 0.25, 0.40)
REFERENCE_RUNNER = 1.00
REFERENCE_STOP = -0.20
REFERENCE_QTYS = (2, 1, 1)
MIN_TRAIN_TRADES = 30
FALLBACK_TRAIN_TRADES = 15
HOLDS_UP_MIN_TRADES = 20
POOL_MIN_BOOKS = 4
# Families A-C and E are the same on every clock. D is the time-stop family.
POOLED_FAMILIES = frozenset({"A", "B", "C", "E"})
_EXCHANGE = 0.02 + 0.02 + 0.0003
_TAF = 0.00279
_TAF_MIN = 0.01
_SEC = 0.0000206
_EULER = 0.5772156649015329


@dataclass(frozen=True)
class Cell:
    family: str
    label: str
    stop: float
    pcts: tuple[float, ...]
    qtys: tuple[int, ...]
    runner_tier: tuple[bool, ...]
    trail: float
    max_hold: Optional[int]
    runner_contracts: int

    def __post_init__(self) -> None:
        if len(self.pcts) != len(self.qtys) or len(self.pcts) != len(self.runner_tier):
            raise ValueError("tier lengths differ")
        if abs(sum(self.qtys) + (0 if any(self.runner_tier) else self.runner_contracts) - 5) > 0:
            if sum(self.qtys) != 5:
                raise ValueError("five contracts")


@dataclass
class QuotePath:
    symbol: str
    direction: str
    fill: pd.Timestamp
    fill_date: date
    ok: bool
    ask: float = 0.0
    debit: float = 0.0
    delta: float = 0.0
    open_bid: Optional[np.ndarray] = None
    adverse_bid: Optional[np.ndarray] = None
    favorable_bid: Optional[np.ndarray] = None
    close_bid: Optional[np.ndarray] = None
    entry_bar: Optional[np.ndarray] = None
    is_last: Optional[np.ndarray] = None
    held: Optional[np.ndarray] = None
    expired: Optional[np.ndarray] = None
    session: Optional[np.ndarray] = None
    stamps: Optional[list] = None


def _pct(value: float) -> str:
    return f"{value:+.0%}"


def _stop_pct(value: float) -> str:
    return f"{value:.0%}"


def _scale_cell(
    family: str,
    rungs: tuple[float, ...],
    qtys: tuple[int, ...],
    runner: float,
    stop: float,
    *,
    trail: float = 0.0,
    max_hold: Optional[int] = None,
) -> Cell:
    pcts = tuple(rungs) + (float(runner),)
    quantities = tuple(qtys) + (1,)
    flags = tuple(False for _ in rungs) + (True,)
    rung_text = "/".join(_pct(item) for item in rungs)
    extra = ""
    if trail > 0:
        extra = f" trail {trail:.0%}"
    if max_hold is not None:
        extra += f" time {max_hold} sessions"
    label = (
        f"{family} stop {_stop_pct(stop)} rungs {rung_text} "
        f"runner {_pct(runner)}{extra}"
    )
    return Cell(family, label, float(stop), pcts, quantities, flags, float(trail), max_hold, 1)


def _open_runner_cell(stop: float, trail: float) -> Cell:
    """Reference rungs. The runner has a trail and no limit."""
    label = (
        f"E stop {_stop_pct(stop)} rungs +15%/+25%/+40% "
        f"runner trail {trail:.0%} no limit"
    )
    return Cell(
        "E",
        label,
        float(stop),
        REFERENCE_RUNGS,
        REFERENCE_QTYS,
        (False, False, False),
        float(trail),
        None,
        1,
    )


def frozen_grid(clock: str) -> list[Cell]:
    """Every cell the search is allowed to try. ``clock`` is hourly or daily."""
    if clock not in {"hourly", "daily"}:
        raise ValueError("clock must be hourly or daily")
    cells: list[Cell] = []
    rung_values = RUNG_TARGETS
    for i, first in enumerate(rung_values):
        for j in range(i + 1, len(rung_values)):
            second = rung_values[j]
            for k in range(j + 1, len(rung_values)):
                third = rung_values[k]
                for runner in RUNNER_TARGETS:
                    if runner <= third:
                        continue
                    for stop in STOPS:
                        cells.append(
                            _scale_cell("A", (first, second, third), (2, 1, 1), runner, stop)
                        )
            for runner in RUNNER_TARGETS:
                if runner <= second:
                    continue
                for stop in STOPS:
                    cells.append(_scale_cell("B", (first, second), (2, 2), runner, stop))
    for target in ALL_OUT_TARGETS:
        for stop in STOPS:
            label = f"C all-out {_pct(target)} stop {_stop_pct(stop)}"
            cells.append(
                Cell(
                    "C",
                    label,
                    float(stop),
                    (float(target),),
                    (5,),
                    (False,),
                    0.0,
                    None,
                    0,
                )
            )
    time_stops = HOURLY_TIME_STOPS if clock == "hourly" else DAILY_TIME_STOPS
    for sessions in time_stops:
        cells.append(
            _scale_cell(
                "D",
                REFERENCE_RUNGS,
                REFERENCE_QTYS,
                REFERENCE_RUNNER,
                REFERENCE_STOP,
                max_hold=int(sessions),
            )
        )
    for stop in STOPS:
        for trail in TRAIL_PCTS:
            cells.append(
                _scale_cell(
                    "E",
                    REFERENCE_RUNGS,
                    REFERENCE_QTYS,
                    REFERENCE_RUNNER,
                    stop,
                    trail=float(trail),
                )
            )
            cells.append(_open_runner_cell(stop, float(trail)))
    labels = [cell.label for cell in cells]
    if len(labels) != len(set(labels)):
        raise RuntimeError("duplicate exit cell")
    return cells


def sell_fee(qty: int, price: float) -> float:
    """Same ticket as ``option_leg_fees`` for a sell. Inlined for the grid."""
    if qty <= 0:
        return 0.0
    notional = max(price, 0.0) * CONTRACT_MULTIPLIER * qty
    taf = _TAF * qty
    if taf < _TAF_MIN:
        taf = _TAF_MIN
    return _EXCHANGE * qty + taf + _SEC * notional


def _proceeds(qty: int, price: float) -> float:
    if qty <= 0:
        return 0.0
    px = price if price > 0.0 else 0.0
    return qty * px * CONTRACT_MULTIPLIER - sell_fee(qty, px)


def run_quotes(cell: Cell, ask: float, rows: list[dict], *, max_hold: int) -> dict:
    """One trade from explicit bids. The search uses this same runner."""
    count = len(rows)
    path = QuotePath(
        symbol="TEST",
        direction="long",
        fill=pd.Timestamp("2024-01-02"),
        fill_date=date(2024, 1, 2),
        ok=True,
        ask=float(ask),
        debit=0.0,
        open_bid=np.array([float(row["open_bid"]) for row in rows]),
        adverse_bid=np.array([float(row["adverse_bid"]) for row in rows]),
        favorable_bid=np.array([float(row["favorable_bid"]) for row in rows]),
        close_bid=np.array([float(row["close_bid"]) for row in rows]),
        entry_bar=np.array([bool(row.get("entry_bar", False)) for row in rows]),
        is_last=np.array([bool(row.get("is_last", False)) for row in rows]),
        held=np.array([int(row.get("held", 1)) for row in rows]),
        expired=np.array([bool(row.get("expired", False)) for row in rows]),
        session=np.arange(count, dtype=int),
        stamps=[pd.Timestamp("2024-01-02") + pd.Timedelta(days=index) for index in range(count)],
    )
    return _run_path(cell, path, max_hold=int(max_hold), base_cash=0.0)


def _run_path(cell: Cell, path: QuotePath, *, max_hold: int, base_cash: float) -> dict:
    """Path edition. Session marks are collected here, not in the quote helper."""
    open_bid = path.open_bid
    assert open_bid is not None and path.adverse_bid is not None
    assert path.favorable_bid is not None and path.close_bid is not None
    assert path.entry_bar is not None and path.is_last is not None
    assert path.held is not None and path.expired is not None and path.session is not None
    if cell.max_hold is not None:
        max_hold = int(cell.max_hold)
    stop_px = path.ask * (1.0 + float(cell.stop))
    pcts = cell.pcts
    qtys = cell.qtys
    flags = cell.runner_tier
    n_tiers = len(pcts)
    ask = float(path.ask)
    limits = [ask * (1.0 + float(pcts[i])) for i in range(n_tiers)]
    remaining = 5
    credit = 0.0
    targets = 0
    runner_open = int(cell.runner_contracts)
    runner_stop = 0.0
    armed = False
    arm_pending = False
    peak = 0.0
    trail = float(cell.trail)
    reason = ""
    runner = ""
    next_tier = 0
    sold: dict[str, int] = {}
    entry_sale = False
    exit_index = len(open_bid) - 1 if len(open_bid) else 0
    count = len(open_bid)
    sessions = path.session
    last_ord = -1
    last_equity = base_cash
    mark_ords: list[int] = []
    mark_eq: list[float] = []

    def _note(index: int, qty: int, bucket: Optional[float]) -> None:
        nonlocal entry_sale
        if int(path.held[index]) <= 1:
            entry_sale = True
        if bucket is not None and qty > 0:
            key = f"{float(bucket):.2f}"
            sold[key] = sold.get(key, 0) + qty

    def _remember(index: int, equity: float) -> None:
        nonlocal last_ord, last_equity
        order = int(sessions[index])
        if order == last_ord:
            mark_eq[-1] = equity
        else:
            mark_ords.append(order)
            mark_eq.append(equity)
            last_ord = order
        last_equity = equity

    for index in range(count):
        ob = float(open_bid[index])
        ab = float(path.adverse_bid[index])
        fb = float(path.favorable_bid[index])
        cb = float(path.close_bid[index])
        is_entry = bool(path.entry_bar[index])
        if remaining > 0 and ((not is_entry and ob <= stop_px) or ab <= stop_px):
            price = ob if (not is_entry and ob <= stop_px) else ab
            credit += _proceeds(remaining, price)
            _note(index, remaining, None)
            if runner_open > 0:
                runner = "initial_stop"
            remaining = 0
            runner_open = 0
            reason = "initial_stop"
            exit_index = index
            _remember(index, base_cash + credit)
            break
        if armed and runner_open > 0 and runner_stop > 0.0:
            hit_open = (not is_entry) and ob <= runner_stop
            if hit_open or ab <= runner_stop:
                price = ob if hit_open else ab
                qty = runner_open
                credit += _proceeds(qty, price)
                _note(index, qty, None)
                remaining -= qty
                runner_open = 0
                runner = "trail" if trail > 0.0 and runner_stop > ask + 1e-9 else "breakeven"
                while next_tier < n_tiers and flags[next_tier]:
                    next_tier += 1
        while next_tier < n_tiers and fb + 1e-12 >= limits[next_tier]:
            tier_index = next_tier
            next_tier += 1
            if flags[tier_index] and runner_open <= 0:
                continue
            qty = int(qtys[tier_index])
            if flags[tier_index]:
                qty = min(qty, runner_open)
            qty = min(qty, remaining)
            if qty <= 0:
                continue
            credit += _proceeds(qty, limits[tier_index])
            _note(index, qty, float(pcts[tier_index]))
            remaining -= qty
            targets += 1
            if flags[tier_index]:
                runner_open = 0
                runner = "target"
            elif tier_index == 0 and cell.family != "C":
                arm_pending = True
        if remaining <= 0:
            if runner == "breakeven":
                reason = "breakeven"
            elif runner == "trail":
                reason = "trail"
            else:
                reason = "target"
            if cell.family == "C":
                runner = "all_out" if reason == "target" else (runner or reason)
            exit_index = index
            _remember(index, base_cash + credit)
            break
        terminal = ""
        if bool(path.expired[index]) and bool(path.is_last[index]):
            terminal = "expiry"
        elif int(path.held[index]) >= max_hold and bool(path.is_last[index]):
            terminal = "time_stop"
        if terminal:
            if remaining > 0:
                credit += _proceeds(remaining, cb)
                _note(index, remaining, None)
            if runner_open > 0:
                runner = terminal
            remaining = 0
            runner_open = 0
            reason = terminal
            if cell.family == "C":
                runner = reason
            exit_index = index
            _remember(index, base_cash + credit)
            break
        if arm_pending:
            armed = True
            arm_pending = False
            runner_stop = ask
            if trail > 0.0 and fb > peak:
                peak = fb
                trailed = peak * (1.0 - trail)
                if trailed > runner_stop:
                    runner_stop = trailed
        elif armed and trail > 0.0 and runner_open > 0 and fb > peak:
            peak = fb
            trailed = peak * (1.0 - trail)
            if trailed > runner_stop:
                runner_stop = trailed
        _remember(index, base_cash + credit + remaining * cb * CONTRACT_MULTIPLIER)
    else:
        if count and remaining > 0:
            price = float(path.close_bid[-1])
            credit += _proceeds(remaining, price)
            _note(count - 1, remaining, None)
            if runner_open > 0:
                runner = "window_end"
            remaining = 0
            reason = "window_end"
            if cell.family == "C":
                runner = reason
            exit_index = count - 1
            _remember(count - 1, base_cash + credit)
    if cell.family == "C" and reason == "target":
        runner = "all_out"
    if not reason:
        reason = "window_end"
    return {
        "credit": credit,
        "reason": reason,
        "targets_hit": targets,
        "runner": runner or reason,
        "armed": 1 if cell.family != "C" and targets > 0 else 0,
        "runner_stop": runner_stop if armed else None,
        "stop_px": stop_px,
        "remaining": remaining,
        "sold": sold,
        "entry_sale": entry_sale,
        "exit_index": exit_index,
        "mark_ords": mark_ords,
        "mark_eq": mark_eq,
    }


def _metrics_from_curve(starting: float, ords: list[int], equity: list[float], pnls: list[float]) -> dict:
    trades = len(pnls)
    ending = float(equity[-1]) if equity else float(starting)
    expectancy = float(np.mean(pnls)) if pnls else 0.0
    wins = [item for item in pnls if item > 0.0]
    losses = [item for item in pnls if item < 0.0]
    win_rate = (len(wins) / trades) if trades else 0.0
    gross_win = float(sum(wins))
    gross_loss = float(-sum(losses))
    if gross_loss > 0.0:
        profit_factor: Optional[float] = gross_win / gross_loss
    elif gross_win > 0.0:
        profit_factor = None
    else:
        profit_factor = 0.0
    if not equity:
        return {
            "starting_equity": float(starting),
            "ending_equity": float(starting),
            "sharpe": 0.0,
            "max_drawdown": 0.0,
            "expectancy": 0.0,
            "trades": 0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "returns": np.empty(0),
        }
    curve = np.empty(len(equity) + 1, dtype=float)
    curve[0] = float(starting)
    curve[1:] = equity
    rets = np.diff(curve) / curve[:-1]
    rets = rets[np.isfinite(rets)]
    std = float(rets.std()) if len(rets) else 0.0
    sharpe = float(rets.mean() / std * math.sqrt(252)) if std > 0.0 else 0.0
    if not math.isfinite(sharpe):
        sharpe = 0.0
    peak = np.maximum.accumulate(curve)
    drawdown = curve / peak - 1.0
    max_dd = float(np.min(drawdown)) if len(drawdown) else 0.0
    if not math.isfinite(max_dd):
        max_dd = 0.0
    return {
        "starting_equity": float(starting),
        "ending_equity": ending,
        "sharpe": sharpe,
        "max_drawdown": max_dd,
        "expectancy": expectancy,
        "trades": trades,
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "returns": rets,
    }


def _pdt_window(day: date, cache: dict[date, set[date]]) -> set[date]:
    found = cache.get(day)
    if found is None:
        found = set(previous_trading_days(day, 5, include_self=True))
        cache[day] = found
    return found


def score_cell(
    paths: list[QuotePath],
    cell: Cell,
    *,
    starting_equity: float,
    max_hold: int,
    pdt_prospective: bool,
    account: str = "margin_pdt",
    keep_returns: bool = False,
    keep_trades: bool = False,
) -> dict:
    """One exit on one sample. Overlap, cash, and the PDT check match the scale book."""
    hold = int(cell.max_hold) if cell.max_hold is not None else int(max_hold)
    cash = float(starting_equity)
    busy: Optional[pd.Timestamp] = None
    pnls: list[float] = []
    curve_ords: list[int] = []
    curve_eq: list[float] = []
    skipped = 0
    blocked = 0
    overlapped = 0
    day_trades: list[date] = []
    window_cache: dict[date, set[date]] = {}
    trades: list[dict] = []
    targets: dict[int, int] = {}
    runners: dict[str, int] = {}
    armed = 0
    for path in paths:
        if busy is not None and path.fill <= busy:
            overlapped += 1
            continue
        if account == "margin_pdt":
            window = _pdt_window(path.fill_date, window_cache)
            already = sum(1 for traded in day_trades if traded in window)
            opening = bool(pdt_prospective) or already >= 3
            decision = check_day_trade(
                as_of=path.fill_date,
                equity=cash,
                trade_days=day_trades,
                opening_same_day=opening,
                account_type="margin",
                mode="on",
            )
            if not decision.allowed:
                blocked += 1
                continue
        if not path.ok:
            skipped += 1
            continue
        if path.debit > cash + 1e-9:
            skipped += 1
            continue
        cash -= float(path.debit)
        outcome = _run_path(cell, path, max_hold=hold, base_cash=cash)
        credit = float(outcome["credit"])
        cash += credit
        pnl = credit - float(path.debit)
        pnls.append(pnl)
        exit_index = int(outcome["exit_index"])
        stamps = path.stamps or [path.fill]
        exit_time = stamps[min(exit_index, len(stamps) - 1)]
        busy = pd.Timestamp(exit_time)
        if outcome["entry_sale"]:
            day_trades.append(path.fill_date)
        mark_ords = outcome["mark_ords"]
        mark_eq = outcome["mark_eq"]
        if mark_ords:
            if curve_ords and mark_ords[0] == curve_ords[-1]:
                curve_eq[-1] = mark_eq[0]
                mark_ords = mark_ords[1:]
                mark_eq = mark_eq[1:]
            curve_ords.extend(mark_ords)
            curve_eq.extend(mark_eq)
        bucket = int(outcome["targets_hit"])
        targets[bucket] = targets.get(bucket, 0) + 1
        runners[str(outcome["runner"])] = runners.get(str(outcome["runner"]), 0) + 1
        armed += int(outcome["armed"])
        if keep_trades:
            trades.append(
                {
                    "symbol": path.symbol,
                    "direction": path.direction,
                    "pnl": pnl,
                    "debit": float(path.debit),
                    "reason": outcome["reason"],
                    "runner": outcome["runner"],
                    "targets_hit": bucket,
                    "armed": int(outcome["armed"]),
                    "entry_delta": float(path.delta),
                }
            )
    metrics = _metrics_from_curve(starting_equity, curve_ords, curve_eq, pnls)
    row = {
        "label": cell.label,
        "family": cell.family,
        "stop": float(cell.stop),
        "sharpe": metrics["sharpe"],
        "expectancy": metrics["expectancy"],
        "max_drawdown": metrics["max_drawdown"],
        "trades": metrics["trades"],
        "ending_equity": metrics["ending_equity"],
        "starting_equity": metrics["starting_equity"],
        "win_rate": metrics["win_rate"],
        "profit_factor": metrics["profit_factor"],
        "skipped": skipped,
        "pdt_blocked": blocked,
        "overlapped": overlapped,
        "targets": {str(key): value for key, value in sorted(targets.items())},
        "runner": runners,
        "armed": armed,
    }
    if keep_returns:
        row["returns"] = metrics["returns"]
    if keep_trades:
        row["trade_rows"] = trades
    return row


def choose(rows: list[dict]) -> dict:
    """Pick one cell from training rows. Holdout fields are not read."""

    def _key(row: dict) -> tuple:
        sharpe = row.get("sharpe")
        expectancy = row.get("expectancy")
        drawdown = row.get("max_drawdown")
        sharpe_v = float(sharpe) if sharpe is not None and math.isfinite(float(sharpe)) else float("-inf")
        exp_v = float(expectancy) if expectancy is not None and math.isfinite(float(expectancy)) else float("-inf")
        dd_v = float(drawdown) if drawdown is not None and math.isfinite(float(drawdown)) else float("-inf")
        return (-sharpe_v, -exp_v, -dd_v, str(row.get("label")))

    def _best(pool: list[dict]) -> Optional[dict]:
        if not pool:
            return None
        return min(pool, key=_key)

    primary = [row for row in rows if int(row.get("trades") or 0) >= MIN_TRAIN_TRADES]
    picked = _best(primary)
    if picked is not None:
        return {
            "label": picked["label"],
            "row": {key: picked[key] for key in picked if key not in {"returns", "trade_rows"}},
            "rule": "highest training Sharpe among cells with at least 30 training trades",
            "fallback": False,
            "eligible": len(primary),
        }
    fallback = [row for row in rows if int(row.get("trades") or 0) >= FALLBACK_TRAIN_TRADES]
    picked = _best(fallback)
    if picked is not None:
        return {
            "label": picked["label"],
            "row": {key: picked[key] for key in picked if key not in {"returns", "trade_rows"}},
            "rule": "fallback: highest training Sharpe among cells with at least 15 training trades",
            "fallback": True,
            "eligible": len(fallback),
        }
    return {
        "label": None,
        "row": None,
        "rule": "no cell had 15 training trades",
        "fallback": True,
        "eligible": 0,
    }


def _index(value: float, choices: tuple[float, ...]) -> int:
    for index, item in enumerate(choices):
        if abs(item - value) < 1e-12:
            return index
    return -1


def neighbors(cell: Cell, grid: list[Cell], clock: str) -> list[Cell]:
    """Adjacent stop, runner, first rung, trail, or time stop. At most eight.

    A neighbor that is not itself in the frozen grid is dropped. These rows
    describe fragility. They are not a second search.
    """
    by_label = {item.label: item for item in grid}
    found: list[Cell] = []
    seen = {cell.label}

    def _add(candidate: Optional[Cell]) -> None:
        if candidate is None or candidate.label in seen:
            return
        match = by_label.get(candidate.label)
        if match is None:
            return
        seen.add(match.label)
        found.append(match)

    stop_at = _index(cell.stop, STOPS)
    if stop_at >= 0:
        for shift in (-1, 1):
            nxt = stop_at + shift
            if 0 <= nxt < len(STOPS) and cell.family != "D":
                _add(_moved(cell, stop=STOPS[nxt]))
    if cell.family in {"A", "B", "D", "E"} and any(cell.runner_tier):
        runner_pct = float(cell.pcts[-1])
        runner_at = _index(runner_pct, RUNNER_TARGETS)
        last_fixed = float(cell.pcts[-2]) if len(cell.pcts) > 1 else 0.0
        if runner_at >= 0:
            for shift in (-1, 1):
                nxt = runner_at + shift
                if 0 <= nxt < len(RUNNER_TARGETS) and RUNNER_TARGETS[nxt] > last_fixed:
                    _add(_moved(cell, runner=RUNNER_TARGETS[nxt]))
    if cell.family in {"A", "B"} and cell.pcts:
        first_at = _index(float(cell.pcts[0]), RUNG_TARGETS)
        second = float(cell.pcts[1])
        if first_at >= 0:
            for shift in (-1, 1):
                nxt = first_at + shift
                if 0 <= nxt < len(RUNG_TARGETS) and RUNG_TARGETS[nxt] < second:
                    _add(_moved(cell, first=RUNG_TARGETS[nxt]))
    if cell.family == "C":
        target_at = _index(float(cell.pcts[0]), ALL_OUT_TARGETS)
        if target_at >= 0:
            for shift in (-1, 1):
                nxt = target_at + shift
                if 0 <= nxt < len(ALL_OUT_TARGETS):
                    _add(_moved(cell, target=ALL_OUT_TARGETS[nxt]))
    if cell.trail > 0.0:
        trail_at = _index(cell.trail, TRAIL_PCTS)
        if trail_at >= 0:
            for shift in (-1, 1):
                nxt = trail_at + shift
                if 0 <= nxt < len(TRAIL_PCTS):
                    _add(_moved(cell, trail=TRAIL_PCTS[nxt]))
    if cell.max_hold is not None:
        schedule = HOURLY_TIME_STOPS if clock == "hourly" else DAILY_TIME_STOPS
        hold_at = _index(float(cell.max_hold), tuple(float(item) for item in schedule))
        if hold_at >= 0:
            for shift in (-1, 1):
                nxt = hold_at + shift
                if 0 <= nxt < len(schedule):
                    _add(_moved(cell, max_hold=schedule[nxt]))
    return found[:8]


def _moved(
    cell: Cell,
    *,
    stop: Optional[float] = None,
    runner: Optional[float] = None,
    first: Optional[float] = None,
    target: Optional[float] = None,
    trail: Optional[float] = None,
    max_hold: Optional[int] = None,
) -> Cell:
    new_stop = float(cell.stop if stop is None else stop)
    new_trail = float(cell.trail if trail is None else trail)
    new_hold = cell.max_hold if max_hold is None else int(max_hold)
    if cell.family == "C":
        new_target = float(cell.pcts[0] if target is None else target)
        label = f"C all-out {_pct(new_target)} stop {_stop_pct(new_stop)}"
        return Cell("C", label, new_stop, (new_target,), (5,), (False,), 0.0, None, 0)
    pcts = list(cell.pcts)
    if first is not None:
        pcts[0] = float(first)
    if runner is not None and any(cell.runner_tier):
        pcts[-1] = float(runner)
    if any(cell.runner_tier):
        rungs = tuple(pcts[:-1])
        qtys = tuple(cell.qtys[:-1])
        return _scale_cell(
            cell.family,
            rungs,
            qtys,
            pcts[-1],
            new_stop,
            trail=new_trail,
            max_hold=new_hold,
        )
    label = (
        f"E stop {_stop_pct(new_stop)} rungs +15%/+25%/+40% "
        f"runner trail {new_trail:.0%} no limit"
    )
    return Cell(
        "E",
        label,
        new_stop,
        tuple(pcts),
        tuple(cell.qtys),
        tuple(cell.runner_tier),
        new_trail,
        new_hold,
        1,
    )


def sized_equity(paths: list[QuotePath], stop: float) -> float:
    """Training median equity that puts this premium stop near 2% of the account."""
    required = [
        required_capital(path.ask, path.debit, stop)
        for path in paths
        if path.ok and path.ask > 0.0 and path.debit > 0.0
    ]
    if not required:
        return float("nan")
    return float(np.median(required))


def build_paths(
    setups,
    execution: dict[str, pd.DataFrame],
    daily: dict[str, pd.DataFrame],
    params: dict,
    *,
    session_filter: bool,
) -> list[QuotePath]:
    """Price each five-lot once. The exit grid replays these bids."""
    frames = _prepare(execution, session_filter)
    realized = _realized(daily)
    chosen = dict(params)
    chosen.pop("exit_style", None)
    chosen["fixed_contracts"] = 5
    chosen["expression"] = "single"
    chosen["dte"] = ATM_DTE
    chosen["delta"] = ATM_DELTA
    ordered = sorted(setups, key=lambda setup: (pd.Timestamp(setup.fill_time), setup.symbol, setup.direction))
    paths: list[QuotePath] = []
    blank_cash = 1.0e12
    started = time.perf_counter()
    for index, setup in enumerate(ordered, start=1):
        if index % 200 == 0:
            print(f"    priced {index}/{len(ordered)} in {time.perf_counter() - started:.1f}s", flush=True)
        fill = pd.Timestamp(setup.fill_time)
        opened = _open(setup, fill, frames, realized, {}, {}, blank_cash, blank_cash, chosen, CostModel())
        if opened is None:
            paths.append(
                QuotePath(
                    symbol=str(setup.symbol),
                    direction=str(setup.direction),
                    fill=fill,
                    fill_date=_session(fill),
                    ok=False,
                )
            )
            continue
        frame = frames.get(setup.symbol)
        if frame is None or fill not in frame.index:
            paths.append(
                QuotePath(str(setup.symbol), str(setup.direction), fill, _session(fill), False)
            )
            continue
        start = frame.index.get_loc(fill)
        if isinstance(start, slice):
            start = start.start
        if isinstance(start, np.ndarray):
            start = int(start[0])
        opened_on = _session(fill)
        expiry = opened_on + timedelta(days=ATM_DTE)
        stamps: list[pd.Timestamp] = []
        spots_open: list[float] = []
        spots_adv: list[float] = []
        spots_fav: list[float] = []
        spots_close: list[float] = []
        entry_flags: list[bool] = []
        last_flags: list[bool] = []
        held_flags: list[int] = []
        expired_flags: list[bool] = []
        session_ords: list[int] = []
        for ts, row in frame.iloc[int(start) :].iterrows():
            ts = pd.Timestamp(ts)
            try:
                open_ = float(row["open"])
                high = float(row["high"])
                low = float(row["low"])
                close = float(row["close"])
            except (TypeError, ValueError, KeyError):
                continue
            if not all(math.isfinite(value) and value > 0.0 for value in (open_, high, low, close)):
                continue
            if opened["direction"] == "long":
                adverse, favorable = low, high
            else:
                adverse, favorable = high, low
            session = _session(ts)
            stamps.append(ts)
            spots_open.append(open_)
            spots_adv.append(adverse)
            spots_fav.append(favorable)
            spots_close.append(close)
            entry_flags.append(ts == fill)
            last_flags.append(_is_last_rth(ts, frame.index))
            held_flags.append(_sessions_held(opened_on, session))
            expired_flags.append(session >= expiry)
            session_ords.append(session.toordinal())
            if session >= expiry and last_flags[-1]:
                break
        if not stamps:
            paths.append(QuotePath(str(setup.symbol), str(setup.direction), fill, opened_on, False))
            continue
        open_bid = np.empty(len(stamps))
        adverse_bid = np.empty(len(stamps))
        favorable_bid = np.empty(len(stamps))
        close_bid = np.empty(len(stamps))
        for index, ts in enumerate(stamps):
            open_bid[index] = _option_bid(opened, ts, spots_open[index], chosen)
            adverse_bid[index] = _option_bid(opened, ts, spots_adv[index], chosen)
            favorable_bid[index] = _option_bid(opened, ts, spots_fav[index], chosen)
            close_bid[index] = _option_bid(opened, ts, spots_close[index], chosen)
        paths.append(
            QuotePath(
                symbol=str(setup.symbol),
                direction=str(opened["direction"]),
                fill=fill,
                fill_date=opened_on,
                ok=True,
                ask=float(opened["entry"]),
                debit=float(opened["debit"]),
                delta=float(opened["delta"]),
                open_bid=open_bid,
                adverse_bid=adverse_bid,
                favorable_bid=favorable_bid,
                close_bid=close_bid,
                entry_bar=np.asarray(entry_flags, dtype=bool),
                is_last=np.asarray(last_flags, dtype=bool),
                held=np.asarray(held_flags, dtype=int),
                expired=np.asarray(expired_flags, dtype=bool),
                session=np.asarray(session_ords, dtype=int),
                stamps=stamps,
            )
        )
    return paths


def filter_paths(paths: list[QuotePath], start: date, end: date) -> list[QuotePath]:
    return [path for path in paths if start <= path.fill_date <= end]


def truncate_paths(paths: list[QuotePath], end: date) -> list[QuotePath]:
    """Drop bars after ``end`` so a training fold cannot see its test window.

    The last bar of a session is already marked as the session's last bar.
    A trade still open on that bar exits as a window end inside the runner.
    """
    limit = end.toordinal()
    trimmed: list[QuotePath] = []
    for path in paths:
        if not path.ok or path.session is None or path.stamps is None:
            trimmed.append(path)
            continue
        keep = int(np.searchsorted(path.session, limit, side="right"))
        if keep <= 0:
            trimmed.append(
                QuotePath(path.symbol, path.direction, path.fill, path.fill_date, False)
            )
            continue
        if keep >= len(path.session):
            trimmed.append(path)
            continue
        trimmed.append(
            QuotePath(
                symbol=path.symbol,
                direction=path.direction,
                fill=path.fill,
                fill_date=path.fill_date,
                ok=True,
                ask=path.ask,
                debit=path.debit,
                delta=path.delta,
                open_bid=path.open_bid[:keep],
                adverse_bid=path.adverse_bid[:keep],
                favorable_bid=path.favorable_bid[:keep],
                close_bid=path.close_bid[:keep],
                entry_bar=path.entry_bar[:keep],
                is_last=path.is_last[:keep],
                held=path.held[:keep],
                expired=path.expired[:keep],
                session=path.session[:keep],
                stamps=path.stamps[:keep],
            )
        )
    return trimmed


def deflated_sharpe(returns: np.ndarray, n_trials: int) -> dict:
    """Bailey and Lopez de Prado deflated Sharpe.

    The hurdle is the Sharpe expected from the best of ``n_trials`` tries
    when the true Sharpe is zero. DSR is the probability the true per-period
    Sharpe clears that hurdle, given this return series. Kurtosis is Pearson
    (a normal sample is about 3).
    """
    rets = np.asarray(returns, dtype=float)
    rets = rets[np.isfinite(rets)]
    count = int(len(rets))
    empty = {
        "dsr": None,
        "sr_period": None,
        "sr_annual": None,
        "sr_star_period": None,
        "sr_star_annual": None,
        "skew": None,
        "kurtosis": None,
        "observations": count,
        "trials": int(n_trials),
    }
    if count < 3 or n_trials < 1:
        return empty
    mean = float(rets.mean())
    std = float(rets.std())
    if std <= 0.0:
        return empty
    sr = mean / std
    centered = rets - mean
    moment2 = float(np.mean(centered ** 2))
    if moment2 <= 0.0:
        return empty
    skew = float(np.mean(centered ** 3) / (moment2 ** 1.5))
    kurtosis = float(np.mean(centered ** 4) / (moment2 ** 2))
    if n_trials <= 1:
        hurdle_z = 0.0
    else:
        hurdle_z = (1.0 - _EULER) * _norm_ppf(1.0 - 1.0 / n_trials) + _EULER * _norm_ppf(
            1.0 - 1.0 / (n_trials * math.e)
        )
    variance_term = 1.0 - skew * sr + ((kurtosis - 1.0) / 4.0) * sr * sr
    if variance_term <= 1e-12:
        variance_term = 1e-12
    sigma = math.sqrt(variance_term / (count - 1))
    sr_star = sigma * hurdle_z
    dsr = _norm_cdf((sr - sr_star) / sigma)
    annual = math.sqrt(252.0)
    return {
        "dsr": float(dsr),
        "sr_period": float(sr),
        "sr_annual": float(sr * annual),
        "sr_star_period": float(sr_star),
        "sr_star_annual": float(sr_star * annual),
        "skew": skew,
        "kurtosis": kurtosis,
        "observations": count,
        "trials": int(n_trials),
    }


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_ppf(p: float) -> float:
    """Acklam's inverse normal. Accurate enough for the trial hurdle."""
    if p <= 0.0:
        return float("-inf")
    if p >= 1.0:
        return float("inf")
    a = (
        -3.969683028665376e01,
        2.209460984245205e02,
        -2.759285104469687e02,
        1.383577518672690e02,
        -3.066479806614716e01,
        2.506628277459239e00,
    )
    b = (
        -5.447609879822406e01,
        1.615858368580409e02,
        -1.556989798598866e02,
        6.680131188771972e01,
        -1.328068155288572e01,
    )
    c = (
        -7.784894002430293e-03,
        -3.223964580411365e-01,
        -2.400758277161838e00,
        -2.549732539343734e00,
        4.374664141464968e00,
        2.938163982698783e00,
    )
    d = (
        7.784695709041462e-03,
        3.224671290700398e-01,
        2.445134137142996e00,
        3.754408661907416e00,
    )
    plow = 0.02425
    phigh = 1.0 - plow
    if p < plow:
        q = math.sqrt(-2.0 * math.log(p))
        return (
            (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5])
            / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0)
        )
    if p > phigh:
        q = math.sqrt(-2.0 * math.log(1.0 - p))
        return -(
            (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5])
            / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0)
        )
    q = p - 0.5
    r = q * q
    return (
        (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5])
        * q
        / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1.0)
    )


def holds_up(holdout: dict, random_row: dict, walk_expectancy: Optional[float]) -> tuple[bool, list[str]]:
    """Pre-registered bar for wiring the chop options sub-book. Not the old 300-trade gate."""
    reasons: list[str] = []
    if float(holdout.get("expectancy") or 0.0) <= 0.0:
        reasons.append("holdout expectancy is not positive after costs")
    if float(holdout.get("ending_equity") or 0.0) <= float(holdout.get("starting_equity") or 0.0):
        reasons.append("holdout ending equity is not above the start")
    if int(holdout.get("trades") or 0) < HOLDS_UP_MIN_TRADES:
        reasons.append("fewer than 20 holdout trades")
    if float(holdout.get("sharpe") or 0.0) <= 0.0:
        reasons.append("holdout Sharpe is not positive")
    if not beats(holdout, random_row):
        reasons.append("it does not beat random entries on Sharpe with a drawdown that is not worse")
    if walk_expectancy is None or not math.isfinite(float(walk_expectancy)) or float(walk_expectancy) <= 0.0:
        reasons.append("walk-forward pooled expectancy is not positive")
    return (not reasons), reasons


def beats(candidate: dict, baseline: dict) -> bool:
    if int(candidate.get("trades") or 0) < HOLDS_UP_MIN_TRADES or int(baseline.get("trades") or 0) < 1:
        return False
    if float(candidate.get("sharpe") or 0.0) <= float(baseline.get("sharpe") or 0.0):
        return False
    return float(candidate.get("max_drawdown") or 0.0) >= float(baseline.get("max_drawdown") or 0.0)


def public_row(row: dict) -> dict:
    """Drop arrays before a report or a JSON dump."""
    skip = {"returns", "trade_rows"}
    return {key: value for key, value in row.items() if key not in skip}
