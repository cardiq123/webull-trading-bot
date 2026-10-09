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
    state["orders"][0]["submitted_at"] = "2026-10-09T14:39:40-04:00"
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
    assert broker.replaced == [("exit-1", 3.0, 0.40)]
    assert state["orders"][0]["limit"] == "0.40"
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
    state["orders"][0]["submitted_at"] = "2026-10-09T15:49:30-04:00"
    state["orders"][0]["limit"] = "0.40"
    state["orders"][0]["sandbox_price"] = "0.40"
    broker = _Broker({"exit-1": {"status": "SUBMITTED", "limit_price": "0.40"}})
    broker.option_contract_quote = lambda symbol: {"bid": 0.40}
    chase_exit_orders(state, broker, _now("15:50"), [])
    assert broker.replaced[-1][2] == pytest.approx(0.39)
    assert broker.placed == []
