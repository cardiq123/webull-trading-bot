"""Sandbox forward test for the frozen 60-minute chop-v2 breakout."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from webull_bot.broker.webull import WebullBroker
from webull_bot.chart_reads.chop import EXPAND_VOLUME
from webull_bot.chart_reads.detect import Setup
from webull_bot.chart_reads.research import SYMBOLS
from webull_bot.cli import build_parser, refuse_if_forward_only
from webull_bot.config import load_config
from webull_bot.execution.forward_chop import (
    FRACTIONAL_SHARES,
    MAX_POSITIONS,
    NOTIONAL,
    SLOT,
    completed_hourly,
    empty_state,
    in_forward_window,
    render_report,
    run_cycle,
    trailing_order,
    whole_shares,
)
from webull_bot.execution.live import _cycle
from webull_bot.journal.store import Journal
from webull_bot.models import Order, OrderType, Position, Side, TimeInForce
from webull_bot.strategies.chop_breakout import (
    FLATTEN_EOD,
    MAX_HOLD_SESSIONS,
    TRAIL_PCT,
    ChopBreakout60m,
)
from webull_bot.strategies.registry import all_strategies, forward_strategy, strategy_by_name

NY = ZoneInfo("America/New_York")


class _Broker:
    def __init__(self, fail_trail: bool = False):
        self.orders = []
        self.cancelled = []
        self.fail_trail = fail_trail
        self._positions = []

    def place_order(self, order):
        if self.fail_trail and order.order_type == OrderType.TRAILING:
            raise RuntimeError("trailing not accepted")
        self.orders.append(order)
        if order.side == Side.BUY:
            self._positions = [
                pos for pos in self._positions if pos.symbol != order.symbol
            ]
            self._positions.append(Position(symbol=order.symbol, quantity=order.quantity, avg_price=200.0))
        return order

    def open_orders(self):
        return [order for order in self.orders if order.order_type == OrderType.TRAILING]

    def cancel_order(self, client_order_id):
        self.cancelled.append(client_order_id)

    def positions(self):
        return list(self._positions)


def _frame(specs) -> pd.DataFrame:
    index = [pd.Timestamp(stamp, tz=NY) for stamp, *_rest in specs]
    rows = [(o, h, low, c, 1_000_000.0) for _stamp, o, h, low, c in specs]
    return pd.DataFrame(rows, index=index, columns=["open", "high", "low", "close", "volume"])


def _book(frame: pd.DataFrame) -> dict[str, pd.DataFrame]:
    return {symbol: frame.copy() for symbol in SYMBOLS}


def _at(text: str) -> datetime:
    return datetime.fromisoformat(text).replace(tzinfo=NY)


def _setup(symbol, direction, signal, stop=190.0) -> Setup:
    stamp = pd.Timestamp(signal, tz=NY)
    return Setup(
        symbol=symbol,
        direction=direction,
        kind="chop_v2",
        signal_time=stamp,
        fill_time=stamp + pd.Timedelta(hours=1),
        anchor_time=stamp,
        stop=stop,
        atr=2.0,
        reference=220.0,
    )


def test_frozen_rules_stay_out_of_the_live_book():
    strategy = ChopBreakout60m()
    assert strategy.name == "chop_breakout_60m"
    assert strategy.forward_only is True
    assert strategy.trail_pct == 0.15
    assert TRAIL_PCT == 0.15
    assert MAX_HOLD_SESSIONS == 5
    assert FLATTEN_EOD is False
    assert EXPAND_VOLUME == 1.5
    assert strategy.default_params["expression"] == "stock"
    assert strategy.default_params["exit_style"] == "trail_pct"
    assert strategy.universe("stock") == list(SYMBOLS)
    assert FRACTIONAL_SHARES is False
    assert NOTIONAL == 10_000.0
    assert MAX_POSITIONS == 3
    assert "chop_breakout_60m" not in [item.name for item in all_strategies()]
    assert forward_strategy("chop_breakout_60m").name == "chop_breakout_60m"
    with pytest.raises(KeyError, match="not in the paper or live book"):
        strategy_by_name("chop_breakout_60m")
    optional = open("config/optional_strategies.json", encoding="utf-8").read()
    selected = open("config/selected_strategies.json", encoding="utf-8").read()
    config = open("config/default.yaml", encoding="utf-8").read()
    assert "chop_breakout_60m" not in optional
    assert "chop_breakout_60m" not in selected
    assert "live_trading_enabled: false" in config
    assert "allow_unproven_strategies: false" in config


def test_scan_calls_the_frozen_breakout_without_a_cell(monkeypatch):
    seen = {}

    def fake(frame, *, symbol="", cell=None, feat=None):
        seen["cell"] = cell
        seen["symbol"] = symbol
        return []

    monkeypatch.setattr("webull_bot.strategies.chop_breakout.find_chop_breakouts", fake)
    frame = _frame(
        [
            ("2026-10-06 09:30", 100, 101, 99, 100),
            ("2026-10-06 10:30", 100, 101, 99, 100),
            ("2026-10-06 11:30", 100, 101, 99, 100),
        ]
    )
    ChopBreakout60m().scan(_book(frame))
    assert seen["cell"] is None
    assert seen["symbol"] in SYMBOLS


def test_window_and_whole_shares():
    assert in_forward_window(_at("2026-10-06T10:35:00"))
    assert in_forward_window(_at("2026-10-06T15:35:30"))
    assert in_forward_window(_at("2026-10-06T15:38:00"))
    assert in_forward_window(_at("2026-10-06T15:45:30"))
    assert not in_forward_window(_at("2026-10-06T10:34:00"))
    assert not in_forward_window(_at("2026-10-06T15:46:00"))
    assert not in_forward_window(_at("2026-10-06T09:40:00"))
    assert not in_forward_window(_at("2026-10-10T11:35:00"))
    assert whole_shares(200.0, SLOT) == 16
    assert whole_shares(4000.0, SLOT) == 0
    done = completed_hourly(
        _frame(
            [
                ("2026-10-06 09:30", 100, 101, 99, 100),
                ("2026-10-06 10:30", 102, 103, 101, 102),
            ]
        ),
        _at("2026-10-06T10:35:00"),
    )
    assert list(done.index.strftime("%H:%M")) == ["09:30"]
    # Yahoo's stamp is the bar open. At 10:45 the 09:30 bar has closed
    # (10:30) and the 10:30 bar has not. At 11:35 both of today's bars have.
    today = completed_hourly(
        _frame(
            [
                ("2026-10-07 09:30", 100, 101, 99, 100),
                ("2026-10-07 10:30", 102, 103, 101, 102),
                ("2026-10-07 11:30", 103, 104, 102, 103),
            ]
        ),
        _at("2026-10-07T10:45:00"),
    )
    assert list(today.index.strftime("%H:%M")) == ["09:30"]
    later = completed_hourly(
        _frame(
            [
                ("2026-10-07 09:30", 100, 101, 99, 100),
                ("2026-10-07 10:30", 102, 103, 101, 102),
                ("2026-10-07 11:30", 103, 104, 102, 103),
            ]
        ),
        _at("2026-10-07T11:35:00"),
    )
    assert list(later.index.strftime("%H:%M")) == ["09:30", "10:30"]


def test_dry_run_prints_the_buy_and_the_day_trail_without_sending(tmp_path):
    journal = Journal(tmp_path / "journal.sqlite")
    broker = _Broker()
    frame = _frame(
        [
            ("2026-10-06 09:30", 198, 205, 197, 204),
            ("2026-10-06 10:30", 200, 206, 199, 205),
        ]
    )
    signal = _setup("NVDA", "long", "2026-10-06 09:30")
    lines = run_cycle(
        journal=journal,
        frames=_book(frame),
        now=_at("2026-10-06T10:35:00"),
        broker=broker,
        dry_run=True,
        scan=lambda frames: [signal],
    )
    text = "\n".join(lines)
    assert "Would BUY 16 NVDA MARKET DAY" in text
    assert "TRAILING_STOP_LOSS PERCENTAGE 0.15 DAY" in text
    assert "No broker call." in text
    assert "Shadow SPY buy-and-hold" in text
    assert "Shadow random entry, seed 17" in text
    assert broker.orders == []
    assert journal.forward_load("chop_breakout_60m") is None


def test_a_real_cycle_is_idempotent_and_a_short_is_not_sent(tmp_path):
    journal = Journal(tmp_path / "journal.sqlite")
    broker = _Broker()
    frame = _frame(
        [
            ("2026-10-06 09:30", 198, 205, 197, 204),
            ("2026-10-06 10:30", 200, 206, 199, 205),
        ]
    )
    long_signal = _setup("NVDA", "long", "2026-10-06 09:30")
    short_signal = _setup("AMD", "short", "2026-10-06 09:30", stop=210.0)

    def scan(frames):
        return [long_signal, short_signal]

    first = run_cycle(
        journal=journal,
        frames=_book(frame),
        now=_at("2026-10-06T10:35:00"),
        broker=broker,
        dry_run=False,
        scan=scan,
    )
    assert any("BUY 16 NVDA" in line for line in first)
    assert any("short signal" in line and "skipped" in line for line in first)
    buys = [order for order in broker.orders if order.side == Side.BUY]
    trails = [order for order in broker.orders if order.order_type == OrderType.TRAILING]
    assert len(buys) == 1
    assert len(trails) == 1
    assert trails[0].trail_type == "PERCENTAGE"
    assert trails[0].trail_step == 0.15
    assert trails[0].time_in_force == TimeInForce.DAY
    second = run_cycle(
        journal=journal,
        frames=_book(frame),
        now=_at("2026-10-06T10:40:00"),
        broker=broker,
        dry_run=False,
        scan=scan,
    )
    assert any("already journaled" in line for line in second)
    assert len([order for order in broker.orders if order.side == Side.BUY]) == 1
    assert len([order for order in broker.orders if order.order_type == OrderType.TRAILING]) == 1


def test_time_stop_sells_on_the_fifth_session_and_a_trail_hit_sells(tmp_path):
    journal = Journal(tmp_path / "journal.sqlite")
    broker = _Broker()
    state = empty_state()
    state["positions"] = [
        {
            "id": "NVDA|old|long",
            "symbol": "NVDA",
            "qty": 10,
            "entry": 100.0,
            "opened_on": "2026-09-30",
            "peak": 100.0,
            "trail": "native",
            "entry_bar": "2026-09-30T09:30:00-04:00",
        }
    ]
    journal.forward_save("chop_breakout_60m", state)
    frame = _frame(
        [
            ("2026-10-06 14:30", 100, 101, 99, 100),
            ("2026-10-06 15:30", 100, 101, 99, 100),
        ]
    )
    lines = run_cycle(
        journal=journal,
        frames=_book(frame),
        now=_at("2026-10-06T15:35:00"),
        broker=broker,
        dry_run=False,
        scan=lambda frames: [],
    )
    assert any("reason time_stop" in line for line in lines)
    saved = journal.forward_load("chop_breakout_60m")
    assert saved["positions"] == []
    assert saved["exits"][0]["reason"] == "time_stop"
    sells = [order for order in broker.orders if order.side == Side.SELL and order.order_type == OrderType.MARKET]
    assert len(sells) == 1

    journal = Journal(tmp_path / "trail.sqlite")
    broker = _Broker()
    state = empty_state()
    state["positions"] = [
        {
            "id": "AAPL|today|long",
            "symbol": "AAPL",
            "qty": 8,
            "entry": 100.0,
            "opened_on": "2026-10-06",
            "peak": 100.0,
            "trail": "bot",
            "entry_bar": "2026-10-06T09:30:00-04:00",
        }
    ]
    journal.forward_save("chop_breakout_60m", state)
    frame = _frame(
        [
            ("2026-10-06 09:30", 100, 101, 99, 100),
            ("2026-10-06 10:30", 100, 100, 80, 90),
            ("2026-10-06 11:30", 90, 91, 89, 90),
        ]
    )
    lines = run_cycle(
        journal=journal,
        frames=_book(frame),
        now=_at("2026-10-06T11:35:00"),
        broker=broker,
        dry_run=False,
        scan=lambda frames: [],
    )
    assert any("reason trail" in line for line in lines)
    assert journal.forward_load("chop_breakout_60m")["positions"] == []


def test_rejected_native_trail_is_kept_in_the_journal_and_the_cap_holds(tmp_path):
    journal = Journal(tmp_path / "journal.sqlite")
    broker = _Broker(fail_trail=True)
    frame = _frame(
        [
            ("2026-10-06 09:30", 198, 205, 197, 204),
            ("2026-10-06 10:30", 200, 206, 199, 205),
        ]
    )
    lines = run_cycle(
        journal=journal,
        frames=_book(frame),
        now=_at("2026-10-06T10:35:00"),
        broker=broker,
        dry_run=False,
        scan=lambda frames: [_setup("NVDA", "long", "2026-10-06 09:30")],
    )
    assert any("Bot-managed 15% trail" in line for line in lines)
    saved = journal.forward_load("chop_breakout_60m")
    assert saved["positions"][0]["trail"] == "bot"
    assert not any(order.order_type == OrderType.TRAILING for order in broker.orders)

    state = empty_state()
    state["positions"] = [
        {"id": f"{symbol}|x|long", "symbol": symbol, "qty": 1, "entry": 100.0, "opened_on": "2026-10-06", "peak": 100.0, "trail": "bot", "entry_bar": "2026-10-05T09:30:00-04:00"}
        for symbol in ("AAPL", "AMD", "MSFT")
    ]
    journal.forward_save("chop_breakout_60m", state)
    lines = run_cycle(
        journal=journal,
        frames=_book(frame),
        now=_at("2026-10-06T10:35:00"),
        broker=_Broker(),
        dry_run=False,
        scan=lambda frames: [_setup("NVDA", "long", "2026-10-06 09:30")],
    )
    assert any("Max 3 positions" in line for line in lines)


def test_idle_outside_the_window_and_the_report(tmp_path):
    journal = Journal(tmp_path / "journal.sqlite")
    broker = _Broker()
    frame = _frame([("2026-10-06 09:30", 100, 101, 99, 100), ("2026-10-06 10:30", 100, 101, 99, 100)])
    lines = run_cycle(
        journal=journal,
        frames=_book(frame),
        now=_at("2026-10-06T09:40:00"),
        broker=broker,
        dry_run=False,
        scan=lambda frames: [_setup("NVDA", "long", "2026-10-06 09:30")],
    )
    assert "Outside the 10:35-15:45 ET window" in lines[0]
    assert broker.orders == []
    assert "No forward-test journal" in render_report(empty_state())


def test_live_and_paper_refuse_it_and_the_cycle_does_not_generate():
    with pytest.raises(SystemExit, match="allow_unproven_strategies does not enable it"):
        refuse_if_forward_only(["chop_breakout_60m"])
    with pytest.raises(SystemExit, match="Live trading stays off"):
        refuse_if_forward_only(["dual_momentum", "chop_breakout_60m"])
    refuse_if_forward_only(["dual_momentum"])
    parser = build_parser()
    args = parser.parse_args(["forward-test", "chop_breakout_60m", "--dry-run"])
    assert args.command == "forward-test"
    assert args.dry_run is True
    report = parser.parse_args(["forward-report", "chop_breakout_60m"])
    assert report.command == "forward-report"

    class Strategy:
        name = "chop_breakout_60m"
        forward_only = True
        custom_universe = False
        holds_overnight = True
        default_params = {}

        def universe(self, kind):
            return ["SPY"]

        def generate(self, bars, regime, params):
            raise AssertionError("live path must not generate this book")

    index = pd.bdate_range("2024-01-02", periods=5)
    frame = pd.DataFrame(
        {"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0, "volume": 1_000_000.0},
        index=index,
    )

    class Provider:
        def latest(self, symbols, interval="1d", lookback_days=500):
            return {"SPY": frame}

    class PaperHost:
        def __init__(self):
            self.sent = []

        def snapshot(self):
            from webull_bot.models import AccountSnapshot

            return AccountSnapshot(equity=100_000, cash=100_000, buying_power=100_000, account_type="margin")

        def place_order(self, order):
            self.sent.append(order)

    class Log:
        def __init__(self):
            self.events = []

        def event(self, kind, message, payload):
            self.events.append(message)

    from webull_bot.risk.manager import RiskLimits

    host = PaperHost()
    log = Log()
    _cycle(host, Provider(), [Strategy()], log, RiskLimits(), ["SPY"], "", dry_run=True, sandbox=True)
    assert host.sent == []
    assert any("sandbox forward-test only" in message for message in log.events)


def test_place_order_sends_the_day_trailing_stop(monkeypatch):
    class OrderV3:
        def __init__(self):
            self.placed = []

        def place_order(self, account_id, payload):
            self.placed.append(payload)
            return {"client_order_id": payload[0]["client_order_id"]}

    broker = WebullBroker(app_key="k" * 8, app_secret="s" * 8, account_id="acct")
    broker._trade = SimpleNamespace(order_v3=OrderV3())
    broker.place_order(trailing_order("NVDA", 16))
    payload = broker._trade.order_v3.placed[0][0]
    assert payload["order_type"] == "TRAILING_STOP_LOSS"
    assert payload["trailing_type"] == "PERCENTAGE"
    assert payload["trailing_stop_step"] == "0.15"
    assert payload["time_in_force"] == "DAY"
    assert payload["side"] == "SELL"
    assert payload["quantity"] == "16"
    market = Order(
        client_order_id="b" * 32,
        symbol="NVDA",
        side=Side.BUY,
        quantity=16,
        order_type=OrderType.MARKET,
        time_in_force=TimeInForce.DAY,
    )
    broker.place_order(market)
    body = broker._trade.order_v3.placed[1][0]
    assert body["order_type"] == "MARKET"
    assert "trailing_type" not in body
    from webull_bot.broker.webull import build_single_option_order

    option = build_single_option_order(
        client_order_id="c" * 32,
        symbol="NVDA",
        side="SELL",
        quantity=1,
        strike_price=200,
        option_expire_date="2026-10-27",
        option_type="CALL",
        limit_price=1.0,
        order_type="LIMIT",
        position_intent="SELL_TO_CLOSE",
    )
    broker.place_option_order(option)
    sent = broker._trade.order_v3.placed[2][0]
    assert sent["instrument_type"] == "OPTION"
    assert sent["order_type"] == "LIMIT"
    assert sent["quantity"] == "1"
    assert "trailing_type" not in sent

    monkeypatch.setenv("WEBULL_ENV", "production")
    from webull_bot.cli import _forward_test

    with pytest.raises(SystemExit, match="WEBULL_ENV=sandbox"):
        _forward_test(
            load_config("config/default.yaml"),
            SimpleNamespace(strategy="chop_breakout_60m", dry_run=False, now="2026-10-06T10:35:00", config="config/default.yaml"),
        )


def test_options_use_the_liquid_list_and_shares_stay_on_the_named_list(tmp_path, monkeypatch):
    def fake(frame, *, symbol="", cell=None, feat=None):
        if symbol == "AMZN":
            return [_setup("AMZN", "long", "2026-10-06 10:30")]
        if symbol == "IWM":
            return [_setup("IWM", "long", "2026-10-06 10:30")]
        return []

    def _priced(frame, symbol, direction, now, rv):
        return {
            "right": "call",
            "option_type": "CALL",
            "strike": 200.0,
            "expiry": "2026-10-27",
            "ask": 1.0,
            "debit": 520.0,
            "sigma": 0.25,
            "delta": 0.45,
            "years": 21 / 365,
            "spot": 200.0,
        }

    monkeypatch.setattr("webull_bot.strategies.chop_breakout.find_chop_breakouts", fake)
    monkeypatch.setattr("webull_bot.execution.forward_options._contract", _priced)
    journal = Journal(tmp_path / "journal.sqlite")
    frame = _frame(
        [
            ("2026-10-06 09:30", 198, 205, 197, 204),
            ("2026-10-06 10:30", 200, 206, 199, 205),
            ("2026-10-06 11:30", 201, 207, 200, 206),
        ]
    )
    frames = _book(frame)
    frames["AMZN"] = frame.copy()
    lines = run_cycle(
        journal=journal,
        frames=frames,
        now=_at("2026-10-06T11:35:00"),
        broker=_Broker(),
        dry_run=True,
    )
    text = "\n".join(lines)
    assert any("IWM" in line and "MARKET" in line for line in lines)
    assert "Would BUY 5 AMZN CALL" in text
    assert "Would BUY 5 IWM" not in text
    assert not any("AMZN" in line and "MARKET" in line for line in lines)
    assert "AVGO" in text and "LLY" in text
    assert journal.forward_load("chop_breakout_60m") is None


def test_dry_run_prints_the_option_ladder_and_does_not_send(tmp_path, monkeypatch):
    def _priced(frame, symbol, direction, now, rv):
        return {
            "right": "call" if direction == "long" else "put",
            "option_type": "CALL" if direction == "long" else "PUT",
            "strike": 200.0,
            "expiry": "2026-10-27",
            "ask": 1.0,
            "debit": 520.0,
            "sigma": 0.25,
            "delta": 0.45,
            "years": 21 / 365,
            "spot": 200.0,
        }

    monkeypatch.setattr("webull_bot.execution.forward_options._contract", _priced)
    journal = Journal(tmp_path / "journal.sqlite")
    broker = _Broker()
    frame = _frame(
        [
            ("2026-10-06 09:30", 198, 205, 197, 204),
            ("2026-10-06 10:30", 200, 206, 199, 205),
        ]
    )
    lines = run_cycle(
        journal=journal,
        frames=_book(frame),
        now=_at("2026-10-06T10:35:00"),
        broker=broker,
        dry_run=True,
        scan=lambda frames: [_setup("NVDA", "long", "2026-10-06 09:30"), _setup("AMD", "short", "2026-10-06 09:30", stop=210.0)],
    )
    text = "\n".join(lines)
    assert "Would BUY 5 NVDA CALL strike 200.00 expiry 2026-10-27 LIMIT 1.00 DAY" in text
    assert "Black-Scholes model, no Webull quote" in text
    assert "14 DTE at the money" in text
    assert "Paper notional $25,000" in text
    assert "above $10,000" in text
    assert "Dry run prices the option with the model" in text
    assert "Whole shares, $10,000 notional" in text
    assert "Would place SELL 2 NVDA CALL LIMIT 1.15 DAY" in text
    assert "Would place SELL 1 NVDA CALL LIMIT 1.20 DAY" in text
    assert "Would place SELL 1 NVDA CALL LIMIT 1.30 DAY" in text
    assert "Would place SELL 1 NVDA CALL LIMIT 2.00 DAY" in text
    assert "contracts 1-4 stay at 0.80" in text
    assert "runner stays there until the +15% tier fills" in text
    assert "Would BUY 5 AMD PUT" in text
    assert "short signal" in text and "skipped" in text
    assert "No broker call." in text
    assert broker.orders == []
    assert journal.forward_load("chop_breakout_60m") is None
    live = Path("src/webull_bot/execution/live.py").read_text()
    assert "place_option_order" not in live
    assert "mark_options" not in live


class _OptionBroker(_Broker):
    def __init__(self):
        super().__init__()
        self.option_orders = []

    def place_option_order(self, payload):
        self.option_orders.append(dict(payload))
        return payload


def test_option_stop_sells_only_the_runner_and_does_not_repeat(tmp_path, monkeypatch):
    """After +15%, a break-even touch sells the runner only, once."""

    def _priced(frame, symbol, direction, now, rv):
        return {
            "right": "call",
            "option_type": "CALL",
            "strike": 200.0,
            "expiry": "2026-10-27",
            "ask": 1.0,
            "debit": 520.0,
            "sigma": 0.25,
            "delta": 0.45,
            "years": 21 / 365,
            "spot": 200.0,
        }

    def _bids(position, row, entry_bar):
        hour = pd.Timestamp(row.name).tz_convert(NY).hour
        if hour <= 9:
            favorable, adverse = 1.05, 0.90
        elif hour == 10:
            favorable, adverse = 1.16, 0.90
        else:
            favorable, adverse = 1.10, 0.97
        return {
            "open_bid": 1.0,
            "adverse_bid": adverse,
            "favorable_bid": favorable,
            "close_bid": 1.0,
            "underlying_hit": False,
            "underlying_bid": 0.0,
            "entry_bar": entry_bar,
        }

    monkeypatch.setattr("webull_bot.execution.forward_options._contract", _priced)
    monkeypatch.setattr("webull_bot.execution.forward_options._quotes", _bids)
    journal = Journal(tmp_path / "journal.sqlite")
    broker = _OptionBroker()
    frame = _frame(
        [
            ("2026-10-06 09:30", 198, 205, 197, 204),
            ("2026-10-06 10:30", 200, 206, 199, 205),
            ("2026-10-06 11:30", 200, 202, 199, 201),
            ("2026-10-06 12:30", 200, 201, 199, 200),
        ]
    )
    signal = _setup("NVDA", "long", "2026-10-06 09:30")

    def cycle(stamp: str):
        return run_cycle(
            journal=journal,
            frames=_book(frame),
            now=_at(stamp),
            broker=broker,
            dry_run=False,
            scan=lambda frames: [signal],
        )

    first = cycle("2026-10-06T10:35:00")
    assert any("BUY 5 NVDA CALL" in line for line in first)
    assert len(broker.option_orders) == 5
    buys = [row for row in broker.option_orders if row["side"] == "BUY"]
    assert len(buys) == 1
    assert buys[0]["quantity"] == "5"
    limits = [row for row in broker.option_orders if row["side"] == "SELL"]
    assert [row["quantity"] for row in limits] == ["2", "1", "1", "1"]
    assert [row["limit_price"] for row in limits] == ["1.15", "1.20", "1.30", "2.00"]
    share_ids = {order.client_order_id for order in broker.orders}

    again = cycle("2026-10-06T10:40:00")
    assert any("already journaled" in line for line in again)
    assert len(broker.option_orders) == 5

    cycle("2026-10-06T11:35:00")
    assert len([row for row in broker.option_orders if row["side"] == "SELL"]) == 4
    stopped = cycle("2026-10-06T12:35:00")
    text = "\n".join(stopped)
    assert "SELL 1 NVDA CALL" in text
    assert "bot stop breakeven" in text
    assert "Only contracts still open" in text
    stops = [
        row
        for row in broker.option_orders
        if row["side"] == "SELL" and row["position_intent"] == "SELL_TO_CLOSE" and float(row["limit_price"]) < 1.1
    ]
    assert len(stops) == 1
    assert stops[0]["quantity"] == "1"
    runner_ids = {row["client_order_id"] for row in limits if row["limit_price"] == "2.00"}
    kept_ids = {row["client_order_id"] for row in limits if row["limit_price"] in {"1.20", "1.30"}}
    assert runner_ids <= set(broker.cancelled)
    assert kept_ids.isdisjoint(broker.cancelled)
    assert share_ids.isdisjoint(broker.cancelled)
    before = len(broker.option_orders)
    cycle("2026-10-06T12:40:00")
    assert len(broker.option_orders) == before
    saved = journal.forward_load("chop_breakout_60m")
    position = saved["option_positions"][0]
    assert position["scale"]["remaining"] == 2
    assert position["scale"]["runner"] == "breakeven"
    assert position["scale"]["sold"]["0.15"] == 2


def test_model_contract_is_14_dte_at_the_nearest_strike():
    from webull_bot.execution.forward_options import _contract

    now = _at("2026-10-06T10:35:00")
    frame = _frame(
        [
            ("2026-10-06 09:30", 200.2, 201.0, 199.5, 200.4),
            ("2026-10-06 10:30", 200.6, 202.0, 200.0, 201.0),
        ]
    )
    rv = pd.Series([0.25], index=pd.to_datetime(["2026-10-06"]))
    contract = _contract(frame, "NVDA", "long", now, {"NVDA": rv})
    assert contract["price_source"] == "model"
    assert contract["expiry"] == "2026-10-20"
    assert contract["strike"] == 201.0
    assert contract["option_type"] == "CALL"
    assert 0.35 < contract["delta"] < 0.65


def test_quote_chain_picks_the_expiry_closest_to_14_dte():
    from webull_bot.execution.option_quote import pick_atm

    rows = [
        {"option_symbol": "NVDA261016C00200000", "option_type": "CALL", "strike_price": "200", "expiration_date": "2026-10-16"},
        {"option_symbol": "NVDA261020C00199000", "option_type": "CALL", "strike_price": "199", "expiration_date": "2026-10-20"},
        {"option_symbol": "NVDA261020C00205000", "option_type": "CALL", "strike_price": "205", "expiration_date": "2026-10-20"},
        {"option_symbol": "NVDA261020P00199000", "option_type": "PUT", "strike_price": "199", "expiration_date": "2026-10-20"},
        {"option_symbol": "NVDA261023C00201000", "option_type": "CALL", "strike_price": "201", "expiration_date": "2026-10-23"},
    ]
    chosen = pick_atm(rows, spot=200.0, target=date(2026, 10, 20), option_type="CALL")
    assert chosen["option_symbol"] == "NVDA261020C00199000"
    assert chosen["strike"] == 199.0
    assert chosen["expiry"] == "2026-10-20"


def test_broker_quote_uses_the_snapshot_ask():
    class Data:
        def __init__(self):
            self.instrument = self
            self.option_market_data = self
            self.seen = []

        def list_option_contracts(self, **kwargs):
            self.seen.append(kwargs)
            if "start_date" in kwargs:
                return {"result": []}
            return {
                "result": [
                    {
                        "option_symbol": "NVDA261020C00199000",
                        "option_type": "CALL",
                        "strike_price": "199",
                        "expiration_date": "2026-10-20",
                    },
                    {
                        "option_symbol": "NVDA261020C00205000",
                        "option_type": "CALL",
                        "strike_price": "205",
                        "expiration_date": "2026-10-20",
                    },
                ]
            }

        def get_option_snapshot(self, symbols, category):
            assert symbols == "NVDA261020C00199000"
            assert category == "US_OPTION"
            return {"result": [{"ask": "3.40", "delta": "0.49"}]}

    broker = WebullBroker(app_key="k", app_secret="s", environment="sandbox")
    broker._data = Data()
    quote = broker.option_atm_quote("NVDA", "CALL", 200.0, date(2026, 10, 6))
    assert quote["expiry"] == "2026-10-20"
    assert quote["strike"] == 199.0
    assert quote["ask"] == 3.40
    assert quote["delta"] == 0.49
    assert broker._data.seen[0]["start_date"] == "2026-10-10"
    assert "start_date" not in broker._data.seen[1]


def test_sandbox_quote_is_journaled_and_a_missing_quote_uses_the_model(tmp_path, monkeypatch):
    def _priced(frame, symbol, direction, now, rv):
        return {
            "right": "call",
            "option_type": "CALL",
            "strike": 200.0,
            "expiry": "2026-10-20",
            "ask": 1.0,
            "debit": 520.0,
            "sigma": 0.25,
            "delta": 0.50,
            "years": 14 / 365,
            "spot": 200.0,
            "price_source": "model",
        }

    monkeypatch.setattr("webull_bot.execution.forward_options._contract", _priced)
    frame = _frame(
        [
            ("2026-10-06 09:30", 198, 205, 197, 204),
            ("2026-10-06 10:30", 200, 206, 199, 205),
        ]
    )
    signal = _setup("NVDA", "long", "2026-10-06 09:30")

    class Quoted(_OptionBroker):
        def option_atm_quote(self, symbol, option_type, spot, as_of):
            return {
                "ask": 2.5,
                "strike": 201.0,
                "expiry": "2026-10-20",
                "delta": 0.51,
                "option_symbol": "NVDA261020C00201000",
            }

    journal = Journal(tmp_path / "quote.sqlite")
    quoted = "\n".join(
        run_cycle(
            journal=journal,
            frames=_book(frame),
            now=_at("2026-10-06T10:35:00"),
            broker=Quoted(),
            dry_run=False,
            scan=lambda frames: [signal],
        )
    )
    assert "BUY 5 NVDA CALL strike 201.00 expiry 2026-10-20 LIMIT 2.50 DAY" in quoted
    assert "Webull sandbox quote" in quoted
    saved = journal.forward_load("chop_breakout_60m")
    assert saved["option_signals"][0]["price_source"] == "webull"
    assert saved["option_orders"][0]["price_source"] == "webull"
    assert saved["option_orders"][0]["limit"] == "2.50"

    class Empty(_OptionBroker):
        def option_atm_quote(self, symbol, option_type, spot, as_of):
            raise RuntimeError("snapshot unavailable")

    fallback = Journal(tmp_path / "model.sqlite")
    text = "\n".join(
        run_cycle(
            journal=fallback,
            frames=_book(frame),
            now=_at("2026-10-06T10:35:00"),
            broker=Empty(),
            dry_run=False,
            scan=lambda frames: [signal],
        )
    )
    assert "Black-Scholes model, no Webull quote" in text
    assert "LIMIT 1.00 DAY" in text
    assert fallback.forward_load("chop_breakout_60m")["option_signals"][0]["price_source"] == "model"


def test_five_lot_above_10000_is_skipped(tmp_path, monkeypatch):
    def _priced(frame, symbol, direction, now, rv):
        return {
            "right": "call",
            "option_type": "CALL",
            "strike": 200.0,
            "expiry": "2026-10-20",
            "ask": 20.1,
            "debit": 10001.0,
            "sigma": 0.25,
            "delta": 0.50,
            "years": 14 / 365,
            "spot": 200.0,
            "price_source": "model",
        }

    monkeypatch.setattr("webull_bot.execution.forward_options._contract", _priced)
    journal = Journal(tmp_path / "journal.sqlite")
    frame = _frame(
        [
            ("2026-10-06 09:30", 198, 205, 197, 204),
            ("2026-10-06 10:30", 200, 206, 199, 205),
        ]
    )
    lines = run_cycle(
        journal=journal,
        frames=_book(frame),
        now=_at("2026-10-06T10:35:00"),
        broker=_Broker(),
        dry_run=True,
        scan=lambda frames: [_setup("NVDA", "long", "2026-10-06 09:30")],
    )
    text = "\n".join(lines)
    assert "above the $10,000 cap" in text
    assert "$25,000 paper book" in text
    assert "Would BUY 5 NVDA" not in text
    assert journal.forward_load("chop_breakout_60m") is None


def test_cli_idle_returns_before_any_broker_or_download(monkeypatch, capsys):
    """Outside 10:35-15:45 ET the command does not connect, even if WEBULL_ENV is production."""
    from webull_bot.cli import _forward_test

    def _boom(*args, **kwargs):
        raise AssertionError("forward-test left the window check")

    monkeypatch.setenv("WEBULL_ENV", "production")
    monkeypatch.setattr("webull_bot.data.yfinance_provider.YFinanceProvider", _boom)
    monkeypatch.setattr("webull_bot.broker.webull.WebullBroker", _boom)
    code = _forward_test(
        load_config("config/default.yaml"),
        SimpleNamespace(strategy="chop_breakout_60m", dry_run=False, now="2026-10-06T09:40:00", config="config/default.yaml"),
    )
    assert code == 0
    captured = capsys.readouterr().out
    assert "Outside the 10:35-15:45 ET window" in captured
    assert "No orders" in captured
