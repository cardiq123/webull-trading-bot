"""9/20 EMA rejection on 5-minute SPY and QQQ.

The rules in ``frozen_rules`` are the ones that get scored. Nothing here
places an order or imports the sandbox forward test.

A bar uses only prices that have closed. The fill is the next bar's open.
The 15:45 bar is an exit, not an entry. A bar that can reach both the stop
and the target fills the stop. EMAs run across sessions. VWAP resets at
09:30. The gate is the VWAP confluence. The other entry, stop, and target
choices are variants and cannot take the gate.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time
from typing import Optional

import numpy as np
import pandas as pd

from webull_bot.calendar import next_trading_day
from webull_bot.chart_reads.chop_v2 import REL_VOLUME_MAX, VOLUME_WINDOW
from webull_bot.chart_reads.vwap_band import (
    GATE_DRAWDOWN,
    GATE_PF,
    GATE_SHARPE,
    GATE_TRADES,
    HALF_SPREAD_FLOOR,
    HALF_SPREAD_PCT,
    RATE,
    DIVIDEND,
    VOL_CAP,
    VOL_FLOOR,
    metrics_from,
    passes_gate,
    walk_exit,
)
from webull_bot.costs import CostModel, buy_fees, buy_price, sell_price, sell_regulatory_fees
from webull_bot.indicators import atr, ema
from webull_bot.mtf_vwap.detect import rth, session_vwap
from webull_bot.options.fees import CONTRACT_MULTIPLIER, option_leg_fees
from webull_bot.options.pricing import listed_strike, option_price

NY = "America/New_York"
FLAT = time(15, 45)
LAST_SIGNAL = time(15, 35)
EMA_FAST = 9
EMA_SLOW = 20
SLOPE_BARS = 3
TOUCH_ATR = 0.10
VWAP_ATR = 0.10
SPREAD_FLOOR_ATR = 0.10
SLOPE_FLOOR_ATR = 0.05
SWING_WIDTH = 2
ATR_WINDOW = 14
STOP_PAD = 0.01
RISK_FRACTION = 0.01
HOLDOUT_START = date(2022, 1, 1)
TRAIN_END = date(2021, 12, 31)
SAMPLE_END = date(2026, 10, 6)
RANDOM_SEED = 17
GATE_VARIANT = "vwap"
GATE_STOP = "reject"
GATE_TARGET = "swing"

# Re-exported so a reader can see the gate without opening the other module.
__all__ = [
    "FLAT",
    "GATE_DRAWDOWN",
    "GATE_PF",
    "GATE_SHARPE",
    "GATE_TARGET",
    "GATE_TRADES",
    "GATE_VARIANT",
    "HOLDOUT_START",
    "LAST_SIGNAL",
    "RANDOM_SEED",
    "SAMPLE_END",
    "Signal",
    "classify_bar",
    "eligible_fill",
    "explain_bar",
    "find_signals",
    "frozen_rules",
    "indicator_frame",
    "metrics_from",
    "passes_gate",
    "random_signals",
    "simulate",
    "swing_targets",
    "to_five_minute",
    "walk_ema_exit",
]


def frozen_rules() -> dict:
    """Written down before the result is scored. The score does not edit this."""
    return {
        "clock": (
            "5-minute regular-hours bars, 09:30 through 15:55 ET, left-labeled. "
            "The 09:30 bar is 09:30-09:34. The last signal bar is 15:35, so the last fill is 15:40. "
            "15:45 is an exit only."
        ),
        "emas": "EMA 9 and EMA 20 on the concatenated regular-hours bars. They do not reset each session.",
        "vwap": "Session VWAP of typical price, volume-weighted, reset at 09:30. Dukascopy volume is a bid-tick count.",
        "atr": "Wilder ATR(14) on the same 5-minute bars.",
        "slope_bars": SLOPE_BARS,
        "trend": (
            "Short: EMA 9 is below EMA 20, both are lower than they were 3 bars ago, and the close is below both. "
            "Long is the mirror."
        ),
        "entry": (
            "Short: the bar's high is within 0.10 ATR of the 9 EMA and the close is back below the 9 EMA. "
            "Long: the low is within 0.10 ATR of the 9 EMA and the close is back above it. "
            "The fill is the next bar's open."
        ),
        "touch_atr": TOUCH_ATR,
        "vwap_atr": VWAP_ATR,
        "gate_variant": GATE_VARIANT,
        "variants": {
            "ema": "9 EMA tag only. This cannot take the gate.",
            "vwap": "The gate. Session VWAP is within 0.10 ATR of the 9 EMA on the signal bar.",
            "reversal": (
                "Not the gate. From a bearish stack on the prior bar (9 EMA below the 20 EMA, and that close below session VWAP), "
                "a green 5-minute bar whose close is above the 9 EMA, the 20 EMA, and VWAP, then a next bar that also closes green. "
                "The fill is the open of the bar after that confirmation. The mirror, from a bullish stack, buys the put. "
                "The price stop is one cent beyond the breakout bar (under its low for a long, over its high for a short). "
                "A close back across the 9 EMA is the same ema exit the rejection study already scores, and the price stop still fills first. "
                "Swing, 1R, and 2R are the other targets. The chop guard is not part of this variant."
            ),
            "ema20": (
                "The bar does not trade through the 20 EMA. A short high stays at or below it. This cannot take the gate. "
                "With a 0.10 ATR tag and a 0.10 ATR spread floor, a bar that tags the 9 EMA is already short of the 20 EMA, "
                "so this variant matches the 9 EMA rule. It is still scored."
            ),
        },
        "chop": (
            "Part of the rejection variants, not a switch. The reversal variant does not use it. "
            "Skip when this bar's volume is under 0.85 times the prior 20-bar average "
            "(chop v2 REL_VOLUME_MAX and VOLUME_WINDOW). Skip when the 9 and 20 EMAs are under 0.10 ATR apart. "
            "Skip when the 9 EMA's 3-bar move is under 0.05 ATR in the trend direction. "
            "Chop v2's 0.75 ATR stack width is not the spread floor."
        ),
        "rel_volume_max": REL_VOLUME_MAX,
        "volume_window": VOLUME_WINDOW,
        "spread_floor_atr": SPREAD_FLOOR_ATR,
        "slope_floor_atr": SLOPE_FLOOR_ATR,
        "swing": (
            "A 5-bar fractal: two bars on each side, unique extreme, confirmed two bars later. "
            "Bar t does not use a pivot that is still open. The gate target is the most recent confirmed swing low below the fill for a short, "
            "and the most recent confirmed swing high above the fill for a long. No such swing skips the trade."
        ),
        "swing_width": SWING_WIDTH,
        "gate_stop": GATE_STOP,
        "stops": {
            "reject": "The gate. One cent beyond the rejection bar: the high plus one cent for a short, the low minus one cent for a long.",
            "ema20": "The 20 EMA on the signal bar. It does not chase. This cannot take the gate.",
        },
        "gate_target": GATE_TARGET,
        "targets": {
            "swing": "The gate. Prior swing, frozen from swings confirmed by the signal bar.",
            "r1": "1R from the fill to the stop. This cannot take the gate.",
            "r2": "2R from the fill to the stop. This cannot take the gate.",
            "ema": "Exit at the close of the first later bar that closes back across the 9 EMA. A stop on that bar fills first. This cannot take the gate.",
        },
        "flat": "Still open at 15:45 ET is sold at that bar's open. That bar's high and low are ignored. No overnight hold.",
        "same_bar": "If one bar can hit the stop and the target, the stop fills. A gap through either fills at the open. If both, the stop.",
        "one_position": "One open trade. A new signal while it is open is skipped.",
        "shares": (
            "The cash book is long only, because a $1,000 cash account cannot short. "
            "Size risks 1% of equity to the stop and never spends more settled cash than is on hand. "
            "Fractional shares. A sale settles the next session. "
            "A both-directions share book is a research baseline and is not the gate."
        ),
        "options": (
            "One at-the-money contract, listed strike nearest the fill. Calls for longs, puts for shorts. "
            "0 DTE expires 16:00 the same day and is still closed by 15:45. "
            "Skip the trade when the debit does not fit in settled cash. The option book takes both directions."
        ),
        "iv": "Prior session VIX1D close when that print exists, otherwise the prior VIX close, divided by 100. Clipped to 5%-150%.",
        "spread": "Option half-spread is the greater of $0.01 and 1.5% of the model mid. Buy the ask, sell the bid, plus Webull option fees.",
        "model": "Black-Scholes, rate 2%, dividend yield 0. No listed chain. The model is the uncertainty. QQQ uses the same VIX print. The spot is the raw print, with no extra stock slippage inside the model.",
        "costs": "Shares use the repo CostModel: 5 bps slippage, 1 bp half-spread, and the 2026 SEC and FINRA sell fees on the whole sample.",
        "account": "Fresh $1,000 and $5,000. Cash earns zero. Taxes are ignored.",
        "split": "Train is every session through 2021-12-31. Holdout is a fresh account from 2022-01-01 through 2026-10-06.",
        "chart_day": (
            "2026-10-07 is the chart the user pointed at. Dukascopy's 1-minute file ends with the last complete session, "
            "so that day is not in the score. The chart uses Yahoo 5-minute bars when those exist, and it does not invent a bar. "
            "The frozen tolerances are not loosened to force a mark at 10:20 ET."
        ),
        "random": "Seed 17 only. The same number of holdout signals that have a prior swing, after the long-only filter. Random eligible bars, a coin-flip direction, a one-cent stop beyond that bar, and a 1R target.",
        "gate": "Holdout profit factor at least 1.10, Sharpe at least 0.40, max drawdown no worse than -30%, and at least 300 trades.",
        "gate_books": [
            "vwap confluence, rejection-high stop, prior swing, shares cash long-only",
            "vwap confluence, rejection-high stop, prior swing, 0 DTE both directions",
        ],
        "qqq": "A Dukascopy QQQ file is the gate only when it has at least 2000 sessions and at most 80 missing days. A short Yahoo sample cannot pass.",
    }


@dataclass(frozen=True)
class Signal:
    symbol: str
    variant: str
    direction: str
    signal_time: pd.Timestamp
    fill_time: pd.Timestamp
    stop_reject: float
    stop_ema20: float
    swing: float
    ema9: float


def _as_ny(stamp) -> pd.Timestamp:
    clock = pd.Timestamp(stamp)
    if clock.tzinfo is None:
        return clock.tz_localize(NY)
    return clock.tz_convert(NY)


def eligible_fill(signal_time, fill_time) -> bool:
    """True when the next bar is the same session, the signal is by 15:35, and the fill is before 15:45."""
    sig = _as_ny(signal_time)
    nxt = _as_ny(fill_time)
    return sig.date() == nxt.date() and sig.time() <= LAST_SIGNAL and nxt.time() < FLAT


def _finite(*values: float) -> bool:
    return all(np.isfinite(value) for value in values)


def _flags(
    *,
    ema9: float,
    ema20: float,
    ema9_prev: float,
    ema20_prev: float,
    close: float,
    high: float,
    low: float,
    width: float,
    rel_volume: float,
    vwap: float,
) -> dict:
    """Boolean readings. Explain and classify both use this, so the words cannot drift from the score."""
    finite = _finite(ema9, ema20, ema9_prev, ema20_prev, close, high, low, width, vwap) and width > 0.0
    rel_ok = bool(finite and np.isfinite(rel_volume) and rel_volume >= REL_VOLUME_MAX)
    spread = abs(ema9 - ema20) if finite else float("nan")
    spread_atr = spread / width if finite else float("nan")
    slope = (ema9 - ema9_prev) if finite else float("nan")
    slope_atr = slope / width if finite else float("nan")
    tag_short = abs(high - ema9) / width if finite else float("nan")
    tag_long = abs(low - ema9) / width if finite else float("nan")
    vwap_distance = abs(vwap - ema9) / width if finite else float("nan")
    return {
        "finite": finite,
        "rel_ok": rel_ok,
        "spread_ok": bool(finite and spread >= SPREAD_FLOOR_ATR * width),
        "short_stack": bool(finite and ema9 < ema20),
        "long_stack": bool(finite and ema9 > ema20),
        "short_slope_dir": bool(finite and ema9 < ema9_prev),
        "long_slope_dir": bool(finite and ema9 > ema9_prev),
        "ema20_slope_short": bool(finite and ema20 < ema20_prev),
        "ema20_slope_long": bool(finite and ema20 > ema20_prev),
        "short_price": bool(finite and close < ema9 and close < ema20),
        "long_price": bool(finite and close > ema9 and close > ema20),
        "slope_mag_short": bool(finite and (ema9_prev - ema9) >= SLOPE_FLOOR_ATR * width),
        "slope_mag_long": bool(finite and (ema9 - ema9_prev) >= SLOPE_FLOOR_ATR * width),
        "tag_short": bool(finite and abs(high - ema9) <= TOUCH_ATR * width and close < ema9),
        "tag_long": bool(finite and abs(low - ema9) <= TOUCH_ATR * width and close > ema9),
        "vwap_ok": bool(finite and abs(vwap - ema9) <= VWAP_ATR * width),
        "ema20_intact_short": bool(finite and high <= ema20),
        "ema20_intact_long": bool(finite and low >= ema20),
        "tag_short_atr": float(tag_short) if finite else float("nan"),
        "tag_long_atr": float(tag_long) if finite else float("nan"),
        "vwap_distance_atr": float(vwap_distance) if finite else float("nan"),
        "spread_atr": float(spread_atr) if finite else float("nan"),
        "slope_atr": float(slope_atr) if finite else float("nan"),
        "rel_volume": float(rel_volume) if np.isfinite(rel_volume) else float("nan"),
    }


def classify_bar(
    *,
    ema9: float,
    ema20: float,
    ema9_prev: float,
    ema20_prev: float,
    close: float,
    high: float,
    low: float,
    width: float,
    rel_volume: float,
    vwap: float,
) -> Optional[tuple[str, tuple[str, ...]]]:
    """Direction and the variants that fire. None when the shared filters fail."""
    flags = _flags(
        ema9=ema9, ema20=ema20, ema9_prev=ema9_prev, ema20_prev=ema20_prev,
        close=close, high=high, low=low, width=width, rel_volume=rel_volume, vwap=vwap,
    )
    if not flags["finite"] or not flags["rel_ok"] or not flags["spread_ok"]:
        return None
    short = all(flags[name] for name in (
        "short_stack", "short_slope_dir", "ema20_slope_short", "short_price", "slope_mag_short", "tag_short",
    ))
    long = all(flags[name] for name in (
        "long_stack", "long_slope_dir", "ema20_slope_long", "long_price", "slope_mag_long", "tag_long",
    ))
    if short == long:
        return None
    direction = "short" if short else "long"
    names = ["ema"]
    if flags["vwap_ok"]:
        names.append("vwap")
    intact = flags["ema20_intact_short"] if direction == "short" else flags["ema20_intact_long"]
    if intact:
        names.append("ema20")
    return direction, tuple(names)


def _blockers(flags: dict, direction: str) -> list[str]:
    """Why a bar missed the gate. Diagnostic only. The score uses ``classify_bar``."""
    if not flags["finite"]:
        return ["indicator missing"]
    found: list[str] = []
    if not flags["rel_ok"]:
        found.append(f"rel volume {flags['rel_volume']:.2f} is below {REL_VOLUME_MAX:.2f}")
    if not flags["spread_ok"]:
        found.append(f"EMA spread {flags['spread_atr']:.2f} ATR is under {SPREAD_FLOOR_ATR:.2f}")
    if direction == "short":
        checks = (
            ("short_stack", "9 EMA is not below the 20 EMA"),
            ("short_slope_dir", "9 EMA is not lower than 3 bars ago"),
            ("ema20_slope_short", "20 EMA is not lower than 3 bars ago"),
            ("short_price", "close is not below both EMAs"),
            ("slope_mag_short", f"9 EMA slope {flags['slope_atr']:.2f} ATR is flatter than {SLOPE_FLOOR_ATR:.2f}"),
            ("tag_short", f"high is {flags['tag_short_atr']:.2f} ATR from the 9 EMA, or the close is not back below it"),
        )
    elif direction == "long":
        checks = (
            ("long_stack", "9 EMA is not above the 20 EMA"),
            ("long_slope_dir", "9 EMA is not higher than 3 bars ago"),
            ("ema20_slope_long", "20 EMA is not higher than 3 bars ago"),
            ("long_price", "close is not above both EMAs"),
            ("slope_mag_long", f"9 EMA slope {flags['slope_atr']:.2f} ATR is flatter than {SLOPE_FLOOR_ATR:.2f}"),
            ("tag_long", f"low is {flags['tag_long_atr']:.2f} ATR from the 9 EMA, or the close is not back above it"),
        )
    else:
        return found + ["neither the short stack nor the long stack"]
    for key, text in checks:
        if not flags[key]:
            found.append(text)
    if direction == "short" and not flags["vwap_ok"]:
        found.append(f"VWAP is {flags['vwap_distance_atr']:.2f} ATR from the 9 EMA")
    if direction == "long" and not flags["vwap_ok"]:
        found.append(f"VWAP is {flags['vwap_distance_atr']:.2f} ATR from the 9 EMA")
    if direction == "short" and not flags["ema20_intact_short"]:
        found.append("high trades above the 20 EMA")
    if direction == "long" and not flags["ema20_intact_long"]:
        found.append("low trades below the 20 EMA")
    return found


def swing_targets(high: np.ndarray, low: np.ndarray, close: np.ndarray, width: int = SWING_WIDTH) -> tuple[np.ndarray, np.ndarray]:
    """Most recent confirmed swing beyond the close. Confirmed ``width`` bars after the pivot."""
    count = len(close)
    short_target = np.full(count, np.nan)
    long_target = np.full(count, np.nan)
    lows: list[float] = []
    highs: list[float] = []
    low_choice = float("nan")
    high_choice = float("nan")
    for index in range(count):
        confirm = index - width
        if confirm >= width:
            start = confirm - width
            stop = confirm + width + 1
            window_low = low[start:stop]
            window_high = high[start:stop]
            if low[confirm] == window_low.min() and np.sum(window_low == low[confirm]) == 1:
                price = float(low[confirm])
                lows.append(price)
                if price < close[index]:
                    low_choice = price
            if high[confirm] == window_high.max() and np.sum(window_high == high[confirm]) == 1:
                price = float(high[confirm])
                highs.append(price)
                if price > close[index]:
                    high_choice = price
        if np.isfinite(low_choice) and low_choice >= close[index]:
            low_choice = float("nan")
            for price in reversed(lows):
                if price < close[index]:
                    low_choice = price
                    break
        if np.isfinite(high_choice) and high_choice <= close[index]:
            high_choice = float("nan")
            for price in reversed(highs):
                if price > close[index]:
                    high_choice = price
                    break
        short_target[index] = low_choice
        long_target[index] = high_choice
    return short_target, long_target


def to_five_minute(minutes: pd.DataFrame) -> pd.DataFrame:
    """Left-labeled 5-minute bars. The 09:30 bar is 09:30 through 09:34."""
    if minutes is None or minutes.empty:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    pieces = []
    for _day, chunk in minutes.groupby(minutes.index.date):
        five = chunk.resample("5min", label="left", closed="left").agg(
            {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
        )
        five = five.dropna(subset=["open"])
        if five.empty:
            continue
        clock_ = five.index.time
        five = five[(clock_ >= time(9, 30)) & (clock_ < time(16, 0))]
        if not five.empty:
            pieces.append(five)
    if not pieces:
        return minutes.iloc[0:0]
    out = pd.concat(pieces)
    return out[~out.index.duplicated(keep="last")].sort_index()


def indicator_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Causal 9/20 EMA, ATR, session VWAP, relative volume, and confirmed swings."""
    bars = rth(frame)
    if bars.empty:
        return bars
    close = bars["close"].astype(float)
    fast = ema(close, EMA_FAST)
    slow = ema(close, EMA_SLOW)
    width = atr(bars, ATR_WINDOW)
    volume = bars["volume"].astype(float) if "volume" in bars.columns else pd.Series(np.nan, index=bars.index)
    prior = volume.shift(1).rolling(VOLUME_WINDOW, min_periods=VOLUME_WINDOW).mean()
    try:
        vwap = session_vwap(bars)["vwap"].reindex(bars.index)
    except (KeyError, TypeError, ValueError):
        vwap = pd.Series(np.nan, index=bars.index)
    short_swing, long_swing = swing_targets(bars["high"].to_numpy(float), bars["low"].to_numpy(float), close.to_numpy(float))
    out = bars.copy()
    out["ema9"] = fast
    out["ema20"] = slow
    out["ema9_prev"] = fast.shift(SLOPE_BARS)
    out["ema20_prev"] = slow.shift(SLOPE_BARS)
    out["atr"] = width
    out["rel_volume"] = volume / prior
    out["vwap"] = vwap
    out["swing_low"] = short_swing
    out["swing_high"] = long_swing
    return out


def find_signals(frame: pd.DataFrame, symbol: str) -> list[Signal]:
    """Every variant that fires. The research book picks one variant."""
    ind = indicator_frame(frame)
    count = len(ind)
    if count < VOLUME_WINDOW + EMA_SLOW + SLOPE_BARS + 2:
        return []
    ema9 = ind["ema9"].to_numpy(dtype=float)
    ema20 = ind["ema20"].to_numpy(dtype=float)
    ema9_prev = ind["ema9_prev"].to_numpy(dtype=float)
    ema20_prev = ind["ema20_prev"].to_numpy(dtype=float)
    close = ind["close"].to_numpy(dtype=float)
    high = ind["high"].to_numpy(dtype=float)
    low = ind["low"].to_numpy(dtype=float)
    width = ind["atr"].to_numpy(dtype=float)
    rel = ind["rel_volume"].to_numpy(dtype=float)
    vwap = ind["vwap"].to_numpy(dtype=float)
    swing_low = ind["swing_low"].to_numpy(dtype=float)
    swing_high = ind["swing_high"].to_numpy(dtype=float)
    index = ind.index
    dates = index.date
    clocks = index.time
    found: list[Signal] = []
    for i in range(count - 1):
        if dates[i] != dates[i + 1] or clocks[i] > LAST_SIGNAL or clocks[i + 1] >= FLAT:
            continue
        hit = classify_bar(
            ema9=ema9[i], ema20=ema20[i], ema9_prev=ema9_prev[i], ema20_prev=ema20_prev[i],
            close=close[i], high=high[i], low=low[i], width=width[i], rel_volume=rel[i], vwap=vwap[i],
        )
        if hit is None:
            continue
        direction, variants = hit
        swing = float(swing_low[i] if direction == "short" else swing_high[i])
        stop_reject = float(high[i]) + STOP_PAD if direction == "short" else float(low[i]) - STOP_PAD
        for name in variants:
            found.append(
                Signal(
                    symbol, name, direction, index[i], index[i + 1],
                    stop_reject, float(ema20[i]), swing, float(ema9[i]),
                )
            )
    found.extend(_reversal_signals(ind, symbol))
    return found


def _reversal_signals(ind: pd.DataFrame, symbol: str) -> list[Signal]:
    """Stack, then a close through 9/20/VWAP, then a same-color confirmation.

    The signal bar is the confirmation. The fill is the next open. The stop
    is one cent beyond the breakout bar, not the confirmation bar.
    """
    count = len(ind)
    if count < 4:
        return []
    opened = ind["open"].to_numpy(dtype=float)
    ema9 = ind["ema9"].to_numpy(dtype=float)
    ema20 = ind["ema20"].to_numpy(dtype=float)
    close = ind["close"].to_numpy(dtype=float)
    high = ind["high"].to_numpy(dtype=float)
    low = ind["low"].to_numpy(dtype=float)
    vwap = ind["vwap"].to_numpy(dtype=float)
    swing_low = ind["swing_low"].to_numpy(dtype=float)
    swing_high = ind["swing_high"].to_numpy(dtype=float)
    index = ind.index
    dates = index.date
    clocks = index.time
    found: list[Signal] = []
    for i in range(1, count - 2):
        if dates[i] != dates[i - 1] or dates[i] != dates[i + 1] or dates[i] != dates[i + 2]:
            continue
        if clocks[i + 1] > LAST_SIGNAL or clocks[i + 2] >= FLAT:
            continue
        prior = (ema9[i - 1], ema20[i - 1], close[i - 1], vwap[i - 1])
        here = (opened[i], close[i], ema9[i], ema20[i], vwap[i], low[i], high[i])
        confirm = (opened[i + 1], close[i + 1])
        if not _finite(*prior, *here, *confirm):
            continue
        long = (
            ema9[i - 1] < ema20[i - 1]
            and close[i - 1] < vwap[i - 1]
            and close[i] > opened[i]
            and close[i] > ema9[i]
            and close[i] > ema20[i]
            and close[i] > vwap[i]
            and close[i + 1] > opened[i + 1]
        )
        short = (
            ema9[i - 1] > ema20[i - 1]
            and close[i - 1] > vwap[i - 1]
            and close[i] < opened[i]
            and close[i] < ema9[i]
            and close[i] < ema20[i]
            and close[i] < vwap[i]
            and close[i + 1] < opened[i + 1]
        )
        if long == short:
            continue
        direction = "long" if long else "short"
        stop = float(low[i]) - STOP_PAD if direction == "long" else float(high[i]) + STOP_PAD
        swing = float(swing_high[i + 1] if direction == "long" else swing_low[i + 1])
        found.append(
            Signal(
                symbol, "reversal", direction, index[i + 1], index[i + 2],
                stop, float(ema20[i + 1]), swing, float(ema9[i + 1]),
            )
        )
    return found


def explain_bar(frame: pd.DataFrame, when) -> dict:
    """Readings at one bar. This does not change a tolerance to force a signal."""
    target = _as_ny(when)
    ind = indicator_frame(frame)
    if ind.empty or target not in ind.index:
        return {"found": False, "stamp": str(target)}
    row = ind.loc[target]
    if isinstance(row, pd.DataFrame):
        row = row.iloc[-1]
    flags = _flags(
        ema9=float(row["ema9"]),
        ema20=float(row["ema20"]),
        ema9_prev=float(row["ema9_prev"]),
        ema20_prev=float(row["ema20_prev"]),
        close=float(row["close"]),
        high=float(row["high"]),
        low=float(row["low"]),
        width=float(row["atr"]),
        rel_volume=float(row["rel_volume"]),
        vwap=float(row["vwap"]),
    )
    hit = classify_bar(
        ema9=float(row["ema9"]),
        ema20=float(row["ema20"]),
        ema9_prev=float(row["ema9_prev"]),
        ema20_prev=float(row["ema20_prev"]),
        close=float(row["close"]),
        high=float(row["high"]),
        low=float(row["low"]),
        width=float(row["atr"]),
        rel_volume=float(row["rel_volume"]),
        vwap=float(row["vwap"]),
    )
    direction = ""
    if flags["short_stack"] or flags["short_price"] or flags["tag_short"]:
        direction = "short"
    if flags["long_stack"] or flags["long_price"] or flags["tag_long"]:
        direction = "long" if direction == "" else ""
    if hit is not None:
        direction = hit[0]
    return {
        "found": True,
        "stamp": str(target),
        "open": float(row["open"]),
        "high": float(row["high"]),
        "low": float(row["low"]),
        "close": float(row["close"]),
        "ema9": float(row["ema9"]) if np.isfinite(row["ema9"]) else None,
        "ema20": float(row["ema20"]) if np.isfinite(row["ema20"]) else None,
        "vwap": float(row["vwap"]) if np.isfinite(row["vwap"]) else None,
        "atr": float(row["atr"]) if np.isfinite(row["atr"]) else None,
        "direction": direction,
        "variants": list(hit[1]) if hit is not None else [],
        "gate": bool(hit is not None and "vwap" in hit[1]),
        "blockers": _blockers(flags, direction),
        "swing_low": float(row["swing_low"]) if np.isfinite(row["swing_low"]) else None,
        "swing_high": float(row["swing_high"]) if np.isfinite(row["swing_high"]) else None,
    }


def walk_ema_exit(
    session: pd.DataFrame,
    fill_loc: int,
    direction: str,
    stop: float,
    ema9: pd.Series,
) -> tuple[str, float, pd.Timestamp]:
    """Stop first. Otherwise the first close back across the 9 EMA, filled at that close. 15:45 exits at the open."""
    last_reason = "last_bar"
    last_price = float(session.iloc[-1]["close"])
    last_time = session.index[-1]
    for j in range(fill_loc, len(session)):
        row = session.iloc[j]
        stamp = session.index[j]
        opened = float(row["open"])
        high = float(row["high"])
        low = float(row["low"])
        close = float(row["close"])
        if stamp.time() >= FLAT:
            return "flat", opened, stamp
        level = float(ema9.iloc[j]) if j < len(ema9) else float("nan")
        if direction == "long":
            if opened <= stop or low <= stop:
                price = opened if opened <= stop else stop
                return "stop", price, stamp
            if np.isfinite(level) and close < level:
                return "ema", close, stamp
        else:
            if opened >= stop or high >= stop:
                price = opened if opened >= stop else stop
                return "stop", price, stamp
            if np.isfinite(level) and close > level:
                return "ema", close, stamp
        last_price = close
        last_time = stamp
    return last_reason, last_price, last_time


def _years(when: pd.Timestamp, dte: int) -> float:
    clock = _as_ny(when)
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
    return _as_ny(stamp).date()


def _target_level(signal: Signal, fill: float, stop: float, target: str) -> Optional[float]:
    if target == "swing":
        level = float(signal.swing)
        if not np.isfinite(level):
            return None
        if signal.direction == "short" and not level < fill:
            return None
        if signal.direction == "long" and not level > fill:
            return None
        return level
    if target in ("r1", "r2"):
        multiple = 1.0 if target == "r1" else 2.0
        risk = abs(fill - stop)
        if risk <= 0:
            return None
        if signal.direction == "long":
            return fill + multiple * risk
        return fill - multiple * risk
    if target == "ema":
        return float(signal.ema9)
    raise ValueError(f"unknown target {target}")


def simulate(
    frame: pd.DataFrame,
    signals: list[Signal],
    *,
    stop: str,
    target: str,
    kind: str,
    stake: float,
    long_only: bool,
    iv_points: dict[date, tuple[float, str]] | None = None,
    start: date | None = None,
    end: date | None = None,
    costs: CostModel | None = None,
) -> dict:
    """Fresh account. ``kind`` is ``shares`` or ``0dte``. ``stop`` is ``reject`` or ``ema20``."""
    if kind not in ("shares", "0dte"):
        raise ValueError("kind must be shares or 0dte")
    if stop not in ("reject", "ema20"):
        raise ValueError("stop must be reject or ema20")
    if target not in ("swing", "r1", "r2", "ema"):
        raise ValueError("target must be swing, r1, r2, or ema")
    model = costs or CostModel()
    points = iv_points or {}
    bars = rth(frame)
    # The exit EMA is the same series the signal used. Slicing first would warm it up again.
    ema9 = ema(bars["close"].astype(float), EMA_FAST) if target == "ema" and not bars.empty else None
    if start is not None or end is not None:
        keep = [stamp for stamp in bars.index if (start is None or _day_key(stamp) >= start) and (end is None or _day_key(stamp) <= end)]
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
    chosen.sort(key=lambda item: (item.fill_time, item.variant))

    settled = float(stake)
    unsettled: list[tuple[date, float]] = []
    equity = float(stake)
    curve: list[tuple[pd.Timestamp, float]] = []
    trades: list[dict] = []
    skips = {"short": 0, "overlap": 0, "no_bar": 0, "iv": 0, "premium": 0, "dust": 0, "bust": 0, "swing": 0}
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
            stop_price = float(signal.stop_reject if stop == "reject" else signal.stop_ema20)
            if fill <= 0 or not np.isfinite(stop_price):
                skips["no_bar"] += 1
                continue
            if signal.direction == "long" and not stop_price < fill:
                skips["dust"] += 1
                continue
            if signal.direction == "short" and not stop_price > fill:
                skips["dust"] += 1
                continue
            distance = abs(fill - stop_price)
            level = _target_level(signal, fill, stop_price, target)
            if target == "swing" and level is None:
                skips["swing"] += 1
                continue
            if level is None:
                skips["dust"] += 1
                continue
            if target == "ema":
                series = ema9.reindex(session.index) if ema9 is not None else pd.Series(np.nan, index=session.index)
                reason, exit_raw, exit_time = walk_ema_exit(session, loc, signal.direction, stop_price, series)
                level = exit_raw
            else:
                reason, exit_raw, exit_time = walk_exit(session, loc, signal.direction, stop_price, level)
            if kind == "shares":
                trade = _share_trade(signal, fill, exit_raw, exit_time, reason, level, distance, settled, equity, model)
            else:
                iv = _iv_on(day, points)
                if iv is None:
                    skips["iv"] += 1
                    continue
                trade = _option_trade(signal, fill, exit_raw, exit_time, reason, level, iv, settled)
            if trade is None:
                skips["premium" if kind != "shares" else "dust"] += 1
                continue
            if trade["debit"] > settled + 1e-9:
                skips["premium" if kind != "shares" else "dust"] += 1
                continue
            settled -= trade["debit"]
            unsettled.append((next_trading_day(day), trade["credit"]))
            equity = settled + sum(amount for _when, amount in unsettled)
            trade["equity"] = equity
            trades.append(trade)
            busy = exit_time
            if equity <= 1.0:
                stopped = True
        curve.append((pd.Timestamp(day.isoformat()), equity))

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
) -> dict | None:
    risk_dollars = RISK_FRACTION * equity
    if signal.direction == "long":
        entry_px = buy_price(fill, costs)
        exit_px = sell_price(exit_raw, costs)
        room = settled / entry_px if entry_px > 0 else 0.0
        quantity = min(room, risk_dollars / distance)
        if quantity <= 1e-8:
            return None
        debit = quantity * entry_px + buy_fees(costs)
        credit = quantity * exit_px - sell_regulatory_fees(exit_px, quantity, costs)
    else:
        entry_px = sell_price(fill, costs)
        exit_px = buy_price(exit_raw, costs)
        room = settled / fill if fill > 0 else 0.0
        quantity = min(room, risk_dollars / distance)
        if quantity <= 1e-8:
            return None
        debit = quantity * exit_px
        credit = quantity * entry_px - sell_regulatory_fees(entry_px, quantity, costs)
        if debit > settled:
            quantity = settled / exit_px if exit_px > 0 else 0.0
            if quantity <= 1e-8:
                return None
            debit = quantity * exit_px
            credit = quantity * entry_px - sell_regulatory_fees(entry_px, quantity, costs)
    return _row(signal, fill, exit_raw, exit_time, reason, level, quantity, debit, credit, credit - debit, None)


def _option_trade(
    signal: Signal,
    fill: float,
    exit_raw: float,
    exit_time: pd.Timestamp,
    reason: str,
    level: float,
    iv: float,
    settled: float,
) -> dict | None:
    right = "call" if signal.direction == "long" else "put"
    strike = listed_strike(fill, fill)
    entry_mid = _option_mid(right, fill, strike, signal.fill_time, iv, 0)
    exit_mid = _option_mid(right, exit_raw, strike, exit_time, iv, 0)
    entry_ask = entry_mid + _half_spread(entry_mid)
    exit_bid = max(0.0, exit_mid - _half_spread(exit_mid))
    debit = entry_ask * CONTRACT_MULTIPLIER + option_leg_fees(1, entry_ask, sell=False)
    if debit <= 0 or debit > settled + 1e-9:
        return None
    credit = exit_bid * CONTRACT_MULTIPLIER - option_leg_fees(1, exit_bid, sell=True)
    return _row(signal, fill, exit_raw, exit_time, reason, level, 1.0, debit, credit, credit - debit, strike)


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
        "variant": signal.variant,
        "direction": signal.direction,
        "signal_time": signal.signal_time,
        "fill_time": signal.fill_time,
        "exit_time": exit_time,
        "entry": fill,
        "exit": exit_raw,
        "stop": signal.stop_reject,
        "target": level,
        "reason": reason,
        "quantity": quantity,
        "debit": debit,
        "credit": credit,
        "pnl": pnl,
        "strike": strike,
    }


def random_signals(frame: pd.DataFrame, symbol: str, count: int, seed: int = RANDOM_SEED) -> list[Signal]:
    """Same count of entries on random eligible bars. Direction is a coin flip. The book applies a 1R target."""
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
            if not eligible_fill(stamp, nxt):
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
        found.append(Signal(symbol, "random", direction, stamp, nxt, stop, float("nan"), float("nan"), float("nan")))
    found.sort(key=lambda item: item.fill_time)
    return found
