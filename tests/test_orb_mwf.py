"""Frozen Monday/Wednesday/Friday opening-range rules, before any score."""

from datetime import date
from pathlib import Path

import pandas as pd

from webull_bot.chart_reads.dukascopy_spy import prices_are_bid_scale
from webull_bot.chart_reads.event_days import CPI_DATES, FOMC_DATES, NFP_DATES
from webull_bot.chart_reads.orb_mwf import (
    FRIDAY_0DTE,
    MONDAY_0DTE,
    RISK_PRIMARY,
    WEDNESDAY_0DTE,
    Break,
    SessionRead,
    contract_count,
    first_break,
    frozen_rules,
    has_spy_0dte,
    opening_bounds,
    scan,
    session_status,
    simulate,
    target_multiple,
    years_left,
)
from webull_bot.options.pricing import option_price

NY = "America/New_York"


def _frame(day: str, rows: list[tuple], minutes: int = 5) -> pd.DataFrame:
    index = []
    data = []
    for clock, opened, high, low, close in rows:
        index.append(pd.Timestamp(f"{day} {clock}", tz=NY))
        data.append((opened, high, low, close, 1_000.0))
    frame = pd.DataFrame(data, index=pd.DatetimeIndex(index), columns=["open", "high", "low", "close", "volume"])
    return frame


def _day_with(clocks: list[str], day: str = "2026-09-18") -> pd.DataFrame:
    rows = []
    for i, clock in enumerate(clocks):
        rows.append((clock, 10.0, 10.2, 9.8, 10.1))
    rows[0] = (clocks[0], 10.0, 10.0, 9.0, 9.5)
    return _frame(day, rows)


def test_frozen_constants_and_calendar():
    rules = frozen_rules()
    assert rules["risk"] == 100.0
    assert rules["dte"] == 0
    assert "no stop" in rules["exit"].lower()
    assert "+100%" in rules["exit"]
    assert "+50%" in rules["exit"]
    assert target_multiple("call") == 2.0
    assert target_multiple("put") == 1.5
    assert RISK_PRIMARY == 100.0
    assert session_status(date(2026, 10, 6)) == "weekday"
    assert session_status(date(2026, 9, 4)) == "event"
    assert session_status(date(2026, 9, 11)) == "event"
    assert session_status(date(2026, 9, 16)) == "event"
    assert session_status(date(2026, 10, 2)) == "event"
    assert session_status(date(2026, 9, 18)) == "trade"
    assert session_status(date(2026, 9, 7)) == "closed"
    assert session_status(date(2025, 9, 5)) == "event"
    assert session_status(date(2025, 8, 22)) == "trade"
    assert session_status(date(2022, 1, 12)) == "event"
    assert session_status(date(2022, 1, 26)) == "event"
    assert session_status(date(2016, 9, 2)) == "calendar_uncovered"
    assert has_spy_0dte(MONDAY_0DTE)
    assert not has_spy_0dte(date(2018, 2, 12))
    assert has_spy_0dte(WEDNESDAY_0DTE)
    assert not has_spy_0dte(date(2016, 8, 24))
    assert has_spy_0dte(FRIDAY_0DTE)
    assert not has_spy_0dte(date(2026, 10, 6))
    assert not has_spy_0dte(date(2024, 11, 14))


def test_range_is_the_first_candle_and_the_first_break_only():
    day = "2026-09-18"
    rows = [
        ("09:30", 9.4, 10.0, 9.0, 9.6),
        ("09:35", 9.6, 20.0, 9.5, 12.0),
        ("09:40", 12.0, 10.4, 9.7, 10.2),
        ("09:45", 10.2, 11.0, 8.0, 8.5),
        ("15:30", 10.0, 10.1, 9.9, 10.0),
    ]
    # The 09:40 bar is inside the first candle's 10 high. The 09:35 bar's
    # high of 20 must not become the range, and it is the only break.
    frame = _frame(day, rows)
    high, low, anchor = opening_bounds(frame, "5m")
    assert high == 10.0
    assert low == 9.0
    assert anchor.time().hour == 9 and anchor.time().minute == 30
    found, why = first_break(frame, "5m")
    assert why == "break"
    assert found is not None
    assert found.direction == "long"
    assert found.right == "call"
    assert found.break_time.strftime("%H:%M") == "09:35"
    assert found.gap is False
    reads = scan(frame, "5m")
    assert len([read for read in reads if read.status == "break"]) == 1


def test_equal_high_is_not_a_break_and_both_sides_skip():
    equal = _frame(
        "2026-09-18",
        [
            ("09:30", 9.5, 10.0, 9.0, 9.5),
            ("09:35", 9.5, 10.0, 9.2, 9.8),
            ("09:40", 9.8, 10.01, 9.4, 10.0),
            ("15:30", 10.0, 10.0, 10.0, 10.0),
        ],
    )
    found, _why = first_break(equal, "5m")
    assert found is not None
    assert found.break_time.strftime("%H:%M") == "09:40"
    both = _frame(
        "2026-09-18",
        [
            ("09:30", 9.5, 10.0, 9.0, 9.5),
            ("09:35", 9.5, 10.5, 8.5, 9.5),
            ("15:30", 9.5, 9.5, 9.5, 9.5),
        ],
    )
    assert first_break(both, "5m")[1] == "both_sides"


def test_one_minute_range_is_09_30_through_09_34():
    rows = [("09:30", 10, 10.2, 9.4, 10)]
    for minute in range(31, 41):
        rows.append((f"09:{minute:02d}", 10, 10.1, 9.5, 10))
    rows[4] = ("09:34", 10, 10.8, 9.2, 10)
    rows.append(("15:30", 10, 10, 10, 10))
    frame = _frame("2026-09-18", rows, minutes=1)
    high, low, anchor = opening_bounds(frame, "1m")
    assert high == 10.8
    assert low == 9.2
    assert anchor.strftime("%H:%M") == "09:34"
    missing = frame.iloc[1:]
    assert opening_bounds(missing, "1m") is None


def test_minutes_to_expiry_are_intraday():
    stamp = pd.Timestamp("2026-09-18 10:00", tz=NY)
    # 360 minutes is a fraction of a day, not a full day.
    assert years_left(stamp) == 360 / (365.0 * 24.0 * 60.0)
    fat = option_price("call", 100, 100, 1 / 365, 0.30, 0.02, 0.018)
    thin = option_price("call", 100, 100, years_left(stamp), 0.30, 0.02, 0.018)
    assert thin < fat / 2


def test_contract_budget_skips_when_one_contract_exceeds_it():
    assert contract_count(1.50, 100, 1000) == 0
    assert contract_count(0.80, 100, 1000) == 1
    assert contract_count(0.40, 100, 1000) == 2
    assert contract_count(0.40, 500, 1000) >= 2
    assert contract_count(0.80, 100, 50) == 0


def _quiet(day: str, extra: list[tuple] | None = None) -> pd.DataFrame:
    rows = [("09:30", 100, 101, 99, 100), ("09:35", 100, 101.2, 99.5, 100.5)]
    rows.extend(extra or [])
    rows.append(("15:25", 100, 100.05, 99.95, 100))
    rows.append(("15:30", 100, 100.02, 99.98, 100))
    return _frame(day, rows)


def test_level_fill_ignores_the_entry_wick_and_exits_at_1530():
    # The break bar's low is not a stop. A level fill does not use that bar,
    # and a quiet rest of the session is still open at 15:30.
    frame = _frame(
        "2026-09-18",
        [
            ("09:30", 100, 101, 99, 100),
            ("15:20", 100, 101.5, 99.1, 101),
            ("15:25", 101.06, 101.07, 101.05, 101.06),
            ("15:30", 101.06, 101.07, 101.05, 101.06),
        ],
    )
    found, why = first_break(frame, "5m")
    assert why == "break" and found is not None
    assert found.break_time.strftime("%H:%M") == "15:20"
    read = SessionRead(date(2026, 9, 18), "break", None, found, 101, 99)
    iv = {date(2026, 9, 18): (20.0, "VIX1D")}
    book = simulate(frame, [read], iv, risk=500, account="cash")
    assert book["trades"] == 1
    assert book["rows"][0]["reason"] == "time"
    assert book["rows"][0]["manage"] == "level"
    assert book["premium_skipped"] == 0


def test_an_adverse_wick_is_not_a_stop_and_a_target_still_fills():
    # The 09:40 bar trades to 70 and to 130. There is no stop, so the call
    # target is the exit even though the same bar also trades far against it.
    frame = _frame(
        "2026-09-18",
        [
            ("09:30", 100, 101, 99, 100),
            ("09:35", 100, 101.5, 99.8, 101),
            ("09:40", 101, 130, 70, 100),
            ("15:30", 100, 100, 100, 100),
        ],
    )
    found, _why = first_break(frame, "5m")
    read = SessionRead(date(2026, 9, 18), "break", None, found)
    book = simulate(frame, [read], {date(2026, 9, 18): (30.0, "VIX")}, risk=500)
    assert book["trades"] == 1
    row = book["rows"][0]
    assert row["reason"] == "target"
    assert abs(row["exit"] - row["ask"] * 2.0) < 1e-9
    assert "stop" not in book["reasons"]


def test_target_fills_at_the_limit():
    frame = _frame(
        "2026-09-18",
        [
            ("09:30", 100, 101, 99, 100),
            ("09:35", 100, 101.2, 99.9, 101),
            ("09:40", 101, 140, 101.0, 130),
            ("15:30", 130, 130, 130, 130),
        ],
    )
    found, _why = first_break(frame, "5m")
    read = SessionRead(date(2026, 9, 18), "break", None, found)
    book = simulate(frame, [read], {date(2026, 9, 18): (30.0, "VIX")}, risk=500)
    row = book["rows"][0]
    assert row["reason"] == "target"
    assert abs(row["exit"] - row["ask"] * 2.0) < 1e-9


def test_gap_adverse_move_is_held_to_the_close():
    frame = _frame(
        "2026-09-18",
        [
            ("09:30", 100, 101, 99, 100),
            ("09:35", 110, 110.4, 102, 108),
            ("15:30", 90, 90, 90, 90),
        ],
    )
    found, why = first_break(frame, "5m")
    assert why == "break" and found is not None and found.gap is True
    read = SessionRead(date(2026, 9, 18), "break", None, found)
    book = simulate(frame, [read], {date(2026, 9, 18): (30.0, "VIX")}, risk=500)
    row = book["rows"][0]
    assert row["manage"] == "gap"
    assert row["reason"] == "time"
    assert row["exit"] < row["ask"] * 0.5


def test_put_target_is_fifty_percent_and_fills_at_the_limit():
    frame = _frame(
        "2026-09-18",
        [
            ("09:30", 100, 101, 99, 100),
            ("09:35", 100, 100.2, 98.8, 99.5),
            ("09:40", 99.5, 99.6, 70, 80),
            ("15:30", 80, 80, 80, 80),
        ],
    )
    found, why = first_break(frame, "5m")
    assert why == "break" and found is not None and found.right == "put"
    read = SessionRead(date(2026, 9, 18), "break", None, found)
    book = simulate(frame, [read], {date(2026, 9, 18): (30.0, "VIX")}, risk=500)
    row = book["rows"][0]
    assert row["reason"] == "target"
    assert abs(row["exit"] - row["ask"] * 1.5) < 1e-9


def test_event_day_and_tuesday_are_not_trades():
    pieces = []
    for day, high in (("2026-10-02", 11.0), ("2026-10-05", 11.0), ("2026-10-06", 11.0)):
        pieces.append(
            _frame(
                day,
                [
                    ("09:30", 10, 10.2, 9.8, 10),
                    ("09:35", 10, high, 9.9, 10.5),
                    ("15:30", 10.5, 10.5, 10.5, 10.5),
                ],
            )
        )
    frame = pd.concat(pieces)
    statuses = {read.day.isoformat(): read.status for read in scan(frame, "5m")}
    assert statuses["2026-10-02"] == "event"
    assert statuses["2026-10-05"] == "break"
    assert statuses["2026-10-06"] == "weekday"


def test_margin_blocks_the_fourth_when_a_thursday_holiday_pulls_it_in():
    # Thanksgiving 2025 is Thursday. Five business days ending Dec 1 contain
    # four Monday/Wednesday/Friday sessions. The calendar year is uncovered
    # for events, so the reads are passed in already marked as breaks.
    days = [date(2025, 11, 24), date(2025, 11, 26), date(2025, 11, 28), date(2025, 12, 1)]
    pieces = []
    reads = []
    iv = {}
    for day in days:
        text = day.isoformat()
        pieces.append(
            _frame(
                text,
                [
                    ("09:30", 100, 101, 99, 100),
                    ("15:20", 100, 101.4, 99.8, 101),
                    ("15:25", 101, 101.05, 100.9, 101),
                    ("15:30", 101, 101, 101, 101),
                ],
            )
        )
        orb = Break(day, "long", "call", pd.Timestamp(f"{text} 15:20", tz=NY), 101.0, 99.0, 101.0, False)
        reads.append(SessionRead(day, "break", None, orb, 101.0, 99.0))
        iv[day] = (20.0, "VIX1D")
    frame = pd.concat(pieces)
    margin = simulate(frame, reads, iv, risk=500, account="margin")
    cash = simulate(frame, reads, iv, risk=500, account="cash")
    assert margin["trades"] == 3
    assert margin["pdt_blocked"] == 1
    assert cash["trades"] == 4
    assert cash["pdt_blocked"] == 0


def test_event_calendar_covers_2017_through_2026_and_skips_notation_votes():
    for year in range(2017, 2027):
        cpi = [day for day in CPI_DATES if day.year == year]
        nfp = [day for day in NFP_DATES if day.year == year]
        fomc = [day for day in FOMC_DATES if day.year == year]
        assert len(cpi) >= 11, year
        assert len(nfp) >= 11, year
        assert len(fomc) >= 8, year
    assert date(2025, 10, 24) in CPI_DATES
    assert date(2025, 11, 20) in NFP_DATES
    assert date(2025, 12, 18) in CPI_DATES
    assert date(2025, 8, 22) not in FOMC_DATES
    assert date(2020, 3, 3) in FOMC_DATES
    assert date(2020, 3, 15) in FOMC_DATES
    assert date(2020, 3, 19) not in FOMC_DATES
    assert date(2019, 10, 4) not in FOMC_DATES
    assert date(2019, 10, 11) in FOMC_DATES
    assert date(2026, 9, 16) in FOMC_DATES
    assert date(2026, 10, 2) in NFP_DATES


def test_bid_candle_scale_rejects_a_tick_mid():
    bid = pd.DataFrame({"open": [100.001], "high": [100.002], "low": [100.0], "close": [100.001]})
    mid = pd.DataFrame({"open": [100.0015], "high": [100.002], "low": [100.0], "close": [100.001]})
    assert prices_are_bid_scale(bid)
    assert not prices_are_bid_scale(mid)


def test_sources_do_not_touch_the_forward_test():
    root = Path("src/webull_bot/chart_reads")
    for name in ("orb_mwf.py", "event_days.py", "research_orb_mwf.py", "dukascopy_spy.py"):
        text = (root / name).read_text()
        for banned in ("forward_options", "forward_chop", "option_quote", "place_option_order", "mark_options"):
            assert banned not in text
