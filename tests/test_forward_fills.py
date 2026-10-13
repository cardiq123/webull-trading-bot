"""An unfilled buy is not a position. Sandbox only. No network."""

from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from webull_bot.execution.forward_fills import sync_working_entries
from webull_bot.execution.forward_reconcile import chase_exit_orders, read_order_detail, reconcile_book, reset_order_poll
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


def test_a_marketable_sell_is_one_cent_through_the_bid():
    from webull_bot.execution.forward_vwap import _exit_limit, _sell_limit

    assert _sell_limit(0.40) == pytest.approx(0.39)
    assert _sell_limit(0.25) == pytest.approx(0.24)
    assert _sell_limit(0.401) == pytest.approx(0.40)
    assert _sell_limit(0.01) == pytest.approx(0.01)
    assert _exit_limit(0.40, _at("14:00"), DAY) == pytest.approx(0.39)
    assert _exit_limit(0.40, _at("15:44"), DAY) == pytest.approx(0.01)


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


def test_a_held_contract_sells_when_order_detail_is_rate_limited(tmp_path):
    """The SPY put is already through the target. The position list confirms the fill."""
    reset_order_poll()
    journal = Journal(tmp_path / "held.sqlite")
    state = _ticket(NAME, "spy-held", "0.50", "1.44", 1000.0, 1000.0, 50.0)
    state["orders"] = [state["orders"][0]]
    state["positions"][0]["entry_filled"] = False
    state["positions"][0]["option_symbol"] = "SPY261013P00776000"
    state["orders"][0]["option_symbol"] = "SPY261013P00776000"

    class Limited(_Broker):
        def __init__(self):
            super().__init__({})
            self.detail_calls = 0

        def get_order_detail(self, account_id, client_order_id):
            self.detail_calls += 1
            raise RuntimeError("HTTP 429 Too Many Requests")

    broker = Limited()
    broker._trade.order_v3.get_order_detail = broker.get_order_detail
    broker._trade.account_v2.get_account_position = lambda account_id: {
        "positions": [{"symbol": "SPY261013P00776000", "quantity": 1, "avg_cost": "0.50"}]
    }
    broker.underlying_quote = lambda symbol: 667.0
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
    assert any(row.get("fill") == pytest.approx(0.50) for row in saved["orders"] if row.get("kind") == "entry")
    assert saved["positions"] == [] or saved["positions"][0].get("entry_filled") is True


def test_order_detail_is_read_once_per_order_on_the_watch():
    reset_order_poll()
    calls = {"n": 0}

    class Once:
        def get_order_detail(self, account_id, client_order_id):
            calls["n"] += 1
            return {"status": "SUBMITTED", "limit_price": "0.76"}

    broker = _Broker({})
    broker._watch_armed = True
    broker._trade.order_v3.get_order_detail = Once().get_order_detail
    first = read_order_detail(broker, "aggr-buy")
    second = read_order_detail(broker, "aggr-buy")
    other = read_order_detail(broker, "other-buy")
    assert first["kind"] == "working"
    assert second["kind"] == "working"
    assert other["kind"] == "deferred"
    assert calls["n"] == 1
    reset_order_poll()


def test_a_journaled_model_compound_buy_is_sent(tmp_path):
    reset_order_poll()
    journal = Journal(tmp_path / "compound.sqlite")
    signal_id = "qqq-1100"
    built = {
        "id": signal_id,
        "status": "open",
        "direction": "short",
        "right": "put",
        "option_type": "PUT",
        "qty": 1,
        "strike": 742.0,
        "expiry": "2026-10-14",
        "signal_time": f"{DAY}T11:00:00-04:00",
        "fill_time": f"{DAY}T11:05:00-04:00",
        "entry_time": f"{DAY}T11:05:00-04:00",
        "entry": 743.0,
        "modeled_entry": 743.0,
        "stop": 744.0,
        "target": 742.0,
        "model_ask": 1.25,
        "model_debit": 126.0,
        "iv": 0.2,
    }
    state = empty_state()
    state["book"] = QQQ_COMPOUND_NAME
    state["stake"] = 5000.0
    state["settled"] = 5000.0
    state["orders"] = [
        {
            "key": f"{signal_id}|entry",
            "id": "compound-1100",
            "kind": "entry",
            "side": "BUY",
            "qty": "1",
            "status": "intent",
            "limit": "1.26",
            "price_source": "model",
            "right": "PUT",
            "symbol": "QQQ",
        }
    ]
    broker = _Broker({})
    broker._trade.order_v3.get_order_open = lambda **kwargs: []
    from webull_bot.execution.forward_vwap import _send_open

    token = _activate(QQQ_COMPOUND_NAME)
    try:
        lines = []
        _send_open(state, built, _at("11:06"), broker, lines, journal)
    finally:
        _ACTIVE.reset(token)
    assert len(broker.placed) == 1
    assert broker.placed[0]["side"] == "BUY"
    assert broker.placed[0]["symbol"] == "QQQ"
    assert float(broker.placed[0]["limit_price"]) == pytest.approx(1.26)
    assert state["orders"][0]["status"] == "submitted"
    assert state["positions"]
    assert state["positions"][0]["stop"] == pytest.approx(744.0)


DAY13 = "2026-10-13"
FOUR_HOUR_CONTRACT = "QQQ261014P00745000"
AGGR_CONTRACT = "QQQ261013P00742000"


def _at13(hhmm: str) -> datetime:
    hour, minute = hhmm.split(":")
    return datetime(2026, 10, 13, int(hour), int(minute), tzinfo=NY)


def _qqq_position_row() -> dict:
    """Sandbox shape: the underlying is the symbol, and the put is a nested leg."""
    return {
        "symbol": "QQQ",
        "quantity": "1.0",
        "cost_price": "3.53",
        "instrument_type": "OPTION",
        "items": [
            {
                "symbol": "QQQ",
                "option_type": "PUT",
                "strike_price": "745",
                "option_expire_date": "2026-10-14",
                "instrument_id": "opt-4hr",
                "quantity": "1",
            }
        ],
    }


def _four_hour_state() -> dict:
    signal_id = "qqq-4hr"
    state = empty_state()
    state["book"] = "four_hour_qqq_1dte"
    state["stake"] = 2500.0
    state["settled"] = 2500.0
    state["signals"] = [
        {
            "id": signal_id,
            "status": "open",
            "symbol": "QQQ",
            "direction": "short",
            "right": "put",
            "option_type": "PUT",
            "qty": 1,
            "strike": 745.0,
            "expiry": "2026-10-14",
            "stop": 748.0,
            "target": 744.0,
            "entry": 746.0,
            "entry_time": f"{DAY13}T10:05:00-04:00",
        }
    ]
    state["positions"] = [
        {
            "id": signal_id,
            "direction": "short",
            "right": "put",
            "option_type": "PUT",
            "qty": 1,
            "strike": 745.0,
            "model_strike": 745.0,
            "expiry": "2026-10-14",
            "option_symbol": FOUR_HOUR_CONTRACT,
            "stop": 748.0,
            "target": 744.0,
            "entry": 746.0,
            "entry_time": f"{DAY13}T10:05:00-04:00",
            "fill_time": f"{DAY13}T10:05:00-04:00",
            "entry_filled": False,
            "iv": 0.2,
            "model_debit": 353.0,
        }
    ]
    state["orders"] = [
        {
            "key": f"{signal_id}|entry",
            "id": "qqq-4hr-buy",
            "kind": "entry",
            "side": "BUY",
            "qty": "1",
            "symbol": "QQQ",
            "right": "PUT",
            "status": "submitted",
            "limit": "3.54",
            "sandbox_price": "3.53",
            "price_source": "webull",
            "strike": 745.0,
            "expiry": "2026-10-14",
            "option_type": "PUT",
            "submitted_at": f"{DAY13}T10:05:00-04:00",
        }
    ]
    return state


def _aggr_state() -> dict:
    signal_id = "qqq-1100"
    state = empty_state()
    state["book"] = "vwap_band_15m_qqq_aggr"
    state["stake"] = 2500.0
    state["settled"] = 2500.0
    state["signals"] = [
        {
            "id": signal_id,
            "status": "open",
            "symbol": "QQQ",
            "direction": "short",
            "right": "put",
            "option_type": "PUT",
            "qty": 1,
            "strike": 742.0,
            "expiry": DAY13,
            "stop": 744.0,
            "target": 741.0,
            "entry": 743.0,
            "entry_time": f"{DAY13}T11:05:00-04:00",
        }
    ]
    state["positions"] = [
        {
            "id": signal_id,
            "direction": "short",
            "right": "put",
            "option_type": "PUT",
            "qty": 1,
            "strike": 742.0,
            "expiry": DAY13,
            "option_symbol": AGGR_CONTRACT,
            "stop": 744.0,
            "target": 741.0,
            "entry": 743.0,
            "entry_time": f"{DAY13}T11:05:00-04:00",
            "entry_filled": False,
        }
    ]
    state["orders"] = [
        {
            "key": f"{signal_id}|entry",
            "id": "qqq-742-buy",
            "kind": "entry",
            "side": "BUY",
            "qty": "1",
            "symbol": "QQQ",
            "right": "PUT",
            "status": "submitted",
            "limit": "0.76",
            "sandbox_price": "0.75",
            "price_source": "webull",
            "strike": 742.0,
            "expiry": DAY13,
            "option_type": "PUT",
            "option_symbol": AGGR_CONTRACT,
            "submitted_at": f"{DAY13}T11:00:00-04:00",
        }
    ]
    return state


class _RateLimited(_Broker):
    def __init__(self, positions, open_orders=None):
        super().__init__({})
        self.positions = positions
        self.open_orders = [] if open_orders is None else open_orders

        def detail(account_id, client_order_id):
            raise RuntimeError("HTTP 429 Too Many Requests")

        self._trade.order_v3.get_order_detail = detail
        self._trade.account_v2.get_account_position = lambda account_id: {"positions": self.positions}
        self._trade.order_v3.get_order_open = lambda **kwargs: self.open_orders


def test_option_fields_confirm_the_four_hour_put_and_not_the_other_qqq_buy(tmp_path):
    """The account row says QQQ. The leg is the 745 put at $3.53, so that book can sell."""
    reset_order_poll()
    import pandas as pd

    from webull_bot.execution.forward_four_hour import _manage_open as hour_manage
    from webull_bot.execution.forward_reconcile import holdings_lines

    journal = Journal(tmp_path / "hour.sqlite")
    state = _four_hour_state()
    broker = _RateLimited([_qqq_position_row()])
    broker.underlying_quote = lambda symbol: 740.0
    broker.option_contract_quote = lambda option_symbol: {"bid": 4.10, "ask": 4.20}
    lines = []
    hour_manage(state, pd.DataFrame(), _at13("12:10"), broker, lines, journal)
    assert broker.cancelled == []
    assert len(broker.placed) == 1
    assert broker.placed[0]["side"] == "SELL"
    assert broker.placed[0]["legs"][0]["strike_price"] == "745.00"
    saved_order = next(row for row in state["orders"] if row.get("kind") == "entry")
    assert saved_order["fill"] == pytest.approx(3.53)
    assert saved_order["fill_source"] == "position"

    other = _aggr_state()
    other_lines = []
    sync_working_entries(other, _RateLimited([_qqq_position_row()], open_orders=[]), _at13("11:20"), 743.0, other_lines)
    assert other["orders"][0].get("fill") in (None, "")
    assert other["signals"][0]["skip"] == "unfilled"
    assert other["positions"] == []

    from webull_bot.execution.forward_reconcile import _position_rows

    parsed = _position_rows({"positions": [_qqq_position_row()]})
    text = "\n".join(holdings_lines(state, parsed, [state["orders"][0], other["orders"][0]]))
    assert "PUT" in text and "745" in text and "avg 3.53" in text
    assert f"{FOUR_HOUR_CONTRACT}: the sandbox account still holds" in text
    assert f"{AGGR_CONTRACT}: the sandbox account does not hold this contract." in text


def test_a_bare_qqq_average_confirms_only_the_near_premium(tmp_path):
    reset_order_poll()
    bare = [{"symbol": "QQQ", "quantity": "1.0", "cost_price": "3.53"}]
    state = _four_hour_state()
    lines = []
    sync_working_entries(state, _RateLimited(bare, open_orders=[]), _at13("12:10"), 746.0, lines)
    assert state["orders"][0]["fill"] == pytest.approx(3.53)
    assert state["positions"][0]["entry_filled"] is True
    assert state["signals"][0]["status"] == "open"

    stock = [{"symbol": "QQQ", "quantity": "1.0", "cost_price": "740.00"}]
    missed = _four_hour_state()
    sync_working_entries(missed, _RateLimited(stock, open_orders=[]), _at13("12:10"), 746.0, [])
    assert missed["orders"][0].get("fill") in (None, "")
    assert missed["signals"][0]["skip"] == "unfilled"


def test_an_unfilled_11_buy_gets_a_missed_fill_shadow(tmp_path):
    reset_order_poll()
    from webull_bot.execution.forward_missed import apply_missed_fills

    state = _aggr_state()
    broker = _RateLimited([_qqq_position_row()], open_orders=[])
    lines = []
    sync_working_entries(state, broker, _at13("11:20"), 743.0, lines)
    assert broker.cancelled == []
    assert state["signals"][0]["status"] == "skip"
    assert state["signals"][0]["skip"] == "unfilled"
    assert state["orders"][0]["status"] == "cancelled"
    assert apply_missed_fills(state, "vwap_band_15m_qqq_aggr", tmp_path)
    shadow = state["missed_fills"][0]
    assert shadow["id"] == "qqq-1100"
    assert shadow["ask"] == pytest.approx(0.75)
    assert shadow["missed_pnl"] is None
    assert shadow["status"] in {"open", "no_quote"}


def test_a_still_working_buy_cancels_through_the_exit_view():
    reset_order_poll()
    from webull_bot.execution.forward_watch import _ExitView

    state = _aggr_state()
    inner = _RateLimited(
        [_qqq_position_row()],
        open_orders=[{"client_order_id": "qqq-742-buy", "status": "SUBMITTED", "limit_price": "0.76"}],
    )
    view = _ExitView(inner, {"QQQ": 743.0})
    lines = []
    sync_working_entries(state, view, _at13("11:20"), 743.0, lines)
    assert inner.cancelled == ["qqq-742-buy"]
    assert state["signals"][0]["skip"] == "unfilled"
    assert inner.placed == []


def _live_holdings() -> list[dict]:
    """The sandbox rows as printed: right and expiry, no strike."""
    return [
        {
            "symbol": "QQQ",
            "quantity": "3.0",
            "cost_price": "0.77",
            "option_type": "PUT",
            "option_expire_date": "2026-10-13",
        },
        {
            "symbol": "SPY",
            "quantity": "1.0",
            "cost_price": "0.50",
            "option_type": "PUT",
            "option_expire_date": "2026-10-13",
        },
        {
            "symbol": "QQQ",
            "quantity": "1.0",
            "cost_price": "3.53",
            "option_type": "PUT",
            "option_expire_date": "2026-10-14",
        },
    ]


def _open_put(signal_id, *, limit, qty, expiry, strike, symbol="QQQ"):
    state = empty_state()
    state["book"] = signal_id
    state["stake"] = 2500.0
    state["settled"] = 2500.0
    state["signals"] = [
        {
            "id": signal_id,
            "status": "open",
            "symbol": symbol,
            "direction": "short",
            "right": "put",
            "option_type": "PUT",
            "qty": qty,
            "strike": strike,
            "order_strike": strike,
            "expiry": expiry,
            "stop": 748.0 if symbol == "QQQ" else 670.0,
            "target": 744.0 if symbol == "QQQ" else 668.0,
            "entry": 746.0 if symbol == "QQQ" else 669.0,
            "entry_time": f"{DAY13}T11:05:00-04:00",
            "iv": 0.2,
            "model_debit": float(limit) * 100.0 * qty,
        }
    ]
    state["positions"] = [
        {
            "id": signal_id,
            "direction": "short",
            "right": "put",
            "option_type": "PUT",
            "qty": qty,
            "strike": strike,
            "model_strike": strike,
            "expiry": expiry,
            "option_symbol": "",
            "stop": state["signals"][0]["stop"],
            "target": state["signals"][0]["target"],
            "entry": state["signals"][0]["entry"],
            "entry_time": f"{DAY13}T11:05:00-04:00",
            "entry_filled": False,
            "iv": 0.2,
            "model_debit": state["signals"][0]["model_debit"],
        }
    ]
    state["orders"] = [
        {
            "key": f"{signal_id}|entry",
            "id": f"{signal_id}-buy",
            "kind": "entry",
            "side": "BUY",
            "qty": str(qty),
            "symbol": symbol,
            "right": "PUT",
            "option_type": "PUT",
            "status": "submitted",
            "limit": f"{limit:.2f}",
            "sandbox_price": f"{limit - 0.01:.2f}",
            "price_source": "webull",
            "strike": strike,
            "expiry": expiry,
            "submitted_at": f"{DAY13}T11:00:00-04:00",
        }
    ]
    return state


def test_a_holding_without_a_strike_keeps_the_matching_book_open():
    """Qty and average separate the 3-lot at $0.77 from the 1-lot at $3.53."""
    reset_order_poll()
    from webull_bot.execution.forward_fills import _HOLDING_LOG
    from webull_bot.execution.forward_reconcile import _describe_holding, _position_rows, holdings_lines

    _HOLDING_LOG.clear()
    holdings = _position_rows({"positions": _live_holdings()})
    text = "\n".join(_describe_holding(row) for row in holdings)
    assert "strike missing" in text
    assert "symbol QQQ" in text
    assert "2026-10-13" in text and "avg 0.77" in text
    assert "option_type=PUT" in text

    aggressive = _open_put("qqq-aggr", limit=0.76, qty=3, expiry=DAY13, strike=742.0)
    lines = []
    sync_working_entries(aggressive, _RateLimited(_live_holdings(), open_orders=[]), _at13("11:20"), 743.0, lines)
    assert aggressive["orders"][0]["fill"] == pytest.approx(0.77)
    assert aggressive["signals"][0]["status"] == "open"
    assert aggressive["signals"][0].get("skip") in (None, "")
    assert aggressive["positions"]
    assert aggressive["positions"][0]["entry_filled"] is True

    four_hour = _open_put("qqq-4hr", limit=3.54, qty=1, expiry="2026-10-14", strike=744.0)
    four_hour["orders"][0]["option_symbol"] = "QQQ261014P00744000"
    four_hour["positions"][0]["option_symbol"] = "QQQ261014P00744000"
    sync_working_entries(four_hour, _RateLimited(_live_holdings(), open_orders=[]), _at13("12:10"), 746.0, [])
    assert four_hour["orders"][0]["fill"] == pytest.approx(3.53)
    assert four_hour["signals"][0].get("skip") in (None, "")
    report = "\n".join(holdings_lines(four_hour, holdings, four_hour["orders"]))
    assert "QQQ261014P00744000: the sandbox account still holds" in report
    assert "does not hold this contract" not in report

    one_dte = _open_put("qqq-1dte", limit=2.81, qty=1, expiry="2026-10-14", strike=742.0)
    compound = _open_put("qqq-compound", limit=1.26, qty=1, expiry="2026-10-14", strike=742.0)
    for state in (one_dte, compound):
        sync_working_entries(state, _RateLimited(_live_holdings(), open_orders=[]), _at13("11:20"), 743.0, [])
        assert state["orders"][0].get("fill") in (None, "")
        assert state["signals"][0]["skip"] == "unfilled"
        assert state["positions"] == []
        sync_working_entries(state, _RateLimited(_live_holdings(), open_orders=[]), _at13("11:21"), 743.0, [])
        assert state["positions"] == []
        assert state["signals"][0]["skip"] == "unfilled"


def test_a_spaced_occ_symbol_supplies_the_strike():
    from webull_bot.execution.forward_reconcile import _position_rows

    rows = _position_rows(
        {"positions": [{"symbol": "QQQ  261014P00745000", "quantity": "1", "cost_price": "3.53"}]}
    )
    assert rows[0]["strike"] == pytest.approx(745.0)
    assert rows[0]["expiry"] == "2026-10-14"
    assert rows[0]["right"] == "P"
    assert "QQQ261014P00745000" in rows[0]["symbols"]


def test_a_skipped_holding_is_adopted_and_the_shadow_is_removed(tmp_path):
    reset_order_poll()
    import pandas as pd

    from webull_bot.execution.forward_fills import _HOLDING_LOG
    from webull_bot.execution.forward_four_hour import _manage_open as hour_manage

    _HOLDING_LOG.clear()
    journal = Journal(tmp_path / "adopt.sqlite")
    state = _open_put("qqq-4hr", limit=3.54, qty=1, expiry="2026-10-14", strike=744.0)
    state["book"] = "four_hour_qqq_1dte"
    state["signals"][0]["status"] = "skip"
    state["signals"][0]["skip"] = "unfilled"
    state["signals"][0]["reason"] = "unfilled"
    state["positions"] = []
    state["orders"][0]["status"] = "cancelled"
    state["orders"][0]["broker_status"] = "cancelled"
    state["orders"][0]["option_symbol"] = "QQQ261014P00744000"
    state["missed_fills"] = [{"id": "qqq-4hr", "missed_pnl": -10.0, "status": "closed"}]
    held = {
        "symbol": "QQQ",
        "quantity": "1.0",
        "cost_price": "3.53",
        "option_type": "PUT",
        "option_expire_date": "2026-10-14",
        "strike_price": "745",
    }
    broker = _RateLimited([held], open_orders=[])
    broker.underlying_quote = lambda symbol: 740.0
    broker.option_contract_quote = lambda option_symbol: {"bid": 4.10, "ask": 4.20}
    lines = []
    hour_manage(state, pd.DataFrame(), _at13("12:10"), broker, lines, journal)
    assert any(row.get("side") == "SELL" for row in broker.placed)
    assert all(row.get("side") != "BUY" for row in broker.placed)
    assert broker.placed[-1]["legs"][0]["strike_price"] == "745.00"
    assert state["missed_fills"] == []
    assert state["signals"][0].get("skip") in (None, "")
    assert state["signals"][0].get("reason") != "unfilled"
    assert state["orders"][0]["fill"] == pytest.approx(3.53)
    assert any("Adopted" in line and "Missed-fill shadow removed" in line for line in lines)
    assert any("745" in line and "744" in line for line in lines)
