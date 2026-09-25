from pathlib import Path

import pandas as pd

from webull_bot.data.yfinance_provider import YFinanceProvider


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
