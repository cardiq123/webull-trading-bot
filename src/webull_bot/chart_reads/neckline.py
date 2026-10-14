"""Double-bottom neckline break, frozen before the score.

This module does not place an order and does not import the sandbox
forward test. The catalog in ``catalog`` is the whole false-discovery
family, including the quick-scalp anticipation entry.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, time
from typing import Optional

import numpy as np
import pandas as pd

from webull_bot.calendar import next_trading_day
from webull_bot.chart_reads.atm_exit import deflated_sharpe
from webull_bot.chart_reads.detect import session_bands
from webull_bot.costs import CostModel, buy_fees, buy_price, sell_price, sell_regulatory_fees
from webull_bot.indicators import atr, ema
from webull_bot.mtf_vwap.detect import rth
from webull_bot.options.fees import CONTRACT_MULTIPLIER, option_leg_fees
from webull_bot.options.pricing import listed_strike, option_price

NY = "America/New_York"
FLAT = time(15, 45)
SWING_WIDTH = 2
MIN_SEP_BARS = 6
MAX_SEP_BARS = 30
TOL_PCT = 0.0015
TOL_ATR = 0.5
PRIOR_BARS = 12
PRIOR_ATR = 0.5
STOP_PAD = 0.01
MAX_TRADES_PER_DAY = 3
STAKE = 2_500.0
RISK_FRACTION = 0.01
RATE = 0.02
DIVIDEND = 0.0
HALF_SPREAD_PCT = 0.015
HALF_SPREAD_FLOOR = 0.01
VOL_FLOOR = 0.05
VOL_CAP = 1.50
TRAIN_START = date(2017, 2, 16)
TRAIN_END = date(2023, 12, 31)
HOLDOUT_START = date(2024, 1, 1)
HOLDOUT_END = date(2026, 10, 6)
RANDOM_SEED = 17
GATE_PF = 1.10
GATE_SHARPE = 0.40
GATE_DRAWDOWN = -0.30
GATE_TRADES = 300
GATE_Q = 0.10
GATE_DSR = 0.95
SYMBOLS = ("SPY", "QQQ")
CONFIRMED_FILTERS = ("base", "vwap", "ema200", "macd", "short")
CONFIRMED_EXITS = ("r1", "measured", "vwap2")
SCALP_EXITS = ("neckline", "r2")
KINDS = ("shares", "0dte")
COSTS = CostModel()


@dataclass(frozen=True)
class Cell:
    symbol: str
    family: str
    filter: str
    exit: str
    kind: str

    @property
    def id(self) -> str:
        return f"{self.symbol}_{self.family}_{self.filter}_{self.exit}_{self.kind}"


@dataclass(frozen=True)
class Event:
    symbol: str
    direction: str
    family: str
    signal_i: int
    fill_i: int
    stop: float
    neckline: float
    extreme: float
    second: float
    above_vwap: bool
    above_ema200: bool
    macd_pos: bool


def catalog() -> tuple[Cell, ...]:
    """Every cell in the false-discovery family. Order is fixed."""
    cells: list[Cell] = []
    for symbol in SYMBOLS:
        for name in CONFIRMED_FILTERS:
            for exit_name in CONFIRMED_EXITS:
                for kind in KINDS:
                    cells.append(Cell(symbol, "confirmed", name, exit_name, kind))
        for exit_name in SCALP_EXITS:
            for kind in KINDS:
                cells.append(Cell(symbol, "scalp", "scalp", exit_name, kind))
    return tuple(cells)


def n_trials() -> int:
    return len(catalog())


def frozen_rules() -> dict:
    return {
        "study": "neckline",
        "registered_before_score": True,
        "train": [TRAIN_START.isoformat(), TRAIN_END.isoformat()],
        "holdout": [HOLDOUT_START.isoformat(), HOLDOUT_END.isoformat()],
        "stake": STAKE,
        "risk_fraction": RISK_FRACTION,
        "max_trades_per_day": MAX_TRADES_PER_DAY,
        "flat": "15:45",
        "symbols": list(SYMBOLS),
        "pattern": {
            "swing": f"strict fractal, {SWING_WIDTH} bars on each side, same session, confirmed {SWING_WIDTH} bars later",
            "prior_move": (
                f"the first swing is at least {PRIOR_ATR:g} ATR({14}) beyond the extreme of the "
                f"prior {PRIOR_BARS} bars in that session"
            ),
            "separation": f"{MIN_SEP_BARS} to {MAX_SEP_BARS} bars between the first and the latest swing",
            "tolerance": (
                f"absolute gap at most the larger of {TOL_PCT:.2%} of the higher swing "
                f"and {TOL_ATR:g} ATR known when the latest swing confirms"
            ),
            "multi": "an earlier swing in that window that matches the latest swing stays in the cluster",
            "neckline_long": "highest high strictly between the first and the latest swing low",
            "neckline_short": "lowest low strictly between the first and the latest swing high",
            "invalid": "a close through the cluster extreme kills the structure",
        },
        "confirmed": (
            "long close strictly above the neckline, the 9 EMA, and the 20 EMA; "
            "short is the mirror; fill is the next bar's open"
        ),
        "filters": {
            "base": "the confirmed close only",
            "vwap": "confirmed long and close above session VWAP",
            "ema200": "confirmed long and close above the 200 EMA",
            "macd": "confirmed long and MACD histogram (12, 26, 9) above zero",
            "short": "confirmed double-top mirror, close under the neckline and both EMAs",
        },
        "scalp": (
            "long only, same double bottom, before any close above the neckline; "
            "a down-close bar after an earlier bar closed above the 9 EMA; "
            "the red bar's low holds above the latest swing low and its close holds above "
            "the lower of the 9 and 20 EMA; fill is the next open; "
            "stop is one cent under that red bar's low"
        ),
        "random": (
            "seed 17, same count of bars, same direction; stop is one cent beyond that bar; "
            "the exit is the cell exit when it does not need a neckline (r1, r2, vwap2); "
            "neckline and measured-move targets fall back to 1R because a random bar has no neckline"
        ),
        "exits": {
            "r1": "stop one cent beyond the latest swing, target one R, stop wins a tie",
            "measured": "same stop, target is the neckline plus the depth from the cluster extreme",
            "vwap2": "same stop, take-profit at the prior bar's session VWAP outer 2 SD band",
            "neckline": "scalp target is the neckline",
            "r2": "scalp target is two R",
            "flat": "15:45 open",
        },
        "options": "one ATM 0 DTE contract, prior VIX1D else VIX, rate 2 percent, dividend 0",
        "gate": {
            "profit_factor": GATE_PF,
            "sharpe": GATE_SHARPE,
            "max_drawdown": GATE_DRAWDOWN,
            "holdout_trades": GATE_TRADES,
            "q": GATE_Q,
            "dsr": GATE_DSR,
            "ending_above_start": True,
            "train_sharpe_above_random": True,
        },
        "random_seed": RANDOM_SEED,
        "n_trials": n_trials(),
        "cells": [cell.id for cell in catalog()],
    }


def assert_window_visible(end: date, *, allow_holdout: bool) -> None:
    if not allow_holdout and end >= HOLDOUT_START:
        raise RuntimeError("holdout is closed")


def benjamini_hochberg(p_values: list[float]) -> np.ndarray:
    p = np.asarray(p_values, dtype=float)
    n = len(p)
    q = np.ones(n, dtype=float)
    if n == 0:
        return q
    order = np.argsort(p, kind="mergesort")
    ranked = p[order]
    adjusted = np.empty(n, dtype=float)
    running = 1.0
    for i in range(n - 1, -1, -1):
        running = min(running, float(ranked[i]) * n / (i + 1))
        adjusted[i] = running
    q[order] = np.clip(adjusted, 0.0, 1.0)
    return q


def _years(when: pd.Timestamp) -> float:
    clock = pd.Timestamp(when)
    if clock.tzinfo is not None:
        clock = clock.tz_convert(NY)
    expiry = clock.normalize() + pd.Timedelta(hours=16)
    minutes = max(1.0, (expiry - clock).total_seconds() / 60.0)
    return minutes / (365.0 * 24.0 * 60.0)


def _half_spread(mid: float) -> float:
    return max(HALF_SPREAD_FLOOR, HALF_SPREAD_PCT * max(mid, 0.0))


def _iv_on(day: date, iv_points: dict) -> Optional[float]:
    point = iv_points.get(day)
    if not point:
        return None
    try:
        raw = float(point[0])
    except (TypeError, ValueError, IndexError):
        return None
    if not math.isfinite(raw) or raw <= 0:
        return None
    return min(VOL_CAP, max(VOL_FLOOR, raw / 100.0))


def _macd_hist(close: pd.Series) -> pd.Series:
    macd = ema(close, 12) - ema(close, 26)
    signal = ema(macd, 9)
    return macd - signal


def _swings(values: np.ndarray, dates: np.ndarray, higher: bool) -> np.ndarray:
    n = len(values)
    out = np.zeros(n, dtype=bool)
    width = SWING_WIDTH
    if n < width * 2 + 1:
        return out
    ok = np.ones(n - 2 * width, dtype=bool)
    mid = values[width:-width]
    mid_day = dates[width:-width]
    for step in range(1, width + 1):
        left = values[width - step : n - width - step]
        right = values[width + step : n - width + step]
        if higher:
            ok &= (mid > left) & (mid > right)
        else:
            ok &= (mid < left) & (mid < right)
        ok &= mid_day == dates[width - step : n - width - step]
        ok &= mid_day == dates[width + step : n - width + step]
    out[width:-width] = ok
    return out


class Prepared:
    def __init__(self, frame: pd.DataFrame, symbol: str) -> None:
        bars = rth(frame)
        self.symbol = symbol
        self.index = bars.index
        self.open = bars["open"].to_numpy(dtype=float)
        self.high = bars["high"].to_numpy(dtype=float)
        self.low = bars["low"].to_numpy(dtype=float)
        self.close = bars["close"].to_numpy(dtype=float)
        close = bars["close"].astype(float)
        self.ema9 = ema(close, 9).to_numpy(dtype=float)
        self.ema20 = ema(close, 20).to_numpy(dtype=float)
        self.ema200 = ema(close, 200).to_numpy(dtype=float)
        self.hist = _macd_hist(close).to_numpy(dtype=float)
        self.atr = atr(bars, 14).to_numpy(dtype=float)
        bands = session_bands(bars, deviations=2.0).reindex(bars.index)
        self.vwap = bands["vwap"].to_numpy(dtype=float)
        self.upper = bands["upper"].to_numpy(dtype=float)
        self.lower = bands["lower"].to_numpy(dtype=float)
        self.dates = np.array([ts.date() for ts in bars.index])
        self.clocks = np.array([ts.time() for ts in bars.index])
        self.swing_low = _swings(self.low, self.dates, higher=False)
        self.swing_high = _swings(self.high, self.dates, higher=True)
        self.events = _events(self)


def prepare(frame: pd.DataFrame, symbol: str) -> Prepared:
    return Prepared(frame, symbol)


def _finite(value: float) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def _events(book: Prepared) -> list[Event]:
    found: list[Event] = []
    n = len(book.close)
    if n == 0:
        return found
    cuts = np.flatnonzero(book.dates[1:] != book.dates[:-1]) + 1
    starts = np.r_[0, cuts]
    ends = np.r_[cuts, n]
    for start, end in zip(starts, ends):
        found.extend(_session_events(book, int(start), int(end)))
    return found


def _tolerance(price_a: float, price_b: float, width: float) -> float:
    return max(TOL_PCT * max(price_a, price_b), TOL_ATR * width)


def _session_events(book: Prepared, start: int, end: int) -> list[Event]:
    lows = [i for i in range(start, end) if book.swing_low[i]]
    highs = [i for i in range(start, end) if book.swing_high[i]]
    found: list[Event] = []
    found.extend(_side_events(book, start, end, lows, long=True))
    found.extend(_side_events(book, start, end, highs, long=False))
    return found


def _side_events(
    book: Prepared,
    start: int,
    end: int,
    swings: list[int],
    long: bool,
    probe_i: Optional[int] = None,
    probe: Optional[dict] = None,
) -> list[Event]:
    """One active cluster at a time. A newer confirmed swing replaces it."""
    events: list[Event] = []
    active: Optional[dict] = None
    swing_at = {index + SWING_WIDTH: index for index in swings}
    for i in range(start, end):
        try:
            born = swing_at.get(i)
            if born is not None:
                cluster = _cluster(book, swings, born, long)
                if cluster is not None:
                    active = cluster
            if active is None or i < active["confirm"]:
                continue
            if long and book.close[i] < active["extreme"]:
                active = None
                continue
            if (not long) and book.close[i] > active["extreme"]:
                active = None
                continue
            if long and _finite(book.close[i]) and book.close[i] > active["neckline"]:
                active["neckline_closed"] = True
            if long and not active["scalp_done"] and not active["neckline_closed"]:
                if book.close[i] > book.ema9[i] and _finite(book.ema9[i]):
                    active["reclaimed"] = True
                if _scalp_bar(book, i, active):
                    event = _make_event(book, i, active, "scalp", "long")
                    if event is not None:
                        events.append(event)
                        active["scalp_done"] = True
            if active is None:
                continue
            if _confirmed_bar(book, i, active, long):
                event = _make_event(book, i, active, "confirmed", "long" if long else "short")
                if event is not None:
                    events.append(event)
                active = None
        finally:
            if probe is not None and i == probe_i:
                probe["active"] = None if active is None else {
                    "neckline": float(active["neckline"]),
                    "extreme": float(active["extreme"]),
                    "second": float(active["second"]),
                    "second_i": int(active["second_i"]),
                    "confirm": int(active["confirm"]),
                    "reclaimed": bool(active["reclaimed"]),
                    "scalp_done": bool(active["scalp_done"]),
                    "neckline_closed": bool(active["neckline_closed"]),
                }
    return events


def inspect_long(book: Prepared, when: pd.Timestamp) -> dict:
    """Long double-bottom state at the close of ``when``. Used for the chart read, not the score."""
    stamp = pd.Timestamp(when)
    if stamp.tzinfo is None:
        stamp = stamp.tz_localize(NY)
    else:
        stamp = stamp.tz_convert(NY)
    loc = book.index.get_loc(stamp)
    if isinstance(loc, slice):
        raise KeyError(str(stamp))
    index = int(loc)
    day = book.dates[index]
    start = index
    while start > 0 and book.dates[start - 1] == day:
        start -= 1
    end = index + 1
    while end < len(book.close) and book.dates[end] == day:
        end += 1
    lows = [i for i in range(start, end) if book.swing_low[i] and i + SWING_WIDTH <= index]
    probe: dict = {}
    _side_events(book, start, end, lows, True, probe_i=index, probe=probe)
    return {
        "time": book.index[index],
        "close": float(book.close[index]),
        "open": float(book.open[index]),
        "high": float(book.high[index]),
        "low": float(book.low[index]),
        "ema9": float(book.ema9[index]),
        "ema20": float(book.ema20[index]),
        "ema200": float(book.ema200[index]),
        "vwap": float(book.vwap[index]),
        "hist": float(book.hist[index]),
        "active": probe.get("active"),
        "swing_lows": [
            {"time": book.index[i], "low": float(book.low[i])}
            for i in range(start, index + 1)
            if book.swing_low[i]
        ],
    }


def _cluster(book: Prepared, swings: list[int], latest: int, long: bool) -> Optional[dict]:
    prices = book.low if long else book.high
    confirm = latest + SWING_WIDTH
    if confirm >= len(book.close):
        return None
    width = float(book.atr[confirm])
    if not _finite(width) or width <= 0:
        return None
    latest_px = float(prices[latest])
    matched: list[int] = []
    for earlier in swings:
        if earlier >= latest:
            break
        gap = latest - earlier
        if gap < MIN_SEP_BARS or gap > MAX_SEP_BARS:
            continue
        earlier_px = float(prices[earlier])
        if abs(latest_px - earlier_px) > _tolerance(latest_px, earlier_px, width):
            continue
        if not _prior_move(book, earlier, long):
            continue
        matched.append(earlier)
    if not matched:
        return None
    first = matched[0]
    between = slice(first + 1, latest)
    if long:
        neckline = float(np.max(book.high[between])) if latest > first + 1 else float("nan")
        extreme = float(np.min(prices[matched + [latest]]))
    else:
        neckline = float(np.min(book.low[between])) if latest > first + 1 else float("nan")
        extreme = float(np.max(prices[matched + [latest]]))
    if not _finite(neckline):
        return None
    return {
        "confirm": confirm,
        "neckline": neckline,
        "extreme": extreme,
        "second": latest_px,
        "second_i": latest,
        "reclaimed": False,
        "scalp_done": False,
        "neckline_closed": False,
    }


def _prior_move(book: Prepared, index: int, long: bool) -> bool:
    if index - PRIOR_BARS < 0 or book.dates[index - PRIOR_BARS] != book.dates[index]:
        return False
    confirm = index + SWING_WIDTH
    if confirm >= len(book.close) or book.dates[confirm] != book.dates[index]:
        return False
    width = float(book.atr[confirm])
    if not _finite(width) or width <= 0:
        return False
    window = slice(index - PRIOR_BARS, index)
    if long:
        peak = float(np.max(book.high[window]))
        return peak - float(book.low[index]) >= PRIOR_ATR * width
    trough = float(np.min(book.low[window]))
    return float(book.high[index]) - trough >= PRIOR_ATR * width


def _scalp_bar(book: Prepared, index: int, active: dict) -> bool:
    """Red pullback after a 9 EMA reclaim, still under the neckline."""
    if not active["reclaimed"] or active["neckline_closed"]:
        return False
    opened = float(book.open[index])
    closed = float(book.close[index])
    low = float(book.low[index])
    ema_low = min(float(book.ema9[index]), float(book.ema20[index]))
    if not all(_finite(value) for value in (opened, closed, low, ema_low, book.ema9[index], book.ema20[index])):
        return False
    prior = False
    second_i = int(active["second_i"])
    for j in range(second_i + 1, index):
        if _finite(book.ema9[j]) and book.close[j] > book.ema9[j]:
            prior = True
            break
    if not prior:
        return False
    return (
        closed < opened
        and closed <= active["neckline"]
        and low > active["second"]
        and closed > active["second"]
        and closed > ema_low
    )


def _confirmed_bar(book: Prepared, index: int, active: dict, long: bool) -> bool:
    closed = float(book.close[index])
    ema9 = float(book.ema9[index])
    ema20 = float(book.ema20[index])
    if not all(_finite(value) for value in (closed, ema9, ema20)):
        return False
    if long:
        return closed > active["neckline"] and closed > ema9 and closed > ema20
    return closed < active["neckline"] and closed < ema9 and closed < ema20


def _make_event(book: Prepared, index: int, active: dict, family: str, direction: str) -> Optional[Event]:
    fill_i = index + 1
    if fill_i >= len(book.close) or book.dates[fill_i] != book.dates[index]:
        return None
    if book.clocks[fill_i] >= FLAT:
        return None
    if family == "scalp":
        stop = float(book.low[index]) - STOP_PAD
    elif direction == "long":
        stop = float(active["second"]) - STOP_PAD
    else:
        stop = float(active["second"]) + STOP_PAD
    if not _finite(stop) or stop <= 0:
        return None
    vwap = float(book.vwap[index])
    ema200 = float(book.ema200[index])
    hist = float(book.hist[index])
    closed = float(book.close[index])
    return Event(
        symbol=book.symbol,
        direction=direction,
        family=family,
        signal_i=index,
        fill_i=fill_i,
        stop=stop,
        neckline=float(active["neckline"]),
        extreme=float(active["extreme"]),
        second=float(active["second"]),
        above_vwap=bool(_finite(vwap) and closed > vwap),
        above_ema200=bool(_finite(ema200) and closed > ema200),
        macd_pos=bool(_finite(hist) and hist > 0),
    )


def select_events(events: list[Event], cell: Cell) -> list[Event]:
    chosen: list[Event] = []
    for event in events:
        if event.symbol != cell.symbol:
            continue
        if cell.family == "scalp":
            if event.family == "scalp" and event.direction == "long":
                chosen.append(event)
            continue
        if event.family != "confirmed":
            continue
        if cell.filter == "short":
            if event.direction == "short":
                chosen.append(event)
            continue
        if event.direction != "long":
            continue
        if cell.filter == "base":
            chosen.append(event)
        elif cell.filter == "vwap" and event.above_vwap:
            chosen.append(event)
        elif cell.filter == "ema200" and event.above_ema200:
            chosen.append(event)
        elif cell.filter == "macd" and event.macd_pos:
            chosen.append(event)
    return chosen


def _planned_target(book: Prepared, event: Event, fill: float, exit_name: str) -> Optional[float]:
    risk = (fill - event.stop) if event.direction == "long" else (event.stop - fill)
    if not _finite(risk) or risk <= 0 or not _finite(fill):
        return None
    if exit_name == "r1":
        return fill + risk if event.direction == "long" else fill - risk
    if exit_name == "r2":
        return fill + 2.0 * risk if event.direction == "long" else fill - 2.0 * risk
    if exit_name == "neckline":
        return event.neckline
    if exit_name == "measured":
        if event.direction == "long":
            depth = event.neckline - event.extreme
            if depth <= 0:
                return None
            return event.neckline + depth
        depth = event.extreme - event.neckline
        if depth <= 0:
            return None
        return event.neckline - depth
    if exit_name == "vwap2":
        band = book.upper[event.signal_i] if event.direction == "long" else book.lower[event.signal_i]
        return float(band) if _finite(band) else None
    return None


def _target_ok(direction: str, fill: float, target: Optional[float], exit_name: str) -> bool:
    if exit_name == "vwap2":
        return True
    if target is None or not _finite(target):
        return False
    if direction == "long":
        return target > fill
    return target < fill


def _walk(book: Prepared, fill_i: int, direction: str, stop: float, target: Optional[float], exit_name: str):
    n = len(book.close)
    for i in range(fill_i, n):
        if book.dates[i] != book.dates[fill_i]:
            break
        if book.clocks[i] >= FLAT:
            return "flat", float(book.open[i]), book.index[i]
        opened = float(book.open[i])
        high = float(book.high[i])
        low = float(book.low[i])
        level = target
        if exit_name == "vwap2" and i > 0:
            level = float(book.upper[i - 1] if direction == "long" else book.lower[i - 1])
            if not _finite(level):
                level = None
        if direction == "long":
            if opened <= stop:
                return "stop", opened, book.index[i]
            if level is not None and _finite(level) and opened >= level:
                return "target", opened, book.index[i]
            hit_stop = low <= stop
            hit_target = level is not None and _finite(level) and high >= level
            if hit_stop:
                return "stop", stop, book.index[i]
            if hit_target:
                return "target", float(level), book.index[i]
        else:
            if opened >= stop:
                return "stop", opened, book.index[i]
            if level is not None and _finite(level) and opened <= level:
                return "target", opened, book.index[i]
            hit_stop = high >= stop
            hit_target = level is not None and _finite(level) and low <= level
            if hit_stop:
                return "stop", stop, book.index[i]
            if hit_target:
                return "target", float(level), book.index[i]
    last = n - 1
    return "flat", float(book.close[last]), book.index[last]


def _option_debit(direction: str, spot: float, when, iv: float) -> Optional[tuple[float, float, float]]:
    right = "call" if direction == "long" else "put"
    strike = listed_strike(spot, spot)
    mid = float(option_price(right, spot, strike, _years(when), iv, RATE, DIVIDEND))
    if not _finite(mid) or mid <= 0:
        return None
    ask = mid + _half_spread(mid)
    debit = ask * CONTRACT_MULTIPLIER + option_leg_fees(1, ask, sell=False)
    return debit, ask, strike


def _option_credit(direction: str, spot: float, strike: float, when, iv: float) -> float:
    right = "call" if direction == "long" else "put"
    mid = float(option_price(right, spot, strike, _years(when), iv, RATE, DIVIDEND))
    if not _finite(mid) or mid < 0:
        mid = 0.0
    bid = max(0.0, mid - _half_spread(mid))
    return bid * CONTRACT_MULTIPLIER - option_leg_fees(1, bid, sell=True)


def simulate(
    book: Prepared,
    events: list[Event],
    *,
    exit_name: str,
    kind: str,
    stake: float,
    iv_points: dict,
    start: date,
    end: date,
    allow_holdout: bool,
) -> dict:
    assert_window_visible(end, allow_holdout=allow_holdout)
    chosen = [
        event
        for event in events
        if start <= book.dates[event.fill_i] <= end
    ]
    chosen.sort(key=lambda event: event.fill_i)
    by_day: dict[date, list[Event]] = {}
    for event in chosen:
        by_day.setdefault(book.dates[event.fill_i], []).append(event)
    days = [day for day in pd.unique(book.dates) if start <= day <= end]
    settled = float(stake)
    pending: list[tuple[date, float]] = []
    equity_points: list[tuple[pd.Timestamp, float]] = []
    trades: list[dict] = []
    pnls: list[float] = []
    planned: list[float] = []
    skips = {"overlap": 0, "cap": 0, "iv": 0, "premium": 0, "dust": 0, "through": 0, "target": 0, "shares": 0}
    for day in days:
        still = []
        for due, amount in pending:
            if due <= day:
                settled += amount
            else:
                still.append((due, amount))
        pending = still
        day_equity = settled + sum(amount for _due, amount in pending)
        taken = 0
        busy_until = -1
        for event in by_day.get(day, []):
            if taken >= MAX_TRADES_PER_DAY:
                skips["cap"] += 1
                continue
            if event.fill_i <= busy_until:
                skips["overlap"] += 1
                continue
            outcome = _take(book, event, exit_name, kind, settled, day_equity, iv_points, skips)
            if outcome is None:
                continue
            taken += 1
            busy_until = outcome["exit_i"]
            settled -= outcome["cash_out"]
            pending.append((next_trading_day(day), outcome["cash_back"]))
            pnls.append(outcome["pnl"])
            if _finite(outcome["planned_rr"]):
                planned.append(float(outcome["planned_rr"]))
            trades.append(outcome)
        equity_points.append((pd.Timestamp(day), settled + sum(amount for _due, amount in pending)))
    equity = pd.Series(
        [point[1] for point in equity_points],
        index=pd.DatetimeIndex([point[0] for point in equity_points]),
        dtype=float,
    )
    metrics = _metrics(equity, pnls, stake)
    metrics["planned_rr"] = float(np.mean(planned)) if planned else None
    metrics["trades_per_day"] = (len(trades) / len(days)) if days else 0.0
    return {"metrics": metrics, "pnls": pnls, "equity": equity, "skips": skips, "trades": trades}


def _take(book, event, exit_name, kind, settled, day_equity, iv_points, skips):
    fill = float(book.open[event.fill_i])
    if not _finite(fill) or fill <= 0:
        skips["dust"] += 1
        return None
    if event.direction == "long" and fill <= event.stop:
        skips["through"] += 1
        return None
    if event.direction == "short" and fill >= event.stop:
        skips["through"] += 1
        return None
    target = _planned_target(book, event, fill, exit_name)
    if not _target_ok(event.direction, fill, target, exit_name):
        skips["target"] += 1
        return None
    risk = abs(fill - event.stop)
    planned_rr = None
    if risk > 0 and target is not None and _finite(target):
        planned_rr = abs(target - fill) / risk
    reason, exit_raw, when = _walk(book, event.fill_i, event.direction, event.stop, target, exit_name)
    exit_i = int(book.index.get_loc(when))
    iv = _iv_on(book.dates[event.fill_i], iv_points)
    if kind == "0dte":
        if iv is None:
            skips["iv"] += 1
            return None
        priced = _option_debit(event.direction, fill, book.index[event.fill_i], iv)
        if priced is None:
            skips["premium"] += 1
            return None
        debit, _ask, strike = priced
        if debit > settled + 1e-9:
            skips["premium"] += 1
            return None
        credit = _option_credit(event.direction, float(exit_raw), strike, when, iv)
        pnl = credit - debit
        return {
            "pnl": pnl,
            "cash_out": debit,
            "cash_back": credit,
            "planned_rr": planned_rr,
            "exit_i": exit_i,
            "reason": reason,
            "entry": fill,
            "exit": float(exit_raw),
            "stop": event.stop,
            "target": target,
            "signal_time": book.index[event.signal_i],
            "fill_time": book.index[event.fill_i],
            "exit_time": when,
        }
    quantity = _share_qty(event.direction, fill, event.stop, settled, day_equity)
    if quantity < 1:
        skips["shares"] += 1
        return None
    if event.direction == "long":
        entry_px = buy_price(fill, COSTS)
        exit_px = sell_price(float(exit_raw), COSTS)
        debit = entry_px * quantity + buy_fees(COSTS)
        credit = exit_px * quantity - sell_regulatory_fees(exit_px, quantity, COSTS)
        if debit > settled + 1e-9:
            skips["shares"] += 1
            return None
        pnl = credit - debit
        return {
            "pnl": pnl,
            "cash_out": debit,
            "cash_back": credit,
            "planned_rr": planned_rr,
            "exit_i": exit_i,
            "reason": reason,
            "entry": fill,
            "exit": float(exit_raw),
            "stop": event.stop,
            "target": target,
            "signal_time": book.index[event.signal_i],
            "fill_time": book.index[event.fill_i],
            "exit_time": when,
            "quantity": quantity,
        }
    entry_px = sell_price(fill, COSTS)
    exit_px = buy_price(float(exit_raw), COSTS)
    notional = entry_px * quantity
    fees_open = sell_regulatory_fees(entry_px, quantity, COSTS)
    fees_close = buy_fees(COSTS)
    if notional + fees_open > settled + 1e-9:
        skips["shares"] += 1
        return None
    pnl = (entry_px - exit_px) * quantity - fees_open - fees_close
    return {
        "pnl": pnl,
        "cash_out": notional + fees_open,
        "cash_back": notional + fees_open + pnl,
        "planned_rr": planned_rr,
        "exit_i": exit_i,
        "reason": reason,
        "entry": fill,
        "exit": float(exit_raw),
        "stop": event.stop,
        "target": target,
        "signal_time": book.index[event.signal_i],
        "fill_time": book.index[event.fill_i],
        "exit_time": when,
        "quantity": quantity,
    }


def _share_qty(direction: str, fill: float, stop: float, settled: float, day_equity: float) -> int:
    distance = abs(fill - stop)
    if distance <= 0 or day_equity <= 0 or settled <= 0:
        return 0
    budget = RISK_FRACTION * day_equity
    raw_qty = int(budget / (distance * (1.0 + COSTS.friction_bps / 10_000.0)))
    if direction == "long":
        entry_px = buy_price(fill, COSTS)
    else:
        entry_px = sell_price(fill, COSTS)
    if entry_px <= 0:
        return 0
    cash_qty = int(settled / entry_px)
    return max(0, min(raw_qty, cash_qty))


def _metrics(equity: pd.Series, pnls: list[float], starting: float) -> dict:
    from webull_bot.chart_reads.vwap_band import metrics_from

    if equity is None or len(equity) == 0:
        equity = pd.Series([starting], index=pd.DatetimeIndex([pd.Timestamp(TRAIN_START)]))
    return metrics_from(equity, pnls, starting)


def p_value(pnls: list[float]) -> float:
    if len(pnls) < 30:
        return 1.0
    values = np.asarray(pnls, dtype=float)
    mean = float(values.mean())
    std = float(values.std(ddof=1))
    if std <= 0:
        return 0.0 if mean > 0 else 1.0
    stat = mean / (std / math.sqrt(len(values)))
    return float(1.0 - 0.5 * (1.0 + math.erf(stat / math.sqrt(2.0))))


def passes_gate(holdout: dict, train: dict, random_train: dict, q_value: float, dsr: float) -> bool:
    metrics = holdout["metrics"]
    trades = int(metrics.get("trades") or 0)
    sharpe = float(metrics.get("sharpe") or 0.0)
    drawdown = float(metrics.get("max_drawdown") or 0.0)
    ending = float(metrics.get("ending_equity") or 0.0)
    profit_factor = metrics.get("profit_factor")
    if profit_factor is None:
        pf_ok = trades > 0 and float(metrics.get("win_rate") or 0.0) == 1.0
    else:
        pf_ok = float(profit_factor) >= GATE_PF
    train_sharpe = float(train["metrics"].get("sharpe") or 0.0)
    random_sharpe = float(random_train["metrics"].get("sharpe") or 0.0)
    return bool(
        trades >= GATE_TRADES
        and pf_ok
        and sharpe >= GATE_SHARPE
        and drawdown >= GATE_DRAWDOWN
        and ending > STAKE
        and train_sharpe > random_sharpe
        and q_value <= GATE_Q
        and dsr >= GATE_DSR
    )


def random_exit(exit_name: str) -> str:
    """A random bar has no neckline, so those targets are scored as 1R."""
    if exit_name in ("r1", "r2", "vwap2"):
        return exit_name
    return "r1"


def random_events(book: Prepared, count: int, direction: str, start: date, end: date, seed: int = RANDOM_SEED) -> list[Event]:
    """Same count of entries, same direction, seed 17. The stop is one cent beyond that bar."""
    if count <= 0:
        return []
    eligible = []
    n = len(book.close)
    for i in range(n - 1):
        day = book.dates[i]
        if day < start or day > end or book.dates[i + 1] != day:
            continue
        if book.clocks[i + 1] >= FLAT:
            continue
        if not _finite(book.atr[i]) or book.atr[i] <= 0:
            continue
        eligible.append(i)
    if not eligible:
        return []
    rng = np.random.default_rng(seed)
    take = min(count, len(eligible))
    picked = rng.choice(np.asarray(eligible, dtype=int), size=take, replace=False)
    events = []
    for index in sorted(int(i) for i in picked):
        if direction == "long":
            stop = float(book.low[index]) - STOP_PAD
        else:
            stop = float(book.high[index]) + STOP_PAD
        events.append(
            Event(
                symbol=book.symbol,
                direction=direction,
                family="random",
                signal_i=index,
                fill_i=index + 1,
                stop=stop,
                neckline=float("nan"),
                extreme=float("nan"),
                second=float(book.low[index] if direction == "long" else book.high[index]),
                above_vwap=False,
                above_ema200=False,
                macd_pos=False,
            )
        )
    return events


def daily_returns(equity: pd.Series, starting: float) -> np.ndarray:
    if equity is None or len(equity) == 0:
        return np.array([])
    curve = pd.concat(
        [pd.Series([starting], index=[equity.index[0] - pd.Timedelta(days=1)]), equity.astype(float)]
    )
    returns = curve.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    return returns.to_numpy(dtype=float)


def public_metrics(metrics: dict) -> dict:
    keep = (
        "starting_equity",
        "ending_equity",
        "sharpe",
        "max_drawdown",
        "trades",
        "win_rate",
        "profit_factor",
        "expectancy",
        "planned_rr",
        "trades_per_day",
    )
    return {key: metrics.get(key) for key in keep}
