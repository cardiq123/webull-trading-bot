"""Re-entry after a 2 SD VWAP-band tag. Backtests only. Does not place an order.

A long tags the upper band, prints a red candle that closes back under it, then
a pullback that tests the 20 EMA and closes back above it. The fill is the next
open. A short is the mirror. The standalone book does not need a prior position.
The add-on book keeps a re-entry only when that band tag is the bar where a base
reversal exited at the band.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd

from webull_bot.calendar import next_trading_day
from webull_bot.chart_reads.band_exit import opposite_band, walk_band
from webull_bot.chart_reads.ema_reclaim import (
    FLAT,
    LAST_CONFIRM,
    RANDOM_SEED,
    RISK_FRACTION,
    TOUCH_ATR,
    Prepared,
    walk,
)
from webull_bot.chart_reads.vwap_band import VOL_CAP, VOL_FLOOR, metrics_from
from webull_bot.costs import CostModel, buy_fees, buy_price, sell_price, sell_regulatory_fees
from webull_bot.options.fees import CONTRACT_MULTIPLIER, option_leg_fees
from webull_bot.options.pricing import listed_strike, option_price

NY = "America/New_York"
RATE = 0.02
DIVIDEND = 0.0
HALF_SPREAD_PCT = 0.015
HALF_SPREAD_FLOOR = 0.01


def frozen_rules() -> dict:
    """Written down before the result is scored. The score does not edit this."""
    return {
        "name": "spy_5m_band_reentry",
        "clock": (
            "5-minute regular-hours bars. The hold bar is at or before 15:20 ET so the fill is before 15:30. "
            "Still open at 15:30 is sold at that bar's open."
        ),
        "tag": (
            "A bar trades the opposite 2 standard deviation session VWAP band: the high reaches the upper band for a long, "
            "the low reaches the lower band for a short. The session standard deviation has to be positive. A zero-width open is not a tag."
        ),
        "rejection": (
            "A red candle after that tag, or the tag bar itself when it is red, closes back under the upper band. "
            "The short mirror is a green candle that closes back above the lower band."
        ),
        "pullback": (
            "A later bar tests the 20 EMA within 0.10 ATR and closes back on the near side of it: above the 20 for a long, "
            "below the 20 for a short. The primary also requires the trade color, green for a long and red for a short. "
            "A hold of any color is the looser variant. The fill is the next open. One position at a time."
        ),
        "stop": (
            "The primary stop is a close back through the 20 EMA, filled at that close. A gap through the 20 EMA at the open "
            "fills at the open. A close back through VWAP is the other stop. The two stops are scored separately."
        ),
        "target": (
            "The opposite 2 SD band again, or the 200 EMA when it is beyond the fill. A tag during the bar fills the target. "
            "The close-based stop is checked after that tag. The two targets are scored separately."
        ),
        "standalone": "The continuation does not need a position already open. It is its own book.",
        "addon": (
            "An add-on keeps the re-entry only when the band tag is the same bar where a base reversal exited at that band. "
            "The base books are the simpler 9 EMA reversal, the strict five-step reclaim, and the reclaim that drops the crack. "
            "The campaign account takes the base band exit and then the re-entry. The re-entry is also scored on its own account."
        ),
        "flat": "15:30 ET open. No overnight hold.",
        "shares": "Cash book is long only. Size risks 1% of equity to the stop level on the fill bar.",
        "options": "One at-the-money 0 DTE contract. Calls for longs, puts for shorts. Both directions.",
        "chart_day": (
            "2026-10-07 is the illustration. The first bar that meets a step is the one that is marked. "
            "The rule is not moved onto a later print, and a missing 20 EMA test is left missing."
        ),
        "not_live": "Not a live strategy. Nothing is added to the optional or selected lists.",
    }


@dataclass(frozen=True)
class Reentry:
    symbol: str
    variant: str
    direction: str
    tag_i: int
    reject_i: int
    signal_i: int
    fill_i: int


def find_reentries(prep: Prepared, symbol: str) -> list[Reentry]:
    """Green hold and any-color hold. Each pass consumes the tag it used."""
    found: list[Reentry] = []
    for start, end in _sessions(prep):
        found.extend(_scan(prep, symbol, start, end, "long", "green", True))
        found.extend(_scan(prep, symbol, start, end, "long", "hold", False))
        found.extend(_scan(prep, symbol, start, end, "short", "green", True))
        found.extend(_scan(prep, symbol, start, end, "short", "hold", False))
    return found


def _scan(prep: Prepared, symbol: str, start: int, end: int, direction: str, variant: str, need_color: bool) -> list[Reentry]:
    found: list[Reentry] = []
    tag = None
    reject = None
    last = end - 1
    for i in range(start, last):
        level = _band(prep, i, direction)
        if _tagged(prep, i, direction, level):
            tag = i
            reject = i if _rejected(prep, i, direction, level) else None
            continue
        if tag is None or level is None:
            continue
        if reject is None:
            if _rejected(prep, i, direction, level):
                reject = i
            continue
        if not _holds(prep, i, direction):
            continue
        if need_color and not _trade_color(prep, i, direction):
            continue
        fill = i + 1
        if prep.dates[fill] != prep.dates[i] or prep.times[i] > LAST_CONFIRM or prep.times[fill] >= FLAT:
            continue
        found.append(Reentry(symbol, variant, direction, tag, reject, i, fill))
        tag = None
        reject = None
    return found


def walk_reentry(prep: Prepared, item: Reentry, target: str, stop_name: str) -> dict | None:
    """Close through the stop level, after a target tag on that bar. Flat at 15:30."""
    if target not in ("band", "ema200") or stop_name not in ("ema9", "ema20", "vwap"):
        raise ValueError("unknown re-entry exit")
    fill_i = item.fill_i
    if fill_i >= len(prep.close):
        return None
    fill = float(prep.open[fill_i])
    planned = _level(prep, fill_i, stop_name)
    if fill <= 0 or planned is None:
        return None
    if item.direction == "long" and not planned < fill:
        return None
    if item.direction == "short" and not planned > fill:
        return None
    end = _session_end(prep, fill_i)
    last_spot = fill
    last_time = prep.index[fill_i]
    for j in range(fill_i, end):
        opened = float(prep.open[j])
        high = float(prep.high[j])
        low = float(prep.low[j])
        closed = float(prep.close[j])
        stamp = prep.index[j]
        stop_level = _level(prep, j, stop_name)
        if prep.times[j] >= FLAT:
            return _path(item, fill, planned, "flat", opened, stamp)
        if stop_level is not None and _gapped_stop(item.direction, opened, stop_level):
            return _path(item, fill, planned, "stop", opened, stamp)
        goal = _target(prep, j, item.direction, fill, target)
        if goal is not None and _tagged(prep, j, item.direction, goal):
            price = opened if _gapped_target(item.direction, opened, goal) else goal
            return _path(item, fill, planned, target, price, stamp)
        if stop_level is not None and _through_close(item.direction, closed, stop_level):
            return _path(item, fill, planned, "stop", closed, stamp)
        last_spot = closed
        last_time = stamp
    return _path(item, fill, planned, "last", last_spot, last_time)


def simulate(
    prep: Prepared,
    items: list[Reentry],
    *,
    target: str,
    stop_name: str,
    kind: str,
    stake: float,
    long_only: bool,
    iv_points: dict | None = None,
    start: date | None = None,
    end: date | None = None,
    costs: CostModel | None = None,
) -> dict:
    """Fresh account. ``kind`` is shares or 0dte."""
    paths = []
    for item in items:
        day = prep.dates[item.fill_i]
        if start is not None and day < start:
            continue
        if end is not None and day > end:
            continue
        if long_only and item.direction != "long":
            continue
        path = walk_reentry(prep, item, target, stop_name)
        if path is not None:
            paths.append(path)
    return simulate_paths(prep, paths, kind=kind, stake=stake, long_only=long_only, iv_points=iv_points, start=start, end=end, costs=costs)


def simulate_paths(
    prep: Prepared,
    paths: list[dict],
    *,
    kind: str,
    stake: float,
    long_only: bool,
    iv_points: dict | None = None,
    start: date | None = None,
    end: date | None = None,
    costs: CostModel | None = None,
) -> dict:
    """One position. Paths already carry the fill, the stop distance, and the exit."""
    if kind not in ("shares", "0dte"):
        raise ValueError("kind must be shares or 0dte")
    model = costs or CostModel()
    points = iv_points or {}
    chosen = [path for path in paths if _in_window(prep, path, start, end) and not (long_only and path["direction"] != "long")]
    chosen.sort(key=lambda path: path["fill_i"])
    days = []
    for day in prep.dates:
        if days and days[-1] == day:
            continue
        if start is not None and day < start:
            continue
        if end is not None and day > end:
            continue
        days.append(day)
    settled = float(stake)
    unsettled: list[tuple[date, float]] = []
    equity = float(stake)
    curve = []
    trades = []
    skips = {"short": 0, "overlap": 0, "iv": 0, "premium": 0, "dust": 0, "bust": 0}
    busy = None
    cursor = 0
    stopped = False
    for day in days:
        if not stopped:
            still = []
            for available_on, amount in unsettled:
                if available_on <= day:
                    settled += amount
                else:
                    still.append((available_on, amount))
            unsettled = still
            equity = settled + sum(amount for _when, amount in unsettled)
        while cursor < len(chosen) and prep.dates[chosen[cursor]["fill_i"]] == day:
            path = chosen[cursor]
            cursor += 1
            if stopped or equity <= 1.0:
                skips["bust"] += 1
                continue
            if busy is not None and prep.index[path["fill_i"]] <= busy:
                skips["overlap"] += 1
                continue
            iv = _iv_on(day, points) if kind == "0dte" else None
            if kind == "0dte" and iv is None:
                skips["iv"] += 1
                continue
            if kind == "shares":
                trade = _share_trade(path, settled, equity, model)
            else:
                trade = _option_trade(prep, path, iv, settled)
            if trade is None:
                skips["premium" if kind == "0dte" else "dust"] += 1
                continue
            if trade["debit"] > settled + 1e-9:
                skips["premium" if kind == "0dte" else "dust"] += 1
                continue
            settled -= trade["debit"]
            unsettled.append((next_trading_day(day), trade["credit"]))
            equity = settled + sum(amount for _when, amount in unsettled)
            trade["equity"] = equity
            trades.append(trade)
            busy = path["exit_time"]
            if equity <= 1.0:
                stopped = True
        curve.append((pd.Timestamp(day.isoformat()), equity))
    equity_series = pd.Series([value for _stamp, value in curve], index=pd.DatetimeIndex([stamp for stamp, _value in curve]), dtype=float)
    stats = metrics_from(equity_series, [float(trade["pnl"]) for trade in trades], float(stake))
    return {"equity": equity_series, "trades": trades, "skips": skips, "metrics": stats}


def base_band_keys(prep: Prepared, setups: list, signals: list | None = None) -> set[tuple]:
    """(session date, direction, exit timestamp) for base trades that exit at the band."""
    keys: set[tuple] = set()
    for setup in setups:
        path = walk(prep, setup, "band")
        if path is None or path["reason"] != "band":
            continue
        keys.add((prep.dates[setup.fill_i], setup.direction, path["exit_time"]))
    for signal in signals or []:
        if getattr(signal, "variant", "") != "reversal":
            continue
        fill_i = _index_at(prep, signal.fill_time)
        if fill_i is None:
            continue
        path = walk_band(
            direction=signal.direction,
            fill=float(prep.open[fill_i]),
            stop=float(signal.stop_reject),
            fill_i=fill_i,
            open_=prep.open,
            high=prep.high,
            low=prep.low,
            close=prep.close,
            stamps=prep.index,
            ema9=prep.ema9,
            ema200=prep.ema200,
            vwap=prep.vwap,
            std=prep.std,
            flat=FLAT,
            mode="band",
            split_half=False,
            session_end=_session_end(prep, fill_i),
        )
        if path is None or path["reason"] != "band":
            continue
        keys.add((prep.dates[fill_i], signal.direction, path["exit_time"]))
    return keys


def addons(prep: Prepared, items: list[Reentry], keys: set[tuple]) -> list[Reentry]:
    """Re-entries whose band tag is a base band-exit bar."""
    return [item for item in items if (prep.dates[item.tag_i], item.direction, prep.index[item.tag_i]) in keys]


def campaign_paths(prep: Prepared, setups: list, items: list[Reentry], target: str, stop_name: str) -> tuple[list[dict], list[dict]]:
    """Base band-exit paths, and those paths plus the linked re-entries."""
    base = []
    for setup in setups:
        path = walk(prep, setup, "band")
        if path is None:
            continue
        path = dict(path)
        path["fill_i"] = setup.fill_i
        base.append(path)
    extra = []
    for item in items:
        path = walk_reentry(prep, item, target, stop_name)
        if path is not None:
            extra.append(path)
    return base, base + extra


def illustrate(prep: Prepared, day: date) -> dict:
    """Long green re-entries on one session, plus a tag that never got a hold.

    A later tag replaces an unfinished one, the same way the scanner does.
    A missing hold stays missing.
    """
    indexes = [i for i, stamp in enumerate(prep.dates) if stamp == day]
    if not indexes:
        return {"found": False, "steps": [], "pending_tag": None, "pending_reject": None}
    start, end = indexes[0], indexes[-1] + 1
    steps = []
    tag = None
    reject = None
    last = end - 1
    for i in range(start, last):
        level = _band(prep, i, "long")
        if _tagged(prep, i, "long", level):
            tag = i
            reject = i if _rejected(prep, i, "long", level) else None
            continue
        if tag is None or level is None:
            continue
        if reject is None:
            if _rejected(prep, i, "long", level):
                reject = i
            continue
        if not _holds(prep, i, "long") or not _trade_color(prep, i, "long"):
            continue
        fill = i + 1
        if prep.dates[fill] != prep.dates[i] or prep.times[i] > LAST_CONFIRM or prep.times[fill] >= FLAT:
            continue
        steps.append({"tag": tag, "reject": reject, "hold": i, "fill": fill})
        tag = None
        reject = None
    return {"found": True, "steps": steps, "pending_tag": tag, "pending_reject": reject}


def reversal_paths(prep: Prepared, signals: list) -> list[dict]:
    """Band-exit paths for the simpler reversal. The account applies them later."""
    paths = []
    for signal in signals:
        if getattr(signal, "variant", "") != "reversal":
            continue
        fill_i = _index_at(prep, signal.fill_time)
        if fill_i is None:
            continue
        path = walk_band(
            direction=signal.direction,
            fill=float(prep.open[fill_i]),
            stop=float(signal.stop_reject),
            fill_i=fill_i,
            open_=prep.open,
            high=prep.high,
            low=prep.low,
            close=prep.close,
            stamps=prep.index,
            ema9=prep.ema9,
            ema200=prep.ema200,
            vwap=prep.vwap,
            std=prep.std,
            flat=FLAT,
            mode="band",
            split_half=False,
            session_end=_session_end(prep, fill_i),
        )
        if path is None:
            continue
        path = dict(path)
        path["fill_i"] = fill_i
        path["variant"] = "reversal"
        paths.append(path)
    return paths


def random_reentries(
    prep: Prepared,
    count: int,
    seed: int = RANDOM_SEED,
    *,
    start: date | None = None,
    end: date | None = None,
) -> list[Reentry]:
    """Same count of coin-flip entries. The book applies the re-entry stop and target."""
    if count <= 0:
        return []
    eligible = []
    for i in range(len(prep.close) - 1):
        day = prep.dates[i + 1]
        if start is not None and day < start:
            continue
        if end is not None and day > end:
            continue
        if prep.dates[i] != prep.dates[i + 1]:
            continue
        if prep.times[i] > LAST_CONFIRM or prep.times[i + 1] >= FLAT:
            continue
        eligible.append(i)
    if not eligible:
        return []
    rng = np.random.default_rng(seed)
    picks = rng.choice(len(eligible), size=count, replace=count > len(eligible))
    sides = rng.integers(0, 2, size=count)
    found = []
    for pick, side in zip(picks, sides):
        i = int(eligible[int(pick)])
        direction = "long" if int(side) == 0 else "short"
        found.append(Reentry("SPY", "random", direction, i, i, i, i + 1))
    found.sort(key=lambda item: item.fill_i)
    return found


def signals_per_month(prep: Prepared, items: list[Reentry], start: date, end: date) -> float | None:
    count = sum(1 for item in items if start <= prep.dates[item.fill_i] <= end)
    months = (end.year - start.year) * 12 + (end.month - start.month) + 1
    if months <= 0:
        return None
    return count / months


def _sessions(prep: Prepared) -> list[tuple[int, int]]:
    spans = []
    start = 0
    for i in range(1, len(prep.dates) + 1):
        if i == len(prep.dates) or prep.dates[i] != prep.dates[start]:
            spans.append((start, i))
            start = i
    return spans


def _session_end(prep: Prepared, i: int) -> int:
    end = i + 1
    while end < len(prep.dates) and prep.dates[end] == prep.dates[i]:
        end += 1
    return end


def _band(prep: Prepared, i: int, direction: str) -> float | None:
    vwap = float(prep.vwap[i])
    std = float(prep.std[i])
    if not _finite(vwap, std) or std <= 0:
        return None
    level = vwap + 2.0 * std if direction == "long" else vwap - 2.0 * std
    return float(level)


def _tagged(prep: Prepared, i: int, direction: str, level: float | None) -> bool:
    if level is None or not np.isfinite(level):
        return False
    if direction == "long":
        return float(prep.high[i]) >= level or float(prep.open[i]) >= level
    return float(prep.low[i]) <= level or float(prep.open[i]) <= level


def _rejected(prep: Prepared, i: int, direction: str, level: float) -> bool:
    opened = float(prep.open[i])
    closed = float(prep.close[i])
    if direction == "long":
        return closed < opened and closed < level
    return closed > opened and closed > level


def _holds(prep: Prepared, i: int, direction: str) -> bool:
    width = float(prep.atr[i])
    ema20 = float(prep.ema20[i])
    if not _finite(width, ema20) or width <= 0:
        return False
    if direction == "long":
        return float(prep.low[i]) <= ema20 + TOUCH_ATR * width and float(prep.close[i]) > ema20
    return float(prep.high[i]) >= ema20 - TOUCH_ATR * width and float(prep.close[i]) < ema20


def _trade_color(prep: Prepared, i: int, direction: str) -> bool:
    if direction == "long":
        return float(prep.close[i]) > float(prep.open[i])
    return float(prep.close[i]) < float(prep.open[i])


def _level(prep: Prepared, i: int, name: str) -> float | None:
    if name == "ema9":
        value = float(prep.ema9[i])
    elif name == "ema20":
        value = float(prep.ema20[i])
    elif name == "vwap":
        value = float(prep.vwap[i])
    else:
        return None
    if not np.isfinite(value):
        return None
    return value


def _target(prep: Prepared, i: int, direction: str, fill: float, name: str) -> float | None:
    if name == "band":
        return opposite_band(direction, float(prep.vwap[i]), float(prep.std[i]), fill)
    return _beyond(direction, float(prep.ema200[i]), fill)


def _beyond(direction: str, level: float, fill: float) -> float | None:
    if not _finite(level, fill):
        return None
    if direction == "long" and level > fill:
        return float(level)
    if direction == "short" and level < fill:
        return float(level)
    return None


def _gapped_stop(direction: str, opened: float, level: float) -> bool:
    if direction == "long":
        return opened <= level
    return opened >= level


def _gapped_target(direction: str, opened: float, level: float) -> bool:
    if direction == "long":
        return opened >= level
    return opened <= level


def _through_close(direction: str, closed: float, level: float) -> bool:
    if direction == "long":
        return closed < level
    return closed > level


def _finite(*values: float) -> bool:
    return all(np.isfinite(value) for value in values)


def _path(item: Reentry, fill: float, stop: float, reason: str, spot: float, stamp) -> dict:
    return {
        "direction": item.direction,
        "variant": item.variant,
        "fill": float(fill),
        "stop": float(stop),
        "reason": reason,
        "exit_spot": float(spot),
        "exit_time": stamp,
        "fill_i": item.fill_i,
        "tag_i": item.tag_i,
        "signal_i": item.signal_i,
    }


def _index_at(prep: Prepared, stamp) -> int | None:
    try:
        loc = prep.index.get_loc(stamp)
    except KeyError:
        return None
    if isinstance(loc, slice) or not isinstance(loc, int):
        return None
    return loc


def _in_window(prep: Prepared, path: dict, start: date | None, end: date | None) -> bool:
    day = prep.dates[path["fill_i"]]
    if start is not None and day < start:
        return False
    if end is not None and day > end:
        return False
    return True


def _share_trade(path: dict, settled: float, equity: float, costs: CostModel) -> dict | None:
    if path["direction"] != "long":
        return None
    fill = float(path["fill"])
    distance = abs(fill - float(path["stop"]))
    if distance <= 0:
        return None
    entry_px = buy_price(fill, costs)
    room = settled / entry_px if entry_px > 0 else 0.0
    quantity = min(room, RISK_FRACTION * equity / distance)
    if quantity <= 1e-8:
        return None
    exit_px = sell_price(float(path["exit_spot"]), costs)
    debit = quantity * entry_px + buy_fees(costs)
    credit = quantity * exit_px - sell_regulatory_fees(exit_px, quantity, costs)
    return _row(path, quantity, debit, credit, credit - debit, None)


def _option_trade(prep: Prepared, path: dict, iv: float, settled: float) -> dict | None:
    fill = float(path["fill"])
    right = "call" if path["direction"] == "long" else "put"
    strike = listed_strike(fill, fill)
    when = prep.index[path["fill_i"]]
    entry_mid = _option_mid(right, fill, strike, when, iv)
    entry_ask = entry_mid + _half_spread(entry_mid)
    debit = entry_ask * CONTRACT_MULTIPLIER + option_leg_fees(1, entry_ask, sell=False)
    if debit <= 0 or debit > settled + 1e-9:
        return None
    bid = _bid(right, float(path["exit_spot"]), strike, path["exit_time"], iv)
    credit = bid * CONTRACT_MULTIPLIER - option_leg_fees(1, bid, sell=True)
    return _row(path, 1.0, debit, credit, credit - debit, strike)


def _row(path: dict, quantity: float, debit: float, credit: float, pnl: float, strike: float | None) -> dict:
    return {
        "direction": path["direction"],
        "variant": path.get("variant", ""),
        "fill_i": path["fill_i"],
        "exit_time": path["exit_time"],
        "entry": path["fill"],
        "exit": path["exit_spot"],
        "reason": path["reason"],
        "quantity": quantity,
        "debit": debit,
        "credit": credit,
        "pnl": pnl,
        "strike": strike,
    }


def _half_spread(mid: float) -> float:
    return max(HALF_SPREAD_FLOOR, HALF_SPREAD_PCT * max(mid, 0.0))


def _years(when: pd.Timestamp) -> float:
    clock = pd.Timestamp(when)
    if clock.tzinfo is None:
        clock = clock.tz_localize(NY)
    else:
        clock = clock.tz_convert(NY)
    expiry = clock.normalize() + pd.Timedelta(hours=16)
    minutes = max(1.0, (expiry - clock).total_seconds() / 60.0)
    return minutes / (365.0 * 24.0 * 60.0)


def _option_mid(right: str, spot: float, strike: float, when: pd.Timestamp, iv: float) -> float:
    if spot <= 0 or strike <= 0 or iv <= 0:
        return 0.0
    return float(option_price(right, spot, strike, _years(when), iv, RATE, DIVIDEND))


def _bid(right: str, spot: float, strike: float, when: pd.Timestamp, iv: float) -> float:
    mid = _option_mid(right, spot, strike, when, iv)
    return max(0.0, mid - _half_spread(mid))


def _iv_on(day: date, iv_points: dict) -> float | None:
    point = iv_points.get(day)
    if point is None:
        return None
    raw = float(point[0])
    if not np.isfinite(raw) or raw <= 0:
        return None
    return min(VOL_CAP, max(VOL_FLOOR, raw / 100.0))
