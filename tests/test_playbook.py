"""Combined playbook grid. No network and no broker."""

from datetime import date, time
from pathlib import Path

import numpy as np
import pandas as pd

from webull_bot.chart_reads.ema_reclaim import Prepared
from webull_bot.chart_reads.playbook import (
    CONTRACTS,
    CUTOFFS,
    GRID_SIZE,
    SIMPLE_CELL,
    STACKS,
    Exit,
    Play,
    Ticket,
    _stack_triggers,
    cells,
    exit_underlying,
    expiry_session,
    folds,
    frozen_rules,
    index_tickets,
    iv_for_expiry,
    neighbors,
    run_cell,
    run_plan,
    select_cell,
    stack_pair,
    years_until,
)

NY = "America/New_York"
DAY = date(2026, 10, 7)


def _prep(stamps, close, ema9, ema20, high=None, low=None, open_=None) -> Prepared:
    index = pd.DatetimeIndex(stamps)
    count = len(index)
    close = np.asarray(close, dtype=float)
    high = close + 0.2 if high is None else np.asarray(high, dtype=float)
    low = close - 0.2 if low is None else np.asarray(low, dtype=float)
    opened = close.copy() if open_ is None else np.asarray(open_, dtype=float)
    zeros = np.zeros(count, dtype=float)
    flags = np.zeros(count, dtype=bool)
    return Prepared(
        index=index,
        open=opened,
        high=high,
        low=low,
        close=close,
        volume=np.full(count, 1000.0),
        ema9=np.asarray(ema9, dtype=float),
        ema20=np.asarray(ema20, dtype=float),
        ema200=np.full(count, 770.0),
        atr=np.ones(count),
        vwap=np.full(count, 776.0),
        std=np.full(count, 1.0),
        macd_line=zeros,
        macd_signal=zeros,
        macd_hist=zeros,
        rsi=np.full(count, 50.0),
        hammer=flags,
        engulf_bull=flags,
        morning=flags,
        shooting=flags,
        engulf_bear=flags,
        evening=flags,
        dates=[stamp.date() for stamp in index],
        times=[stamp.time() for stamp in index],
    )


def _afternoon() -> Prepared:
    """15:05 is not under both averages. 15:10 and 15:15 are. 15:20 is the fill."""
    stamps = pd.date_range("2026-10-07 15:00", periods=6, freq="5min", tz=NY)
    # 15:00 above, 15:05 mixed (under the 9, above the 20), then two unders, then the fill bar.
    close = [777.65, 777.35, 777.20, 777.17, 777.20, 777.19]
    ema9 = [777.49, 777.43, 777.39, 777.34, 777.32, 777.30]
    ema20 = [777.33, 777.33, 777.32, 777.31, 777.30, 777.29]
    high = [777.84, 777.49, 777.43, 777.33, 777.26, 777.23]
    low = [777.56, 777.03, 777.17, 777.01, 776.93, 776.90]
    opened = [777.58, 777.32, 777.35, 777.22, 777.20, 777.19]
    return _prep(stamps, close, ema9, ema20, high, low, opened)


def _metrics(sharpe: float, trades: int = 100) -> dict:
    return {
        "trades": trades,
        "sharpe": sharpe,
        "profit_factor": 1.2,
        "max_drawdown": -0.2,
        "win_rate": 0.5,
    }


def _ticket(setup, clock, pnl, stack_ok=False, priority=0) -> Ticket:
    fill = pd.Timestamp(f"2026-10-07 {clock}", tz=NY)
    exit_at = fill + pd.Timedelta(minutes=5)
    path = type("Path", (), {})  # placeholder replaced below
    from webull_bot.chart_reads.playbook import Path

    priced = Path(exit_at, 100.0, 100.0 + pnl, pnl, "target")
    paths = {"1r": priced, ("1r", "stack"): priced}
    return Ticket(setup, DAY, fill, priority, paths, stack_ok)


def test_grid_is_frozen_at_5376_cells():
    assert frozen_rules()["grid_size"] == GRID_SIZE == 5376
    assert len(cells()) == 5376
    assert len(set(cells())) == 5376
    assert STACKS == ("off", "exit", "confirm", "both")
    assert CUTOFFS == (None, time(15, 0), time(15, 15))
    assert CONTRACTS == (
        (0, "flat"),
        (1, "flat"),
        (1, "overnight"),
        (3, "flat"),
        (3, "overnight"),
        (7, "flat"),
        (7, "overnight"),
    )
    assert SIMPLE_CELL == ("trend", 3, "1r", "off", None, 0, "flat")
    assert all(not (dte == 0 and hold == "overnight") for *_head, dte, hold in cells())
    universe = set(cells())
    for cell in (
        cells()[0],
        ("all", 5, "ema20", "both", time(15, 15), 7, "overnight"),
        ("confirmed", 3, "1r", "exit", time(15, 0), 0, "flat"),
        ("turn", 5, "band", "confirm", None, 3, "flat"),
    ):
        assert cell in universe
        for neighbor in neighbors(cell):
            assert neighbor in universe
            assert neighbor != cell
    assert ("trend", 3, "1r", "exit", None, 0, "flat") in neighbors(SIMPLE_CELL)
    assert ("trend", 3, "1r", "off", time(15, 0), 0, "flat") in neighbors(SIMPLE_CELL)
    assert ("trend", 3, "1r", "off", None, 1, "flat") in neighbors(SIMPLE_CELL)
    assert ("trend", 3, "1r", "off", None, 1, "overnight") not in neighbors(SIMPLE_CELL)


def test_folds_do_not_overlap_their_own_test():
    found = folds()
    assert len(found) == 7
    assert found[0].test_start == date(2020, 1, 1)
    assert found[-1].test_end == date(2026, 10, 6)
    for fold in found:
        assert fold.train_end < fold.test_start
        assert fold.train_start == date(fold.test_start.year - 3, 1, 1)
        assert fold.train_end == date(fold.test_start.year - 1, 12, 31)


def test_selection_prefers_the_stable_neighborhood():
    table = {cell: _metrics(0.2) for cell in cells()}
    table[("all", 5, "prem100", "both", time(15, 0), 7, "overnight")] = _metrics(5.0)
    for cell in (SIMPLE_CELL, *neighbors(SIMPLE_CELL)):
        table[cell] = _metrics(0.9)
    picked, eligible = select_cell(table)
    assert eligible is True
    assert picked == SIMPLE_CELL
    fallback, ok = select_cell({cell: _metrics(3.0, trades=10) for cell in cells()})
    assert ok is False
    assert fallback == SIMPLE_CELL


def test_two_closes_under_both_averages_trigger_the_1520_put():
    prep = _afternoon()
    assert stack_pair(prep, 2, "short") is False
    assert stack_pair(prep, 3, "short") is True
    triggers = _stack_triggers(prep, {}, np.full(6, np.nan), np.full(6, np.nan))
    shorts = [item for item in triggers if item.direction == "short"]
    assert len(shorts) == 1
    assert shorts[0].setup == "stack2"
    assert shorts[0].signal_time == pd.Timestamp("2026-10-07 15:15", tz=NY)
    assert shorts[0].fill_time == pd.Timestamp("2026-10-07 15:20", tz=NY)
    assert shorts[0].stack_ok is True
    assert shorts[0].stop == max(777.43, 777.33) + 0.01


def test_a_third_close_in_the_same_streak_does_not_fire_again():
    stamps = pd.date_range("2026-10-07 15:10", periods=4, freq="5min", tz=NY)
    close = [777.0, 776.8, 776.6, 776.4]
    emas = [778.0, 778.0, 778.0, 778.0]
    prep = _prep(stamps, close, emas, emas)
    triggers = [item for item in _stack_triggers(prep, {}, np.full(4, np.nan), np.full(4, np.nan)) if item.direction == "short"]
    assert len(triggers) == 1
    assert triggers[0].signal_time == pd.Timestamp("2026-10-07 15:15", tz=NY)


def test_two_closes_above_both_averages_trigger_the_call():
    stamps = pd.date_range("2026-10-07 10:00", periods=4, freq="5min", tz=NY)
    close = [100.0, 102.0, 103.0, 104.0]
    emas = [101.0, 101.0, 101.0, 101.0]
    low = [99.0, 101.5, 102.5, 103.5]
    prep = _prep(stamps, close, emas, emas, low=low, open_=[100.0, 101.5, 102.5, 103.5])
    longs = [item for item in _stack_triggers(prep, {}, np.full(4, np.nan), np.full(4, np.nan)) if item.direction == "long"]
    assert len(longs) == 1
    assert longs[0].fill_time == pd.Timestamp("2026-10-07 10:15", tz=NY)
    assert longs[0].stop == min(101.5, 102.5) - 0.01


def test_one_close_under_only_the_20_does_not_count():
    stamps = pd.date_range("2026-10-07 15:10", periods=3, freq="5min", tz=NY)
    # Under the 20, still above the 9.
    prep = _prep(stamps, [777.2, 777.2, 777.2], [777.0, 777.0, 777.0], [777.4, 777.4, 777.4])
    assert _stack_triggers(prep, {}, np.full(3, np.nan), np.full(3, np.nan)) == []


def test_long_exits_at_the_second_close_under_both_averages():
    prep = _afternoon()
    play = Play(
        "vwap",
        "long",
        DAY,
        prep.index[0],
        prep.index[0],
        0,
        770.0,
        time(15, 45),
        float("nan"),
        0,
        False,
    )
    outcome = exit_underlying(prep, play, "1r", None, stack_exit=True)
    assert outcome == Exit("stack2", 777.17, prep.index[3], None)
    held = exit_underlying(prep, play, "1r", None, stack_exit=False)
    assert held.reason != "stack2"


def test_closes_before_the_fill_do_not_exit_the_new_trade():
    stamps = pd.date_range("2026-10-07 15:00", periods=4, freq="5min", tz=NY)
    close = [776.0, 776.0, 778.0, 778.5]
    emas = [777.0, 777.0, 777.0, 777.0]
    prep = _prep(stamps, close, emas, emas, open_=[778.5, 778.5, 778.5, 778.5])
    play = Play("vwap", "long", DAY, prep.index[1], prep.index[2], 2, 770.0, time(15, 30), float("nan"), 0, False)
    outcome = exit_underlying(prep, play, "1r", None, stack_exit=True)
    assert outcome.reason != "stack2"


def test_cutoff_blocks_the_1520_fill_and_keeps_a_fill_at_the_cutoff():
    late = _ticket("stack2", "15:20", 10.0, stack_ok=True, priority=7)
    on_time = _ticket("vwap", "15:00", 5.0, priority=0)
    indexed = index_tickets([late, on_time])
    days = [DAY]

    def run(cutoff):
        plan = {DAY: (frozenset({"vwap", "stack2"}), 5, "1r", "off", cutoff)}
        return run_plan(indexed, days, plan, 1000.0)

    assert run(None)["metrics"]["trades"] == 2
    assert run(time(15, 0))["metrics"]["trades"] == 1
    assert run(time(15, 0))["skips"]["cutoff"] == 1
    assert run(time(15, 15))["metrics"]["trades"] == 1
    assert run(time(15, 15))["skips"]["cutoff"] == 1


def test_confirm_keeps_the_pair_and_drops_an_unconfirmed_short():
    put = _ticket("stack2", "15:20", 8.0, stack_ok=True, priority=7)
    other = _ticket("vwap", "10:15", 20.0, stack_ok=False, priority=0)
    indexed = index_tickets([put, other])
    cell = ("trend", 5, "1r", "confirm", None)
    result = run_cell(indexed, [DAY], cell, 1000.0)
    assert result["metrics"]["trades"] == 1
    assert result["skips"]["stack"] == 1
    assert result["pnls"] == [8.0]


def test_cap_drops_the_later_trade_and_overlap_does_not_use_a_slot():
    from webull_bot.chart_reads.playbook import Path

    day = DAY
    rows = []
    for offset, clock in enumerate(("10:00", "10:30", "11:00", "11:30")):
        fill = pd.Timestamp(f"2026-10-07 {clock}", tz=NY)
        path = Path(fill + pd.Timedelta(minutes=10), 50.0, 60.0, 10.0, "target")
        rows.append(Ticket("vwap", day, fill, 0, {"1r": path}, False))
    overlap_fill = pd.Timestamp("2026-10-07 10:05", tz=NY)
    overlap_path = Path(overlap_fill + pd.Timedelta(minutes=5), 50.0, 40.0, -10.0, "stop")
    rows.append(Ticket("wick", day, overlap_fill, 3, {"1r": overlap_path}, False))
    result = run_plan(
        index_tickets(rows),
        [day],
        {day: (frozenset({"vwap", "wick"}), 3, "1r", "off", None)},
        1000.0,
    )
    assert result["metrics"]["trades"] == 3
    assert result["skips"]["cap"] == 1
    assert result["skips"]["overlap"] == 1
    assert result["pnls"] == [10.0, 10.0, 10.0]


def test_friday_1dte_expires_monday_and_vol_follows_the_tenor():
    friday = date(2026, 10, 2)
    assert expiry_session(friday, 0) == friday
    assert expiry_session(friday, 1) == date(2026, 10, 5)
    assert expiry_session(date(2026, 10, 5), 3) == date(2026, 10, 8)
    when = pd.Timestamp("2026-10-07 15:20", tz=NY)
    from webull_bot.chart_reads.band_exit import _years

    assert years_until(when, DAY) == _years(when, 0)
    short = {DAY: (20.0, "VIX1D")}
    longer = {DAY: (15.0, "VIX")}
    assert iv_for_expiry(DAY, 0, short, longer) == 0.20
    assert iv_for_expiry(DAY, 1, short, longer) == 0.20
    assert iv_for_expiry(DAY, 3, short, longer) == 0.15
    assert iv_for_expiry(DAY, 7, short, longer) == 0.15
    assert iv_for_expiry(DAY, 1, {}, longer) == 0.15


def test_overnight_holds_past_the_entry_close_and_flats_on_expiry():
    stamps = pd.to_datetime(
        [
            "2026-10-05 15:20",
            "2026-10-05 15:25",
            "2026-10-06 09:30",
            "2026-10-06 15:25",
            "2026-10-06 15:30",
        ]
    ).tz_localize(NY)
    close = [777.0, 777.1, 777.2, 777.3, 777.4]
    emas = [776.0, 776.0, 776.0, 776.0, 776.0]
    prep = _prep(stamps, close, emas, emas, open_=close)
    play = Play("vwap", "long", date(2026, 10, 5), prep.index[0], prep.index[0], 0, 700.0, time(15, 30), float("nan"), 0, False)
    held = exit_underlying(prep, play, "1r", None, dte=1, hold="overnight")
    assert held.reason == "flat"
    assert held.when == prep.index[4]
    same_day = exit_underlying(prep, play, "1r", None, dte=1, hold="flat")
    assert same_day.when == prep.index[1]
    assert same_day.reason == "last"


def test_overnight_credit_settles_the_session_after_the_exit():
    from webull_bot.chart_reads.playbook import Path

    monday = date(2026, 10, 5)
    tuesday = date(2026, 10, 6)
    fill = pd.Timestamp("2026-10-05 10:00", tz=NY)
    exit_at = pd.Timestamp("2026-10-06 10:00", tz=NY)
    path = Path(exit_at, 100.0, 150.0, 50.0, "target")
    later = Path(pd.Timestamp("2026-10-06 11:00", tz=NY), 950.0, 960.0, 10.0, "target")
    key = ("1r", "off", 1, "overnight")
    indexed = index_tickets(
        [
            Ticket("vwap", monday, fill, 0, {key: path}, False),
            Ticket("vwap", tuesday, pd.Timestamp("2026-10-06 11:00", tz=NY), 0, {key: later}, False),
        ]
    )
    plan = {
        monday: (frozenset({"vwap"}), 3, "1r", "off", None, 1, "overnight"),
        tuesday: (frozenset({"vwap"}), 3, "1r", "off", None, 1, "overnight"),
    }
    result = run_plan(indexed, [monday, tuesday], plan, 1000.0)
    assert result["metrics"]["trades"] == 1
    assert result["skips"]["premium"] == 1
    assert list(result["equity"]) == [1000.0, 1050.0]
    assert result["spans"] == [(monday, tuesday)]


def test_modules_do_not_import_the_broker():
    for name in ("playbook.py", "research_playbook.py"):
        text = Path("src/webull_bot/chart_reads", name).read_text()
        for banned in ("forward_options", "forward_chop", "place_option_order", "live_trading_enabled", "option_quote"):
            assert banned not in text
