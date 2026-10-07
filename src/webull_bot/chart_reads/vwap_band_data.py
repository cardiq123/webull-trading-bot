"""Free 1-minute bids for the session-VWAP study, resampled to 15 minutes.

SPY reuses Dukascopy's public ``SPYUSUSD`` feed. The Monday/Wednesday/Friday
files already cached for the opening-range study are copied, and the other
sessions are downloaded into ``data/cache/``. This module does not place an
order and does not import the sandbox forward test.

QQQ is requested from the same host. If that instrument is absent, the
caller uses Yahoo's short 15-minute file and says so. Dukascopy volume is
a bid-tick count, not share volume. Prices are bids.
"""

from __future__ import annotations

import shutil
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, time as clock
from pathlib import Path

import pandas as pd

from webull_bot.calendar import is_trading_day
from webull_bot.chart_reads.dukascopy_spy import (
    END,
    NY,
    START,
    _minutes,
    prices_are_bid_scale,
    trading_days,
)

ROOT = Path("data/cache/vwap_band/dukascopy")
LEGACY_SPY = Path("data/cache/orb_mwf/dukascopy/days")
QQQ_CANDIDATES = ("QQQUSUSD", "QQQUSD")


def _url(instrument: str, day: date) -> str:
    return (
        "https://datafeed.dukascopy.com/datafeed/"
        f"{instrument}/{day.year}/{day.month - 1:02d}/{day.day:02d}/BID_candles_min_1.bi5"
    )


def _fetch(instrument: str, day: date) -> bytes | None:
    """Raw bi5 bytes, or None when that session was never published."""
    request = urllib.request.Request(_url(instrument, day), headers={"User-Agent": "Mozilla/5.0"})
    delay = 1.0
    for _attempt in range(6):
        try:
            with urllib.request.urlopen(request, timeout=40) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
            time.sleep(delay)
            delay = min(delay * 2, 20.0)
        except (urllib.error.URLError, TimeoutError, OSError):
            time.sleep(delay)
            delay = min(delay * 2, 20.0)
    raise RuntimeError(f"Dukascopy failed for {_url(instrument, day)}")


def _day_path(symbol: str, day: date) -> Path:
    return ROOT / symbol / f"{day.isoformat()}.csv"


def _write_day(symbol: str, day: date, buckets: dict) -> None:
    path = _day_path(symbol, day)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    if not buckets:
        temporary.write_text("timestamp,open,high,low,close,volume\n")
        temporary.replace(path)
        return
    lines = ["timestamp,open,high,low,close,volume"]
    for stamp, (opened, high, low, closed, count) in sorted(buckets.items()):
        lines.append(
            f"{stamp.isoformat()},{opened:.4f},{high:.4f},{low:.4f},{closed:.4f},{int(count)}"
        )
    temporary.write_text("\n".join(lines) + "\n")
    temporary.replace(path)


def _seed_spy(day: date) -> bool:
    legacy = LEGACY_SPY / f"{day.isoformat()}.csv"
    dest = _day_path("SPY", day)
    if dest.exists() or not legacy.exists():
        return dest.exists()
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(legacy, dest)
    return True


def _one_day(symbol: str, instrument: str, day: date) -> str:
    path = _day_path(symbol, day)
    if path.exists():
        return "cached"
    if symbol == "SPY" and _seed_spy(day):
        return "copied"
    try:
        raw = _fetch(instrument, day)
    except RuntimeError as exc:
        print(f"DUKASCOPY FAIL {symbol} {day.isoformat()} {exc}", flush=True)
        return "fail"
    _write_day(symbol, day, _minutes(raw or b"", day))
    return "empty" if not raw else "ok"


def probe_qqq(day: date | None = None) -> str | None:
    """Return the Dukascopy instrument name, or None when QQQ is not published."""
    probe = day or date(2024, 1, 2)
    if not is_trading_day(probe):
        probe = date(2024, 1, 3)
    for name in QQQ_CANDIDATES:
        try:
            raw = _fetch(name, probe)
        except RuntimeError:
            continue
        if raw:
            print(f"QQQ INSTRUMENT {name}", flush=True)
            return name
    print("QQQ INSTRUMENT none", flush=True)
    return None


def ensure_symbol(symbol: str, instrument: str, workers: int = 6) -> dict:
    """Download any missing sessions. A 404 is an empty file. A network error is retried next run."""
    days = trading_days(START, END)
    pending = []
    copied = 0
    for day in days:
        if symbol == "SPY" and not _day_path(symbol, day).exists() and _seed_spy(day):
            copied += 1
        if not _day_path(symbol, day).exists():
            pending.append(day)
    print(f"DUKASCOPY {symbol} days {len(days)} copied {copied} pending {len(pending)}", flush=True)
    failed = 0
    done = len(days) - len(pending)
    if pending:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_one_day, symbol, instrument, day): day for day in pending}
            for future in as_completed(futures):
                if future.result() == "fail":
                    failed += 1
                done += 1
                if done % 50 == 0 or done == len(days):
                    print(f"DUKASCOPY {symbol} {done}/{len(days)} failed {failed}", flush=True)
    return {"symbol": symbol, "instrument": instrument, "days": len(days), "failed": failed, "pending_left": failed}


def load_minutes(symbol: str) -> tuple[pd.DataFrame | None, dict]:
    days = trading_days(START, END)
    missing: list[str] = []
    empty: list[str] = []
    poison: list[str] = []
    frames: list[pd.DataFrame] = []
    for day in days:
        path = _day_path(symbol, day)
        if not path.exists():
            missing.append(day.isoformat())
            continue
        frame = pd.read_csv(path)
        if frame.empty or "timestamp" not in frame.columns:
            empty.append(day.isoformat())
            continue
        if not prices_are_bid_scale(frame):
            poison.append(day.isoformat())
            continue
        frames.append(frame)
    info = {
        "symbol": symbol,
        "sessions_expected": len(days),
        "sessions": len(frames),
        "missing": len(missing),
        "empty": len(empty),
        "poison": poison[:8],
        "source": "dukascopy_bid",
        "volume": "bid tick count, not share volume",
    }
    if poison or not frames:
        return None, info
    combined = pd.concat(frames, ignore_index=True)
    index = pd.to_datetime(combined["timestamp"], utc=True).dt.tz_convert(NY)
    out = combined.drop(columns=["timestamp"])
    out.index = pd.DatetimeIndex(index)
    out = out[~out.index.duplicated(keep="last")].sort_index()
    info["first"] = str(out.index[0].date())
    info["last"] = str(out.index[-1].date())
    info["rows"] = int(len(out))
    return out, info


def to_fifteen_minute(minutes: pd.DataFrame) -> pd.DataFrame:
    """Left-labeled 15-minute bars. The 09:30 bar is 09:30 through 09:44."""
    if minutes is None or minutes.empty:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    pieces = []
    for _day, chunk in minutes.groupby(minutes.index.date):
        fifteen = chunk.resample("15min", label="left", closed="left").agg(
            {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
        )
        fifteen = fifteen.dropna(subset=["open"])
        if fifteen.empty:
            continue
        clock_ = fifteen.index.time
        fifteen = fifteen[(clock_ >= clock(9, 30)) & (clock_ < clock(16, 0))]
        if not fifteen.empty:
            pieces.append(fifteen)
    if not pieces:
        return minutes.iloc[0:0]
    out = pd.concat(pieces)
    return out[~out.index.duplicated(keep="last")].sort_index()


def main() -> None:
    ensure_symbol("SPY", "SPYUSUSD")
    instrument = probe_qqq()
    if instrument:
        ensure_symbol("QQQ", instrument)


if __name__ == "__main__":
    main()
