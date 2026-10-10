"""Sandbox forward test of QQQ Trapdoor. No network."""

from datetime import date, datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

from webull_bot.cli import build_parser, refuse_if_forward_only
from webull_bot.config import load_config
from webull_bot.execution.forward_trapdoor import (
    BOOK_CAP,
    DISPLAY,
    NAME,
    STAKE,
    plan_day,
    report_text,
    run_cycle,
)
from webull_bot.execution.forward_vwap import NAME as VWAP_NAME, empty_state
from webull_bot.journal.store import Journal
from webull_bot.strategies.registry import strategy_by_name

NY = ZoneInfo("America/New_York")
DAY = "2020-06-15"


class Broker:
    def __init__(self, quote=None):
        self.orders = []
        self.quote = quote
        self.ask = 1.25
        self.bid = 1.10

    def underlying_quote(self, symbol):
        return self.quote

    def option_zero_dte_quote(self, symbol, option_type, spot, as_of):
        return {
            "ask": self.ask,
            "bid": self.bid,
            "strike": 100.0,
            "expiry": DAY,
            "option_symbol": "QQQ200615P00100000",
            "option_type": option_type,
        }

    def option_contract_quote(self, option_symbol):
        return {"ask": self.ask, "bid": self.bid}

    def place_option_order(self, payload):
        self.orders.append(payload)
        return {"client_order_id": payload["client_order_id"]}


def _at(clock: str) -> datetime:
    text = clock if clock.count(":") == 2 else f"{clock}:00"
    return datetime.fromisoformat(f"{DAY}T{text}").replace(tzinfo=NY)


def _qqq() -> pd.DataFrame:
    """The flipped double bottom from the neckline tests. One confirmed short."""
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
    index = pd.date_range(f"{DAY} 09:30", periods=n, freq="5min", tz=NY)
    frame = pd.DataFrame(
        {"open": opened, "high": high, "low": low, "close": closed, "volume": np.full(n, 1000.0)},
        index=index,
    )
    flipped = frame.copy()
    flipped["open"] = 200.0 - frame["open"]
    flipped["close"] = 200.0 - frame["close"]
    flipped["high"] = 200.0 - frame["low"]
    flipped["low"] = 200.0 - frame["high"]
    return flipped


def _cycle(journal, hhmm, broker=None, dry_run=False, bars=None, iv=None):
    points = {date.fromisoformat(DAY): (16.0, "VIX1D")} if iv is None else iv
    return run_cycle(
        journal=journal,
        bars5=_qqq() if bars is None else bars,
        now=_at(hhmm),
        iv_points=points,
        broker=broker,
        dry_run=dry_run,
    )


def test_the_name_stays_off_the_live_book_and_the_cli_accepts_all_three():
    assert NAME == "neckline_trapdoor_qqq"
    assert DISPLAY == "QQQ Trapdoor"
    assert STAKE == 2500.0
    assert BOOK_CAP == 3
    with pytest.raises(KeyError, match="not in the paper or live book"):
        strategy_by_name(NAME)
    with pytest.raises(SystemExit, match="Live trading stays off"):
        refuse_if_forward_only([NAME])
    parser = build_parser()
    args = parser.parse_args(
        ["forward-test", "vwap_band_15m", "vwap_band_15m_qqq", NAME, "--dry-run", "--now", f"{DAY}T14:25:30"]
    )
    assert args.strategy == ["vwap_band_15m", "vwap_band_15m_qqq", NAME]
    report = parser.parse_args(["forward-report", NAME])
    assert report.strategy == NAME


def test_the_first_cycle_buys_one_put_and_a_later_cycle_does_not_resend(tmp_path, monkeypatch):
    monkeypatch.setenv("WEBULL_APP_SECRET", "super-secret-value")
    monkeypatch.setenv("WEBULL_APP_KEY", "super-secret-key")
    journal = Journal(tmp_path / "journal.sqlite")
    broker = Broker()
    lines = _cycle(journal, "14:25:30", broker=broker)
    text = "\n".join(lines)
    assert "super-secret-value" not in text
    assert "super-secret-key" not in text
    assert DISPLAY in text
    assert len(broker.orders) == 1
    order = broker.orders[0]
    assert order["symbol"] == "QQQ"
    assert order["side"] == "BUY"
    assert order["quantity"] == "1"
    assert order["legs"][0]["option_type"] == "PUT"
    assert order["position_intent"] == "BUY_TO_OPEN"
    assert order["order_type"] == "LIMIT"
    saved = journal.forward_load(NAME)
    assert "super-secret-value" not in str(saved)
    position = saved["positions"][0]
    assert position["stop"] == pytest.approx(position["second"] + 0.01)
    risk = position["stop"] - position["modeled_entry"]
    assert risk > 0
    assert position["target"] == pytest.approx(position["modeled_entry"] - risk)
    assert position["target"] < position["entry"] < position["stop"]
    assert saved["signals"][0]["iv_source"] == "VIX1D prior close"
    again = _cycle(journal, "14:25:30", broker=broker)
    assert any("Already journaled" in line for line in again)
    later = _cycle(journal, "14:26:30", broker=broker)
    assert any("already journaled" in line for line in later)
    assert len(broker.orders) == 1


def test_a_price_outside_the_bracket_is_journaled_once(tmp_path):
    journal = Journal(tmp_path / "out.sqlite")
    broker = Broker(quote=200.0)
    lines = _cycle(journal, "14:25:30", broker=broker)
    assert any("no longer between the stop" in line for line in lines)
    assert broker.orders == []
    saved = journal.forward_load(NAME)
    assert saved["signals"][0]["skip"] == "outside"
    again = _cycle(journal, "14:26:30", broker=broker)
    assert any("already journaled" in line for line in again)
    assert broker.orders == []


def test_a_cycle_after_ten_minutes_expires_the_signal(tmp_path):
    journal = Journal(tmp_path / "late.sqlite")
    broker = Broker()
    lines = _cycle(journal, "14:36", broker=broker)
    assert any("expired, late" in line for line in lines)
    assert broker.orders == []
    assert journal.forward_load(NAME)["signals"][0]["skip"] == "expired"


def test_the_book_stops_at_three_and_five_across_books_stops_it_sooner(tmp_path):
    journal = Journal(tmp_path / "cap.sqlite")
    state = {
        "book": NAME,
        "stake": STAKE,
        "settled": STAKE,
        "unsettled": [],
        "stopped": False,
        "signals": [
            {"id": f"seed-{i}", "status": "closed", "entry_time": f"{DAY}T11:0{i}:00"}
            for i in range(3)
        ],
        "orders": [],
        "fills": [],
        "exits": [],
        "positions": [],
        "last_cycle": None,
    }
    journal.forward_save(NAME, state)
    broker = Broker()
    lines = _cycle(journal, "14:25:30", broker=broker)
    assert any("already opened 3 trades today" in line for line in lines)
    assert broker.orders == []

    other = Journal(tmp_path / "combined.sqlite")
    seeded = empty_state()
    seeded["signals"] = [
        {"id": f"vwap-{i}", "status": "open", "entry_time": f"{DAY}T10:1{i}:00"}
        for i in range(5)
    ]
    other.forward_save(VWAP_NAME, seeded)
    lines = _cycle(other, "14:25:30", broker=Broker())
    assert any("already used 5 signals today" in line for line in lines)
    assert other.forward_load(NAME)["signals"][0]["skip"] == "cap"


def test_a_live_quote_through_the_target_sells_and_1545_flattens(tmp_path):
    journal = Journal(tmp_path / "exit.sqlite")
    broker = Broker()
    _cycle(journal, "14:25:30", broker=broker)
    assert len(broker.orders) == 1
    target = journal.forward_load(NAME)["positions"][0]["target"]
    broker.quote = target - 0.50
    lines = _cycle(journal, "14:26:30", broker=broker)
    assert any("reason target" in line for line in lines)
    assert broker.orders[-1]["side"] == "SELL"
    assert broker.orders[-1]["position_intent"] == "SELL_TO_CLOSE"
    assert journal.forward_load(NAME)["positions"] == []

    fresh = Journal(tmp_path / "flat.sqlite")
    held = Broker()
    _cycle(fresh, "14:25:30", broker=held)
    lines = _cycle(fresh, "15:45:30", broker=held)
    assert any("reason flat" in line for line in lines)
    assert held.orders[-1]["side"] == "SELL"


def test_dry_run_replays_the_put_and_does_not_write(tmp_path):
    journal = Journal(tmp_path / "dry.sqlite")
    lines = _cycle(journal, "14:25:30", dry_run=True)
    text = "\n".join(lines)
    assert "Dry run" in text
    assert "QQQ put" in text
    assert "not sent" in text
    assert journal.forward_load(NAME) is None
    events = plan_day(bars5=_qqq(), now=_at("14:25:30"), iv_points={date.fromisoformat(DAY): (16.0, "VIX1D")})
    assert events[0]["status"] == "open"
    assert events[0]["option_type"] == "PUT"
    assert events[0]["modeled_from"] == "next open"
    report = report_text(journal)
    assert "No forward-test journal" in report


def test_cli_dry_run_names_the_trapdoor_and_refuses_a_live_host(monkeypatch):
    import webull_bot.broker.webull as broker_mod
    import webull_bot.data.yfinance_provider as provider_mod
    import webull_bot.journal.store as store_mod

    def boom(*_args, **_kwargs):
        raise AssertionError("dry-run connected")

    monkeypatch.setattr(broker_mod, "WebullBroker", boom)

    class Provider:
        def __init__(self, *_args, **_kwargs):
            pass

        def history(self, symbols, start, end, interval="1d"):
            if interval == "5m":
                return {symbol: _qqq() for symbol in symbols}
            if interval == "15m":
                frame = _qqq().resample("15min").agg(
                    {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
                ).dropna()
                return {symbol: frame for symbol in symbols}
            index = pd.to_datetime(["2020-06-12", "2020-06-15"])
            frame = pd.DataFrame({"close": [16.0, 17.0]}, index=index)
            return {"^VIX": frame, "^VIX1D": frame.copy()}

    monkeypatch.setattr(provider_mod, "YFinanceProvider", Provider)

    class Memory:
        def __init__(self, path):
            self.path = path
            self.saved = {}

        def forward_load(self, name):
            return self.saved.get(name)

        def forward_save(self, name, payload):
            self.saved[name] = payload

    monkeypatch.setattr(store_mod, "Journal", Memory)
    from webull_bot.cli import _forward_vwap

    args = SimpleNamespace(
        strategy=["vwap_band_15m", "vwap_band_15m_qqq", NAME],
        dry_run=True,
        now=f"{DAY}T14:25:30",
        config="config/default.yaml",
    )
    assert _forward_vwap(
        load_config("config/default.yaml"),
        args,
        ["vwap_band_15m", "vwap_band_15m_qqq"],
        [NAME],
    ) == 0
    live = SimpleNamespace(
        strategy=[NAME],
        dry_run=False,
        now=f"{DAY}T14:25:30",
        config="config/default.yaml",
    )
    monkeypatch.delenv("WEBULL_ENV", raising=False)
    with pytest.raises(SystemExit, match="WEBULL_ENV=sandbox"):
        _forward_vwap(load_config("config/default.yaml"), live, [], [NAME])
