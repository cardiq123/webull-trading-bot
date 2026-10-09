"""The 0 DTE quote inversion. No market data and no orders."""

from datetime import date

import pandas as pd

from webull_bot.chart_reads.odte_calibration import (
    QUOTE_TIME,
    calibrate,
    contracts_for,
    daily_equity,
    half_spread,
    implied_vol,
    model_mid,
)


def test_eleven_thirty_six_quote_is_about_1_67_times_vix1d():
    fitted = calibrate(10.24)
    assert abs(fitted["quote_mid"] - 1.135) < 1e-9
    assert abs(fitted["model_at_prior"] - 0.659) < 0.01
    assert abs(fitted["multiplier_0dte"] - 1.67) < 0.02
    assert abs(fitted["implied_0dte"] - 0.171) < 0.005
    assert fitted["additive_points"] > 6.0
    assert fitted["minutes_if_vol_unchanged"] > 600
    assert fitted["book_minutes"] < 300


def test_logged_model_matches_the_october_6_close():
    priced = [
        model_mid("call", 776.885, 777.0, QUOTE_TIME, 8.69 / 100.0, dte)
        for dte in (0, 3, 4, 5)
    ]
    logged = (0.548, 2.51, 2.90, 3.25)
    for got, want in zip(priced, logged):
        assert abs(got - want) < 0.02


def test_one_cent_width_is_half_a_cent_each_side():
    assert half_spread(1.14, "0.01") == 0.005
    assert half_spread(1.14, "0.02") == 0.01
    assert half_spread(0.50, "model") == 0.01
    assert abs(half_spread(2.0, "model") - 0.03) < 1e-12


def test_three_lot_is_skipped_whole_when_cash_is_short():
    assert contracts_for(3, 200.0, 100.0) == 0
    assert contracts_for(1, 200.0, 100.0) == 1
    day = date(2024, 1, 3)
    due = date(2024, 1, 4)
    cands = [(day, due, 1, 2, 100.0, 150.0, 1.0)]
    equity, pnls = daily_equity(cands, [day], qty=3, cap=5, stake=250.0)
    assert pnls == []
    assert float(equity.iloc[-1]) == 250.0
    equity, pnls = daily_equity(cands, [day], qty=1, cap=None, stake=250.0)
    assert pnls == [50.0]
    assert float(equity.iloc[-1]) == 300.0


def test_one_position_lock_ends_with_the_session():
    first = date(2018, 11, 23)
    second = date(2018, 11, 26)
    cands = [
        (first, second, 10, 100_000, 100.0, 110.0, 1.0),
        (second, date(2018, 11, 27), 20, 30, 100.0, 150.0, 1.0),
    ]
    _equity, pnls = daily_equity(cands, [first, second], qty=1, cap=3, stake=2500.0)
    assert pnls == [10.0, 50.0]


def test_implied_round_trip():
    iv = implied_vol("call", 776.885, 777.0, QUOTE_TIME, 1.135, 0)
    assert abs(model_mid("call", 776.885, 777.0, QUOTE_TIME, iv, 0) - 1.135) < 0.002
    assert isinstance(pd.Timestamp(QUOTE_TIME), pd.Timestamp)
