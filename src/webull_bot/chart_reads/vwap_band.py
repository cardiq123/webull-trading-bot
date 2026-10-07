"""Session VWAP bands on 15-minute SPY and QQQ.

The rules in ``frozen_rules`` are the ones that get scored. Nothing here
places an order or imports the sandbox forward test.

A bar uses only prices that have closed. The fill is the next bar's open.
The 15:45 bar is an exit, not an entry. A bar that can reach both the stop
and the target fills the stop.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time
from typing import Optional

import numpy as np
import pandas as pd

from webull_bot.calendar import next_trading_day
from webull_bot.chart_reads.band_exit import walk_band
from webull_bot.chart_reads.detect import session_bands
from webull_bot.costs import CostModel, buy_fees, buy_price, sell_price, sell_regulatory_fees
from webull_bot.indicators import ema
from webull_bot.mtf_vwap.detect import rth, session_vwap
from webull_bot.options.fees import CONTRACT_MULTIPLIER, option_leg_fees
from webull_bot.options.pricing import listed_strike, option_price

NY = "America/New_York"
FLAT = time(15, 45)
LAST_SIGNAL = time(15, 15)
OUTER_DEFAULT = 2.0
OUTER_VARIANTS = (2.5, 3.0)
STOP_PAD = 0.01
RISK_FRACTION = 0.01
RATE = 0.02
DIVIDEND = 0.0
HALF_SPREAD_PCT = 0.015
HALF_SPREAD_FLOOR = 0.01
VOL_FLOOR = 0.05
VOL_CAP = 1.50
HOLDOUT_START = date(2022, 1, 1)
TRAIN_END = date(2021, 12, 31)
SAMPLE_END = date(2026, 10, 6)
RANDOM_SEED = 17
GATE_PF = 1.10
GATE_SHARPE = 0.40
GATE_DRAWDOWN = -0.30
GATE_TRADES = 300


def frozen_rules() -> dict:
    """Written down before the result is scored. The score does not edit this."""
    return {
        "clock": "15-minute regular-hours bars, 09:30 through 15:45 ET. The 09:30 bar is 09:30-09:44.",
        "vwap": "Session VWAP of typical price, volume-weighted, reset at 09:30. Dukascopy volume is a bid-tick count.",
        "outer_default": OUTER_DEFAULT,
        "outer_variants": list(OUTER_VARIANTS),
        "outer_note": "The gate reads 2 standard deviations. 2.5 and 3 are pre-registered variants and cannot take the gate.",
        "extension": (
            "A 15-minute close strictly beyond the outer band, after a close inside it, trades that way. "
            "Close above the upper band is a long. Close below the lower band is a short. "
            "The fill is the next bar's open. The stop is one cent beyond that signal bar's adverse extreme. "
            "The target is 1R, the distance from the fill to the stop. VWAP is behind this entry, so it is not a target."
        ),
        "reversal": (
            "A bar pierces an outer band, or closes beyond it. The confirmation is the first later close back "
            "inside both outer bands, and a wick that pierces and closes inside confirms on that same bar. "
            "A bar through both bands is skipped. The fill is the next bar's open, toward VWAP. "
            "A lower-band bounce is a long. An upper-band bounce is a short. "
            "The stop is one cent beyond the extreme of the excursion, from the pierce through the confirmation."
        ),
        "reversal_targets": "The gate reads VWAP at the confirmation close. The 1 SD band on that side, and 1R, are variants.",
        "band": (
            "Take the whole position at the opposite 2 SD session VWAP band, the upper band for a long and the lower band for a short, "
            "when that band is beyond the fill. The band updates with the session. The stop fills first. "
            "A close back across the 15-minute 9 EMA exits at that close. This cannot take the gate."
        ),
        "band200": (
            "Half at the first of the opposite 2 SD band and the 15-minute 200 EMA, when each is beyond the fill. "
            "The rest exits at the other or on a close back across the 9 EMA. The stop is not moved to the fill. "
            "One option contract sells at the first tag. This cannot take the gate."
        ),
        "prem50": "0 DTE and 7 DTE. Exit when the model bid is 50% above the entry ask. A gap fills at the open bid. This cannot take the gate.",
        "prem100": "0 DTE and 7 DTE. Exit when the model bid is 100% above the entry ask. A gap fills at the open bid. This cannot take the gate.",
        "targets_fixed": "Band targets are the confirmation bar's VWAP and 1 SD value. They do not chase later bars.",
        "flat": "Still open at 15:45 ET is sold at that bar's open. No overnight hold. The last signal bar is 15:15.",
        "same_bar": "If one bar can hit the stop and the target, the stop fills. A gap through either fills at the open.",
        "one_position": "One open trade. A new signal while it is open is skipped.",
        "shares": (
            "The cash book is long only, because a $1,000 cash account cannot short. "
            "Size risks 1% of equity to the stop and never spends more settled cash than is on hand. "
            "Fractional shares. A sale settles the next session. "
            "A both-directions share book is a research baseline and is not the gate."
        ),
        "options": (
            "One at-the-money contract, listed strike nearest the fill. Calls for longs, puts for shorts. "
            "0 DTE expires 16:00 the same day. 7 DTE is seven calendar days, not the listed Friday. "
            "Both are closed by 15:45 the entry day. Skip the trade when the debit does not fit in settled cash."
        ),
        "iv": "Prior session VIX1D close when that print exists, otherwise the prior VIX close, divided by 100. Clipped to 5%-150%.",
        "spread": "Option half-spread is the greater of $0.01 and 1.5% of the model mid. Buy the ask, sell the bid, plus Webull option fees.",
        "model": "Black-Scholes, rate 2%, dividend yield 0. No listed chain. The model is the uncertainty. QQQ uses the same VIX print.",
        "costs": "Shares use the repo CostModel: 5 bps slippage, 1 bp half-spread, and the 2026 SEC and FINRA sell fees on the whole sample.",
        "account": "Fresh $1,000 and $5,000. Cash earns zero. Taxes are ignored.",
        "split": "Train is every session through 2021-12-31. Holdout is a fresh account from 2022-01-01 through 2026-10-06.",
        "random": "Seed 17 only. The same number of entries, random eligible bars, the same stop style and a 1R target.",
        "gate": "Holdout profit factor at least 1.10, Sharpe at least 0.40, max drawdown no worse than -30%, and at least 300 trades.",
        "gate_books": [
            "extension 2 SD shares cash long-only target 1R",
            "reversal 2 SD shares cash long-only target VWAP",
            "extension 2 SD 0 DTE target 1R",
            "reversal 2 SD 0 DTE target VWAP",
            "extension 2 SD 7 DTE target 1R",
            "reversal 2 SD 7 DTE target VWAP",
        ],
    }


@dataclass(frozen=True)
class Signal:
    symbol: str
    mode: str
    direction: str
    signal_time: pd.Timestamp
    fill_time: pd.Timestamp
    stop: float
    vwap: float
    inner: float
    outer: float


def _inner(direction: str, vwap: float, std: float) -> float:
    if direction == "long":
        return vwap - std
    return vwap + std


def find_signals(frame: pd.DataFrame, symbol: str, outer: float = OUTER_DEFAULT) -> list[Signal]:
    """Extension and reversal signals. ``outer`` is the band width in standard deviations."""
    if outer <= 0:
        raise ValueError("outer must be positive")
    bars = rth(frame)
    if bars.empty:
        return []
    bands = session_bands(frame, deviations=1.0).reindex(bars.index)
    found: list[Signal] = []
    for _day, session in bars.groupby(bars.index.date):
        band = bands.reindex(session.index)
        prev_inside = True
        exc: Optional[dict] = None
        n = len(session)
        for i in range(n):
            row = session.iloc[i]
            width = band.iloc[i]
            std = float(width["std"]) if pd.notna(width["std"]) else float("nan")
            vwap = float(width["vwap"]) if pd.notna(width["vwap"]) else float("nan")
            if not np.isfinite(std) or std <= 0.0 or not np.isfinite(vwap):
                prev_inside = True
                exc = None
                continue
            upper = vwap + outer * std
            lower = vwap - outer * std
            high = float(row["high"])
            low = float(row["low"])
            close = float(row["close"])
            stamp = session.index[i]
            nxt = session.index[i + 1] if i + 1 < n else None
            can_fill = (
                nxt is not None
                and stamp.time() <= LAST_SIGNAL
                and nxt.time() < FLAT
                and nxt.date() == stamp.date()
            )
            outside_up = close > upper
            outside_dn = close < lower
            if prev_inside and can_fill and (outside_up ^ outside_dn):
                direction = "long" if outside_up else "short"
                stop = (low - STOP_PAD) if direction == "long" else (high + STOP_PAD)
                found.append(
                    Signal(
                        symbol, "extension", direction, stamp, nxt, stop, vwap,
                        _inner(direction, vwap, std), outer,
                    )
                )
            prev_inside = not (outside_up or outside_dn)

            pierce_up = high > upper
            pierce_dn = low < lower
            inside = lower <= close <= upper
            if pierce_up and pierce_dn:
                exc = None
                continue
            if exc is None:
                if pierce_up:
                    exc = {"side": "up", "extreme": high}
                elif pierce_dn:
                    exc = {"side": "down", "extreme": low}
                if exc is not None and inside and can_fill:
                    found.append(_reversal(symbol, session, i, exc, vwap, std, outer))
                    exc = None
                continue
            if exc["side"] == "up":
                exc["extreme"] = max(float(exc["extreme"]), high)
                if close < lower:
                    exc = {"side": "down", "extreme": low}
                    continue
                if inside and can_fill:
                    found.append(_reversal(symbol, session, i, exc, vwap, std, outer))
                    exc = None
            else:
                exc["extreme"] = min(float(exc["extreme"]), low)
                if close > upper:
                    exc = {"side": "up", "extreme": high}
                    continue
                if inside and can_fill:
                    found.append(_reversal(symbol, session, i, exc, vwap, std, outer))
                    exc = None
    return found


def _reversal(symbol: str, session: pd.DataFrame, i: int, exc: dict, vwap: float, std: float, outer: float) -> Signal:
    direction = "short" if exc["side"] == "up" else "long"
    extreme = float(exc["extreme"])
    stop = extreme + STOP_PAD if direction == "short" else extreme - STOP_PAD
    return Signal(
        symbol, "reversal", direction, session.index[i], session.index[i + 1],
        stop, vwap, _inner(direction, vwap, std), outer,
    )


def target_price(signal: Signal, fill: float, kind: str) -> float:
    if kind == "vwap":
        return float(signal.vwap)
    if kind == "inner":
        return float(signal.inner)
    if kind == "r":
        risk = abs(fill - float(signal.stop))
        if signal.direction == "long":
            return fill + risk
        return fill - risk
    raise ValueError(f"unknown target {kind}")


def walk_exit(
    session: pd.DataFrame,
    fill_loc: int,
    direction: str,
    stop: float,
    target: float,
) -> tuple[str, float, pd.Timestamp]:
    """Stop wins when both levels trade in one bar. 15:45 exits at the open."""
    last_reason = "last_bar"
    last_price = float(session.iloc[-1]["close"])
    last_time = session.index[-1]
    for j in range(fill_loc, len(session)):
        row = session.iloc[j]
        stamp = session.index[j]
        opened = float(row["open"])
        high = float(row["high"])
        low = float(row["low"])
        if stamp.time() >= FLAT:
            return "flat", opened, stamp
        if direction == "long":
            through_stop = opened <= stop
            through_target = opened >= target
            hit_stop = low <= stop
            hit_target = high >= target
        else:
            through_stop = opened >= stop
            through_target = opened <= target
            hit_stop = high >= stop
            hit_target = low <= target
        if through_stop and through_target:
            return "stop", opened, stamp
        if through_stop:
            return "stop", opened, stamp
        if through_target:
            return "target", opened, stamp
        if hit_stop and hit_target:
            return "stop", stop, stamp
        if hit_stop:
            return "stop", stop, stamp
        if hit_target:
            return "target", target, stamp
        last_price = float(row["close"])
        last_time = stamp
    return last_reason, last_price, last_time


def _years(when: pd.Timestamp, dte: int) -> float:
    clock = pd.Timestamp(when)
    if clock.tzinfo is not None:
        clock = clock.tz_convert(NY)
    expiry = clock.normalize() + pd.Timedelta(days=int(dte), hours=16)
    minutes = max(1.0, (expiry - clock).total_seconds() / 60.0)
    return minutes / (365.0 * 24.0 * 60.0)


def _half_spread(mid: float) -> float:
    return max(HALF_SPREAD_FLOOR, HALF_SPREAD_PCT * max(mid, 0.0))


def _option_mid(right: str, spot: float, strike: float, when: pd.Timestamp, iv: float, dte: int) -> float:
    if spot <= 0 or strike <= 0 or iv <= 0:
        return 0.0
    return float(option_price(right, spot, strike, _years(when, dte), iv, RATE, DIVIDEND))


def _iv_on(day: date, iv_points: dict[date, tuple[float, str]]) -> Optional[float]:
    point = iv_points.get(day)
    if point is None:
        return None
    raw = float(point[0])
    if not np.isfinite(raw) or raw <= 0:
        return None
    return min(VOL_CAP, max(VOL_FLOOR, raw / 100.0))


def _day_key(stamp: pd.Timestamp) -> date:
    clock = pd.Timestamp(stamp)
    if clock.tzinfo is not None:
        clock = clock.tz_convert(NY)
    return clock.date()


def simulate(
    frame: pd.DataFrame,
    signals: list[Signal],
    *,
    target: str,
    kind: str,
    stake: float,
    long_only: bool,
    iv_points: dict[date, tuple[float, str]] | None = None,
    start: date | None = None,
    end: date | None = None,
    costs: CostModel | None = None,
) -> dict:
    """Fresh account. ``kind`` is ``shares``, ``0dte``, or ``7dte``."""
    if kind not in ("shares", "0dte", "7dte"):
        raise ValueError("kind must be shares, 0dte, or 7dte")
    if target not in ("vwap", "inner", "r", "band", "band200", "prem50", "prem100"):
        raise ValueError("target must be vwap, inner, r, band, band200, prem50, or prem100")
    if target in ("prem50", "prem100") and kind == "shares":
        raise ValueError("premium targets are option exits")
    model = costs or CostModel()
    points = iv_points or {}
    dte = 0 if kind == "0dte" else 7
    bars = rth(frame)
    managed = target in ("band", "band200", "prem50", "prem100")
    if managed and not bars.empty:
        close = bars["close"].astype(float)
        ema9_all = ema(close, 9)
        ema200_all = ema(close, 200)
        width = session_vwap(bars).reindex(bars.index)
        vwap_all = width["vwap"]
        std_all = width["upper"] - width["vwap"]
    else:
        ema9_all = ema200_all = vwap_all = std_all = None
    if start is not None or end is not None:
        keep = []
        for stamp in bars.index:
            day = _day_key(stamp)
            if start is not None and day < start:
                continue
            if end is not None and day > end:
                continue
            keep.append(stamp)
        bars = bars.loc[keep] if keep else bars.iloc[0:0]
    by_day: dict[date, pd.DataFrame] = {}
    for key, chunk in bars.groupby(bars.index.date):
        by_day[key if isinstance(key, date) else pd.Timestamp(key).date()] = chunk
    chosen = []
    for signal in signals:
        day = _day_key(signal.fill_time)
        if start is not None and day < start:
            continue
        if end is not None and day > end:
            continue
        if long_only and signal.direction != "long":
            continue
        chosen.append(signal)
    chosen.sort(key=lambda item: item.fill_time)

    settled = float(stake)
    unsettled: list[tuple[date, float]] = []
    equity = float(stake)
    curve: list[tuple[pd.Timestamp, float]] = []
    trades: list[dict] = []
    skips = {"short": 0, "overlap": 0, "no_bar": 0, "iv": 0, "premium": 0, "dust": 0, "bust": 0}
    if long_only:
        skips["short"] = sum(1 for signal in signals if _in_window(signal, start, end) and signal.direction != "long")
    busy: Optional[pd.Timestamp] = None
    cursor = 0
    stopped = False

    for day in sorted(by_day):
        if not stopped:
            still = []
            for available_on, amount in unsettled:
                if available_on <= day:
                    settled += amount
                else:
                    still.append((available_on, amount))
            unsettled = still
            equity = settled + sum(amount for _when, amount in unsettled)
        session = by_day[day]
        while cursor < len(chosen) and _day_key(chosen[cursor].fill_time) == day:
            signal = chosen[cursor]
            cursor += 1
            if stopped or equity <= 1.0:
                skips["bust"] += 1
                continue
            if busy is not None and signal.fill_time <= busy:
                skips["overlap"] += 1
                continue
            if signal.fill_time not in session.index:
                skips["no_bar"] += 1
                continue
            loc = session.index.get_loc(signal.fill_time)
            if isinstance(loc, slice) or not isinstance(loc, int):
                skips["no_bar"] += 1
                continue
            fill = float(session.iloc[loc]["open"])
            if fill <= 0 or not np.isfinite(signal.stop):
                skips["no_bar"] += 1
                continue
            distance = abs(fill - float(signal.stop))
            if distance <= 0:
                skips["dust"] += 1
                continue
            scale_raw = None
            premium = None
            if managed:
                iv = _iv_on(day, points) if kind != "shares" else None
                if kind != "shares" and iv is None:
                    skips["iv"] += 1
                    continue
                aligned = session.index
                entry_ask = None
                strike = None
                if target.startswith("prem"):
                    strike = listed_strike(fill, fill)
                    right = "call" if signal.direction == "long" else "put"
                    entry_mid = _option_mid(right, fill, strike, signal.fill_time, iv, dte)
                    entry_ask = entry_mid + _half_spread(entry_mid)
                path = walk_band(
                    direction=signal.direction,
                    fill=fill,
                    stop=float(signal.stop),
                    fill_i=loc,
                    open_=session["open"].to_numpy(dtype=float),
                    high=session["high"].to_numpy(dtype=float),
                    low=session["low"].to_numpy(dtype=float),
                    close=session["close"].to_numpy(dtype=float),
                    stamps=aligned,
                    ema9=ema9_all.reindex(aligned).to_numpy(dtype=float),
                    ema200=ema200_all.reindex(aligned).to_numpy(dtype=float),
                    vwap=vwap_all.reindex(aligned).to_numpy(dtype=float),
                    std=std_all.reindex(aligned).to_numpy(dtype=float),
                    flat=FLAT,
                    mode=target,
                    split_half=kind == "shares" and target == "band200",
                    session_end=len(session),
                    iv=iv,
                    strike=strike,
                    entry_ask=entry_ask,
                    dte=dte,
                )
                if path is None:
                    skips["dust"] += 1
                    continue
                reason = path["reason"]
                exit_raw = float(path["exit_spot"])
                exit_time = path["exit_time"]
                level = exit_raw
                scale_raw = path["scale_spot"] if path["scaled"] else None
                premium = path["premium"]
            else:
                level = target_price(signal, fill, target)
                reason, exit_raw, exit_time = walk_exit(session, loc, signal.direction, float(signal.stop), level)
            if kind == "shares":
                trade = _share_trade(
                    signal, fill, exit_raw, exit_time, reason, level, distance,
                    settled, equity, model, stake_cash=True, scale_raw=scale_raw,
                )
            else:
                iv = _iv_on(day, points)
                if iv is None:
                    skips["iv"] += 1
                    continue
                trade = _option_trade(
                    signal, fill, exit_raw, exit_time, reason, level, iv, dte, settled, premium=premium,
                )
            if trade is None:
                skips["premium" if kind != "shares" else "dust"] += 1
                continue
            if trade["debit"] > settled + 1e-9:
                skips["premium" if kind != "shares" else "dust"] += 1
                continue
            settled -= trade["debit"]
            pay = trade["credit"]
            unsettled.append((next_trading_day(day), pay))
            equity = settled + sum(amount for _when, amount in unsettled)
            trade["equity"] = equity
            trades.append(trade)
            busy = exit_time
            if equity <= 1.0:
                stopped = True
        mark = pd.Timestamp(day.isoformat())
        curve.append((mark, equity if not stopped or trades else equity))

    equity_series = pd.Series(
        [value for _stamp, value in curve],
        index=pd.DatetimeIndex([stamp for stamp, _value in curve]),
        dtype=float,
    )
    pnls = [float(trade["pnl"]) for trade in trades]
    stats = metrics_from(equity_series, pnls, float(stake))
    under_one = sum(1 for trade in trades if trade.get("quantity", 1) < 1.0 - 1e-9)
    return {
        "equity": equity_series,
        "trades": trades,
        "skips": skips,
        "metrics": stats,
        "under_one_share": under_one,
    }


def _in_window(signal: Signal, start: date | None, end: date | None) -> bool:
    day = _day_key(signal.fill_time)
    if start is not None and day < start:
        return False
    if end is not None and day > end:
        return False
    return True


def _long_credit(quantity: float, exit_raw: float, scale_raw: float | None, costs: CostModel) -> float:
    legs = [(1.0, exit_raw)] if scale_raw is None else [(0.5, float(scale_raw)), (0.5, exit_raw)]
    credit = 0.0
    for fraction, raw in legs:
        px = sell_price(raw, costs)
        qty = quantity * fraction
        credit += qty * px - sell_regulatory_fees(px, qty, costs)
    return credit


def _share_trade(
    signal: Signal,
    fill: float,
    exit_raw: float,
    exit_time: pd.Timestamp,
    reason: str,
    level: float,
    distance: float,
    settled: float,
    equity: float,
    costs: CostModel,
    stake_cash: bool,
    scale_raw: float | None = None,
) -> dict | None:
    del stake_cash
    risk_dollars = RISK_FRACTION * equity
    if signal.direction == "long":
        entry_px = buy_price(fill, costs)
        room = settled / entry_px if entry_px > 0 else 0.0
        quantity = min(room, risk_dollars / distance)
        if quantity <= 1e-8:
            return None
        debit = quantity * entry_px + buy_fees(costs)
        credit = _long_credit(quantity, exit_raw, scale_raw, costs)
    else:
        entry_px = sell_price(fill, costs)
        exit_px = buy_price(exit_raw, costs)
        room = settled / fill if fill > 0 else 0.0
        quantity = min(room, risk_dollars / distance)
        if quantity <= 1e-8:
            return None
        # The research short locks the cover cost, not a cash-secured short.
        debit = quantity * exit_px
        credit = quantity * entry_px - sell_regulatory_fees(entry_px, quantity, costs)
        if debit > settled:
            quantity = settled / exit_px if exit_px > 0 else 0.0
            if quantity <= 1e-8:
                return None
            debit = quantity * exit_px
            credit = quantity * entry_px - sell_regulatory_fees(entry_px, quantity, costs)
    pnl = credit - debit
    return _row(signal, fill, exit_raw, exit_time, reason, level, quantity, debit, credit, pnl, None)


def _option_trade(
    signal: Signal,
    fill: float,
    exit_raw: float,
    exit_time: pd.Timestamp,
    reason: str,
    level: float,
    iv: float,
    dte: int,
    settled: float,
    premium: float | None = None,
) -> dict | None:
    right = "call" if signal.direction == "long" else "put"
    strike = listed_strike(fill, fill)
    entry_mid = _option_mid(right, fill, strike, signal.fill_time, iv, dte)
    entry_ask = entry_mid + _half_spread(entry_mid)
    if premium is not None:
        exit_bid = float(premium)
    else:
        exit_mid = _option_mid(right, exit_raw, strike, exit_time, iv, dte)
        exit_bid = max(0.0, exit_mid - _half_spread(exit_mid))
    debit = entry_ask * CONTRACT_MULTIPLIER + option_leg_fees(1, entry_ask, sell=False)
    if debit <= 0 or debit > settled + 1e-9:
        return None
    credit = exit_bid * CONTRACT_MULTIPLIER - option_leg_fees(1, exit_bid, sell=True)
    pnl = credit - debit
    return _row(signal, fill, exit_raw, exit_time, reason, level, 1.0, debit, credit, pnl, strike)


def _row(
    signal: Signal,
    fill: float,
    exit_raw: float,
    exit_time: pd.Timestamp,
    reason: str,
    level: float,
    quantity: float,
    debit: float,
    credit: float,
    pnl: float,
    strike: float | None,
) -> dict:
    return {
        "symbol": signal.symbol,
        "mode": signal.mode,
        "direction": signal.direction,
        "signal_time": signal.signal_time,
        "fill_time": signal.fill_time,
        "exit_time": exit_time,
        "entry": fill,
        "exit": exit_raw,
        "stop": signal.stop,
        "target": level,
        "reason": reason,
        "quantity": quantity,
        "debit": debit,
        "credit": credit,
        "pnl": pnl,
        "strike": strike,
        "outer": signal.outer,
    }


def metrics_from(equity: pd.Series, pnls: list[float], starting: float) -> dict:
    """Same daily Sharpe as the rest of this repo: sqrt(252), zero risk-free rate."""
    empty = {
        "starting_equity": starting,
        "ending_equity": starting,
        "total_return": 0.0,
        "cagr": 0.0,
        "sharpe": 0.0,
        "max_drawdown": 0.0,
        "trades": 0,
        "win_rate": 0.0,
        "avg_win": 0.0,
        "avg_loss": 0.0,
        "profit_factor": None,
        "expectancy": 0.0,
        "breakeven_win_rate": None,
        "years": 0.0,
    }
    if equity is None or len(equity) == 0:
        return empty
    curve = pd.concat(
        [pd.Series([starting], index=[equity.index[0] - pd.Timedelta(days=1)]), equity.astype(float)]
    )
    ending = float(curve.iloc[-1])
    years = max((curve.index[-1] - curve.index[0]).days, 1) / 365.25
    total = ending / starting - 1.0 if starting else 0.0
    cagr = (ending / starting) ** (1.0 / years) - 1.0 if ending > 0 and starting > 0 else -1.0
    rets = curve.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    std = float(rets.std(ddof=0)) if len(rets) else 0.0
    sharpe = float(rets.mean() / std * np.sqrt(252)) if std > 0 else 0.0
    peak = curve.cummax()
    drawdown = curve / peak - 1.0
    max_dd = float(drawdown.min()) if len(drawdown) else 0.0
    count = len(pnls)
    win_rate = 0.0
    avg_win = 0.0
    avg_loss = 0.0
    profit_factor: float | None = None
    expectancy = 0.0
    breakeven = None
    if count:
        pnl = np.array(pnls, dtype=float)
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
        if avg_win + abs(avg_loss) > 0 and len(losses):
            breakeven = abs(avg_loss) / (avg_win + abs(avg_loss))
    return {
        "starting_equity": starting,
        "ending_equity": ending,
        "total_return": total,
        "cagr": cagr,
        "sharpe": sharpe,
        "max_drawdown": max_dd,
        "trades": count,
        "win_rate": win_rate,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "profit_factor": profit_factor,
        "expectancy": expectancy,
        "breakeven_win_rate": breakeven,
        "years": years,
    }


def passes_gate(metrics: dict) -> bool:
    """The published gate. A book of only winners has no finite profit factor and still clears that leg."""
    trades = int(metrics.get("trades") or 0)
    sharpe = float(metrics.get("sharpe") or 0.0)
    drawdown = float(metrics.get("max_drawdown") or 0.0)
    profit_factor = metrics.get("profit_factor")
    if profit_factor is None:
        pf_ok = trades > 0 and float(metrics.get("win_rate") or 0.0) == 1.0
    else:
        pf_ok = float(profit_factor) >= GATE_PF
    return trades >= GATE_TRADES and pf_ok and sharpe >= GATE_SHARPE and drawdown >= GATE_DRAWDOWN


def random_signals(frame: pd.DataFrame, symbol: str, count: int, seed: int = RANDOM_SEED) -> list[Signal]:
    """Same count of entries on random eligible bars. Direction is a coin flip. Target is applied later as 1R."""
    if count <= 0:
        return []
    bars = rth(frame)
    eligible: list[tuple[pd.Timestamp, pd.Timestamp, float, float]] = []
    for _day, session in bars.groupby(bars.index.date):
        if len(session) < 2:
            continue
        for i in range(len(session) - 1):
            stamp = session.index[i]
            nxt = session.index[i + 1]
            if stamp.time() > LAST_SIGNAL or nxt.time() >= FLAT or nxt.date() != stamp.date():
                continue
            low = float(session.iloc[i]["low"])
            high = float(session.iloc[i]["high"])
            if not np.isfinite(low) or not np.isfinite(high) or high <= 0 or low <= 0:
                continue
            eligible.append((stamp, nxt, low, high))
    if not eligible:
        return []
    rng = np.random.default_rng(seed)
    picks = rng.choice(len(eligible), size=count, replace=count > len(eligible))
    sides = rng.integers(0, 2, size=count)
    found = []
    for pick, side in zip(picks, sides):
        stamp, nxt, low, high = eligible[int(pick)]
        direction = "long" if int(side) == 0 else "short"
        stop = (low - STOP_PAD) if direction == "long" else (high + STOP_PAD)
        found.append(Signal(symbol, "random", direction, stamp, nxt, stop, float("nan"), float("nan"), OUTER_DEFAULT))
    found.sort(key=lambda item: item.fill_time)
    return found
