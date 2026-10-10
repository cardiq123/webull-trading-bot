"""The 5-second watch. No network and no orders leave this file."""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from webull_bot.cli import build_parser
from webull_bot.execution.forward_vwap import NAME, _manage_open, empty_state
from webull_bot.execution.forward_watch import (
    LATEST,
    EndpointBudget,
    BudgetExceeded,
    boundary_of,
    cycle_lock,
    full_cycle_due,
    rate_limited,
    run_watch,
)
from webull_bot.journal.store import Journal

NY = ZoneInfo("America/New_York")
DAY = "2024-01-03"


def _at(hhmm: str) -> datetime:
    return datetime.fromisoformat(f"{DAY}T{hhmm}:00").replace(tzinfo=NY)


class Broker:
    def __init__(self, fail_quote: bool = False):
        self.orders = []
        self.fail_quote = fail_quote

    def underlying_quote(self, symbol):
        if self.fail_quote:
            raise RuntimeError("snapshot down")
        return None

    def option_contract_quote(self, option_symbol):
        return {"bid": 1.0, "ask": 1.1}

    def place_option_order(self, payload):
        self.orders.append(payload)
        return {"client_order_id": payload["client_order_id"]}


def _position():
    return {
        "id": "sig-1",
        "direction": "long",
        "right": "call",
        "option_type": "CALL",
        "strike": 100.0,
        "model_strike": 100.0,
        "expiry": DAY,
        "option_symbol": "SPY240103C00100000",
        "signal_time": f"{DAY}T11:45:00-05:00",
        "fill_time": f"{DAY}T12:00:00-05:00",
        "entry_time": f"{DAY}T12:00:30-05:00",
        "entry": 100.0,
        "stop": 90.0,
        "target": 110.0,
        "iv": 0.20,
        "model_debit": 100.0,
        "qty": 1,
    }


def test_bar_close_is_three_seconds_past_the_boundary():
    assert full_cycle_due(_at("11:00").replace(second=3), None)
    assert not full_cycle_due(_at("11:00").replace(second=2), None)
    assert not full_cycle_due(_at("11:02"), boundary_of(_at("11:00")))
    assert full_cycle_due(_at("11:05").replace(second=3), boundary_of(_at("11:00")))


def test_budget_stays_under_the_sandbox_snapshot_cap_and_backs_off():
    from webull_bot.execution.forward_watch import REQUESTS_PER_MINUTE, snapshot_prices

    assert REQUESTS_PER_MINUTE == 15
    budget = EndpointBudget()
    for _ in range(15):
        budget.gate("option_snapshot")
    with pytest.raises(BudgetExceeded):
        budget.gate("option_snapshot")
    budget.gate("stock_snapshot")

    tight = EndpointBudget(cap=10)
    for _ in range(10):
        tight.gate("stock_snapshot")
    with pytest.raises(BudgetExceeded):
        tight.gate("stock_snapshot")
    delay = tight.penalize("option_snapshot")
    assert delay == 15.0
    assert tight.cooling("option_snapshot")
    assert rate_limited(RuntimeError("HTTP 429 Too Many Requests"))
    assert not rate_limited(RuntimeError("timeout"))

    class Market:
        def __init__(self):
            self.calls = []

        def get_snapshot(self, symbols, category):
            self.calls.append((list(symbols), category))
            return {"data": [{"symbol": item, "price": 500.0 + index} for index, item in enumerate(symbols)]}

    class Data:
        def __init__(self):
            self.market_data = Market()

    class QuoteBroker:
        def __init__(self):
            self._data = Data()

    broker = QuoteBroker()
    prices = snapshot_prices(broker, ["SPY", "QQQ"], EndpointBudget())
    assert broker._data.market_data.calls == [(["SPY", "QQQ"], "US_ETF")]
    assert prices == {"SPY": 500.0, "QQQ": 501.0}


def test_sdk_errors_are_one_line_and_do_not_repeat():
    import logging

    from webull_bot.execution.forward_watch import _SdkOneLine, quiet_sdk_errors

    log = logging.getLogger("webull.core.client")
    log.setLevel(logging.ERROR)
    log.filters[:] = [item for item in log.filters if not isinstance(item, _SdkOneLine)]
    quiet_sdk_errors()
    quiet_sdk_errors()
    seen = []

    class Capture(logging.Handler):
        def emit(self, record):
            seen.append(record.getMessage())

    handler = Capture(level=logging.ERROR)
    log.addHandler(handler)
    try:
        dump = (
            "ServerException occurred. Request:"
            "{'path': '/market-data/stocks/depths/list', 'category': 'US_OPTION'} "
            "HTTP 417 UNSUPPORTED_CATEGORY"
        )
        log.error(dump)
        log.error(dump)
        assert seen == ["Webull market data rejected the category (HTTP 417). The request was not logged."]
        assert "Request" not in seen[0]
        assert "depths" not in seen[0]
    finally:
        log.removeHandler(handler)


def test_the_cycle_lock_does_not_overlap(tmp_path):
    path = tmp_path / "cycle.lock"
    with cycle_lock(0, path) as outer:
        assert outer
        with cycle_lock(0, path) as inner:
            assert inner is False


def test_a_live_target_exits_and_a_quote_failure_does_not(tmp_path):
    from webull_bot.execution.forward_vwap import _activate, _ACTIVE

    journal = Journal(tmp_path / "watch.sqlite")
    state = empty_state()
    state["positions"] = [_position()]
    state["signals"] = [{"id": "sig-1", "status": "open"}]
    journal.forward_save(NAME, state)
    broker = Broker()
    broker.underlying_quote = lambda symbol: 120.0
    token = _activate(NAME)
    try:
        lines = []
        loaded = journal.forward_load(NAME)
        _manage_open(loaded, None, _at("12:05"), broker, lines, journal)
    finally:
        _ACTIVE.reset(token)
    assert any("reason target" in line for line in lines)
    assert journal.forward_load(NAME)["positions"] == []

    journal2 = Journal(tmp_path / "fail.sqlite")
    state["positions"] = [_position()]
    journal2.forward_save(NAME, state)
    broken = Broker(fail_quote=True)
    token = _activate(NAME)
    try:
        lines = []
        loaded = journal2.forward_load(NAME)
        _manage_open(loaded, None, _at("12:05"), broken, lines, journal2)
    finally:
        _ACTIVE.reset(token)
    assert journal2.forward_load(NAME)["positions"]
    assert broken.orders == []


def test_dry_run_fast_tick_does_not_connect(capsys):
    LATEST.clear()
    LATEST["full"] = boundary_of(_at("11:00"))
    parser = build_parser()
    args = parser.parse_args(
        ["forward-watch", NAME, "--dry-run", "--once", "--now", f"{DAY}T11:02:00"]
    )
    from webull_bot.config import load_config

    code = run_watch(load_config(args.config), args, [NAME])
    assert code == 0
    assert "Dry run: no snapshots, no orders" in capsys.readouterr().out
