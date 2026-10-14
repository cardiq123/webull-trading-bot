"""Quote-touch paper fills stay in the sandbox and never double-book."""

import csv
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from webull_bot.execution.forward_cash import prepare_cash
from webull_bot.execution.forward_quote_touch import (
    apply_quote_touches,
    quote_touch_enabled,
    replay_day,
)
from webull_bot.execution.forward_reconcile import _book_mismatches, release_unheld_positions, reset_order_poll
from webull_bot.execution.forward_vwap import opened_on

NY = ZoneInfo("America/New_York")
DAY = date(2026, 10, 14)


def _at(hhmm: str) -> datetime:
    hour, minute = hhmm.split(":")
    return datetime(2026, 10, 14, int(hour), int(minute), tzinfo=NY)


class _Broker:
    def __init__(self, detail=None):
        self.detail = detail or {"kind": "working"}
        self.cancelled = []

    def order_detail(self, order_id):
        return self.detail

    def cancel_order(self, order_id):
        self.cancelled.append(order_id)


def _state(contract="QQQ261014P00742000", limit="1.00", ask_touch=True):
    return {
        "book": "vwap_band_15m_qqq_aggr",
        "stake": 2500.0,
        "settled": 2500.0,
        "unsettled": [],
        "signals": [
            {
                "id": "aggr-945",
                "status": "working",
                "symbol": "QQQ",
                "direction": "short",
                "right": "put",
                "option_symbol": contract,
                "qty": 3,
                "entry_time": "2026-10-14T09:46:00-04:00",
                "stop": 501.0,
                "target": 499.0,
                "entry": 500.0,
            }
        ],
        "orders": [
            {
                "key": "aggr-945|entry",
                "id": "buy-1",
                "kind": "entry",
                "side": "BUY",
                "qty": "3",
                "symbol": "QQQ",
                "option_symbol": contract,
                "status": "submitted",
                "broker_status": "working",
                "limit": limit,
                "submitted_at": "2026-10-14T09:46:00-04:00",
                "fill": None,
            }
        ],
        "positions": [
            {
                "id": "aggr-945",
                "symbol": "QQQ",
                "right": "put",
                "option_symbol": contract,
                "qty": 3,
                "entry_filled": False,
                "direction": "short",
                "stop": 501.0,
                "target": 499.0,
                "entry_time": "2026-10-14T09:46:00-04:00",
            }
        ],
        "exits": [],
        "fills": [],
    }


def _write_ticks(folder, rows):
    path = folder / "ticks_vwap_band_15m_qqq_aggr_20261014.csv"
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["timestamp", "book", "symbol", "underlying", "option_symbol", "bid", "ask", "bid_size", "ask_size"],
        )
        writer.writeheader()
        writer.writerows(rows)
    return path


def test_quote_touch_is_sandbox_only(monkeypatch):
    monkeypatch.setenv("WEBULL_ENV", "sandbox")
    monkeypatch.delenv("FORWARD_QUOTE_TOUCH", raising=False)
    assert quote_touch_enabled() is True
    monkeypatch.setenv("FORWARD_QUOTE_TOUCH", "0")
    assert quote_touch_enabled() is False
    monkeypatch.setenv("FORWARD_QUOTE_TOUCH", "1")
    monkeypatch.setenv("WEBULL_ENV", "production")
    assert quote_touch_enabled() is False
    monkeypatch.delenv("WEBULL_ENV", raising=False)
    assert quote_touch_enabled() is False


def test_ask_at_or_below_the_limit_books_one_quote_touch_fill(tmp_path, monkeypatch):
    monkeypatch.setenv("WEBULL_ENV", "sandbox")
    monkeypatch.setenv("FORWARD_QUOTE_DIR", str(tmp_path))
    contract = "QQQ261014P00742000"
    _write_ticks(
        tmp_path,
        [
            {
                "timestamp": "2026-10-14T09:47:00-04:00",
                "book": "vwap_band_15m_qqq_aggr",
                "symbol": "QQQ",
                "underlying": "500.20",
                "option_symbol": contract,
                "bid": "0.80",
                "ask": "0.90",
                "bid_size": "10",
                "ask_size": "10",
            }
        ],
    )
    state = _state(contract)
    broker = _Broker()
    lines = []
    assert apply_quote_touches(state, broker, _at("09:48"), 500.2, lines) is True
    assert apply_quote_touches(state, broker, _at("09:48"), 500.2, lines) is False
    order = state["orders"][0]
    assert order["fill"] == pytest.approx(1.0)
    assert order["fill_source"] == "quote_touch"
    assert broker.cancelled == ["buy-1"]
    assert state["positions"][0]["entry_filled"] is True
    assert state["signals"][0]["status"] == "open"
    assert opened_on(state, DAY) == 1
    assert len(state["positions"]) == 1
    prepare_cash(state, None, 2500.0, DAY)
    assert state["settled"] < 2500.0
    assert any("venue quote_touch" in line for line in lines)
    from webull_bot.execution.forward_quote_touch import venue_suffix

    assert venue_suffix(order) == " venue quote_touch"
    assert venue_suffix({"fill": 0.94, "fill_source": "order"}) == " venue sandbox"


def test_a_higher_ask_and_a_real_fill_are_not_paper_filled(tmp_path, monkeypatch):
    monkeypatch.setenv("WEBULL_ENV", "sandbox")
    monkeypatch.setenv("FORWARD_QUOTE_DIR", str(tmp_path))
    contract = "QQQ261014P00742000"
    _write_ticks(
        tmp_path,
        [
            {
                "timestamp": "2026-10-14T09:47:00-04:00",
                "book": "vwap_band_15m_qqq_aggr",
                "symbol": "QQQ",
                "underlying": "500.20",
                "option_symbol": contract,
                "bid": "1.20",
                "ask": "1.30",
                "bid_size": "1",
                "ask_size": "1",
            }
        ],
    )
    state = _state(contract, limit="1.00")
    broker = _Broker()
    assert apply_quote_touches(state, broker, _at("09:48"), 500.2, []) is False
    assert state["orders"][0]["fill"] is None
    assert broker.cancelled == []

    state["orders"][0]["fill"] = 0.97
    state["orders"][0]["fill_source"] = "order"
    assert apply_quote_touches(state, broker, _at("09:48"), 500.2, []) is False
    assert state["orders"][0]["fill"] == pytest.approx(0.97)
    assert state["orders"][0]["fill_source"] == "order"


def test_a_later_sandbox_fill_replaces_the_paper_fill(tmp_path, monkeypatch):
    monkeypatch.setenv("WEBULL_ENV", "sandbox")
    monkeypatch.setenv("FORWARD_QUOTE_DIR", str(tmp_path))
    contract = "QQQ261014P00742000"
    _write_ticks(
        tmp_path,
        [
            {
                "timestamp": "2026-10-14T09:47:00-04:00",
                "book": "vwap_band_15m_qqq_aggr",
                "symbol": "QQQ",
                "underlying": "500.20",
                "option_symbol": contract,
                "bid": "0.80",
                "ask": "0.90",
                "bid_size": "1",
                "ask_size": "1",
            }
        ],
    )
    state = _state(contract)
    broker = _Broker({"kind": "filled", "price": 0.94})
    apply_quote_touches(state, broker, _at("09:48"), 500.2, [])
    assert state["orders"][0]["fill_source"] == "quote_touch"
    apply_quote_touches(state, broker, _at("09:49"), 500.2, [])
    assert state["orders"][0]["fill"] == pytest.approx(0.94)
    assert state["orders"][0]["fill_source"] == "order"
    assert len([row for row in state["signals"] if row.get("status") in {"open", "closed"}]) == 1


def test_a_stuck_exit_fills_at_the_logged_bid(tmp_path, monkeypatch):
    monkeypatch.setenv("WEBULL_ENV", "sandbox")
    monkeypatch.setenv("FORWARD_QUOTE_DIR", str(tmp_path))
    contract = "QQQ261014P00742000"
    _write_ticks(
        tmp_path,
        [
            {
                "timestamp": "2026-10-14T10:05:00-04:00",
                "book": "vwap_band_15m_qqq_aggr",
                "symbol": "QQQ",
                "underlying": "498.50",
                "option_symbol": contract,
                "bid": "1.55",
                "ask": "1.60",
                "bid_size": "4",
                "ask_size": "4",
            }
        ],
    )
    state = _state(contract)
    state["orders"][0]["fill"] = 1.0
    state["orders"][0]["fill_source"] = "order"
    state["orders"][0]["status"] = "filled"
    state["positions"][0]["entry_filled"] = True
    state["signals"][0]["status"] = "open"
    state["orders"].append(
        {
            "key": "aggr-945|exit",
            "id": "sell-1",
            "kind": "exit",
            "side": "SELL",
            "qty": "3",
            "option_symbol": contract,
            "status": "submitted",
            "broker_status": "working",
            "limit": "1.40",
            "fill": None,
        }
    )
    broker = _Broker()
    assert apply_quote_touches(state, broker, _at("10:06"), 498.5, []) is True
    exit_order = state["orders"][1]
    assert exit_order["fill"] == pytest.approx(1.55)
    assert exit_order["fill_source"] == "quote_touch"
    assert broker.cancelled == ["sell-1"]
    assert state["positions"] == []
    prepare_cash(state, None, 2500.0, DAY)
    assert state["signals"][0]["fill_pnl"] is not None
    assert state["signals"][0]["fill_source"] == "mixed"


def test_quote_touch_positions_are_not_nightly_mismatches(monkeypatch):
    monkeypatch.setenv("WEBULL_ENV", "sandbox")
    state = _state()
    state["orders"][0]["fill"] = 1.0
    state["orders"][0]["fill_source"] = "quote_touch"
    state["orders"][0]["status"] = "filled"
    state["positions"][0]["entry_filled"] = True
    state["positions"][0]["fill_source"] = "quote_touch"
    state["signals"][0]["status"] = "open"
    assert _book_mismatches("vwap_band_15m_qqq_aggr", state, None, [], True) == []
    reset_order_poll()
    broker = _Broker()
    broker._trade = type("T", (), {})()
    lines = []
    release_unheld_positions(state, _EmptyAccount(), lines, _at("10:00"))
    release_unheld_positions(state, _EmptyAccount(), lines, _at("10:01"))
    assert state["positions"]
    assert state["signals"][0]["status"] == "open"


class _EmptyAccount:
    account_id = "sandbox-account"

    def __init__(self):
        self._trade = type("T", (), {"account_v2": self, "order_v3": self})()

    def get_account_position(self, account_id):
        return {"positions": []}

    def get_order_open(self, account_id, page_size=50):
        return {"orders": []}


def _entry(book, sid, when, limit, qty, contract):
    return {
        "key": f"{sid}|entry",
        "id": f"{sid}-buy",
        "kind": "entry",
        "side": "BUY",
        "qty": str(qty),
        "symbol": "QQQ" if book != "vwap_band_15m" else "SPY",
        "option_symbol": contract,
        "status": "cancelled",
        "broker_status": "cancelled",
        "limit": f"{limit:.2f}",
        "submitted_at": when,
        "fill": None,
    }


def _signal(sid, when, qty, contract, direction="short"):
    return {
        "id": sid,
        "status": "skip",
        "skip": "unfilled",
        "symbol": "SPY" if sid.startswith("spy") else "QQQ",
        "direction": direction,
        "right": "put",
        "option_symbol": contract,
        "qty": qty,
        "entry_time": when,
        "entry": 500.0,
        "stop": 501.0,
        "target": 499.0,
    }


def _tick(book, when, contract, underlying, bid, ask):
    return {
        "timestamp": when,
        "book": book,
        "symbol": "SPY" if book == "vwap_band_15m" else "QQQ",
        "underlying": f"{underlying:.2f}",
        "option_symbol": contract,
        "bid": f"{bid:.2f}",
        "ask": f"{ask:.2f}",
    }


def test_replay_20261014_books_the_ten_entries_without_double_counting():
    """The runner's ticks_*.csv are not in this environment.

    These ten rows are the session the log described: SPY at 9:45 and 12:00,
    QQQ Aggressive at 9:45, 11:00, 11:30, and 12:00, and 1DTE and Compound at
    9:45 and 12:00. Each ask is at or below the limit in the first minute.
    The exit bid is the next logged touch of the stop or the target.
    """
    specs = [
        ("vwap_band_15m", "spy-945", "09:46", 1.00, 0.90, 1.40, 1, "SPY261014P00720000", 498.0, "09:52"),
        ("vwap_band_15m", "spy-1200", "12:01", 0.80, 0.70, 0.40, 1, "SPY261014P00718000", 502.0, "12:06"),
        ("vwap_band_15m_qqq_aggr", "aggr-945", "09:46", 1.20, 1.10, 1.80, 3, "QQQ261014P00742000", 498.0, "09:52"),
        ("vwap_band_15m_qqq_aggr", "aggr-1100", "11:01", 1.00, 0.95, 1.30, 3, "QQQ261014P00743000", 498.0, "11:08"),
        ("vwap_band_15m_qqq_aggr", "aggr-1130", "11:31", 0.90, 0.85, 0.50, 3, "QQQ261014P00744000", 502.0, "11:40"),
        ("vwap_band_15m_qqq_aggr", "aggr-1200", "12:01", 1.10, 1.00, 1.50, 3, "QQQ261014P00745000", 498.0, "12:10"),
        ("vwap_band_15m_qqq_aggr_1dte", "dte-945", "09:46", 2.00, 1.90, 2.40, 1, "QQQ261015P00742000", 498.0, "09:52"),
        ("vwap_band_15m_qqq_aggr_1dte", "dte-1200", "12:01", 1.50, 1.40, 1.10, 1, "QQQ261015P00743000", 502.0, "12:06"),
        ("vwap_band_15m_qqq_compound", "cmp-945", "09:46", 1.00, 0.90, 1.25, 2, "QQQ261015P00744000", 498.0, "09:52"),
        ("vwap_band_15m_qqq_compound", "cmp-1200", "12:01", 0.75, 0.70, 0.95, 2, "QQQ261015P00745000", 498.0, "12:08"),
    ]
    states = {}
    ticks = []
    for book, sid, sent, limit, ask, bid, qty, contract, underlying, exited in specs:
        stamp = f"2026-10-14T{sent}:00-04:00"
        touch = _at(sent)
        ask_at = (touch.replace(minute=touch.minute + 1)).isoformat()
        exit_at = f"2026-10-14T{exited}:00-04:00"
        state = states.setdefault(
            book,
            {"book": book, "stake": 5000.0 if "compound" in book else 2500.0, "signals": [], "orders": [], "positions": [], "exits": [], "fills": []},
        )
        state["signals"].append(_signal(sid, stamp, qty, contract))
        state["orders"].append(_entry(book, sid, stamp, limit, qty, contract))
        ticks.append(_tick(book, ask_at, contract, 500.2, ask - 0.05, ask))
        ticks.append(_tick(book, exit_at, contract, underlying, bid, bid + 0.05))
    lines = replay_day(states, ticks, DAY)
    text = "\n".join(lines)
    assert "from 2 fills" in text
    assert "vwap_band_15m_qqq_aggr: quote-touch fill P&L" in text
    assert text.count("quote-touch fill P&L") == 4
    assert len([line for line in lines if "$" in line and " from " not in line]) == 10
    assert "No order was sent" in text
    summary = [line for line in lines if "quote-touch fill P&L" in line]
    assert len(summary) == 4
