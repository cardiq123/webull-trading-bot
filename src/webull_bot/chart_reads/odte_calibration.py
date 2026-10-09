"""0DTE implied-vol check and a re-score of the three sandbox books.

The signal, the 1R stop and target, and the 15:45 flat stay frozen. Only the
Black-Scholes volatility and the bid-ask width change. Nothing here places
an order or imports the sandbox forward books.
"""

from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Optional

import numpy as np
import pandas as pd

from webull_bot.calendar import next_trading_day
from webull_bot.chart_reads.neckline import (
    DIVIDEND,
    HOLDOUT_END,
    HOLDOUT_START,
    MAX_TRADES_PER_DAY,
    RATE,
    TRAIN_END,
    TRAIN_START,
    VOL_CAP,
    VOL_FLOOR,
    Cell,
    _iv_on,
    _planned_target,
    _target_ok,
    _walk,
    _years,
    prepare,
    select_events,
)
from webull_bot.chart_reads.vwap_band import (
    OUTER_DEFAULT,
    find_signals,
    metrics_from,
    target_price,
    walk_exit,
)
from webull_bot.mtf_vwap.detect import rth
from webull_bot.options.fees import CONTRACT_MULTIPLIER, option_leg_fees
from webull_bot.options.pricing import listed_strike, option_price

GOAL = 10_000.0
RUIN = 500.0
VIX1D_OCT8 = 10.24
QUOTE_DAY = date(2026, 10, 9)
QUOTE_TIME = pd.Timestamp("2026-10-09 11:36", tz="America/New_York")
QUOTE_SPOT = 776.885
QUOTE_STRIKE = 777.0
QUOTE_BID = 1.13
QUOTE_ASK = 1.14
MORNING_TIME = pd.Timestamp("2026-10-09 10:05:30", tz="America/New_York")
MORNING_SPOT = 775.63
MORNING_STRIKE = 776.0
MORNING_FILL = 1.05
LOGGED_MODEL = (0.548, 2.51, 2.90, 3.25)
TRAP_CELL = Cell("QQQ", "confirmed", "short", "r1", "0dte")


def quote_mid() -> float:
    return (QUOTE_BID + QUOTE_ASK) / 2.0


def years_left(when: pd.Timestamp, dte: int = 0) -> float:
    """Same clock as the books: minutes until 16:00 on the expiry day, over a 365-day year."""
    clock = pd.Timestamp(when)
    if clock.tzinfo is not None:
        clock = clock.tz_convert("America/New_York")
    expiry = clock.normalize() + pd.Timedelta(days=int(dte), hours=16)
    minutes = max(1.0, (expiry - clock).total_seconds() / 60.0)
    return minutes / (365.0 * 24.0 * 60.0)


def implied_vol(right: str, spot: float, strike: float, when: pd.Timestamp, price: float, dte: int = 0) -> float:
    """Black-Scholes vol that matches ``price``. Same rate and dividend as the books."""
    if price <= 0 or spot <= 0 or strike <= 0:
        return float("nan")
    expiry_years = years_left(when, dte)
    lo, hi = 0.01, 3.0
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        value = float(option_price(right, spot, strike, expiry_years, mid, RATE, DIVIDEND))
        if value < price:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def model_mid(right: str, spot: float, strike: float, when: pd.Timestamp, iv: float, dte: int = 0) -> float:
    return float(option_price(right, spot, strike, years_left(when, dte), iv, RATE, DIVIDEND))


def minutes_that_fit(price: float, iv: float, spot: float = QUOTE_SPOT, strike: float = QUOTE_STRIKE) -> float:
    """Minutes to 16:00 that would make ``iv`` price the call at ``price``. The book uses the real minutes."""
    lo, hi = 1.0, 5.0 * 24.0 * 60.0
    for _ in range(50):
        minutes = 0.5 * (lo + hi)
        expiry_years = minutes / (365.0 * 24.0 * 60.0)
        value = float(option_price("call", spot, strike, expiry_years, iv, RATE, DIVIDEND))
        if value < price:
            lo = minutes
        else:
            hi = minutes
    return 0.5 * (lo + hi)


def calibrate(vix1d_points: float = VIX1D_OCT8) -> dict:
    """Implied vol of the 11:36 SPY quote and of the morning fill, against one VIX1D close."""
    prior = float(vix1d_points) / 100.0
    mid = quote_mid()
    iv_mid = implied_vol("call", QUOTE_SPOT, QUOTE_STRIKE, QUOTE_TIME, mid, 0)
    iv_fill = implied_vol("call", MORNING_SPOT, MORNING_STRIKE, MORNING_TIME, MORNING_FILL, 0)
    book_minutes = years_left(QUOTE_TIME, 0) * 365.0 * 24.0 * 60.0
    return {
        "vix1d_points": float(vix1d_points),
        "vix1d": prior,
        "quote_mid": mid,
        "implied_0dte": iv_mid,
        "multiplier_0dte": iv_mid / prior if prior else float("nan"),
        "additive_points": (iv_mid - prior) * 100.0,
        "morning_implied": iv_fill,
        "morning_multiplier": iv_fill / prior if prior else float("nan"),
        "book_minutes": book_minutes,
        "minutes_if_vol_unchanged": minutes_that_fit(mid, prior),
        "model_at_prior": model_mid("call", QUOTE_SPOT, QUOTE_STRIKE, QUOTE_TIME, prior, 0),
    }


def half_spread(mid: float, width: str) -> float:
    """``model`` is the book's spread. ``0.01`` and ``0.02`` are the full bid-ask width."""
    if width == "model":
        return max(0.01, 0.015 * max(float(mid), 0.0))
    if width == "0.01":
        return 0.005
    if width == "0.02":
        return 0.01
    raise ValueError(width)


def _clip(iv: float) -> float:
    return min(VOL_CAP, max(VOL_FLOOR, float(iv)))


def price_structures(structures: list[dict], iv_points: dict, scale: float, width: str) -> list[tuple]:
    """One contract's debit and credit. Sizing is applied later."""
    rows: list[tuple] = []
    for item in structures:
        base = _iv_on(item["day"], iv_points)
        if base is None:
            continue
        used = _clip(base * float(scale))
        strike = listed_strike(item["fill"], item["fill"])
        opened = _ticket(item["right"], item["fill"], strike, item["fill_time"], used, width, buy=True)
        if opened is None:
            continue
        debit, ask = opened
        credit = _ticket(item["right"], item["exit"], strike, item["exit_time"], used, width, buy=False)
        rows.append((item["day"], item["due"], item["fill_i"], item["exit_i"], float(debit), float(credit), float(ask)))
    rows.sort(key=lambda row: (row[0], row[2]))
    return rows


def _ticket(right: str, spot: float, strike: float, when, iv: float, width: str, buy: bool) -> Optional[tuple[float, float] | float]:
    mid = float(option_price(right, spot, strike, _years(when), iv, RATE, DIVIDEND))
    if not math.isfinite(mid) or mid < 0:
        mid = 0.0
    spread = half_spread(mid, width)
    if buy:
        ask = mid + spread
        if ask <= 0:
            return None
        debit = ask * CONTRACT_MULTIPLIER + option_leg_fees(1, ask, sell=False)
        if not math.isfinite(debit) or debit <= 0:
            return None
        return debit, ask
    bid = max(0.0, mid - spread)
    return bid * CONTRACT_MULTIPLIER - option_leg_fees(1, bid, sell=True)


def contracts_for(qty: int, settled: float, debit: float) -> int:
    """The whole ticket or nothing. A 3-lot is not cut down to one."""
    if qty < 1 or debit <= 0 or settled <= 0:
        return 0
    if qty * debit > settled + 1e-9:
        return 0
    return qty


def daily_equity(
    cands: list[tuple],
    sessions: list[date],
    qty: int,
    cap: Optional[int],
    stake: float,
) -> tuple[pd.Series, list[float]]:
    if not sessions:
        index = pd.DatetimeIndex([pd.Timestamp(TRAIN_START)])
        return pd.Series([stake], index=index), []
    by_day: dict[date, list[tuple]] = {}
    for row in cands:
        by_day.setdefault(row[0], []).append(row)
    settled = float(stake)
    pending: list[tuple[date, float]] = []
    pnls: list[float] = []
    values = []
    for day in sessions:
        if pending:
            still = []
            for when, amount in pending:
                if when <= day:
                    settled += amount
                else:
                    still.append((when, amount))
            pending = still
        taken_n = 0
        # Flat by the close, so the next session is free. A walk that runs off
        # a half-day must not keep the lock for the rest of the file.
        busy = -1
        for _day, due, fill_i, exit_i, debit, credit, _ask in by_day.get(day, []):
            if cap is not None and taken_n >= cap:
                continue
            if fill_i <= busy:
                continue
            if contracts_for(qty, settled, debit) < 1:
                continue
            settled -= qty * debit
            pending.append((due, qty * credit))
            pnls.append(qty * (credit - debit))
            taken_n += 1
            busy = exit_i
        values.append(settled + sum(amount for _when, amount in pending))
    index = pd.DatetimeIndex([pd.Timestamp(day) for day in sessions])
    return pd.Series(values, index=index, dtype=float), pnls


def simulate_path(cands: list[tuple], start: date, end: date, qty: int, cap: Optional[int], stake: float) -> dict:
    settled = float(stake)
    pending: list[tuple[date, float]] = []
    busy = -1
    taken_day = None
    taken_n = 0
    equity = float(stake)
    peak = float(stake)
    max_dd = 0.0
    reached: Optional[date] = None
    ruined = False

    def _mark(day: date, value: float) -> None:
        nonlocal peak, max_dd, reached, ruined
        if value > peak:
            peak = value
        if peak > 0:
            drawdown = value / peak - 1.0
            if drawdown < max_dd:
                max_dd = drawdown
        if reached is None and value >= GOAL:
            reached = day
        if value < RUIN:
            ruined = True

    for day, due, fill_i, exit_i, debit, credit, _ask in cands:
        if day < start or day > end:
            continue
        if pending:
            still = []
            for when, amount in pending:
                if when <= day:
                    settled += amount
                else:
                    still.append((when, amount))
            pending = still
        if taken_day != day:
            taken_day = day
            taken_n = 0
            busy = -1
        if cap is not None and taken_n >= cap:
            continue
        if fill_i <= busy:
            continue
        if contracts_for(qty, settled, debit) < 1:
            continue
        settled -= qty * debit
        pending.append((due, qty * credit))
        taken_n += 1
        busy = exit_i
        equity = settled + sum(amount for _when, amount in pending)
        _mark(day, equity)
    return {"ending": equity, "max_dd": max_dd, "reached": reached, "ruined": ruined}


def _bisect_left(ords: list[int], target: int) -> int:
    lo, hi = 0, len(ords)
    while lo < hi:
        mid = (lo + hi) // 2
        if ords[mid] < target:
            lo = mid + 1
        else:
            hi = mid
    return lo


def _bisect_right(ords: list[int], target: int) -> int:
    lo, hi = 0, len(ords)
    while lo < hi:
        mid = (lo + hi) // 2
        if ords[mid] <= target:
            lo = mid + 1
        else:
            hi = mid
    return lo


def _add_months(day: date, months: int) -> date:
    month_index = day.month - 1 + int(months)
    year = day.year + month_index // 12
    month = month_index % 12 + 1
    if month == 12:
        nxt = date(year + 1, 1, 1)
    else:
        nxt = date(year, month + 1, 1)
    last = (nxt - timedelta(days=1)).day
    return date(year, month, min(day.day, last))


def rolling_stats(cands: list[tuple], sessions: list[date], window_end: date, qty: int, cap: Optional[int], stake: float) -> dict:
    eligible = [day for day in sessions if _add_months(day, 12) <= window_end]
    empty = {
        "starts": 0,
        "p_reach_12": None,
        "p_ruin": None,
        "median_ending": None,
        "p10_ending": None,
    }
    if not eligible:
        return empty
    ords = [row[0].toordinal() for row in cands]
    endings = []
    reach = 0
    ruins = 0
    for start in eligible:
        horizon = _add_months(start, 12)
        left = _bisect_left(ords, start.toordinal())
        right = _bisect_right(ords, horizon.toordinal())
        path = simulate_path(cands[left:right], start, horizon, qty, cap, stake)
        endings.append(path["ending"])
        if path["ruined"]:
            ruins += 1
        if path["reached"] is not None and path["reached"] <= horizon:
            reach += 1
    count = len(eligible)
    return {
        "starts": count,
        "p_reach_12": reach / count,
        "p_ruin": ruins / count,
        "median_ending": float(np.median(endings)),
        "p10_ending": float(np.percentile(endings, 10)),
    }


def score_window(
    cands: list[tuple],
    sessions: list[date],
    start: date,
    end: date,
    qty: int,
    cap: Optional[int],
    stake: float,
    rolling: bool,
) -> dict:
    window_sessions = [day for day in sessions if start <= day <= end]
    equity, pnls = daily_equity(cands, window_sessions, qty, cap, stake)
    metrics = metrics_from(equity, pnls, stake)
    out = {"metrics": metrics}
    if rolling:
        out["rolling"] = rolling_stats(cands, window_sessions, end, qty, cap, stake)
    return out


def to_fifteen(five: pd.DataFrame) -> pd.DataFrame:
    bars = rth(five)
    if bars.empty:
        return bars
    bucket = bars.index.floor("15min")
    grouped = bars.groupby(bucket, sort=True).agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
    )
    grouped.index = pd.DatetimeIndex(grouped.index)
    if bars.index.tz is not None and grouped.index.tz is None:
        grouped.index = grouped.index.tz_localize(bars.index.tz)
    return grouped.dropna(subset=["open", "high", "low", "close"])


def vwap_structures(frame: pd.DataFrame, symbol: str) -> list[dict]:
    signals = [item for item in find_signals(frame, symbol, OUTER_DEFAULT) if item.mode == "extension"]
    if frame.empty or not signals:
        return []
    positions = {stamp: i for i, stamp in enumerate(frame.index)}
    days: dict[date, pd.DataFrame] = {}
    for day, session in frame.groupby(frame.index.date):
        days[day if isinstance(day, date) else pd.Timestamp(day).date()] = session
    found = []
    for signal in signals:
        fill_time = pd.Timestamp(signal.fill_time)
        day = fill_time.date()
        session = days.get(day)
        if session is None or fill_time not in session.index:
            continue
        fill = float(session.loc[fill_time, "open"])
        if not math.isfinite(fill) or fill <= 0:
            continue
        if signal.direction == "short" and fill >= float(signal.stop):
            continue
        if signal.direction == "long" and fill <= float(signal.stop):
            continue
        target = float(target_price(signal, fill, "r"))
        loc = int(session.index.get_loc(fill_time))
        _reason, exit_raw, when = walk_exit(session, loc, signal.direction, float(signal.stop), target)
        when = pd.Timestamp(when)
        if when not in positions or fill_time not in positions:
            continue
        found.append(
            {
                "day": day,
                "due": next_trading_day(day),
                "fill_i": positions[fill_time],
                "exit_i": positions[when],
                "fill": fill,
                "exit": float(exit_raw),
                "fill_time": fill_time,
                "exit_time": when,
                "right": "call" if signal.direction == "long" else "put",
            }
        )
    return found


def trapdoor_structures(book) -> list[dict]:
    found = []
    for event in select_events(book.events, TRAP_CELL):
        fill = float(book.open[event.fill_i])
        if not math.isfinite(fill) or fill <= 0 or fill >= event.stop:
            continue
        target = _planned_target(book, event, fill, "r1")
        if not _target_ok(event.direction, fill, target, "r1"):
            continue
        _reason, exit_raw, when = _walk(book, event.fill_i, event.direction, event.stop, target, "r1")
        exit_i = int(book.index.get_loc(when))
        day = book.dates[event.fill_i]
        if not isinstance(day, date):
            day = pd.Timestamp(day).date()
        found.append(
            {
                "day": day,
                "due": next_trading_day(day),
                "fill_i": int(event.fill_i),
                "exit_i": exit_i,
                "fill": fill,
                "exit": float(exit_raw),
                "fill_time": book.index[event.fill_i],
                "exit_time": when,
                "right": "put",
            }
        )
    return found


def session_dates(frame: pd.DataFrame) -> list[date]:
    found = []
    seen = set()
    for stamp in frame.index:
        day = pd.Timestamp(stamp).date()
        if day in seen:
            continue
        seen.add(day)
        found.append(day)
    return found


def books() -> tuple[dict, ...]:
    return (
        {
            "id": "spy_vwap",
            "name": "SPY VWAP",
            "qty": 1,
            "stake": 1_000.0,
            "cap": None,
            "rolling": False,
            "blurb": "One at-the-money 0 DTE contract, 1R, $1,000, no daily count cap.",
        },
        {
            "id": "qqq_aggr",
            "name": "QQQ Aggressive",
            "qty": 3,
            "stake": 2_500.0,
            "cap": 5,
            "rolling": True,
            "blurb": "Three at-the-money 0 DTE contracts, 1R, $2,500, at most 5 fills a day.",
        },
        {
            "id": "trapdoor",
            "name": "QQQ Trapdoor",
            "qty": 1,
            "stake": 2_500.0,
            "cap": MAX_TRADES_PER_DAY,
            "rolling": False,
            "blurb": "One at-the-money 0 DTE put, 1R, $2,500, at most 3 fills a day.",
        },
    )


def scenarios(multiplier: float) -> tuple[tuple[str, float, str], ...]:
    scales = (1.0, 1.5, 2.0, multiplier)
    rows = [("x1.0, book spread", 1.0, "model")]
    for scale in scales:
        label = _scale_label(scale, multiplier)
        rows.append((f"{label}, 1 cent wide", scale, "0.01"))
        rows.append((f"{label}, 2 cents wide", scale, "0.02"))
    return tuple(rows)


def _scale_label(scale: float, multiplier: float) -> str:
    if abs(scale - multiplier) < 1e-9 and abs(scale - 1.0) > 1e-9 and abs(scale - 1.5) > 1e-9 and abs(scale - 2.0) > 1e-9:
        return f"x{scale:.2f} calibrated"
    return f"x{scale:.1f}"
