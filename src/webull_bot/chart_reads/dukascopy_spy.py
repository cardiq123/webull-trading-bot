"""Free SPY 1-minute bars from Dukascopy's public bid-candle feed.

Dukascopy publishes SPY (instrument ``SPYUSUSD``) without an account. Each
file is one UTC day of 1-minute bid candles. Prices are bids, not the
consolidated tape. The cache lives under ``data/cache/``, which is gitignored.
This module does not place an order.
"""

from __future__ import annotations

import lzma
import struct
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, time as clock, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from webull_bot.calendar import is_trading_day

NY = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")
SCALE = 1000.0
ROOT = Path("data/cache/orb_mwf/dukascopy")
DAY_DIR = ROOT / "days"
BARS_PATH = ROOT / "SPY_1m.csv"
DONE_PATH = ROOT / "COMPLETE"
START = date(2017, 2, 16)
# The feed's first listed session. A later first print is reported, not invented.
END = date(2026, 10, 6)


def _day_url(day: date) -> str:
    # One UTC day of 1-minute bid candles. The cash session sits inside that UTC date.
    return (
        "https://datafeed.dukascopy.com/datafeed/SPYUSUSD/"
        f"{day.year}/{day.month - 1:02d}/{day.day:02d}/BID_candles_min_1.bi5"
    )


def _fetch(day: date) -> bytes | None:
    """Raw bi5 bytes, or None when that session was never published."""
    request = urllib.request.Request(_day_url(day), headers={"User-Agent": "Mozilla/5.0"})
    delay = 1.0
    for _attempt in range(8):
        try:
            with urllib.request.urlopen(request, timeout=40) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
            time.sleep(delay)
            delay = min(delay * 2, 30.0)
        except (urllib.error.URLError, TimeoutError, OSError):
            time.sleep(delay)
            delay = min(delay * 2, 30.0)
    raise RuntimeError(f"Dukascopy failed for {_day_url(day)}")


def _minutes(raw: bytes, day: date) -> dict[pd.Timestamp, list[float]]:
    """1-minute bid bars. Record order is time, open, close, low, high, volume."""
    if not raw:
        return {}
    try:
        payload = lzma.decompress(raw)
    except lzma.LZMAError:
        return {}
    origin = datetime(day.year, day.month, day.day, tzinfo=UTC)
    buckets: dict[pd.Timestamp, list[float]] = {}
    for offset in range(0, len(payload) - 23, 24):
        second, open_i, close_i, low_i, high_i, volume = struct.unpack(">IIIIIf", payload[offset : offset + 24])
        if volume <= 0 or open_i <= 0 or high_i <= 0 or low_i <= 0:
            continue
        stamp = (origin + timedelta(seconds=int(second))).astimezone(NY)
        bar = pd.Timestamp(stamp.replace(second=0, microsecond=0))
        if bar.date() != day or bar.time() < clock(9, 30) or bar.time() >= clock(16, 0):
            continue
        opened = open_i / SCALE
        closed = close_i / SCALE
        high = high_i / SCALE
        low = low_i / SCALE
        buckets[bar] = [opened, high, low, closed, float(volume)]
    return buckets


def _day_path(day: date) -> Path:
    return DAY_DIR / f"{day.isoformat()}.csv"


def _day_done(day: date) -> bool:
    # The writer renames into place only after every hour for that session
    # has been fetched, so a present file is a finished session.
    return _day_path(day).exists()


def _write_day(day: date, buckets: dict[pd.Timestamp, list[float]]) -> None:
    path = _day_path(day)
    temporary = path.with_suffix(".tmp")
    if not buckets:
        temporary.write_text("timestamp,open,high,low,close,volume\n")
        temporary.replace(path)
        return
    rows = sorted(buckets.items())
    lines = ["timestamp,open,high,low,close,volume"]
    for stamp, (opened, high, low, closed, count) in rows:
        lines.append(
            f"{stamp.isoformat()},{opened:.4f},{high:.4f},{low:.4f},{closed:.4f},{int(count)}"
        )
    temporary.write_text("\n".join(lines) + "\n")
    temporary.replace(path)


def _one_day(day: date) -> str:
    if _day_done(day):
        return "cached"
    try:
        raw = _fetch(day)
    except RuntimeError as exc:
        print(f"DUKASCOPY FAIL {day.isoformat()} {exc}", flush=True)
        return "fail"
    buckets = _minutes(raw or b"", day)
    _write_day(day, buckets)
    return "empty" if not buckets else "ok"


# Tuesday and Thursday are not traded. October 6, 2026 is kept for the chart.
CHART_DAYS = {date(2026, 10, 6)}


def study_days(start: date = START, end: date = END) -> list[date]:
    return [day for day in trading_days(start, end) if day.weekday() in (0, 2, 4) or day in CHART_DAYS]


def trading_days(start: date = START, end: date = END) -> list[date]:
    days = []
    cursor = start
    while cursor <= end:
        if is_trading_day(cursor):
            days.append(cursor)
        cursor += timedelta(days=1)
    return days


def download(workers: int = 4) -> Path:
    """Download any missing sessions, newest first, and write the combined 1-minute file."""
    DAY_DIR.mkdir(parents=True, exist_ok=True)
    days = study_days()
    pending = [day for day in reversed(days) if not _day_done(day)]
    print(f"DUKASCOPY days {len(days)} pending {len(pending)}", flush=True)
    done = len(days) - len(pending)
    failed = 0
    if pending:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_one_day, day): day for day in pending}
            for future in as_completed(futures):
                if future.result() == "fail":
                    failed += 1
                done += 1
                if done % 25 == 0 or done == len(days):
                    print(f"DUKASCOPY {done}/{len(days)} failed {failed}", flush=True)
    frames = []
    for day in days:
        path = _day_path(day)
        if not path.exists() or path.stat().st_size < 40:
            continue
        frame = pd.read_csv(path)
        if frame.empty:
            continue
        frames.append(frame)
    if not frames:
        raise RuntimeError("Dukascopy returned no SPY sessions")
    combined = pd.concat(frames, ignore_index=True)
    combined.to_csv(BARS_PATH, index=False)
    first = str(combined["timestamp"].iloc[0])[:10]
    last = str(combined["timestamp"].iloc[-1])[:10]
    if failed == 0:
        DONE_PATH.write_text(f"{first} {last} {len(combined)}\n")
    print(f"DUKASCOPY WROTE {BARS_PATH} {first} {last} {len(combined)} failed {failed}", flush=True)
    return BARS_PATH


def load_minutes() -> pd.DataFrame | None:
    if not BARS_PATH.exists():
        return None
    frame = pd.read_csv(BARS_PATH)
    if frame.empty:
        return None
    index = pd.to_datetime(frame["timestamp"], utc=True).dt.tz_convert(NY)
    out = frame.drop(columns=["timestamp"])
    out.index = pd.DatetimeIndex(index)
    out = out[~out.index.duplicated(keep="last")].sort_index()
    return out


def to_five_minute(minutes: pd.DataFrame) -> pd.DataFrame:
    """Left-labeled 5-minute bars. The 09:30 bar is 09:30 through 09:34."""
    pieces = []
    for _day, chunk in minutes.groupby(minutes.index.date):
        five = chunk.resample("5min", label="left", closed="left").agg(
            {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
        )
        five = five.dropna(subset=["open"])
        if not five.empty:
            pieces.append(five)
    if not pieces:
        return minutes.iloc[0:0]
    return pd.concat(pieces)


def prices_are_bid_scale(frame: pd.DataFrame) -> bool:
    """Bid candles are quoted in thousandths. A tick-mid file is not this feed."""
    if frame.empty:
        return True
    for column in ("open", "high", "low", "close"):
        scaled = frame[column].astype(float) * SCALE
        if ((scaled - scaled.round()).abs() > 1e-4).any():
            return False
    return True


def load_study_minutes() -> tuple[pd.DataFrame | None, dict]:
    """Load finished Monday/Wednesday/Friday sessions. Missing or mixed files do not score."""
    days = study_days()
    missing: list[str] = []
    empty: list[str] = []
    poison: list[str] = []
    frames: list[pd.DataFrame] = []
    for day in days:
        path = _day_path(day)
        if not path.exists():
            missing.append(day.isoformat())
            continue
        frame = pd.read_csv(path)
        if frame.empty:
            empty.append(day.isoformat())
            continue
        if not prices_are_bid_scale(frame):
            poison.append(day.isoformat())
            continue
        frames.append(frame)
    info = {
        "study_days": len(days),
        "sessions": len(frames),
        "missing": missing,
        "empty": empty,
        "poison": poison,
    }
    if missing or poison or not frames:
        return None, info
    combined = pd.concat(frames, ignore_index=True)
    index = pd.to_datetime(combined["timestamp"], utc=True).dt.tz_convert(NY)
    out = combined.drop(columns=["timestamp"])
    out.index = pd.DatetimeIndex(index)
    out = out[~out.index.duplicated(keep="last")].sort_index()
    info["first"] = str(out.index[0])
    info["last"] = str(out.index[-1])
    info["rows"] = int(len(out))
    return out, info


def main() -> None:
    download()


if __name__ == "__main__":
    main()
