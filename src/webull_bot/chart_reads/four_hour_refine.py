"""Pre-registered refinements of the QQQ 4-hour EMA, session-VWAP, 1R, 1 DTE cell.

Thresholds in this file were chosen before any refinement score. The original
72-cell detector is unchanged when these filters are left off.
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from webull_bot.chart_reads.four_hour import Book, Event, _as_date, _finite

CHOP_ATR_FRACTION = 0.05
CHOP_RSI_LOW = 45.0
CHOP_RSI_HIGH = 55.0
OPEN_SKIP_BEFORE = 9 * 60 + 45
LUNCH_START = 11 * 60 + 30
LUNCH_END = 13 * 60 + 30
VOLUME_BARS = 20
SLOPE_BARS = 3
SLOPE_MIN = 0.0015
VIX_WINDOW = 252
VIX_PERCENTILE = 10.0
WF_YEARS = (2020, 2021, 2022, 2023)
MIN_WF_TRADES = 80
PRIOR_TRIALS = 72
BASE_CELL = "QQQ_ema_vwap_r1_1dte"
REFINEMENT_IDS = (
    "chop",
    "time",
    "volume",
    "vwap_hold",
    "slope",
    "dead_tape",
    "be15",
    "cap2",
)


def frozen_refine_rules() -> dict:
    return {
        "study": "4hr_refine",
        "registered_before_score": True,
        "base_cell": BASE_CELL,
        "base_plain": "QQQ, 4-hour EMA, session-VWAP pullback, 1R, one 1 DTE contract",
        "why_this_cell": (
            "PR 23's closest option cell: highest holdout Sharpe among option cells "
            "with at least 300 trades. The holdout was already looked at, so this "
            "round does not use it to choose."
        ),
        "selection": {
            "window": "train only, 2017-02-16 through 2023-12-31",
            "walk_forward": (
                "Four fresh $2,500 accounts, one each for 2020, 2021, 2022, and 2023. "
                "Signals may use bars before the test year. The score is the mean of "
                "the four yearly Sharpes."
            ),
            "winner": (
                "A refinement wins only when that mean is strictly greater than the "
                f"base mean and the four years together have at least {MIN_WF_TRADES} trades."
            ),
            "reported_walk_forward_account": (
                "One fresh $2,500 account from 2020-01-01 through 2023-12-31, "
                "with indicators warmed up on earlier bars."
            ),
            "full_train_uses": (
                "The 2017-02-16 through 2023-12-31 account feeds the p-value, "
                "the deflated Sharpe, and the train-Sharpe-versus-seed-17 leg of the gate."
            ),
            "selected_rule": (
                "If two or more refinements win, the selected rule is those winners "
                "combined with AND, and that combination is one extra trial. "
                "If exactly one wins, that refinement is the selected rule and it is "
                "already one of the eight trials. If none win, the selected rule is the base. "
                "Holdout numbers are not an input to this choice."
            ),
            "holdout_report": (
                "Every pre-registered row is scored once on 2024-01-01 through 2026-10-06 "
                "after the choice is locked. Those holdout figures are a report, not a vote."
            ),
        },
        "family": {
            "prior_trials": PRIOR_TRIALS,
            "single_change_trials": len(REFINEMENT_IDS),
            "combination": "one extra trial only when two or more refinements win and the combination is scored",
            "base_not_double_counted": True,
            "bh": "Benjamini-Hochberg on the 72 saved training p-values plus these new p-values",
            "deflated_sharpe": "Bailey and Lopez de Prado on the training daily returns, with the expanded trial count",
            "gate": "the original 4hr gate, unchanged. The -30% drawdown line and the 0.95 deflated-Sharpe line stay put.",
        },
        "refinements": [
            {
                "id": "chop",
                "change": (
                    "Skip the entry when the 5-minute 9 EMA and 20 EMA are within "
                    "0.05 of the 5-minute ATR(14) of each other and the 5-minute "
                    "Wilder RSI(14) is between 45 and 55, both read on the signal bar. "
                    "If either indicator is not finite, the bar is not called chop."
                ),
            },
            {
                "id": "time",
                "change": (
                    "No fill before 9:45 ET, and no fill from 11:30 ET up to but not "
                    "including 13:30 ET. A 9:45 fill is allowed. A 13:30 fill is allowed. "
                    "The clock is the fill open, not the signal bar."
                ),
            },
            {
                "id": "volume",
                "change": (
                    "The signal bar's volume must be at least the mean of the prior "
                    "20 completed 5-minute bars, excluding itself. Those 20 bars are "
                    "the regular-hours tape and may cross the previous session. "
                    "Dukascopy volume is a bid-tick count, not share volume. "
                    "Fewer than 20 prior bars does not qualify."
                ),
            },
            {
                "id": "vwap_hold",
                "change": (
                    "While the pullback is armed, and on the arming bar, a 15-minute "
                    "close through session VWAP against the trend disarms it. "
                    "Long: close below VWAP. Short: close above VWAP. Equal is not through."
                ),
            },
            {
                "id": "slope",
                "change": (
                    "The last completed 4-hour 20 EMA must have moved at least 0.15% "
                    "over the prior three 4-hour bars, in the trade's direction. "
                    "Long: (ema[t] - ema[t-3]) / ema[t-3] >= 0.0015. "
                    "Short: that ratio <= -0.0015. The 0.15% line is a round number, "
                    "not a fitted one. A missing slope does not qualify."
                ),
            },
            {
                "id": "dead_tape",
                "change": (
                    "Skip the day when the prior VIX1D close is strictly below the "
                    "10th percentile of the 252 VIX1D closes strictly before that print. "
                    "The percentile is numpy's linear percentile. Until 252 prior closes "
                    "exist, the filter does not skip. VIX is not a substitute. "
                    "The VIX1D cache starts 2023-04-24, so this filter cannot bind on "
                    "the 2017-2023 train or on the 2020-2023 walk-forward."
                ),
            },
            {
                "id": "be15",
                "change": (
                    "One contract cannot sell two thirds at 1R. Instead, once price "
                    "trades +0.5R, later bars use the fill price as the stop, and the "
                    "target is 1.5R. On the bar that first trades +0.5R, the original "
                    "stop still wins if both trade, and the breakeven stop is not "
                    "applied until the next bar. If that same bar trades 1.5R without "
                    "the original stop, the target fills. Flat stays 15:45."
                ),
            },
            {
                "id": "cap2",
                "change": "At most 2 new entries a day for this book. The base cap is 5.",
            },
        ],
        "combination_mechanics": (
            "Start from the VWAP-hold scan when that refinement won, otherwise the "
            "base scan. Then apply every other winning event filter. Use the "
            "breakeven exit only when that refinement won, otherwise 1R. Use the "
            "2-trade cap only when that refinement won, otherwise 5."
        ),
        "random": (
            "Seed 17, same count of bars as that refinement's own signals, each bar "
            "keeps the paired signal's direction, stop one cent beyond that bar, "
            "then the same exit and the same daily cap."
        ),
        "overlap": (
            "QQQ Aggressive is the same 15-minute 2 SD continuation, 1R, unscaled "
            "1 DTE, 1 cent market, one contract, cap 5, fresh $2,500. Report raw "
            "signal-day overlap, filled-trade overlap, same 15-minute bucket overlap, "
            "and the Pearson correlation of daily trade P&L."
        ),
        "slope_min": SLOPE_MIN,
        "vix_window": VIX_WINDOW,
        "vix_percentile": VIX_PERCENTILE,
        "min_walk_forward_trades": MIN_WF_TRADES,
        "walk_forward_years": list(WF_YEARS),
        "ids": list(REFINEMENT_IDS),
    }


def _chop(book: Book, event: Event) -> bool:
    i = int(event.signal_i)
    fast = book.ema9[i]
    slow = book.ema20[i]
    width = book.atr14[i]
    oscillator = book.rsi14[i]
    if not (_finite(fast) and _finite(slow) and _finite(width) and _finite(oscillator)):
        return False
    if float(width) <= 0:
        return False
    close_emas = abs(float(fast) - float(slow)) <= CHOP_ATR_FRACTION * float(width)
    mid_rsi = CHOP_RSI_LOW <= float(oscillator) <= CHOP_RSI_HIGH
    return bool(close_emas and mid_rsi)


def _time_blocks(book: Book, event: Event) -> bool:
    minute = int(book.minute[int(event.fill_i)])
    if minute < OPEN_SKIP_BEFORE:
        return True
    if LUNCH_START <= minute < LUNCH_END:
        return True
    return False


def _volume_fails(book: Book, event: Event) -> bool:
    i = int(event.signal_i)
    if i < VOLUME_BARS:
        return True
    window = np.asarray(book.volume[i - VOLUME_BARS : i], dtype=float)
    if window.size < VOLUME_BARS or not np.isfinite(window).all():
        return True
    current = book.volume[i]
    if not _finite(current):
        return True
    return float(current) < float(window.mean())


def _slope_fails(book: Book, event: Event) -> bool:
    slope = book.h4_slope[int(event.signal_i)]
    if not _finite(slope):
        return True
    if event.direction == "long":
        return float(slope) < SLOPE_MIN
    return float(slope) > -SLOPE_MIN


def dead_print_dates(vix1d: pd.Series) -> set[date]:
    """VIX1D print dates whose close is below the 10th percentile of the prior 252 closes."""
    if vix1d is None or len(vix1d) == 0:
        return set()
    series = vix1d.dropna().astype(float).sort_index()
    values = series.to_numpy(dtype=float)
    found: set[date] = set()
    for i in range(VIX_WINDOW, len(values)):
        window = values[i - VIX_WINDOW : i]
        if not np.isfinite(window).all() or not np.isfinite(values[i]):
            continue
        cutoff = float(np.percentile(window, VIX_PERCENTILE))
        if float(values[i]) < cutoff:
            stamp = series.index[i]
            found.add(stamp.date() if hasattr(stamp, "date") else stamp)
    return found


def prior_print(vix_dates: list[date], day: date) -> date | None:
    if not vix_dates:
        return None
    # vix_dates must be sorted.
    lo, hi = 0, len(vix_dates)
    while lo < hi:
        mid = (lo + hi) // 2
        if vix_dates[mid] < day:
            lo = mid + 1
        else:
            hi = mid
    if lo == 0:
        return None
    return vix_dates[lo - 1]


def dead_trade_days(vix1d: pd.Series, trade_days: list[date]) -> set[date]:
    prints = dead_print_dates(vix1d)
    if vix1d is None or len(vix1d) == 0:
        return set()
    series = vix1d.dropna().sort_index()
    vix_dates = []
    for stamp in series.index:
        vix_dates.append(stamp.date() if hasattr(stamp, "date") else stamp)
    skipped = set()
    for day in trade_days:
        previous = prior_print(vix_dates, day)
        if previous is not None and previous in prints:
            skipped.add(day)
    return skipped


def blocks(book: Book, event: Event, name: str, dead_days: set[date] | None = None) -> bool:
    """True when this single-change filter rejects the event."""
    if name == "chop":
        return _chop(book, event)
    if name == "time":
        return _time_blocks(book, event)
    if name == "volume":
        return _volume_fails(book, event)
    if name == "slope":
        return _slope_fails(book, event)
    if name == "dead_tape":
        day = _as_date(book.dates[int(event.fill_i)])
        return day in (dead_days or set())
    raise KeyError(name)


def apply_filters(book: Book, events: list[Event], names: list[str], dead_days: set[date] | None = None) -> list[Event]:
    if not names:
        return list(events)
    kept = []
    for event in events:
        if any(blocks(book, event, name, dead_days) for name in names):
            continue
        kept.append(event)
    return kept


def train_winners(base_mean: float, rows: list[dict]) -> list[str]:
    """Walk-forward winners. Holdout fields are ignored on purpose."""
    found = []
    for row in rows:
        if row.get("id") == "base":
            continue
        mean = float(row["mean_yearly_sharpe"])
        trades = int(row["wf_trades"])
        if mean > float(base_mean) and trades >= MIN_WF_TRADES:
            found.append(str(row["id"]))
    return found


def selected_rule(winner_ids: list[str]) -> dict:
    ordered = [name for name in REFINEMENT_IDS if name in set(winner_ids)]
    if len(ordered) >= 2:
        return {
            "id": "combo",
            "kind": "combination",
            "parts": ordered,
            "extra_trial": True,
        }
    if len(ordered) == 1:
        return {
            "id": ordered[0],
            "kind": "single",
            "parts": ordered,
            "extra_trial": False,
        }
    return {
        "id": "base",
        "kind": "base",
        "parts": [],
        "extra_trial": False,
    }


def variant_spec(names: list[str]) -> dict:
    """How to build one row from a list of winning filter ids."""
    chosen = set(names)
    event_filters = [name for name in ("chop", "time", "volume", "slope", "dead_tape") if name in chosen]
    return {
        "hold_vwap": "vwap_hold" in chosen,
        "event_filters": event_filters,
        "exit": "be15" if "be15" in chosen else "r1",
        "cap": 2 if "cap2" in chosen else 5,
    }
