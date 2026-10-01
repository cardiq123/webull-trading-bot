"""Paper broker replay: stops, session flat, daily loss, and no short orders."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from webull_bot.backtest.engine import run_backtest
from webull_bot.backtest.metrics import compute_metrics
from webull_bot.broker.paper import PaperBroker
from webull_bot.broker.webull import new_client_order_id
from webull_bot.costs import CostModel, buy_fees, buy_price, sell_price, sell_regulatory_fees
from webull_bot.execution.session import run_replay
from webull_bot.execution.signal_replay import replay_signals
from webull_bot.fanatics.simulate import Signal
from webull_bot.journal.store import Journal
from webull_bot.models import Order, OrderType, Side, TimeInForce
from webull_bot.risk.manager import RiskLimits
from webull_bot.strategies.base import Strategy
from webull_bot.strategies.signals import blank


class _Scripted(Strategy):
    name = "scripted"
    citation = "test"
    style = "swing"
    holds_overnight = True
    survivorship_sensitive = False
    trail_pct = None
    default_params = {}

    def universe(self, mode: str) -> list[str]:
        return ["SPY"]

    def generate(self, bars, regime, params):
        frame = bars["SPY"]
        signals = blank(frame.index)
        if len(frame) > 30:
            signals.iloc[30, signals.columns.get_loc("entry_next_open")] = True
            signals.iloc[30, signals.columns.get_loc("stop_price")] = 99.0
        if len(frame) > 34:
            signals.iloc[34, signals.columns.get_loc("exit_next_open")] = True
        return {"SPY": signals}


def _daily(prices: list[float]) -> dict[str, pd.DataFrame]:
    index = pd.bdate_range("2024-01-02", periods=len(prices))
    rows = []
    for price in prices:
        rows.append({"open": price, "high": price, "low": price, "close": price, "volume": 1_000_000})
    frame = pd.DataFrame(rows, index=index)
    return {"SPY": frame}


def _limits() -> RiskLimits:
    return RiskLimits(
        risk_per_trade=0.0075,
        max_position_pct=0.20,
        max_concurrent_positions=5,
        max_sector_pct=0.35,
        daily_max_loss_pct=0.02,
        max_drawdown_pct=0.15,
        flatten_on_daily_loss=True,
        allow_fractional=False,
    )


def _run_both(bars, strategy, start, limits, costs, equity=100_000.0):
    regime = pd.DataFrame(index=bars["SPY"].index)
    result = run_backtest(
        bars,
        [strategy],
        regime,
        starting_equity=equity,
        costs=costs,
        limits=limits,
        sectors={"SPY": "broad"},
        account_type="margin",
        params={strategy.name: {"symbols": ["SPY"]}},
        trade_start=pd.Timestamp(start),
        flatten_at_end=True,
    )
    metrics = compute_metrics(result, equity)
    tmp = Path(bars["SPY"].index[0].strftime("/tmp/paper-replay-%Y%m%d"))
    # Unique directory per call so tests do not share a ledger.
    import tempfile

    folder = Path(tempfile.mkdtemp())
    broker = PaperBroker(folder / "paper.sqlite", costs, starting_equity=equity, account_type="margin")
    broker.connect()
    summary = run_replay(
        bars,
        [strategy],
        regime,
        broker,
        Journal(folder / "journal.sqlite"),
        cycles=1,
        limits=limits,
        params={strategy.name: {"symbols": ["SPY"]}},
        start=start,
        quiet=True,
        flatten_at_end=True,
        include_prior_open=False,
    )
    del tmp
    return metrics, summary


def test_paper_replay_matches_backtest_on_one_round_trip():
    prices = [100.0] * 31 + [100.0, 102.0, 104.0, 106.0, 108.0, 110.0] + [110.0] * 8
    bars = _daily(prices)
    start = bars["SPY"].index[30]
    metrics, summary = _run_both(bars, _Scripted(), start, _limits(), CostModel())
    assert metrics["trades"] == 1
    assert summary["closed_trades"] == 1
    assert abs(metrics["ending_equity"] - summary["ending_equity"]) < 0.05


def test_day_trade_flattens_on_the_last_bar_of_the_session():
    class DayTrade(_Scripted):
        name = "day_scripted"
        holds_overnight = False

        def generate(self, bars, regime, params):
            frame = bars["SPY"]
            signals = blank(frame.index)
            # Signal on the first bar of the second session. Fill is the next hour.
            signals.iloc[6, signals.columns.get_loc("entry_next_open")] = True
            signals.iloc[6, signals.columns.get_loc("stop_price")] = 90.0
            return {"SPY": signals}

    index = []
    stamp = pd.Timestamp("2024-06-03 09:30", tz="America/New_York")
    for _day in range(4):
        for hour in range(6):
            index.append(stamp + pd.Timedelta(hours=hour))
        stamp += pd.Timedelta(days=1)
    rows = []
    for i, ts in enumerate(index):
        price = 110.0 if ts.hour == 14 else 100.0
        rows.append({"open": 100.0, "high": price, "low": 99.0, "close": price, "volume": 1_000_000, "ts": ts})
    frame = pd.DataFrame(rows).set_index("ts")
    bars = {"SPY": frame}
    start = index[6]
    _metrics, summary = _run_both(bars, DayTrade(), start, _limits(), CostModel())
    assert summary["closed_trades"] == 1
    assert summary["positions"] == []
    # Exit at the 14:30 close (110), not at the fill bar's close (100).
    assert summary["pnl"] > 100


def test_stop_fills_before_target_on_the_same_bar():
    import tempfile

    folder = Path(tempfile.mkdtemp())
    broker = PaperBroker(folder / "paper.sqlite", CostModel(slippage_bps=0, half_spread_bps=0, sec_fee_per_dollar_sold=0, finra_taf_per_share=0))
    broker.connect()
    broker.place_order(
        Order(
            client_order_id=new_client_order_id(),
            symbol="SPY",
            side=Side.BUY,
            quantity=10,
            order_type=OrderType.MARKET,
            stop_price=95,
            strategy="test",
        )
    )
    broker.place_order(
        Order(
            client_order_id=new_client_order_id(),
            symbol="SPY",
            side=Side.SELL,
            quantity=10,
            order_type=OrderType.LIMIT,
            limit_price=110,
            strategy="test",
        )
    )
    fills = broker.process_bar("SPY", 100, 120, 90, 100)
    reasons = [fill.reason for fill in fills if fill.side == Side.SELL]
    assert reasons == ["stop"]
    assert broker.positions() == []


def test_daily_loss_flatten_fires():
    class Wide(_Scripted):
        def generate(self, bars, regime, params):
            frame = bars["SPY"]
            signals = blank(frame.index)
            signals.iloc[30, signals.columns.get_loc("entry_next_open")] = True
            signals.iloc[30, signals.columns.get_loc("stop_price")] = 50.0
            return {"SPY": signals}

    prices = [100.0] * 45
    bars = _daily(prices)
    # The bar after the fill drops 20 points without trading through the stop.
    bars["SPY"].iloc[32, :] = [100.0, 100.0, 70.0, 70.0, 1_000_000]
    start = bars["SPY"].index[30]
    limits = _limits()
    limits.risk_per_trade = 0.05
    limits.max_position_pct = 1.0
    _metrics, summary = _run_both(bars, Wide(), start, limits, CostModel())
    kinds = {item["kind"] for item in summary["risk_triggers"]}
    assert "daily_loss" in kinds
    assert summary["positions"] == []


def test_leverage_one_round_trip_matches_full_notional():
    import tempfile

    costs = CostModel()
    folder = Path(tempfile.mkdtemp())
    broker = PaperBroker(folder / "paper.sqlite", costs, starting_equity=100_000)
    broker.connect()
    order = Order(
        client_order_id=new_client_order_id(),
        symbol="SPY",
        side=Side.BUY,
        quantity=10,
        order_type=OrderType.MARKET,
        stop_price=90,
        strategy="test",
    )
    broker.fill_order_at(order, 100)
    broker.fill_exit("SPY", 100, "signal")
    buy = buy_price(100, costs)
    sell = sell_price(100, costs)
    fees = sell_regulatory_fees(sell, 10, costs) + buy_fees(costs)
    expected = 100_000 + (sell - buy) * 10 - fees
    assert abs(broker.snapshot().cash - expected) < 0.01


def test_resting_target_does_not_consume_a_position_slot():
    """A GTC profit limit is an exit, not a second position.

    With the cap at 3, two open trades plus their resting targets must still
    leave room for a third entry. Counting each target as a position rejected it.
    """

    class Three(_Scripted):
        name = "three_names"

        def generate(self, bars, regime, params):
            out = {}
            for symbol in ("AAA", "BBB", "CCC"):
                frame = bars[symbol]
                signals = blank(frame.index)
                slot = 10 if symbol != "CCC" else 11
                if len(frame) > slot:
                    signals.iloc[slot, signals.columns.get_loc("entry_next_open")] = True
                    signals.iloc[slot, signals.columns.get_loc("stop_price")] = 90.0
                    signals.iloc[slot, signals.columns.get_loc("take_profit")] = 500.0
                out[symbol] = signals
            return out

    index = pd.bdate_range("2024-01-02", periods=20)
    frame = pd.DataFrame(
        {"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0, "volume": 1_000_000},
        index=index,
    )
    bars = {"SPY": frame.copy(), "AAA": frame.copy(), "BBB": frame.copy(), "CCC": frame.copy()}
    limits = _limits()
    limits.max_concurrent_positions = 3
    _metrics, summary = _run_both(
        bars,
        Three(),
        index[10],
        limits,
        CostModel(slippage_bps=0, half_spread_bps=0, sec_fee_per_dollar_sold=0, finra_taf_per_share=0),
    )
    assert summary["orders"] == 3
    assert summary["closed_trades"] == 3
    assert "max concurrent positions reached" not in summary["rejected"]


def test_signal_exit_frees_the_sector_before_the_next_entry():
    """A next-open exit fills before a new entry is sized.

    QQQ and SPY are both broad. Each order is capped at 20%, so the two
    together exceed the 35% sector cap. Exiting QQQ at the open has to
    happen before SPY is sized, or SPY is rejected and the backtest is not.
    """

    class Rotate(_Scripted):
        name = "rotate"
        holds_overnight = True

        def generate(self, bars, regime, params):
            out = {}
            for symbol, frame in bars.items():
                if symbol not in {"QQQ", "SPY"}:
                    continue
                signals = blank(frame.index)
                if symbol == "QQQ" and len(frame) > 30:
                    signals.iloc[30, signals.columns.get_loc("entry_next_open")] = True
                    signals.iloc[30, signals.columns.get_loc("stop_price")] = 99.0
                if symbol == "QQQ" and len(frame) > 32:
                    signals.iloc[32, signals.columns.get_loc("exit_next_open")] = True
                if symbol == "SPY" and len(frame) > 32:
                    signals.iloc[32, signals.columns.get_loc("entry_next_open")] = True
                    signals.iloc[32, signals.columns.get_loc("stop_price")] = 99.0
                out[symbol] = signals
            return out

    index = pd.bdate_range("2024-01-02", periods=40)
    frame = pd.DataFrame(
        {"open": 100.0, "high": 101.0, "low": 99.5, "close": 100.0, "volume": 1_000_000},
        index=index,
    )
    bars = {"SPY": frame.copy(), "QQQ": frame.copy()}
    limits = _limits()
    costs = CostModel(slippage_bps=0, half_spread_bps=0, sec_fee_per_dollar_sold=0, finra_taf_per_share=0)
    metrics, summary = _run_both(bars, Rotate(), index[30], limits, costs)
    assert metrics["trades"] == 2
    assert summary["closed_trades"] == 2
    assert summary["orders"] == 2
    assert "sector broad would exceed 35%" not in summary["rejected"]
    assert abs(metrics["ending_equity"] - summary["ending_equity"]) < 0.05


def test_stop_through_the_raw_open_is_not_filled():
    """A stop between the open and the slipped buy is invalid, matching the engine."""

    class Through(_Scripted):
        def generate(self, bars, regime, params):
            frame = bars["SPY"]
            signals = blank(frame.index)
            if len(frame) > 30:
                signals.iloc[30, signals.columns.get_loc("entry_next_open")] = True
                # Open is 100. Default slippage lifts the buy to 100.06.
                signals.iloc[30, signals.columns.get_loc("stop_price")] = 100.05
            return {"SPY": signals}

    prices = [100.0] * 40
    bars = _daily(prices)
    start = bars["SPY"].index[30]
    metrics, summary = _run_both(bars, Through(), start, _limits(), CostModel())
    assert metrics["trades"] == 0
    assert summary["closed_trades"] == 0
    assert summary["orders"] == 0
    assert summary["rejected"].get("invalid stop", 0) == 1


def test_signal_replay_does_not_send_shorts_and_waits_for_the_next_bar():
    import tempfile

    index = pd.date_range("2026-09-01 09:30", periods=6, freq="5min", tz="America/New_York")
    frame = pd.DataFrame(
        {"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5, "volume": 10},
        index=index,
    )
    # A long signaled on bar 1 fills on bar 2. A short on bar 1 is not sent.
    signals = [
        Signal("NQ=F", 1, 1, 98.0, 110.0, 5),
        Signal("NQ=F", -1, 1, 102.0, 90.0, 5),
    ]
    folder = Path(tempfile.mkdtemp())
    costs = CostModel(slippage_bps=0, half_spread_bps=0, sec_fee_per_dollar_sold=0, finra_taf_per_share=0)
    broker = PaperBroker(folder / "paper.sqlite", costs, starting_equity=100_000, leverage=20)
    broker.connect()
    summary = replay_signals(
        {"NQ=F": frame},
        signals,
        broker,
        Journal(folder / "journal.sqlite"),
        _limits(),
        strategy="fanatics_test",
        risk=0.005,
        trade_start=index[0].date(),
    )
    assert summary["shorts_not_sent"] == 1
    assert summary["orders"] == 1
    assert summary["closed_trades"] == 1
    assert broker.positions() == []
