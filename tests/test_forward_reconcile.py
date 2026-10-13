"""Read-only reconcile, exit reprice, and limit-versus-fill wording."""

from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from webull_bot.cli import build_parser
from webull_bot.execution.forward_cash import prepare_cash
from webull_bot.execution.forward_reconcile import (
    chase_exit_orders,
    limit_fill_text,
    parse_order_detail,
    reconcile_book,
    require_sandbox,
)
from webull_bot.execution.forward_vwap import QQQ_AGGR_NAME, report_text
from webull_bot.journal.store import Journal

NY = ZoneInfo("America/New_York")
SECRET = "super-secret-value"
CONTRACT = "QQQ261009C00751000"


def _now(hhmm: str, day: str = "2026-10-09") -> datetime:
    hour, minute = hhmm.split(":")
    return datetime(2026, 10, 9, int(hour), int(minute), tzinfo=NY) if day == "2026-10-09" else datetime.fromisoformat(f"{day}T{hhmm}:00-04:00")


def _state(status_payload_ready: bool = True) -> dict:
    return {
        "book": QQQ_AGGR_NAME,
        "stake": 2500.0,
        "settled": 2316.88,
        "unsettled": [],
        "signals": [
            {
                "id": "qqq-stop",
                "status": "closed",
                "symbol": "QQQ",
                "direction": "long",
                "right": "call",
                "option_type": "CALL",
                "strike": 751.0,
                "expiry": "2026-10-09",
                "qty": 3,
                "signal_time": "2026-10-09T14:00:00-04:00",
                "entry_time": "2026-10-09T14:15:00-04:00",
                "exit_time": "2026-10-09T14:34:56-04:00",
                "entry": 751.0,
                "stop": 750.0,
                "target": 752.0,
                "model_debit": 180.0,
                "model_credit": 40.0,
                "pnl": -140.0,
                "reason": "stop",
                "exit": 749.2,
            }
        ],
        "orders": [
            {
                "key": "qqq-stop|exit",
                "id": "exit-1",
                "kind": "exit",
                "side": "SELL",
                "qty": "3",
                "symbol": "QQQ",
                "right": "call",
                "option_type": "CALL",
                "strike": 751.0,
                "expiry": "2026-10-09",
                "status": "submitted",
                "limit": "0.60",
                "submitted_at": "2026-10-09T14:34:56-04:00",
                "fill": None,
            }
        ],
        "fills": [
            {
                "id": "qqq-stop",
                "side": "SELL",
                "qty": "3",
                "right": "call",
                "price": "0.60",
                "time": "2026-10-09T14:34:56-04:00",
            }
        ],
        "exits": [
            {
                "id": "qqq-stop",
                "time": "2026-10-09T14:34:56-04:00",
                "right": "call",
                "reason": "stop",
                "underlying": 749.2,
                "pnl": -140.0,
            }
        ],
        "positions": [],
    }


class _Detail:
    def __init__(self, payloads):
        self.payloads = payloads
        self.calls = []

    def get_order_detail(self, account_id, client_order_id):
        self.calls.append(client_order_id)
        payload = self.payloads[client_order_id]
        if isinstance(payload, Exception):
            raise payload
        return payload


class _Account:
    def __init__(self, rows):
        self.rows = rows

    def get_account_position(self, account_id):
        return {"positions": self.rows}


class _Broker:
    def __init__(self, payloads, holdings=None):
        self._trade = SimpleNamespace(order_v3=_Detail(payloads), account_v2=_Account(holdings or []))
        self.account_id = "sandbox-account"
        self.placed = []
        self.cancelled = []
        self.replaced = []

    def place_option_order(self, payload):
        self.placed.append(payload)
        return {"ok": True}

    def cancel_order(self, client_order_id):
        self.cancelled.append(client_order_id)

    def replace_order(self, client_order_id, quantity, limit_price=None):
        self.replaced.append((client_order_id, quantity, limit_price))

    def option_contract_quote(self, option_symbol):
        return {"bid": 0.40, "ask": 0.45}


def test_parser_accepts_reconcile_and_live_env_is_refused(monkeypatch):
    parser = build_parser()
    args = parser.parse_args(["forward-reconcile", QQQ_AGGR_NAME])
    assert args.strategy == QQQ_AGGR_NAME
    monkeypatch.delenv("WEBULL_ENV", raising=False)
    with pytest.raises(SystemExit, match="WEBULL_ENV=sandbox"):
        require_sandbox()
    monkeypatch.setenv("WEBULL_ENV", "production")
    with pytest.raises(SystemExit, match="Live trading stays off"):
        require_sandbox()


def test_a_limit_in_the_payload_is_not_a_fill():
    pending = parse_order_detail({"status": "SUBMITTED", "limit_price": "0.60", "price": "0.60"})
    assert pending["kind"] == "working"
    assert pending["price"] is None
    assert "not a fill" in limit_fill_text("0.60", None)
    assert "Fill 0.60" not in limit_fill_text("0.60", None)
    filled = parse_order_detail(
        {"status": "FILLED", "limit_price": "0.60", "avg_filled_price": "0.55", "filled_time": "2026-10-09T14:35:10-04:00"}
    )
    assert filled["kind"] == "filled"
    assert filled["price"] == pytest.approx(0.55)
    partial = parse_order_detail(
        {"status": "PARTIALLY_FILLED", "avg_filled_price": "0.40", "filled_quantity": "1", "quantity": "3"}
    )
    assert partial["kind"] == "partial"
    assert parse_order_detail({"status": "CANCELLED", "limit_price": "0.60"})["kind"] == "cancelled"
    filled_qty = parse_order_detail(
        {"status": "SUBMITTED", "limit_price": "2.82", "avgFilledPrice": "2.82", "filledQuantity": "1", "quantity": "1"}
    )
    assert filled_qty["kind"] == "filled"
    assert filled_qty["price"] == pytest.approx(2.82)
    assert parse_order_detail({"status": "EXPIRED", "limit_price": "0.60"})["kind"] == "expired"


def test_reconcile_records_the_fill_and_does_not_trade(tmp_path):
    journal = Journal(tmp_path / "reconcile.sqlite")
    journal.forward_save(QQQ_AGGR_NAME, _state())
    broker = _Broker(
        {"exit-1": {"status": "FILLED", "limit_price": "0.60", "avg_filled_price": "0.55", "filled_time": "2026-10-09T14:35:02-04:00"}},
        holdings=[{"symbol": CONTRACT, "quantity": 0}],
    )
    lines = reconcile_book(journal, broker, QQQ_AGGR_NAME, _now("20:10"))
    text = "\n".join(lines)
    assert SECRET not in text
    assert "does not place" in text
    assert "Fill 0.55" in text
    assert "not a fill" in text
    assert broker.placed == []
    assert broker.cancelled == []
    assert broker.replaced == []
    saved = journal.forward_load(QQQ_AGGR_NAME)
    assert saved["orders"][0]["fill"] == pytest.approx(0.55)
    assert saved["orders"][0]["limit"] == "0.60"
    assert saved["orders"][0]["status"] == "submitted"
    assert saved["fills"][0]["fill"] == pytest.approx(0.55)
    assert saved["fills"][0]["price"] == "0.60"
    report = report_text(journal, book=QQQ_AGGR_NAME)
    assert "Limit 0.60, not a fill. Fill 0.55" in report
    assert "The limit is not a fill" not in report or "fill P&L" in report
    assert SECRET not in report


def test_reconcile_reports_a_pending_limit_and_an_open_contract(tmp_path):
    journal = Journal(tmp_path / "pending.sqlite")
    journal.forward_save(QQQ_AGGR_NAME, _state())
    broker = _Broker(
        {"exit-1": RuntimeError(f"request failed {SECRET}")},
        holdings=[{"symbol": CONTRACT, "quantity": 3}],
    )
    # A transport error must not leak the secret, and must not trade.
    lines = reconcile_book(journal, broker, QQQ_AGGR_NAME, _now("14:40"))
    text = "\n".join(lines)
    assert SECRET not in text
    assert "not printed" in text
    assert broker.placed == []
    assert broker.cancelled == []

    broker = _Broker(
        {"exit-1": {"status": "SUBMITTED", "limit_price": "0.60"}},
        holdings=[{"option_symbol": CONTRACT, "quantity": 3}],
    )
    lines = reconcile_book(journal, broker, QQQ_AGGR_NAME, _now("14:41"))
    text = "\n".join(lines)
    assert "Limit 0.60, not a fill. Fill pending." in text
    assert f"{CONTRACT}: the sandbox account still holds 3" in text
    assert "Fill 0.60" not in text
    saved = journal.forward_load(QQQ_AGGR_NAME)
    assert saved["orders"][0].get("fill") in (None, "")
    assert saved["orders"][0]["broker_status"] == "working"
    report = report_text(journal, book=QQQ_AGGR_NAME)
    assert "Limit 0.60, not a fill. Fill pending." in report
    assert "The limit is not a fill." in report


def test_a_working_order_is_read_again_on_the_next_cycle():
    state = _state()
    payloads = {
        "exit-1": {"status": "SUBMITTED", "limit_price": "0.60"},
    }

    class Flip:
        def __init__(self):
            self.calls = 0

        def get_order_detail(self, account_id, client_order_id):
            self.calls += 1
            if self.calls == 1:
                return {"status": "SUBMITTED", "limit_price": "0.60"}
            return {"status": "FILLED", "avg_filled_price": "0.55", "limit_price": "0.60"}

    broker = _Broker(payloads)
    broker._trade.order_v3 = Flip()
    prepare_cash(state, broker, 2500.0, _now("14:40").date())
    assert state["orders"][0].get("fill") in (None, "")
    prepare_cash(state, broker, 2500.0, _now("14:45").date())
    assert state["orders"][0]["fill"] == pytest.approx(0.55)
    assert broker._trade.order_v3.calls == 2


def test_a_working_exit_is_repriced_only_after_the_wait():
    state = _state()
    state["orders"][0]["submitted_at"] = "2026-10-09T14:39:58-04:00"
    broker = _Broker({"exit-1": {"status": "SUBMITTED", "limit_price": "0.60"}})
    lines = []
    chase_exit_orders(state, broker, _now("14:40"), lines)
    assert broker.replaced == []
    assert broker.placed == []
    assert any("Fill pending" in line for line in lines)

    state["orders"][0]["submitted_at"] = "2026-10-09T14:34:56-04:00"
    lines = []
    chase_exit_orders(state, broker, _now("14:40"), lines)
    assert broker.placed == []
    assert broker.cancelled == []
    assert broker.replaced == [("exit-1", 3.0, 0.39)]
    assert state["orders"][0]["limit"] == "0.39"
    assert any("not a fill" in line for line in lines)


def test_a_cancelled_exit_is_resent_and_an_expired_contract_is_not():
    state = _state()
    broker = _Broker({"exit-1": {"status": "CANCELLED", "limit_price": "0.60"}})
    lines = []
    chase_exit_orders(state, broker, _now("14:40"), lines)
    assert broker.replaced == []
    assert len(broker.placed) == 1
    assert broker.placed[0]["side"] == "SELL"
    assert broker.placed[0]["position_intent"] == "SELL_TO_CLOSE"
    assert state["orders"][0]["status"] == "submitted"
    assert any("not a fill" in line for line in lines)

    later = _state()
    quiet = _Broker({"exit-1": {"status": "SUBMITTED", "limit_price": "0.60"}})
    lines = []
    chase_exit_orders(later, quiet, _now("10:00", "2026-10-12"), lines)
    assert quiet.placed == []
    assert quiet.replaced == []
    assert quiet.cancelled == []
    assert any("expiry has passed" in line for line in lines)


def test_the_flatten_window_walks_the_limit_down():
    state = _state()
    state["orders"][0]["submitted_at"] = "2026-10-09T14:39:50-04:00"
    state["orders"][0]["limit"] = "0.40"
    state["orders"][0]["sandbox_price"] = "0.40"
    broker = _Broker({"exit-1": {"status": "SUBMITTED", "limit_price": "0.40"}})
    broker.option_contract_quote = lambda symbol: {"bid": 0.40}
    chase_exit_orders(state, broker, _now("14:40"), [])
    assert broker.replaced[-1][2] == pytest.approx(0.39)
    assert broker.placed == []

    later = _state()
    later["orders"][0]["submitted_at"] = "2026-10-09T15:39:00-04:00"
    later["orders"][0]["limit"] = "2.00"
    floor = _Broker({"exit-1": {"status": "SUBMITTED", "limit_price": "2.00"}})
    chase_exit_orders(later, floor, _now("15:40"), [])
    assert floor.replaced[-1][2] == pytest.approx(0.01)
    assert floor.placed == []

    flat = _state()
    flat["orders"][0]["submitted_at"] = "2026-10-09T15:49:30-04:00"
    flat["orders"][0]["limit"] = "0.40"
    flat["orders"][0]["sandbox_price"] = "0.40"
    broker = _Broker({"exit-1": {"status": "SUBMITTED", "limit_price": "0.40"}})
    broker.option_contract_quote = lambda symbol: {"bid": 0.40}
    chase_exit_orders(flat, broker, _now("15:50"), [])
    assert broker.replaced[-1][2] == pytest.approx(0.01)
    assert broker.placed == []


def test_the_watch_exit_view_still_reprices_through_the_bid():
    from webull_bot.execution.forward_watch import _ExitView, _LivePrice

    state = _state()
    state["orders"][0]["submitted_at"] = "2026-10-09T14:34:56-04:00"
    inner = _Broker({"exit-1": {"status": "SUBMITTED", "limit_price": "0.60"}})
    view = _LivePrice(_ExitView(inner, {}), {})
    chase_exit_orders(state, view, _now("14:40"), [])
    assert inner.replaced == [("exit-1", 3.0, 0.39)]
    assert inner.placed == []


def test_a_rejected_modify_is_cancelled_and_replaced_and_the_body_is_logged():
    state = _state()
    state["orders"][0]["submitted_at"] = "2026-10-09T14:34:56-04:00"

    class Reject(_Broker):
        def replace_order(self, client_order_id, quantity, limit_price=None):
            self.replaced.append((client_order_id, quantity, limit_price))
            raise RuntimeError("INVALID_MODIFY app_secret=super-secret-value")

    broker = Reject({"exit-1": {"status": "SUBMITTED", "limit_price": "0.60"}})
    lines = []
    chase_exit_orders(state, broker, _now("14:40"), lines)
    text = "\n".join(lines)
    assert "INVALID_MODIFY" in text
    assert "super-secret-value" not in text
    assert "[redacted]" in text
    assert broker.cancelled == ["exit-1"]
    assert len(broker.placed) == 1
    assert broker.placed[0]["side"] == "SELL"
    assert broker.placed[0]["position_intent"] == "SELL_TO_CLOSE"
    assert state["orders"][0]["modify_rejected"] is True

    new_id = state["orders"][0]["id"]
    broker._trade.order_v3.payloads[new_id] = {"status": "SUBMITTED", "limit_price": state["orders"][0]["limit"]}
    state["orders"][0]["submitted_at"] = "2026-10-09T14:39:40-04:00"
    state["orders"][0]["broker_status"] = "working"
    before = len(broker.replaced)
    chase_exit_orders(state, broker, _now("14:40"), [])
    assert len(broker.replaced) == before
    assert len(broker.placed) == 2
    assert broker.cancelled[-1] == new_id


def test_a_working_market_sell_is_not_stepped(monkeypatch):
    monkeypatch.setenv("FORWARD_OPTION_MARKET", "1")
    state = _state()
    state["orders"][0]["submitted_at"] = "2026-10-09T14:34:56-04:00"
    state["orders"][0]["order_type"] = "MARKET"
    state["orders"][0]["quote_side"] = "bid"
    state["orders"][0]["quote_px"] = "0.4000"
    broker = _Broker({"exit-1": {"status": "SUBMITTED"}})
    lines = []
    chase_exit_orders(state, broker, _now("14:40"), lines)
    assert broker.replaced == []
    assert broker.placed == []
    assert any("MARKET, not a fill" in line for line in lines)


def test_an_expired_unsold_qqq_put_books_a_full_premium_loss(tmp_path):
    """QQQ closed at 746.04 on 2026-10-12, so the 745 put expired out of the money."""
    from webull_bot.execution.forward_cash import option_cash
    from webull_bot.execution.forward_trapdoor import NAME as TRAP_NAME
    from webull_bot.execution.forward_trapdoor import report_text as trap_report

    journal = Journal(tmp_path / "trapdoor.sqlite")
    journal.forward_save(TRAP_NAME, _trapdoor_put())
    broker = _Broker(
        {"exit-put": {"status": "CANCELLED", "limit_price": "0.25"}},
        holdings=[],
    )
    broker.underlying_close = lambda symbol, day: 746.039978
    lines = reconcile_book(journal, broker, TRAP_NAME, _now("10:00", "2026-10-13"))
    text = "\n".join(lines)
    assert "does not place" in text
    assert "No order was sent." in text
    assert "full premium loss" in text
    assert broker.placed == []
    assert broker.cancelled == []
    assert broker.replaced == []
    saved = journal.forward_load(TRAP_NAME)
    assert saved["positions"] == []
    assert saved["orders"][1]["fill"] == pytest.approx(0.0)
    assert saved["orders"][1]["settlement"] == "expiry"
    debit = option_cash(0.40, 1, sell=False)
    assert saved["signals"][0]["fill_pnl"] == pytest.approx(-debit)
    assert "Fill pending" not in text
    report = trap_report(journal)
    assert "Fill pending" not in report
    assert f"${saved['signals'][0]['fill_pnl']:.2f}" in report


def test_an_expired_unsold_put_books_intrinsic_when_it_finishes_in_the_money(tmp_path):
    from webull_bot.execution.forward_cash import option_cash
    from webull_bot.execution.forward_trapdoor import NAME as TRAP_NAME

    journal = Journal(tmp_path / "itm.sqlite")
    journal.forward_save(TRAP_NAME, _trapdoor_put())
    broker = _Broker({"exit-put": {"status": "CANCELLED", "limit_price": "0.25"}})
    broker.underlying_close = lambda symbol, day: 740.0
    reconcile_book(journal, broker, TRAP_NAME, _now("10:00", "2026-10-13"))
    saved = journal.forward_load(TRAP_NAME)
    assert saved["orders"][1]["fill"] == pytest.approx(5.0)
    debit = option_cash(0.40, 1, sell=False)
    assert saved["signals"][0]["fill_pnl"] == pytest.approx(500.0 - debit)
    assert broker.placed == []


def test_an_expired_contract_the_account_still_holds_is_not_closed(tmp_path):
    from webull_bot.execution.forward_trapdoor import NAME as TRAP_NAME

    journal = Journal(tmp_path / "held.sqlite")
    journal.forward_save(TRAP_NAME, _trapdoor_put())
    broker = _Broker(
        {"exit-put": {"status": "CANCELLED", "limit_price": "0.25"}},
        holdings=[{"symbol": "QQQ261012P00745000", "quantity": 1}],
    )
    broker.underlying_close = lambda symbol, day: 746.039978
    lines = reconcile_book(journal, broker, TRAP_NAME, _now("10:00", "2026-10-13"))
    assert any("still holds" in line for line in lines)
    saved = journal.forward_load(TRAP_NAME)
    assert saved["orders"][1].get("settlement") != "expiry"
    assert saved["orders"][1].get("fill") in (None, "")
    assert broker.placed == []


def _trapdoor_put() -> dict:
    return {
        "book": "neckline_trapdoor_qqq",
        "stake": 2500.0,
        "settled": 2459.96,
        "unsettled": [],
        "signals": [
            {
                "id": "qqq-trap",
                "status": "closed",
                "symbol": "QQQ",
                "direction": "short",
                "right": "put",
                "option_type": "PUT",
                "strike": 745.0,
                "expiry": "2026-10-12",
                "option_symbol": "QQQ261012P00745000",
                "qty": 1,
                "signal_time": "2026-10-12T14:00:00-04:00",
                "entry_time": "2026-10-12T14:05:00-04:00",
                "exit_time": "2026-10-12T15:34:55-04:00",
                "model_debit": 180.0,
                "model_credit": 25.0,
                "pnl": -155.0,
                "reason": "stop",
            }
        ],
        "orders": [
            {
                "key": "qqq-trap|entry",
                "id": "entry-put",
                "kind": "entry",
                "side": "BUY",
                "qty": "1",
                "symbol": "QQQ",
                "right": "PUT",
                "option_type": "PUT",
                "strike": 745.0,
                "expiry": "2026-10-12",
                "option_symbol": "QQQ261012P00745000",
                "status": "submitted",
                "broker_status": "filled",
                "limit": "0.42",
                "fill": 0.40,
                "submitted_at": "2026-10-12T14:05:00-04:00",
            },
            {
                "key": "qqq-trap|exit",
                "id": "exit-put",
                "kind": "exit",
                "side": "SELL",
                "qty": "1",
                "symbol": "QQQ",
                "right": "PUT",
                "option_type": "PUT",
                "strike": 745.0,
                "expiry": "2026-10-12",
                "option_symbol": "QQQ261012P00745000",
                "status": "submitted",
                "broker_status": "cancelled",
                "limit": "0.25",
                "fill": None,
                "submitted_at": "2026-10-12T15:34:55-04:00",
            },
        ],
        "fills": [
            {"id": "qqq-trap", "side": "BUY", "qty": "1", "right": "put", "price": "0.42", "fill": 0.40},
            {"id": "qqq-trap", "side": "SELL", "qty": "1", "right": "put", "price": "0.25", "fill": None},
        ],
        "exits": [
            {
                "id": "qqq-trap",
                "time": "2026-10-12T15:34:55-04:00",
                "right": "put",
                "reason": "stop",
                "underlying": 746.3,
                "pnl": -155.0,
            }
        ],
        "positions": [],
    }


def test_a_cancel_the_broker_refuses_does_not_send_a_second_sell_and_books_the_fill():
    state = _state()
    state["orders"][0]["submitted_at"] = "2026-10-09T14:34:56-04:00"
    calls = {"n": 0}

    class Block(_Broker):
        def replace_order(self, client_order_id, quantity, limit_price=None):
            self.replaced.append((client_order_id, quantity, limit_price))
            raise RuntimeError("OPENAPI_ORDER_CAN_NOT_BE_CANCEL")

    broker = Block({"exit-1": {"status": "SUBMITTED", "limit_price": "0.60"}})

    def detail(account_id, client_order_id):
        calls["n"] += 1
        if calls["n"] == 1:
            return {"status": "SUBMITTED", "limit_price": "0.60"}
        return {"status": "FILLED", "avg_filled_price": "0.55", "limit_price": "0.60"}

    broker._trade.order_v3.get_order_detail = detail
    lines = []
    chase_exit_orders(state, broker, _now("14:40"), lines)
    assert broker.placed == []
    assert state["orders"][0]["fill"] == pytest.approx(0.55)
    assert state["orders"][0]["id"] == "exit-1"
    assert any("No new sell" in line for line in lines)


def test_a_reverse_rejection_restores_the_working_sell_and_does_not_send_another():
    state = _state()
    state["orders"][0]["submitted_at"] = "2026-10-09T14:34:56-04:00"

    class Reverse(_Broker):
        def replace_order(self, client_order_id, quantity, limit_price=None):
            self.replaced.append((client_order_id, quantity, limit_price))
            raise RuntimeError("OPENAPI_PARAM_ERR")

        def place_option_order(self, payload):
            self.placed.append(payload)
            raise RuntimeError("OPENAPI_ORDER_NOT_SUPPORT_REVERSE_OPTION")

    broker = Reverse({"exit-1": {"status": "SUBMITTED", "limit_price": "0.60"}})
    lines = []
    chase_exit_orders(state, broker, _now("14:40"), lines)
    text = "\n".join(lines)
    assert "OPENAPI_PARAM_ERR" in text
    assert "OPENAPI_ORDER_NOT_SUPPORT_REVERSE_OPTION" in text
    assert state["orders"][0]["id"] == "exit-1"
    assert state["orders"][0]["reverse_blocked"] is True
    assert len(broker.placed) == 1
    before = len(broker.placed)
    chase_exit_orders(state, broker, _now("14:41"), lines)
    assert len(broker.placed) == before
    assert any("No second sell" in line for line in lines)


def test_nightly_prints_a_skipped_fill_and_cancels_only_the_blank_buy(tmp_path):
    from webull_bot.execution.forward_reconcile import _BLANK_TRIED, nightly_reconcile, reset_order_poll
    from webull_bot.execution.forward_vwap import QQQ_AGGR_1DTE_NAME, empty_state

    reset_order_poll()
    _BLANK_TRIED.clear()
    journal = Journal(tmp_path / "night.sqlite")
    state = empty_state()
    state["book"] = QQQ_AGGR_1DTE_NAME
    state["signals"] = [
        {
            "id": "qqq-1dte",
            "status": "skip",
            "skip": "unfilled",
            "reason": "unfilled",
            "symbol": "QQQ",
            "option_type": "PUT",
            "right": "put",
            "qty": 1,
            "strike": 742.0,
            "expiry": "2026-10-14",
        }
    ]
    state["orders"] = [
        {
            "key": "qqq-1dte|entry",
            "id": "qqq-1dte-buy",
            "kind": "entry",
            "side": "BUY",
            "qty": "1",
            "symbol": "QQQ",
            "right": "PUT",
            "option_type": "PUT",
            "status": "cancelled",
            "limit": "2.82",
            "strike": 742.0,
            "expiry": "2026-10-14",
        }
    ]
    state["positions"] = []
    journal.forward_save(QQQ_AGGR_1DTE_NAME, state)

    class Night(_Broker):
        def __init__(self):
            super().__init__({})
            self._trade.account_v2.get_account_position = lambda account_id: {
                "positions": [
                    {
                        "symbol": "QQQ",
                        "quantity": "3.0",
                        "cost_price": "0.77",
                        "option_type": "PUT",
                        "option_expire_date": "2026-10-13",
                    }
                ]
            }
            self._trade.order_v3.get_order_open = lambda **kwargs: [
                {
                    "client_order_id": "blank-1",
                    "side": "BUY",
                    "order_type": "MARKET",
                    "quantity": "0",
                    "symbol": "",
                    "status": "SUBMITTED",
                }
            ]
            self._trade.order_v3.get_order_detail = lambda account_id, client_order_id: {
                "status": "FILLED",
                "avg_filled_price": "2.82",
            }

    broker = Night()
    lines = nightly_reconcile(journal, broker, _now("16:10", "2026-10-13"))
    text = "\n".join(lines)
    assert "No order is placed" in text
    assert "skipped unfilled" in text
    assert "filled at 2.82" in text
    assert "Unexplained holding" in text
    assert "Cancelled blank order blank-1" in text
    assert broker.placed == []
    assert broker.cancelled == ["blank-1"]
    saved = journal.forward_load(QQQ_AGGR_1DTE_NAME)
    assert saved["signals"][0]["skip"] == "unfilled"


def test_a_rejected_option_order_logs_the_body():
    from webull_bot.execution.forward_vwap import _place

    class Fail:
        def place_option_order(self, payload):
            raise RuntimeError("OPENAPI_PARAM_ERR missing instrument")

    order = {"id": "flatten-1", "limit": "2.55"}
    lines = []
    sent = _place(
        Fail(),
        {"instrument_type": "OPTION", "order_type": "LIMIT", "client_order_id": "flatten-1"},
        order,
        lines,
        "exit",
    )
    text = "\n".join(lines)
    assert sent is False
    assert "OPENAPI_PARAM_ERR" in text
    assert "was rejected" in text
    assert order["error"]
    assert "not printed" not in text
