"""Opposite 2 SD VWAP-band exit. Backtests only. Does not place an order.

A long takes the upper band. A short takes the lower band. The band is the
session band on that bar, and it counts only when it is beyond the fill.
The combined exit sells half at the first of that band and the 200 EMA, and
the rest at the other or on a close back across the 9 EMA. One option
contract cannot be split, so it sells at the first of those two.
"""

from __future__ import annotations

from datetime import time

import numpy as np
import pandas as pd

from webull_bot.options.pricing import option_price

RATE = 0.02
DIVIDEND = 0.0
HALF_SPREAD_PCT = 0.015
HALF_SPREAD_FLOOR = 0.01
BAND_SD = 2.0
NY = "America/New_York"


def opposite_band(direction: str, vwap: float, std: float, fill: float) -> float | None:
    """Upper 2 SD for a long, lower 2 SD for a short, only when that side is past the fill."""
    if not _finite(vwap, std, fill) or std < 0.0 or fill <= 0.0:
        return None
    level = vwap + BAND_SD * std if direction == "long" else vwap - BAND_SD * std
    if direction == "long" and not level > fill:
        return None
    if direction == "short" and not level < fill:
        return None
    return float(level)


def _beyond(direction: str, level: float, fill: float) -> float | None:
    if not _finite(level, fill):
        return None
    if direction == "long" and level > fill:
        return float(level)
    if direction == "short" and level < fill:
        return float(level)
    return None


def _finite(*values: float) -> bool:
    return all(np.isfinite(value) for value in values)


def _tag(direction: str, opened: float, high: float, low: float, level: float | None) -> float | None:
    if level is None:
        return None
    if direction == "long":
        if opened >= level:
            return float(opened)
        if high >= level:
            return float(level)
    else:
        if opened <= level:
            return float(opened)
        if low <= level:
            return float(level)
    return None


def _nearer(direction: str, hits: list[tuple[str, float, float]]) -> list[tuple[str, float, float]]:
    return sorted(hits, key=lambda item: item[1] if direction == "long" else -item[1])


def walk_band(
    *,
    direction: str,
    fill: float,
    stop: float,
    fill_i: int,
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    stamps: pd.DatetimeIndex,
    ema9: np.ndarray,
    ema200: np.ndarray,
    vwap: np.ndarray,
    std: np.ndarray,
    flat: time,
    mode: str,
    split_half: bool,
    session_end: int,
    iv: float | None = None,
    strike: float | None = None,
    entry_ask: float | None = None,
    dte: int = 0,
) -> dict | None:
    """Stop first. Then the profit target. Then a close back across the 9 EMA. Flat at ``flat``."""
    if mode not in ("band", "band200", "prem50", "prem100"):
        raise ValueError(f"unknown band exit {mode}")
    if fill <= 0 or not np.isfinite(stop):
        return None
    if direction == "long" and not stop < fill:
        return None
    if direction == "short" and not stop > fill:
        return None
    target_mult = 1.5 if mode == "prem50" else 2.0 if mode == "prem100" else None
    right = "call" if direction == "long" else "put"
    scaled = False
    scale_spot = None
    scale_time = None
    waiting: str | None = None
    last_spot = float(fill)
    last_time = stamps[fill_i]
    for j in range(fill_i, session_end):
        opened = float(open_[j])
        bar_high = float(high[j])
        bar_low = float(low[j])
        closed = float(close[j])
        stamp = stamps[j]
        level9 = float(ema9[j]) if j < len(ema9) else float("nan")
        if stamp.time() >= flat:
            return _path(direction, fill, stop, "flat", opened, stamp, scaled, scale_spot, scale_time, None)
        if direction == "long" and (opened <= stop or bar_low <= stop):
            price = opened if opened <= stop else stop
            return _path(direction, fill, stop, "stop", price, stamp, scaled, scale_spot, scale_time, None)
        if direction == "short" and (opened >= stop or bar_high >= stop):
            price = opened if opened >= stop else stop
            return _path(direction, fill, stop, "stop", price, stamp, scaled, scale_spot, scale_time, None)
        if target_mult is not None and entry_ask is not None and strike is not None and iv is not None:
            open_bid = _bid(right, opened, strike, stamp, iv, dte)
            extreme = bar_high if direction == "long" else bar_low
            extreme_bid = _bid(right, extreme, strike, stamp, iv, dte)
            if open_bid >= target_mult * entry_ask:
                return _path(direction, fill, stop, mode, opened, stamp, False, None, None, open_bid)
            if extreme_bid >= target_mult * entry_ask:
                return _path(direction, fill, stop, mode, extreme, stamp, False, None, None, target_mult * entry_ask)
        if mode in ("band", "band200"):
            band_level = opposite_band(direction, float(vwap[j]), float(std[j]), fill)
            ema_level = _beyond(direction, float(ema200[j]), fill)
            levels = {"band": band_level, "ema200": ema_level}
            if scaled and waiting is not None:
                price = _tag(direction, opened, bar_high, bar_low, levels[waiting])
                if price is not None:
                    return _path(direction, fill, stop, waiting, price, stamp, True, scale_spot, scale_time, None)
            elif not scaled:
                names = ("band",) if mode == "band" else ("band", "ema200")
                hits = []
                for name in names:
                    price = _tag(direction, opened, bar_high, bar_low, levels[name])
                    if price is not None:
                        hits.append((name, float(levels[name]), price))
                if hits:
                    ordered = _nearer(direction, hits)
                    name, _level, price = ordered[0]
                    both = mode == "band200" and band_level is not None and ema_level is not None
                    if both and split_half:
                        if len(ordered) > 1:
                            second = ordered[1]
                            return _path(
                                direction, fill, stop, second[0], second[2], stamp, True, price, stamp, None,
                            )
                        if _crossed(direction, closed, level9):
                            return _path(direction, fill, stop, "ema", closed, stamp, True, price, stamp, None)
                        scaled = True
                        scale_spot = price
                        scale_time = stamp
                        waiting = "ema200" if name == "band" else "band"
                    else:
                        return _path(direction, fill, stop, name, price, stamp, False, None, None, None)
        if _crossed(direction, closed, level9):
            return _path(direction, fill, stop, "ema", closed, stamp, scaled, scale_spot, scale_time, None)
        last_spot = closed
        last_time = stamp
    return _path(direction, fill, stop, "last", last_spot, last_time, scaled, scale_spot, scale_time, None)


def _crossed(direction: str, closed: float, level: float) -> bool:
    if not _finite(closed, level):
        return False
    if direction == "long":
        return closed < level
    return closed > level


def _path(direction, fill, stop, reason, spot, stamp, scaled, scale_spot, scale_time, premium) -> dict:
    return {
        "direction": direction,
        "fill": float(fill),
        "stop": float(stop),
        "reason": reason,
        "exit_spot": float(spot),
        "exit_time": stamp,
        "scaled": bool(scaled),
        "scale_spot": None if scale_spot is None else float(scale_spot),
        "scale_time": scale_time,
        "premium": None if premium is None else float(premium),
    }


def _half_spread(mid: float) -> float:
    return max(HALF_SPREAD_FLOOR, HALF_SPREAD_PCT * max(mid, 0.0))


def _years(when: pd.Timestamp, dte: int = 0) -> float:
    clock = pd.Timestamp(when)
    if clock.tzinfo is None:
        clock = clock.tz_localize(NY)
    else:
        clock = clock.tz_convert(NY)
    expiry = clock.normalize() + pd.Timedelta(days=int(dte), hours=16)
    minutes = max(1.0, (expiry - clock).total_seconds() / 60.0)
    return minutes / (365.0 * 24.0 * 60.0)


def _option_mid(right: str, spot: float, strike: float, when: pd.Timestamp, iv: float, dte: int = 0) -> float:
    if spot <= 0 or strike <= 0 or iv <= 0:
        return 0.0
    return float(option_price(right, spot, strike, _years(when, dte), iv, RATE, DIVIDEND))


def _bid(right: str, spot: float, strike: float, when: pd.Timestamp, iv: float, dte: int = 0) -> float:
    mid = _option_mid(right, spot, strike, when, iv, dte)
    return max(0.0, mid - _half_spread(mid))
