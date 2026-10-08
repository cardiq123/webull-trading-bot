"""The scale-out exit sells two contracts at the band and keeps one runner."""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from webull_bot.chart_reads.scale_out import (
    CONTRACTS,
    EXITS,
    PRIMARY_STAKE,
    credit_of,
    debit_of,
    n_trials,
    prior_bands,
    simulate_account,
    tendency_eligible,
    walk_legs,
)


class Spot:
    """The model mid equals the underlying, so a premium stop is a spot stop."""

    def mid(self, spot, minute):
        return float(spot)

    def bid(self, spot, minute):
        return float(spot)

    def bid_for_mid(self, mid):
        return float(mid)


def _bars(rows, *, side="long", stop=9.0):
    frame = {
        "minute": np.array([row[0] for row in rows], dtype=int),
        "open": np.array([row[1] for row in rows], dtype=float),
        "high": np.array([row[2] for row in rows], dtype=float),
        "low": np.array([row[3] for row in rows], dtype=float),
        "close": np.array([row[4] for row in rows], dtype=float),
        "upper": np.array([row[5] for row in rows], dtype=float),
        "lower": np.array([row[6] for row in rows], dtype=float),
        "side": side,
        "stop": stop,
    }
    return frame


def test_catalog_stake_and_trial_count_are_frozen():
    assert PRIMARY_STAKE == 2500.0
    assert CONTRACTS == 3
    assert len(EXITS) == 6
    assert n_trials() == 18
    text = open("src/webull_bot/chart_reads/scale_out.py", encoding="utf-8").read()
    other = open("src/webull_bot/chart_reads/research_scale_out.py", encoding="utf-8").read()
    for name in ("forward_options", "forward_chop", "forward_vwap", "place_option_order", "live_trading_enabled", "option_quote"):
        assert name not in text
        assert name not in other


def test_a_stop_closes_all_three_before_the_band():
    path = _bars([(575, 10, 12.5, 8.5, 11, 12, 8)], stop=9)
    legs = walk_legs(path, "scale_prem10", Spot(), 10.0, debit_of(3, 10.0))
    assert [(leg["qty"], leg["reason"], leg["bid"]) for leg in legs] == [(3, "stop", 9.0)]


def test_scale_sells_two_at_the_band_and_the_runner_can_reach_fifty_percent():
    path = _bars(
        [
            (575, 10, 10.4, 9.6, 10.2, np.nan, np.nan),
            (580, 10.2, 12.4, 10.1, 12.0, 12, 8),
            (585, 12.0, 16.0, 11.8, 15.0, 12, 8),
        ],
        stop=9,
    )
    debit = debit_of(3, 10.0)
    band = walk_legs(path, "all_band", Spot(), 10.0, debit)
    assert [(leg["qty"], leg["reason"]) for leg in band] == [(3, "band")]
    scaled = walk_legs(path, "scale_prem10", Spot(), 10.0, debit)
    assert [(leg["qty"], leg["reason"], leg["bid"]) for leg in scaled] == [(2, "band", 12.0), (1, "runner_pct50", 15.0)]


def test_a_fill_already_through_the_band_scales_at_the_open():
    path = _bars([(575, 13, 13.5, 8.0, 12, 12, 8)], stop=7)
    legs = walk_legs(path, "scale_prem10", Spot(), 10.0, debit_of(3, 13.0))
    assert legs[0]["qty"] == 2 and legs[0]["reason"] == "band" and legs[0]["bid"] == 13
    assert legs[1]["reason"] == "runner_prem10" and legs[1]["bid"] == 9.0


def test_flat_is_the_1545_open():
    path = _bars(
        [
            (930, 10, 10.2, 9.8, 10.0, np.nan, np.nan),
            (945, 10.4, 11.0, 10.2, 10.8, np.nan, np.nan),
        ],
        stop=9,
    )
    legs = walk_legs(path, "r1", Spot(), 10.0, debit_of(3, 10.0))
    assert legs[-1]["reason"] == "flat" and legs[-1]["minute"] == 945 and legs[-1]["qty"] == 3


def test_one_r_loses_to_the_stop_on_the_same_bar():
    path = _bars([(575, 10, 12, 8, 11, np.nan, np.nan)], stop=9)
    legs = walk_legs(path, "r1", Spot(), 10.0, debit_of(3, 10.0))
    assert legs[0]["reason"] == "stop"


def test_full_position_stop_fills_at_a_ten_percent_loss():
    path = _bars(
        [
            (575, 10, 10.2, 9.6, 10.0, np.nan, np.nan),
            (580, 10.2, 11.2, 10.1, 11.0, 11, 8),
            (585, 11.0, 11.0, 1.0, 5.0, 11, 8),
        ],
        stop=8,
    )
    debit = debit_of(3, 10.0)
    legs = walk_legs(path, "scale_full10", Spot(), 10.0, debit)
    assert [leg["reason"] for leg in legs] == ["band", "runner_full10"]
    pnl = sum(credit_of(leg["qty"], leg["bid"]) for leg in legs) - debit
    assert pnl == pytest.approx(-0.10 * debit, abs=0.05)


def test_a_short_uses_the_lower_band():
    path = _bars([(575, 10, 10.5, 7.5, 8, 12, 8)], side="short", stop=11)
    legs = walk_legs(path, "all_band", Spot(), 10.0, debit_of(3, 10.0))
    assert legs[0]["reason"] == "band" and legs[0]["qty"] == 3 and legs[0]["spot"] == 8


def test_three_contracts_that_do_not_fit_are_skipped_and_do_not_block_a_cheaper_name():
    day = date(2024, 6, 3)
    leg = [{"qty": 3, "bid": 1.0, "minute": 600, "reason": "flat", "spot": 10.0}]

    def _row(symbol, debit, priority):
        return {
            "day": day,
            "symbol": symbol,
            "side": "long",
            "priority": priority,
            "entry_minute": 575,
            "debit": debit,
            "legs": {"r1": leg},
        }

    book = simulate_account(
        [_row("AAA", 4000.0, 10.0), _row("BBB", 200.0, 1.0)],
        "r1",
        day,
        day,
        2500.0,
        [day],
        cap=3,
    )
    assert book["skips"]["premium"] == 1
    assert book["metrics"]["trades"] == 1
    assert book["trades"][0]["symbol"] == "BBB"


def test_an_inconsistent_tendency_cell_is_not_a_trade():
    assert tendency_eligible([{"label": "inconsistent"}, {"label": "mean-reverting", "id": "keep"}]) == [
        {"label": "mean-reverting", "id": "keep"}
    ]


def test_the_first_bar_of_a_session_has_no_band():
    index = pd.date_range("2024-06-03 09:30", periods=4, freq="5min", tz="America/New_York")
    frame = pd.DataFrame(
        {"open": [10, 10, 11, 12], "high": [11, 12, 13, 14], "low": [9, 9, 10, 11], "close": [10, 11, 12, 13], "volume": [1, 1, 1, 1]},
        index=index,
    )
    bands = prior_bands(frame)
    assert np.isnan(bands["upper"].iloc[0])
    assert np.isfinite(bands["upper"].iloc[2])
