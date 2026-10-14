"""Shadow P&L for entries that expired, were cancelled, or stayed unfilled."""

import csv

from webull_bot.execution.forward_cash import option_cash
from webull_bot.execution.forward_missed import apply_missed_fills, daily_summary_line
from webull_bot.execution.forward_vwap import NAME, report_text
from webull_bot.journal.store import Journal

CONTRACT = "SPY261012P00667000"


def _state(status: str = "cancelled", skip: str = "unfilled") -> dict:
    return {
        "signals": [
            {
                "id": "spy-1000",
                "status": "skip",
                "skip": skip,
                "reason": skip,
                "direction": "short",
                "right": "put",
                "stop": 746.0,
                "target": 744.0,
                "qty": 1,
                "signal_time": "2026-10-12T09:45:00-04:00",
                "entry_time": "2026-10-12T10:00:00-04:00",
            }
        ],
        "orders": [
            {
                "key": "spy-1000|entry",
                "kind": "entry",
                "side": "BUY",
                "qty": "1",
                "right": "PUT",
                "status": status,
                "broker_status": status,
                "fill": None,
                "price_source": "webull",
                "sandbox_price": "0.8600",
                "option_symbol": CONTRACT,
                "submitted_at": "2026-10-12T10:00:00-04:00",
            }
        ],
        "fills": [],
        "exits": [],
        "positions": [],
    }


def _ticks(folder, rows):
    path = folder / "ticks_vwap_band_15m_20261012.csv"
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["timestamp", "book", "symbol", "underlying", "option_symbol", "bid", "ask"],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def test_a_cancelled_short_books_the_stop_bid_separate_from_fill_pnl(tmp_path):
    _ticks(
        tmp_path,
        [
            {
                "timestamp": "2026-10-12T10:00:00-04:00",
                "book": NAME,
                "symbol": "SPY",
                "underlying": "745.20",
                "option_symbol": CONTRACT,
                "bid": "0.80",
                "ask": "0.86",
            },
            {
                "timestamp": "2026-10-12T10:06:00-04:00",
                "book": NAME,
                "symbol": "SPY",
                "underlying": "746.10",
                "option_symbol": CONTRACT,
                "bid": "0.40",
                "ask": "0.46",
            },
        ],
    )
    state = _state()
    assert apply_missed_fills(state, NAME, tmp_path) is True
    row = state["missed_fills"][0]
    debit = option_cash(0.86, 1, sell=False)
    credit = option_cash(0.40, 1, sell=True)
    assert row["reason"] == "stop"
    assert row["ask"] == 0.86
    assert row["bid"] == 0.4
    assert row["missed_pnl"] == round(credit - debit, 4)
    assert state["signals"][0].get("fill_pnl") is None
    assert "missed-fill P&L" in daily_summary_line(state)
    assert f"${row['missed_pnl']:.2f}" in daily_summary_line(state)
    assert apply_missed_fills(state, NAME, tmp_path) is False


def test_an_expired_order_flattens_on_the_1545_bid(tmp_path):
    path = tmp_path / "ticks_vwap_band_15m_20261013.csv"
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["timestamp", "book", "symbol", "underlying", "option_symbol", "bid", "ask"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "timestamp": "2026-10-13T10:15:00-04:00",
                "book": NAME,
                "symbol": "SPY",
                "underlying": "670.00",
                "option_symbol": CONTRACT,
                "bid": "0.44",
                "ask": "0.50",
            }
        )
        writer.writerow(
            {
                "timestamp": "2026-10-13T15:45:00-04:00",
                "book": NAME,
                "symbol": "SPY",
                "underlying": "671.00",
                "option_symbol": CONTRACT,
                "bid": "0.22",
                "ask": "0.28",
            }
        )
    state = _state(status="expired", skip="expired")
    state["signals"][0]["stop"] = 680.0
    state["signals"][0]["target"] = 660.0
    state["orders"][0]["broker_status"] = "expired"
    state["orders"][0]["status"] = "expired"
    state["orders"][0]["sandbox_price"] = "0.5000"
    state["orders"][0]["submitted_at"] = "2026-10-13T10:15:00-04:00"
    assert apply_missed_fills(state, NAME, tmp_path) is True
    assert state["missed_fills"][0]["reason"] == "flat"
    assert state["missed_fills"][0]["bid"] == 0.22


def test_a_filled_order_is_not_a_missed_fill(tmp_path):
    state = _state()
    state["orders"][0]["fill"] = 0.8
    state["orders"][0]["broker_status"] = "filled"
    state["signals"][0]["status"] = "closed"
    state["signals"][0]["skip"] = ""
    state["signals"][0]["reason"] = "stop"
    assert apply_missed_fills(state, NAME, tmp_path) is False
    assert state.get("missed_fills") in (None, [])


def test_the_report_keeps_missed_fill_pnl_off_the_cash_mirror(tmp_path, monkeypatch):
    monkeypatch.setenv("FORWARD_QUOTE_DIR", str(tmp_path))
    _ticks(
        tmp_path,
        [
            {
                "timestamp": "2026-10-12T10:00:00-04:00",
                "book": NAME,
                "symbol": "SPY",
                "underlying": "745.20",
                "option_symbol": CONTRACT,
                "bid": "0.80",
                "ask": "0.86",
            },
            {
                "timestamp": "2026-10-12T10:06:00-04:00",
                "book": NAME,
                "symbol": "SPY",
                "underlying": "744.00",
                "option_symbol": CONTRACT,
                "bid": "1.20",
                "ask": "1.26",
            },
        ],
    )
    journal = Journal(tmp_path / "journal.sqlite")
    state = _state(status="unfilled", skip="unfilled")
    state["signals"][0]["target"] = 744.5
    journal.forward_save(NAME, state)
    text = report_text(journal, book=NAME)
    assert "Realized fill P&L $0.00." in text
    assert "missed-fill P&L" in text
    assert "Daily summary: missed-fill P&L" in text
    saved = journal.forward_load(NAME)
    assert saved["signals"][0].get("fill_pnl") is None
    assert saved["missed_fills"][0]["reason"] == "target"
    assert saved["settled"] != saved["missed_fills"][0]["missed_pnl"]


def test_no_quote_log_does_not_invent_a_pnl(tmp_path):
    state = _state()
    state["orders"][0]["price_source"] = "model"
    state["orders"][0]["sandbox_price"] = "0.8600"
    assert apply_missed_fills(state, NAME, tmp_path) is True
    assert state["missed_fills"][0]["missed_pnl"] is None
    assert daily_summary_line(state) == "Daily summary: missed-fill P&L waiting on the quote log."
