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


def test_fifteen_minute_cache_needs_the_completed_bar(tmp_path: Path, monkeypatch):
    path = tmp_path / "SPY_15m.csv"
    _hourly_cache(
        path,
        [("2026-10-07 09:30:00-04:00", 101.0)],
        datetime(2026, 10, 7, 9, 50, tzinfo=NY),
    )
    monkeypatch.setattr(yfinance_provider, "_clock", lambda: datetime(2026, 10, 7, 10, 20, tzinfo=NY))
    assert YFinanceProvider(tmp_path)._read_cache("SPY", "15m", "2026-10-07", "2026-10-08") is None


def test_fifteen_minute_bar_written_after_it_closes_is_fresh(tmp_path: Path, monkeypatch):
    path = tmp_path / "SPY_15m.csv"
    _hourly_cache(
        path,
        [
            ("2026-10-07 09:30:00-04:00", 101.0),
            ("2026-10-07 09:45:00-04:00", 101.2),
            ("2026-10-07 10:00:00-04:00", 101.4),
        ],
        datetime(2026, 10, 7, 10, 20, tzinfo=NY),
    )
    monkeypatch.setattr(yfinance_provider, "_clock", lambda: datetime(2026, 10, 7, 10, 20, tzinfo=NY))
    fresh = YFinanceProvider(tmp_path)._read_cache("SPY", "15m", "2026-10-07", "2026-10-08")
    assert fresh is not None
    assert fresh.index[-1].strftime("%Y-%m-%d %H:%M") == "2026-10-07 10:00"


def test_fifteen_minute_history_before_today_keeps_the_slack(tmp_path: Path, monkeypatch):
    path = tmp_path / "SPY_15m.csv"
    _hourly_cache(
        path,
        [("2026-09-28 15:30:00-04:00", 100.0)],
        datetime(2026, 9, 28, 16, 5, tzinfo=NY),
    )
    monkeypatch.setattr(yfinance_provider, "_clock", lambda: datetime(2026, 10, 7, 10, 20, tzinfo=NY))
    frame = YFinanceProvider(tmp_path)._read_cache("SPY", "15m", "2026-09-28", "2026-10-01")
    assert frame is not None


def test_download_does_not_store_the_open_fifteen_or_five_minutes(tmp_path: Path, monkeypatch):
    index = pd.DatetimeIndex(
        [
            pd.Timestamp("2026-10-07 09:45", tz=NY),
            pd.Timestamp("2026-10-07 10:00", tz=NY),
        ]
    )
    frame = pd.DataFrame(
        {"open": [1, 2], "high": [2, 3], "low": [1, 2], "close": [1.5, 2.5], "volume": [10, 10]},
        index=index,
    )
    monkeypatch.setattr(yfinance_provider, "_clock", lambda: datetime(2026, 10, 7, 10, 7, tzinfo=NY))
    closed = _closed_hourly(frame, "15m", yfinance_provider._clock())
    assert list(closed.index.strftime("%H:%M")) == ["09:45"]
    five = pd.DataFrame(
        {"open": [1, 2], "high": [2, 3], "low": [1, 2], "close": [1.5, 2.5], "volume": [10, 10]},
        index=pd.DatetimeIndex(
            [pd.Timestamp("2026-10-07 10:00", tz=NY), pd.Timestamp("2026-10-07 10:05", tz=NY)]
        ),
    )
    five_closed = _closed_hourly(five, "5m", yfinance_provider._clock())
    assert list(five_closed.index.strftime("%H:%M")) == ["10:00"]


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


def test_an_empty_download_retries_and_uses_the_cached_file(tmp_path: Path, monkeypatch):
    path = tmp_path / "SPY_15m.csv"
    _hourly_cache(
        path,
        [("2026-10-06 15:30:00-04:00", 100.0)],
        datetime(2026, 10, 6, 16, 5, tzinfo=NY),
    )
    monkeypatch.setattr(yfinance_provider, "_clock", lambda: datetime(2026, 10, 7, 10, 20, tzinfo=NY))
    calls = {"n": 0}

    def empty_download(*_args, **_kwargs):
        calls["n"] += 1
        return pd.DataFrame()

    monkeypatch.setattr("yfinance.download", empty_download, raising=False)
    import yfinance

    monkeypatch.setattr(yfinance, "download", empty_download)
    monkeypatch.setattr(yfinance_provider.time, "sleep", lambda _seconds: None)
    provider = YFinanceProvider(tmp_path)
    frames = provider.history(["SPY", "QQQ"], "2026-10-06", "2026-10-08", "15m")
    assert "SPY" in frames
    assert float(frames["SPY"]["close"].iloc[-1]) == 100.0
    assert "QQQ" not in frames
    assert calls["n"] >= 3


def test_a_raising_download_does_not_abort_the_other_symbol(tmp_path: Path, monkeypatch):
    path = tmp_path / "QQQ_5m.csv"
    _hourly_cache(
        path,
        [("2026-10-06 15:30:00-04:00", 400.0)],
        datetime(2026, 10, 6, 16, 5, tzinfo=NY),
    )
    fresh = pd.DataFrame(
        {"open": [101.0], "high": [102.0], "low": [100.0], "close": [101.5], "volume": [10]},
        index=pd.DatetimeIndex([pd.Timestamp("2026-10-07 09:45", tz=NY)]),
    )

    def download(*_args, **kwargs):
        tickers = kwargs.get("tickers")
        if tickers == "QQQ":
            raise RuntimeError("possibly delisted")
        return fresh

    import yfinance

    monkeypatch.setattr(yfinance, "download", download)
    monkeypatch.setattr(yfinance_provider.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(yfinance_provider, "_clock", lambda: datetime(2026, 10, 7, 10, 20, tzinfo=NY))
    frames = YFinanceProvider(tmp_path).history(["SPY", "QQQ"], "2026-10-07", "2026-10-08", "5m")
    assert float(frames["SPY"]["close"].iloc[-1]) == 101.5
    assert float(frames["QQQ"]["close"].iloc[-1]) == 400.0
