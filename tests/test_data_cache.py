import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from webull_bot.data import yfinance_provider
from webull_bot.data.yfinance_provider import YFinanceProvider, _closed_hourly

NY = ZoneInfo("America/New_York")


def test_hourly_cache_accepts_mixed_est_and_edt_offsets(tmp_path: Path):
    path = tmp_path / "SPY_60m.csv"
    path.write_text(
        "Datetime,open,high,low,close,volume\n"
        "2024-01-02 10:30:00-05:00,100,101,99,100.5,1000\n"
        "2024-06-03 10:30:00-04:00,101,102,100,101.5,1100\n"
    )
    frame = YFinanceProvider(tmp_path)._read_cache("SPY", "60m", "2024-01-02", "2024-06-04")
    assert frame is not None
    assert str(frame.index.tz) == "America/New_York"
    assert len(frame) == 2
    assert list(frame["close"]) == [100.5, 101.5]


def test_cache_keeps_a_name_listed_after_the_requested_start(tmp_path: Path):
    path = tmp_path / "META_1d.csv"
    rows = ["Date,open,high,low,close,volume"]
    start = pd.Timestamp("2012-05-18")
    for i in range(400):
        day = (start + pd.Timedelta(days=i)).date().isoformat()
        rows.append(f"{day},10,11,9,10.5,1000")
    path.write_text("\n".join(rows) + "\n")
    frame = YFinanceProvider(tmp_path)._read_cache("META", "1d", "2011-01-01", "2013-06-20")
    assert frame is not None
    assert len(frame) == 400


def _hourly_cache(path: Path, rows: list[tuple[str, float]], written: datetime) -> None:
    lines = ["Datetime,open,high,low,close,volume"]
    for stamp, close in rows:
        lines.append(f"{stamp},{close - 1},{close + 1},{close - 1},{close},1000")
    path.write_text("\n".join(lines) + "\n")
    moment = written.timestamp()
    os.utime(path, (moment, moment))


def test_prior_close_does_not_cover_the_1045_cycle(tmp_path: Path, monkeypatch):
    """The 2026-10-07 10:45 run was still on the 2026-10-06 15:30 bar."""
    path = tmp_path / "SPY_60m.csv"
    _hourly_cache(
        path,
        [("2026-10-06 15:30:00-04:00", 100.0)],
        datetime(2026, 10, 6, 19, 39, tzinfo=NY),
    )
    monkeypatch.setattr(yfinance_provider, "_clock", lambda: datetime(2026, 10, 7, 10, 45, tzinfo=NY))
    provider = YFinanceProvider(tmp_path)
    assert provider._read_cache("SPY", "60m", "2026-10-06", "2026-10-08") is None


def test_0930_bar_is_fresh_at_1045_and_stale_at_1135(tmp_path: Path, monkeypatch):
    path = tmp_path / "SPY_60m.csv"
    _hourly_cache(
        path,
        [
            ("2026-10-07 09:30:00-04:00", 101.0),
        ],
        datetime(2026, 10, 7, 10, 45, tzinfo=NY),
    )
    provider = YFinanceProvider(tmp_path)
    monkeypatch.setattr(yfinance_provider, "_clock", lambda: datetime(2026, 10, 7, 10, 45, tzinfo=NY))
    fresh = provider._read_cache("SPY", "60m", "2026-10-07", "2026-10-08")
    assert fresh is not None
    assert fresh.index[-1].strftime("%Y-%m-%d %H:%M") == "2026-10-07 09:30"
    monkeypatch.setattr(yfinance_provider, "_clock", lambda: datetime(2026, 10, 7, 11, 35, tzinfo=NY))
    assert provider._read_cache("SPY", "60m", "2026-10-07", "2026-10-08") is None


def test_a_forming_hour_saved_early_is_not_the_1135_bar(tmp_path: Path, monkeypatch):
    path = tmp_path / "SPY_60m.csv"
    _hourly_cache(
        path,
        [("2026-10-07 10:30:00-04:00", 102.0)],
        datetime(2026, 10, 7, 10, 50, tzinfo=NY),
    )
    monkeypatch.setattr(yfinance_provider, "_clock", lambda: datetime(2026, 10, 7, 11, 35, tzinfo=NY))
    assert YFinanceProvider(tmp_path)._read_cache("SPY", "60m", "2026-10-07", "2026-10-08") is None


def test_download_does_not_store_the_open_hour(tmp_path: Path, monkeypatch):
    index = pd.DatetimeIndex(
        [
            pd.Timestamp("2026-10-07 09:30", tz=NY),
            pd.Timestamp("2026-10-07 10:30", tz=NY),
        ]
    )
    frame = pd.DataFrame(
        {"open": [1, 2], "high": [2, 3], "low": [1, 2], "close": [1.5, 2.5], "volume": [10, 10]},
        index=index,
    )
    monkeypatch.setattr(yfinance_provider, "_clock", lambda: datetime(2026, 10, 7, 10, 45, tzinfo=NY))
    closed = _closed_hourly(frame, "60m", yfinance_provider._clock())
    assert list(closed.index.strftime("%H:%M")) == ["09:30"]
