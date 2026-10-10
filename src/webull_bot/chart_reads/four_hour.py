"""Session-aligned 4-hour trend, then a 15-minute pullback and a 5-minute entry.

The bars are the cash session, not a rolling 240-minute window. Each regular
session can complete two blocks: 9:30-13:30 and 13:30-16:00. The afternoon
block is two and a half hours and still counts as one bar. A block exists
only when its first and its last 5-minute bars both printed. Nothing in this
module places an order.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, time
from typing import Optional

import numpy as np
import pandas as pd

from webull_bot.calendar import next_trading_day
from webull_bot.chart_reads.detect import session_bands
from webull_bot.costs import CostModel, buy_fees, buy_price, sell_price, sell_regulatory_fees
from webull_bot.indicators import atr, ema
from webull_bot.mtf_vwap.detect import rth

NY = "America/New_York"
FLAT = time(15, 45)
FLAT_MINUTE = 15 * 60 + 45
OPEN_MINUTE = 9 * 60 + 30
MORNING_LAST = 13 * 60 + 25
AFTERNOON_START = 13 * 60 + 30
AFTERNOON_LAST = 15 * 60 + 55
HOUR_EDGES = (
    (9 * 60 + 30, 10 * 60 + 25),
    (10 * 60 + 30, 11 * 60 + 25),
    (11 * 60 + 30, 12 * 60 + 25),
    (12 * 60 + 30, 13 * 60 + 25),
    (13 * 60 + 30, 14 * 60 + 25),
    (14 * 60 + 30, 15 * 60 + 25),
)
STOP_PAD = 0.01
TOUCH_ATR = 0.1
MAX_TRADES_PER_DAY = 5
STAKE = 2_500.0
RISK_FRACTION = 0.01
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
MAG7 = ("AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA")
DIRECTIONS = ("ema", "structure")
PULLBACKS = ("ema20", "vwap")
EXITS = ("r1", "r2", "vwap2")
KINDS = ("shares", "1dte", "0dte")
REFERENCE_DIRECTION = "ema"
REFERENCE_PULLBACK = "ema20"
REFERENCE_EXIT = "r1"
COMPOUND_FRACTION = 0.05
COMPOUND_CAP = 30
COSTS = CostModel()


@dataclass(frozen=True)
class Cell:
    symbol: str
    direction_mode: str
    pullback: str
    exit: str
    kind: str

    @property
    def id(self) -> str:
        return f"{self.symbol}_{self.direction_mode}_{self.pullback}_{self.exit}_{self.kind}"


@dataclass(frozen=True)
class Event:
    symbol: str
    direction: str
    direction_mode: str
    pullback: str
    signal_i: int
    fill_i: int
    stop: float


class Book:
    def __init__(self, frame: pd.DataFrame, symbol: str) -> None:
        bars = rth(frame)
        bars = bars[~bars.index.duplicated(keep="last")].sort_index()
        self.symbol = symbol
        self.index = bars.index
        self.open = bars["open"].to_numpy(dtype=float)
        self.high = bars["high"].to_numpy(dtype=float)
        self.low = bars["low"].to_numpy(dtype=float)
        self.close = bars["close"].to_numpy(dtype=float)
        self.minute = (bars.index.hour * 60 + bars.index.minute).to_numpy(dtype=int)
        self.dates = np.asarray(bars.index.date, dtype=object)
        close = bars["close"].astype(float)
        self.ema9 = ema(close, 9).to_numpy(dtype=float)
        bands = session_bands(bars, deviations=2.0)
        self.vwap = bands["vwap"].to_numpy(dtype=float)
        self.upper = bands["upper"].to_numpy(dtype=float)
        self.lower = bands["lower"].to_numpy(dtype=float)
        n = len(bars)
        self.h4_ema = np.zeros(n, dtype=int)
        self.h4_structure = np.zeros(n, dtype=int)
        self.h1_agree = np.zeros(n, dtype=int)
        self.h1_ema20 = np.full(n, np.nan)
        self.m15_done = np.zeros(n, dtype=bool)
        self.m15_first = np.full(n, -1, dtype=int)
        self.m15_low = np.full(n, np.nan)
        self.m15_high = np.full(n, np.nan)
        self.m15_close = np.full(n, np.nan)
        self.m15_ema20 = np.full(n, np.nan)
        self.m15_atr = np.full(n, np.nan)
        self.m15_vwap = np.full(n, np.nan)
        self.sessions = 0
        self.h4_bars = 0
        self.h1_bars = 0
        if n:
            _map_higher(self, bars)


def catalog() -> tuple[Cell, ...]:
    cells = []
    for symbol in SYMBOLS:
        for direction_mode in DIRECTIONS:
            for pullback in PULLBACKS:
                for exit_name in EXITS:
                    for kind in KINDS:
                        cells.append(Cell(symbol, direction_mode, pullback, exit_name, kind))
    return tuple(cells)


def n_trials() -> int:
    return len(catalog())


def frozen_rules() -> dict:
    cells = [cell.id for cell in catalog()]
    return {
        "study": "4hr",
        "registered_before_score": True,
        "bars": {
            "source": "completed 5-minute regular-hours bars",
            "four_hour": (
                "session-aligned, not a rolling 240-minute window. "
                "Morning is 9:30-13:30 and afternoon is 13:30-16:00. "
                "The afternoon block is 2.5 hours and counts as one bar. "
                "A block is complete only when its first and last 5-minute bars both exist."
            ),
            "one_hour": (
                "session-aligned 60-minute blocks from 9:30. "
                "The 15:30-16:00 stub is not an EMA bar."
            ),
            "fifteen": "session-aligned 15-minute blocks, including 15:45-16:00 when its last bar exists",
            "entry_clock": "5-minute bars. A higher bar is known on the 5-minute bar that completes it.",
        },
        "direction_ema": "long if the last completed 4h close is above its 20 EMA and that EMA is rising. Short is the mirror.",
        "direction_structure": (
            "long if the last completed 4h bar has a higher high, a higher low, "
            "and a close above the prior 4h high. Short is the mirror. One variant, both conditions."
        ),
        "one_hour": "long if the last completed 1h close is above its 20 EMA and the 9 EMA is above the 20 EMA. Short is the mirror.",
        "pullback": (
            "a completed 15-minute bar whose range overlaps the band 0.1 ATR(14) around "
            "the 15-minute 20 EMA, or around session VWAP. Those are two cells, not a mix. "
            "A 15-minute close through the last completed 1-hour 20 EMA cancels the pullback."
        ),
        "entry": (
            "the first later 5-minute bar that closes in the trend direction through the 5-minute 9 EMA. "
            "Longs need a bullish close, close above the open. Shorts need a bearish close. "
            "The fill is the next 5-minute open. The stop is one cent beyond the pullback extreme, "
            "measured from the first 5-minute bar of the pullback through the signal bar."
        ),
        "exits": {
            "r1": "one R, and the stop wins when both trade on the same bar",
            "r2": "two R, same stop rule",
            "vwap2": "the prior bar's outer session-VWAP 2 SD band",
            "flat": "15:45 open, same session",
        },
        "daily_cap": MAX_TRADES_PER_DAY,
        "daily_cap_note": "One cap, 5 new trades a day, which is the top of the 3-to-5 range. 3 is not a second cell.",
        "stake": STAKE,
        "share_risk": RISK_FRACTION,
        "options": {
            "1dte": "one ATM contract, unscaled prior VIX1D close else prior VIX, 1 cent market, next-session expiry, same-day 15:45 sale",
            "0dte": "one ATM contract, 1.67x that prior close (the unrounded calibration ratio), 1 cent market, same-day expiry",
        },
        "compound": (
            "Scored once, on the best option cell, and not counted in the false-discovery family. "
            "contracts = floor(0.05 * equity / (ask * 100)), cap 30. "
            "If that rounds to 0, buy 1 when one contract costs at most 10% of equity. "
            "Size slippage is the extra cent per ten contracts past the first ten used in the compound study."
        ),
        "best_cell": (
            "Among option cells that pass the gate, the highest holdout Sharpe, then profit factor, "
            "then trade count, then the cell id. If none pass, the option cell with at least 300 holdout "
            "trades and the highest holdout Sharpe. If none have 300, the option cell with the most holdout trades."
        ),
        "reference": {
            "symbols": list(MAG7),
            "cell": f"{REFERENCE_DIRECTION}_{REFERENCE_PULLBACK}_{REFERENCE_EXIT}_shares",
            "in_family": False,
            "note": "Yahoo 5-minute cache only. Not part of the gate or the q-values.",
        },
        "random": "seed 17, the same number of bars, each bar keeps the paired signal's direction, stop one cent beyond that bar",
        "train": [TRAIN_START.isoformat(), TRAIN_END.isoformat()],
        "holdout": [HOLDOUT_START.isoformat(), HOLDOUT_END.isoformat()],
        "gate": {
            "profit_factor": GATE_PF,
            "sharpe": GATE_SHARPE,
            "max_drawdown": GATE_DRAWDOWN,
            "holdout_trades": GATE_TRADES,
            "ending_above_start": True,
            "train_sharpe_above_random": True,
            "q": GATE_Q,
            "dsr": GATE_DSR,
        },
        "random_seed": RANDOM_SEED,
        "n_trials": len(cells),
        "cells": cells,
    }


def completed_blocks(minutes: np.ndarray) -> list[tuple[str, int, int]]:
    """Offsets of completed blocks inside one session. The end offset is included."""
    found: list[tuple[str, int, int]] = []
    pairs = [("h4", OPEN_MINUTE, MORNING_LAST), ("h4", AFTERNOON_START, AFTERNOON_LAST)]
    pairs.extend(("h1", start, end) for start, end in HOUR_EDGES)
    cursor = OPEN_MINUTE
    while cursor <= 15 * 60 + 45:
        pairs.append(("m15", cursor, cursor + 10))
        cursor += 15
    for name, start, end in pairs:
        start_at = np.flatnonzero(minutes == start)
        end_at = np.flatnonzero(minutes == end)
        if len(start_at) == 0 or len(end_at) == 0:
            continue
        left = int(start_at[0])
        right = int(end_at[0])
        if right > left:
            found.append((name, left, right))
    return found


def _finite(value: float) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def _directions(closes: np.ndarray, highs: np.ndarray, lows: np.ndarray, slow: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    n = len(closes)
    ema_dir = np.zeros(n, dtype=int)
    structure = np.zeros(n, dtype=int)
    for i in range(1, n):
        if _finite(slow[i]) and _finite(slow[i - 1]):
            if closes[i] > slow[i] and slow[i] > slow[i - 1]:
                ema_dir[i] = 1
            elif closes[i] < slow[i] and slow[i] < slow[i - 1]:
                ema_dir[i] = -1
        if highs[i] > highs[i - 1] and lows[i] > lows[i - 1] and closes[i] > highs[i - 1]:
            structure[i] = 1
        elif highs[i] < highs[i - 1] and lows[i] < lows[i - 1] and closes[i] < lows[i - 1]:
            structure[i] = -1
    return ema_dir, structure


def _hour_agreement(closes: np.ndarray, fast: np.ndarray, slow: np.ndarray) -> np.ndarray:
    out = np.zeros(len(closes), dtype=int)
    for i in range(len(closes)):
        if not (_finite(fast[i]) and _finite(slow[i])):
            continue
        if closes[i] > slow[i] and fast[i] > slow[i]:
            out[i] = 1
        elif closes[i] < slow[i] and fast[i] < slow[i]:
            out[i] = -1
    return out


def _stamp_last(dest: np.ndarray, ends: np.ndarray, values: np.ndarray) -> None:
    if len(ends) == 0:
        return
    pos = np.searchsorted(ends, np.arange(len(dest)), side="right") - 1
    valid = pos >= 0
    dest[valid] = values[pos[valid]]


def _map_higher(book: Book, bars: pd.DataFrame) -> None:
    n = len(book.close)
    day_starts = [0]
    for i in range(1, n):
        if book.dates[i] != book.dates[i - 1]:
            day_starts.append(i)
    day_starts.append(n)
    book.sessions = len(day_starts) - 1
    h4_end: list[int] = []
    h4_high: list[float] = []
    h4_low: list[float] = []
    h4_close: list[float] = []
    h1_end: list[int] = []
    h1_close: list[float] = []
    m15_end: list[int] = []
    m15_first: list[int] = []
    m15_high: list[float] = []
    m15_low: list[float] = []
    m15_close: list[float] = []
    for left, right in zip(day_starts, day_starts[1:]):
        blocks = completed_blocks(book.minute[left:right])
        for name, start, end in blocks:
            a = left + start
            b = left + end
            if name == "h4":
                h4_end.append(b)
                h4_high.append(float(book.high[a : b + 1].max()))
                h4_low.append(float(book.low[a : b + 1].min()))
                h4_close.append(float(book.close[b]))
            elif name == "h1":
                h1_end.append(b)
                h1_close.append(float(book.close[b]))
            else:
                m15_end.append(b)
                m15_first.append(a)
                m15_high.append(float(book.high[a : b + 1].max()))
                m15_low.append(float(book.low[a : b + 1].min()))
                m15_close.append(float(book.close[b]))
    book.h4_bars = len(h4_end)
    book.h1_bars = len(h1_end)
    if h4_end:
        closes = np.asarray(h4_close, dtype=float)
        slow = ema(pd.Series(closes), 20).to_numpy(dtype=float)
        ema_dir, structure = _directions(
            closes,
            np.asarray(h4_high, dtype=float),
            np.asarray(h4_low, dtype=float),
            slow,
        )
        ends = np.asarray(h4_end, dtype=int)
        _stamp_last(book.h4_ema, ends, ema_dir)
        _stamp_last(book.h4_structure, ends, structure)
    if h1_end:
        closes = np.asarray(h1_close, dtype=float)
        series = pd.Series(closes)
        fast = ema(series, 9).to_numpy(dtype=float)
        slow = ema(series, 20).to_numpy(dtype=float)
        agree = _hour_agreement(closes, fast, slow)
        ends = np.asarray(h1_end, dtype=int)
        _stamp_last(book.h1_agree, ends, agree)
        _stamp_last(book.h1_ema20, ends, slow)
    if not m15_end:
        return
    frame = pd.DataFrame(
        {
            "high": m15_high,
            "low": m15_low,
            "close": m15_close,
        }
    )
    slow = ema(frame["close"].astype(float), 20).to_numpy(dtype=float)
    width = atr(frame, 14).to_numpy(dtype=float)
    ends = np.asarray(m15_end, dtype=int)
    book.m15_done[ends] = True
    book.m15_first[ends] = np.asarray(m15_first, dtype=int)
    book.m15_low[ends] = np.asarray(m15_low, dtype=float)
    book.m15_high[ends] = np.asarray(m15_high, dtype=float)
    book.m15_close[ends] = np.asarray(m15_close, dtype=float)
    book.m15_ema20[ends] = slow
    book.m15_atr[ends] = width
    book.m15_vwap[ends] = book.vwap[ends]


def _touch(book: Book, index: int, pullback: str) -> bool:
    ref = book.m15_ema20[index] if pullback == "ema20" else book.m15_vwap[index]
    width = book.m15_atr[index]
    if not (_finite(ref) and _finite(width) and width > 0):
        return False
    band = TOUCH_ATR * float(width)
    low = float(book.m15_low[index])
    high = float(book.m15_high[index])
    return low <= ref + band and high >= ref - band


def _aligned(book: Book, index: int, direction_mode: str) -> int:
    trend = int(book.h4_ema[index] if direction_mode == "ema" else book.h4_structure[index])
    if trend == 0 or int(book.h1_agree[index]) != trend:
        return 0
    return trend


def find_signals(book: Book, direction_mode: str, pullback: str) -> list[Event]:
    """Causal signals. Bar i uses only blocks whose last 5-minute bar is i or earlier."""
    events: list[Event] = []
    armed = False
    arm_dir = 0
    arm_first = -1
    arm_end = -1
    extreme = float("nan")
    n = len(book.close)
    for i in range(n):
        if book.m15_done[i]:
            aligned = _aligned(book, i, direction_mode)
            level = book.h1_ema20[i]
            close = book.m15_close[i]
            invalid = aligned == 0 or not _finite(level)
            if not invalid and aligned == 1 and close < level:
                invalid = True
            if not invalid and aligned == -1 and close > level:
                invalid = True
            if invalid:
                armed = False
            elif _touch(book, i, pullback):
                if not armed or arm_dir != aligned:
                    armed = True
                    arm_dir = aligned
                    arm_first = int(book.m15_first[i])
                    arm_end = i
                    extreme = float(book.m15_low[i] if aligned == 1 else book.m15_high[i])
                elif aligned == 1:
                    extreme = min(extreme, float(book.m15_low[i]))
                else:
                    extreme = max(extreme, float(book.m15_high[i]))
            elif armed and arm_dir == aligned:
                if aligned == 1:
                    extreme = min(extreme, float(book.m15_low[i]))
                else:
                    extreme = max(extreme, float(book.m15_high[i]))
            else:
                armed = False
        if not armed or i <= arm_end:
            continue
        if int(book.minute[i]) >= FLAT_MINUTE:
            continue
        if _aligned(book, i, direction_mode) != arm_dir:
            armed = False
            continue
        ema9 = book.ema9[i]
        if not _finite(ema9):
            continue
        if arm_dir == 1:
            extreme = min(extreme, float(book.low[i]))
            trigger = book.close[i] > book.open[i] and book.close[i] > ema9
        else:
            extreme = max(extreme, float(book.high[i]))
            trigger = book.close[i] < book.open[i] and book.close[i] < ema9
        if not trigger:
            continue
        fill_i = i + 1
        if fill_i >= n or book.dates[fill_i] != book.dates[i] or int(book.minute[fill_i]) >= FLAT_MINUTE:
            armed = False
            continue
        stop = extreme - STOP_PAD if arm_dir == 1 else extreme + STOP_PAD
        events.append(
            Event(
                symbol=book.symbol,
                direction="long" if arm_dir == 1 else "short",
                direction_mode=direction_mode,
                pullback=pullback,
                signal_i=i,
                fill_i=fill_i,
                stop=float(stop),
            )
        )
        armed = False
    return events


def _planned_target(book: Book, event: Event, fill: float, exit_name: str) -> Optional[float]:
    risk = (fill - event.stop) if event.direction == "long" else (event.stop - fill)
    if not _finite(risk) or risk <= 0 or not _finite(fill):
        return None
    if exit_name == "r1":
        return fill + risk if event.direction == "long" else fill - risk
    if exit_name == "r2":
        return fill + 2.0 * risk if event.direction == "long" else fill - 2.0 * risk
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


def _walk(book: Book, fill_i: int, direction: str, stop: float, target: Optional[float], exit_name: str):
    n = len(book.close)
    last = fill_i
    for i in range(fill_i, n):
        if book.dates[i] != book.dates[fill_i]:
            return "flat", float(book.close[last]), book.index[last]
        last = i
        if int(book.minute[i]) >= FLAT_MINUTE:
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
            if low <= stop:
                return "stop", stop, book.index[i]
            if level is not None and _finite(level) and high >= level:
                return "target", float(level), book.index[i]
        else:
            if opened >= stop:
                return "stop", opened, book.index[i]
            if level is not None and _finite(level) and opened <= level:
                return "target", opened, book.index[i]
            if high >= stop:
                return "stop", stop, book.index[i]
            if level is not None and _finite(level) and low <= level:
                return "target", float(level), book.index[i]
    return "flat", float(book.close[last]), book.index[last]


def resolve(book: Book, events: list[Event], exit_name: str) -> list[dict]:
    """Underlying fills. The option price and the share count come later."""
    found = []
    for event in events:
        fill = float(book.open[event.fill_i])
        if not _finite(fill) or fill <= 0:
            continue
        if event.direction == "long" and fill <= event.stop:
            continue
        if event.direction == "short" and fill >= event.stop:
            continue
        target = _planned_target(book, event, fill, exit_name)
        if not _target_ok(event.direction, fill, target, exit_name):
            continue
        reason, exit_raw, when = _walk(book, event.fill_i, event.direction, event.stop, target, exit_name)
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
                "right": "call" if event.direction == "long" else "put",
                "direction": event.direction,
                "stop": float(event.stop),
                "reason": reason,
                "signal_i": int(event.signal_i),
            }
        )
    found.sort(key=lambda row: (row["day"], row["fill_i"]))
    return found


def _share_qty(direction: str, fill: float, stop: float, settled: float, day_equity: float) -> int:
    distance = abs(fill - stop)
    if distance <= 0 or day_equity <= 0 or settled <= 0:
        return 0
    budget = RISK_FRACTION * day_equity
    raw_qty = int(budget / (distance * (1.0 + COSTS.friction_bps / 10_000.0)))
    entry_px = buy_price(fill, COSTS) if direction == "long" else sell_price(fill, COSTS)
    if entry_px <= 0:
        return 0
    cash_qty = int(settled / entry_px)
    return max(0, min(raw_qty, cash_qty))


def _share_ticket(row: dict, quantity: int) -> Optional[tuple[float, float, float]]:
    fill = float(row["fill"])
    exit_raw = float(row["exit"])
    if row["direction"] == "long":
        entry_px = buy_price(fill, COSTS)
        exit_px = sell_price(exit_raw, COSTS)
        debit = entry_px * quantity + buy_fees(COSTS)
        credit = exit_px * quantity - sell_regulatory_fees(exit_px, quantity, COSTS)
        if debit <= 0:
            return None
        return debit, credit, credit - debit
    entry_px = sell_price(fill, COSTS)
    exit_px = buy_price(exit_raw, COSTS)
    notional = entry_px * quantity
    fees_open = sell_regulatory_fees(entry_px, quantity, COSTS)
    fees_close = buy_fees(COSTS)
    debit = notional + fees_open
    pnl = (entry_px - exit_px) * quantity - fees_open - fees_close
    return debit, debit + pnl, pnl


def simulate_shares(rows: list[dict], sessions: list[date], stake: float = STAKE) -> dict:
    from webull_bot.chart_reads.vwap_band import metrics_from

    by_day: dict[date, list[dict]] = {}
    for row in rows:
        by_day.setdefault(row["day"], []).append(row)
    if not sessions:
        index = pd.DatetimeIndex([pd.Timestamp(TRAIN_START)])
        equity = pd.Series([stake], index=index)
        return {"metrics": metrics_from(equity, [], stake), "pnls": [], "equity": equity}
    settled = float(stake)
    pending: list[tuple[date, float]] = []
    pnls: list[float] = []
    values = []
    for day in sessions:
        if pending:
            still = []
            for due, amount in pending:
                if due <= day:
                    settled += amount
                else:
                    still.append((due, amount))
            pending = still
        day_equity = settled + sum(amount for _due, amount in pending)
        taken = 0
        busy = -1
        for row in by_day.get(day, []):
            if taken >= MAX_TRADES_PER_DAY or int(row["fill_i"]) <= busy:
                continue
            quantity = _share_qty(row["direction"], float(row["fill"]), float(row["stop"]), settled, day_equity)
            if quantity < 1:
                continue
            ticket = _share_ticket(row, quantity)
            if ticket is None or ticket[0] > settled + 1e-9:
                continue
            debit, credit, pnl = ticket
            settled -= debit
            pending.append((row["due"], credit))
            pnls.append(pnl)
            taken += 1
            busy = int(row["exit_i"])
            day_equity = settled + sum(amount for _due, amount in pending)
        values.append(settled + sum(amount for _due, amount in pending))
    index = pd.DatetimeIndex([pd.Timestamp(day) for day in sessions])
    equity = pd.Series(values, index=index, dtype=float)
    return {"metrics": metrics_from(equity, pnls, stake), "pnls": pnls, "equity": equity}


def session_days(book: Book) -> list[date]:
    found = []
    seen = set()
    for day in book.dates:
        if day in seen:
            continue
        seen.add(day)
        found.append(day if isinstance(day, date) else pd.Timestamp(day).date())
    return found


def window_rows(rows: list[dict], start: date, end: date) -> list[dict]:
    return [row for row in rows if start <= row["day"] <= end]


def random_events(book: Book, events: list[Event], start: date, end: date, seed: int = RANDOM_SEED) -> list[Event]:
    """Same count, same directions, seed 17. The stop is one cent beyond the sampled bar."""
    chosen = [event for event in events if start <= _as_date(book.dates[event.fill_i]) <= end]
    if not chosen:
        return []
    eligible = []
    n = len(book.close)
    for i in range(n - 1):
        if book.dates[i + 1] != book.dates[i]:
            continue
        day = _as_date(book.dates[i + 1])
        if day < start or day > end or int(book.minute[i + 1]) >= FLAT_MINUTE:
            continue
        eligible.append(i)
    if not eligible:
        return []
    rng = np.random.default_rng(seed)
    take = min(len(chosen), len(eligible))
    picked = sorted(int(i) for i in rng.choice(np.asarray(eligible, dtype=int), size=take, replace=False))
    paired = chosen[:take]
    out = []
    for index, event in zip(picked, paired):
        if event.direction == "long":
            stop = float(book.low[index]) - STOP_PAD
        else:
            stop = float(book.high[index]) + STOP_PAD
        out.append(
            Event(
                symbol=book.symbol,
                direction=event.direction,
                direction_mode=event.direction_mode,
                pullback=event.pullback,
                signal_i=index,
                fill_i=index + 1,
                stop=stop,
            )
        )
    return out


def _as_date(value) -> date:
    if isinstance(value, date):
        return value
    return pd.Timestamp(value).date()


def passes_gate(holdout: dict, train: dict, random_train: dict, q_value: float, dsr: float) -> bool:
    trades = int(holdout.get("trades") or 0)
    sharpe = float(holdout.get("sharpe") or 0.0)
    drawdown = float(holdout.get("max_drawdown") or 0.0)
    ending = float(holdout.get("ending_equity") or 0.0)
    profit_factor = holdout.get("profit_factor")
    if profit_factor is None:
        pf_ok = trades > 0 and float(holdout.get("win_rate") or 0.0) == 1.0
    else:
        pf_ok = float(profit_factor) >= GATE_PF
    train_sharpe = float(train.get("sharpe") or 0.0)
    random_sharpe = float(random_train.get("sharpe") or 0.0)
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


def gate_label(holdout: dict, train: dict, random_train: dict, q_value: float, dsr: float) -> str:
    if passes_gate(holdout, train, random_train, q_value, dsr):
        return "yes"
    reasons = []
    trades = int(holdout.get("trades") or 0)
    if trades < GATE_TRADES:
        reasons.append(f"trades {trades}<{GATE_TRADES}")
    profit_factor = holdout.get("profit_factor")
    if profit_factor is not None and float(profit_factor) < GATE_PF:
        reasons.append(f"PF {float(profit_factor):.3f}<{GATE_PF:.2f}")
    elif profit_factor is None and not (trades > 0 and float(holdout.get("win_rate") or 0.0) == 1.0):
        reasons.append("PF missing")
    sharpe = float(holdout.get("sharpe") or 0.0)
    if sharpe < GATE_SHARPE:
        reasons.append(f"Sharpe {sharpe:.2f}<{GATE_SHARPE:.2f}")
    drawdown = float(holdout.get("max_drawdown") or 0.0)
    if drawdown < GATE_DRAWDOWN:
        reasons.append(f"drawdown {drawdown:.1%}")
    if float(holdout.get("ending_equity") or 0.0) <= STAKE:
        reasons.append("ending at or under $2,500")
    if float(train.get("sharpe") or 0.0) <= float(random_train.get("sharpe") or 0.0):
        reasons.append("train Sharpe did not beat seed 17")
    if q_value > GATE_Q:
        reasons.append(f"q {q_value:.3f}>{GATE_Q:.2f}")
    if dsr < GATE_DSR:
        reasons.append(f"DSR {dsr:.3f}<{GATE_DSR:.2f}")
    return "no (" + ", ".join(reasons) + ")"
