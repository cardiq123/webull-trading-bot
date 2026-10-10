"""Sandbox forward test of the original 4hr cell. No network."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from webull_bot.cli import build_parser, refuse_if_forward_only
from webull_bot.execution.forward_four_hour import (
    BOOK_CAP,
    DISPLAY,
    NAME,
    STAKE,
    _Signal,
    _decide_entry,
    _exit_after,
    expiry_for,
    report_text,
    run_cycle,
    signals_through,
)
from webull_bot.execution.forward_vwap import ENTRY_BOOKS, empty_state, signal_cap_reached
from webull_bot.journal.store import Journal
from webull_bot.strategies.registry import strategy_by_name

NY = ZoneInfo("America/New_York")
DAY = "2020-06-15"
EXPIRY = "2020-06-16"


class Broker:
    def __init__(self, quote=100.4, expiry=EXPIRY):
        self.orders = []
        self.quote = quote
        self.ask = 1.25
        self.bid = 1.10
        self.expiry = expiry

    def underlying_quote(self, symbol):
        return self.quote

    def option_zero_dte_quote(self, symbol, option_type, spot, as_of):
        return {
            "ask": self.ask,
            "bid": self.bid,
            "strike": 100.0,
            "expiry": self.expiry,
            "option_symbol": "QQQ200616C00100000",
            "option_type": option_type,
        }

    def option_contract_quote(self, option_symbol):
        return {"ask": self.ask, "bid": self.bid}

    def place_option_order(self, payload):
        self.orders.append(payload)
        return {"client_order_id": payload["client_order_id"]}


def _at(clock: str, day: str = DAY) -> datetime:
    text = clock if clock.count(":") == 2 else f"{clock}:00"
    return datetime.fromisoformat(f"{day}T{text}").replace(tzinfo=NY)


def _bars(day: str = DAY) -> pd.DataFrame:
    index = pd.date_range(f"{day} 09:30", periods=8, freq="5min", tz=NY)
    return pd.DataFrame(
        {
            "open": [100.0] * len(index),
            "high": [100.2] * len(index),
            "low": [99.8] * len(index),
            "close": [100.0] * len(index),
            "volume": [1000.0] * len(index),
        },
        index=index,
    )


def _signal() -> _Signal:
    return _Signal(
        signal_time=pd.Timestamp(f"{DAY} 10:00", tz=NY),
        fill_time=pd.Timestamp(f"{DAY} 10:05", tz=NY),
        stop=99.0,
        direction="long",
        close=100.0,
    )


def _cycle(journal, hhmm, broker=None, dry_run=False, monkeypatch=None):
    if monkeypatch is not None:
        monkeypatch.setattr(
            "webull_bot.execution.forward_four_hour.signals_through",
            lambda frame, now: [_signal()],
        )
    points = {date.fromisoformat(DAY): (16.0, "VIX1D")}
    return run_cycle(
        journal=journal,
        bars5=_bars(),
        now=_at(hhmm),
        iv_points=points,
        broker=broker,
        dry_run=dry_run,
    )


def test_the_book_stays_off_the_live_path_and_the_commands_accept_it():
    assert NAME == "four_hour_qqq_1dte"
    assert DISPLAY == "4hr"
    assert STAKE == 2500.0
    assert BOOK_CAP == 5
    assert NAME in ENTRY_BOOKS
    assert expiry_for(date(2020, 6, 15)) == date(2020, 6, 16)
    assert expiry_for(date(2026, 10, 9)) == date(2026, 10, 12)
    with pytest.raises(KeyError, match="not in the paper or live book"):
        strategy_by_name(NAME)
    with pytest.raises(SystemExit, match="Live trading stays off"):
        refuse_if_forward_only([NAME])
    parser = build_parser()
    args = parser.parse_args(["forward-test", NAME, "--dry-run", "--now", f"{DAY}T10:05:30"])
    assert args.strategy == [NAME]
    assert parser.parse_args(["forward-report", NAME]).strategy == NAME
    assert parser.parse_args(["forward-reconcile", NAME]).strategy == NAME
    watch = parser.parse_args(["forward-watch", NAME, "--dry-run", "--once", "--now", f"{DAY}T10:05:30"])
    assert watch.strategy == [NAME]
    from pathlib import Path

    text = (Path(__file__).resolve().parents[1] / "scripts" / "vwap-watch.sh").read_text()
    assert NAME in text


def test_the_scanner_uses_the_base_cell_only(monkeypatch):
    captured = {}

    def fake(book, direction_mode, pullback, hold_vwap=False):
        captured["call"] = (direction_mode, pullback, hold_vwap)
        return []

    monkeypatch.setattr("webull_bot.execution.forward_four_hour.find_signals", fake)
    assert signals_through(_bars(), pd.Timestamp(f"{DAY} 10:05:30", tz=NY)) == []
    assert captured["call"] == ("ema", "vwap", False)
    import webull_bot.execution.forward_four_hour as mod

    assert "four_hour_refine" not in mod.__dict__["find_signals"].__module__


def test_the_first_cycle_buys_one_next_session_call(tmp_path, monkeypatch):
    monkeypatch.setenv("WEBULL_APP_SECRET", "super-secret-value")
    monkeypatch.setenv("WEBULL_APP_KEY", "super-secret-key")
    journal = Journal(tmp_path / "journal.sqlite")
    broker = Broker()
    lines = _cycle(journal, "10:05:30", broker=broker, monkeypatch=monkeypatch)
    text = "\n".join(lines)
    assert "super-secret-value" not in text
    assert "super-secret-key" not in text
    assert DISPLAY in text
    assert "chop filter is not applied" in text
    assert len(broker.orders) == 1
    order = broker.orders[0]
    assert order["symbol"] == "QQQ"
    assert order["side"] == "BUY"
    assert order["quantity"] == "1"
    assert order["legs"][0]["option_type"] == "CALL"
    assert order["legs"][0]["option_expire_date"] == EXPIRY
    assert order["position_intent"] == "BUY_TO_OPEN"
    saved = journal.forward_load(NAME)
    assert saved["positions"][0]["qty"] == 1
    assert saved["positions"][0]["expiry"] == EXPIRY
    assert saved["positions"][0]["stop"] == pytest.approx(99.0)
    assert saved["positions"][0]["target"] == pytest.approx(101.0)
    assert saved["signals"][0]["id"].endswith("|long|four_hour")
    again = _cycle(journal, "10:06:30", broker=Broker(), monkeypatch=monkeypatch)
    assert any("already journaled" in line for line in again)
    assert len(broker.orders) == 1


def test_a_same_day_quote_does_not_replace_the_next_session(tmp_path, monkeypatch):
    journal = Journal(tmp_path / "journal.sqlite")
    broker = Broker(expiry=DAY)
    _cycle(journal, "10:05:30", broker=broker, monkeypatch=monkeypatch)
    order = broker.orders[0]
    assert order["legs"][0]["option_expire_date"] == EXPIRY
    saved = journal.forward_load(NAME)
    assert saved["orders"][0]["price_source"] == "model"


def test_price_outside_the_bracket_is_skipped_and_a_late_cycle_expires(tmp_path, monkeypatch):
    journal = Journal(tmp_path / "outside.sqlite")
    broker = Broker(quote=102.0)
    lines = _cycle(journal, "10:05:30", broker=broker, monkeypatch=monkeypatch)
    assert broker.orders == []
    assert any("no longer between" in line for line in lines)
    late = Journal(tmp_path / "late.sqlite")
    late_broker = Broker()
    lines = _cycle(late, "10:20:30", broker=late_broker, monkeypatch=monkeypatch)
    assert late_broker.orders == []
    assert any("expired, late" in line for line in lines)


def test_the_shared_cap_counts_this_signal_as_its_own_slot(tmp_path, monkeypatch):
    journal = Journal(tmp_path / "cap.sqlite")
    day = date.fromisoformat(DAY)
    for book, sid in (
        ("vwap_band_15m", "SPY|a|long|extension"),
        ("vwap_band_15m_qqq", "QQQ|a|long|extension"),
        ("vwap_band_15m_qqq_aggr", "QQQ|b|long|extension"),
        ("vwap_band_15m_qqq_aggr_1dte", "QQQ|c|long|extension"),
        ("neckline_trapdoor_qqq", "QQQ|d|short|trapdoor"),
    ):
        journal.forward_save(
            book,
            {"signals": [{"id": sid, "status": "open", "entry_time": f"{DAY}T10:00:00"}]},
        )
    sid = f"QQQ|{DAY} 10:00|long|four_hour"
    assert signal_cap_reached(journal, day, NAME, empty_state(), sid)
    broker = Broker()
    lines = _cycle(journal, "10:05:30", broker=broker, monkeypatch=monkeypatch)
    assert broker.orders == []
    assert any("already used 5 signals today" in line for line in lines)


def test_dry_run_evaluates_and_does_not_write_or_send(tmp_path, monkeypatch):
    monkeypatch.setenv("WEBULL_APP_SECRET", "super-secret-value")
    journal = Journal(tmp_path / "dry.sqlite")
    broker = Broker()
    lines = _cycle(journal, "10:05:30", broker=broker, dry_run=True)
    text = "\n".join(lines)
    assert "super-secret-value" not in text
    assert "Dry run: orders are not sent and the journal is not written." in text
    assert "No 4hr signal through this cycle." in text
    assert broker.orders == []
    assert journal.forward_load(NAME) is None


def test_a_stop_and_a_target_on_one_bar_exits_at_the_stop():
    index = pd.date_range(f"{DAY} 10:05", periods=2, freq="5min", tz=NY)
    bars = pd.DataFrame(
        {
            "open": [100.0, 100.0],
            "high": [100.1, 101.5],
            "low": [99.9, 98.5],
            "close": [100.0, 100.0],
            "volume": [1.0, 1.0],
        },
        index=index,
    )
    position = {
        "direction": "long",
        "entry_time": f"{DAY}T10:05:30-04:00",
        "fill_time": f"{DAY}T10:05:00-04:00",
        "stop": 99.0,
        "target": 101.0,
        "entry": 100.4,
    }
    reason, _price, _when = _exit_after(position, bars, bars, pd.Timestamp(f"{DAY} 10:15:30", tz=NY), None)
    assert reason == "stop"


def test_the_report_names_the_book(tmp_path):
    journal = Journal(tmp_path / "report.sqlite")
    assert report_text(journal).startswith(f"No forward-test journal for {NAME}")
    built = _decide_entry(
        _signal(),
        _bars(),
        pd.Timestamp(f"{DAY} 10:05:30", tz=NY),
        {date.fromisoformat(DAY): (16.0, "VIX1D")},
        STAKE,
        broker=Broker(),
    )
    assert built["status"] == "open"
    assert built["qty"] == 1
    assert built["expiry"] == EXPIRY
    journal.forward_save(NAME, {"book": NAME, "stake": STAKE, "settled": STAKE, "signals": [built], "orders": [], "fills": [], "exits": [], "positions": [], "unsettled": []})
    text = report_text(journal)
    assert DISPLAY in text
    assert "Cash mirror" in text
    assert "chop filter is not applied" in text
