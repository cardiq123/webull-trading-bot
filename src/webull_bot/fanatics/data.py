"""Free history for the Chart Fanatics specs.

Dukascopy publishes bid 1-minute candles without an API key. This module
caches those files and resamples them. Yahoo daily bars cover the overnight
study back to 2000. Nothing here places an order.

Index names ``USATECHIDXUSD`` and ``USA500IDXUSD`` are CFDs, not CME NQ and
ES. Results that use them are proxies.
"""

from __future__ import annotations

import lzma
import struct
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ET = ZoneInfo("America/New_York")
UTC = timezone.utc

# scale: integer price divisor used by Dukascopy.
# usd_quote: P&L is (exit-entry) * point_value. Otherwise USD is the base
# currency and spot P&L divides by the exit price (USDJPY, USDCAD).
INSTRUMENTS = {
    "USATECHIDXUSD": {"scale": 1_000, "tick": 0.25, "point_value": 20.0, "usd_quote": True, "kind": "cfd-nq"},
    "USA500IDXUSD": {"scale": 1_000, "tick": 0.25, "point_value": 50.0, "usd_quote": True, "kind": "cfd-es"},
    "XAUUSD": {"scale": 1_000, "tick": 0.10, "point_value": 100.0, "usd_quote": True, "kind": "gc-proxy"},
    "EURUSD": {"scale": 100_000, "tick": 0.00005, "point_value": 125_000.0, "usd_quote": True, "kind": "fx"},
    "GBPUSD": {"scale": 100_000, "tick": 0.0001, "point_value": 62_500.0, "usd_quote": True, "kind": "fx"},
    "NZDUSD": {"scale": 100_000, "tick": 0.00005, "point_value": 100_000.0, "usd_quote": True, "kind": "fx"},
    "USDJPY": {"scale": 1_000, "tick": 0.01, "point_value": 100_000.0, "usd_quote": False, "kind": "fx-spot"},
    "USDCAD": {"scale": 100_000, "tick": 0.0001, "point_value": 100_000.0, "usd_quote": False, "kind": "fx-spot"},
    # Crypto proxies. Quantity is fractional. Fee is the spot taker rate, not the $2 futures commission.
    "BTCUSDT": {"scale": 1, "tick": 0.01, "point_value": 1.0, "usd_quote": True, "kind": "crypto", "fee_bps": 10.0, "fractional": True},
    "ETHUSDT": {"scale": 1, "tick": 0.01, "point_value": 1.0, "usd_quote": True, "kind": "crypto", "fee_bps": 10.0, "fractional": True},
    "PAXGUSDT": {"scale": 1, "tick": 0.01, "point_value": 1.0, "usd_quote": True, "kind": "crypto", "fee_bps": 10.0, "fractional": True},
    "NQ=F": {"scale": 1, "tick": 0.25, "point_value": 20.0, "usd_quote": True, "kind": "future"},
    "ES=F": {"scale": 1, "tick": 0.25, "point_value": 50.0, "usd_quote": True, "kind": "future"},
    "GC=F": {"scale": 1, "tick": 0.10, "point_value": 100.0, "usd_quote": True, "kind": "future"},
}

DATA_START = date(2013, 1, 1)
SAMPLE_END = date(2026, 9, 30)
CACHE = Path("data/cache/dukascopy")
BARS = Path("data/cache/fanatics")

_RECORD = struct.Struct(">IIIIIf")


def _session() -> requests.Session:
    retry = Retry(total=5, backoff_factor=0.4, status_forcelist=(429, 500, 502, 503, 504))
    adapter = HTTPAdapter(max_retries=retry, pool_connections=8, pool_maxsize=8)
    session = requests.Session()
    session.headers["User-Agent"] = "research-backtest"
    session.mount("https://", adapter)
    return session


def _day_url(symbol: str, day: date) -> str:
    return (
        "https://datafeed.dukascopy.com/datafeed/"
        f"{symbol}/{day.year}/{day.month - 1:02d}/{day.day:02d}/BID_candles_min_1.bi5"
    )


def _cache_path(symbol: str, day: date) -> Path:
    return CACHE / symbol / f"{day.isoformat()}.bi5"


def download_symbol(symbol: str, start: date = DATA_START, end: date = SAMPLE_END) -> tuple[int, int]:
    """Cache one calendar day per file. Returns (downloaded, missing)."""
    session = _session()
    downloaded = 0
    missing = 0
    day = start
    while day <= end:
        path = _cache_path(symbol, day)
        if path.exists() and path.stat().st_size > 0:
            day += timedelta(days=1)
            continue
        if day.weekday() == 5:
            missing += 1
            day += timedelta(days=1)
            continue
        try:
            response = session.get(_day_url(symbol, day), timeout=40)
        except requests.RequestException:
            time.sleep(1.0)
            day += timedelta(days=1)
            missing += 1
            continue
        if response.status_code == 404:
            missing += 1
        elif response.status_code == 200 and response.content:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(response.content)
            downloaded += 1
        else:
            missing += 1
            time.sleep(0.5)
        if (downloaded + missing) % 400 == 0:
            print(f"{symbol} progress downloaded={downloaded} missing={missing} at {day}", flush=True)
        day += timedelta(days=1)
    print(f"{symbol} done downloaded={downloaded} missing={missing}", flush=True)
    return downloaded, missing


def download_all(symbols: list[str] | None = None) -> None:
    names = symbols or list(INSTRUMENTS)
    with ThreadPoolExecutor(max_workers=min(4, len(names))) as pool:
        futures = {pool.submit(download_symbol, name): name for name in names}
        for future in as_completed(futures):
            future.result()


def _decode_day(symbol: str, day: date, blob: bytes) -> list[tuple]:
    scale = INSTRUMENTS[symbol]["scale"]
    try:
        raw = lzma.decompress(blob)
    except lzma.LZMAError:
        return []
    if len(raw) < _RECORD.size:
        return []
    rows = []
    usable = len(raw) - (len(raw) % _RECORD.size)
    for sec, open_, close, low, high, volume in _RECORD.iter_unpack(raw[:usable]):
        if high < low or open_ <= 0:
            continue
        stamp = datetime(day.year, day.month, day.day, tzinfo=UTC) + timedelta(seconds=int(sec))
        rows.append(
            (
                stamp,
                open_ / scale,
                high / scale,
                low / scale,
                close / scale,
                float(volume),
            )
        )
    return rows


def _five_minute(rows: list[tuple]) -> list[tuple]:
    if not rows:
        return []
    buckets: dict[datetime, list] = {}
    for stamp, open_, high, low, close, volume in rows:
        minute = stamp.minute - (stamp.minute % 5)
        key = stamp.replace(minute=minute, second=0, microsecond=0)
        buckets.setdefault(key, []).append((open_, high, low, close, volume))
    out = []
    for key in sorted(buckets):
        chunk = buckets[key]
        out.append(
            (
                key,
                chunk[0][0],
                max(item[1] for item in chunk),
                min(item[2] for item in chunk),
                chunk[-1][3],
                float(sum(item[4] for item in chunk)),
            )
        )
    return out


def _rth_profile(rows: list[tuple], tick: float) -> dict | None:
    """70% value area of the completed 09:30–16:00 ET session.

    Volume inside each 1-minute bar is spread evenly across the bins the
    bar's range touches. Dukascopy CFD volume is not CME volume.
    """
    bins: dict[int, float] = {}
    highs = []
    lows = []
    for stamp, _open, high, low, close, volume in rows:
        local = stamp.astimezone(ET)
        minute = local.hour * 60 + local.minute
        if minute < 9 * 60 + 30 or minute >= 16 * 60:
            continue
        if volume < 0 or not np.isfinite(close):
            continue
        highs.append(high)
        lows.append(low)
        if high <= low or volume == 0:
            key = int(round(close / tick))
            bins[key] = bins.get(key, 0.0) + max(volume, 0.0)
            continue
        start = int(np.floor(low / tick))
        end = int(np.ceil(high / tick))
        count = max(end - start, 1)
        share = volume / count
        for key in range(start, end):
            bins[key] = bins.get(key, 0.0) + share
    if not bins or not highs:
        return None
    keys = sorted(bins)
    volumes = np.array([bins[key] for key in keys], dtype=float)
    poc_i = int(np.argmax(volumes))
    total = float(volumes.sum())
    lo = hi = poc_i
    filled = float(volumes[poc_i])
    while filled < 0.70 * total and (lo > 0 or hi < len(keys) - 1):
        left = float(volumes[lo - 1]) if lo > 0 else -1.0
        right = float(volumes[hi + 1]) if hi < len(keys) - 1 else -1.0
        if left > right:
            lo -= 1
            filled += float(volumes[lo])
        elif right > left:
            hi += 1
            filled += float(volumes[hi])
        else:
            if lo > 0:
                lo -= 1
                filled += float(volumes[lo])
            if hi < len(keys) - 1:
                hi += 1
                filled += float(volumes[hi])
    return {
        "date": stamp.astimezone(ET).date().isoformat() if False else rows[0][0].astimezone(ET).date().isoformat(),
        "poc": keys[poc_i] * tick,
        "vah": keys[hi] * tick,
        "val": keys[lo] * tick,
        "rth_high": float(max(highs)),
        "rth_low": float(min(lows)),
    }


def aggregate_symbol(symbol: str, start: date = DATA_START, end: date = SAMPLE_END) -> pd.DataFrame:
    """Build a 5-minute bid bar frame and a daily value-area table."""
    bars_rows = []
    profiles = []
    tick = float(INSTRUMENTS[symbol]["tick"])
    day = start
    while day <= end:
        path = _cache_path(symbol, day)
        day += timedelta(days=1)
        if not path.exists() or path.stat().st_size == 0:
            continue
        minutes = _decode_day(symbol, path.stem and date.fromisoformat(path.stem), path.read_bytes())
        if not minutes:
            continue
        bars_rows.extend(_five_minute(minutes))
        if INSTRUMENTS[symbol]["kind"].startswith("cfd"):
            profile = _rth_profile(minutes, tick)
            if profile is not None:
                # The session date is the New York date of the last RTH bar,
                # not the UTC file date. Recompute from the minutes.
                profiles.append(profile)
    frame = pd.DataFrame(bars_rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
    if frame.empty:
        return frame
    frame = frame.drop_duplicates("timestamp").sort_values("timestamp")
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True).dt.tz_convert(ET)
    frame = frame.set_index("timestamp")
    BARS.mkdir(parents=True, exist_ok=True)
    frame.to_pickle(BARS / f"{symbol}_5m.pkl")
    if profiles:
        # Fix session date: file-day ET date can be wrong for the evening
        # session. Profiles were tagged with the first minute's ET date.
        # Rebuild the date from RTH content by recomputing below only when
        # the first row is inside RTH; otherwise leave the tag and let
        # consumers shift to the completed session.
        table = pd.DataFrame(profiles).drop_duplicates("date")
        table.to_pickle(BARS / f"{symbol}_va.pkl")
    print(f"{symbol} 5m bars {len(frame)} profiles {len(profiles)}", flush=True)
    return frame


def _rth_profile_dated(symbol: str, day: date, minutes: list[tuple], tick: float) -> dict | None:
    profile = _rth_profile(minutes, tick)
    if profile is None:
        return None
    # A UTC file dated Monday holds Sunday evening plus Monday RTH.
    # The RTH bars belong to `day` in ET only when the file's UTC date
    # matches. Re-tag from the actual RTH timestamps.
    rth_days = []
    for stamp, *_rest in minutes:
        local = stamp.astimezone(ET)
        minute = local.hour * 60 + local.minute
        if 9 * 60 + 30 <= minute < 16 * 60:
            rth_days.append(local.date())
    if not rth_days:
        return None
    profile["date"] = rth_days[-1].isoformat()
    return profile


def aggregate_symbol_fixed(symbol: str, start: date = DATA_START, end: date = SAMPLE_END) -> pd.DataFrame:
    bars_rows = []
    profiles = []
    tick = float(INSTRUMENTS[symbol]["tick"])
    day = start
    while day <= end:
        path = _cache_path(symbol, day)
        this = day
        day += timedelta(days=1)
        if not path.exists() or path.stat().st_size == 0:
            continue
        minutes = _decode_day(symbol, this, path.read_bytes())
        if not minutes:
            continue
        bars_rows.extend(_five_minute(minutes))
        if INSTRUMENTS[symbol]["kind"].startswith("cfd"):
            profile = _rth_profile_dated(symbol, this, minutes, tick)
            if profile is not None:
                profiles.append(profile)
    frame = pd.DataFrame(bars_rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
    if frame.empty:
        return frame
    frame = frame.drop_duplicates("timestamp").sort_values("timestamp")
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True).dt.tz_convert(ET)
    frame = frame.set_index("timestamp")
    BARS.mkdir(parents=True, exist_ok=True)
    frame.to_pickle(BARS / f"{symbol}_5m.pkl")
    if profiles:
        table = pd.DataFrame(profiles).drop_duplicates("date", keep="last")
        table.to_pickle(BARS / f"{symbol}_va.pkl")
    print(f"{symbol} 5m bars {len(frame)} profiles {len(profiles)}", flush=True)
    return frame


def load_5m(symbol: str) -> pd.DataFrame:
    path = BARS / f"{symbol}_5m.pkl"
    if not path.exists():
        raise FileNotFoundError(path)
    frame = pd.read_pickle(path)
    if frame.index.tz is None:
        frame.index = frame.index.tz_localize(ET)
    return frame


def load_value_area(symbol: str) -> pd.DataFrame:
    path = BARS / f"{symbol}_va.pkl"
    if not path.exists():
        return pd.DataFrame(columns=["date", "poc", "vah", "val", "rth_high", "rth_low"])
    return pd.read_pickle(path)


def download_yahoo_daily(start: str = "2000-01-01", end: str = "2026-10-01") -> dict[str, pd.DataFrame]:
    import yfinance as yf

    BARS.mkdir(parents=True, exist_ok=True)
    frames = {}
    for symbol in ("SPY", "QQQ", "^VIX", "ES=F", "NQ=F", "GC=F"):
        path = BARS / f"yahoo_{symbol.replace('=', '').replace('^', '')}_1d.pkl"
        if path.exists():
            frames[symbol] = pd.read_pickle(path)
            continue
        data = yf.download(symbol, start=start, end=end, auto_adjust=False, progress=False, threads=False)
        if data is None or len(data) == 0:
            print(f"yahoo missing {symbol}", flush=True)
            continue
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = [str(col[0]).lower() for col in data.columns]
        else:
            data.columns = [str(col).lower() for col in data.columns]
        data = data.rename(columns={"adj close": "adj_close"})
        data.index = pd.to_datetime(data.index).tz_localize(None)
        data.to_pickle(path)
        frames[symbol] = data
        print(f"yahoo {symbol} {data.index.min().date()} {data.index.max().date()} rows {len(data)}", flush=True)
    return frames


def prepare(symbols: list[str] | None = None) -> None:
    names = symbols or ["USATECHIDXUSD", "USA500IDXUSD", "XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "USDCAD", "NZDUSD"]
    download_all(names)
    for name in names:
        aggregate_symbol_fixed(name)
    download_yahoo_daily()


def _binance_months(start: date, end: date) -> list[tuple[int, int]]:
    months = []
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        months.append((year, month))
        month += 1
        if month == 13:
            month = 1
            year += 1
    return months


def _read_kline_csv(blob: bytes) -> list[tuple]:
    rows = []
    for line in blob.splitlines():
        # Zip payloads are bytes. Indexing a bytes line returns an int, so
        # test a one-byte slice. Header rows (newer monthly files) are skipped.
        if not line or not line[:1].isdigit():
            continue
        parts = line.split(b",")
        if len(parts) < 6:
            continue
        raw = int(parts[0])
        scale = 1_000_000 if raw > 10**14 else 1000
        stamp = datetime.fromtimestamp(raw / scale, tz=UTC)
        rows.append(
            (
                stamp,
                float(parts[1]),
                float(parts[2]),
                float(parts[3]),
                float(parts[4]),
                float(parts[5]),
            )
        )
    return rows


def _binance_daily(session, symbol: str, interval: str, year: int, month: int, start: date, end: date) -> pd.DataFrame | None:
    """Daily zips cover a month whose monthly archive is not published yet."""
    import calendar
    import zipfile

    cache = Path("data/cache/binance")
    last = calendar.monthrange(year, month)[1]
    frames = []
    for day in range(1, last + 1):
        current = date(year, month, day)
        if current < start or current > end:
            continue
        name = f"{symbol}-{interval}-{year}-{month:02d}-{day:02d}"
        path = cache / f"{name}.zip"
        if not path.exists():
            url = f"https://data.binance.vision/data/spot/daily/klines/{symbol}/{interval}/{name}.zip"
            try:
                response = session.get(url, timeout=40)
            except requests.RequestException:
                continue
            if response.status_code != 200 or not response.content:
                continue
            path.write_bytes(response.content)
        try:
            with zipfile.ZipFile(path) as archive:
                payload = archive.read(archive.namelist()[0])
        except (zipfile.BadZipFile, IndexError):
            continue
        rows = _read_kline_csv(payload)
        if rows:
            frames.append(pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"]))
    if not frames:
        return None
    return pd.concat(frames, ignore_index=True)


def download_binance(symbol: str, interval: str, start: date, end: date) -> pd.DataFrame:
    """Monthly public klines from data.binance.vision. No API key."""
    import io
    import zipfile

    cache = Path("data/cache/binance")
    cache.mkdir(parents=True, exist_ok=True)
    session = _session()
    frames = []

    def one(year_month: tuple[int, int]) -> pd.DataFrame | None:
        year, month = year_month
        name = f"{symbol}-{interval}-{year}-{month:02d}"
        path = cache / f"{name}.zip"
        if not path.exists():
            url = f"https://data.binance.vision/data/spot/monthly/klines/{symbol}/{interval}/{name}.zip"
            try:
                response = session.get(url, timeout=40)
            except requests.RequestException:
                response = None
            if response is not None and response.status_code == 200 and response.content:
                path.write_bytes(response.content)
            else:
                return _binance_daily(session, symbol, interval, year, month, start, end)
        try:
            with zipfile.ZipFile(path) as archive:
                payload = archive.read(archive.namelist()[0])
        except (zipfile.BadZipFile, IndexError):
            return None
        rows = _read_kline_csv(payload)
        if not rows:
            return None
        frame = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
        return frame

    months = _binance_months(start, end)
    with ThreadPoolExecutor(max_workers=8) as pool:
        for frame in pool.map(one, months):
            if frame is not None and len(frame):
                frames.append(frame)
    if not frames:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    out = pd.concat(frames, ignore_index=True)
    out = out.drop_duplicates("timestamp").sort_values("timestamp")
    out["timestamp"] = pd.to_datetime(out["timestamp"], utc=True).dt.tz_convert(ET)
    out = out.set_index("timestamp")
    BARS.mkdir(parents=True, exist_ok=True)
    out.to_pickle(BARS / f"{symbol}_{interval}.pkl")
    print(f"binance {symbol} {interval} {out.index.min()} {out.index.max()} rows {len(out)}", flush=True)
    return out


def value_areas_from_bars(frame: pd.DataFrame, bin_size: float) -> pd.DataFrame:
    """70% value area from completed 09:30–16:00 ET bars. Coarse bins, so this is a proxy."""
    from webull_bot.fanatics.detectors import value_area

    if frame.empty:
        return pd.DataFrame(columns=["date", "poc", "vah", "val", "rth_high", "rth_low"])
    local = frame.index.tz_convert(ET)
    minutes = local.hour * 60 + local.minute
    rth = frame[(minutes >= 9 * 60 + 30) & (minutes < 16 * 60)]
    rows = []
    for day, chunk in rth.groupby(rth.index.tz_convert(ET).strftime("%Y-%m-%d")):
        bins: dict[int, float] = {}
        for high, low, close, volume in chunk[["high", "low", "close", "volume"]].itertuples(index=False):
            if volume <= 0 or not np.isfinite(close):
                continue
            if high <= low:
                key = int(round(close / bin_size))
                bins[key] = bins.get(key, 0.0) + float(volume)
                continue
            start = int(np.floor(low / bin_size))
            end = int(np.ceil(high / bin_size))
            count = max(end - start, 1)
            share = float(volume) / count
            for key in range(start, end):
                bins[key] = bins.get(key, 0.0) + share
        if not bins:
            continue
        keys = np.array(sorted(bins), dtype=float)
        volumes = np.array([bins[int(key)] for key in keys], dtype=float)
        poc, vah, val = value_area(keys * bin_size, volumes)
        rows.append(
            {
                "date": day,
                "poc": poc,
                "vah": vah,
                "val": val,
                "rth_high": float(chunk["high"].max()),
                "rth_low": float(chunk["low"].min()),
            }
        )
    return pd.DataFrame(rows)


def download_yahoo_intraday() -> dict[str, pd.DataFrame]:
    import yfinance as yf

    BARS.mkdir(parents=True, exist_ok=True)
    jobs = [
        ("NQ=F", "5m", "60d"),
        ("ES=F", "5m", "60d"),
        ("GC=F", "30m", "60d"),
        ("NQ=F", "60m", "730d"),
        ("ES=F", "60m", "730d"),
    ]
    frames = {}
    for symbol, interval, period in jobs:
        safe = symbol.replace("=", "")
        path = BARS / f"yahoo_{safe}_{interval}.pkl"
        key = f"{symbol}_{interval}"
        if path.exists():
            frames[key] = pd.read_pickle(path)
            continue
        data = yf.download(symbol, period=period, interval=interval, auto_adjust=False, progress=False, threads=False)
        if data is None or len(data) == 0:
            print(f"yahoo intraday missing {symbol} {interval}", flush=True)
            continue
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = [str(col[0]).lower() for col in data.columns]
        else:
            data.columns = [str(col).lower() for col in data.columns]
        data = data.rename(columns={"adj close": "adj_close"})
        data.index = pd.to_datetime(data.index)
        if data.index.tz is None:
            data.index = data.index.tz_localize("America/New_York")
        else:
            data.index = data.index.tz_convert("America/New_York")
        keep = data[["open", "high", "low", "close", "volume"]].dropna()
        keep.to_pickle(path)
        frames[key] = keep
        print(f"yahoo {symbol} {interval} {keep.index.min()} {keep.index.max()} rows {len(keep)}", flush=True)
    return frames


def prepare_free() -> None:
    download_yahoo_daily()
    download_yahoo_intraday()
    download_binance("BTCUSDT", "5m", date(2018, 1, 1), SAMPLE_END)
    download_binance("ETHUSDT", "5m", date(2018, 1, 1), SAMPLE_END)
    download_binance("PAXGUSDT", "30m", date(2020, 1, 1), SAMPLE_END)
    for symbol, bin_size in (("BTCUSDT", 5.0), ("ETHUSDT", 0.5)):
        frame = pd.read_pickle(BARS / f"{symbol}_5m.pkl")
        value_areas_from_bars(frame, bin_size).to_pickle(BARS / f"{symbol}_va.pkl")


if __name__ == "__main__":
    prepare_free()
