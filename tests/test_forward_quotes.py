"""Quote logging stays off the order path. No network."""

import csv
import time
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pandas as pd

from webull_bot.execution.forward_quotes import (
    note_quotes,
    occ_symbol,
    one_contract_pnl,
    parse_snapshot,
    pick_expiry_ladder,
    report_lines,
)
from webull_bot.execution.forward_trapdoor import empty_state as trapdoor_empty
from webull_bot.execution.forward_vwap import empty_state as vwap_empty

NY = ZoneInfo("America/New_York")
DAY = date(2026, 10, 9)
STRIKE = 776
EXPIRES = (
    date(2026, 10, 9),
    date(2026, 10, 12),
    date(2026, 10, 13),
    date(2026, 10, 14),
)


def _occ(expiry: date) -> str:
    return occ_symbol("SPY", expiry, "call", STRIKE)


def _contracts() -> list[dict]:
    rows = []
    for expiry in EXPIRES:
        rows.append(
            {
                "option_symbol": _occ(expiry),
                "option_type": "CALL",
                "strike_price": str(STRIKE),
                "expiration_date": expiry.isoformat(),
            }
        )
    return rows


class _Market:
    def __init__(self, book: dict):
        self.book = book
        self.option_market_data = self
        self.instrument = self
        self.market_data = self
        self.snapshot_calls = []
        self.depth_calls = []
        self.stock_calls = []

    def list_option_contracts(self, **kwargs):
        return {"contracts": _contracts()}

    def get_option_snapshot(self, symbols, category):
        self.snapshot_calls.append((symbols, category))
        if isinstance(symbols, str):
            symbols = [item for item in symbols.split(",") if item]
        rows = []
        for symbol in symbols:
            row = self.book.get(symbol)
            if row is None:
                continue
            rows.append(dict(row, symbol=symbol))
        return {"data": rows}

    def get_snapshot(self, symbols, category):
        self.stock_calls.append((symbols, category))
        raise AssertionError("an option quote does not use the stock snapshot")

    def get_quotes(self, *args, **kwargs):
        self.depth_calls.append((args, kwargs))
        raise AssertionError("an option quote does not use stock depth")


class _Broker:
    def __init__(self, data):
        self._data = data
        self.sent = []

    def place_option_order(self, payload):
        self.sent.append(payload)


def _book(bids: dict[int, float], asks: dict[int, float]) -> dict:
    out = {}
    for offset, expiry in enumerate(EXPIRES):
        out[_occ(expiry)] = {
            "bid": bids[offset],
            "ask": asks[offset],
            "bid_size": 10 + offset,
            "ask_size": 20 + offset,
            "last": bids[offset],
        }
    return out


def _at(hhmm: str, day: str = "2026-10-09") -> datetime:
    return datetime.fromisoformat(f"{day}T{hhmm}:00").replace(tzinfo=NY)


def _signal(**extra) -> dict:
    row = {
        "id": "SPY|2026-10-09T09:45|long|extension",
        "status": "open",
        "direction": "long",
        "right": "call",
        "signal_time": "2026-10-09T09:45:00-04:00",
        "entry_time": "2026-10-09T10:00:00-04:00",
        "fill_time": "2026-10-09T10:00:00-04:00",
        "modeled_entry": 775.26,
        "entry": 775.63,
        "iv": 0.16,
        "model_ask": 0.54,
        "strike": STRIKE,
        "expiry": "2026-10-09",
        "stop": 774.56,
        "target": 775.96,
        "qty": 1,
    }
    row.update(extra)
    return row


def _position(signal: dict) -> dict:
    return {
        "id": signal["id"],
        "direction": "long",
        "right": "call",
        "option_type": "CALL",
        "strike": STRIKE,
        "expiry": "2026-10-09",
        "option_symbol": _occ(EXPIRES[0]),
        "entry_time": signal["entry_time"],
        "entry": signal["entry"],
        "stop": signal["stop"],
        "target": signal["target"],
        "iv": signal["iv"],
        "qty": signal["qty"],
    }


def _bars() -> pd.DataFrame:
    stamp = pd.Timestamp("2026-10-09 09:45", tz="America/New_York")
    return pd.DataFrame({"open": [774.0], "high": [775.0], "low": [773.5], "close": [774.5]}, index=[stamp])


def _use(tmp_path, monkeypatch) -> None:
    from webull_bot.execution.forward_quotes import clear_option_cache

    clear_option_cache()
    monkeypatch.setenv("FORWARD_QUOTE_DIR", str(tmp_path))


def test_expiry_ladder_uses_the_next_listed_day():
    friday = date(2026, 10, 9)
    listed = [friday, date(2026, 10, 12), date(2026, 10, 13), date(2026, 10, 14)]
    assert pick_expiry_ladder(listed, friday) == listed
    missing_monday = [friday, date(2026, 10, 13), date(2026, 10, 14), date(2026, 10, 15)]
    assert pick_expiry_ladder(missing_monday, friday) == missing_monday
    assert pick_expiry_ladder([friday], friday)[0] == friday
    assert pick_expiry_ladder([friday], friday)[1] is None


def test_parse_snapshot_and_one_contract_pnl():
    parsed = parse_snapshot(
        {
            "quotes": [
                {
                    "symbol": "SPY261009C00776000",
                    "bids": [{"price": "1.00", "size": "12"}],
                    "asks": [{"price": "1.10", "size": "8"}],
                    "last": "1.04",
                }
            ]
        }
    )
    assert parsed["bid"] == 1.0
    assert parsed["ask"] == 1.1
    assert parsed["bid_size"] == 12
    assert parsed["ask_size"] == 8
    assert parsed["mid"] == 1.05
    assert parsed["contract"] == "SPY261009C00776000"
    assert one_contract_pnl(1.05, 1.06) > 0
    assert one_contract_pnl(1.05, 0.40) < 0
    assert one_contract_pnl(None, 1.0) is None
    assert occ_symbol("spy", DAY, "put", 776) == "SPY261009P00776000"


def test_skipped_signal_logs_four_expiries_and_sends_nothing(tmp_path, monkeypatch):
    _use(tmp_path, monkeypatch)
    market = _Market(_book({0: 1.00, 1: 2.00, 2: 3.00, 3: 4.00}, {0: 1.05, 1: 2.10, 2: 3.20, 3: 4.30}))
    broker = _Broker(market)
    signal = _signal(status="skip", qty=3)
    state = {"signals": [signal], "orders": [], "positions": [], "exits": [], "settled": 2500.0, "quote_log": [], "shadow": []}
    lines = ["Already journaled 2026-10-09T10:00. No new orders."]
    changed = note_quotes(
        state,
        book="vwap_band_15m",
        symbol="SPY",
        now=_at("10:00"),
        underlying=775.63,
        broker=broker,
        lines=lines,
        bars=_bars(),
    )
    assert changed is True
    assert signal["status"] == "skip"
    assert signal["qty"] == 3
    assert state["settled"] == 2500.0
    assert state["shadow"] == []
    assert broker.sent == []
    offsets = {row["expiry_offset"] for row in state["quote_log"] if row["phase"] == "signal_close"}
    assert offsets == {0, 1, 2, 3}
    modeled = [row for row in state["quote_log"] if row["phase"] == "modeled_entry" and row["expiry_offset"] == 0]
    assert modeled[0]["model"] == 0.54
    assert modeled[0]["underlying"] == 775.26
    assert modeled[0]["ask"] == 1.05
    close = next(row for row in state["quote_log"] if row["phase"] == "signal_close" and row["expiry_offset"] == 0)
    assert close["underlying"] == 774.5
    path = tmp_path / "quotes_vwap_band_15m_20261009.csv"
    with path.open() as handle:
        rows = list(csv.DictReader(handle))
    assert {int(row["expiry_offset"]) for row in rows if row["phase"] == "modeled_entry"} == {0, 1, 2, 3}
    assert rows[0]["bid_size"] != ""
    assert "Already journaled" in lines[0]


def test_shadow_uses_each_expiry_bid_and_the_hold_variants(tmp_path, monkeypatch):
    _use(tmp_path, monkeypatch)
    entry_asks = {0: 1.05, 1: 2.10, 2: 3.20, 3: 4.30}
    market = _Market(_book({0: 1.00, 1: 2.00, 2: 3.00, 3: 4.00}, entry_asks))
    broker = _Broker(market)
    signal = _signal()
    state = {
        "signals": [signal],
        "orders": [],
        "positions": [_position(signal)],
        "exits": [],
        "settled": 1000.0,
        "quote_log": [],
        "shadow": [],
    }
    note_quotes(
        state,
        book="vwap_band_15m",
        symbol="SPY",
        now=_at("10:00"),
        underlying=775.63,
        broker=broker,
        lines=[],
        bars=_bars(),
    )
    assert signal["status"] == "open"
    assert state["settled"] == 1000.0
    assert broker.sent == []
    shadow = state["shadow"][0]
    assert shadow["entry_quote_late"] is False
    assert [leg["entry_ask"] for leg in shadow["legs"]] == [1.05, 2.10, 3.20, 4.30]
    assert len({leg["contract"] for leg in shadow["legs"]}) == 4

    state["positions"] = []
    state["exits"] = [
        {
            "id": signal["id"],
            "time": "2026-10-09T10:50:00-04:00",
            "right": "call",
            "reason": "target",
            "underlying": 776.95,
            "model_bid": 1.22,
        }
    ]
    market.book = _book({0: 1.40, 1: 1.80, 2: 2.50, 3: 3.10}, {0: 1.50, 1: 1.90, 2: 2.60, 3: 3.20})
    note_quotes(
        state,
        book="vwap_band_15m",
        symbol="SPY",
        now=_at("10:50"),
        underlying=776.95,
        broker=broker,
        lines=[],
        bars=_bars(),
    )
    assert signal["status"] == "open"
    assert state["settled"] == 1000.0
    bids = [leg["exit_bid"] for leg in shadow["legs"]]
    assert bids == [1.40, 1.80, 2.50, 3.10]
    assert len(set(bids)) == 4
    assert shadow["legs"][0]["pnl_exit"] == one_contract_pnl(1.05, 1.40)
    assert shadow["legs"][1]["pnl_exit"] == one_contract_pnl(2.10, 1.80)
    assert shadow["status"] == "closed"
    exit_mark = next(row for row in state["quote_log"] if row["phase"] == "exit")
    assert exit_mark["model"] == 1.22
    assert exit_mark["bid"] == 1.40

    market.book = _book({0: 0.90, 1: 1.70, 2: 2.40, 3: 2.90}, {0: 1.00, 1: 1.80, 2: 2.50, 3: 3.00})
    note_quotes(
        state,
        book="vwap_band_15m",
        symbol="SPY",
        now=_at("15:46"),
        underlying=776.10,
        broker=broker,
        lines=[],
        bars=_bars(),
    )
    assert [leg.get("flat_bid") for leg in shadow["legs"][1:]] == [1.70, 2.40, 2.90]
    assert shadow["legs"][1]["flat_bid"] != shadow["legs"][1]["exit_bid"]

    market.book = _book({0: 0.10, 1: 1.10, 2: 2.20, 3: 3.30}, {0: 0.20, 1: 1.20, 2: 2.30, 3: 3.40})
    note_quotes(
        state,
        book="vwap_band_15m",
        symbol="SPY",
        now=_at("09:50", "2026-10-12"),
        underlying=777.0,
        broker=broker,
        lines=[],
        bars=_bars(),
    )
    assert [leg.get("next_bid") for leg in shadow["legs"][1:]] == [1.10, 2.20, 3.30]
    text = "\n".join(report_lines(state))
    assert "Real P&L by expiry" in text
    assert "1DTE" in text
    assert "held to 15:45" in text
    assert "held to the next session" in text
    assert "Entry slippage versus the model" in text
    assert "Sandbox fill minus model" in text


def test_quote_failure_does_not_change_the_order(tmp_path, monkeypatch):
    _use(tmp_path, monkeypatch)

    class Boom:
        sent = []

        def __init__(self):
            self.instrument = self
            self.option_market_data = self
            self.market_data = self

        def list_option_contracts(self, **kwargs):
            raise RuntimeError("chain down")

        def get_option_snapshot(self, *args, **kwargs):
            raise RuntimeError("no option quote")

        def get_snapshot(self, *args, **kwargs):
            raise RuntimeError("no option quote")

        def get_quotes(self, *args, **kwargs):
            raise RuntimeError("no option quote")

        def place_option_order(self, payload):
            self.sent.append(payload)

    broker = _Broker(Boom())
    signal = _signal(qty=3)
    order = {"key": signal["id"] + "|entry", "id": "cid-1", "status": "submitted", "limit": "1.05", "qty": "3", "kind": "entry"}
    state = {
        "signals": [signal],
        "orders": [order],
        "positions": [_position(signal)],
        "exits": [],
        "settled": 2500.0,
        "quote_log": [],
        "shadow": [],
    }
    lines = []
    changed = note_quotes(
        state,
        book="vwap_band_15m",
        symbol="SPY",
        now=_at("10:00"),
        underlying=775.63,
        broker=broker,
        lines=lines,
        bars=_bars(),
    )
    assert changed is True
    assert signal["status"] == "open"
    assert signal["qty"] == 3
    assert state["positions"][0]["qty"] == 3
    assert state["settled"] == 2500.0
    assert order["status"] == "submitted"
    assert order["limit"] == "1.05"
    assert order["qty"] == "3"
    assert broker.sent == []
    assert state["quote_error"]
    assert lines[-1].startswith("Quote log:")


def test_timeout_is_stored_and_does_not_raise(tmp_path, monkeypatch):
    _use(tmp_path, monkeypatch)
    monkeypatch.setattr("webull_bot.execution.forward_quotes.CALL_TIMEOUT_S", 0.05)

    class Slow:
        def __init__(self):
            self.instrument = self
            self.option_market_data = self

        def list_option_contracts(self, **kwargs):
            return {"contracts": _contracts()}

        def get_option_snapshot(self, *args, **kwargs):
            time.sleep(1)

    signal = _signal(status="skip")
    state = {"signals": [signal], "orders": [], "positions": [], "exits": [], "settled": 1000.0, "quote_log": [], "shadow": []}
    changed = note_quotes(
        state,
        book="vwap_band_15m",
        symbol="SPY",
        now=_at("10:00"),
        underlying=775.63,
        broker=_Broker(Slow()),
        lines=[],
        bars=_bars(),
    )
    assert changed is True
    assert signal["status"] == "skip"
    assert signal.get("market") is None
    assert "timed out" in state["quote_error"]
    assert state["settled"] == 1000.0


def test_fill_lookup_does_not_change_order_status(tmp_path, monkeypatch):
    _use(tmp_path, monkeypatch)
    market = _Market(_book({0: 1.00, 1: 2.00, 2: 3.00, 3: 4.00}, {0: 1.05, 1: 2.10, 2: 3.20, 3: 4.30}))
    broker = _Broker(market)

    class OrderV3:
        def get_order_detail(self, account_id, client_order_id):
            return {"avg_filled_price": "1.05", "filled_time": "2026-10-09T10:05:30-04:00"}

    class Trade:
        order_v3 = OrderV3()

    broker._trade = Trade()
    broker.account_id = "sandbox"
    signal = _signal(status="skip")
    order = {
        "key": signal["id"] + "|entry",
        "id": "cid-9",
        "status": "submitted",
        "limit": "1.05",
        "qty": "1",
        "kind": "entry",
    }
    state = {"signals": [signal], "orders": [order], "positions": [], "exits": [], "settled": 1000.0, "quote_log": [], "shadow": []}
    note_quotes(
        state,
        book="vwap_band_15m",
        symbol="SPY",
        now=_at("10:06"),
        underlying=775.63,
        broker=broker,
        lines=[],
        bars=_bars(),
    )
    assert order["status"] == "submitted"
    assert order["limit"] == "1.05"
    assert order["fill"] == 1.05
    assert order["fill_time"] == "2026-10-09T10:05:30-04:00"
    assert broker.sent == []


def test_missing_data_client_does_not_write_a_csv(tmp_path, monkeypatch):
    _use(tmp_path, monkeypatch)
    signal = _signal()
    state = {"signals": [signal], "orders": [], "positions": [_position(signal)], "exits": [], "settled": 1000.0}
    lines = ["Already journaled 2026-10-09T10:00. No new orders."]
    changed = note_quotes(
        state,
        book="vwap_band_15m",
        symbol="SPY",
        now=_at("10:00"),
        underlying=775.63,
        broker=object(),
        lines=lines,
        bars=_bars(),
    )
    assert changed is False
    assert lines == ["Already journaled 2026-10-09T10:00. No new orders."]
    assert list(tmp_path.iterdir()) == []
    assert signal["status"] == "open"


def test_empty_state_keeps_quote_fields():
    for builder in (vwap_empty, trapdoor_empty):
        state = builder()
        assert state["shadow"] == []
        assert state["quote_log"] == []
        assert state["quote_error"] is None


def test_late_shadow_is_labeled(tmp_path, monkeypatch):
    _use(tmp_path, monkeypatch)
    market = _Market(_book({0: 1.00, 1: 2.00, 2: 3.00, 3: 4.00}, {0: 1.05, 1: 2.10, 2: 3.20, 3: 4.30}))
    broker = _Broker(market)
    signal = _signal(status="closed")
    state = {"signals": [signal], "orders": [], "positions": [], "exits": [], "settled": 1000.0, "quote_log": [], "shadow": []}
    note_quotes(
        state,
        book="vwap_band_15m",
        symbol="SPY",
        now=_at("11:07"),
        underlying=776.95,
        broker=broker,
        lines=[],
        bars=_bars(),
    )
    text = "\n".join(report_lines(state))
    assert "first live quote after this logger started" in text
    assert broker.sent == []


def _open_state():
    signal = _signal()
    return {
        "signals": [signal],
        "orders": [],
        "positions": [_position(signal)],
        "exits": [],
        "settled": 1000.0,
        "quote_log": [],
        "shadow": [],
    }


def test_open_contract_and_shadows_share_one_option_snapshot(tmp_path, monkeypatch):
    _use(tmp_path, monkeypatch)
    market = _Market(_book({0: 1.00, 1: 2.00, 2: 3.00, 3: 4.00}, {0: 1.05, 1: 2.10, 2: 3.20, 3: 4.30}))
    state = _open_state()
    note_quotes(
        state,
        book="vwap_band_15m",
        symbol="SPY",
        now=_at("10:00"),
        underlying=775.63,
        broker=_Broker(market),
        lines=[],
        bars=_bars(),
    )
    assert market.depth_calls == []
    assert market.stock_calls == []
    assert len(market.snapshot_calls) == 1
    symbols, category = market.snapshot_calls[0]
    assert category == "US_OPTION"
    assert isinstance(symbols, list)
    assert set(symbols) == {_occ(expiry) for expiry in EXPIRES}
    assert state["positions"][0]["qty"] == 1
    assert state["settled"] == 1000.0


def test_a_blank_option_snapshot_does_not_fall_through_to_depth(tmp_path, monkeypatch):
    _use(tmp_path, monkeypatch)
    blank = {symbol: {} for symbol in _book({0: 1, 1: 1, 2: 1, 3: 1}, {0: 1, 1: 1, 2: 1, 3: 1})}
    market = _Market(blank)
    state = _open_state()
    note_quotes(
        state,
        book="vwap_band_15m",
        symbol="SPY",
        now=_at("10:00"),
        underlying=775.63,
        broker=_Broker(market),
        lines=[],
        bars=_bars(),
    )
    assert market.depth_calls == []
    assert market.stock_calls == []
    assert len(market.snapshot_calls) == 1
    assert state["positions"]
    assert state["settled"] == 1000.0


def test_a_primed_cycle_quotes_the_ladder_once(tmp_path, monkeypatch):
    from webull_bot.execution.forward_quotes import prime_forward_quotes

    _use(tmp_path, monkeypatch)
    market = _Market(_book({0: 1.00, 1: 2.00, 2: 3.00, 3: 4.00}, {0: 1.05, 1: 2.10, 2: 3.20, 3: 4.30}))
    state = _open_state()

    class Journal:
        def forward_load(self, book):
            return state

    prime_forward_quotes(Journal(), _Broker(market), [("vwap_band_15m", "SPY", _bars())], _at("10:00"), True)
    note_quotes(
        state,
        book="vwap_band_15m",
        symbol="SPY",
        now=_at("10:00"),
        underlying=775.63,
        broker=_Broker(market),
        lines=[],
        bars=_bars(),
    )
    assert len(market.snapshot_calls) == 1
    assert market.depth_calls == []
    assert set(market.snapshot_calls[0][0]) == {_occ(expiry) for expiry in EXPIRES}
