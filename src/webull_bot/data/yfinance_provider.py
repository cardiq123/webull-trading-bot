"""Yahoo Finance via yfinance.

This is the default provider because it needs no paid key. Limits that
matter for research:

* The universe is whoever you ask for. A list of today's large caps is
  survivorship-biased. Delisted names are not filled in.
* Daily history is long. Adjusted prices (auto_adjust) remove splits and
  fold in dividends, which is what a total-return test wants. A gap study
  on adjusted bars can still show a false gap on a bad print; the gap
  strategy drops gaps above 20 percent for that reason.
* Intraday depth on the free endpoint is short: about 7 days of 1-minute
  bars, about 60 days of 5- and 15-minute bars, and about 730 days of
  hourly bars. That is not enough history to claim a durable intraday edge.
* Bars can be missing, late, or revised. Yahoo is not the consolidated tape.
* Volume on adjusted series is split-adjusted, not a raw print count.

Cache files live under data/cache and are safe to delete.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable
from zoneinfo import ZoneInfo

import pandas as pd

from webull_bot.calendar import is_trading_day, to_ny
from webull_bot.data.base import DataProvider, normalize_frame

NY = ZoneInfo("America/New_York")
# Yahoo stamps an intraday bar with its open, not its close.
_BAR_LENGTH = {
    "60m": timedelta(hours=1),
    "1h": timedelta(hours=1),
    "15m": timedelta(minutes=15),
    "5m": timedelta(minutes=5),
    "1m": timedelta(minutes=1),
}
_HOURLY = {"60m", "1h"}
# Requests that end today must include the newest finished bar, and a
# download must not store the bar that is still forming. 60-minute bars
# already worked this way. 15-minute and 5-minute bars use the same rule
# so the VWAP forward test cannot trade on yesterday's file.
_TIMELY = _HOURLY | {"15m", "5m"}

_INTERVALS = {
    "1d": "1d",
    "1h": "60m",
    "60m": "60m",
    "15m": "15m",
    "5m": "5m",
    "1m": "1m",
}


class YFinanceProvider(DataProvider):
    def __init__(self, cache_dir: str | Path = "data/cache") -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def history(
        self,
        symbols: Iterable[str],
        start: str,
        end: str,
        interval: str = "1d",
    ) -> dict[str, pd.DataFrame]:
        yf_interval = _INTERVALS.get(interval, interval)
        frames: dict[str, pd.DataFrame] = {}
        needed: list[str] = []
        for symbol in symbols:
            try:
                cached = self._read_cache(symbol, yf_interval, start, end)
            except Exception:
                cached = None
            if cached is not None:
                frames[symbol] = cached
            else:
                needed.append(symbol)
        if needed:
            try:
                downloaded = self._download(needed, start, end, yf_interval)
            except Exception:
                downloaded = {}
            frames.update(downloaded)
            for symbol in needed:
                if symbol in frames:
                    continue
                relaxed = self._relaxed_cache(symbol, yf_interval)
                if relaxed is not None:
                    frames[symbol] = relaxed
        return frames

    def _cache_path(self, symbol: str, interval: str) -> Path:
        safe = symbol.replace("^", "_").replace("/", "_")
        return self.cache_dir / f"{safe}_{interval}.csv"

    def _read_cache(self, symbol: str, interval: str, start: str, end: str) -> pd.DataFrame | None:
        path = self._cache_path(symbol, interval)
        if not path.exists():
            return None
        frame = pd.read_csv(path, index_col=0)
        # Hourly files span EST and EDT, so the offset column is mixed.
        # Parse as UTC first, then let normalize_frame land on New York time.
        if interval == "1d":
            frame.index = pd.to_datetime(frame.index)
        else:
            frame.index = pd.to_datetime(frame.index, utc=True)
        frame = normalize_frame(frame, "1d" if interval == "1d" else interval)
        if frame.empty:
            return None
        first = pd.Timestamp(frame.index[0]).tz_localize(None)
        last = pd.Timestamp(frame.index[-1]).tz_localize(None)
        start_ts = pd.Timestamp(start).tz_localize(None)
        end_ts = pd.Timestamp(end).tz_localize(None)
        # Daily files get a few days of slack so a weekend or a holiday does
        # not refetch. Hourly, 15-minute, and 5-minute files do not, when
        # the request ends today. A cache that ends at the prior close is
        # not "today", and a bar that was still forming when the file was
        # written is not a finished bar on the next cycle.
        covers_end = _covers_end(path, interval, last, end_ts)
        covers_start = first <= start_ts + pd.Timedelta(days=7)
        # Names listed after `start` (META in 2012, for example) are a complete
        # download even though they begin late. A short lookback file is not.
        long_history = (last - first) >= pd.Timedelta(days=370)
        if covers_end and (covers_start or long_history):
            return frame
        return None

    def _relaxed_cache(self, symbol: str, interval: str) -> pd.DataFrame | None:
        """Last on-disk file, including one that is too old to trade.

        A Yahoo empty download ("possibly delisted") must not drop the symbol
        or raise. The forward book still refuses a stale bar. It does not crash.
        """
        path = self._cache_path(symbol, interval)
        if not path.exists():
            return None
        try:
            frame = pd.read_csv(path, index_col=0)
            if interval == "1d":
                frame.index = pd.to_datetime(frame.index)
            else:
                frame.index = pd.to_datetime(frame.index, utc=True)
            frame = normalize_frame(frame, "1d" if interval == "1d" else interval)
        except Exception:
            return None
        if frame.empty:
            return None
        return frame

    def _download(self, symbols: list[str], start: str, end: str, interval: str) -> dict[str, pd.DataFrame]:
        import yfinance as yf

        # Hourly Yahoo history is capped near 730 days. Clamp the request so
        # the call does not come back empty.
        start_ts = pd.Timestamp(start)
        end_ts = pd.Timestamp(end)
        if interval in {"60m", "1h", "15m", "5m", "1m"}:
            cap_days = {"1m": 6, "5m": 55, "15m": 55, "60m": 720, "1h": 720}[interval if interval != "1h" else "60m"]
            earliest = end_ts - pd.Timedelta(days=cap_days)
            if start_ts < earliest:
                start_ts = earliest
        frames: dict[str, pd.DataFrame] = {}
        # Batch in chunks. A single huge download is more likely to be throttled.
        for offset in range(0, len(symbols), 12):
            chunk = symbols[offset : offset + 12]
            raw = None
            for attempt in range(3):
                try:
                    raw = yf.download(
                        tickers=chunk if len(chunk) > 1 else chunk[0],
                        start=start_ts.date().isoformat(),
                        end=(end_ts + pd.Timedelta(days=1)).date().isoformat(),
                        interval=interval,
                        auto_adjust=True,
                        group_by="ticker",
                        threads=False,
                        progress=False,
                    )
                    break
                except Exception:
                    time.sleep(2 ** attempt)
            if raw is None or raw.empty:
                for symbol in chunk:
                    one = self._download_one(symbol, start_ts, end_ts, interval)
                    if one is not None:
                        frames[symbol] = one
                continue
            try:
                parsed = _split_download(raw, chunk)
            except Exception:
                parsed = {}
            for symbol in chunk:
                frame = parsed.get(symbol)
                if frame is None:
                    one = self._download_one(symbol, start_ts, end_ts, interval)
                    if one is not None:
                        frames[symbol] = one
                    continue
                try:
                    normal = normalize_frame(frame, "1d" if interval == "1d" else interval)
                except ValueError:
                    one = self._download_one(symbol, start_ts, end_ts, interval)
                    if one is not None:
                        frames[symbol] = one
                    continue
                if normal.empty:
                    continue
                normal = _closed_hourly(normal, interval, _clock())
                if normal.empty:
                    continue
                normal.to_csv(self._cache_path(symbol, interval))
                frames[symbol] = normal
            time.sleep(0.4)
        return frames

    def _download_one(self, symbol: str, start: pd.Timestamp, end: pd.Timestamp, interval: str):
        import yfinance as yf

        for attempt in range(3):
            try:
                raw = yf.download(
                    tickers=symbol,
                    start=start.date().isoformat(),
                    end=(end + pd.Timedelta(days=1)).date().isoformat(),
                    interval=interval,
                    auto_adjust=True,
                    progress=False,
                    threads=False,
                )
            except Exception:
                raw = None
            if raw is not None and not raw.empty:
                parsed = _split_download(raw, [symbol])
                frame = parsed.get(symbol)
                if frame is not None:
                    try:
                        normal = normalize_frame(frame, "1d" if interval == "1d" else interval)
                    except ValueError:
                        normal = None
                    if normal is not None and not normal.empty:
                        normal = _closed_hourly(normal, interval, _clock())
                        if not normal.empty:
                            normal.to_csv(self._cache_path(symbol, interval))
                            return normal
            if attempt < 2:
                time.sleep(0.4 * (attempt + 1))
        return None


def _clock() -> datetime:
    return datetime.now(NY)


def bar_end(start, interval: str = "60m") -> pd.Timestamp:
    """When a left-labeled bar is finished. The 15:30 hourly bar ends at 16:00."""
    stamp = pd.Timestamp(start)
    if stamp.tzinfo is None:
        stamp = stamp.tz_localize(NY)
    else:
        stamp = stamp.tz_convert(NY)
    length = _BAR_LENGTH.get(interval, timedelta(hours=1))
    session_close = stamp.normalize() + pd.Timedelta(hours=16)
    return min(stamp + pd.Timedelta(seconds=length.total_seconds()), session_close)


def latest_completed_bar_start(now: datetime, interval: str = "60m") -> pd.Timestamp | None:
    """Open time of the newest regular-hours bar that has fully closed."""
    local = to_ny(now)
    length = _BAR_LENGTH.get(interval, timedelta(hours=1))
    day = local.date()
    for _ in range(12):
        if is_trading_day(day):
            cursor = datetime.combine(day, datetime.min.time(), tzinfo=NY).replace(hour=9, minute=30)
            session_close = cursor.replace(hour=16, minute=0)
            last_ok = None
            while cursor < session_close:
                end = min(cursor + length, session_close)
                if end <= local:
                    last_ok = cursor
                else:
                    break
                cursor = cursor + length
            if last_ok is not None:
                return pd.Timestamp(last_ok)
        day -= timedelta(days=1)
    return None


def _wall(stamp) -> pd.Timestamp:
    clock = pd.Timestamp(stamp)
    if clock.tzinfo is not None:
        clock = clock.tz_convert(NY).tz_localize(None)
    return clock


def _covers_end(path: Path, interval: str, last: pd.Timestamp, end_ts: pd.Timestamp) -> bool:
    if interval not in _TIMELY:
        return last >= end_ts - pd.Timedelta(days=5)
    today = _wall(_clock()).normalize()
    if end_ts.normalize() < today:
        return last >= end_ts - pd.Timedelta(days=5)
    need = latest_completed_bar_start(_clock(), interval)
    if need is None or last < _wall(need):
        return False
    # The file has to have been written after that bar closed. A 10:30 bar
    # saved at 10:50 is still the forming hour, and the 11:35 cycle must
    # not treat it as the finished bar.
    written = datetime.fromtimestamp(path.stat().st_mtime, tz=NY)
    return written >= bar_end(need, interval).to_pydatetime()


def _closed_hourly(frame: pd.DataFrame, interval: str, now: datetime) -> pd.DataFrame:
    """Drop the bar Yahoo has opened but not finished. Daily bars are unchanged."""
    if interval not in _TIMELY or frame.empty:
        return frame
    now_ts = pd.Timestamp(to_ny(now))
    keep = [bar_end(ts, interval) <= now_ts for ts in frame.index]
    return frame.loc[keep]


def _split_download(raw: pd.DataFrame, symbols: list[str]) -> dict[str, pd.DataFrame]:
    frames: dict[str, pd.DataFrame] = {}
    if isinstance(raw.columns, pd.MultiIndex):
        level0 = {str(value) for value in raw.columns.get_level_values(0)}
        # yfinance has used both (ticker, field) and (field, ticker).
        if any(symbol in level0 for symbol in symbols):
            for symbol in symbols:
                if symbol in raw.columns.get_level_values(0):
                    frames[symbol] = raw[symbol].copy()
        else:
            for symbol in symbols:
                if symbol in raw.columns.get_level_values(1):
                    piece = raw.xs(symbol, axis=1, level=1).copy()
                    frames[symbol] = piece
    else:
        if len(symbols) == 1:
            frames[symbols[0]] = raw.copy()
    return frames
