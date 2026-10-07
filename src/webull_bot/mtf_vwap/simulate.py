"""$1,000 option and stock books for the VWAP-test setups.

Whole contracts only. One contract is skipped when its debit is above the
pre-registered fraction of equity. The default account is margin under
$25,000, so a fourth day trade in five sessions is blocked. A cash variant
does not reuse a sale until the next session. Option prices are
Black-Scholes. Nothing here calls a broker.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Optional

import numpy as np
import pandas as pd

from webull_bot.backtest.engine import BacktestResult
from webull_bot.backtest.metrics import compute_metrics
from webull_bot.calendar import next_trading_day
from webull_bot.costs import CostModel, buy_price, sell_price
from webull_bot.mtf_vwap.detect import Setup, rth, session_vwap
from webull_bot.options.fees import CONTRACT_MULTIPLIER, option_leg_fees
from webull_bot.options.pricing import (
    listed_strike,
    option_delta,
    option_price,
    realized_vol,
    strike_for_delta,
    strike_for_put_delta,
)
from webull_bot.risk.pdt import check_day_trade

RATE = 0.02
DIVIDEND = 0.018
HALF_SPREAD_ATM = 0.04
HALF_SPREAD_OTM = 0.08
HALF_SPREAD_CHEAP = 0.12
CHEAP_MID = 1.00
MIN_MID = 0.05
VOL_FLOOR = 0.10
VOL_CAP = 1.50
BUST_FLOOR = 100.0


@dataclass
class BookStats:
    metrics: dict[str, Any]
    trades: pd.DataFrame
    equity: pd.Series
    pdt_blocked: int = 0
    premium_skipped: int = 0
    bust: bool = False
    min_equity: float = 0.0
    ruin_estimate: Optional[float] = None
    ending_equity: float = 0.0
    extra: dict[str, Any] = field(default_factory=dict)


def _half_spread(delta: float, mid: float, multiplier: float) -> float:
    if mid < CHEAP_MID:
        base = HALF_SPREAD_CHEAP
    elif abs(delta) >= 0.50:
        base = HALF_SPREAD_ATM
    else:
        base = HALF_SPREAD_OTM
    return base * multiplier


def _buy(mid: float, delta: float, multiplier: float) -> float:
    return max(MIN_MID, mid) * (1.0 + _half_spread(delta, mid, multiplier))


def _sell(mid: float, delta: float, multiplier: float) -> float:
    return max(0.0, mid * (1.0 - _half_spread(delta, mid, multiplier)))


def _years(dte: int, stamp: pd.Timestamp) -> float:
    clock = pd.Timestamp(stamp)
    if clock.tzinfo is not None:
        clock = clock.tz_convert("America/New_York")
    minutes_left = max(0, (16 * 60) - (clock.hour * 60 + clock.minute))
    return max(0.0, (dte + minutes_left / (24 * 60)) / 365.0)


def _vol(rv: pd.Series, day: date, iv_premium: float) -> Optional[float]:
    if rv.empty:
        return None
    stamp = pd.Timestamp(day)
    value = rv.asof(stamp)
    if value is None or pd.isna(value):
        return None
    scaled = float(value) * iv_premium
    if not np.isfinite(scaled):
        return None
    return min(VOL_CAP, max(VOL_FLOOR, scaled))


def _session(stamp: pd.Timestamp) -> date:
    ts = pd.Timestamp(stamp)
    if ts.tzinfo is not None:
        ts = ts.tz_convert("America/New_York")
    return ts.date()


def simulate_options(
    setups: list[Setup],
    execution: dict[str, pd.DataFrame],
    daily: dict[str, pd.DataFrame],
    params: dict,
    *,
    starting_equity: float = 1_000.0,
) -> BookStats:
    return _simulate(setups, execution, daily, params, starting_equity=starting_equity, kind="option")


def simulate_stock(
    setups: list[Setup],
    execution: dict[str, pd.DataFrame],
    daily: dict[str, pd.DataFrame],
    params: dict,
    *,
    starting_equity: float = 1_000.0,
    costs: CostModel | None = None,
) -> BookStats:
    return _simulate(
        setups, execution, daily, params,
        starting_equity=starting_equity, kind="stock", costs=costs or CostModel(),
    )


def _simulate(
    setups: list[Setup],
    execution: dict[str, pd.DataFrame],
    daily: dict[str, pd.DataFrame],
    params: dict,
    *,
    starting_equity: float,
    kind: str,
    costs: CostModel | None = None,
) -> BookStats:
    frames = {symbol: rth(frame) for symbol, frame in execution.items() if frame is not None and len(frame)}
    if not frames:
        return _empty(starting_equity)
    clock = pd.DatetimeIndex(sorted(set().union(*[frame.index for frame in frames.values()])))
    vwaps = {symbol: session_vwap(frame)["vwap"] for symbol, frame in frames.items()}
    rv = {}
    for symbol, frame in daily.items():
        if frame is None or frame.empty:
            continue
        series = realized_vol(frame["close"].astype(float)).shift(1)
        index = pd.DatetimeIndex(series.index)
        if index.tz is not None:
            index = index.tz_convert("America/New_York").tz_localize(None)
        series.index = index.normalize()
        rv[symbol] = series
    by_fill: dict[pd.Timestamp, list[Setup]] = {}
    for setup in setups:
        if setup.symbol not in frames:
            continue
        by_fill.setdefault(pd.Timestamp(setup.fill_time), []).append(setup)

    cash = float(starting_equity)
    settled = float(starting_equity)
    unsettled: list[tuple[date, float]] = []
    positions: list[dict[str, Any]] = []
    closed: list[dict[str, Any]] = []
    day_trades: list[date] = []
    equity_values: list[float] = []
    exposure_values: list[float] = []
    index: list[pd.Timestamp] = []
    pdt_blocked = 0
    premium_skipped = 0
    account = str(params.get("account", "margin_pdt"))
    cap = float(params["premium_cap"])
    max_positions = int(params["max_positions"])
    dte = int(params["dte"])
    flatten_eod = bool(params["flatten_eod"]) or dte <= 0
    max_sessions = 1 if flatten_eod else int(params.get("max_hold_sessions", 2))

    for ts in clock:
        ts = pd.Timestamp(ts)
        session = _session(ts)
        if account == "cash_t1":
            still_cash = []
            for available_on, amount in unsettled:
                if available_on <= session:
                    settled += amount
                else:
                    still_cash.append((available_on, amount))
            unsettled = still_cash
        equity_now = cash + _mark_positions(positions, frames, ts, params, kind, field="open")
        entries = by_fill.get(ts, [])
        for setup in entries:
            if len(positions) >= max_positions:
                break
            if any(pos["symbol"] == setup.symbol for pos in positions):
                continue
            if account == "margin_pdt":
                # Every new entry can be stopped out today. At three day
                # trades already on the books, that stop would be a fourth,
                # so the entry is skipped until one ages out of the window.
                decision = check_day_trade(
                    as_of=session,
                    equity=equity_now,
                    trade_days=day_trades,
                    opening_same_day=True,
                    account_type="margin",
                    mode="on",
                )
                if not decision.allowed:
                    pdt_blocked += 1
                    continue
            opened = _open(setup, ts, frames, rv, equity_now, settled if account == "cash_t1" else cash, params, kind, costs)
            if opened is None:
                premium_skipped += 1
                continue
            cash -= opened["debit"]
            if account == "cash_t1":
                settled -= opened["debit"]
            positions.append(opened)
            equity_now = cash + _mark_positions(positions, frames, ts, params, kind, field="open")

        last_bar = _is_last_rth(ts, clock)
        still = []
        for pos in positions:
            sessions_held = _sessions_held(pos["opened_on"], session)
            reason = _exit_reason(pos, ts, frames, vwaps, params, kind, last_bar, sessions_held, max_sessions)
            if reason is None:
                still.append(pos)
                continue
            credit = _credit(pos, ts, frames, params, kind, reason, costs)
            cash += credit
            if account == "cash_t1":
                unsettled.append((next_trading_day(session), credit))
            if pos["opened_on"] == session:
                day_trades.append(session)
            closed.append(_row(pos, ts, credit, reason))
        positions = still
        equity_now = cash + _mark_positions(positions, frames, ts, params, kind, field="close")
        at_risk = sum(pos["debit"] for pos in positions)
        equity_values.append(equity_now)
        exposure_values.append(at_risk / equity_now if equity_now else 0.0)
        index.append(ts)

    if positions and index:
        ts = index[-1]
        for pos in positions:
            credit = _credit(pos, ts, frames, params, kind, "window_end", costs)
            cash += credit
            closed.append(_row(pos, ts, credit, "window_end"))
        equity_values[-1] = cash
        exposure_values[-1] = 0.0

    equity = pd.Series(equity_values, index=pd.DatetimeIndex(index), name="equity")
    exposure = pd.Series(exposure_values, index=equity.index, name="exposure") if len(equity) else pd.Series(dtype=float)
    trades = pd.DataFrame(closed)
    result = BacktestResult(
        equity=equity,
        exposure=exposure,
        trades=trades,
        ending_equity=float(equity.iloc[-1]) if len(equity) else starting_equity,
    )
    metrics = compute_metrics(result, starting_equity)
    min_equity = float(equity.min()) if len(equity) else starting_equity
    bust = bool(len(equity) and (equity < BUST_FLOOR).any())
    return BookStats(
        metrics=metrics,
        trades=trades,
        equity=equity,
        pdt_blocked=pdt_blocked,
        premium_skipped=premium_skipped,
        bust=bust,
        min_equity=min_equity,
        ruin_estimate=_ruin(trades, starting_equity),
        ending_equity=float(metrics["ending_equity"]),
    )


def _open(setup, ts, frames, rv, equity, buying_cash, params, kind, costs) -> Optional[dict]:
    frame = frames.get(setup.symbol)
    if frame is None or ts not in frame.index:
        return None
    spot = float(frame.loc[ts, "open"])
    if not np.isfinite(spot) or spot <= 0:
        return None
    cap_cash = equity * float(params["premium_cap"])
    budget = min(cap_cash, buying_cash)
    if kind == "stock":
        fill = buy_price(spot, costs) if setup.direction == "long" else sell_price(spot, costs)
        shares = int(np.floor(budget / fill)) if fill > 0 else 0
        if shares < 1:
            return None
        debit = shares * fill
        return {
            "symbol": setup.symbol,
            "direction": setup.direction,
            "right": "call" if setup.direction == "long" else "put",
            "quantity": shares,
            "debit": debit,
            "entry": fill,
            "opened_on": _session(ts),
            "entry_time": ts,
            "stop": float(setup.stop),
            "target": setup.target,
            "bars": 0,
        }
    sigma = _vol(rv.get(setup.symbol, pd.Series(dtype=float)), _session(ts), float(params["iv_premium"]))
    if sigma is None:
        return None
    years = _years(int(params["dte"]), ts)
    if years <= 0 and int(params["dte"]) > 0:
        years = int(params["dte"]) / 365.0
    right = "call" if setup.direction == "long" else "put"
    raw = (
        strike_for_delta(spot, max(years, 1 / 365), sigma, float(params["delta"]), RATE, DIVIDEND)
        if right == "call"
        else strike_for_put_delta(spot, max(years, 1 / 365), sigma, float(params["delta"]), RATE, DIVIDEND)
    )
    strike = listed_strike(spot, raw)
    mid = option_price(right, spot, strike, max(years, 1 / 3650), sigma, RATE, DIVIDEND)
    delta = option_delta(right, spot, strike, max(years, 1 / 3650), sigma, RATE, DIVIDEND)
    ask = _buy(mid, delta, float(params["spread_multiplier"]))
    one = ask * CONTRACT_MULTIPLIER + option_leg_fees(1, ask, sell=False)
    if one > budget or one <= 0:
        return None
    contracts = int(np.floor(budget / one))
    if contracts < 1:
        return None
    fees = option_leg_fees(contracts, ask, sell=False)
    debit = contracts * ask * CONTRACT_MULTIPLIER + fees
    return {
        "symbol": setup.symbol,
        "direction": setup.direction,
        "right": right,
        "quantity": contracts,
        "debit": debit,
        "entry": ask,
        "strike": strike,
        "sigma": sigma,
        "expiry_years": years,
        "opened_on": _session(ts),
        "entry_time": ts,
        "stop": float(setup.stop),
        "target": setup.target,
        "delta": delta,
        "bars": 0,
    }


def _exit_reason(pos, ts, frames, vwaps, params, kind, last_bar, sessions_held, max_sessions) -> Optional[str]:
    frame = frames[pos["symbol"]]
    if ts not in frame.index:
        return None
    row = frame.loc[ts]
    high = float(row["high"])
    low = float(row["low"])
    close = float(row["close"])
    opened = float(row["open"])
    pos["bars"] += 1
    vwap = vwaps[pos["symbol"]]
    vwap_now = float(vwap.loc[ts]) if ts in vwap.index and np.isfinite(vwap.loc[ts]) else np.nan
    if kind == "option":
        stop_hit, target_hit = _option_extremes(pos, ts, opened, high, low, close, params)
        if stop_hit and target_hit:
            return "premium_stop"
        if stop_hit:
            return "premium_stop"
        if target_hit:
            return "premium_target"
    if pos["direction"] == "long":
        if np.isfinite(pos["stop"]) and (opened <= pos["stop"] or low <= pos["stop"]):
            return "invalidation"
        if np.isfinite(vwap_now) and close < vwap_now:
            return "vwap_lost"
        if pos["target"] is not None and high >= float(pos["target"]):
            return "level_target"
    else:
        if np.isfinite(pos["stop"]) and (opened >= pos["stop"] or high >= pos["stop"]):
            return "invalidation"
        if np.isfinite(vwap_now) and close > vwap_now:
            return "vwap_lost"
        if pos["target"] is not None and low <= float(pos["target"]):
            return "level_target"
    if sessions_held >= max_sessions and last_bar:
        return "time_stop"
    if bool(params.get("flatten_eod")) and last_bar:
        return "session_flat"
    return None


def _option_extremes(pos, ts, opened, high, low, close, params) -> tuple[bool, bool]:
    entry = float(pos["entry"])
    stop_line = entry * (1.0 + float(params["premium_stop"]))
    target_line = entry * (1.0 + float(params["premium_target"]))
    adverse = low if pos["direction"] == "long" else high
    favorable = high if pos["direction"] == "long" else low
    # A gap through the stop is the open, not a price inside the bar.
    if pos["direction"] == "long" and opened < pos["stop"]:
        adverse = opened
    if pos["direction"] == "short" and opened > pos["stop"]:
        adverse = opened
    stop_bid = _option_bid(pos, ts, adverse, params)
    target_bid = _option_bid(pos, ts, favorable, params)
    return stop_bid <= stop_line, target_bid >= target_line


def _option_bid(pos, ts, spot: float, params) -> float:
    years = _years_left(pos, ts)
    mid = option_price(pos["right"], spot, pos["strike"], years, pos["sigma"], RATE, DIVIDEND)
    delta = option_delta(pos["right"], spot, pos["strike"], years, pos["sigma"], RATE, DIVIDEND)
    return _sell(mid, delta, float(params["spread_multiplier"]))


def _years_left(pos, ts) -> float:
    opened = pd.Timestamp(pos["entry_time"])
    now = pd.Timestamp(ts)
    elapsed = max(0.0, (now - opened).total_seconds() / (365.0 * 24 * 3600))
    return max(0.0, float(pos["expiry_years"]) - elapsed)


def _credit(pos, ts, frames, params, kind, reason, costs) -> float:
    frame = frames[pos["symbol"]]
    row = frame.loc[ts]
    if kind == "stock":
        if reason == "invalidation":
            raw = float(pos["stop"])
            if pos["direction"] == "long" and float(row["open"]) <= raw:
                raw = float(row["open"])
            if pos["direction"] == "short" and float(row["open"]) >= raw:
                raw = float(row["open"])
        elif reason == "level_target" and pos["target"] is not None:
            raw = float(pos["target"])
        else:
            raw = float(row["close"])
        if pos["direction"] == "long":
            fill = sell_price(raw, costs)
            return pos["quantity"] * fill
        fill = buy_price(raw, costs)
        return pos["debit"] + (pos["entry"] - fill) * pos["quantity"]
    if reason == "premium_target":
        bid = float(pos["entry"]) * (1.0 + float(params["premium_target"]))
    elif reason == "premium_stop":
        spot = float(row["open"]) if (
            (pos["direction"] == "long" and float(row["open"]) <= pos["stop"])
            or (pos["direction"] == "short" and float(row["open"]) >= pos["stop"])
        ) else (float(row["low"]) if pos["direction"] == "long" else float(row["high"]))
        bid = min(_option_bid(pos, ts, spot, params), float(pos["entry"]) * (1.0 + float(params["premium_stop"])))
    elif reason == "level_target" and pos["target"] is not None:
        bid = _option_bid(pos, ts, float(pos["target"]), params)
    elif reason == "invalidation":
        spot = float(pos["stop"])
        if pos["direction"] == "long" and float(row["open"]) < spot:
            spot = float(row["open"])
        if pos["direction"] == "short" and float(row["open"]) > spot:
            spot = float(row["open"])
        bid = _option_bid(pos, ts, spot, params)
    else:
        bid = _option_bid(pos, ts, float(row["close"]), params)
    fees = option_leg_fees(int(pos["quantity"]), bid, sell=True)
    return max(0.0, pos["quantity"] * bid * CONTRACT_MULTIPLIER - fees)


def _mark_positions(positions, frames, ts, params, kind, field: str) -> float:
    marked = 0.0
    for pos in positions:
        frame = frames.get(pos["symbol"])
        if frame is None or ts not in frame.index:
            marked += pos["debit"]
            continue
        spot = float(frame.loc[ts, field if field in frame.columns else "close"])
        if kind == "stock":
            if pos["direction"] == "long":
                marked += pos["quantity"] * spot
            else:
                marked += pos["debit"] + (pos["entry"] - spot) * pos["quantity"]
        else:
            bid = _option_bid(pos, ts, spot, params)
            marked += pos["quantity"] * bid * CONTRACT_MULTIPLIER
    return marked


def _row(pos, ts, credit, reason) -> dict:
    return {
        "symbol": pos["symbol"],
        "strategy": pos["direction"],
        "quantity": pos["quantity"],
        "entry_time": pos["entry_time"],
        "entry_price": pos["entry"],
        "exit_time": ts,
        "exit_price": credit / pos["quantity"] if pos["quantity"] else 0.0,
        "pnl": credit - pos["debit"],
        "fees": 0.0,
        "reason": reason,
        "bars_held": pos["bars"],
    }


def _sessions_held(opened: date, today: date) -> int:
    if today <= opened:
        return 1
    cursor = opened
    count = 1
    while cursor < today and count < 8:
        cursor = next_trading_day(cursor)
        count += 1
    return count


def _is_last_rth(ts: pd.Timestamp, clock: pd.DatetimeIndex) -> bool:
    loc = clock.get_loc(ts)
    if isinstance(loc, slice):
        loc = loc.start
    if loc >= len(clock) - 1:
        return True
    return _session(clock[loc + 1]) != _session(ts)


def _ruin(trades: pd.DataFrame, starting: float) -> Optional[float]:
    """Chance of eventually going broke if these payoffs repeated. An estimate."""
    if trades is None or trades.empty or len(trades) < 5:
        return None
    pnl = trades["pnl"].astype(float)
    wins = pnl[pnl > 0]
    losses = pnl[pnl < 0]
    if len(wins) == 0 or len(losses) == 0:
        return 0.0 if len(losses) == 0 else 1.0
    probability = float(len(wins) / len(pnl))
    average_win = float(wins.mean())
    average_loss = float(-losses.mean())
    edge = probability * average_win - (1.0 - probability) * average_loss
    if edge <= 0:
        return 1.0
    ratio = ((1.0 - probability) * average_loss) / (probability * average_win)
    units = starting / average_loss
    if ratio >= 1:
        return 1.0
    return float(min(1.0, ratio ** units))


def _empty(starting: float) -> BookStats:
    metrics = compute_metrics(
        BacktestResult(pd.Series(dtype=float), pd.Series(dtype=float), pd.DataFrame()),
        starting,
    )
    return BookStats(
        metrics=metrics,
        trades=pd.DataFrame(),
        equity=pd.Series(dtype=float),
        min_equity=starting,
        ending_equity=starting,
        ruin_estimate=None,
    )
