"""Scale-out exit on frozen entries. Research only.

The entries are not refit. Open-versus-support uses Paul's headline. The
VWAP book is the 2 SD continuation on 15-minute bars, priced as 0 DTE.
Tendency has no mean-reverting cell, so this module does not build a
tendency trade. Nothing here places an order.
"""

from __future__ import annotations

import math
from datetime import date

import numpy as np
import pandas as pd

from webull_bot.calendar import next_trading_day
from webull_bot.chart_reads.detect import session_bands
from webull_bot.chart_reads.open_support import (
    CATALOG_BY_ID,
    HEADLINE_ID,
    _vix_on,
    _years_left,
    benjamini_hochberg,
    build_views,
    make_signal,
)
from webull_bot.chart_reads.vwap_band import find_signals, metrics_from
from webull_bot.mtf_vwap.detect import rth
from webull_bot.options.fees import CONTRACT_MULTIPLIER, option_leg_fees
from webull_bot.options.pricing import listed_strike, option_price

FLAT_MINUTE = 15 * 60 + 45
CONTRACTS = 3
RATE = 0.02
DIVIDEND = 0.0
EXITS = ("all_band", "r1", "pct50", "scale_prem10", "scale_be", "scale_full10")
SCALE_EXITS = ("scale_prem10", "scale_be", "scale_full10")
BAND_EXITS = ("all_band",) + SCALE_EXITS
STAKES = (1000.0, 2500.0, 5000.0)
PRIMARY_STAKE = 2500.0
RUNNER_PREMIUM_STOP = 0.90
RUNNER_PREMIUM_TARGET = 1.50
FULL_POSITION_STOP = 0.10


def frozen_rules() -> dict:
    """Written down before the result is scored. The score does not edit this."""
    return {
        "contracts": CONTRACTS,
        "primary_stake": PRIMARY_STAKE,
        "stakes": list(STAKES),
        "flat": "15:45 ET, at that bar's open. No overnight hold.",
        "band": (
            "The profit-side session VWAP 2 SD band known from the prior bar. "
            "The first bar of the session has no band. A zero-width band is ignored."
        ),
        "before_band": "The entry's underlying stop closes all contracts. If the stop and the band are both in one bar, the stop fills.",
        "scale": (
            "Sell 2 of 3 contracts when the underlying touches that band. "
            "If the fill open is already through the band, those 2 sell at the open. "
            "The runner is managed on later bars, and also on the same bar when the scale filled at the open."
        ),
        "runner_stops": {
            "scale_prem10": "Model mid at or below 90% of the entry mid.",
            "scale_be": "Model mid back at the entry mid.",
            "scale_full10": "Combined premium P&L at or below -10% of the 3-contract debit, fees included.",
        },
        "runner_target": "Model mid at or above 150% of the entry mid. A stop and a target in one bar fill the stop.",
        "comparisons": {
            "all_band": "Sell all 3 at the band.",
            "r1": "Sell all 3 at 1R, the fill-to-stop distance.",
            "pct50": "Sell all 3 when the mid is up 50%. The underlying stop still applies.",
        },
        "fill": "A level touched inside the bar fills at that premium. A gap through fills at the open.",
        "cash": "Skip the trade when the 3-contract ask does not fit in settled cash. One lot is not a substitute. Settlement is the next session.",
        "open_support_entry": HEADLINE_ID,
        "vwap_entry": "extension, 2 SD, 15-minute, both directions, one position at a time, 0 DTE.",
        "tendency": "No trade. A $2,500 start does not relax the mean-reversion bar, and the holdout is not opened.",
        "trials": "18 exit books on the $2,500 account. The $1,000 and $5,000 columns reuse the same legs and are not extra trials.",
        "promotion": "This comparison does not add a sandbox book.",
    }


def n_trials() -> int:
    """Open-support headline plus SPY and QQQ continuation, six exits each."""
    return 3 * len(EXITS)


def credit_of(qty: int, bid: float) -> float:
    if qty <= 0:
        return 0.0
    premium = max(float(bid), 0.0)
    return qty * premium * CONTRACT_MULTIPLIER - option_leg_fees(qty, premium, sell=True)


def debit_of(qty: int, ask: float) -> float:
    if qty <= 0:
        return 0.0
    premium = max(float(ask), 0.0)
    return qty * premium * CONTRACT_MULTIPLIER + option_leg_fees(qty, premium, sell=False)


def bid_for_credit(qty: int, target: float) -> float | None:
    """Smallest bid whose sale credit meets ``target``. None when a zero bid is already below it."""
    if qty <= 0:
        return None
    if target <= credit_of(qty, 0.0) + 1e-9:
        return None
    lo = 0.0
    hi = max(1.0, target / (qty * CONTRACT_MULTIPLIER) + 1.0)
    for _ in range(24):
        if credit_of(qty, hi) >= target:
            break
        hi *= 2.0
    for _ in range(48):
        mid = (lo + hi) / 2.0
        if credit_of(qty, mid) >= target:
            hi = mid
        else:
            lo = mid
    return hi


class ModelPricer:
    """Black-Scholes mid. The bid and the ask are a half-spread around it."""

    def __init__(self, right: str, strike: float, iv: float):
        self.right = right
        self.strike = float(strike)
        self.iv = min(1.50, max(0.05, float(iv)))

    def mid(self, spot: float, minute: int) -> float:
        if spot <= 0 or self.strike <= 0:
            return 0.0
        return float(option_price(self.right, float(spot), self.strike, _years_left(int(minute), 0), self.iv, RATE, DIVIDEND))

    def half(self, mid: float) -> float:
        return max(0.01, 0.015 * max(float(mid), 0.0))

    def bid(self, spot: float, minute: int) -> float:
        mid = self.mid(spot, minute)
        return max(0.0, mid - self.half(mid))

    def bid_for_mid(self, mid: float) -> float:
        return max(0.0, float(mid) - self.half(mid))


def _finite(value: float) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def _band_level(side: str, upper: float, lower: float) -> float:
    return float(upper) if side == "long" else float(lower)


def _beyond(side: str, spot: float, level: float, *, profit: bool) -> bool:
    if not _finite(spot) or not _finite(level):
        return False
    if side == "long":
        return spot >= level if profit else spot <= level
    return spot <= level if profit else spot >= level


def _adverse(side: str, bar_low: float, bar_high: float) -> float:
    return float(bar_low) if side == "long" else float(bar_high)


def _favorable(side: str, bar_low: float, bar_high: float) -> float:
    return float(bar_high) if side == "long" else float(bar_low)


def walk_legs(path: dict, exit_name: str, pricer, entry_mid: float, debit: float) -> list[dict]:
    """Contract legs for one position. The runner starts after the two-thirds sale."""
    if exit_name not in EXITS:
        raise ValueError(f"unknown exit {exit_name}")
    minutes = path["minute"]
    if len(minutes) == 0 or int(minutes[0]) >= FLAT_MINUTE:
        return []
    side = path["side"]
    fill = float(path["open"][0])
    stop = float(path["stop"])
    risk = abs(fill - stop)
    if risk <= 0 or not _finite(entry_mid) or entry_mid <= 0 or debit <= 0:
        return []
    r_target = fill + risk if side == "long" else fill - risk
    contracts = CONTRACTS
    credit_booked = 0.0
    scaled = False
    legs: list[dict] = []

    def sell(qty: int, bid: float, minute: int, reason: str, spot: float) -> None:
        nonlocal contracts, credit_booked
        qty = min(int(qty), contracts)
        if qty <= 0:
            return
        premium = max(float(bid), 0.0)
        credit_booked += credit_of(qty, premium)
        contracts -= qty
        legs.append({"qty": qty, "bid": premium, "minute": int(minute), "reason": reason, "spot": float(spot)})

    def premium_target_hit(spot: float, minute: int) -> bool:
        return pricer.mid(spot, minute) >= RUNNER_PREMIUM_TARGET * entry_mid - 1e-12

    def runner_at_open(index: int) -> bool:
        minute = int(minutes[index])
        opened = float(path["open"][index])
        stop_fill = _runner_decision(opened, minute, gapped=True)
        if stop_fill is not None:
            sell(1, stop_fill[1], minute, stop_fill[0], opened)
            return True
        if premium_target_hit(opened, minute):
            sell(1, pricer.bid(opened, minute), minute, "runner_pct50", opened)
            return True
        return False

    def _runner_decision(spot: float, minute: int, *, gapped: bool) -> tuple[str, float] | None:
        mid = pricer.mid(spot, minute)
        if exit_name == "scale_prem10" and mid <= RUNNER_PREMIUM_STOP * entry_mid + 1e-12:
            bid = pricer.bid(spot, minute) if gapped else pricer.bid_for_mid(RUNNER_PREMIUM_STOP * entry_mid)
            return "runner_prem10", bid
        if exit_name == "scale_be" and mid <= entry_mid + 1e-12:
            bid = pricer.bid(spot, minute) if gapped else pricer.bid_for_mid(entry_mid)
            return "runner_be", bid
        if exit_name == "scale_full10":
            target = (1.0 - FULL_POSITION_STOP) * debit - credit_booked
            this_credit = credit_of(1, pricer.bid(spot, minute))
            if this_credit <= target + 1e-6:
                if gapped:
                    return "runner_full10", pricer.bid(spot, minute)
                exact = bid_for_credit(1, target)
                if exact is None:
                    return "runner_full10", pricer.bid(spot, minute)
                return "runner_full10", exact
        return None

    def runner_in_range(index: int) -> bool:
        minute = int(minutes[index])
        low = float(path["low"][index])
        high = float(path["high"][index])
        adverse = _adverse(side, low, high)
        favorable = _favorable(side, low, high)
        stop_fill = _runner_decision(adverse, minute, gapped=False)
        if stop_fill is not None and premium_target_hit(favorable, minute):
            sell(1, stop_fill[1], minute, stop_fill[0], adverse)
            return True
        if stop_fill is not None:
            sell(1, stop_fill[1], minute, stop_fill[0], adverse)
            return True
        if premium_target_hit(favorable, minute):
            sell(1, pricer.bid_for_mid(RUNNER_PREMIUM_TARGET * entry_mid), minute, "runner_pct50", favorable)
            return True
        return False

    for index in range(len(minutes)):
        minute = int(minutes[index])
        opened = float(path["open"][index])
        high = float(path["high"][index])
        low = float(path["low"][index])
        if minute >= FLAT_MINUTE:
            sell(contracts, pricer.bid(opened, minute), minute, "flat", opened)
            break
        if not scaled:
            if _beyond(side, opened, stop, profit=False):
                sell(CONTRACTS, pricer.bid(opened, minute), minute, "stop", opened)
                break
            if _beyond(side, _adverse(side, low, high), stop, profit=False):
                sell(CONTRACTS, pricer.bid(stop, minute), minute, "stop", stop)
                break
            if exit_name == "r1":
                if _beyond(side, opened, r_target, profit=True):
                    sell(CONTRACTS, pricer.bid(opened, minute), minute, "r1", opened)
                    break
                if _beyond(side, _favorable(side, low, high), r_target, profit=True):
                    sell(CONTRACTS, pricer.bid(r_target, minute), minute, "r1", r_target)
                    break
            if exit_name == "pct50":
                if premium_target_hit(opened, minute):
                    sell(CONTRACTS, pricer.bid(opened, minute), minute, "pct50", opened)
                    break
                if premium_target_hit(_favorable(side, low, high), minute):
                    sell(CONTRACTS, pricer.bid_for_mid(RUNNER_PREMIUM_TARGET * entry_mid), minute, "pct50", _favorable(side, low, high))
                    break
            if exit_name in BAND_EXITS:
                level = _band_level(side, float(path["upper"][index]), float(path["lower"][index]))
                opened_through = _beyond(side, opened, level, profit=True)
                range_through = _beyond(side, _favorable(side, low, high), level, profit=True)
                if opened_through or range_through:
                    spot = opened if opened_through else level
                    bid = pricer.bid(spot, minute)
                    if exit_name == "all_band":
                        sell(CONTRACTS, bid, minute, "band", spot)
                        break
                    sell(2, bid, minute, "band", spot)
                    scaled = True
                    if opened_through:
                        if runner_at_open(index) or runner_in_range(index):
                            break
                    continue
        else:
            if runner_at_open(index) or runner_in_range(index):
                break
        if index == len(minutes) - 1 and contracts:
            sell(contracts, pricer.bid(float(path["close"][index]), minute), minute, "flat", float(path["close"][index]))
    if contracts:
        last = len(minutes) - 1
        last_minute = int(minutes[last])
        sell(contracts, pricer.bid(float(path["close"][last]), last_minute), last_minute, "flat", float(path["close"][last]))
    return legs


def prior_bands(frame: pd.DataFrame) -> pd.DataFrame:
    """2 SD band from the previous bar in the session. The first bar is blank."""
    bars = rth(frame)
    empty = pd.DataFrame(columns=["upper", "lower"])
    if bars.empty:
        return empty
    bands = session_bands(frame, deviations=2.0).reindex(bars.index)
    upper = np.full(len(bars), np.nan)
    lower = np.full(len(bars), np.nan)
    cursor = 0
    for _day, chunk in bars.groupby(bars.index.date):
        width = len(chunk)
        std = bands["std"].iloc[cursor : cursor + width].to_numpy(dtype=float)
        up = bands["upper"].iloc[cursor : cursor + width].to_numpy(dtype=float)
        lo = bands["lower"].iloc[cursor : cursor + width].to_numpy(dtype=float)
        for offset in range(1, width):
            if np.isfinite(std[offset - 1]) and std[offset - 1] > 0:
                upper[cursor + offset] = up[offset - 1]
                lower[cursor + offset] = lo[offset - 1]
        cursor += width
    return pd.DataFrame({"upper": upper, "lower": lower}, index=bars.index)


def _minutes(index: pd.DatetimeIndex) -> np.ndarray:
    return np.array([stamp.hour * 60 + stamp.minute for stamp in index], dtype=int)


def prepare_open_paths(
    symbol: str,
    five: pd.DataFrame,
    daily: pd.DataFrame | None = None,
    dollar_volume: pd.Series | None = None,
) -> list[dict]:
    """Headline entries. The original 1R target is not the exit."""
    cell = CATALOG_BY_ID[HEADLINE_ID]
    views = build_views(symbol, five, daily, dollar_volume)
    bands = prior_bands(five)
    lookup = {
        (stamp.date(), stamp.hour * 60 + stamp.minute): (float(row.upper), float(row.lower))
        for stamp, row in bands.iterrows()
    }
    paths = []
    for view in views:
        signal = make_signal(view, cell)
        if signal is None:
            continue
        uppers = []
        lowers = []
        for minute in view.bar_minutes:
            upper, lower = lookup.get((view.day, int(minute)), (float("nan"), float("nan")))
            uppers.append(upper)
            lowers.append(lower)
        paths.append(
            {
                "symbol": symbol,
                "day": view.day,
                "side": signal["side"],
                "fill": float(signal["fill"]),
                "stop": float(signal["stop"]),
                "priority": float(signal["priority"]),
                "minute": np.asarray(view.bar_minutes, dtype=int),
                "open": np.asarray(view.bars_open, dtype=float),
                "high": np.asarray(view.bars_high, dtype=float),
                "low": np.asarray(view.bars_low, dtype=float),
                "close": np.asarray(view.bars_close, dtype=float),
                "upper": np.asarray(uppers, dtype=float),
                "lower": np.asarray(lowers, dtype=float),
            }
        )
    return paths


def prepare_extension_paths(frame: pd.DataFrame, symbol: str) -> list[dict]:
    """2 SD continuation. The fill is the next 15-minute open."""
    signals = [item for item in find_signals(frame, symbol, 2.0) if item.mode == "extension"]
    bars = rth(frame)
    bands = prior_bands(frame).reindex(bars.index)
    by_day = {stamp: chunk for stamp, chunk in bars.groupby(bars.index.date)}
    paths = []
    for signal in signals:
        clock = pd.Timestamp(signal.fill_time)
        if clock.tzinfo is not None:
            clock = clock.tz_convert("America/New_York")
        day = clock.date()
        session = by_day.get(day)
        if session is None or signal.fill_time not in session.index:
            continue
        loc = session.index.get_loc(signal.fill_time)
        if isinstance(loc, slice) or not isinstance(loc, int):
            continue
        path = session.iloc[loc:]
        band = bands.reindex(path.index)
        paths.append(
            {
                "symbol": symbol,
                "day": day,
                "side": signal.direction,
                "fill": float(path["open"].iloc[0]),
                "stop": float(signal.stop),
                "priority": 0.0,
                "minute": _minutes(path.index),
                "open": path["open"].to_numpy(dtype=float),
                "high": path["high"].to_numpy(dtype=float),
                "low": path["low"].to_numpy(dtype=float),
                "close": path["close"].to_numpy(dtype=float),
                "upper": band["upper"].to_numpy(dtype=float),
                "lower": band["lower"].to_numpy(dtype=float),
            }
        )
    return paths


def attach_prices(paths: list[dict], iv_points: dict[date, float]) -> list[dict]:
    """Price every exit once. The debit does not depend on the account size."""
    priced = []
    for path in paths:
        sigma_points = _vix_on(iv_points, path["day"])
        if sigma_points is None:
            continue
        iv = min(1.50, max(0.05, sigma_points / 100.0))
        right = "call" if path["side"] == "long" else "put"
        strike = listed_strike(float(path["fill"]), float(path["fill"]))
        pricer = ModelPricer(right, strike, iv)
        entry_minute = int(path["minute"][0])
        entry_mid = pricer.mid(float(path["fill"]), entry_minute)
        if not _finite(entry_mid) or entry_mid <= 0:
            continue
        ask = entry_mid + pricer.half(entry_mid)
        debit = debit_of(CONTRACTS, ask)
        legs = {name: walk_legs(path, name, pricer, entry_mid, debit) for name in EXITS}
        if any(len(item) == 0 for item in legs.values()):
            continue
        stored = {key: value for key, value in path.items() if key not in {"minute", "open", "high", "low", "close", "upper", "lower"}}
        stored.update(
            {
                "ask": ask,
                "debit": debit,
                "debit_one": debit_of(1, ask),
                "entry_mid": entry_mid,
                "entry_minute": entry_minute,
                "legs": legs,
            }
        )
        priced.append(stored)
    return priced


def _pnl_p(returns: list[float]) -> float:
    values = np.asarray(returns, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) < 5:
        return 1.0
    std = float(values.std(ddof=1))
    if std <= 0:
        return 1.0
    stat = float(values.mean() / (std / math.sqrt(len(values))))
    return float(0.5 * math.erfc(stat / math.sqrt(2.0)))


def simulate_account(
    paths: list[dict],
    exit_name: str,
    start: date,
    end: date,
    starting: float,
    session_days: list[date],
    *,
    cap: int | None = None,
    one_position: bool = False,
) -> dict:
    """Fresh cash account. ``cap`` limits new entries per day. ``one_position`` blocks an overlap."""
    chosen = [path for path in paths if start <= path["day"] <= end and path["legs"].get(exit_name)]
    days = [day for day in session_days if start <= day <= end]
    by_day: dict[date, list[dict]] = {}
    for path in chosen:
        by_day.setdefault(path["day"], []).append(path)
    settled = float(starting)
    pending: list[tuple[date, float]] = []
    equity_values = []
    trades = []
    skips = {"premium": 0, "cap": 0, "overlap": 0}
    busy: tuple[date, int] | None = None

    def equity() -> float:
        return settled + sum(amount for _when, amount in pending)

    for session in days:
        still = []
        for when, amount in pending:
            if when <= session:
                settled += amount
            else:
                still.append((when, amount))
        pending = still
        if settled < 0:
            settled = 0.0
        ranked = by_day.get(session, [])
        if one_position:
            ranked = sorted(ranked, key=lambda row: int(row["entry_minute"]))
        else:
            ranked = sorted(ranked, key=lambda row: (-float(row.get("priority") or 0.0), row["symbol"]))
        taken = 0
        for path in ranked:
            if cap is not None and taken >= cap:
                skips["cap"] += 1
                continue
            entry_minute = int(path["entry_minute"])
            if one_position and busy is not None and (busy[0] > session or (busy[0] == session and busy[1] >= entry_minute)):
                skips["overlap"] += 1
                continue
            debit = float(path["debit"])
            if debit > settled + 1e-9:
                skips["premium"] += 1
                continue
            legs = path["legs"][exit_name]
            credit = sum(credit_of(int(leg["qty"]), float(leg["bid"])) for leg in legs)
            pnl = credit - debit
            settled -= debit
            pending.append((next_trading_day(session), debit + pnl))
            taken += 1
            last = legs[-1]
            busy = (session, int(last["minute"]))
            trades.append(
                {
                    "symbol": path["symbol"],
                    "day": session,
                    "side": path["side"],
                    "debit": debit,
                    "pnl": pnl,
                    "entry_minute": entry_minute,
                    "exit_minute": int(last["minute"]),
                    "reasons": [leg["reason"] for leg in legs],
                    "scaled_at_fill": bool(legs[0]["reason"] == "band" and int(legs[0]["minute"]) == entry_minute),
                }
            )
        equity_values.append(equity())
    index = pd.to_datetime(days) if days else pd.DatetimeIndex([])
    series = pd.Series(equity_values, index=index, dtype=float) if days else pd.Series(dtype=float)
    metrics = metrics_from(series, [float(row["pnl"]) for row in trades], float(starting))
    sessions = max(len(days), 1)
    metrics["trades_per_day"] = len(trades) / sessions
    metrics["sessions"] = len(days)
    scaled = sum(1 for row in trades if row["scaled_at_fill"])
    metrics["scaled_at_fill"] = scaled
    metrics["scaled_at_fill_rate"] = (scaled / len(trades)) if trades else 0.0
    return {
        "metrics": metrics,
        "skips": skips,
        "trades": trades,
        "equity": series,
        "p": _pnl_p([row["pnl"] / row["debit"] for row in trades if row["debit"] > 0]),
    }


def feasibility(paths: list[dict], start: date, end: date) -> dict:
    """How often the ask fits, before cash from earlier trades is spent."""
    window = [path for path in paths if start <= path["day"] <= end]
    out = {"signals": len(window)}
    if not window:
        for stake in STAKES:
            out[f"fit_3_{int(stake)}"] = 0
            out[f"fit_1_{int(stake)}"] = 0
        out["median_debit_3"] = None
        return out
    debits = np.array([float(path["debit"]) for path in window], dtype=float)
    ones = np.array([float(path["debit_one"]) for path in window], dtype=float)
    out["median_debit_3"] = float(np.median(debits))
    out["median_debit_1"] = float(np.median(ones))
    for stake in STAKES:
        out[f"fit_3_{int(stake)}"] = int(np.sum(debits <= stake + 1e-9))
        out[f"fit_1_{int(stake)}"] = int(np.sum(ones <= stake + 1e-9))
    return out


def assign_q(rows: list[dict]) -> None:
    """Benjamini-Hochberg on the training p-values. In place."""
    if not rows:
        return
    adjusted = benjamini_hochberg([float(row["p"]) for row in rows])
    for row, q_value in zip(rows, adjusted):
        row["q"] = float(q_value)


def tendency_eligible(cells: list[dict]) -> list[dict]:
    """The exit attaches only to a mean-reverting cell. Anything else is dropped."""
    return [row for row in cells if row.get("label") == "mean-reverting"]


def three_lot_fit(trades: list[dict], iv_points: dict[date, float], dte: int = 0) -> dict:
    """How many of these fills can pay for 3 ATM contracts. This does not place that trade."""
    counted = {"signals": 0}
    for stake in STAKES:
        counted[f"fit_3_{int(stake)}"] = 0
        counted[f"fit_1_{int(stake)}"] = 0
    debits = []
    for trade in trades:
        sigma_points = _vix_on(iv_points, trade["day"])
        if sigma_points is None:
            continue
        iv = min(1.50, max(0.05, float(sigma_points) / 100.0))
        right = "call" if trade["side"] == "long" else "put"
        fill = float(trade["fill"])
        strike = listed_strike(fill, fill)
        minute = int(trade.get("entry_minute") or (9 * 60 + 35))
        mid = float(option_price(right, fill, strike, _years_left(minute, dte), iv, RATE, DIVIDEND))
        if not _finite(mid) or mid <= 0:
            continue
        half = max(0.01, 0.015 * mid)
        ask = mid + half
        debits.append(debit_of(CONTRACTS, ask))
        one = debit_of(1, ask)
        counted["signals"] += 1
        for stake in STAKES:
            if debits[-1] <= stake + 1e-9:
                counted[f"fit_3_{int(stake)}"] += 1
            if one <= stake + 1e-9:
                counted[f"fit_1_{int(stake)}"] += 1
    counted["median_debit_3"] = float(np.median(debits)) if debits else None
    return counted
