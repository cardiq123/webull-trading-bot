"""Fixed contract counts, longer expiries, and a 1-minute exit check.

The signals stay the ones already scored. A 1-minute bar is the finest
Dukascopy print in this cache. It stands in for a 5-second check. Nothing
here places an order.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from webull_bot.chart_reads.vwap_band import walk_exit

# A missing print more than this far after the signal bar is not an entry.
ENTRY_GAP = pd.Timedelta(minutes=10)
MINUTE_ROOT = Path("/workspace/data/cache/vwap_band/dukascopy")


def load_minutes(symbol: str) -> pd.DataFrame:
    """One-minute Dukascopy bars, 2017-02-16 through 2026-10-06 when the cache is complete."""
    root = MINUTE_ROOT / symbol
    if not root.is_dir():
        raise FileNotFoundError(f"no 1-minute cache for {symbol}")
    frames = [pd.read_csv(path) for path in sorted(root.glob("*.csv"))]
    if not frames:
        raise FileNotFoundError(f"no 1-minute files for {symbol}")
    raw = pd.concat(frames, ignore_index=True)
    raw["timestamp"] = pd.to_datetime(raw["timestamp"], utc=True).dt.tz_convert("America/New_York")
    frame = raw.set_index("timestamp").sort_index()
    frame = frame[~frame.index.duplicated(keep="last")]
    return frame[["open", "high", "low", "close", "volume"]].astype(float)


def retime(structures: list[dict], minutes: pd.DataFrame) -> tuple[list[dict], dict]:
    """Enter at the first 1-minute open after the signal bar, and exit on the first touch.

    The first 1-minute open at the signal's fill time is the next 5-minute or
    15-minute open on this file, so the entry usually matches the current
    backtest. The exit does not. Each minute can hit the stop or the target.
    When both trade inside one coarser bar, the earlier minute decides. When
    both trade inside one minute, the stop still wins, because the file has
    no 5-second bars.
    """
    by_day: dict[date, pd.DataFrame] = {}
    for day, session in minutes.groupby(minutes.index.date):
        key = day if isinstance(day, date) else pd.Timestamp(day).date()
        by_day[key] = session
    index = minutes.index
    stats = {
        "signals": 0,
        "kept": 0,
        "missing": 0,
        "through_stop": 0,
        "entry_changed": 0,
        "exit_reason_changed": 0,
        "exit_price_changed": 0,
    }
    found: list[dict] = []
    for item in structures:
        stats["signals"] += 1
        session = by_day.get(item["day"])
        if session is None or "stop" not in item or "direction" not in item:
            stats["missing"] += 1
            continue
        fill_time = pd.Timestamp(item["fill_time"])
        later = session.loc[session.index >= fill_time]
        if later.empty:
            stats["missing"] += 1
            continue
        stamp = pd.Timestamp(later.index[0])
        if stamp > fill_time + ENTRY_GAP:
            stats["missing"] += 1
            continue
        opened = float(later.iloc[0]["open"])
        stop = float(item["stop"])
        direction = str(item["direction"])
        if not _on_side(direction, opened, stop):
            stats["through_stop"] += 1
            continue
        risk = abs(opened - stop)
        if risk <= 0:
            stats["through_stop"] += 1
            continue
        target = opened + risk if direction == "long" else opened - risk
        loc = int(session.index.get_loc(stamp))
        reason, exit_raw, when = walk_exit(session, loc, direction, stop, target)
        when = pd.Timestamp(when)
        fill_i = _loc(index, stamp)
        exit_i = _loc(index, when)
        if fill_i is None or exit_i is None:
            stats["missing"] += 1
            continue
        if abs(opened - float(item["fill"])) > 1e-6 or stamp != fill_time:
            stats["entry_changed"] += 1
        if item.get("reason") not in (None, reason):
            stats["exit_reason_changed"] += 1
        if abs(float(exit_raw) - float(item["exit"])) > 1e-6:
            stats["exit_price_changed"] += 1
        stats["kept"] += 1
        found.append(
            {
                "day": item["day"],
                "due": item["due"],
                "fill_i": fill_i,
                "exit_i": exit_i,
                "fill": opened,
                "exit": float(exit_raw),
                "fill_time": stamp,
                "exit_time": when,
                "right": item["right"],
                "direction": direction,
                "stop": stop,
                "reason": reason,
            }
        )
    return found, stats


def _on_side(direction: str, price: float, stop: float) -> bool:
    if direction == "long":
        return price > stop
    return price < stop


def _loc(index: pd.DatetimeIndex, stamp: pd.Timestamp) -> int | None:
    try:
        loc = index.get_loc(stamp)
    except KeyError:
        return None
    if isinstance(loc, slice):
        return int(loc.start)
    if isinstance(loc, int):
        return loc
    return None
