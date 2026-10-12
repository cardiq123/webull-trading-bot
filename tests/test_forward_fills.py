"""An unfilled buy is not a position. Sandbox only. No network."""

from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from webull_bot.execution.forward_fills import sync_working_entries
from webull_bot.execution.forward_reconcile import chase_exit_orders, reconcile_book
from webull_bot.execution.forward_vwap import (
    NAME,
    QQQ_COMPOUND_NAME,
    _ACTIVE,
    _activate,
    _buy_limit,
    _manage_open,
    empty_state,
)
from webull_bot.journal.store import Journal

NY = ZoneInfo("America/New_York")
DAY = "2026-10-12"


def _at(hhmm: str) -> datetime:
    hour, minute = hhmm.split(":")
    return datetime(2026, 10, 12, int(hour), int(minute), tzinfo=NY)


class _Detail:
    def __init__(self, payloads):
        self.payloads = payloads

    def get_order_detail(self, account_id, client_order_id):
        payload = self.payloads[client_order_id]
        if isinstance(payload, Exception):
            raise payload
        return payload


class _Account:
    def get_account_position(self, account_id):
        return {"positions": []}


class _Broker:
    def __init__(self, payloads):
        self._trade = SimpleNamespace(order_v3=_Detail(payloads), account_v2=_Account())
        self.account_id = "sandbox-account"
        self.placed = []
        self.cancelled = []

    def place_option_order(self, payload):
        self.placed.append(payload)
        return {"client_order_id": payload["client_order_id"]}

    def cancel_order(self, client_order_id):
        self.cancelled.append(client_order_id)

    def option_contract_quote(self, option_symbol):
        return {"bid": 1.20, "ask": 1.30}

    def underlying_quote(self, symbol):
        return 667.0


def _ticket(book, signal_id, limit, sell_limit, stake, settled, debit):
    state = empty_state()
    state["book"] = book
    state["stake"] = stake
    state["settled"] = settled
    state["signals"] = [
        {
            "id": signal_id,
            "status": "open",
            "symbol": "SPY" if book == NAME else "QQQ",
            "direction": "short",
            "right": "put",
            "option_type": "PUT",
            "qty": 1,
            "stop": 670.0,
            "target": 668.0,
            "entry": 669.0,
            "entry_time": f"{DAY}T10:00:00-04:00",
            "model_debit": debit,
        }
    ]
    state["positions"] = [
        {
            "id": signal_id,
            "direction": "short",
            "right": "put",
            "option_type": "PUT",
            "qty": 1,
            "strike": 670.0,
            "model_strike": 670.0,
            "expiry": DAY,
            "option_symbol": "TEST",
            "stop": 670.0,
            "target": 668.0,
            "entry": 669.0,
            "entry_time": f"{DAY}T10:00:00-04:00",
            "iv": 0.2,
            "model_debit": debit,
        }
    ]
    state["orders"] = [
        {
            "key": f"{signal_id}|entry",
            "id": f"{signal_id}-buy",
            "kind": "entry",
            "side": "BUY",
            "qty": "1",
            "symbol": state["signals"][0]["symbol"],
            "right": "PUT",
            "status": "submitted",
            "limit": limit,
            "submitted_at": f"{DAY}T10:00:00-04:00",
        },
        {
            "key": f"{signal_id}|exit",
            "id": f"{signal_id}-sell",
            "kind": "exit",
            "side": "SELL",
            "qty": "1",
            "symbol": state["signals"][0]["symbol"],
            "right": "PUT",
            "status": "rejected",
            "limit": sell_limit,
            "error": "rejected",
            "submitted_at": f"{DAY}T10:00:30-04:00",
        },
    ]
    state["fills"] = [
        {
            "id": signal_id,
            "side": "BUY",
            "qty": "1",
            "right": "put",
            "price": limit,
            "time": f"{DAY}T10:00:00-04:00",
        }
    ]
    return state


def test_a_marketable_buy_is_one_cent_through_the_ask():
    assert _buy_limit(0.86) == pytest.approx(0.87)
    assert _buy_limit(2.49) == pytest.approx(2.50)
    assert _buy_limit(2.50) == pytest.approx(2.51)
    assert _buy_limit(2.501) == pytest.approx(2.51)


def test_a_working_entry_does_not_sell_until_the_fill_is_confirmed(tmp_path):
    journal = Journal(tmp_path / "working.sqlite")
    state = _ticket(NAME, "spy-1000", "0.86", "1.44", 1000.0, 1000.0, 86.0)
    state["orders"] = [state["orders"][0]]
    broker = _Broker({"spy-1000-buy": {"status": "SUBMITTED", "limit_price": "0.86"}})
    broker.underlying_quote = lambda symbol: 669.0
    token = _activate(NAME)
    try:
        journal.forward_save(NAME, state)
        lines = []
        _manage_open(journal.forward_load(NAME), None, _at("10:02"), broker, lines, journal)
    finally:
        _ACTIVE.reset(token)
    saved = journal.forward_load(NAME)
    assert saved["positions"]
    assert saved["signals"][0]["status"] == "open"
    assert broker.placed == []
    assert broker.cancelled == []
    assert any("No exit" in line for line in lines)


def test_price_outside_the_band_cancels_before_the_window_ends():
    state = _ticket(NAME, "spy-band", "0.86", "1.44", 1000.0, 1000.0, 86.0)
    state["orders"] = [state["orders"][0]]
    broker = _Broker({"spy-band-buy": {"status": "SUBMITTED", "limit_price": "0.86"}})
    lines = []
    sync_working_entries(state, broker, _at("10:02"), 671.0, lines)
    assert broker.cancelled == ["spy-band-buy"]
    assert broker.placed == []
    assert state["positions"] == []
    assert state["signals"][0]["status"] == "skip"
    assert state["signals"][0]["skip"] == "unfilled"


def test_unknown_detail_does_not_cancel_or_sell():
    state = _ticket(NAME, "spy-unknown", "0.86", "1.44", 1000.0, 1000.0, 86.0)
    state["orders"] = [state["orders"][0]]

    class Quiet(_Broker):
        def order_detail(self, order_id):
            return {"kind": "unknown"}

    broker = Quiet({})
    lines = []
    sync_working_entries(state, broker, _at("10:30"), None, lines)
    assert broker.cancelled == []
    assert broker.placed == []
    assert state["positions"]
    assert any("not confirmed" in line for line in lines)


def test_a_confirmed_fill_can_exit(tmp_path):
    journal = Journal(tmp_path / "filled.sqlite")
    state = _ticket(NAME, "spy-fill", "0.86", "1.44", 1000.0, 1000.0, 86.0)
    state["orders"] = [state["orders"][0]]
    broker = _Broker(
        {"spy-fill-buy": {"status": "FILLED", "limit_price": "0.86", "avg_filled_price": "0.80"}}
    )
    token = _activate(NAME)
    try:
        journal.forward_save(NAME, state)
        lines = []
        _manage_open(journal.forward_load(NAME), None, _at("10:05"), broker, lines, journal)
    finally:
        _ACTIVE.reset(token)
    assert broker.cancelled == []
    assert len(broker.placed) == 1
    assert broker.placed[0]["side"] == "SELL"
    saved = journal.forward_load(NAME)
    assert saved["signals"][0]["status"] == "open" or saved["positions"] == []
    assert any(row.get("fill") == pytest.approx(0.80) for row in saved["orders"] if row.get("kind") == "entry")


def test_a_working_sell_is_not_resent_without_an_entry_fill():
    state = _ticket(NAME, "spy-chase", "0.86", "1.44", 1000.0, 1000.0, 86.0)
    state["orders"][1]["status"] = "submitted"
    state["orders"][1]["broker_status"] = "working"
    broker = _Broker(
        {
            "spy-chase-buy": {"status": "SUBMITTED", "limit_price": "0.86"},
            "spy-chase-sell": {"status": "SUBMITTED", "limit_price": "1.44"},
        }
    )
    lines = []
    chase_exit_orders(state, broker, _at("10:30"), lines)
    assert broker.placed == []
    assert broker.cancelled == ["spy-chase-sell"]
    assert state["orders"][1]["error"] == "no entry fill"
    assert any("not confirmed" in line for line in lines)


def test_reconcile_marks_the_october_12_buys_unfilled(tmp_path):
    journal = Journal(tmp_path / "today.sqlite")
    spy = _ticket(NAME, "spy-1000", "0.86", "1.44", 1000.0, 914.0, 86.0)
    compound = _ticket(QQQ_COMPOUND_NAME, "qqq-compound", "2.49", "3.49", 5000.0, 4751.0, 249.0)
    journal.forward_save(NAME, spy)
    journal.forward_save(QQQ_COMPOUND_NAME, compound)
    spy_broker = _Broker({"spy-1000-buy": {"status": "SUBMITTED", "limit_price": "0.86"}})
    compound_broker = _Broker({"qqq-compound-buy": {"status": "SUBMITTED", "limit_price": "2.49"}})
    spy_lines = reconcile_book(journal, spy_broker, NAME, _at("10:30"))
    compound_lines = reconcile_book(journal, compound_broker, QQQ_COMPOUND_NAME, _at("10:30"))
    spy_text = "\n".join(spy_lines)
    compound_text = "\n".join(compound_lines)
    assert "does not place" in spy_text
    assert "unfilled" in spy_text
    assert "unfilled" in compound_text
    assert spy_broker.placed == []
    assert compound_broker.placed == []
    assert spy_broker.cancelled == ["spy-1000-buy"]
    assert compound_broker.cancelled == ["qqq-compound-buy"]
    saved_spy = journal.forward_load(NAME)
    saved_compound = journal.forward_load(QQQ_COMPOUND_NAME)
    assert saved_spy["positions"] == []
    assert saved_compound["positions"] == []
    assert saved_spy["signals"][0]["status"] == "skip"
    assert saved_spy["signals"][0]["skip"] == "unfilled"
    assert saved_compound["signals"][0]["status"] == "skip"
    assert saved_compound["signals"][0]["skip"] == "unfilled"
    assert saved_spy["settled"] == pytest.approx(1000.0)
    assert saved_compound["settled"] == pytest.approx(5000.0)
    assert saved_spy["orders"][1]["error"] == "no entry fill"
    assert saved_compound["orders"][1]["limit"] == "3.49"
    assert all(row.get("fill") in (None, "") for row in saved_spy["fills"])
    assert all(row.get("side") != "SELL" or row.get("status") != "submitted" for row in saved_spy["orders"])
