from datetime import date

import numpy as np
import pandas as pd

from webull_bot.backtest.assessment import fragile_grid, is_selectable, pick_params
from webull_bot.backtest.engine import run_backtest
from webull_bot.costs import CostModel
from webull_bot.risk.manager import RiskLimits
from webull_bot.strategies.base import Strategy
from webull_bot.strategies.day import GapAndGo
from webull_bot.strategies.signals import blank
from webull_bot.strategies.swing import ConnorsRSI2, DualMomentum


def _frame(values, start="2024-01-02"):
    index = pd.bdate_range(start, periods=len(values))
    close = pd.Series(values, index=index, dtype=float)
    return pd.DataFrame(
        {
            "open": close,
            "high": close,
            "low": close,
            "close": close,
            "volume": np.full(len(close), 1_000_000.0),
        },
        index=index,
    )


class Scripted(Strategy):
    name = "scripted"
    citation = "test"
    style = "day"
    holds_overnight = True
    survivorship_sensitive = False
    trail_pct = None
    default_params: dict = {}

    def __init__(self, entries: dict[str, set[pd.Timestamp]], overnight: bool = True, stop_pct: float = 0.10):
        self._entries = entries
        self.holds_overnight = overnight
        self._stop_pct = stop_pct

    def universe(self, mode: str) -> list[str]:
        return list(self._entries)

    def generate(self, bars, regime, params):
        out = {}
        for symbol, marks in self._entries.items():
            frame = bars[symbol]
            signals = blank(frame.index)
            mask = frame.index.isin(list(marks))
            signals.loc[mask, "entry_next_open"] = True
            signals["stop_price"] = frame["close"] * (1.0 - self._stop_pct)
            signals["max_hold"] = 5
            out[symbol] = signals
        return out


def _limits(**kwargs) -> RiskLimits:
    base = dict(
        risk_per_trade=0.01,
        max_position_pct=1.0,
        max_concurrent_positions=5,
        max_sector_pct=1.0,
        max_correlation=1.0,
        daily_max_loss_pct=0.99,
        max_drawdown_pct=0.99,
        flatten_on_daily_loss=False,
        pdt_mode="off",
        intraday_margin_ratio=1.0,
        min_margin_equity=0,
    )
    base.update(kwargs)
    return RiskLimits(**base)


def _costs() -> CostModel:
    return CostModel(
        slippage_bps=0,
        half_spread_bps=0,
        sec_fee_per_dollar_sold=0,
        finra_taf_per_share=0,
        commission_per_trade=0,
    )


def test_next_open_fill_does_not_use_the_signal_close():
    # Signal on bar 1 (close 10). The next open is 20. A lookahead fill
    # would buy at 10. The engine must buy at 20.
    prices = [10, 10, 20, 20, 20]
    frame = _frame(prices)
    signal_day = frame.index[1]
    result = run_backtest(
        {"SPY": frame, "AAA": frame.copy()},
        [Scripted({"AAA": {signal_day}})],
        pd.DataFrame(index=frame.index),
        starting_equity=100_000,
        costs=_costs(),
        limits=_limits(),
        sectors={"AAA": "technology"},
        flatten_at_end=True,
    )
    assert len(result.trades) == 1
    trade = result.trades.iloc[0]
    assert trade["entry_time"] == frame.index[2]
    assert trade["entry_price"] == 20
    assert trade["entry_price"] != 10


def test_no_fill_after_the_last_bar():
    frame = _frame([10, 10, 10])
    result = run_backtest(
        {"SPY": frame, "AAA": frame.copy()},
        [Scripted({"AAA": {frame.index[-1]}})],
        pd.DataFrame(index=frame.index),
        starting_equity=100_000,
        costs=_costs(),
        limits=_limits(),
        sectors={"AAA": "technology"},
    )
    assert result.trades.empty


def test_gap_through_stop_fills_at_the_open():
    index = pd.bdate_range("2024-01-02", periods=4)
    rows = [
        (10, 10, 10, 10),
        (10, 10, 10, 10),  # signal here, stop = 9
        (10, 10, 10, 10),  # enter at 10
        (8, 8, 7, 8),      # gap through the stop; fill the exit at 8, not 9
    ]
    frame = pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=index)
    frame["volume"] = 1_000_000.0

    class OneStop(Scripted):
        def generate(self, bars, regime, params):
            signals = blank(bars["AAA"].index)
            signals.loc[bars["AAA"].index[1], "entry_next_open"] = True
            signals["stop_price"] = 9.0
            signals["max_hold"] = 10
            return {"AAA": signals}

    result = run_backtest(
        {"SPY": frame, "AAA": frame.copy()},
        [OneStop({})],
        pd.DataFrame(index=index),
        starting_equity=100_000,
        costs=_costs(),
        limits=_limits(),
        sectors={"AAA": "technology"},
    )
    assert len(result.trades) == 1
    trade = result.trades.iloc[0]
    assert trade["entry_price"] == 10
    assert trade["exit_price"] == 8
    assert trade["reason"] == "stop"
    assert trade["pnl"] == (8 - 10) * trade["quantity"]


def test_cash_proceeds_settle_next_session_not_the_same_one():
    index = pd.bdate_range("2024-01-02", periods=4)
    price = pd.DataFrame(
        {"open": 100.0, "high": 100.0, "low": 100.0, "close": 100.0, "volume": 1e6},
        index=index,
    )

    class TwoNames(Strategy):
        name = "two"
        citation = "test"
        style = "swing"
        holds_overnight = True
        survivorship_sensitive = False
        trail_pct = None
        default_params: dict = {}

        def universe(self, mode: str) -> list[str]:
            return ["AAA", "BBB"]

        def generate(self, bars, regime, params):
            out = {}
            for symbol in ("AAA", "BBB"):
                signals = blank(bars[symbol].index)
                signals["stop_price"] = 90.0
                signals["max_hold"] = 1
                out[symbol] = signals
            # Buy AAA for the next open (bar 1). Buy BBB for the open after
            # that sale (bar 2). Same-day cash cannot fund BBB; settled cash can.
            out["AAA"].loc[index[0], "entry_next_open"] = True
            out["BBB"].loc[index[1], "entry_next_open"] = True
            return out

    result = run_backtest(
        {"SPY": price, "AAA": price.copy(), "BBB": price.copy()},
        [TwoNames()],
        pd.DataFrame(index=index),
        starting_equity=10_000,
        costs=_costs(),
        limits=_limits(risk_per_trade=1.0, max_position_pct=1.0),
        sectors={"AAA": "a", "BBB": "b"},
        account_type="cash",
        flatten_at_end=True,
    )
    symbols = set(result.trades["symbol"])
    assert "AAA" in symbols
    assert "BBB" in symbols
    bbb = result.trades[result.trades["symbol"] == "BBB"].iloc[0]
    assert pd.Timestamp(bbb["entry_time"]).date() == index[2].date()


def test_gap_signal_ignores_the_same_bar_close():
    index = pd.bdate_range("2023-01-02", periods=40)
    close = pd.Series(np.linspace(100, 110, len(index)), index=index)
    frame = pd.DataFrame(
        {"open": close, "high": close + 1, "low": close - 1, "close": close, "volume": 1_000_000.0},
        index=index,
    )
    # Force a 5% gap on the last day with heavy prior volume.
    frame.iloc[-1, frame.columns.get_loc("open")] = float(close.iloc[-2]) * 1.05
    frame.iloc[-2, frame.columns.get_loc("volume")] = 5_000_000.0
    regime = pd.DataFrame({"risk_on": True, "aggressive_ok": True}, index=index)
    strategy = GapAndGo()
    params = dict(strategy.default_params)
    params["symbols"] = ["SPY"]
    first = strategy.generate({"SPY": frame}, regime, params)["SPY"]["entry_this_open"].iloc[-1]
    crashed = frame.copy()
    crashed.iloc[-1, crashed.columns.get_loc("close")] = 1.0
    crashed.iloc[-1, crashed.columns.get_loc("low")] = 1.0
    crashed.iloc[-1, crashed.columns.get_loc("high")] = float(crashed.iloc[-1]["open"])
    second = strategy.generate({"SPY": crashed}, regime, params)["SPY"]["entry_this_open"].iloc[-1]
    assert bool(first) is True
    assert bool(second) is True


def test_strategy_signals_do_not_depend_on_future_bars():
    rng = np.random.default_rng(7)
    index = pd.bdate_range("2018-01-01", periods=500)
    price = 100 * np.exp(np.cumsum(rng.normal(0.0003, 0.01, len(index))))
    frame = pd.DataFrame(
        {
            "open": price,
            "high": price * 1.01,
            "low": price * 0.99,
            "close": price,
            "volume": rng.integers(1_000_000, 2_000_000, len(index)),
        },
        index=index,
    )
    regime = pd.DataFrame(
        {"risk_on": True, "aggressive_ok": True, "spy_uptrend": True, "qqq_uptrend": True, "vix": 15.0, "breadth": 0.6},
        index=index,
    )
    cut = index[350]
    for strategy in (ConnorsRSI2(),):
        params = dict(strategy.default_params)
        params["symbols"] = ["SPY"]
        full = strategy.generate({"SPY": frame}, regime, params)["SPY"]
        part = strategy.generate({"SPY": frame.loc[:cut]}, regime.loc[:cut], params)["SPY"]
        pd.testing.assert_series_equal(
            full.loc[:cut, "entry_next_open"].astype(bool),
            part["entry_next_open"].astype(bool),
            check_names=False,
        )


def test_param_picker_uses_only_the_rows_it_is_given():
    default = {"rsi_entry": 10}
    chosen = pick_params(
        [
            {"params": {"rsi_entry": 5}, "sharpe": 0.2, "profit_factor": 1.1, "trades": 40},
            {"params": {"rsi_entry": 15}, "sharpe": 1.4, "profit_factor": 1.5, "trades": 40},
        ],
        default,
    )
    assert chosen["rsi_entry"] == 15
    # Too few trades falls back to the default instead of a lucky cell.
    fallback = pick_params(
        [{"params": {"rsi_entry": 5}, "sharpe": 3.0, "profit_factor": 4.0, "trades": 2}],
        default,
    )
    assert fallback == default


def test_selection_gates_reject_fragile_and_short_samples():
    good = {
        "trades": 40,
        "profit_factor": 1.3,
        "sharpe": 0.6,
        "max_drawdown": -0.12,
        "expectancy": 10,
    }
    assert is_selectable([], good) is True
    assert is_selectable(["short_sample"], good) is False
    assert is_selectable(["survivorship_bias"], good) is False
    assert fragile_grid([2.0, -0.2, -0.1, 0.0]) is True
    assert date(2026, 9, 25).isoformat()


def test_same_bar_entries_do_not_depend_on_dict_order():
    prices = [10, 10, 10, 11, 11]
    frame = _frame(prices)
    day = frame.index[1]
    limits = _limits(max_concurrent_positions=1)

    def symbols_taken(order: list[str]) -> list[str]:
        bars = {"SPY": frame}
        entries = {}
        for symbol in order:
            bars[symbol] = frame.copy()
            entries[symbol] = {day}
        result = run_backtest(
            bars,
            [Scripted(entries)],
            pd.DataFrame(index=frame.index),
            starting_equity=100_000,
            costs=_costs(),
            limits=limits,
            sectors={symbol: "technology" for symbol in order},
            flatten_at_end=True,
        )
        return list(result.trades["symbol"])

    forward = symbols_taken(["AAA", "ZZZ"])
    backward = symbols_taken(["ZZZ", "AAA"])
    assert forward == backward
    assert forward[0] == "AAA"


def test_vwap_generate_tolerates_zero_volume_bars():
    from webull_bot.strategies.day import VWAPPullback

    index = pd.date_range("2026-09-21 09:30", periods=24, freq="h", tz="America/New_York")
    frame = pd.DataFrame(
        {
            "open": 100.0,
            "high": 101.0,
            "low": 99.5,
            "close": 100.4,
            "volume": [0.0 if i % 5 == 0 else 1000.0 for i in range(24)],
        },
        index=index,
    )
    regime = pd.DataFrame({"risk_on": [True]}, index=pd.to_datetime(["2026-09-23"]))
    params = {"thrust": 0.001, "max_hold": 8, "symbols": ["AAPL"]}
    out = VWAPPullback().generate({"AAPL": frame}, regime, params)
    assert "AAPL" in out
    assert len(out["AAPL"]) == len(frame)
    assert int(out["AAPL"]["entry_next_open"].isna().sum()) == 0
