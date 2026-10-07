"""Option expiry on the original 2 SD VWAP extension. Backtests only.

The quality filters are not crossed with this table and are not retuned.
Nothing here places an order or edits the sandbox book.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Optional

import pandas as pd

from webull_bot.calendar import next_trading_day
from webull_bot.chart_reads.vwap_band import (
    DIVIDEND,
    FLAT,
    HALF_SPREAD_FLOOR,
    HALF_SPREAD_PCT,
    RATE,
    Signal,
    _day_key,
    _iv_on,
    metrics_from,
    target_price,
    walk_exit,
)
from webull_bot.mtf_vwap.detect import rth
from webull_bot.options.fees import CONTRACT_MULTIPLIER, option_leg_fees
from webull_bot.options.pricing import listed_strike, option_price

NY = "America/New_York"
CONTRACTS = (
    (0, "flat"),
    (1, "flat"),
    (1, "overnight"),
    (3, "flat"),
    (3, "overnight"),
    (7, "flat"),
    (7, "overnight"),
)


def contract_name(dte: int, hold: str) -> str:
    return f"{dte}dte-{hold}"


def expiry_session(entry: date, dte: int) -> date:
    """0 is the entry session. Later counts are trading days, so Friday + 1 is Monday."""
    cursor = entry
    for _ in range(int(dte)):
        cursor = next_trading_day(cursor)
    return cursor


def years_until(when: pd.Timestamp, expiry_day: date) -> float:
    """Clock time until 16:00 ET on the expiration session."""
    clock = pd.Timestamp(when)
    if clock.tzinfo is None:
        clock = clock.tz_localize(NY)
    else:
        clock = clock.tz_convert(NY)
    expiry = pd.Timestamp(datetime.combine(expiry_day, time(16, 0))).tz_localize(NY)
    minutes = max(1.0, (expiry - clock).total_seconds() / 60.0)
    return minutes / (365.0 * 24.0 * 60.0)


def iv_for_expiry(day: date, dte: int, short_points: dict, long_points: dict) -> Optional[float]:
    """0 and 1 DTE prefer VIX1D. 3 and 7 DTE use VIX. A missing VIX1D print falls back to VIX."""
    if int(dte) <= 1:
        value = _iv_on(day, short_points)
        if value is None:
            value = _iv_on(day, long_points)
        return value
    return _iv_on(day, long_points)


@dataclass(frozen=True)
class ContractFill:
    signal: Signal
    fill: float
    exit_time: pd.Timestamp
    reason: str
    debit: float
    credit: float
    pnl: float
    skip: str


def _half_spread(mid: float) -> float:
    return max(HALF_SPREAD_FLOOR, HALF_SPREAD_PCT * max(mid, 0.0))


def _mid(right: str, spot: float, strike: float, when: pd.Timestamp, iv: float, expiry_day: date) -> float:
    if spot <= 0 or strike <= 0 or iv <= 0:
        return 0.0
    return float(option_price(right, spot, strike, years_until(when, expiry_day), iv, RATE, DIVIDEND))


def _price_exit(
    signal: Signal,
    fill: float,
    exit_raw: float,
    exit_time: pd.Timestamp,
    reason: str,
    iv: float,
    expiry_day: date,
) -> ContractFill | None:
    right = "call" if signal.direction == "long" else "put"
    strike = listed_strike(fill, fill)
    entry_mid = _mid(right, fill, strike, signal.fill_time, iv, expiry_day)
    entry_ask = entry_mid + _half_spread(entry_mid)
    if entry_ask <= 0:
        return None
    exit_mid = _mid(right, exit_raw, strike, exit_time, iv, expiry_day)
    exit_bid = max(0.0, exit_mid - _half_spread(exit_mid))
    debit = entry_ask * CONTRACT_MULTIPLIER + option_leg_fees(1, entry_ask, sell=False)
    if debit <= 0:
        return None
    credit = exit_bid * CONTRACT_MULTIPLIER - option_leg_fees(1, exit_bid, sell=True)
    return ContractFill(signal, fill, exit_time, reason, debit, credit, credit - debit, "")


def _walk_held(
    bars: pd.DataFrame,
    fill_loc: int,
    direction: str,
    stop: float,
    target: float,
    expiry_day: date,
) -> tuple[str, float, pd.Timestamp]:
    """Same stop-first walk as the 15-minute book. Flat only on the expiration session."""
    last_reason = "last_bar"
    last_price = float(bars.iloc[fill_loc]["open"])
    last_time = bars.index[fill_loc]
    for offset in range(fill_loc, len(bars)):
        row = bars.iloc[offset]
        stamp = bars.index[offset]
        day = _day_key(stamp)
        if day > expiry_day:
            break
        opened = float(row["open"])
        high = float(row["high"])
        low = float(row["low"])
        if day == expiry_day and stamp.tz_convert(NY).time() >= FLAT:
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
        last_reason = "last_bar"
    return last_reason, last_price, last_time


def _sessions(bars: pd.DataFrame) -> dict[date, pd.DataFrame]:
    found = {}
    for key, chunk in bars.groupby(bars.index.date):
        day = key if isinstance(key, date) else pd.Timestamp(key).date()
        found[day] = chunk
    return found


def price_contracts(
    frame: pd.DataFrame,
    signals: list[Signal],
    short_points: dict,
    long_points: dict,
) -> dict[str, list[ContractFill]]:
    """One underlying walk per hold style, then a Black-Scholes price for each contract."""
    bars = rth(frame)
    by_day = _sessions(bars)
    books = {contract_name(dte, hold): [] for dte, hold in CONTRACTS}
    for signal in signals:
        day = _day_key(signal.fill_time)
        session = by_day.get(day)
        if session is None or signal.fill_time not in session.index:
            _drop(books, signal, "no_bar")
            continue
        loc = session.index.get_loc(signal.fill_time)
        full_loc = bars.index.get_loc(signal.fill_time)
        if isinstance(loc, slice) or not isinstance(loc, int) or isinstance(full_loc, slice) or not isinstance(full_loc, int):
            _drop(books, signal, "no_bar")
            continue
        fill = float(session.iloc[loc]["open"])
        if fill <= 0 or not pd.notna(signal.stop):
            _drop(books, signal, "no_bar")
            continue
        distance = abs(fill - float(signal.stop))
        if distance <= 0:
            _drop(books, signal, "dust")
            continue
        level = target_price(signal, fill, "r")
        flat_reason, flat_raw, flat_time = walk_exit(session, loc, signal.direction, float(signal.stop), level)
        held = {}
        for dte, hold in CONTRACTS:
            name = contract_name(dte, hold)
            iv = iv_for_expiry(day, dte, short_points, long_points)
            if iv is None:
                books[name].append(ContractFill(signal, fill, signal.fill_time, "", 0.0, 0.0, 0.0, "iv"))
                continue
            if hold == "overnight" and dte > 0:
                if dte not in held:
                    expiry = expiry_session(day, dte)
                    held[dte] = _walk_held(bars, full_loc, signal.direction, float(signal.stop), level, expiry)
                reason, raw, when = held[dte]
                expiry = expiry_session(day, dte)
            else:
                reason, raw, when = flat_reason, flat_raw, flat_time
                expiry = expiry_session(day, dte)
            priced = _price_exit(signal, fill, float(raw), when, reason, iv, expiry)
            if priced is None:
                books[name].append(ContractFill(signal, fill, when, reason, 0.0, 0.0, 0.0, "premium"))
            else:
                books[name].append(priced)
    for rows in books.values():
        rows.sort(key=lambda item: (item.signal.fill_time, item.signal.signal_time))
    return books


def _drop(books: dict, signal: Signal, skip: str) -> None:
    blank = ContractFill(signal, float("nan"), signal.fill_time, "", 0.0, 0.0, 0.0, skip)
    for rows in books.values():
        rows.append(blank)


def _marked(settled: float, unsettled: list, carries: list) -> float:
    return settled + sum(amount for _when, amount in unsettled) + sum(debit for _day, debit, _credit, _when in carries)


def run_expiry_account(
    frame: pd.DataFrame,
    priced: list[ContractFill],
    *,
    stake: float,
    start: date | None = None,
    end: date | None = None,
) -> dict:
    """One position. A same-day sale settles the next session. An overnight debit stays invested until the exit."""
    bars = rth(frame)
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
    days = []
    seen = set()
    for stamp in bars.index:
        day = _day_key(stamp)
        if day not in seen:
            seen.add(day)
            days.append(day)
    chosen = []
    for item in priced:
        day = _day_key(item.signal.fill_time)
        if start is not None and day < start:
            continue
        if end is not None and day > end:
            continue
        chosen.append(item)
    chosen.sort(key=lambda item: (item.signal.fill_time, item.signal.signal_time))

    settled = float(stake)
    unsettled: list[tuple[date, float]] = []
    carries: list[tuple[date, float, float, pd.Timestamp]] = []
    equity = float(stake)
    curve = []
    trades = []
    spans: list[tuple[date, date]] = []
    skips = {"overlap": 0, "no_bar": 0, "iv": 0, "premium": 0, "dust": 0, "bust": 0}
    busy = None
    cursor = 0
    stopped = False
    for day in days:
        still = []
        for available_on, amount in unsettled:
            if available_on <= day:
                settled += amount
            else:
                still.append((available_on, amount))
        unsettled = still
        held = []
        released = None
        for exit_day, debit, credit, exit_time in carries:
            if exit_day <= day:
                unsettled.append((next_trading_day(exit_day), credit))
                if exit_day == day:
                    released = exit_time
            else:
                held.append((exit_day, debit, credit, exit_time))
        carries = held
        if carries:
            busy = max(item[3] for item in carries)
        elif released is not None:
            busy = released
        else:
            busy = None
        equity = _marked(settled, unsettled, carries)
        while cursor < len(chosen) and _day_key(chosen[cursor].signal.fill_time) == day:
            item = chosen[cursor]
            cursor += 1
            if stopped or equity <= 1.0:
                skips["bust"] += 1
                continue
            if busy is not None and item.signal.fill_time <= busy:
                skips["overlap"] += 1
                continue
            if item.skip in skips:
                skips[item.skip] += 1
                continue
            if item.debit > settled + 1e-9:
                skips["premium"] += 1
                continue
            exit_day = _day_key(item.exit_time)
            settled -= item.debit
            if exit_day <= day:
                unsettled.append((next_trading_day(exit_day), item.credit))
            else:
                carries.append((exit_day, item.debit, item.credit, item.exit_time))
            equity = _marked(settled, unsettled, carries)
            trades.append(
                {
                    "signal_time": item.signal.signal_time,
                    "fill_time": item.signal.fill_time,
                    "exit_time": item.exit_time,
                    "pnl": item.pnl,
                    "reason": item.reason,
                }
            )
            spans.append((day, exit_day))
            busy = item.exit_time
            if equity <= 1.0:
                stopped = True
        curve.append((pd.Timestamp(day.isoformat()), equity))
    equity_series = pd.Series(
        [value for _stamp, value in curve],
        index=pd.DatetimeIndex([stamp for stamp, _value in curve]),
        dtype=float,
    )
    pnls = [float(trade["pnl"]) for trade in trades]
    return {
        "equity": equity_series,
        "trades": trades,
        "spans": spans,
        "skips": skips,
        "metrics": metrics_from(equity_series, pnls, float(stake)),
    }


def day_trade_stats(spans: list[tuple[date, date]], sessions: list[date]) -> dict:
    """Same-day round trips versus the 3-in-5 pattern-day-trader count. The account does not enforce it."""
    counts: dict[date, int] = {}
    day_trades = 0
    overnight = 0
    for entry, exit_day in spans:
        if exit_day <= entry:
            day_trades += 1
            counts[entry] = counts.get(entry, 0) + 1
        else:
            overnight += 1
    worst = 0
    exceed = 0
    windows = 0
    for index, _day in enumerate(sessions):
        window = sessions[max(0, index - 4): index + 1]
        if len(window) < 5:
            continue
        windows += 1
        total = sum(counts.get(item, 0) for item in window)
        worst = max(worst, total)
        if total > 3:
            exceed += 1
    return {
        "day_trades": day_trades,
        "overnight_holds": overnight,
        "worst_day_trades_in_5_sessions": worst,
        "windows_over_3": exceed,
        "windows": windows,
    }
