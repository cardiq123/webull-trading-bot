"""Long calls and puts that exit at +30% of the premium paid.

This is a model. The option price is Black-Scholes on the underlying's
daily open, high, low, and close. There is no option high and no chain.
The pre-registered default checks the +30% target on the favorable
underlying extreme (the high for a call, the low for a put) and the
premium stop on the adverse extreme. If both could have traded, the stop
fills. A close-based variant marks both at the close.

The fill at the target is the limit (+30% of the ask that was paid), not
the full overshoot. A premium stop that gaps through fills at the worse
bid. Walk-forward does not choose DTE, delta, the target, or the stop.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from webull_bot.backtest.engine import BacktestResult
from webull_bot.backtest.metrics import compute_metrics
from webull_bot.options.fees import CONTRACT_MULTIPLIER, option_leg_fees
from webull_bot.options.pricing import listed_strike, option_delta, option_price, realized_vol, strike_for_delta, strike_for_put_delta

RATE = 0.02
DIVIDEND = 0.018
# Fixed before the run. Sensitivities change one of these at a time.
DEFAULT_DTE = 30
DEFAULT_DELTA = 0.65
PREMIUM_TARGET = 0.30
PREMIUM_STOP = -0.50
MAX_HOLD = 10
HALF_SPREAD_ATM = 0.04
HALF_SPREAD_OTM = 0.08
MIN_MID = 0.05
VOL_FLOOR = 0.10
VOL_CAP = 1.50


def simulate_premium_book(
    entries: list[dict[str, Any]],
    bars: dict[str, pd.DataFrame],
    *,
    dte: int = DEFAULT_DTE,
    delta: float = DEFAULT_DELTA,
    iv_premium: float = 1.15,
    spread_multiplier: float = 1.0,
    premium_stop: float = PREMIUM_STOP,
    path: str = "extreme",
    max_hold: int = MAX_HOLD,
    risk_fraction: float = 0.015,
    starting_equity: float = 100_000.0,
    max_positions: int = 5,
    trade_end: pd.Timestamp | None = None,
) -> dict[str, Any]:
    """``path`` is ``extreme`` or ``close``. ``entries`` fill on ``fill_time``."""
    if path not in {"extreme", "close"}:
        raise ValueError(path)
    empty = _empty(starting_equity)
    if not entries or "SPY" not in bars:
        return empty
    clock = bars["SPY"].index
    if trade_end is not None:
        clock = clock[clock <= pd.Timestamp(trade_end)]
    if len(clock) == 0:
        return empty
    rv_cache = {symbol: realized_vol(frame["close"]).shift(1) for symbol, frame in bars.items() if frame is not None and len(frame)}
    pending: dict[pd.Timestamp, list[dict[str, Any]]] = {}
    for entry in entries:
        pending.setdefault(pd.Timestamp(entry["fill_time"]), []).append(entry)

    cash = float(starting_equity)
    positions: list[dict[str, Any]] = []
    closed: list[dict[str, Any]] = []
    equity_values: list[float] = []
    exposure_values: list[float] = []
    index: list[pd.Timestamp] = []
    peak = cash
    drawdown_halt = False
    day_start = cash

    for ts in clock:
        ts = pd.Timestamp(ts)
        equity_open = cash + _mark(positions, ts, bars, iv_premium, field="open")
        day_start = equity_open
        if peak > 0 and (1.0 - equity_open / peak) >= 0.15 - 1e-12:
            drawdown_halt = True
        # Fills at the open use the cash available then. A stop later in the
        # day does not fund another entry on the same open.
        if not drawdown_halt:
            equity_now = equity_open
            for spec in pending.get(ts, []):
                if len(positions) >= max_positions:
                    break
                if any(pos["symbol"] == spec["symbol"] for pos in positions):
                    continue
                opened = _open_position(
                    spec, ts, bars, rv_cache, equity_now, cash, dte, delta,
                    iv_premium, spread_multiplier, risk_fraction,
                )
                if opened is None:
                    continue
                cash -= opened["debit_cash"]
                positions.append(opened)
                equity_now = cash + _mark(positions, ts, bars, iv_premium, field="open")
        still = []
        for pos in positions:
            exit_fill = _exit_decision(pos, ts, bars, iv_premium, spread_multiplier, premium_stop, path, max_hold)
            if exit_fill is None:
                still.append(pos)
                continue
            cash += exit_fill["credit"]
            closed.append(_trade_row(pos, ts, exit_fill))
        positions = still
        equity_now = cash + _mark(positions, ts, bars, iv_premium, field="close")
        if day_start > 0 and equity_now <= day_start * (1.0 - 0.02):
            for pos in positions:
                forced = _force_close(pos, ts, bars, iv_premium, spread_multiplier, "daily_loss_breaker")
                cash += forced["credit"]
                closed.append(_trade_row(pos, ts, forced))
            positions = []
            equity_now = cash
        peak = max(peak, equity_now)
        if peak > 0 and (1.0 - equity_now / peak) >= 0.15 - 1e-12:
            drawdown_halt = True
        at_risk = sum(pos["debit_cash"] for pos in positions)
        equity_values.append(equity_now)
        exposure_values.append(at_risk / equity_now if equity_now else 0.0)
        index.append(ts)

    if positions and index:
        ts = index[-1]
        for pos in positions:
            forced = _force_close(pos, ts, bars, iv_premium, spread_multiplier, "window_end")
            cash += forced["credit"]
            closed.append(_trade_row(pos, ts, forced))
        equity_values[-1] = cash
        exposure_values[-1] = 0.0

    frame = pd.DataFrame(closed)
    equity = pd.Series(equity_values, index=pd.DatetimeIndex(index), name="equity")
    exposure = pd.Series(exposure_values, index=equity.index, name="exposure")
    result = BacktestResult(
        equity=equity,
        exposure=exposure,
        trades=frame,
        ending_equity=float(equity.iloc[-1]) if len(equity) else starting_equity,
    )
    metrics = compute_metrics(result, starting_equity)
    metrics["avg_hold_sessions"] = float(frame["bars_held"].mean()) if len(frame) else 0.0
    metrics["target_hit_rate"] = float((frame["reason"] == "premium_target").mean()) if len(frame) else 0.0
    return {"metrics": metrics, "equity": result.daily_equity(), "trades": frame}


def entries_from_signals(
    signals: dict[str, pd.DataFrame],
    trade_start: pd.Timestamp,
    trade_end: pd.Timestamp,
) -> list[dict[str, Any]]:
    """Next-open fills. Long signals become calls and short signals become puts."""
    rows: list[dict[str, Any]] = []
    start = pd.Timestamp(trade_start)
    end = pd.Timestamp(trade_end)
    for symbol in sorted(signals):
        frame = signals[symbol]
        if frame is None or frame.empty:
            continue
        index = frame.index
        long_flag = frame["entry_next_open"].fillna(False).to_numpy(dtype=bool)
        short_flag = (
            frame["short_next_open"].fillna(False).to_numpy(dtype=bool)
            if "short_next_open" in frame.columns
            else np.zeros(len(frame), dtype=bool)
        )
        exit_flag = frame["exit_next_open"].fillna(False).to_numpy(dtype=bool) if "exit_next_open" in frame.columns else np.zeros(len(frame), dtype=bool)
        level = frame["inv_level"].to_numpy(dtype=float) if "inv_level" in frame.columns else np.full(len(frame), np.nan)
        slope = frame["inv_slope"].to_numpy(dtype=float) if "inv_slope" in frame.columns else np.zeros(len(frame))
        for i in range(len(frame) - 1):
            fill_time = pd.Timestamp(index[i + 1])
            if fill_time < start or fill_time > end:
                continue
            if long_flag[i]:
                rows.append(_entry(symbol, index, i, fill_time, "call", level, slope, exit_flag))
            elif short_flag[i]:
                rows.append(_entry(symbol, index, i, fill_time, "put", level, slope, exit_flag))
    rows.sort(key=lambda row: (row["fill_time"], row["symbol"], row["right"]))
    return rows


def _entry(symbol, index, i, fill_time, right, level, slope, exit_flag) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "signal_index": i,
        "fill_time": fill_time,
        "right": right,
        "inv_level": float(level[i]) if np.isfinite(level[i]) else np.nan,
        "inv_slope": float(slope[i]) if np.isfinite(slope[i]) else 0.0,
        "exit_flags": exit_flag,
        "index": index,
    }


def _empty(starting_equity: float) -> dict[str, Any]:
    result = BacktestResult(pd.Series(dtype=float), pd.Series(dtype=float), pd.DataFrame(), ending_equity=starting_equity)
    metrics = compute_metrics(result, starting_equity)
    metrics["avg_hold_sessions"] = 0.0
    metrics["target_hit_rate"] = 0.0
    return {"metrics": metrics, "equity": result.daily_equity(), "trades": pd.DataFrame()}


def _half(delta: float, multiplier: float) -> float:
    base = HALF_SPREAD_ATM if abs(delta) >= 0.50 else HALF_SPREAD_OTM
    return base * multiplier


def _ask(mid: float, delta: float, multiplier: float) -> float:
    return mid * (1.0 + _half(delta, multiplier))


def _bid(mid: float, delta: float, multiplier: float) -> float:
    return max(0.0, mid * (1.0 - _half(delta, multiplier)))


def _sigma(rv: pd.Series, ts: pd.Timestamp, iv_premium: float, fallback: float | None) -> float | None:
    if rv is None or rv.empty:
        return fallback
    value = rv.asof(ts)
    if value is None or pd.isna(value):
        return fallback
    scaled = float(value) * iv_premium
    if scaled != scaled:
        return fallback
    return min(VOL_CAP, max(VOL_FLOOR, scaled))


def _years(expiry: pd.Timestamp, ts: pd.Timestamp) -> float:
    days = (expiry.normalize() - pd.Timestamp(ts).normalize()).days
    return max(0.0, days / 365.0)


def _open_position(spec, ts, bars, rv_cache, equity, cash, dte, delta, iv_premium, spread_multiplier, risk_fraction):
    frame = bars.get(spec["symbol"])
    if frame is None or ts not in frame.index:
        return None
    spot = float(frame.loc[ts, "open"])
    if not np.isfinite(spot) or spot <= 0:
        return None
    rv = rv_cache.get(spec["symbol"])
    sigma = _sigma(rv, ts, iv_premium, None)
    if sigma is None:
        return None
    t_years = dte / 365.0
    if spec["right"] == "put":
        raw = strike_for_put_delta(spot, t_years, sigma, delta, RATE, DIVIDEND)
    else:
        raw = strike_for_delta(spot, t_years, sigma, delta, RATE, DIVIDEND)
    strike = listed_strike(spot, raw)
    mid = option_price(spec["right"], spot, strike, t_years, sigma, RATE, DIVIDEND)
    opt_delta = option_delta(spec["right"], spot, strike, t_years, sigma, RATE, DIVIDEND)
    if mid < MIN_MID:
        return None
    ask = _ask(mid, opt_delta, spread_multiplier)
    if ask <= 0.05:
        return None
    unit_fees = option_leg_fees(1, ask, sell=False)
    unit = ask * CONTRACT_MULTIPLIER + unit_fees
    budget = min(equity * risk_fraction, cash)
    contracts = int(budget // unit) if unit > 0 else 0
    if contracts < 1:
        return None
    fees = option_leg_fees(contracts, ask, sell=False)
    debit_cash = ask * CONTRACT_MULTIPLIER * contracts + fees
    if debit_cash > cash:
        return None
    locate = frame.index.get_loc(ts)
    fill_index = int(locate) if not isinstance(locate, slice) else int(locate.start)
    return {
        "symbol": spec["symbol"],
        "right": spec["right"],
        "entry_time": ts,
        "fill_index": fill_index,
        "expiry": pd.Timestamp(ts).normalize() + pd.Timedelta(days=dte),
        "strike": strike,
        "entry_ask": ask,
        "entry_delta": opt_delta,
        "sigma_entry": sigma,
        "contracts": contracts,
        "debit_cash": debit_cash,
        "entry_fees": fees,
        "inv_level": spec["inv_level"],
        "inv_slope": spec["inv_slope"],
        "signal_index": spec["signal_index"],
        "exit_flags": spec["exit_flags"],
        "index": spec["index"],
        "rv": rv,
        "bars_held": 0,
    }


def _bar(pos, ts, bars):
    frame = bars.get(pos["symbol"])
    if frame is None or ts not in frame.index:
        return None
    row = frame.loc[ts]
    return frame, row


def _quote(pos, spot, ts, iv_premium, spread_multiplier):
    sigma = _sigma(pos["rv"], ts, iv_premium, pos["sigma_entry"]) or pos["sigma_entry"]
    t_left = _years(pos["expiry"], ts)
    if t_left <= 0:
        if pos["right"] == "put":
            mid = max(0.0, pos["strike"] - spot)
            delta = -1.0 if spot < pos["strike"] else 0.0
        else:
            mid = max(0.0, spot - pos["strike"])
            delta = 1.0 if spot > pos["strike"] else 0.0
        return mid, delta, t_left
    mid = option_price(pos["right"], spot, pos["strike"], t_left, sigma, RATE, DIVIDEND)
    delta = option_delta(pos["right"], spot, pos["strike"], t_left, sigma, RATE, DIVIDEND)
    return mid, delta, t_left


def _credit(pos, bid, spread_multiplier) -> tuple[float, float]:
    contracts = pos["contracts"]
    fees = option_leg_fees(contracts, bid, sell=True)
    return bid * CONTRACT_MULTIPLIER * contracts - fees, fees


def _exit_decision(pos, ts, bars, iv_premium, spread_multiplier, premium_stop, path, max_hold):
    found = _bar(pos, ts, bars)
    if found is None:
        return None
    _frame, row = found
    locate = pos["index"].get_loc(ts) if ts in pos["index"] else None
    bar_i = int(locate) if isinstance(locate, (int, np.integer)) else pos["fill_index"]
    spots = {
        "open": float(row["open"]),
        "high": float(row["high"]),
        "low": float(row["low"]),
        "close": float(row["close"]),
    }
    if any(not np.isfinite(value) or value <= 0 for value in spots.values()):
        return None
    target_px = pos["entry_ask"] * (1.0 + PREMIUM_TARGET)
    stop_px = pos["entry_ask"] * (1.0 + premium_stop)
    if path == "close":
        favorable = adverse = spots["close"]
    elif pos["right"] == "put":
        favorable, adverse = spots["low"], spots["high"]
    else:
        favorable, adverse = spots["high"], spots["low"]
    adv_mid, adv_delta, _t_left = _quote(pos, adverse, ts, iv_premium, spread_multiplier)
    fav_mid, fav_delta, t_left = _quote(pos, favorable, ts, iv_premium, spread_multiplier)
    adv_bid = _bid(adv_mid, adv_delta, spread_multiplier)
    fav_bid = _bid(fav_mid, fav_delta, spread_multiplier)
    if adv_bid <= stop_px:
        credit, fees = _credit(pos, adv_bid, spread_multiplier)
        return {"price": adv_bid, "credit": credit, "fees": fees, "reason": "premium_stop"}
    if fav_bid >= target_px:
        credit, fees = _credit(pos, target_px, spread_multiplier)
        return {"price": target_px, "credit": credit, "fees": fees, "reason": "premium_target"}
    if t_left <= 0:
        credit, fees = _credit(pos, adv_bid, spread_multiplier)
        return {"price": adv_bid, "credit": credit, "fees": fees, "reason": "expiry"}
    close_mid, close_delta, _ = _quote(pos, spots["close"], ts, iv_premium, spread_multiplier)
    close_bid = _bid(close_mid, close_delta, spread_multiplier)
    invalidated = False
    line = pos["inv_level"] + pos["inv_slope"] * (bar_i - pos["signal_index"])
    if np.isfinite(line):
        if pos["right"] == "put" and spots["close"] > line:
            invalidated = True
        elif pos["right"] == "call" and spots["close"] < line:
            invalidated = True
    if bar_i > pos["fill_index"] and 0 <= bar_i < len(pos["exit_flags"]) and bool(pos["exit_flags"][bar_i]):
        invalidated = True
    if invalidated:
        credit, fees = _credit(pos, close_bid, spread_multiplier)
        return {"price": close_bid, "credit": credit, "fees": fees, "reason": "invalidation"}
    pos["bars_held"] = bar_i - pos["fill_index"] + 1
    if pos["bars_held"] >= max_hold:
        credit, fees = _credit(pos, close_bid, spread_multiplier)
        return {"price": close_bid, "credit": credit, "fees": fees, "reason": "time_stop"}
    return None


def _force_close(pos, ts, bars, iv_premium, spread_multiplier, reason):
    found = _bar(pos, ts, bars)
    spot = float(found[1]["close"]) if found is not None else pos.get("entry_spot", 1.0)
    if not np.isfinite(spot) or spot <= 0:
        spot = 1.0
    mid, delta, _ = _quote(pos, spot, ts, iv_premium, spread_multiplier)
    bid = _bid(mid, delta, spread_multiplier)
    credit, fees = _credit(pos, bid, spread_multiplier)
    return {"price": bid, "credit": credit, "fees": fees, "reason": reason}


def _mark(positions, ts, bars, iv_premium, field: str = "close") -> float:
    total = 0.0
    for pos in positions:
        found = _bar(pos, ts, bars)
        if found is None:
            continue
        spot = float(found[1][field])
        if not np.isfinite(spot) or spot <= 0:
            continue
        mid, _delta, _t = _quote(pos, spot, ts, iv_premium, 1.0)
        total += mid * CONTRACT_MULTIPLIER * pos["contracts"]
    return total


def _trade_row(pos, ts, exit_fill) -> dict[str, Any]:
    return {
        "symbol": pos["symbol"],
        "strategy": pos["right"],
        "quantity": pos["contracts"],
        "entry_time": pos["entry_time"],
        "entry_price": pos["entry_ask"],
        "exit_time": ts,
        "exit_price": exit_fill["price"],
        "pnl": exit_fill["credit"] - pos["debit_cash"],
        "fees": pos["entry_fees"] + exit_fill["fees"],
        "reason": exit_fill["reason"],
        "bars_held": max(int(pos.get("bars_held") or 1), 1),
    }
