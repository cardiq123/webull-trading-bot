"""Strike and size grid for the frozen QQQ Trapdoor. Backtests only.

The entry is the neckline cell ``QQQ_confirmed_short_r1_0dte``. This module
does not add signals, does not retune the double top, and does not import
the sandbox forward book. A second block repeats the same size grid on the
frozen 15-minute 2 SD QQQ continuation (``vwap_band_15m_qqq``), 1R only.

Nothing here places an order.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

import numpy as np
import pandas as pd

from webull_bot.calendar import next_trading_day
from webull_bot.chart_reads.atm_exit import deflated_sharpe
from webull_bot.chart_reads.neckline import (
    DIVIDEND,
    HOLDOUT_END,
    HOLDOUT_START,
    MAX_TRADES_PER_DAY,
    RATE,
    STAKE,
    TRAIN_END,
    TRAIN_START,
    VOL_CAP,
    VOL_FLOOR,
    Cell as NeckCell,
    _half_spread,
    _iv_on,
    _planned_target,
    _target_ok,
    _walk,
    _years,
    benjamini_hochberg,
    daily_returns,
    p_value,
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
from webull_bot.options.pricing import listed_strike, option_delta, option_price, strike_for_put_delta

GOAL = 10_000.0
RUIN = 500.0
HORIZONS = (4, 8, 12)
# +1.5 volatility points per 0.10 of absolute delta below 0.50.
SKEW_STEP = 0.015
SKEW_WIDTH = 0.10
SKEW_ANCHOR = 0.50
OTM_HALF_SPREAD_FLOOR = 0.02
OTM_HALF_SPREAD_PCT = 0.08
GATE_PF = 1.10
GATE_SHARPE = 0.40
GATE_DRAWDOWN = -0.30
GATE_TRADES = 300
GATE_Q = 0.10
GATE_DSR = 0.95
TRAP_CAP = MAX_TRADES_PER_DAY
VWAP_CAP = 5
SIGNAL = NeckCell("QQQ", "confirmed", "short", "r1", "0dte")
STRIKES = ("atm", "otm1", "otm2", "otm3", "d40", "d30", "d20")
OTM_STRIKES = ("otm1", "otm2", "otm3", "d40", "d30", "d20")
DELTA_TARGET = {"d40": 0.40, "d30": 0.30, "d20": 0.20}
SIZES = ("c1", "c3", "c5", "c7", "c10", "f10", "f20", "f30", "f50")
WEAK_STRIKES = {"otm2", "otm3", "d30", "d20"}
SIZE_CONTRACTS = {"c1": 1, "c3": 3, "c5": 5, "c7": 7, "c10": 10}
SIZE_FRACTION = {"f10": 0.10, "f20": 0.20, "f30": 0.30, "f50": 0.50}


@dataclass(frozen=True)
class Spec:
    book: str
    strike: str
    exit: str
    size: str
    skew: str

    @property
    def id(self) -> str:
        return f"{self.book}_{self.strike}_{self.exit}_{self.size}_{self.skew}"

    @property
    def cap(self) -> int:
        return TRAP_CAP if self.book == "trapdoor" else VWAP_CAP


def catalog() -> tuple[Spec, ...]:
    """Every cell in the false-discovery family. Order is fixed."""
    cells: list[Spec] = []
    for strike in STRIKES:
        exits = ("r1",) if strike == "atm" else ("r1", "r2")
        skews = ("off",) if strike == "atm" else ("off", "on")
        for exit_name in exits:
            for size in SIZES:
                for skew in skews:
                    cells.append(Spec("trapdoor", strike, exit_name, size, skew))
    for size in SIZES:
        cells.append(Spec("vwap", "atm", "r1", size, "off"))
    return tuple(cells)


def n_trials() -> int:
    return len(catalog())


def frozen_rules() -> dict:
    return {
        "study": "trapdoor_aggressive",
        "registered_before_score": True,
        "question": (
            "Which pre-registered put and size, on the unchanged QQQ Trapdoor signal, "
            "most often turns a fresh $2,500 into $10,000 inside a year, and how often "
            "that path falls under $500."
        ),
        "signal": (
            "QQQ confirmed short only. Double top as frozen in the neckline study, "
            "including the six-bar minimum separation. Trigger is a 5-minute close "
            "below the neckline and below both the 9 and 20 EMA. Entries are not retuned."
        ),
        "signal_cell": SIGNAL.id,
        "comparison": (
            "vwap_band_15m_qqq is the frozen 15-minute 2 SD continuation, both directions, "
            "1R, one position, flat at 15:45. The size grid is the same. The strike stays at the money. "
            "Its daily cap in this study is 5 fills. The scored VWAP book had no daily count cap."
        ),
        "train": [TRAIN_START.isoformat(), TRAIN_END.isoformat()],
        "holdout": [HOLDOUT_START.isoformat(), HOLDOUT_END.isoformat()],
        "stake": STAKE,
        "goal": GOAL,
        "ruin": RUIN,
        "horizons_months": list(HORIZONS),
        "rolling": (
            "Every session start with a full 12 months still inside that window gets a fresh $2,500. "
            "Train starts cannot use 2024. Holdout starts cannot use prices after 2026-10-06. "
            "The 4-month and 8-month chances use those same 12-month starts, so a start that gets "
            "to $10,000 in month 5 counts for 8 and 12 months and not for 4."
        ),
        "daily_cap": {"trapdoor": TRAP_CAP, "vwap": VWAP_CAP},
        "flat": "15:45 ET open. No overnight hold.",
        "one_position": "A new signal while a trade is open is skipped. A skipped trade does not block the next one.",
        "sizing": {
            "fixed_contracts": [1, 3, 5, 7, 10],
            "fixed_fraction_of_equity": [0.10, 0.20, 0.30, 0.50],
            "unaffordable": (
                "If the whole ticket costs more than settled cash, the trade is skipped. "
                "A 10-lot is not cut down to whatever fits."
            ),
            "settlement": "The sale is spendable the next session. It still counts in equity the same day.",
        },
        "strikes": {
            "atm": "Listed strike nearest the fill.",
            "otm1": "One listed strike below that, a put further out of the money.",
            "otm2": "Two listed strikes below.",
            "otm3": "Three listed strikes below.",
            "d40": "Listed strike whose Black-Scholes put delta is nearest -0.40, at or below the at-the-money strike.",
            "d30": "Same for -0.30.",
            "d20": "Same for -0.20.",
            "exits": "At the money is 1R only. Every out-of-the-money put is scored at 1R and at 2R. The stop stays one cent beyond the second high.",
        },
        "pricing": {
            "model": "Black-Scholes, rate 2%, dividend 0, same 0 DTE clock as the neckline study.",
            "iv": "Prior VIX1D close when that print exists, otherwise the prior VIX close. Clipped to 5%–150%.",
            "skew": (
                "Off uses that IV for every strike. On adds 1.5 volatility points per 0.10 of absolute delta "
                "below 0.50, measured at the base IV: bump = 0.015 * max(0, 0.50 - abs(delta)) / 0.10. "
                "The bump is frozen at entry and used for the exit mark too. At-the-money delta is about 0.50, so the bump is zero and that cell is not doubled."
            ),
            "spread_atm": "Half-spread max($0.01, 1.5% of the mid), the neckline book's spread.",
            "spread_otm": (
                "Half-spread max($0.02, 8% of the mid) on each side when the listed put strike is below "
                "the at-the-money strike. A delta target that the $1 board rounds back to at the money "
                "keeps the at-the-money spread. Both skew settings use this."
            ),
            "trust": (
                "A cheap 0 DTE out-of-the-money put is where this model is least trustworthy. "
                "Two and three strikes out, and deltas 0.30 and 0.20, are flagged, as is a median ask under $0.50."
            ),
        },
        "gate": {
            "holdout_only": True,
            "profit_factor": GATE_PF,
            "sharpe": GATE_SHARPE,
            "max_drawdown": GATE_DRAWDOWN,
            "trades": GATE_TRADES,
            "q": GATE_Q,
            "dsr": GATE_DSR,
            "null": "The average holdout trade does not make money. One-sided t test, then Benjamini-Hochberg across the whole grid.",
            "note": "Reaching $10,000 is the report sort. It is not a second gate and it does not retune the entry.",
        },
        "family": n_trials(),
        "live_trading": False,
    }


def plain_name(spec: Spec) -> str:
    strike = {
        "atm": "at the money",
        "otm1": "1 strike out of the money",
        "otm2": "2 strikes out of the money",
        "otm3": "3 strikes out of the money",
        "d40": "about a 0.40 delta",
        "d30": "about a 0.30 delta",
        "d20": "about a 0.20 delta",
    }[spec.strike]
    size = {
        "c1": "1 contract",
        "c3": "3 contracts",
        "c5": "5 contracts",
        "c7": "7 contracts",
        "c10": "10 contracts",
        "f10": "10% of equity",
        "f20": "20% of equity",
        "f30": "30% of equity",
        "f50": "50% of equity",
    }[spec.size]
    book = "QQQ Trapdoor" if spec.book == "trapdoor" else "QQQ VWAP 2 SD"
    exit_name = "1R" if spec.exit == "r1" else "2R"
    skew = ""
    if spec.strike != "atm":
        skew = ", skew bump on" if spec.skew == "on" else ", skew bump off"
    return f"{book}, {strike}, {exit_name}, {size}{skew}"


def skew_bump(abs_delta: float) -> float:
    """Extra IV, in decimal, for an out-of-the-money put. Zero at 0.50 delta."""
    if not math.isfinite(abs_delta):
        return 0.0
    gap = max(0.0, SKEW_ANCHOR - abs(float(abs_delta)))
    return SKEW_STEP * (gap / SKEW_WIDTH)


def half_spread(mid: float, otm: bool) -> float:
    if otm:
        return max(OTM_HALF_SPREAD_FLOOR, OTM_HALF_SPREAD_PCT * max(float(mid), 0.0))
    return _half_spread(mid)


def add_months(day: date, months: int) -> date:
    month_index = day.month - 1 + int(months)
    year = day.year + month_index // 12
    month = month_index % 12 + 1
    last = _month_last(year, month)
    return date(year, month, min(day.day, last))


def _month_last(year: int, month: int) -> int:
    if month == 12:
        nxt = date(year + 1, 1, 1)
    else:
        nxt = date(year, month + 1, 1)
    return (nxt - timedelta(days=1)).day


def choose_strike(spot: float, when, iv: float, rule: str) -> tuple[float, float]:
    """Listed strike and the absolute put delta at the base IV."""
    years = _years(when)
    atm = listed_strike(spot, spot)
    if rule == "atm":
        strike = atm
    elif rule in {"otm1", "otm2", "otm3"}:
        step = 1.0 if spot >= 25.0 else 0.5
        strike = max(step, atm - int(rule[-1]) * step)
    else:
        raw = strike_for_put_delta(spot, years, iv, DELTA_TARGET[rule], RATE, DIVIDEND)
        strike = min(atm, listed_strike(spot, raw))
    delta = option_delta("put", spot, strike, years, iv, RATE, DIVIDEND)
    return float(strike), abs(float(delta))


def quote_ticket(right: str, spot: float, strike: float, when, iv: float, otm: bool) -> Optional[tuple[float, float, float]]:
    """Per-contract debit, credit ingredients: debit, mid, ask. Credit is priced later."""
    mid = float(option_price(right, spot, strike, _years(when), iv, RATE, DIVIDEND))
    if not math.isfinite(mid) or mid < 0:
        mid = 0.0
    spread = half_spread(mid, otm)
    ask = mid + spread
    if ask <= 0:
        return None
    debit = ask * CONTRACT_MULTIPLIER + option_leg_fees(1, ask, sell=False)
    if not math.isfinite(debit) or debit <= 0:
        return None
    return debit, mid, ask


def credit_ticket(right: str, spot: float, strike: float, when, iv: float, otm: bool) -> float:
    mid = float(option_price(right, spot, strike, _years(when), iv, RATE, DIVIDEND))
    if not math.isfinite(mid) or mid < 0:
        mid = 0.0
    bid = max(0.0, mid - half_spread(mid, otm))
    return bid * CONTRACT_MULTIPLIER - option_leg_fees(1, bid, sell=True)


def trapdoor_events(book) -> list:
    """The frozen short. No other neckline cell is added here."""
    return select_events(book.events, SIGNAL)


def to_fifteen(five: pd.DataFrame) -> pd.DataFrame:
    """Regular-hours 5-minute bars rolled up to 15 minutes, left-labeled."""
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


def _clip_iv(iv: float, bump: float) -> float:
    return min(VOL_CAP, max(VOL_FLOOR, float(iv) + float(bump)))


def _structural_trap(book, event, exit_name: str) -> Optional[dict]:
    fill = float(book.open[event.fill_i])
    if not math.isfinite(fill) or fill <= 0:
        return None
    if event.direction == "short" and fill >= event.stop:
        return None
    if event.direction == "long" and fill <= event.stop:
        return None
    target = _planned_target(book, event, fill, exit_name)
    if not _target_ok(event.direction, fill, target, exit_name):
        return None
    _reason, exit_raw, when = _walk(book, event.fill_i, event.direction, event.stop, target, exit_name)
    exit_i = int(book.index.get_loc(when))
    return {
        "day": book.dates[event.fill_i],
        "due": next_trading_day(book.dates[event.fill_i]),
        "fill_i": int(event.fill_i),
        "exit_i": exit_i,
        "fill": fill,
        "exit": float(exit_raw),
        "fill_time": book.index[event.fill_i],
        "exit_time": when,
        "right": "put" if event.direction == "short" else "call",
    }


def price_structures(structures: list[dict], iv_points: dict, strike: str, skew: str) -> list[tuple]:
    """Per-contract tickets. Sizing is applied later, so one price serves every size."""
    rows: list[tuple] = []
    for item in structures:
        base = _iv_on(item["day"], iv_points)
        if base is None:
            continue
        atm_strike = listed_strike(item["fill"], item["fill"])
        if item["right"] == "put":
            chosen, abs_delta = choose_strike(item["fill"], item["fill_time"], base, strike if strike != "atm" else "atm")
        else:
            chosen = atm_strike
            abs_delta = abs(
                option_delta("call", item["fill"], chosen, _years(item["fill_time"]), base, RATE, DIVIDEND)
            )
        truly_otm = item["right"] == "put" and chosen < atm_strike - 1e-9
        bump = skew_bump(abs_delta) if skew == "on" else 0.0
        used = _clip_iv(base, bump)
        opened = quote_ticket(item["right"], item["fill"], chosen, item["fill_time"], used, truly_otm)
        if opened is None:
            continue
        debit, _mid, ask = opened
        credit = credit_ticket(item["right"], item["exit"], chosen, item["exit_time"], used, truly_otm)
        rows.append(
            (item["day"], item["due"], item["fill_i"], item["exit_i"], float(debit), float(credit), float(ask))
        )
    rows.sort(key=lambda row: (row[0], row[2]))
    return rows


def trapdoor_structures(book, events) -> dict[str, list[dict]]:
    found = {"r1": [], "r2": []}
    for event in events:
        for exit_name in ("r1", "r2"):
            item = _structural_trap(book, event, exit_name)
            if item is not None:
                found[exit_name].append(item)
    return found


def vwap_structures(frame: pd.DataFrame) -> list[dict]:
    """Frozen 2 SD continuation only. Reversals are not in this comparison."""
    signals = [item for item in find_signals(frame, "QQQ", OUTER_DEFAULT) if item.mode == "extension"]
    if frame.empty or not signals:
        return []
    positions = {stamp: i for i, stamp in enumerate(frame.index)}
    days: dict[date, pd.DataFrame] = {}
    for day, session in frame.groupby(frame.index.date):
        days[day] = session
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


def contracts_for(size: str, equity: float, settled: float, debit: float) -> int:
    """Whole ticket or nothing. A fixed lot is not scaled down to the cash on hand."""
    if debit <= 0 or equity <= 0 or settled <= 0:
        return 0
    if size in SIZE_CONTRACTS:
        qty = SIZE_CONTRACTS[size]
    else:
        qty = int((SIZE_FRACTION[size] * equity) / debit)
    if qty < 1:
        return 0
    if qty * debit > settled + 1e-9:
        return 0
    return qty


def simulate_path(cands: list[tuple], start: date, end: date, size: str, cap: int, stake: float = STAKE) -> dict:
    """One fresh account. Equity counts an exit the same day. Cash can spend it the next session."""
    settled = float(stake)
    pending: list[tuple[date, float]] = []
    busy = -1
    taken_day = None
    taken_n = 0
    pnls: list[float] = []
    skips = {"cap": 0, "overlap": 0, "premium": 0}
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
        if day < start:
            continue
        if day > end:
            break
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
        if taken_n >= cap:
            skips["cap"] += 1
            continue
        if fill_i <= busy:
            skips["overlap"] += 1
            continue
        equity_now = settled + sum(amount for _when, amount in pending)
        qty = contracts_for(size, equity_now, settled, debit)
        if qty < 1:
            skips["premium"] += 1
            continue
        cash_out = qty * debit
        cash_back = qty * credit
        settled -= cash_out
        pending.append((due, cash_back))
        pnls.append(cash_back - cash_out)
        taken_n += 1
        busy = exit_i
        equity = settled + sum(amount for _when, amount in pending)
        _mark(day, equity)
    if reached is not None and reached < start:
        reached = None
    return {
        "pnls": pnls,
        "ending": equity,
        "max_dd": max_dd,
        "reached": reached,
        "ruined": ruined,
        "trades": len(pnls),
        "skips": skips,
    }


def daily_equity(cands: list[tuple], sessions: list[date], size: str, cap: int, stake: float = STAKE) -> tuple[pd.Series, list[float], dict]:
    """End-of-day cash mirror, including sessions with no trade."""
    if not sessions:
        index = pd.DatetimeIndex([pd.Timestamp(TRAIN_START)])
        return pd.Series([stake], index=index), [], {"cap": 0, "overlap": 0, "premium": 0}
    by_day: dict[date, list[tuple]] = {}
    for row in cands:
        by_day.setdefault(row[0], []).append(row)
    settled = float(stake)
    pending: list[tuple[date, float]] = []
    busy = -1
    pnls: list[float] = []
    skips = {"cap": 0, "overlap": 0, "premium": 0}
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
        for _day, due, fill_i, exit_i, debit, credit, _ask in by_day.get(day, []):
            if taken_n >= cap:
                skips["cap"] += 1
                continue
            if fill_i <= busy:
                skips["overlap"] += 1
                continue
            equity_now = settled + sum(amount for _when, amount in pending)
            qty = contracts_for(size, equity_now, settled, debit)
            if qty < 1:
                skips["premium"] += 1
                continue
            cash_out = qty * debit
            cash_back = qty * credit
            settled -= cash_out
            pending.append((due, cash_back))
            pnls.append(cash_back - cash_out)
            taken_n += 1
            busy = exit_i
        values.append(settled + sum(amount for _when, amount in pending))
    index = pd.DatetimeIndex([pd.Timestamp(day) for day in sessions])
    return pd.Series(values, index=index, dtype=float), pnls, skips


def _empty_rolling() -> dict:
    return {
        "starts": 0,
        "p_reach_4": None,
        "p_reach_8": None,
        "p_reach_12": None,
        "median_days_to_goal": None,
        "paths_reaching_12": 0,
        "p_ruin": None,
        "median_ending": None,
        "p10_ending": None,
        "median_drawdown": None,
        "p10_drawdown": None,
    }


def rolling_stats(cands: list[tuple], sessions: list[date], window_end: date, size: str, cap: int) -> dict:
    """Fresh $2,500 at each start that still has 12 months inside the window."""
    eligible = [day for day in sessions if add_months(day, 12) <= window_end]
    if not eligible:
        return _empty_rolling()
    ords = [row[0].toordinal() for row in cands]
    endings = []
    drawdowns = []
    days_to = []
    reach4 = 0
    reach8 = 0
    reach12 = 0
    ruins = 0
    for start in eligible:
        horizon = add_months(start, 12)
        left = _bisect_left(ords, start.toordinal())
        right = _bisect_right(ords, horizon.toordinal())
        path = simulate_path(cands[left:right], start, horizon, size, cap)
        endings.append(path["ending"])
        drawdowns.append(path["max_dd"])
        if path["ruined"]:
            ruins += 1
        reached = path["reached"]
        if reached is not None and reached <= horizon:
            reach12 += 1
            days_to.append((reached - start).days)
            if reached <= add_months(start, 8):
                reach8 += 1
            if reached <= add_months(start, 4):
                reach4 += 1
    count = len(eligible)
    return {
        "starts": count,
        "p_reach_4": reach4 / count,
        "p_reach_8": reach8 / count,
        "p_reach_12": reach12 / count,
        "median_days_to_goal": float(np.median(days_to)) if days_to else None,
        "paths_reaching_12": reach12,
        "p_ruin": ruins / count,
        "median_ending": float(np.median(endings)),
        "p10_ending": float(np.percentile(endings, 10)),
        "median_drawdown": float(np.median(drawdowns)),
        "p10_drawdown": float(np.percentile(drawdowns, 10)),
    }


def _bisect_left(ords: list[int], target: int) -> int:
    lo = 0
    hi = len(ords)
    while lo < hi:
        mid = (lo + hi) // 2
        if ords[mid] < target:
            lo = mid + 1
        else:
            hi = mid
    return lo


def _bisect_right(ords: list[int], target: int) -> int:
    lo = 0
    hi = len(ords)
    while lo < hi:
        mid = (lo + hi) // 2
        if ords[mid] <= target:
            lo = mid + 1
        else:
            hi = mid
    return lo


def pricing_stats(cands: list[tuple]) -> dict:
    if not cands:
        return {"median_ask": None, "mean_ask": None, "cheap_share": None}
    asks = np.asarray([row[6] for row in cands], dtype=float)
    return {
        "median_ask": float(np.median(asks)),
        "mean_ask": float(np.mean(asks)),
        "cheap_share": float(np.mean(asks < 0.50)),
    }


def model_trust(strike: str, median_ask: Optional[float]) -> str:
    cheap = median_ask is not None and median_ask < 0.50
    if strike in WEAK_STRIKES or cheap:
        return "least"
    if strike != "atm":
        return "wide"
    return "ordinary"


def evaluate_window(cands: list[tuple], sessions: list[date], start: date, end: date, size: str, cap: int) -> dict:
    window_sessions = [day for day in sessions if start <= day <= end]
    equity, pnls, skips = daily_equity(cands, window_sessions, size, cap)
    metrics = metrics_from(equity, pnls, STAKE)
    rolling = rolling_stats(cands, window_sessions, end, size, cap)
    return {
        "metrics": metrics,
        "pnls": pnls,
        "skips": skips,
        "rolling": rolling,
        "p_value": p_value(pnls),
        "daily_returns": daily_returns(equity, STAKE),
    }


def survives(metrics: dict, q_value: float, dsr: float) -> bool:
    trades = int(metrics.get("trades") or 0)
    if trades < GATE_TRADES:
        return False
    profit_factor = metrics.get("profit_factor")
    if profit_factor is None:
        pf_ok = float(metrics.get("win_rate") or 0.0) == 1.0 and trades > 0
    else:
        pf_ok = float(profit_factor) >= GATE_PF
    sharpe = float(metrics.get("sharpe") or 0.0)
    drawdown = float(metrics.get("max_drawdown") or 0.0)
    dsr_value = -1.0 if dsr is None or not math.isfinite(float(dsr)) else float(dsr)
    return bool(
        pf_ok
        and sharpe >= GATE_SHARPE
        and drawdown >= GATE_DRAWDOWN
        and q_value <= GATE_Q
        and dsr_value >= GATE_DSR
    )


def assign_q(p_values: list[float]) -> np.ndarray:
    return benjamini_hochberg(p_values)


def prepare_symbol(frame: pd.DataFrame, symbol: str = "QQQ"):
    return prepare(frame, symbol)
