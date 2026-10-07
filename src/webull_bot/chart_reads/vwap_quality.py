"""Quality, daily-cap, and confirmation filters for the 2 SD VWAP continuation.

The extension rule itself is unchanged. These filters sit on top of
``find_signals`` and the existing one-position account. Nothing here places
an order or edits the sandbox book.

Thresholds are the training median of a feature, with the direction written
down below. An end-of-day top-N would rank a morning signal with afternoon
bars that have not closed yet. That look-ahead is not in this family and
cannot be a forward test.
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
from webull_bot.chart_reads.vwap_band import (
    FLAT,
    LAST_SIGNAL,
    OUTER_DEFAULT,
    STOP_PAD,
    RANDOM_SEED,
    TRAIN_END,
    Signal,
    _day_key,
    _iv_on,
    _option_trade,
    metrics_from,
    passes_gate,
    target_price,
    walk_exit,
)
from webull_bot.indicators import atr, ema
from webull_bot.mtf_vwap.detect import rth

NY = "America/New_York"
EARLY_CUTOFF = time(10, 30)
LUNCH_START = time(11, 30)
LUNCH_END = time(13, 30)
REL_VOLUME_BARS = 20
ATR_WINDOW = 14
FDR_Q = 0.10
FDR_MIN_TRADES = 30
QQQ_COVERAGE = 0.90
QQQ_FIRST_DEADLINE = date(2018, 1, 1)

# Named before any holdout dollar. Order is the false-discovery family order.
FAMILY = (
    "cap3",
    "cap4",
    "cap5",
    "stop_two_losses",
    "stop_first_win",
    "stretch",
    "relvol",
    "ema_stack",
    "htf60",
    "qqq",
    "skip_lunch",
    "risk_tight",
    "risk_wide",
    "confirm_15m",
    "confirm_5m",
    "ema_vwap",
    "early_15m",
    "stack",
    "stretch_relvol",
    "stack_cap3",
    "stack_cap5",
    "confirm15_cap3",
    "ema_vwap_cap3",
)


def frozen_rules() -> dict:
    """Written down before the result is scored. The score does not edit this."""
    return {
        "book": (
            "The 15-minute 2 SD session-VWAP extension, one at-the-money 0 DTE contract, "
            "1R target, stop one cent beyond the signal bar, flat at 15:45 ET. "
            "This is the sandbox book. These filters do not replace it."
        ),
        "clock": "15-minute regular-hours bars. A 10:00 bar is 10:00-10:15. The fill of an unconfirmed signal is still the next 15-minute open.",
        "split": "Train is every session through 2021-12-31. Holdout is a fresh account from 2022-01-01 through 2026-10-06.",
        "caps": "cap3, cap4, and cap5 keep the first 3, 4, or 5 extension signals of the session in signal-time order, then the existing one-position account.",
        "path": (
            "stop_two_losses stops new entries after two closed trades that day have a negative pnl. "
            "stop_first_win stops new entries after the first closed trade that day has a positive pnl. "
            "A trade still open does not count. Flat pnl is neither a loss nor a win. "
            "The decision uses only exits whose timestamp is strictly before the new fill."
        ),
        "stretch": (
            "Close distance beyond the signal bar's own 2 SD band, divided by Wilder ATR(14). "
            "Higher is the pre-registered side. The cutoff is the median on training extension signals. "
            "A holdout bar cannot move it. No other cutoff is tried."
        ),
        "relvol": (
            f"Signal-bar volume divided by the mean of the prior {REL_VOLUME_BARS} regular-hours bars, "
            "not including the signal bar. Higher is the pre-registered side. Cutoff is the training median."
        ),
        "ema_stack": "Long only when the 15-minute 9 EMA is above the 20. Short only when the 9 is below the 20. No extra gap.",
        "htf60": (
            "60-minute bars are built from 1-minute bids, left-labeled from 09:30. "
            "The feature is the last completed hour only. A bar still forming is not used. "
            "The 15:30 hour ends at 16:00. Alignment is that hour's 9 EMA versus its 20 EMA. "
            "If the hour has not closed, or the average is not ready, the signal fails this filter."
        ),
        "qqq": (
            "QQQ's 15-minute close is outside QQQ's own 2 SD session band in the same direction, "
            "on the same timestamp. A missing QQQ bar fails the filter. "
            f"QQQ stays in the false-discovery family only when its first Dukascopy session is on or before "
            f"{QQQ_FIRST_DEADLINE.isoformat()} and at least {QQQ_COVERAGE:.0%} of training signals have a QQQ bar. "
            "Otherwise it is reported and left out of the family. That decision uses coverage, not profit."
        ),
        "lunch": "skip_lunch drops a signal whose timestamp is from 11:30 through 13:30 ET inclusive. The window is not searched.",
        "risk": (
            "Stop distance is the absolute gap from the signal close to the stop, divided by ATR(14). "
            "risk_tight keeps distances at or below the training median. "
            "risk_wide keeps distances at or above it. Both are scored. The side is not chosen after seeing pnl."
        ),
        "confirm_15m": (
            "The next 15-minute bar must close strictly beyond that bar's own 2 SD band, in the signal direction. "
            "The fill is the open after that confirmation bar, not the original next open. "
            "The stop stays one cent beyond the original signal bar. 1R is measured from the new fill to that stop. "
            "A new fill already through the stop is a skip. The fill must be before 15:45 the same day."
        ),
        "confirm_5m": (
            "The 15-minute signal bar ends at its close. The next 5-minute bar is the one that starts then. "
            "That 5-minute close is compared with the signal bar's frozen 2 SD band, not a 5-minute band. "
            "The fill is the next 5-minute open. The stop stays the original signal stop. 1R uses the new fill. "
            "This book walks the stop on 5-minute bars, because that open is not a 15-minute open. "
            "Every other book walks 15-minute bars, the same path as the published extension score."
        ),
        "ema_vwap": (
            "On the signal bar only. A long needs the 9 EMA above the 20 and the close above session VWAP. "
            "A short needs the 9 below the 20 and the close below session VWAP. The fill stays the original next open."
        ),
        "early_15m": (
            "A signal strictly before 10:30 ET must pass the 15-minute follow-through. "
            "A signal at 10:30 or later keeps the original entry. 10:30 is not early. The cutoff is not searched."
        ),
        "stack": "ema_stack and htf60, and not lunch. Then stack_cap3 and stack_cap5 keep the first 3 or 5 of those.",
        "stretch_relvol": "stretch and relvol, both at or above their training medians.",
        "confirm15_cap3": "15-minute follow-through, then the first 3 confirmed signals of the session.",
        "ema_vwap_cap3": "ema_vwap, then the first 3 that pass.",
        "lookahead": (
            "An end-of-day top-N would look ahead to later signals before taking the morning trade. "
            "It is not in this family."
        ),
        "family": list(FAMILY),
        "fdr": (
            f"Benjamini-Hochberg on the one-sided normal p-value of the holdout mean trade pnl, "
            f"the same erfc approximation the candle study uses. q <= {FDR_Q:.2f}. "
            f"A book with fewer than {FDR_MIN_TRADES} holdout trades is left out of the adjusted set. "
            "The original uncapped extension is the baseline, not a family member."
        ),
        "gate": (
            "A family member is a candidate only when the fresh $1,000 account clears the published gate "
            "in training and again in the holdout: at least 300 trades, profit factor at least 1.10, "
            "Sharpe at least 0.40, max drawdown no worse than -30%, and the false-discovery q is at most 0.10. "
            "The $5,000 account is reported beside it. Seed 17 is the random baseline and is not in the family."
        ),
        "random": f"Seed {RANDOM_SEED} only, matched to the number of holdout extension signals.",
        "account": "Fresh $1,000 and $5,000. One contract. The same cash, spread, fee, and IV rules as the extension book.",
        "promote": (
            "A candidate would be a new sandbox book beside vwap_band_15m, not a replacement. "
            "Nothing is promoted unless it clears both windows and the correction."
        ),
        "expiry": (
            "A separate pre-declared contract table on the original uncapped 2 SD extension, 1R, one position. "
            "Contracts are 0 DTE flat, and 1, 3, and 7 DTE each flat-by-close and overnight. "
            "0 DTE has no overnight cell. 1, 3, and 7 DTE expire that many trading sessions later. "
            "0 DTE and 1 DTE use prior VIX1D, or prior VIX when that print is missing. 3 DTE and 7 DTE use prior VIX. "
            "Half-spread is the greater of $0.01 and 1.5% of the mid. "
            "Flat sells at 15:45 the entry day. Overnight keeps the stop and the 1R target and flats at 15:45 on the expiration session. "
            "The filter family above is not crossed with expiry and is not retuned. "
            "A contract is robust when the fresh $1,000 account clears the published gate in training and in the holdout "
            "and its false-discovery q on this seven-contract set is at most 0.10. "
            "It does not replace vwap_band_15m."
        ),
    }


@dataclass(frozen=True)
class Feature:
    signal: Signal
    stretch: float
    rel_volume: float
    stop_atr: float
    ema_stack: bool
    ema_vwap: bool
    htf60: bool
    qqq_known: bool
    qqq_confirm: bool
    lunch: bool
    early: bool


@dataclass(frozen=True)
class Priced:
    signal: Signal
    fill: float
    exit_raw: float
    exit_time: pd.Timestamp
    reason: str
    debit: float
    credit: float
    pnl: float
    level: float
    quantity: float
    strike: Optional[float]
    skip: str


def is_early(stamp: pd.Timestamp) -> bool:
    """True only before 10:30 ET. A 10:30 signal is not early."""
    return _clock(stamp) < EARLY_CUTOFF


def in_lunch(stamp: pd.Timestamp) -> bool:
    """11:30 through 13:30 ET inclusive, on the signal timestamp."""
    clock = _clock(stamp)
    return LUNCH_START <= clock <= LUNCH_END


def agrees_ema_vwap(direction: str, ema9: float, ema20: float, close: float, vwap: float) -> bool:
    """9/20 stack and the close on the same side of VWAP as the trade."""
    if not _finite(ema9) or not _finite(ema20) or not _finite(close) or not _finite(vwap):
        return False
    if direction == "long":
        return ema9 > ema20 and close > vwap
    if direction == "short":
        return ema9 < ema20 and close < vwap
    return False


def closes_beyond(close: float, vwap: float, std: float, direction: str, width: float = OUTER_DEFAULT) -> bool:
    """Strict close outside the band. A zero-width band does not confirm."""
    if not _finite(close) or not _finite(vwap) or not _finite(std) or std <= 0.0 or width <= 0.0:
        return False
    upper = vwap + width * std
    lower = vwap - width * std
    if direction == "long":
        return close > upper
    if direction == "short":
        return close < lower
    return False


def qqq_covers(first_day: date | None, known_fraction: float) -> bool:
    """Coverage rule. Profit is not an input."""
    if first_day is None or not _finite(known_fraction):
        return False
    return first_day <= QQQ_FIRST_DEADLINE and float(known_fraction) >= QQQ_COVERAGE


def to_rth_bars(minutes: pd.DataFrame, step: str) -> pd.DataFrame:
    """Left-labeled regular-hours bars aligned to 09:30 ET."""
    bars = rth(minutes)
    empty = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    if bars.empty:
        return empty
    pieces = []
    for day, chunk in bars.groupby(bars.index.date):
        origin = pd.Timestamp(f"{pd.Timestamp(day).date().isoformat()} 09:30", tz=NY)
        out = chunk.resample(step, label="left", closed="left", origin=origin).agg(
            {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
        )
        out = out.dropna(subset=["open"])
        if out.empty:
            continue
        clock = out.index.time
        out = out[(clock >= time(9, 30)) & (clock < time(16, 0))]
        if not out.empty:
            pieces.append(out)
    if not pieces:
        return empty
    combined = pd.concat(pieces)
    return combined[~combined.index.duplicated(keep="last")].sort_index()


def first_n(signals: list[Signal], count: int) -> list[Signal]:
    """First ``count`` signals of each session by signal time, not by a later score."""
    if count <= 0:
        return []
    grouped: dict[date, list[Signal]] = {}
    for signal in signals:
        grouped.setdefault(_day_key(signal.signal_time), []).append(signal)
    kept: list[Signal] = []
    for items in grouped.values():
        items.sort(key=lambda item: item.signal_time)
        kept.extend(items[:count])
    kept.sort(key=lambda item: (item.fill_time, item.signal_time))
    return kept


def confirm_15m(frame: pd.DataFrame, signals: list[Signal]) -> list[Signal]:
    """Delay the fill until the bar after a 15-minute follow-through. Stop stays put."""
    bars = rth(frame)
    if bars.empty or not signals:
        return []
    bands = session_bands(frame, deviations=1.0).reindex(bars.index)
    position = {stamp: index for index, stamp in enumerate(bars.index)}
    kept: list[Signal] = []
    for signal in signals:
        if signal.mode != "extension":
            continue
        index = position.get(signal.signal_time)
        if index is None:
            continue
        confirm_at = signal.signal_time + pd.Timedelta(minutes=15)
        fill_at = confirm_at + pd.Timedelta(minutes=15)
        if index + 2 >= len(bars):
            continue
        if bars.index[index + 1] != confirm_at or bars.index[index + 2] != fill_at:
            continue
        if _day_key(fill_at) != _day_key(signal.signal_time) or fill_at.time() >= FLAT:
            continue
        width = bands.iloc[index + 1]
        std = float(width["std"]) if pd.notna(width["std"]) else float("nan")
        vwap = float(width["vwap"]) if pd.notna(width["vwap"]) else float("nan")
        close = float(bars.iloc[index + 1]["close"])
        if not closes_beyond(close, vwap, std, signal.direction):
            continue
        kept.append(_retimed(signal, fill_at))
    kept.sort(key=lambda item: (item.fill_time, item.signal_time))
    return kept


def confirm_5m(frame: pd.DataFrame, five: pd.DataFrame, signals: list[Signal]) -> list[Signal]:
    """Next 5-minute close versus the signal bar's frozen 15-minute band."""
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
        if _day_key(fill_at) != _day_key(signal.signal_time) or fill_at.time() >= FLAT:
            continue
        width = bands.loc[signal.signal_time]
        std = float(width["std"]) if pd.notna(width["std"]) else float("nan")
        vwap = float(width["vwap"]) if pd.notna(width["vwap"]) else float("nan")
        close = float(five_bars.loc[confirm_at, "close"])
        if not closes_beyond(close, vwap, std, signal.direction):
            continue
        kept.append(_retimed(signal, fill_at))
    kept.sort(key=lambda item: (item.fill_time, item.signal_time))
    return kept


def apply_early_15m(frame: pd.DataFrame, signals: list[Signal]) -> list[Signal]:
    """Before 10:30, require the 15-minute follow-through. Later signals stay as they are."""
    early = [signal for signal in signals if is_early(signal.signal_time)]
    later = [signal for signal in signals if not is_early(signal.signal_time)]
    kept = confirm_15m(frame, early) + later
    kept.sort(key=lambda item: (item.fill_time, item.signal_time))
    return kept


def build_features(
    frame: pd.DataFrame,
    signals: list[Signal],
    hourly: pd.DataFrame | None = None,
    qqq: pd.DataFrame | None = None,
) -> list[Feature]:
    """Features known at the signal-bar close. Later bars are not read."""
    bars = rth(frame)
    if bars.empty or not signals:
        return []
    bands = session_bands(frame, deviations=1.0).reindex(bars.index)
    width = atr(bars, ATR_WINDOW)
    ema9 = ema(bars["close"].astype(float), 9)
    ema20 = ema(bars["close"].astype(float), 20)
    volume = bars["volume"].astype(float)
    prior = volume.rolling(REL_VOLUME_BARS, min_periods=REL_VOLUME_BARS).mean().shift(1)
    relative = volume / prior.replace(0.0, np.nan)
    hour_ends, hour_long, hour_short = _hourly_flags(hourly)
    qqq_bands = None
    qqq_close = None
    if qqq is not None and not qqq.empty:
        qqq_bars = rth(qqq)
        qqq_bands = session_bands(qqq, deviations=1.0).reindex(qqq_bars.index)
        qqq_close = qqq_bars["close"].astype(float)
    found: list[Feature] = []
    for signal in signals:
        if signal.mode != "extension" or signal.signal_time not in bars.index:
            continue
        row = bars.loc[signal.signal_time]
        band = bands.loc[signal.signal_time]
        close = float(row["close"])
        std = float(band["std"]) if pd.notna(band["std"]) else float("nan")
        vwap = float(band["vwap"]) if pd.notna(band["vwap"]) else float("nan")
        bar_atr = float(width.loc[signal.signal_time]) if signal.signal_time in width.index else float("nan")
        upper = vwap + OUTER_DEFAULT * std if _finite(vwap) and _finite(std) else float("nan")
        lower = vwap - OUTER_DEFAULT * std if _finite(vwap) and _finite(std) else float("nan")
        if signal.direction == "long" and _finite(bar_atr) and bar_atr > 0 and _finite(upper):
            stretch = (close - upper) / bar_atr
        elif signal.direction == "short" and _finite(bar_atr) and bar_atr > 0 and _finite(lower):
            stretch = (lower - close) / bar_atr
        else:
            stretch = float("nan")
        stop_distance = abs(close - float(signal.stop)) / bar_atr if _finite(bar_atr) and bar_atr > 0 else float("nan")
        rel = float(relative.loc[signal.signal_time]) if signal.signal_time in relative.index else float("nan")
        if not _finite(rel):
            rel = float("nan")
        fast = float(ema9.loc[signal.signal_time]) if signal.signal_time in ema9.index else float("nan")
        slow = float(ema20.loc[signal.signal_time]) if signal.signal_time in ema20.index else float("nan")
        stack = _stack(signal.direction, fast, slow)
        found.append(
            Feature(
                signal=signal,
                stretch=float(stretch),
                rel_volume=float(rel),
                stop_atr=float(stop_distance),
                ema_stack=stack,
                ema_vwap=agrees_ema_vwap(signal.direction, fast, slow, close, vwap),
                htf60=_hourly_agrees(signal, hour_ends, hour_long, hour_short),
                qqq_known=_qqq_known(signal, qqq_bands),
                qqq_confirm=_qqq_confirm(signal, qqq_bands, qqq_close),
                lunch=in_lunch(signal.signal_time),
                early=is_early(signal.signal_time),
            )
        )
    return found


def freeze_cuts(features: list[Feature]) -> dict:
    """Medians from training signals only. Holdout rows are ignored."""
    train = [item for item in features if _day_key(item.signal.signal_time) <= TRAIN_END]
    return {
        "stretch": _median([item.stretch for item in train]),
        "relvol": _median([item.rel_volume for item in train]),
        "stop_atr": _median([item.stop_atr for item in train]),
        "train_signals": len(train),
    }


def select_signals(
    name: str,
    features: list[Feature],
    cuts: dict,
    frame: pd.DataFrame,
    five: pd.DataFrame | None = None,
    *,
    use_qqq: bool = True,
) -> tuple[list[Signal], str]:
    """Return the signals this variant may enter, and ``15m`` or ``5m`` for the walk."""
    if name not in FAMILY and name != "baseline":
        raise KeyError(name)
    if name == "baseline":
        return [item.signal for item in features], "15m"
    if name == "confirm_5m":
        return confirm_5m(frame, five if five is not None else pd.DataFrame(), [item.signal for item in features]), "5m"
    if name == "confirm_15m":
        return confirm_15m(frame, [item.signal for item in features]), "15m"
    if name == "early_15m":
        return apply_early_15m(frame, [item.signal for item in features]), "15m"
    if name == "confirm15_cap3":
        return first_n(confirm_15m(frame, [item.signal for item in features]), 3), "15m"

    pred = _predicate(name, use_qqq=use_qqq)
    chosen = [item.signal for item in features if pred(item, cuts)]
    cap = _cap_of(name)
    if cap is not None:
        chosen = first_n(chosen, cap)
    return chosen, "15m"


def path_of(name: str) -> str | None:
    if name == "stop_two_losses":
        return "two_losses"
    if name == "stop_first_win":
        return "first_win"
    return None


def price_signals(
    frame: pd.DataFrame,
    signals: list[Signal],
    iv_points: dict,
    *,
    target: str = "r",
) -> list[Priced]:
    """One walk and one option price per signal. Cash is applied later."""
    bars = rth(frame)
    by_day: dict[date, pd.DataFrame] = {}
    for key, chunk in bars.groupby(bars.index.date):
        by_day[key if isinstance(key, date) else pd.Timestamp(key).date()] = chunk
    priced: list[Priced] = []
    for signal in signals:
        day = _day_key(signal.fill_time)
        session = by_day.get(day)
        if session is None or signal.fill_time not in session.index:
            priced.append(_empty(signal, "no_bar"))
            continue
        loc = session.index.get_loc(signal.fill_time)
        if isinstance(loc, slice) or not isinstance(loc, int):
            priced.append(_empty(signal, "no_bar"))
            continue
        fill = float(session.iloc[loc]["open"])
        if fill <= 0 or not np.isfinite(signal.stop):
            priced.append(_empty(signal, "no_bar"))
            continue
        distance = abs(fill - float(signal.stop))
        if distance <= 0:
            priced.append(_empty(signal, "dust"))
            continue
        level = target_price(signal, fill, target)
        reason, exit_raw, exit_time = walk_exit(session, loc, signal.direction, float(signal.stop), level)
        iv = _iv_on(day, iv_points)
        if iv is None:
            priced.append(_empty(signal, "iv", fill=fill, exit_raw=exit_raw, exit_time=exit_time, reason=reason, level=level))
            continue
        trade = _option_trade(signal, fill, exit_raw, exit_time, reason, level, iv, 0, 1e18)
        if trade is None:
            priced.append(_empty(signal, "premium", fill=fill, exit_raw=exit_raw, exit_time=exit_time, reason=reason, level=level))
            continue
        priced.append(
            Priced(
                signal=signal,
                fill=fill,
                exit_raw=float(exit_raw),
                exit_time=exit_time,
                reason=reason,
                debit=float(trade["debit"]),
                credit=float(trade["credit"]),
                pnl=float(trade["pnl"]),
                level=float(level),
                quantity=float(trade["quantity"]),
                strike=trade.get("strike"),
                skip="",
            )
        )
    priced.sort(key=lambda item: (item.signal.fill_time, item.signal.signal_time))
    return priced


def run_account(
    frame: pd.DataFrame,
    priced: list[Priced],
    *,
    stake: float,
    start: date | None = None,
    end: date | None = None,
    path: str | None = None,
) -> dict:
    """The extension account. ``path`` is the only extra gate."""
    if path not in (None, "two_losses", "first_win"):
        raise ValueError("path must be two_losses, first_win, or none")
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
    by_day: dict[date, pd.DataFrame] = {}
    for key, chunk in bars.groupby(bars.index.date):
        by_day[key if isinstance(key, date) else pd.Timestamp(key).date()] = chunk
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
    equity = float(stake)
    curve: list[tuple[pd.Timestamp, float]] = []
    trades: list[dict] = []
    skips = {"short": 0, "overlap": 0, "no_bar": 0, "iv": 0, "premium": 0, "dust": 0, "bust": 0, "path": 0}
    busy: Optional[pd.Timestamp] = None
    cursor = 0
    stopped = False
    closed: list[tuple[float, pd.Timestamp]] = []

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
        closed = []
        while cursor < len(chosen) and _day_key(chosen[cursor].signal.fill_time) == day:
            item = chosen[cursor]
            cursor += 1
            signal = item.signal
            if stopped or equity <= 1.0:
                skips["bust"] += 1
                continue
            if busy is not None and signal.fill_time <= busy:
                skips["overlap"] += 1
                continue
            if item.skip == "no_bar":
                skips["no_bar"] += 1
                continue
            if item.skip == "dust":
                skips["dust"] += 1
                continue
            if item.skip == "iv":
                skips["iv"] += 1
                continue
            if item.skip == "premium":
                skips["premium"] += 1
                continue
            if item.debit > settled + 1e-9:
                skips["premium"] += 1
                continue
            if path == "two_losses" and sum(pnl < 0 and exit_time < signal.fill_time for pnl, exit_time in closed) >= 2:
                skips["path"] += 1
                continue
            if path == "first_win" and any(pnl > 0 and exit_time < signal.fill_time for pnl, exit_time in closed):
                skips["path"] += 1
                continue
            settled -= item.debit
            unsettled.append((next_trading_day(day), item.credit))
            equity = settled + sum(amount for _when, amount in unsettled)
            trades.append(_trade_row(item, equity))
            busy = item.exit_time
            closed.append((item.pnl, item.exit_time))
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
        "skips": skips,
        "metrics": metrics_from(equity_series, pnls, float(stake)),
        "under_one_share": 0,
    }


def summarize_days(counts: dict[date, int], sessions: list[date]) -> dict:
    """Mean and the share of sessions over 3 and over 5. A quiet session counts as zero."""
    values = [int(counts.get(day, 0)) for day in sessions]
    if not values:
        return {"sessions": 0, "mean": 0.0, "pct_gt_3": 0.0, "pct_gt_5": 0.0, "active_days": 0, "max": 0}
    array = np.asarray(values, dtype=float)
    return {
        "sessions": int(len(array)),
        "mean": float(array.mean()),
        "pct_gt_3": float(np.mean(array > 3)),
        "pct_gt_5": float(np.mean(array > 5)),
        "active_days": int(np.sum(array > 0)),
        "max": int(array.max()),
    }


def sessions_between(frame: pd.DataFrame, start: date | None, end: date | None) -> list[date]:
    bars = rth(frame)
    found = []
    seen = set()
    for stamp in bars.index:
        day = _day_key(stamp)
        if start is not None and day < start:
            continue
        if end is not None and day > end:
            continue
        if day not in seen:
            seen.add(day)
            found.append(day)
    return found


def count_by_day(signals: list[Signal]) -> dict[date, int]:
    counts: dict[date, int] = {}
    for signal in signals:
        day = _day_key(signal.signal_time)
        counts[day] = counts.get(day, 0) + 1
    return counts


def trade_t(pnls: list[float]) -> float | None:
    """One-sample t of trade pnl against zero. Sample standard deviation."""
    count = len(pnls)
    if count < 2:
        return None
    values = np.asarray(pnls, dtype=float)
    mean = float(values.mean())
    std = float(values.std(ddof=1))
    if std == 0.0:
        if mean > 0:
            return math.inf
        if mean < 0:
            return -math.inf
        return 0.0
    return mean / (std / math.sqrt(count))


def one_sided_p(stat: float | None) -> float | None:
    """Upper-tail normal p-value, matching the candle study's erfc approximation."""
    if stat is None:
        return None
    if stat == math.inf:
        return 0.0
    if stat == -math.inf:
        return 1.0
    return 0.5 * math.erfc(float(stat) / math.sqrt(2.0))


def benjamini_hochberg(p_values: list[float]) -> np.ndarray:
    count = len(p_values)
    if count == 0:
        return np.array([], dtype=float)
    order = np.argsort(np.asarray(p_values, dtype=float))
    ranked = np.asarray(p_values, dtype=float)[order]
    adjusted = np.empty(count)
    running = 1.0
    for index in range(count - 1, -1, -1):
        running = min(running, ranked[index] * count / (index + 1))
        adjusted[index] = running
    out = np.empty(count)
    out[order] = np.clip(adjusted, 0.0, 1.0)
    return out


def cleared(metrics: dict) -> bool:
    return passes_gate(metrics)


def scored_family(use_qqq: bool) -> tuple[str, ...]:
    """Family after the coverage rule. Dropping QQQ is not a result of pnl."""
    if use_qqq:
        return FAMILY
    return tuple(name for name in FAMILY if name != "qqq")


def pending_extensions(frame: pd.DataFrame, day: date, symbol: str = "SPY") -> list[Signal]:
    """Extension closes that have no next bar yet, so ``find_signals`` cannot fill them.

    The stop and the band are known. The fill timestamp is the next 15 minutes
    even when that bar is absent. Confirmation can still be judged.
    """
    bars = rth(frame)
    if bars.empty:
        return []
    bands = session_bands(frame, deviations=1.0).reindex(bars.index)
    found: list[Signal] = []
    for _day, session in bars.groupby(bars.index.date):
        if (_day if isinstance(_day, date) else pd.Timestamp(_day).date()) != day:
            continue
        band = bands.reindex(session.index)
        prev_inside = True
        for i in range(len(session)):
            width = band.iloc[i]
            std = float(width["std"]) if pd.notna(width["std"]) else float("nan")
            vwap = float(width["vwap"]) if pd.notna(width["vwap"]) else float("nan")
            if not _finite(std) or std <= 0.0 or not _finite(vwap):
                prev_inside = True
                continue
            close = float(session.iloc[i]["close"])
            upper = vwap + OUTER_DEFAULT * std
            lower = vwap - OUTER_DEFAULT * std
            outside_up = close > upper
            outside_dn = close < lower
            stamp = session.index[i]
            nxt = session.index[i + 1] if i + 1 < len(session) else None
            can_fill = (
                nxt is not None
                and stamp.time() <= LAST_SIGNAL
                and nxt.time() < FLAT
                and _day_key(nxt) == _day_key(stamp)
            )
            if prev_inside and (outside_up ^ outside_dn) and not can_fill and stamp.time() <= LAST_SIGNAL:
                direction = "long" if outside_up else "short"
                extreme = float(session.iloc[i]["low"] if direction == "long" else session.iloc[i]["high"])
                stop = extreme - STOP_PAD if direction == "long" else extreme + STOP_PAD
                fill_at = stamp + pd.Timedelta(minutes=15)
                found.append(
                    Signal(symbol, "extension", direction, stamp, fill_at, stop, vwap, vwap, OUTER_DEFAULT)
                )
            prev_inside = not (outside_up or outside_dn)
    return found


def confirmation_marks(
    frame: pd.DataFrame,
    five: pd.DataFrame,
    day: date,
) -> list[dict]:
    """What each frozen confirmation rule does to one session's extension signals."""
    from webull_bot.chart_reads.vwap_band import find_signals

    signals = [
        item
        for item in find_signals(frame, "SPY", OUTER_DEFAULT)
        if item.mode == "extension" and _day_key(item.signal_time) == day
    ]
    pending = pending_extensions(frame, day)
    signals = signals + [item for item in pending if item.signal_time not in {signal.signal_time for signal in signals}]
    features = {item.signal.signal_time: item for item in build_features(frame, signals)}
    by_15 = {item.signal_time: item for item in confirm_15m(frame, signals)}
    by_5 = {item.signal_time: item for item in confirm_5m(frame, five, signals)}
    early = {item.signal_time: item for item in apply_early_15m(frame, signals)}
    rows = []
    for signal in signals:
        feature = features.get(signal.signal_time)
        row_15 = by_15.get(signal.signal_time)
        row_5 = by_5.get(signal.signal_time)
        row_early = early.get(signal.signal_time)
        rows.append(
            {
                "signal_time": signal.signal_time,
                "direction": signal.direction,
                "original_fill": signal.fill_time,
                "stop": float(signal.stop),
                "confirm_15m": row_15 is not None,
                "confirm_15m_fill": None if row_15 is None else row_15.fill_time,
                "confirm_5m": row_5 is not None,
                "confirm_5m_fill": None if row_5 is None else row_5.fill_time,
                "ema_vwap": bool(feature.ema_vwap) if feature is not None else False,
                "ema_stack": bool(feature.ema_stack) if feature is not None else False,
                "early": bool(feature.early) if feature is not None else is_early(signal.signal_time),
                "early_15m": row_early is not None,
                "early_15m_fill": None if row_early is None else row_early.fill_time,
                "lunch": bool(feature.lunch) if feature is not None else in_lunch(signal.signal_time),
                "awaiting_fill": signal.signal_time in {item.signal_time for item in pending},
            }
        )
    return rows


def _predicate(name: str, *, use_qqq: bool):
    def stretch(item: Feature, cuts: dict) -> bool:
        return _finite(item.stretch) and item.stretch >= float(cuts["stretch"])

    def relvol(item: Feature, cuts: dict) -> bool:
        return _finite(item.rel_volume) and item.rel_volume >= float(cuts["relvol"])

    def tight(item: Feature, cuts: dict) -> bool:
        return _finite(item.stop_atr) and item.stop_atr <= float(cuts["stop_atr"])

    def wide(item: Feature, cuts: dict) -> bool:
        return _finite(item.stop_atr) and item.stop_atr >= float(cuts["stop_atr"])

    def qqq(item: Feature, _cuts: dict) -> bool:
        return bool(use_qqq and item.qqq_confirm)

    def stack(item: Feature, _cuts: dict) -> bool:
        return item.ema_stack and item.htf60 and not item.lunch

    table = {
        "cap3": lambda _item, _cuts: True,
        "cap4": lambda _item, _cuts: True,
        "cap5": lambda _item, _cuts: True,
        "stop_two_losses": lambda _item, _cuts: True,
        "stop_first_win": lambda _item, _cuts: True,
        "stretch": stretch,
        "relvol": relvol,
        "ema_stack": lambda item, _cuts: item.ema_stack,
        "htf60": lambda item, _cuts: item.htf60,
        "qqq": qqq,
        "skip_lunch": lambda item, _cuts: not item.lunch,
        "risk_tight": tight,
        "risk_wide": wide,
        "ema_vwap": lambda item, _cuts: item.ema_vwap,
        "stack": stack,
        "stretch_relvol": lambda item, cuts: stretch(item, cuts) and relvol(item, cuts),
        "stack_cap3": stack,
        "stack_cap5": stack,
        "ema_vwap_cap3": lambda item, _cuts: item.ema_vwap,
    }
    if name not in table:
        raise KeyError(name)
    return table[name]


def _cap_of(name: str) -> int | None:
    return {"cap3": 3, "cap4": 4, "cap5": 5, "stack_cap3": 3, "stack_cap5": 5, "ema_vwap_cap3": 3}.get(name)


def _retimed(signal: Signal, fill_time: pd.Timestamp) -> Signal:
    return Signal(
        signal.symbol,
        signal.mode,
        signal.direction,
        signal.signal_time,
        fill_time,
        signal.stop,
        signal.vwap,
        signal.inner,
        signal.outer,
    )


def _empty(
    signal: Signal,
    skip: str,
    fill: float = float("nan"),
    exit_raw: float = float("nan"),
    exit_time: pd.Timestamp | None = None,
    reason: str = "",
    level: float = float("nan"),
) -> Priced:
    when = exit_time if exit_time is not None else signal.fill_time
    return Priced(signal, fill, exit_raw, when, reason, 0.0, 0.0, 0.0, level, 0.0, None, skip)


def _trade_row(item: Priced, equity: float) -> dict:
    signal = item.signal
    return {
        "symbol": signal.symbol,
        "mode": signal.mode,
        "direction": signal.direction,
        "signal_time": signal.signal_time,
        "fill_time": signal.fill_time,
        "exit_time": item.exit_time,
        "entry": item.fill,
        "exit": item.exit_raw,
        "stop": signal.stop,
        "target": item.level,
        "reason": item.reason,
        "quantity": item.quantity,
        "debit": item.debit,
        "credit": item.credit,
        "pnl": item.pnl,
        "strike": item.strike,
        "outer": signal.outer,
        "equity": equity,
    }


def _hourly_flags(hourly: pd.DataFrame | None):
    if hourly is None or hourly.empty:
        return np.array([], dtype=np.int64), np.array([], dtype=bool), np.array([], dtype=bool)
    bars = rth(hourly)
    if bars.empty:
        return np.array([], dtype=np.int64), np.array([], dtype=bool), np.array([], dtype=bool)
    fast_v = ema(bars["close"].astype(float), 9).to_numpy(dtype=float)
    slow_v = ema(bars["close"].astype(float), 20).to_numpy(dtype=float)
    ends = []
    for stamp in bars.index:
        if stamp.time() >= time(15, 30):
            ends.append(stamp.normalize() + pd.Timedelta(hours=16))
        else:
            ends.append(stamp + pd.Timedelta(hours=1))
    end_index = pd.DatetimeIndex(ends)
    ready = np.isfinite(fast_v) & np.isfinite(slow_v)
    return np.asarray(end_index.asi8, dtype=np.int64), ready & (fast_v > slow_v), ready & (fast_v < slow_v)


def _hourly_agrees(signal: Signal, ends: np.ndarray, long_ok: np.ndarray, short_ok: np.ndarray) -> bool:
    if len(ends) == 0:
        return False
    signal_end = signal.signal_time + pd.Timedelta(minutes=15)
    position = int(np.searchsorted(ends, signal_end.value, side="right") - 1)
    if position < 0:
        return False
    if signal.direction == "long":
        return bool(long_ok[position])
    if signal.direction == "short":
        return bool(short_ok[position])
    return False


def _qqq_known(signal: Signal, bands: pd.DataFrame | None) -> bool:
    if bands is None or signal.signal_time not in bands.index:
        return False
    width = bands.loc[signal.signal_time]
    std = float(width["std"]) if pd.notna(width["std"]) else float("nan")
    vwap = float(width["vwap"]) if pd.notna(width["vwap"]) else float("nan")
    return _finite(std) and std > 0.0 and _finite(vwap)


def _qqq_confirm(signal: Signal, bands: pd.DataFrame | None, closes: pd.Series | None) -> bool:
    if not _qqq_known(signal, bands) or closes is None or signal.signal_time not in closes.index:
        return False
    width = bands.loc[signal.signal_time]
    return closes_beyond(float(closes.loc[signal.signal_time]), float(width["vwap"]), float(width["std"]), signal.direction)


def _stack(direction: str, fast: float, slow: float) -> bool:
    if not _finite(fast) or not _finite(slow):
        return False
    if direction == "long":
        return fast > slow
    if direction == "short":
        return fast < slow
    return False


def _median(values: list[float]) -> float:
    clean = np.asarray([value for value in values if _finite(value)], dtype=float)
    if len(clean) == 0:
        return float("nan")
    return float(np.median(clean))


def _finite(value: float) -> bool:
    return value is not None and bool(np.isfinite(value))


def _clock(stamp: pd.Timestamp) -> time:
    clock = pd.Timestamp(stamp)
    if clock.tzinfo is not None:
        clock = clock.tz_convert(NY)
    return clock.time()
