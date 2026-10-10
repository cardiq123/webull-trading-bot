"""The Trapdoor size grid is frozen before any score. No network and no orders."""

from datetime import date, time
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from webull_bot.chart_reads.neckline import (
    FLAT,
    Event,
    _planned_target,
    prepare,
    select_events,
)
from webull_bot.chart_reads.trapdoor_aggressive import (
    GOAL,
    RUIN,
    STAKE,
    SIGNAL,
    add_months,
    catalog,
    choose_strike,
    contracts_for,
    credit_ticket,
    frozen_rules,
    half_spread,
    model_trust,
    n_trials,
    quote_ticket,
    rolling_stats,
    simulate_path,
    skew_bump,
    survives,
    to_fifteen,
    trapdoor_events,
)

NY = "America/New_York"


def test_the_family_is_frozen_and_the_signal_is_not_a_new_entry():
    cells = catalog()
    assert n_trials() == 234
    assert len(cells) == 234
    assert len({spec.id for spec in cells}) == 234
    assert cells[0].id == "trapdoor_atm_r1_c1_off"
    assert cells[-1].id == "vwap_atm_r1_f50_off"
    assert SIGNAL.id == "QQQ_confirmed_short_r1_0dte"
    assert all(spec.exit == "r1" for spec in cells if spec.strike == "atm")
    assert all(spec.skew == "off" for spec in cells if spec.strike == "atm")
    rules = frozen_rules()
    assert rules["registered_before_score"] is True
    assert rules["family"] == 234
    assert rules["live_trading"] is False
    assert rules["stake"] == 2500
    assert rules["goal"] == 10000
    assert rules["ruin"] == 500
    assert rules["daily_cap"] == {"trapdoor": 3, "vwap": 5}
    text = open("src/webull_bot/chart_reads/trapdoor_aggressive.py").read()
    research = open("src/webull_bot/chart_reads/research_trapdoor_aggressive.py").read()
    for banned in ("forward_trapdoor", "forward_vwap", "forward_chop", "place_option_order", "WEBULL_APP_SECRET"):
        assert banned not in text
        assert banned not in research


def test_skew_and_the_wide_otm_spread_follow_the_written_rule():
    assert skew_bump(0.50) == pytest.approx(0.0)
    assert skew_bump(0.40) == pytest.approx(0.015)
    assert skew_bump(0.30) == pytest.approx(0.030)
    assert skew_bump(0.20) == pytest.approx(0.045)
    assert half_spread(1.0, otm=False) == pytest.approx(0.015)
    assert half_spread(0.10, otm=True) == pytest.approx(0.02)
    assert half_spread(1.0, otm=True) == pytest.approx(0.08)
    when = pd.Timestamp("2024-01-02 10:00", tz=NY)
    strike, delta = choose_strike(480.0, when, 0.25, "atm")
    assert strike == 480.0
    assert delta == pytest.approx(0.5, abs=0.05)
    one, _delta = choose_strike(480.0, when, 0.25, "otm1")
    three, _far = choose_strike(480.0, when, 0.25, "otm3")
    assert one == 479.0
    assert three == 477.0
    aimed, aimed_delta = choose_strike(480.0, when, 0.25, "d20")
    assert aimed < strike
    assert aimed_delta < delta
    opened = quote_ticket("put", 100.0, 97.0, when, 0.20, True)
    assert opened is not None
    _debit, mid, ask = opened
    assert ask - mid == pytest.approx(half_spread(mid, True))
    assert model_trust("d20", 0.40) == "least"
    assert model_trust("atm", 1.20) == "ordinary"
    assert model_trust("otm1", 0.20) == "least"


def test_a_fixed_lot_is_skipped_whole_when_cash_cannot_pay_it():
    assert contracts_for("c10", equity=2500, settled=2500, debit=300) == 0
    assert contracts_for("c1", equity=2500, settled=2500, debit=300) == 1
    assert contracts_for("f50", equity=2500, settled=2500, debit=400) == 3
    assert contracts_for("f50", equity=2500, settled=400, debit=400) == 0
    day = date(2024, 1, 2)
    due = date(2024, 1, 3)
    expensive = [(day, due, 1, 2, 300.0, 100.0, 3.0)]
    skipped = simulate_path(expensive, day, day, "c10", cap=3)
    assert skipped["trades"] == 0
    assert skipped["skips"]["premium"] == 1
    assert skipped["ending"] == STAKE
    taken = simulate_path(expensive, day, day, "c1", cap=3)
    assert taken["trades"] == 1
    assert taken["ending"] == pytest.approx(STAKE - 300.0 + 100.0)


def test_three_trades_a_day_and_an_open_trade_blocks_the_next_signal():
    day = date(2024, 1, 2)
    due = date(2024, 1, 3)
    rows = [(day, due, index, index, 100.0, 110.0, 1.0) for index in range(1, 5)]
    path = simulate_path(rows, day, day, "c1", cap=3)
    assert path["trades"] == 3
    assert path["skips"]["cap"] == 1
    overlap = [
        (day, due, 1, 5, 100.0, 110.0, 1.0),
        (day, due, 4, 6, 100.0, 110.0, 1.0),
        (day, due, 6, 7, 100.0, 110.0, 1.0),
    ]
    blocked = simulate_path(overlap, day, day, "c1", cap=3)
    assert blocked["trades"] == 2
    assert blocked["skips"]["overlap"] == 1


def test_reaching_ten_thousand_and_ruin_are_counted_on_fresh_starts():
    start = date(2024, 1, 2)
    end = add_months(start, 12)
    assert end == date(2025, 1, 2)
    sessions = [start, date(2024, 6, 3), end]
    winner = [(start, date(2024, 1, 3), 1, 2, 500.0, 8000.0, 5.0)]
    rolled = rolling_stats(winner, sessions, end, "c1", cap=3)
    assert rolled["starts"] == 1
    assert rolled["p_reach_12"] == 1.0
    assert rolled["p_reach_4"] == 1.0
    assert rolled["p_ruin"] == 0.0
    assert rolled["median_days_to_goal"] == 0.0
    loser = [(start, date(2024, 1, 3), 1, 2, 2200.0, 0.0, 22.0)]
    broke = rolling_stats(loser, sessions, end, "c1", cap=3)
    assert broke["p_ruin"] == 1.0
    assert broke["p_reach_12"] == 0.0
    assert simulate_path(loser, start, start, "c1", cap=3)["ending"] < RUIN
    assert simulate_path(winner, start, start, "c1", cap=3)["ending"] >= GOAL


def test_two_r_is_twice_the_distance_and_1545_flattens():
    event = Event("QQQ", "short", "confirmed", 0, 1, 110.0, 100.0, 112.0, 109.99, False, False, False)
    assert _planned_target(None, event, 100.0, "r1") == pytest.approx(90.0)
    assert _planned_target(None, event, 100.0, "r2") == pytest.approx(80.0)
    index = pd.date_range("2024-01-02 15:40", periods=2, freq="5min", tz=NY)
    book = SimpleNamespace(
        open=np.array([100.0, 99.0]),
        high=np.array([101.0, 99.5]),
        low=np.array([98.0, 98.5]),
        close=np.array([99.0, 99.0]),
        dates=np.array([date(2024, 1, 2), date(2024, 1, 2)]),
        clocks=np.array([time(15, 40), time(15, 45)]),
        index=index,
    )
    from webull_bot.chart_reads.neckline import _walk

    reason, price, when = _walk(book, 0, "short", 110.0, 80.0, "r2")
    assert reason == "flat"
    assert price == pytest.approx(99.0)
    assert when == index[1]
    assert FLAT == time(15, 45)


def test_trapdoor_events_match_the_neckline_short_and_fifteen_minute_bars_roll_up():
    frame = _short_day()
    book = prepare(frame, "QQQ")
    assert trapdoor_events(book) == select_events(book.events, SIGNAL)
    fifteen = to_fifteen(frame)
    assert len(fifteen) == 26
    first = fifteen.iloc[0]
    assert first["open"] == pytest.approx(frame.iloc[0]["open"])
    assert first["high"] == pytest.approx(frame.iloc[:3]["high"].max())
    assert first["low"] == pytest.approx(frame.iloc[:3]["low"].min())
    assert first["close"] == pytest.approx(frame.iloc[2]["close"])


def test_the_gate_rejects_a_short_sample_and_a_deep_drawdown():
    good = {
        "trades": 300,
        "profit_factor": 1.2,
        "sharpe": 0.5,
        "max_drawdown": -0.2,
        "win_rate": 0.5,
    }
    assert survives(good, q_value=0.05, dsr=0.99)
    assert not survives(good, q_value=0.20, dsr=0.99)
    thin = dict(good)
    thin["trades"] = 299
    assert not survives(thin, q_value=0.01, dsr=0.99)
    deep = dict(good)
    deep["max_drawdown"] = -0.31
    assert not survives(deep, q_value=0.01, dsr=0.99)


def _short_day() -> pd.DataFrame:
    n = 78
    mid = np.zeros(n)
    for i in range(23):
        mid[i] = 104.0 - (104.0 - 96.2) * i / 22
    for i in range(23, 33):
        mid[i] = mid[22] + (98.6 - mid[22]) * (i - 22) / 10
    for i in range(33, 43):
        mid[i] = mid[32] + (96.3 - mid[32]) * (i - 32) / 10
    for i in range(43, n):
        mid[i] = mid[42] + (103.0 - mid[42]) * (i - 42) / (n - 43)
    opened = mid.copy()
    closed = mid.copy()
    high = mid + 0.12
    low = mid - 0.12
    low[22] = 96.00
    low[42] = 96.05
    high[32] = 99.20
    opened[52] = mid[52] + 0.30
    closed[52] = mid[52] - 0.25
    opened[64] = mid[64] + 0.20
    closed[64] = mid[64] - 0.15
    high = np.maximum(high, np.maximum(opened, closed))
    low = np.minimum(low, np.minimum(opened, closed))
    low[22] = min(float(low[22]), 96.00)
    low[42] = min(float(low[42]), 96.05)
    index = pd.date_range("2020-06-15 09:30", periods=n, freq="5min", tz=NY)
    raw = pd.DataFrame(
        {"open": opened, "high": high, "low": low, "close": closed, "volume": np.full(n, 1000.0)},
        index=index,
    )
    flipped = raw.copy()
    flipped["open"] = 200.0 - raw["open"]
    flipped["close"] = 200.0 - raw["close"]
    flipped["high"] = 200.0 - raw["low"]
    flipped["low"] = 200.0 - raw["high"]
    return flipped
