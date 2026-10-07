"""The three account books are frozen before any measured return is known."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from webull_bot.account_winners import (
    DUAL_LOOKBACK,
    DUAL_SKIP,
    HOLDOUT_START,
    RANDOM_SEED,
    SAMPLE_START,
    SMA_MONTHS,
    BookResult,
    buy_and_hold,
    frozen_rules,
    performance,
    recommend,
    shuffle_weights,
    simulate_weights,
    verdict,
    weights_from_monthly_dual,
    weights_from_monthly_gtaa,
    weights_from_monthly_trend,
    window_stats,
)
from webull_bot.costs import CostModel, buy_price

ROOT = Path(__file__).resolve().parents[1]


def _months(values: dict[str, list[float]], start: str = "2004-01-31") -> pd.DataFrame:
    count = len(next(iter(values.values())))
    index = pd.date_range(start, periods=count, freq="ME")
    return pd.DataFrame(values, index=index)


def test_rules_are_frozen_before_the_score():
    rules = frozen_rules()
    assert rules["sample_start"] == str(SAMPLE_START.date())
    assert rules["holdout_start"] == str(HOLDOUT_START.date())
    assert "10-month" in rules["conservative"]
    assert "else cash" in rules["conservative"]
    assert "12-1" in rules["moderate"]
    assert "No trailing stop" in rules["moderate"]
    assert "TQQQ" in rules["high_risk"]
    assert "Earns zero" in rules["cash"]
    assert SMA_MONTHS == 10
    assert (DUAL_LOOKBACK, DUAL_SKIP) == (12, 1)
    assert RANDOM_SEED == 17
    text = "\n".join(str(value) for value in rules.values())
    assert "104,429" not in text
    assert "ending equity" not in text.lower()


def test_gtaa_sleeve_is_equal_and_a_tie_with_the_average_is_cash():
    tied = _months({symbol: [10.0] * 10 for symbol in ("SPY", "EFA", "IEF", "GLD")})
    # A close that only equals the average is cash.
    weights = weights_from_monthly_gtaa(tied, months=10)
    assert float(weights.iloc[-1].sum()) == 0.0
    rising = _months({"SPY": list(range(10, 20)), "IEF": list(range(10, 20))})
    on = weights_from_monthly_gtaa(rising, months=10)
    assert on.iloc[-1].tolist() == [0.5, 0.5]
    # A later month that is not in the average yet cannot turn the prior signal on.
    extended = _months({"SPY": list(range(10, 21))})
    prior = weights_from_monthly_trend(extended["SPY"].iloc[:-1], months=10)
    later = weights_from_monthly_trend(extended["SPY"], months=10)
    assert float(prior.iloc[-1, 0]) == float(later.iloc[-2, 0])


def test_dual_momentum_holds_the_leader_or_cash():
    index_count = 14
    leader = [100.0] * 12 + [110.0, 130.0]
    laggard = [100.0] * 12 + [101.0, 102.0]
    frame = _months({"QQQ": leader, "SPY": laggard})
    weights = weights_from_monthly_dual(frame, lookback=12, skip=1)
    # 12-1 uses the close one month back. At the last row that close is 110 vs 101.
    assert weights.iloc[-1].idxmax() == "QQQ"
    assert float(weights.iloc[-1].sum()) == 1.0
    # Absolute 12-month return is negative for both, and the hurdle is zero.
    down = _months({"QQQ": [100.0] * 12 + [90.0, 80.0], "SPY": [100.0] * 12 + [95.0, 90.0]})
    cash = weights_from_monthly_dual(down, lookback=12, skip=1)
    assert float(cash.iloc[-1].sum()) == 0.0
    hurdle = pd.Series(0.50, index=frame.index)
    blocked = weights_from_monthly_dual(frame, hurdle=hurdle, lookback=12, skip=1)
    assert float(blocked.iloc[-1].sum()) == 0.0


def test_cash_account_buys_the_session_after_the_sale():
    clock = pd.bdate_range("2024-01-02", periods=6)
    signal = pd.DataFrame({"AAA": [0.0, 1.0], "BBB": [1.0, 0.0]}, index=pd.DatetimeIndex([clock[0], clock[2]]))
    opens = {
        "AAA": pd.Series([10.0, 10.0, 10.0, 10.0, 50.0, 50.0], index=clock),
        "BBB": pd.Series(20.0, index=clock),
    }
    closes = {
        "AAA": pd.Series([10.0, 10.0, 10.0, 50.0, 50.0, 50.0], index=clock),
        "BBB": pd.Series(20.0, index=clock),
    }
    flat_costs = CostModel(slippage_bps=0.0, half_spread_bps=0.0, sec_fee_per_dollar_sold=0.0, finra_taf_per_share=0.0)
    book = simulate_weights(
        clock,
        opens,
        closes,
        signal,
        starting_equity=1_000.0,
        trade_start=clock[0],
        trade_end=clock[-1],
        costs=flat_costs,
        same_day_buys=False,
    )
    # Cash is already settled, so the first buy fills the session after the signal.
    # The switch sells on the next session and cannot buy AAA until the session after that.
    # AAA's open has doubled by then, so the cash book misses the gap the margin book catches.
    assert book.entries == 2
    assert book.exits == 1
    assert book.equity.loc[clock[1]] == 1_000.0
    assert book.equity.loc[clock[3]] == 1_000.0
    assert book.equity.loc[clock[4]] == 1_000.0
    margin = simulate_weights(
        clock,
        opens,
        closes,
        signal,
        starting_equity=1_000.0,
        trade_start=clock[0],
        trade_end=clock[-1],
        costs=flat_costs,
        same_day_buys=True,
    )
    assert margin.equity.loc[clock[3]] == 5_000.0


def test_signal_day_does_not_trade_and_costs_worsen_the_buy():
    clock = pd.bdate_range("2024-06-03", periods=4)
    signal = pd.DataFrame({"SPY": [1.0]}, index=pd.DatetimeIndex([clock[0]]))
    opens = {"SPY": pd.Series([100.0, 100.0, 100.0, 100.0], index=clock)}
    closes = {"SPY": pd.Series([100.0, 110.0, 110.0, 110.0], index=clock)}
    costs = CostModel()
    book = simulate_weights(
        clock,
        opens,
        closes,
        signal,
        starting_equity=1_000.0,
        trade_start=clock[0],
        trade_end=clock[-1],
        costs=costs,
    )
    assert book.equity.loc[clock[0]] == 1_000.0
    paid = buy_price(100.0, costs)
    shares = 1_000.0 / paid
    assert book.equity.loc[clock[1]] == pytest.approx(shares * 110.0)
    assert book.equity.loc[clock[1]] < 1_100.0


def test_shuffle_keeps_the_weights_and_changes_the_dates():
    frame = pd.DataFrame({"SPY": [1.0, 0.0, 0.5], "IEF": [0.0, 1.0, 0.5]})
    shuffled = shuffle_weights(frame, seed=17)
    assert shuffled.to_numpy().sum() == frame.to_numpy().sum()
    assert not shuffled.equals(frame)
    assert shuffle_weights(frame, seed=17).equals(shuffled)


def test_winner_rule_rejects_a_training_loss_and_a_raw_return_gap():
    train = {"years": 10, "cagr": 0.05}
    holdout = {"years": 9, "cagr": 0.08, "sharpe": 0.9, "calmar": 0.8, "max_drawdown": -0.10}
    spy = {"years": 9, "cagr": 0.12, "sharpe": 0.6, "calmar": 0.4, "max_drawdown": -0.30}
    called = verdict(holdout, spy, train)
    assert called["winner_vs_spy"]
    assert called["path_risk"]
    assert not called["beats_spy_raw"]
    broke = verdict(holdout, spy, {"years": 10, "cagr": -0.01})
    assert not broke["winner_vs_spy"]
    short = dict(holdout)
    short["years"] = 3
    assert not verdict(short, spy, train)["winner_vs_spy"]
    similar = {
        "years": 9,
        "cagr": 0.10,
        "sharpe": 0.4,
        "calmar": 0.3,
        "max_drawdown": -0.15,
    }
    path = verdict(similar, spy, train)
    assert path["path_similar"]
    assert path["winner_vs_spy"]
    benchmark = {"sharpe": 0.2, "max_drawdown": -0.70}
    assert verdict(holdout, spy, train, benchmark)["winner_vs_benchmark"]
    worse_benchmark = {"sharpe": 1.5, "max_drawdown": -0.05}
    assert not verdict(holdout, spy, train, worse_benchmark)["winner_vs_benchmark"]


def test_recommendation_follows_the_spy_test_only():
    def book(name: str, calmar: float, wins: bool) -> dict:
        return {
            "name": name,
            "holdout": {"calmar": calmar},
            "verdict": {"winner_vs_spy": wins, "winner_vs_benchmark": True},
        }

    chosen = recommend(
        [
            book("conservative", 0.4, True),
            book("moderate", 0.9, True),
            book("high_risk", 1.5, False),
        ]
    )
    assert chosen["pick"] == "moderate"
    none = recommend([book("conservative", 0.4, False), book("high_risk", 2.0, False)])
    assert none["pick"] is None


def test_window_distribution_is_in_dollars_on_the_stake():
    index = pd.date_range("2020-01-31", periods=40, freq="BME")
    equity = pd.Series(np.linspace(1000, 1600, len(index)), index=index)
    spy = pd.Series(np.linspace(100, 130, len(index)), index=index)
    stats = window_stats(equity, spy, months=6, stake=1_000)
    assert stats["windows"] > 0
    assert stats["ending_median"] == 1_000 * (1 + stats["median"])
    assert stats["spy_windows"] == stats["windows"]
    bigger = window_stats(equity, spy, months=6, stake=5_000)
    assert bigger["ending_median"] == pytest.approx(stats["ending_median"] * 5)


def test_sources_do_not_touch_the_forward_test():
    for name in ("account_winners.py", "research_account_winners.py"):
        text = (ROOT / "src" / "webull_bot" / name).read_text()
        for banned in ("forward_options", "forward_chop", "option_quote", "place_option_order", "mark_options"):
            assert banned not in text


def test_performance_matches_a_flat_double():
    index = pd.bdate_range("2018-01-02", periods=252)
    equity = pd.Series(np.linspace(1000, 2000, len(index)), index=index)
    stats = performance(equity, 1000)
    assert stats["ending_equity"] == 2000
    assert stats["cagr"] > 0
    assert stats["sharpe"] > 0
    assert stats["max_drawdown"] == 0 or stats["max_drawdown"] > -0.01
    assert isinstance(BookResult.__dataclass_fields__["equity"].name, str)
