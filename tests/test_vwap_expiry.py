"""Expiry contracts on the VWAP extension. No network and no broker."""

from datetime import date

import pandas as pd

from webull_bot.chart_reads.vwap_band import FLAT, Signal
from webull_bot.chart_reads.vwap_expiry import (
    CONTRACTS,
    contract_name,
    expiry_session,
    iv_for_expiry,
    price_contracts,
    run_expiry_account,
    years_until,
)
from webull_bot.chart_reads.vwap_quality import frozen_rules

NY = "America/New_York"
DAY = date(2026, 10, 7)


def test_expiry_is_declared_and_friday_1dte_is_monday():
    text = frozen_rules()["expiry"]
    assert "0 DTE" in text and "7 DTE" in text and "VIX1D" in text and "not retuned" in text
    assert [contract_name(dte, hold) for dte, hold in CONTRACTS] == [
        "0dte-flat",
        "1dte-flat",
        "1dte-overnight",
        "3dte-flat",
        "3dte-overnight",
        "7dte-flat",
        "7dte-overnight",
    ]
    assert expiry_session(date(2026, 10, 2), 1) == date(2026, 10, 5)
    when = pd.Timestamp("2026-10-07 10:00", tz=NY)
    from webull_bot.chart_reads.vwap_band import _years

    assert years_until(when, DAY) == _years(when, 0)
    short = {DAY: (20.0, "VIX1D")}
    longer = {DAY: (15.0, "VIX")}
    assert iv_for_expiry(DAY, 0, short, longer) == 0.20
    assert iv_for_expiry(DAY, 1, short, longer) == 0.20
    assert iv_for_expiry(DAY, 7, short, longer) == 0.15
    assert iv_for_expiry(DAY, 1, {}, longer) == 0.15


def _signal(day: str, hour: str = "10:00") -> Signal:
    signal_time = pd.Timestamp(f"{day} {hour}", tz=NY)
    return Signal("SPY", "extension", "long", signal_time, signal_time + pd.Timedelta(minutes=15), 99.0, 100.0, 100.5, 2.0)


def _bars() -> pd.DataFrame:
    monday = pd.date_range("2026-10-05 10:15", periods=3, freq="15min", tz=NY)
    tuesday = pd.date_range("2026-10-06 10:00", periods=2, freq="15min", tz=NY)
    flat = pd.DatetimeIndex([pd.Timestamp("2026-10-06 15:45", tz=NY)])
    index = monday.append(tuesday).append(flat)
    close = [100.2, 100.3, 100.4, 100.5, 100.6, 100.7]
    return pd.DataFrame(
        {"open": close, "high": [item + 0.1 for item in close], "low": [item - 0.1 for item in close], "close": close, "volume": 1.0},
        index=index,
    )


def test_overnight_holds_past_the_entry_flat_and_settles_after_the_exit():
    bars = _bars()
    signal = _signal("2026-10-05", "10:00")
    # The 10:00 bar is not in the frame. The fill is 10:15, which is the first bar.
    signal = Signal("SPY", "extension", "long", pd.Timestamp("2026-10-05 10:00", tz=NY), bars.index[0], 99.0, 100.0, 100.5, 2.0)
    short = {date(2026, 10, 5): (20.0, "VIX1D"), date(2026, 10, 6): (20.0, "VIX1D")}
    longer = {date(2026, 10, 5): (15.0, "VIX"), date(2026, 10, 6): (15.0, "VIX")}
    books = price_contracts(bars, [signal], short, longer)
    flat = books["1dte-flat"][0]
    held = books["1dte-overnight"][0]
    assert flat.skip == ""
    assert held.skip == ""
    assert flat.exit_time == bars.index[2]
    assert held.exit_time == bars.index[-1]
    assert held.reason == "flat"
    assert books["7dte-flat"][0].debit > books["0dte-flat"][0].debit
    result = run_expiry_account(bars, books["1dte-overnight"], stake=1000.0)
    assert result["metrics"]["trades"] == 1
    assert result["spans"] == [(date(2026, 10, 5), date(2026, 10, 6))]
    assert FLAT == __import__("datetime").time(15, 45)
