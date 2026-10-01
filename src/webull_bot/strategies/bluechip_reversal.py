"""Dow 30 reversal off a confirmed low.

Pre-registered before the out-of-sample run. The grid is the six variants
in ``param_grid`` and nothing else. 8/20/21 EMAs, other pivot widths, and
other hold times were not searched.

Default, fixed before seeing the 2017–2026 result:

* Universe: point-in-time Dow 30 (``universe_dow``).
* Support: the low tags the latest confirmed 5/5 swing low, or the 200-day
  EMA, within 1.5 percent. A swing is confirmed ``pivot_right`` bars after
  it prints, so the signal does not use the bars that confirm it early.
* RSI(2) below 10 at some point in the last three sessions.
* Bullish divergence on RSI(14): the new swing low is a lower price and a
  higher RSI(14) than the previous confirmed swing low. Divergence stays
  on RSI(14) even when the oversold check is RSI(2) or RSI(5).
* Trigger: the close reclaims the 10-day EMA (yesterday at or below, today
  above). The alternate trigger is a reclaim of VWAP anchored at that swing.
* Trend filter off by default. The variant turns it on (close above the
  200-day EMA).
* Stop: the swing low minus 0.25 ATR. Target: the last confirmed swing high
  if it is above the close. Time stop: 15 sessions.
* Fill is the next open. Leaving the Dow schedules an exit on the first
  session the name is no longer a member.

The options expression is not part of this signal. It reprices these stock
trades. See ``webull_bot.options``.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from webull_bot.indicators import atr, ema, rsi
from webull_bot.strategies.base import Strategy
from webull_bot.strategies.signals import blank, limit_symbols
from webull_bot.universe_dow import all_dow_tickers, is_member


def confirmed_pivot_low(low: pd.Series, left: int, right: int) -> pd.Series:
    """Price of a swing low confirmed on this bar, else NaN.

    Bar ``t`` confirms the low at ``t - right``. That low is the unique
    minimum of ``[t - right - left, t]``.
    """
    values = low.to_numpy(dtype=float)
    out = np.full(len(values), np.nan)
    for t in range(left + right, len(values)):
        i = t - right
        window = values[i - left : t + 1]
        pivot = values[i]
        if not np.isfinite(pivot):
            continue
        if pivot == np.nanmin(window) and int(np.sum(window == pivot)) == 1:
            out[t] = pivot
    return pd.Series(out, index=low.index)


def confirmed_pivot_high(high: pd.Series, left: int, right: int) -> pd.Series:
    values = high.to_numpy(dtype=float)
    out = np.full(len(values), np.nan)
    for t in range(left + right, len(values)):
        i = t - right
        window = values[i - left : t + 1]
        pivot = values[i]
        if not np.isfinite(pivot):
            continue
        if pivot == np.nanmax(window) and int(np.sum(window == pivot)) == 1:
            out[t] = pivot
    return pd.Series(out, index=high.index)


def bullish_divergence(low: pd.Series, rsi_series: pd.Series, left: int, right: int) -> pd.Series:
    """True on the bar that confirms a lower price low with a higher RSI."""
    values = low.to_numpy(dtype=float)
    rsi_values = rsi_series.to_numpy(dtype=float)
    flag = np.zeros(len(values), dtype=bool)
    prev_price = np.nan
    prev_rsi = np.nan
    for t in range(left + right, len(values)):
        i = t - right
        window = values[i - left : t + 1]
        pivot = values[i]
        if not np.isfinite(pivot) or pivot != np.nanmin(window) or int(np.sum(window == pivot)) != 1:
            continue
        rsi_at_pivot = rsi_values[i]
        if np.isfinite(prev_price) and np.isfinite(prev_rsi) and np.isfinite(rsi_at_pivot):
            if pivot < prev_price and rsi_at_pivot > prev_rsi:
                flag[t] = True
        prev_price = pivot
        prev_rsi = rsi_at_pivot
    return pd.Series(flag, index=low.index)


def anchored_vwap(frame: pd.DataFrame, pivot_low: pd.Series, right: int) -> pd.Series:
    """VWAP from the confirmed swing's own bar through today."""
    typical = ((frame["high"] + frame["low"] + frame["close"]) / 3.0).to_numpy(dtype=float)
    volume = frame["volume"].to_numpy(dtype=float)
    confirmed = pivot_low.notna().to_numpy()
    out = np.full(len(typical), np.nan)
    anchor = -1
    pv = 0.0
    vol = 0.0
    for t in range(len(typical)):
        if confirmed[t]:
            anchor = t - right
            pv = 0.0
            vol = 0.0
            for j in range(max(anchor, 0), t + 1):
                v = volume[j]
                if not np.isfinite(v) or v < 0:
                    v = 0.0
                pv += typical[j] * v
                vol += v
        elif anchor >= 0:
            v = volume[t]
            if not np.isfinite(v) or v < 0:
                v = 0.0
            pv += typical[t] * v
            vol += v
        if vol > 0:
            out[t] = pv / vol
    return pd.Series(out, index=frame.index)


def member_mask(symbol: str, index: pd.Index) -> pd.Series:
    flags = []
    for ts in index:
        flags.append(is_member(symbol, pd.Timestamp(ts).date()))
    return pd.Series(flags, index=index)


def recent(flag: pd.Series, window: int = 3) -> pd.Series:
    return flag.fillna(False).astype(float).rolling(window, min_periods=1).max().fillna(0).astype(bool)


def reclaims(close: pd.Series, level: pd.Series) -> pd.Series:
    """True when the close crosses back above ``level``.

    Yesterday's close has to be at or below yesterday's level. A close that
    was already above the level is not a new reclaim.
    """
    return ((close > level) & (close.shift(1) <= level.shift(1))).fillna(False)


class BluechipReversal(Strategy):
    name = "bluechip_reversal"
    citation = (
        "Point-in-time Dow 30 (S&P Dow Jones historical component changes). "
        "Reversal off a confirmed swing low or the 200-day EMA after RSI "
        "washes out, with bullish divergence and a 10-day EMA reclaim. "
        "Options P&L, when reported, is a Black-Scholes estimate."
    )
    style = "swing"
    holds_overnight = True
    survivorship_sensitive = False
    custom_universe = True
    short_sample = False
    trail_pct = None
    default_params = {
        "rsi_length": 2,
        "rsi_entry": 10,
        "trigger": "ema10",
        "trend_filter": False,
        "require_divergence": True,
        "pivot_left": 5,
        "pivot_right": 5,
        "support_pct": 0.015,
        "max_hold": 15,
        "stop_atr": 0.25,
    }

    def universe(self, mode: str) -> list[str]:
        if mode == "dow":
            return all_dow_tickers()
        return []

    def param_grid(self) -> list[dict[str, Any]]:
        """Six pre-registered variants. Not a cartesian product."""
        variants = [
            {},
            {"rsi_length": 14, "rsi_entry": 30},
            {"rsi_length": 5, "rsi_entry": 15},
            {"trigger": "avwap"},
            {"trend_filter": True},
            {"require_divergence": False},
        ]
        grid = []
        for update in variants:
            params = dict(self.default_params)
            params.update(update)
            grid.append(params)
        return grid

    def generate(self, bars, regime, params):
        del regime
        out: dict[str, pd.DataFrame] = {}
        left = int(params["pivot_left"])
        right = int(params["pivot_right"])
        support_pct = float(params["support_pct"])
        for symbol, frame in limit_symbols(bars, params).items():
            if len(frame) < left + right + 5:
                continue
            close = frame["close"]
            low = frame["low"]
            high = frame["high"]
            member = member_mask(symbol, frame.index)
            pivot_low = confirmed_pivot_low(low, left, right)
            last_low = pivot_low.ffill()
            ema200 = ema(close, 200)
            near_pivot = last_low.notna() & (low <= last_low * (1.0 + support_pct))
            near_ema = ema200.notna() & (low <= ema200 * (1.0 + support_pct))
            rsi_now = rsi(close, int(params["rsi_length"]))
            oversold = recent(rsi_now < float(params["rsi_entry"]))
            divergence = recent(bullish_divergence(low, rsi(close, 14), left, right))
            if params["trigger"] == "avwap":
                level = anchored_vwap(frame, pivot_low, right)
            else:
                level = ema(close, 10)
            reclaim = reclaims(close, level)
            if params["trend_filter"]:
                trend_ok = ema200.notna() & (close > ema200)
            else:
                trend_ok = pd.Series(True, index=frame.index)
            div_ok = divergence if params["require_divergence"] else pd.Series(True, index=frame.index)
            entry = recent(near_pivot | near_ema) & oversold & reclaim.fillna(False) & trend_ok & div_ok & member
            entry = entry & level.notna() & last_low.notna()
            stop = last_low - float(params["stop_atr"]) * atr(frame, 14)
            swing_high = confirmed_pivot_high(high, left, right).ffill()
            target = swing_high.where(swing_high > close)
            # First session out of the index. shift(1) is the prior session,
            # which is already known; this does not read the next bar.
            was_member = member.shift(1).fillna(False)
            signals = blank(frame.index)
            signals["entry_next_open"] = entry.fillna(False).to_numpy()
            signals["exit_next_open"] = (was_member & ~member).fillna(False).to_numpy()
            signals["stop_price"] = stop.to_numpy()
            signals["take_profit"] = target.to_numpy()
            signals["max_hold"] = int(params["max_hold"])
            out[symbol] = signals
        return out
