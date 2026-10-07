"""Offline tests for live/sandbox reconcile. No Webull calls."""

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from webull_bot.backtest.engine import run_backtest
from webull_bot.calendar import is_trading_day, next_trading_day
from webull_bot.costs import CostModel
from webull_bot.execution.live import _cycle
from webull_bot.execution.reconcile import replay_path
from webull_bot.journal.store import Journal
from webull_bot.models import AccountSnapshot, Order, OrderType, Position, Side, TimeInForce
from webull_bot.risk.manager import RiskLimits
from webull_bot.strategies.regime import build_regime
from webull_bot.strategies.signals import blank
from webull_bot.strategies.swing import DualMomentum
from webull_bot.universe import all_sectors

NY = ZoneInfo("America/New_York")


def _trading_index(start: str, end: str) -> pd.DatetimeIndex:
    days = [day for day in pd.bdate_range(start, end) if is_trading_day(day.date())]
    return pd.DatetimeIndex(days)


def _frames_from_close(index: pd.DatetimeIndex, closes: dict[str, np.ndarray]) -> dict[str, pd.DataFrame]:
    frames = {}
    for symbol, close in closes.items():
        open_ = np.empty_like(close)
        open_[0] = close[0]
        open_[1:] = close[:-1]
        high = np.maximum(open_, close) * 1.001
        low = np.minimum(open_, close) * 0.999
        frames[symbol] = pd.DataFrame(
            {"open": open_, "high": high, "low": low, "close": close, "volume": 1_000_000.0},
            index=index,
        )
    return frames


def _dual_momentum_bars() -> dict[str, pd.DataFrame]:
    """Smooth ETF paths with two leadership changes and one gap through the trail."""
    index = _trading_index("2015-01-02", "2020-12-31")
    n = len(index)
    step = np.arange(n)

    def mask(start: str, end: str) -> np.ndarray:
        return np.asarray((index >= start) & (index <= end))

    def path(base: float, extra_ranges: list[tuple[str, str, float]]) -> np.ndarray:
        rate = np.full(n, base)
        for start, end, extra in extra_ranges:
            rate[mask(start, end)] += extra
        close = 100.0 * np.cumprod(1.0 + rate)
        return close

    closes = {
        "SPY": path(0.00025, [("2020-01-02", "2020-12-31", 0.0012)]),
        "QQQ": path(0.0002, []),
        "IWM": path(0.00015, []),
        "EFA": path(0.00012, []),
        "EEM": path(0.0002, [("2017-01-03", "2018-06-29", 0.0014)]),
        "TLT": path(0.00008, []),
        "GLD": path(0.0001, [("2018-07-02", "2019-12-31", 0.0013)]),
        "BIL": path(0.00004, []),
    }
    gap_at = int(np.flatnonzero(index >= "2018-02-01")[5])
    for symbol in closes:
        closes[symbol][gap_at:] *= 0.72
    return _frames_from_close(index, closes)


class _Book:
    def __init__(self, positions=None, orders=None):
        self.positions = list(positions or [])
        self.orders = list(orders or [])
        self.sent = []
        self.cancelled = []
        self.replaced = []
        self.hosts = ["api.sandbox.webull.com", "data-api.sandbox.webull.com"]
        self.environment = "sandbox"
        self.sandbox_only = True

    def snapshot(self):
        return AccountSnapshot(
            equity=100_000,
            cash=100_000,
            buying_power=100_000,
            account_type="margin",
            positions=list(self.positions),
            open_orders=list(self.orders),
        )

    def open_orders(self):
        return list(self.orders)

    def place_order(self, order):
        self.sent.append(order)
        return order

    def cancel_order(self, client_order_id):
        self.cancelled.append(client_order_id)

    def replace_order(self, client_order_id, quantity, limit_price=None, stop_price=None):
        self.replaced.append((client_order_id, quantity, stop_price))


class _ListJournal:
    def __init__(self):
        self.events = []

    def event(self, kind, message, payload):
        self.events.append((kind, message, payload))


def _spy_qqq(periods=8, start="2024-06-03") -> dict[str, pd.DataFrame]:
    index = _trading_index(start, (pd.Timestamp(start) + timedelta(days=periods * 3)).date().isoformat())[:periods]
    close = 100.0 + np.arange(len(index), dtype=float) * 4.0
    return _frames_from_close(index, {"SPY": close, "QQQ": close * 0.9})


class _Rotation:
    name = "dual_momentum"
    custom_universe = False
    holds_overnight = True
    trail_pct = 0.20
    default_params = {}

    def __init__(self, frames):
        self.frames = frames

    def universe(self, kind):
        return ["SPY", "QQQ"]

    def generate(self, bars, regime, params):
        clock = bars["SPY"].index
        spy = blank(clock)
        spy["entry_next_open"] = False
        spy.iloc[0, spy.columns.get_loc("entry_next_open")] = True
        spy["stop_price"] = 80.0
        qqq = blank(clock)
        qqq["stop_price"] = 70.0
        return {"SPY": spy, "QQQ": qqq}


def test_dual_momentum_replay_matches_backtest_holdings():
    bars = _dual_momentum_bars()
    regime = build_regime(bars, ["SPY"])
    strategy = DualMomentum()
    params = dict(strategy.default_params)
    signals = strategy.generate(bars, regime, params)
    log: list = []
    run_backtest(
        bars,
        [strategy],
        regime,
        starting_equity=100_000,
        costs=CostModel(),
        limits=RiskLimits(),
        sectors=all_sectors(),
        account_type="margin",
        params={strategy.name: params},
        trade_start=pd.Timestamp("2017-01-01"),
        flatten_at_end=False,
        position_log=log,
    )
    path = replay_path(
        bars,
        signals,
        strategy=strategy.name,
        trail_pct=strategy.trail_pct,
        holds_overnight=True,
        trade_start=pd.Timestamp("2017-01-01"),
    )
    assert len(path) == len(log)
    mismatches = []
    for (left_ts, left), (right_ts, right) in zip(log, path):
        if pd.Timestamp(left_ts) != pd.Timestamp(right_ts) or set(left) != set(right):
            mismatches.append((pd.Timestamp(left_ts).date(), set(left), set(right)))
            if len(mismatches) >= 8:
                break
    assert mismatches == []
    held_sets = [set(symbols) for _, symbols in log if symbols]
    assert held_sets, "dual momentum never held a target"
    assert len({tuple(sorted(symbols)) for symbols in held_sets}) >= 2


def test_cycle_buys_the_open_target_on_a_day_that_is_not_month_end(capsys):
    bars = _dual_momentum_bars()
    regime = build_regime(bars, ["SPY"])
    strategy = DualMomentum()
    signals = strategy.generate(bars, regime, dict(strategy.default_params))
    log: list = []
    run_backtest(
        bars,
        [strategy],
        regime,
        starting_equity=100_000,
        costs=CostModel(),
        limits=RiskLimits(),
        sectors=all_sectors(),
        account_type="margin",
        trade_start=pd.Timestamp("2017-01-01"),
        flatten_at_end=False,
        position_log=log,
    )
    chosen = None
    for ts, held in log:
        if len(held) != 1:
            continue
        symbol = next(iter(held))
        row = signals[symbol].loc[ts]
        if bool(row["entry_next_open"]) or bool(row["exit_next_open"]):
            continue
        chosen = (pd.Timestamp(ts), symbol)
        break
    assert chosen is not None
    ts, symbol = chosen
    nxt = next_trading_day(ts.date())
    now = datetime.combine(nxt, time(10, 30), tzinfo=NY)
    sliced = {name: frame.loc[:ts] for name, frame in bars.items()}
    broker = _Book()
    journal = _ListJournal()
    _cycle(
        broker,
        type("P", (), {"latest": lambda self, symbols, interval="1d", lookback_days=6000: sliced})(),
        [strategy],
        journal,
        RiskLimits(),
        list(sliced),
        "",
        dry_run=True,
        sandbox=True,
        now=now,
    )
    printed = capsys.readouterr().out
    assert f"would BUY {symbol} qty " in printed
    assert "MARKET DAY + STOP_LOSS GTC @" in printed
    assert "outside rebalance" in printed
    assert broker.sent == []
    assert any(kind == "dry_run" and symbol in message for kind, message, _payload in journal.events)
    # The month-end flag is not on this bar, so the old last-bar check would have been silent.
    assert not bool(signals[symbol].loc[ts, "entry_next_open"])


def test_dry_run_prints_hold_or_buy_and_does_not_send(capsys):
    bars = _spy_qqq()
    broker = _Book(
        positions=[Position(symbol="SPY", quantity=8, avg_price=100)],
        orders=[
            Order(
                client_order_id="stop1",
                symbol="SPY",
                side=Side.SELL,
                quantity=8,
                order_type=OrderType.STOP,
                stop_price=500,
                time_in_force=TimeInForce.GTC,
            )
        ],
    )
    journal = _ListJournal()
    now = datetime.combine(bars["SPY"].index[-1].date() + timedelta(days=5), time(11, 0), tzinfo=NY)
    _cycle(
        broker,
        type("P", (), {"latest": lambda self, symbols, interval="1d", lookback_days=6000: bars})(),
        [_Rotation(bars)],
        journal,
        RiskLimits(),
        ["SPY", "QQQ"],
        "",
        dry_run=True,
        sandbox=True,
        now=now,
    )
    printed = capsys.readouterr().out
    assert "dual_momentum SPY: no signal: dual_momentum target SPY already held" in printed
    assert "dual_momentum QQQ: outside rebalance" in printed
    assert broker.sent == []
    assert broker.cancelled == []
    assert broker.replaced == []
    assert {event[0] for event in journal.events} == {"dry_run"}


def test_rotation_sell_cancels_the_stop_and_sends_a_market_sell(capsys):
    bars = _spy_qqq()

    class Flat(_Rotation):
        def generate(self, bars, regime, params):
            clock = bars["SPY"].index
            spy = blank(clock)
            qqq = blank(clock)
            return {"SPY": spy, "QQQ": qqq}

    stop = Order(
        client_order_id="stop-spy",
        symbol="SPY",
        side=Side.SELL,
        quantity=4,
        order_type=OrderType.STOP,
        stop_price=90,
        time_in_force=TimeInForce.GTC,
    )
    broker = _Book(positions=[Position(symbol="SPY", quantity=4, avg_price=100)], orders=[stop])
    journal = _ListJournal()
    now = datetime.combine(bars["SPY"].index[-1].date() + timedelta(days=5), time(11, 0), tzinfo=NY)
    _cycle(
        broker,
        type("P", (), {"latest": lambda self, symbols, interval="1d", lookback_days=6000: bars})(),
        [Flat(bars)],
        journal,
        RiskLimits(),
        ["SPY", "QQQ"],
        "",
        dry_run=False,
        sandbox=True,
        now=now,
    )
    printed = capsys.readouterr().out
    assert "sent SELL SPY qty 4 MARKET DAY; cancel STOP_LOSS" in printed
    assert broker.cancelled == ["stop-spy"]
    assert len(broker.sent) == 1
    assert broker.sent[0].side == Side.SELL
    assert broker.sent[0].order_type == OrderType.MARKET
    assert broker.sent[0].quantity == 4


def test_trail_replaces_the_stop_and_the_peak_survives_a_restart(tmp_path, capsys):
    bars = _spy_qqq(periods=10)
    broker = _Book(
        positions=[Position(symbol="SPY", quantity=6, avg_price=100)],
        orders=[
            Order(
                client_order_id="stop-spy",
                symbol="SPY",
                side=Side.SELL,
                quantity=6,
                order_type=OrderType.STOP,
                stop_price=70,
                time_in_force=TimeInForce.GTC,
            )
        ],
    )
    journal = Journal(tmp_path / "journal.sqlite")
    now = datetime.combine(bars["SPY"].index[-1].date() + timedelta(days=5), time(11, 0), tzinfo=NY)
    provider = type("P", (), {"latest": lambda self, symbols, interval="1d", lookback_days=6000: bars})()
    _cycle(
        broker,
        provider,
        [_Rotation(bars)],
        journal,
        RiskLimits(),
        ["SPY", "QQQ"],
        "",
        dry_run=False,
        sandbox=True,
        now=now,
    )
    printed = capsys.readouterr().out
    assert "sent replace STOP_LOSS SPY qty 6 GTC @" in printed
    assert broker.replaced
    _client, qty, stop = broker.replaced[-1]
    assert qty == 6
    assert stop > 70
    rows = journal._conn.execute(
        "SELECT strategy, symbol, entry_key, peak, stop FROM peaks"
    ).fetchall()
    assert len(rows) == 1
    strategy, symbol, entry_key, peak, saved_stop = rows[0]
    assert symbol == "SPY"
    assert saved_stop == stop

    restarted = Journal(tmp_path / "journal.sqlite")
    assert restarted.get_peak(strategy, symbol, entry_key) == peak
    # A lower saved peak must not pull the stop down.
    restarted.save_peak(strategy, symbol, entry_key, peak * 0.5, 1.0)
    broker.replaced.clear()
    _cycle(
        broker,
        provider,
        [_Rotation(bars)],
        restarted,
        RiskLimits(),
        ["SPY", "QQQ"],
        "",
        dry_run=True,
        sandbox=True,
        now=now,
    )
    dry = capsys.readouterr().out
    assert f"would replace STOP_LOSS SPY qty 6 GTC @ {stop:.2f}" in dry
    assert broker.replaced == []
    assert restarted.get_peak(strategy, symbol, entry_key) >= peak

    restarted.save_peak(strategy, symbol, entry_key, peak * 1.1, stop)
    _cycle(
        broker,
        provider,
        [_Rotation(bars)],
        restarted,
        RiskLimits(),
        ["SPY", "QQQ"],
        "",
        dry_run=True,
        sandbox=True,
        now=now,
    )
    higher = capsys.readouterr().out
    assert "would replace STOP_LOSS SPY" in higher
    raised = float(higher.split("GTC @ ")[1].splitlines()[0])
    assert raised > stop


def test_forming_bar_through_the_stop_does_not_buy(capsys):
    bars = _spy_qqq()
    last = bars["SPY"].index[-1]
    today = next_trading_day(last.date())
    today_ts = pd.Timestamp(today)
    for symbol, frame in bars.items():
        prior = float(frame["close"].iloc[-1])
        extra = pd.DataFrame(
            {"open": prior, "high": prior * 1.01, "low": prior * 0.5, "close": prior * 0.7, "volume": 1.0},
            index=[today_ts],
        )
        bars[symbol] = pd.concat([frame, extra])
    now = datetime.combine(today, time(11, 0), tzinfo=NY)
    broker = _Book()
    journal = _ListJournal()
    _cycle(
        broker,
        type("P", (), {"latest": lambda self, symbols, interval="1d", lookback_days=6000: bars})(),
        [_Rotation(bars)],
        journal,
        RiskLimits(),
        ["SPY", "QQQ"],
        "",
        dry_run=True,
        sandbox=True,
        now=now,
    )
    printed = capsys.readouterr().out
    assert "stop already through" in printed
    assert "would BUY" not in printed
    assert broker.sent == []
