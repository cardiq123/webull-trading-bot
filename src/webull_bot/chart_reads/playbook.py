"""One combined SPY 0 DTE playbook. Backtests only. Does not place an order.

The grid below is the whole search. It was written before the walk-forward
score. A cell is a book, a daily cap, an exit, the two-close 9/20 rule, and a
late-day cutoff. The score picks the cell that holds up next to its neighbors
on each training window. It does not pick the single best training Sharpe.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from datetime import date, time
from typing import Optional

import numpy as np
import pandas as pd

from webull_bot.calendar import next_trading_day
from webull_bot.chart_reads.band_exit import _bid, _half_spread, _option_mid, opposite_band
from webull_bot.chart_reads.detect import session_bands
from webull_bot.chart_reads.ema_reclaim import Setup, find_setups
from webull_bot.chart_reads.ema_reject import swing_targets
from webull_bot.chart_reads.exhaustion import find_exhaustions
from webull_bot.chart_reads.reentry import find_reentries
from webull_bot.chart_reads.trendline_bounce import _stop_at, _structures, find_bounces
from webull_bot.chart_reads.vwap_band import (
    FLAT as VWAP_FLAT,
    SAMPLE_END,
    Signal,
    _iv_on,
    find_signals,
    metrics_from,
    passes_gate,
)
from webull_bot.chart_reads.wick import find_wicks
from webull_bot.mtf_vwap.detect import rth
from webull_bot.options.fees import CONTRACT_MULTIPLIER, option_leg_fees
from webull_bot.options.pricing import listed_strike, norm_cdf

NY = "America/New_York"
FLAT_5M = time(15, 30)
RANDOM_SEED = 17
MIN_TRAIN_TRADES = 80
TRAIN_PF = 1.0
TRAIN_DD_FLOOR = -0.60
DSR_MIN = 0.95
OUTER = 2.0

BOOKS = ("trend", "turn", "all", "confirmed")
CAPS = (3, 5)
EXITS = ("1r", "2r", "prem50", "prem100", "band", "ema200", "level", "ema20")
EXIT_FAMILY = {
    "1r": ("1r", "2r"),
    "2r": ("1r", "2r"),
    "prem50": ("prem50", "prem100"),
    "prem100": ("prem50", "prem100"),
    "band": ("band", "ema200", "level", "ema20"),
    "ema200": ("band", "ema200", "level", "ema20"),
    "level": ("band", "ema200", "level", "ema20"),
    "ema20": ("band", "ema200", "level", "ema20"),
}
BOOK_NEIGHBORS = {
    "trend": ("all",),
    "turn": ("all",),
    "all": ("trend", "turn", "confirmed"),
    "confirmed": ("all",),
}
BOOK_SETUPS = {
    "trend": frozenset({"vwap", "wick", "bounce"}),
    "turn": frozenset({"reclaim", "reentry", "exhaustion"}),
    "all": frozenset({"vwap", "reclaim", "reentry", "wick", "exhaustion", "bounce"}),
    "confirmed": frozenset({"vwap5", "reclaim", "reentry", "wick", "exhaustion", "bounce"}),
}
PRIORITY = {
    "vwap": 0,
    "vwap5": 0,
    "reclaim": 1,
    "reentry": 2,
    "wick": 3,
    "exhaustion": 4,
    "bounce": 5,
    "random": 6,
    "stack2": 7,
}
RECLAIM_RANK = {
    "strict": 0,
    "body": 1,
    "no_crack": 2,
    "no_pullback": 3,
    "no_crack_no_pullback": 4,
    "reclaim9": 5,
}
STACKS = ("off", "exit", "confirm", "both")
CUTOFFS = (None, time(15, 0), time(15, 15))
STACK_NEIGHBORS = {
    "off": ("exit", "confirm"),
    "exit": ("off", "both"),
    "confirm": ("off", "both"),
    "both": ("exit", "confirm"),
}
CUTOFF_NEIGHBORS = {
    None: (time(15, 0),),
    time(15, 0): (None, time(15, 15)),
    time(15, 15): (time(15, 0),),
}
# 4 books x 2 caps x 8 exits x 4 stack roles x 3 cutoffs.
GRID_SIZE = 768
SIMPLE_CELL = ("trend", 3, "1r", "off", None)


def frozen_rules() -> dict:
    """Written down before the result is scored. The score does not edit this."""
    return {
        "name": "spy_0dte_playbook",
        "clock": (
            "Signals keep the clock of the setup that found them. Exits are walked on 5-minute bars. "
            "The 2 SD continuation flats at 15:45 ET. Every 5-minute setup flats at 15:30 ET. No overnight hold."
        ),
        "setups": {
            "vwap": "15-minute 2 SD extension, the published continuation. Fill is the next 15-minute open. Stop is one cent beyond the signal bar.",
            "vwap5": (
                "The same extension, kept only when the next 5-minute close is still beyond that signal bar's frozen 2 SD band. "
                "The fill is the open after that 5-minute bar. The stop stays the original signal bar's stop. A 10:30 signal is not treated as early."
            ),
            "reclaim": (
                "Five-step 9 EMA reclaim and the looser variants. On one direction and one fill, the strictest variant is kept: "
                "strict, body, no_crack, no_pullback, no_crack_no_pullback, then reclaim9. A looser variant still enters when the stricter one did not fire on that fill."
            ),
            "reentry": "20 EMA re-entry after a 2 SD tag, green hold only. The structural stop is the 20 EMA on the fill bar.",
            "wick": "Filtered 9 EMA wick. The structural stop is the 9 EMA on the fill bar.",
            "exhaustion": "Trend-exhaustion shelf break. The structural stop is the published swing stop.",
            "bounce": "Trendline-plus-support confluence only. Support alone and the trendline alone stay out of this grid. The structural stop is the confluence level on the fill bar.",
            "stack2": (
                "Two consecutive 5-minute closes under both the 9 EMA and the 20 EMA trigger a put. "
                "The fill is the next open. The stop is one cent above the higher high of those two bars. "
                "The mirror is two consecutive closes above both averages, and that triggers a call, "
                "with the stop one cent under the lower low of those two bars. "
                "The first time the pair completes is the trigger. Later bars in the same streak do not fire again. "
                "On 2026-10-07 the 14:50 high tags the upper band and closes back under it. "
                "The first pair under both averages after that is the 15:10 close and the 15:15 close. "
                "The fill is the 15:20 open. The spike is the illustration, not an extra filter."
            ),
        },
        "books": {
            "trend": "vwap, wick, bounce",
            "turn": "reclaim, reentry, exhaustion",
            "all": "vwap, reclaim, reentry, wick, exhaustion, bounce",
            "confirmed": "vwap5, reclaim, reentry, wick, exhaustion, bounce",
        },
        "book_neighbors": {key: list(value) for key, value in BOOK_NEIGHBORS.items()},
        "caps": list(CAPS),
        "cap_meaning": "The cap counts entries taken that session. A skipped overlap does not use a slot. One position at a time.",
        "priority": "Same fill time: vwap, reclaim, reentry, wick, exhaustion, bounce, then the two-close trigger. The later one overlaps and is skipped.",
        "stack": {
            "off": "The two-close rule is not used.",
            "exit": (
                "A long exits at the close of the second consecutive 5-minute bar that closes under both the 9 and the 20. "
                "A short exits at the close of the second consecutive bar that closes above both. "
                "The two bars are the fill bar or later. Bars before the fill do not count. "
                "The cell's own stop and target are checked first on that bar."
            ),
            "confirm": (
                "A put is taken only when the two-close-under pair has just completed, and a call only when the two-close-above pair has just completed. "
                "The pair itself is an entry. Another setup on that same fill is kept only when its own signal bar is the second close of the pair. "
                "The named setup wins the tie."
            ),
            "both": "The confirm rule and the exit rule together.",
        },
        "stack_neighbors": {key: list(value) for key, value in STACK_NEIGHBORS.items()},
        "cutoff": (
            "New entries whose fill is after the cutoff are skipped. The cutoff does not use a cap slot. "
            "None keeps the setup's own last-fill clock. 15:00 and 15:15 are the other two values. "
            "A fill at exactly the cutoff is still taken. The 15:20 fill of the 2026-10-07 pair is after both 15:00 and 15:15, so only the no-cutoff cells can take that illustration."
        ),
        "cutoffs": ["none", "15:00", "15:15"],
        "drop": "A fill that is already through the structural stop is not a trade, on every exit, so the entry list does not depend on the exit.",
        "exits": {
            "1r": "Structural stop, target one times the fill-to-stop distance. Stop wins if both trade in one bar.",
            "2r": "Same stop, target two times that distance.",
            "prem50": "Same structural stop. Exit when the model bid is 50% above the entry ask. Stop is checked first. No extra 9 EMA exit.",
            "prem100": "Same, at 100% above the entry ask.",
            "band": "Structural stop. Target is that bar's opposite 2 SD session band when it is beyond the fill.",
            "ema200": "Structural stop. Target is that bar's 5-minute 200 EMA when it is beyond the fill.",
            "level": (
                "Structural stop. Target is frozen on the last closed 5-minute bar before the fill: "
                "the nearer of the latest confirmed swing beyond the fill and the opposite trendline beyond the fill."
            ),
            "ema20": "Stop is a close through the 5-minute 20 EMA. A gap through it fills at the open. The target is the opposite 2 SD band, and a tag during the bar fills before that close.",
        },
        "exit_families": {key: list(value) for key, value in EXIT_FAMILY.items()},
        "grid": "4 books, caps 3 and 5, 8 exits, 4 roles for the two-close rule, 3 late-day cutoffs. 768 cells. Nothing is added after the score.",
        "grid_size": GRID_SIZE,
        "account": "One at-the-money 0 DTE contract. Calls for longs, puts for shorts. Both directions. Sale settles the next session. Equity at or under $1 takes no new trade.",
        "model": "Black-Scholes, rate 2%, dividend 0, prior-session VIX1D or else prior VIX, clipped to 5%-150%. Half-spread is the greater of $0.01 and 1.5% of the mid.",
        "walk_forward": (
            "Train is the three calendar years before the test year. Test is the next calendar year. "
            "Tests are 2020, 2021, 2022, 2023, 2024, 2025, and 2026 through 2026-10-06. "
            "The cache starts 2017-02-16, so the 2017-2019 train is the sessions that exist. "
            "A test day is never inside its own train window."
        ),
        "selection": (
            "On the $1,000 train account only. A cell is eligible with at least 80 trades, profit factor at least 1.0, "
            "and a train drawdown no worse than -60%. Its score is the worse of its own Sharpe and the median Sharpe of its neighbors. "
            "Neighbors are the other cap, the other exits in its family, the books listed in book_neighbors, "
            "the stack roles that change one job, and the adjacent cutoff. "
            "Ties go to the simpler cell: fewer setups, then trend before turn before all before confirmed, then the smaller cap, "
            "then the earlier exit, then the two-close rule off, then no late cutoff. "
            "If no cell is eligible, the fold uses trend, cap 3, exit 1R, the two-close rule off, and no late cutoff, and is marked as a fallback."
        ),
        "headline": (
            "The stitched equity trades each test year with that year's train pick only. "
            "The rule sheet is the cell picked most often. It is stable when that cell is a strict majority of the folds and it is also the last fold's pick. "
            "The last train ends 2025-12-31, so 2026 is not an input to the rule that would be traded next."
        ),
        "correction": (
            "Deflated Sharpe uses the stitched daily returns and 768 trials. "
            "The probability has to be at least 0.95 on the walk-forward stitch and on the single majority rule replayed across every test day."
        ),
        "gate": "The published gate on the stitched test segments: 300 trades, profit factor at least 1.10, Sharpe at least 0.40, max drawdown no worse than -30%.",
        "promote": (
            "A sandbox book is added only when the walk-forward stitch and the single majority rule both clear that gate, "
            "both deflated Sharpes clear 0.95, the majority is strict, the last fold picked that same cell, and the last fold was eligible. "
            "Otherwise nothing is added. Existing books are not edited either way."
        ),
        "baselines": "The original 2 SD continuation, 1R, no daily cap, walked on 15-minute bars. SPY bought at the first test open. Seed 17 random 1R entries, the same number of attempts as the stitch took.",
        "seed": RANDOM_SEED,
        "simple_cell": list(SIMPLE_CELL),
        "sample_end": SAMPLE_END.isoformat(),
        "not_live": "Not a live strategy. Nothing is added to the optional or selected lists unless the promote rule above fires, and then only as a separate sandbox forward book.",
    }


def cells() -> tuple:
    """The 768 cells, in the frozen order."""
    return tuple(
        (book, cap, exit_name, stack, cutoff)
        for book in BOOKS
        for cap in CAPS
        for exit_name in EXITS
        for stack in STACKS
        for cutoff in CUTOFFS
    )


def neighbors(cell: tuple) -> tuple:
    """One change of cap, exit family, book, two-close role, or cutoff. The cell itself is not included."""
    book, cap, exit_name, stack, cutoff = cell
    found = []
    other_cap = 5 if cap == 3 else 3
    found.append((book, other_cap, exit_name, stack, cutoff))
    for other_exit in EXIT_FAMILY[exit_name]:
        if other_exit != exit_name:
            found.append((book, cap, other_exit, stack, cutoff))
    for other_book in BOOK_NEIGHBORS[book]:
        found.append((other_book, cap, exit_name, stack, cutoff))
    for other_stack in STACK_NEIGHBORS[stack]:
        found.append((book, cap, exit_name, other_stack, cutoff))
    for other_cutoff in CUTOFF_NEIGHBORS[cutoff]:
        found.append((book, cap, exit_name, stack, other_cutoff))
    return tuple(dict.fromkeys(found))


def simplicity_rank(cell: tuple) -> tuple:
    """Lower is the simpler cell. Used only to break a tie."""
    book, cap, exit_name, stack, cutoff = cell
    cutoff_rank = {None: 0, time(15, 15): 1, time(15, 0): 2}[cutoff]
    return (
        len(BOOK_SETUPS[book]),
        BOOKS.index(book),
        int(cap),
        EXITS.index(exit_name),
        STACKS.index(stack),
        cutoff_rank,
    )


def cell_setups(cell: tuple) -> frozenset:
    """Book members, plus the two-close trigger when that role is on."""
    book, _cap, _exit_name, stack, _cutoff = cell
    setups = set(BOOK_SETUPS[book])
    if stack in ("confirm", "both"):
        setups.add("stack2")
    return frozenset(setups)


def path_key(exit_name: str, stack: str):
    """The priced path. Exit and both use the walk that also honors the two-close exit."""
    if stack in ("exit", "both"):
        return (exit_name, "stack")
    return exit_name


@dataclass(frozen=True)
class Fold:
    train_start: date
    train_end: date
    test_start: date
    test_end: date

    @property
    def name(self) -> str:
        return f"{self.test_start.year}"


def folds() -> tuple[Fold, ...]:
    """Seven folds. Each train window ends the day before its test window."""
    found = []
    for year in range(2020, 2027):
        test_start = date(year, 1, 1)
        test_end = SAMPLE_END if year == 2026 else date(year, 12, 31)
        found.append(
            Fold(
                train_start=date(year - 3, 1, 1),
                train_end=date(year - 1, 12, 31),
                test_start=test_start,
                test_end=test_end,
            )
        )
    return tuple(found)


def _sharpe(metrics: dict) -> float:
    value = metrics.get("sharpe")
    if value is None or not np.isfinite(value):
        return -1.0
    return float(value)


def eligible(metrics: dict) -> bool:
    """Train screen. This is not the published gate."""
    trades = int(metrics.get("trades") or 0)
    if trades < MIN_TRAIN_TRADES:
        return False
    drawdown = metrics.get("max_drawdown")
    if drawdown is None or not np.isfinite(drawdown) or float(drawdown) < TRAIN_DD_FLOOR:
        return False
    profit_factor = metrics.get("profit_factor")
    if profit_factor is None:
        return float(metrics.get("win_rate") or 0.0) == 1.0
    return bool(np.isfinite(profit_factor) and float(profit_factor) >= TRAIN_PF)


def stability_score(cell: tuple, table: dict) -> Optional[float]:
    """Worse of this cell and the median neighbor. Ineligible cells have no score."""
    metrics = table.get(cell)
    if metrics is None or not eligible(metrics):
        return None
    neighbor_sharpes = [_sharpe(table[item]) for item in neighbors(cell) if item in table]
    if not neighbor_sharpes:
        return None
    return min(_sharpe(metrics), float(np.median(neighbor_sharpes)))


def select_cell(table: dict) -> tuple[tuple, bool]:
    """Highest stability score. Ties use simplicity_rank. False means every cell missed the train screen."""
    best = None
    best_score = None
    for cell in cells():
        score = stability_score(cell, table)
        if score is None:
            continue
        if best is None or score > best_score + 1e-12 or (
            abs(score - best_score) <= 1e-12 and simplicity_rank(cell) < simplicity_rank(best)
        ):
            best = cell
            best_score = score
    if best is None:
        return SIMPLE_CELL, False
    return best, True


def best_sharpe_cell(table: dict) -> Optional[tuple]:
    """The highest train Sharpe among eligible cells. Reported, not used to pick."""
    best = None
    best_value = None
    for cell in cells():
        metrics = table.get(cell)
        if metrics is None or not eligible(metrics):
            continue
        value = _sharpe(metrics)
        if best is None or value > best_value:
            best = cell
            best_value = value
    return best


def modal_cell(picks: list[tuple]) -> tuple[tuple, int]:
    """Most common pick. A tie uses the simpler cell."""
    if not picks:
        return SIMPLE_CELL, 0
    counts: dict[tuple, int] = {}
    for cell in picks:
        counts[cell] = counts.get(cell, 0) + 1
    best_count = max(counts.values())
    tied = [cell for cell, count in counts.items() if count == best_count]
    tied.sort(key=simplicity_rank)
    return tied[0], best_count


def strict_majority(count: int, total: int) -> bool:
    return count * 2 > total


@dataclass(frozen=True)
class Play:
    setup: str
    direction: str
    day: date
    signal_time: pd.Timestamp
    fill_time: pd.Timestamp
    fill_i: int
    stop: float
    flat: time
    level: float
    priority: int
    stack_ok: bool = False


@dataclass(frozen=True)
class Exit:
    reason: str
    spot: float
    when: pd.Timestamp
    premium: Optional[float]


@dataclass(frozen=True)
class Path:
    exit_time: pd.Timestamp
    debit: float
    credit: float
    pnl: float
    reason: str


@dataclass(frozen=True)
class Ticket:
    setup: str
    day: date
    fill_time: pd.Timestamp
    priority: int
    paths: dict
    stack_ok: bool = False


def dedup_reclaim(setups: list[Setup]) -> list[Setup]:
    """One fill and one direction. The stricter variant wins."""
    best: dict[tuple, Setup] = {}
    for item in setups:
        key = (item.direction, item.fill_i)
        prior = best.get(key)
        if prior is None or RECLAIM_RANK[item.variant] < RECLAIM_RANK[prior.variant]:
            best[key] = item
    return list(best.values())


def closes_beyond(close: float, vwap: float, std: float, direction: str) -> bool:
    """Strict close outside the frozen 2 SD band. A zero-width band does not confirm."""
    if not np.isfinite(close) or not np.isfinite(vwap) or not np.isfinite(std) or std <= 0.0:
        return False
    if direction == "long":
        return close > vwap + OUTER * std
    if direction == "short":
        return close < vwap - OUTER * std
    return False


def confirm_5m(frame: pd.DataFrame, five: pd.DataFrame, signals: list[Signal]) -> list[Signal]:
    """Next 5-minute close versus the signal bar's frozen 15-minute band. The stop is unchanged."""
    bars = rth(frame)
    five_bars = rth(five) if five is not None else five
    if bars.empty or five_bars is None or five_bars.empty or not signals:
        return []
    bands = session_bands(frame, deviations=1.0).reindex(bars.index)
    kept: list[Signal] = []
    for signal in signals:
        if signal.mode != "extension" or signal.signal_time not in bands.index:
            continue
        confirm_at = signal.signal_time + pd.Timedelta(minutes=15)
        fill_at = confirm_at + pd.Timedelta(minutes=5)
        if confirm_at not in five_bars.index or fill_at not in five_bars.index:
            continue
        if _day(fill_at) != _day(signal.signal_time) or fill_at.tz_convert(NY).time() >= VWAP_FLAT:
            continue
        width = bands.loc[signal.signal_time]
        std = float(width["std"]) if pd.notna(width["std"]) else float("nan")
        vwap = float(width["vwap"]) if pd.notna(width["vwap"]) else float("nan")
        close = float(five_bars.loc[confirm_at, "close"])
        if not closes_beyond(close, vwap, std, signal.direction):
            continue
        kept.append(replace(signal, fill_time=fill_at))
    kept.sort(key=lambda item: (item.fill_time, item.signal_time))
    return kept


def _day(stamp: pd.Timestamp) -> date:
    clock = pd.Timestamp(stamp)
    if clock.tzinfo is not None:
        clock = clock.tz_convert(NY)
    return clock.date()


def _stop_beyond(direction: str, stop: float, fill: float) -> bool:
    if not np.isfinite(stop) or not np.isfinite(fill) or fill <= 0.0:
        return False
    if direction == "long":
        return stop < fill
    return stop > fill


def _session_end(dates: list[date], index: int) -> int:
    day = dates[index]
    end = index + 1
    count = len(dates)
    while end < count and dates[end] == day:
        end += 1
    return end


def _nearer(direction: str, fill: float, candidates: list[float]) -> float:
    best = None
    best_distance = None
    for level in candidates:
        if not np.isfinite(level):
            continue
        if direction == "long" and not level > fill:
            continue
        if direction == "short" and not level < fill:
            continue
        distance = abs(level - fill)
        if best is None or distance < best_distance:
            best = float(level)
            best_distance = distance
    if best is None:
        return float("nan")
    return best


def _line_value(structures: dict, side: str, index: int) -> float:
    row = structures.get((side, index))
    if row is None:
        return float("nan")
    anchor1, anchor2, y1, y2, _shelf = row
    if anchor2 <= anchor1 or not np.isfinite(y1) or not np.isfinite(y2):
        return float("nan")
    return float(y1 + (y2 - y1) / (anchor2 - anchor1) * (index - anchor1))


def _level_at(structures: dict, long_swing: np.ndarray, short_swing: np.ndarray, direction: str, known: int, fill: float) -> float:
    if known < 0:
        return float("nan")
    if direction == "long":
        swing = float(long_swing[known]) if known < len(long_swing) else float("nan")
        line = _line_value(structures, "short", known)
    else:
        swing = float(short_swing[known]) if known < len(short_swing) else float("nan")
        line = _line_value(structures, "long", known)
    return _nearer(direction, fill, [swing, line])


def _r_target(direction: str, fill: float, stop: float, multiple: float) -> float:
    risk = abs(fill - stop)
    if direction == "long":
        return fill + multiple * risk
    return fill - multiple * risk


def _price_stop_hit(direction: str, opened: float, high: float, low: float, stop: float) -> Optional[float]:
    if direction == "long":
        if opened <= stop:
            return opened
        if low <= stop:
            return stop
        return None
    if opened >= stop:
        return opened
    if high >= stop:
        return stop
    return None


def _target_hit(direction: str, opened: float, high: float, low: float, goal: Optional[float]) -> Optional[float]:
    if goal is None or not np.isfinite(goal):
        return None
    if direction == "long":
        if opened >= goal:
            return opened
        if high >= goal:
            return goal
        return None
    if opened <= goal:
        return opened
    if low <= goal:
        return goal
    return None


def closes_on_side(prep, index: int, direction: str) -> bool:
    """Long: the close is above the 9 and the 20. Short: the close is under both."""
    if index < 0 or index >= len(prep.close):
        return False
    closed = float(prep.close[index])
    fast = float(prep.ema9[index])
    slow = float(prep.ema20[index])
    if not np.isfinite(closed) or not np.isfinite(fast) or not np.isfinite(slow):
        return False
    if direction == "long":
        return closed > fast and closed > slow
    if direction == "short":
        return closed < fast and closed < slow
    return False


def stack_pair(prep, index: int, direction: str) -> bool:
    """This bar and the prior bar, same session, both closed on ``direction``'s side of the 9 and the 20."""
    prior = index - 1
    if prior < 0 or prep.dates[prior] != prep.dates[index]:
        return False
    return closes_on_side(prep, prior, direction) and closes_on_side(prep, index, direction)


def exit_underlying(prep, play: Play, exit_name: str, iv: Optional[float], stack_exit: bool = False) -> Optional[Exit]:
    """Walk one exit. The stop is filled before the target when both trade."""
    if exit_name not in EXITS:
        raise ValueError(f"unknown exit {exit_name}")
    fill_i = play.fill_i
    if fill_i < 0 or fill_i >= len(prep.close):
        return None
    fill = float(prep.open[fill_i])
    if not _stop_beyond(play.direction, play.stop, fill):
        return None
    end = _session_end(prep.dates, fill_i)
    last_spot = fill
    last_time = prep.index[fill_i]
    multiple = 1.0 if exit_name == "1r" else 2.0 if exit_name == "2r" else None
    premium_multiple = 1.5 if exit_name == "prem50" else 2.0 if exit_name == "prem100" else None
    fixed = _r_target(play.direction, fill, play.stop, multiple) if multiple is not None else None
    if exit_name == "level":
        fixed = float(play.level) if np.isfinite(play.level) else None
    entry_ask = None
    strike = None
    right = "call" if play.direction == "long" else "put"
    if premium_multiple is not None:
        if iv is None:
            return None
        strike = listed_strike(fill, fill)
        entry_mid = _option_mid(right, fill, strike, play.fill_time, iv, 0)
        entry_ask = entry_mid + _half_spread(entry_mid)
        if entry_ask <= 0:
            return None
    for j in range(fill_i, end):
        opened = float(prep.open[j])
        high = float(prep.high[j])
        low = float(prep.low[j])
        closed = float(prep.close[j])
        stamp = prep.index[j]
        if prep.times[j] >= play.flat:
            return Exit("flat", opened, stamp, None)
        if exit_name == "ema20":
            level = float(prep.ema20[j])
            if np.isfinite(level) and _price_stop_hit(play.direction, opened, opened, opened, level) is not None:
                return Exit("stop", opened, stamp, None)
            band = opposite_band(play.direction, float(prep.vwap[j]), float(prep.std[j]), fill)
            tagged = _target_hit(play.direction, opened, high, low, band)
            if tagged is not None:
                return Exit("band", tagged, stamp, None)
            if np.isfinite(level) and _close_through(play.direction, closed, level):
                return Exit("stop", closed, stamp, None)
        else:
            stopped = _price_stop_hit(play.direction, opened, high, low, play.stop)
            if premium_multiple is not None:
                if stopped is not None:
                    return Exit("stop", stopped, stamp, None)
                open_bid = _bid(right, opened, strike, stamp, iv, 0)
                extreme = high if play.direction == "long" else low
                extreme_bid = _bid(right, extreme, strike, stamp, iv, 0)
                if open_bid >= premium_multiple * entry_ask:
                    return Exit(exit_name, opened, stamp, open_bid)
                if extreme_bid >= premium_multiple * entry_ask:
                    return Exit(exit_name, extreme, stamp, premium_multiple * entry_ask)
            elif exit_name in ("1r", "2r", "level"):
                goal = fixed if fixed is not None and _beyond(play.direction, fixed, fill) else None
                tagged = _target_hit(play.direction, opened, high, low, goal)
                if stopped is not None and tagged is not None:
                    return Exit("stop", stopped, stamp, None)
                if stopped is not None:
                    return Exit("stop", stopped, stamp, None)
                if tagged is not None:
                    return Exit("target", tagged, stamp, None)
            else:
                if stopped is not None:
                    return Exit("stop", stopped, stamp, None)
                if exit_name == "band":
                    goal = opposite_band(play.direction, float(prep.vwap[j]), float(prep.std[j]), fill)
                else:
                    goal = _beyond(play.direction, float(prep.ema200[j]), fill)
                tagged = _target_hit(play.direction, opened, high, low, goal)
                if tagged is not None:
                    return Exit(exit_name, tagged, stamp, None)
        adverse = "short" if play.direction == "long" else "long"
        if stack_exit and j > fill_i and stack_pair(prep, j, adverse):
            return Exit("stack2", closed, stamp, None)
        if np.isfinite(closed):
            last_spot = closed
            last_time = stamp
    return Exit("last", last_spot, last_time, None)


def _beyond(direction: str, level: float, fill: float) -> Optional[float]:
    if not np.isfinite(level) or not np.isfinite(fill):
        return None
    if direction == "long" and level > fill:
        return float(level)
    if direction == "short" and level < fill:
        return float(level)
    return None


def _close_through(direction: str, closed: float, level: float) -> bool:
    if not np.isfinite(closed) or not np.isfinite(level):
        return False
    if direction == "long":
        return closed < level
    return closed > level


def price_play(prep, play: Play, iv: Optional[float], exits: tuple[str, ...] = EXITS) -> Optional[Ticket]:
    """Price every requested exit. Missing IV drops the play."""
    if iv is None or play.fill_i >= len(prep.close):
        return None
    fill = float(prep.open[play.fill_i])
    if not _stop_beyond(play.direction, play.stop, fill):
        return None
    right = "call" if play.direction == "long" else "put"
    strike = listed_strike(fill, fill)
    entry_mid = _option_mid(right, fill, strike, play.fill_time, iv, 0)
    entry_ask = entry_mid + _half_spread(entry_mid)
    debit = entry_ask * CONTRACT_MULTIPLIER + option_leg_fees(1, entry_ask, sell=False)
    if debit <= 0:
        return None
    paths = {}
    for exit_name in exits:
        for stack_exit in (False, True):
            outcome = exit_underlying(prep, play, exit_name, iv, stack_exit)
            if outcome is None:
                continue
            if outcome.premium is None:
                exit_bid = _bid(right, outcome.spot, strike, outcome.when, iv, 0)
            else:
                exit_bid = float(outcome.premium)
            credit = exit_bid * CONTRACT_MULTIPLIER - option_leg_fees(1, exit_bid, sell=True)
            key = (exit_name, "stack") if stack_exit else exit_name
            paths[key] = Path(outcome.when, debit, credit, credit - debit, outcome.reason)
    if not paths:
        return None
    return Ticket(play.setup, play.day, play.fill_time, play.priority, paths, play.stack_ok)


def _known_index(prep, fill_i: int) -> int:
    if fill_i <= 0:
        return -1
    if prep.dates[fill_i - 1] != prep.dates[fill_i]:
        return -1
    return fill_i - 1


def _make_play(prep, structures, long_swing, short_swing, setup: str, direction: str, signal_time, fill_i: int, stop: float, flat: time) -> Optional[Play]:
    if fill_i < 0 or fill_i >= len(prep.close):
        return None
    fill = float(prep.open[fill_i])
    if prep.times[fill_i] >= flat:
        return None
    if not _stop_beyond(direction, stop, fill):
        return None
    known = _known_index(prep, fill_i)
    level = _level_at(structures, long_swing, short_swing, direction, known, fill)
    confirmed = known >= 0 and stack_pair(prep, known, direction)
    return Play(
        setup,
        direction,
        prep.dates[fill_i],
        pd.Timestamp(signal_time),
        prep.index[fill_i],
        fill_i,
        float(stop),
        flat,
        level,
        PRIORITY[setup],
        confirmed,
    )


def _index_of(lookup: dict, stamp: pd.Timestamp) -> Optional[int]:
    key = pd.Timestamp(stamp)
    found = lookup.get(key)
    if found is None and key.tzinfo is not None:
        found = lookup.get(key.tz_convert(NY))
    return found


def build_plays(prep, frame_15: pd.DataFrame) -> tuple[list[Play], dict]:
    """Every setup, once. Pricing is separate so a test can inspect the list."""
    lookup = {pd.Timestamp(stamp): index for index, stamp in enumerate(prep.index)}
    structures = _structures(prep)
    long_swing, short_swing = swing_targets(
        prep.high.astype(float), prep.low.astype(float), prep.close.astype(float), width=2,
    )
    # swing_targets returns (short_target, long_target): support below, resistance above.
    short_level, long_level = long_swing, short_swing
    plays: list[Play] = []
    notes = {"dropped_stop": 0}

    def add(play: Optional[Play], attempted: bool = True) -> None:
        if play is None:
            if attempted:
                notes["dropped_stop"] += 1
            return
        plays.append(play)

    raw = [item for item in find_signals(frame_15, "SPY", OUTER) if item.mode == "extension"]
    for signal in raw:
        fill_i = _index_of(lookup, signal.fill_time)
        if fill_i is None:
            notes["dropped_stop"] += 1
            continue
        signal_i = _index_of(lookup, signal.signal_time)
        signal_time = prep.index[signal_i] if signal_i is not None else signal.signal_time
        add(_make_play(prep, structures, long_level, short_level, "vwap", signal.direction, signal_time, fill_i, float(signal.stop), VWAP_FLAT))
    confirmed = confirm_5m(frame_15, _five_frame(prep), raw)
    for signal in confirmed:
        fill_i = _index_of(lookup, signal.fill_time)
        if fill_i is None:
            notes["dropped_stop"] += 1
            continue
        add(_make_play(prep, structures, long_level, short_level, "vwap5", signal.direction, signal.signal_time, fill_i, float(signal.stop), VWAP_FLAT))
    for item in dedup_reclaim(find_setups(prep, "SPY")):
        add(_make_play(prep, structures, long_level, short_level, "reclaim", item.direction, prep.index[item.trigger_i], item.fill_i, float(item.stop), FLAT_5M))
    for item in find_reentries(prep, "SPY"):
        if item.variant != "green":
            continue
        stop = float(prep.ema20[item.fill_i])
        add(_make_play(prep, structures, long_level, short_level, "reentry", item.direction, prep.index[item.signal_i], item.fill_i, stop, FLAT_5M))
    for item in find_wicks(prep, "SPY"):
        if item.variant != "filtered":
            continue
        stop = float(prep.ema9[item.fill_i])
        add(_make_play(prep, structures, long_level, short_level, "wick", item.direction, prep.index[item.signal_i], item.fill_i, stop, FLAT_5M))
    for item in find_exhaustions(prep, "SPY"):
        add(_make_play(prep, structures, long_level, short_level, "exhaustion", item.direction, prep.index[item.signal_i], item.fill_i, float(item.stop), FLAT_5M))
    for item in find_bounces(prep, "SPY"):
        if item.variant != "confluence":
            continue
        stop = _stop_at(item, item.fill_i)
        if stop is None:
            notes["dropped_stop"] += 1
            continue
        add(_make_play(prep, structures, long_level, short_level, "bounce", item.direction, prep.index[item.signal_i], item.fill_i, float(stop), FLAT_5M))
    for play in _stack_triggers(prep, structures, long_level, short_level):
        add(play)
    plays.sort(key=lambda item: (item.fill_time, item.priority))
    notes["plays"] = len(plays)
    for name in PRIORITY:
        if name == "random":
            continue
        notes[name] = sum(1 for item in plays if item.setup == name)
    return plays, notes


def _stack_triggers(prep, structures, long_level, short_level) -> list[Play]:
    """First completion of the two-close pair in a streak. The fill is the next open."""
    found = []
    count = len(prep.close)
    index = 0
    while index < count:
        end = _session_end(prep.dates, index)
        streak_long = 0
        streak_short = 0
        last = end - 1
        for cursor in range(index, last):
            if closes_on_side(prep, cursor, "short"):
                streak_short += 1
                streak_long = 0
            elif closes_on_side(prep, cursor, "long"):
                streak_long += 1
                streak_short = 0
            else:
                streak_long = 0
                streak_short = 0
            if streak_short == 2:
                stop = max(float(prep.high[cursor - 1]), float(prep.high[cursor])) + 0.01
                found.append(
                    _make_play(
                        prep, structures, long_level, short_level, "stack2", "short",
                        prep.index[cursor], cursor + 1, stop, FLAT_5M,
                    )
                )
            elif streak_long == 2:
                stop = min(float(prep.low[cursor - 1]), float(prep.low[cursor])) - 0.01
                found.append(
                    _make_play(
                        prep, structures, long_level, short_level, "stack2", "long",
                        prep.index[cursor], cursor + 1, stop, FLAT_5M,
                    )
                )
        index = end
    return [item for item in found if item is not None]


def _five_frame(prep) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "open": prep.open,
            "high": prep.high,
            "low": prep.low,
            "close": prep.close,
            "volume": prep.volume,
        },
        index=prep.index,
    )


def build_tickets(prep, frame_15: pd.DataFrame, iv_points: dict, exits: tuple[str, ...] = EXITS) -> tuple[list[Ticket], dict]:
    """Plays priced with the prior-session vol print. Days without a print are counted and dropped."""
    plays, notes = build_plays(prep, frame_15)
    tickets = []
    missing_iv = 0
    for play in plays:
        iv = _iv_on(play.day, iv_points)
        if iv is None:
            missing_iv += 1
            continue
        ticket = price_play(prep, play, iv, exits)
        if ticket is not None:
            tickets.append(ticket)
    notes["missing_iv"] = missing_iv
    notes["tickets"] = len(tickets)
    return tickets, notes


def index_tickets(tickets: list[Ticket]) -> dict[date, list[Ticket]]:
    grouped: dict[date, list[Ticket]] = {}
    for ticket in tickets:
        grouped.setdefault(ticket.day, []).append(ticket)
    for rows in grouped.values():
        rows.sort(key=lambda item: (item.fill_time, item.priority))
    return grouped


def run_cell(indexed: dict, days: list[date], cell: tuple, stake: float) -> dict:
    """One frozen cell. Cash carries across ``days`` and nowhere else."""
    _book, cap, exit_name, stack, cutoff = cell
    plan = {day: (cell_setups(cell), cap, exit_name, stack, cutoff) for day in days}
    return run_plan(indexed, days, plan, stake)


def run_days(indexed: dict, days: list[date], setups: frozenset, cap: Optional[int], exit_name: str, stake: float) -> dict:
    """One exit and cap, with the two-close rule off and no late cutoff."""
    plan = {day: (setups, cap, exit_name, "off", None) for day in days}
    return run_plan(indexed, days, plan, stake)


def _fill_clock(stamp: pd.Timestamp) -> time:
    clock = pd.Timestamp(stamp)
    if clock.tzinfo is not None:
        clock = clock.tz_convert(NY)
    return clock.time()


def run_plan(indexed: dict, days: list[date], plan: dict, stake: float) -> dict:
    """``plan[day]`` is ``(setups, cap, exit, stack, cutoff)``. Days are marked even when no trade is taken."""
    settled = float(stake)
    unsettled: list[tuple[date, float]] = []
    equity = float(stake)
    stopped = False
    curve_days = []
    curve_values = []
    pnls: list[float] = []
    trade_days: list[date] = []
    skips = {"overlap": 0, "cap": 0, "premium": 0, "bust": 0, "exit": 0, "cutoff": 0, "stack": 0}
    for day in days:
        still = []
        for available_on, amount in unsettled:
            if available_on <= day:
                settled += amount
            else:
                still.append((available_on, amount))
        unsettled = still
        equity = settled + sum(amount for _when, amount in unsettled)
        slot = plan.get(day)
        taken = 0
        busy = None
        if slot is not None and not stopped:
            setups, cap, exit_name, stack, cutoff = slot
            for ticket in indexed.get(day, []):
                if ticket.setup not in setups:
                    continue
                if cutoff is not None and _fill_clock(ticket.fill_time) > cutoff:
                    skips["cutoff"] += 1
                    continue
                if stack in ("confirm", "both") and ticket.setup != "stack2" and not ticket.stack_ok:
                    skips["stack"] += 1
                    continue
                if stopped or equity <= 1.0:
                    skips["bust"] += 1
                    continue
                if cap is not None and taken >= cap:
                    skips["cap"] += 1
                    continue
                if busy is not None and ticket.fill_time <= busy:
                    skips["overlap"] += 1
                    continue
                path = ticket.paths.get(path_key(exit_name, stack))
                if path is None:
                    skips["exit"] += 1
                    continue
                if path.debit > settled + 1e-9:
                    skips["premium"] += 1
                    continue
                settled -= path.debit
                unsettled.append((next_trading_day(day), path.credit))
                equity = settled + sum(amount for _when, amount in unsettled)
                pnls.append(path.pnl)
                trade_days.append(day)
                taken += 1
                busy = path.exit_time
                if equity <= 1.0:
                    stopped = True
        curve_days.append(pd.Timestamp(day))
        curve_values.append(equity)
    equity_series = pd.Series(curve_values, index=pd.DatetimeIndex(curve_days), dtype=float)
    stats = metrics_from(equity_series, pnls, float(stake))
    return {
        "equity": equity_series,
        "metrics": stats,
        "pnls": pnls,
        "trade_days": trade_days,
        "skips": skips,
        "stopped": stopped,
    }


def session_days(prep, start: Optional[date] = None, end: Optional[date] = None) -> list[date]:
    found = []
    seen = set()
    for day in prep.dates:
        if day in seen:
            continue
        seen.add(day)
        if start is not None and day < start:
            continue
        if end is not None and day > end:
            continue
        found.append(day)
    return found


def worst_month(equity: pd.Series) -> dict:
    """The lowest month-to-month change of the equity marks."""
    if equity is None or len(equity) == 0:
        return {"month": None, "return": None}
    frame = equity.to_frame("equity")
    frame["month"] = frame.index.to_period("M")
    last = frame.groupby("month")["equity"].last()
    changes = last.pct_change().dropna()
    if changes.empty:
        return {"month": None, "return": None}
    stamp = changes.idxmin()
    return {"month": str(stamp), "return": float(changes.loc[stamp])}


def fold_results(equity: pd.Series, stake: float, fold_list: tuple[Fold, ...]) -> list[dict]:
    """Each test segment against the equity mark just before it."""
    rows = []
    for fold in fold_list:
        window = equity.loc[(equity.index.date >= fold.test_start) & (equity.index.date <= fold.test_end)]
        before = equity.loc[equity.index.date < fold.test_start]
        start_equity = float(before.iloc[-1]) if len(before) else float(stake)
        end_equity = float(window.iloc[-1]) if len(window) else start_equity
        rows.append(
            {
                "fold": fold.name,
                "start": start_equity,
                "end": end_equity,
                "profit": bool(end_equity > start_equity + 1e-6),
            }
        )
    return rows


def deflated_sharpe(equity: pd.Series, starting: float, n_trials: int) -> dict:
    """Bailey and Lopez de Prado. ``n_trials`` is the grid size. The Sharpe here is per day, not annualized."""
    empty = {"dsr": 0.0, "sr": 0.0, "sr0": 0.0, "trials": n_trials, "observations": 0}
    if equity is None or len(equity) < 3 or n_trials < 2:
        return empty
    curve = pd.concat(
        [pd.Series([float(starting)], index=[equity.index[0] - pd.Timedelta(days=1)]), equity.astype(float)]
    )
    returns = curve.pct_change().replace([np.inf, -np.inf], np.nan).dropna().to_numpy(dtype=float)
    count = len(returns)
    if count < 3:
        return empty
    mean = float(returns.mean())
    std = float(returns.std(ddof=0))
    sr = mean / std if std > 0 else 0.0
    centered = returns - mean
    second = float(np.mean(centered ** 2))
    if second <= 0:
        return empty
    skew = float(np.mean(centered ** 3) / second ** 1.5)
    kurt = float(np.mean(centered ** 4) / second ** 2)
    gamma = 0.5772156649015329
    variance = (1.0 - skew * sr + ((kurt - 1.0) / 4.0) * sr * sr) / (count - 1)
    if not np.isfinite(variance) or variance <= 0:
        return {"dsr": 0.0, "sr": sr, "sr0": None, "trials": n_trials, "observations": count}
    sr0 = math.sqrt(variance) * (
        (1.0 - gamma) * _norm_ppf(1.0 - 1.0 / n_trials) + gamma * _norm_ppf(1.0 - 1.0 / (n_trials * math.e))
    )
    scale = 1.0 - skew * sr + ((kurt - 1.0) / 4.0) * sr * sr
    if not np.isfinite(scale) or scale <= 0:
        return {"dsr": 0.0, "sr": sr, "sr0": sr0, "trials": n_trials, "observations": count}
    zed = (sr - sr0) * math.sqrt(count - 1) / math.sqrt(scale)
    probability = float(norm_cdf(zed))
    return {"dsr": probability, "sr": sr, "sr0": sr0, "trials": n_trials, "observations": count}


def _norm_ppf(probability: float) -> float:
    """Inverse standard normal. Peter Acklam's approximation."""
    if probability <= 0.0 or probability >= 1.0:
        raise ValueError("probability must be between 0 and 1")
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
    if probability < plow:
        cue = math.sqrt(-2.0 * math.log(probability))
        return (
            (((((c[0] * cue + c[1]) * cue + c[2]) * cue + c[3]) * cue + c[4]) * cue + c[5])
            / ((((d[0] * cue + d[1]) * cue + d[2]) * cue + d[3]) * cue + 1.0)
        )
    if probability > phigh:
        cue = math.sqrt(-2.0 * math.log(1.0 - probability))
        return -(
            (((((c[0] * cue + c[1]) * cue + c[2]) * cue + c[3]) * cue + c[4]) * cue + c[5])
            / ((((d[0] * cue + d[1]) * cue + d[2]) * cue + d[3]) * cue + 1.0)
        )
    cue = probability - 0.5
    radius = cue * cue
    return (
        (((((a[0] * radius + a[1]) * radius + a[2]) * radius + a[3]) * radius + a[4]) * radius + a[5]) * cue
        / (((((b[0] * radius + b[1]) * radius + b[2]) * radius + b[3]) * radius + b[4]) * radius + 1.0)
    )


def promote_decision(
    *,
    adaptive: dict,
    fixed: dict,
    adaptive_dsr: dict,
    fixed_dsr: dict,
    majority_count: int,
    fold_count: int,
    last_cell: tuple,
    modal: tuple,
    last_eligible: bool,
) -> dict:
    """Both stitched paths, both deflated Sharpes, and a stable last-fold pick."""
    adaptive_gate = passes_gate(adaptive)
    fixed_gate = passes_gate(fixed)
    adaptive_ok = float(adaptive_dsr.get("dsr") or 0.0) >= DSR_MIN
    fixed_ok = float(fixed_dsr.get("dsr") or 0.0) >= DSR_MIN
    stable = strict_majority(majority_count, fold_count) and last_cell == modal and last_eligible
    return {
        "promote": bool(adaptive_gate and fixed_gate and adaptive_ok and fixed_ok and stable),
        "adaptive_gate": adaptive_gate,
        "fixed_gate": fixed_gate,
        "adaptive_dsr": adaptive_ok,
        "fixed_dsr": fixed_ok,
        "stable": stable,
    }


def rule_sheet(cell: tuple, *, promoted: bool, fallback: bool) -> str:
    """Plain English for the cell the folds agreed on."""
    book, cap, exit_name, stack, cutoff = cell
    book_text = {
        "trend": "the 2 SD VWAP continuation, the filtered 9 EMA wick, and the trendline-plus-support bounce",
        "turn": "the 9 EMA reclaim (strictest variant on a shared fill), the green 20 EMA re-entry, and the trend-exhaustion shelf break",
        "all": "all six setups, with the raw 2 SD VWAP continuation",
        "confirmed": "all six setups, and the VWAP continuation only after the next 5-minute close is still outside the signal bar's 2 SD band",
    }[book]
    exit_text = {
        "1r": "The stop is the setup's own price stop. The target is 1R from the fill to that stop. If one bar can hit both, the stop fills.",
        "2r": "The same stop. The target is 2R.",
        "prem50": "The same price stop, checked first. Take the profit when the model bid is 50% above the entry ask.",
        "prem100": "The same price stop, checked first. Take the profit when the model bid is 100% above the entry ask.",
        "band": "The same price stop. The target is the opposite 2 SD session VWAP band on the 5-minute bar, when that band is beyond the fill.",
        "ema200": "The same price stop. The target is the 5-minute 200 EMA when it is beyond the fill.",
        "level": "The same price stop. The target is frozen before the fill: the nearer of the last confirmed swing and the opposite trendline, when that level is beyond the fill.",
        "ema20": "The stop is a 5-minute close back through the 20 EMA. A gap through the 20 EMA fills at the open. The target is the opposite 2 SD band, and a tag during the bar fills before that close.",
    }[exit_name]
    stack_text = {
        "off": "The two-close 9/20 rule is off.",
        "exit": "A long is sold at the second straight 5-minute close under both the 9 and the 20. A short is covered at the second straight close above both. That check uses only bars from the fill onward, and the price stop or target on that bar fills first.",
        "confirm": "A put is opened only by two straight closes under both averages, and a call only by two straight closes above both. The fill is the next open. Another setup is kept on that fill only when its signal bar is that second close.",
        "both": "The two-close pair is required to open the trade, and the opposite pair exits it.",
    }[stack]
    if cutoff is None:
        cutoff_text = "There is no extra late-day cutoff. A fill is still refused at the setup's own flat."
    else:
        cutoff_text = f"No new entry fills after {cutoff.strftime('%H:%M')} ET. A fill at exactly that time is still taken."
    status = (
        "This is a separate sandbox forward book. The older books were not changed."
        if promoted
        else "This rule was not added to the sandbox forward test, and it was not added to the live list."
    )
    screen = (
        "No training cell cleared the screen, so this is the pre-declared simple cell, not a tuned winner."
        if fallback
        else "The folds picked this cell because it held up next to its neighbors, not because it had the highest training Sharpe."
    )
    return (
        f"One SPY position, at the money, expiring the same day. At most {cap} entries a day. "
        f"The entries are {book_text}. "
        f"{exit_text} {stack_text} {cutoff_text} "
        "The continuation is flat at 15:45. The 5-minute setups are flat at 15:30. "
        "A new signal while a trade is open is skipped. A contract that costs more than settled cash is skipped. "
        f"{screen} {status}"
    )


def random_plays(prep, count: int, start: date, end: date, seed: int = RANDOM_SEED) -> list[Play]:
    """Seeded bars inside the test window. Direction is a coin flip. The stop is the signal bar's extreme."""
    if count <= 0:
        return []
    eligible = []
    count_bars = len(prep.close)
    for index in range(count_bars - 1):
        if prep.dates[index] != prep.dates[index + 1]:
            continue
        day = prep.dates[index + 1]
        if day < start or day > end:
            continue
        if prep.times[index] > time(15, 20) or prep.times[index + 1] >= FLAT_5M:
            continue
        low = float(prep.low[index])
        high = float(prep.high[index])
        if not np.isfinite(low) or not np.isfinite(high):
            continue
        eligible.append(index)
    if not eligible:
        return []
    rng = np.random.default_rng(seed)
    take = min(count, len(eligible))
    chosen = rng.choice(np.array(eligible, dtype=int), size=take, replace=False)
    directions = rng.integers(0, 2, size=take)
    plays = []
    for offset, index in enumerate(chosen):
        direction = "long" if int(directions[offset]) == 1 else "short"
        stop = float(prep.low[index] - 0.01) if direction == "long" else float(prep.high[index] + 0.01)
        fill_i = int(index) + 1
        fill = float(prep.open[fill_i])
        if not _stop_beyond(direction, stop, fill):
            continue
        plays.append(
            Play(
                "random",
                direction,
                prep.dates[fill_i],
                prep.index[index],
                prep.index[fill_i],
                fill_i,
                stop,
                FLAT_5M,
                float("nan"),
                PRIORITY["random"],
            )
        )
    plays.sort(key=lambda item: item.fill_time)
    return plays


def spy_hold(prep, stake: float, start: date, end: date) -> dict:
    """Buy at the first test open. Fractional shares. No option and no fee."""
    marks = []
    index = 0
    count = len(prep.close)
    first_open = None
    while index < count:
        day = prep.dates[index]
        end_i = _session_end(prep.dates, index)
        if start <= day <= end:
            if first_open is None:
                first_open = float(prep.open[index])
            marks.append((pd.Timestamp(day), float(prep.close[end_i - 1])))
        index = end_i
    if not marks or first_open is None or first_open <= 0:
        return metrics_from(pd.Series(dtype=float), [], stake)
    shares = float(stake) / first_open
    equity = pd.Series([shares * close for _day, close in marks], index=pd.DatetimeIndex([day for day, _close in marks]))
    stats = metrics_from(equity, [], stake)
    stats["shares"] = shares
    stats["first_open"] = first_open
    return stats
