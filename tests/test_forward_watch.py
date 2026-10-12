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
    assert 15.0 <= delay <= 15.0 * 1.25
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


def test_a_rate_limit_still_checks_the_stop_before_new_quotes(tmp_path, monkeypatch):
    from webull_bot.execution.forward_vwap import empty_state
    from webull_bot.execution.forward_watch import fast_tick

    journal = Journal(tmp_path / "cool.sqlite")
    state = empty_state()
    state["positions"] = [_position()]
    state["signals"] = [{"id": "sig-1", "status": "open"}]
    journal.forward_save(NAME, state)
    broker = Broker()
    budget = EndpointBudget()
    budget.penalize("stock_snapshot")
    budget.penalize("option_snapshot")
    budget.penalize("option_chain")
    broker._watch_budget = budget

    def boom(*args, **kwargs):
        raise AssertionError("new quotes waited")

    monkeypatch.setattr("webull_bot.execution.forward_quotes.prime_forward_quotes", boom)
    LATEST.clear()
    lines = fast_tick(journal, broker, _at("12:05"), {"SPY": 120.0}, [NAME])
    text = "\n".join(lines)
    assert "Rate limit backoff" in text
    assert "reason target" in text
    assert broker.orders[-1]["side"] == "SELL"


def test_four_hour_qqq_1dte_is_loaded_and_evaluated(tmp_path, monkeypatch):
    from pathlib import Path

    from webull_bot.execution.forward_watch import fast_tick

    script = Path(__file__).resolve().parents[1].joinpath("scripts", "vwap-watch.sh").read_text()
    assert "four_hour_qqq_1dte" in script
    seen = []
    monkeypatch.setattr(
        "webull_bot.execution.forward_four_hour._manage_open",
        lambda *args, **kwargs: seen.append("manage"),
    )
    monkeypatch.setattr(
        "webull_bot.execution.forward_four_hour._take_signals",
        lambda *args, **kwargs: seen.append("take"),
    )
    monkeypatch.setattr("webull_bot.execution.forward_quotes.prime_forward_quotes", lambda *args, **kwargs: None)
    journal = Journal(tmp_path / "hour.sqlite")
    LATEST.clear()
    lines = fast_tick(journal, Broker(), _at("12:05"), {"QQQ": 500.0}, ["four_hour_qqq_1dte"])
    assert seen == ["manage", "take"]
    assert any("Watching four_hour_qqq_1dte." in line for line in lines)


def test_cycle_timing_alerts_when_the_cycle_exceeds_a_minute():
    from webull_bot.execution.forward_watch import entry_lag_line, timing_lines

    quiet = timing_lines(0.01, 0.20, 0.05)
    assert quiet == ["Cycle timing: exits 0.01s, bars 0.20s, entries 0.05s, total 0.26s."]
    slow = timing_lines(1.0, 70.0, 1.0)
    assert any("Cycle alert" in line and "over 60s" in line for line in slow)
    lag = entry_lag_line(12.4, _at("13:35"))
    assert any("12.4s after the 13:35 ET bar close" in line for line in lag)
    assert any("share one bar cache" in line for line in lag)
    late = entry_lag_line(47.0, _at("13:35"))
    assert any("past 30s" in line for line in late)


def test_a_bar_close_checks_entries_after_exits_without_the_full_reload(tmp_path, monkeypatch):
    from webull_bot.execution import forward_watch as watch

    seen = []

    def refresh(config, now, names, broker=None):
        seen.append("bars")
        return ["Bar cache updated from the new 5-minute bars. Books share this cache."]

    def entries(config, names, now):
        seen.append(tuple(names))
        return ["Entry checks for 2 books share one bar cache and run together.", "QQQ Trapdoor"]

    monkeypatch.setattr(watch, "refresh_closed_bars", refresh)
    monkeypatch.setattr(watch, "dry_entry_checks", entries)
    watch.LATEST.clear()
    watch._REFRESH_THREAD = None
    lines = watch.watch_cycle(_cfg(tmp_path), None, ["vwap_band_15m", "neckline_trapdoor_qqq"], _at("13:35").replace(second=5), True)
    assert seen[0] == "bars"
    assert seen[1] == ("vwap_band_15m", "neckline_trapdoor_qqq")
    text = "\n".join(lines)
    assert "Cycle timing:" in text
    assert "13:35 ET bar close" in text
    assert "QQQ Trapdoor" in text


def test_a_slow_download_still_runs_the_entry_check(tmp_path, monkeypatch):
    from webull_bot.execution import forward_watch as watch

    def slow(*args, **kwargs):
        import time

        time.sleep(1.0)

    seen = []
    monkeypatch.setattr(watch, "BAR_REFRESH_TIMEOUT_S", 0.1)
    monkeypatch.setattr(watch, "_prime", slow)
    monkeypatch.setattr(watch, "dry_entry_checks", lambda *args, **kwargs: seen.append("entries") or ["entries"])
    watch.LATEST.clear()
    watch._REFRESH_THREAD = None
    lines = watch.watch_cycle(_cfg(tmp_path), None, ["neckline_trapdoor_qqq"], _at("13:35").replace(second=5), True)
    assert seen == ["entries"]
    assert any("timed out" in line for line in lines)
    assert any("Cycle timing:" in line for line in lines)
    thread = watch._REFRESH_THREAD
    if thread is not None:
        thread.join(2)


def test_books_share_one_tail_fetch(tmp_path, monkeypatch):
    from webull_bot.execution import forward_watch as watch

    calls = []

    class Provider:
        def __init__(self, *args, **kwargs):
            pass

        def append_recent(self, symbols, interval, now, days=3):
            calls.append((list(symbols), interval))
            return {}

    monkeypatch.setattr("webull_bot.data.yfinance_provider.YFinanceProvider", Provider)
    frame = _tiny()
    watch.LATEST.clear()
    watch.LATEST["bars5"] = {"SPY": frame, "QQQ": frame}
    watch.LATEST["bars15"] = {"SPY": frame, "QQQ": frame}
    watch._REFRESH_THREAD = None
    names = [
        "vwap_band_15m",
        "vwap_band_15m_qqq_aggr",
        "vwap_band_15m_qqq_aggr_1dte",
        "vwap_band_15m_qqq_compound",
        "neckline_trapdoor_qqq",
        "four_hour_qqq_1dte",
    ]
    lines = watch.refresh_closed_bars(_cfg(tmp_path), _at("13:35").replace(second=5), names, None)
    five = [item for item in calls if item[1] == "5m"]
    fifteen = [item for item in calls if item[1] == "15m"]
    assert len(five) == 1
    assert five[0][0] == ["SPY", "QQQ"]
    assert len(fifteen) == 1
    assert fifteen[0][0] == ["SPY", "QQQ"]
    assert any("share this cache" in line for line in lines)


def test_the_watch_does_not_call_the_full_history_cycle(tmp_path, monkeypatch, capsys):
    from webull_bot.execution import forward_watch as watch

    def boom(*args, **kwargs):
        raise AssertionError("full history cycle")

    monkeypatch.setattr("webull_bot.cli._forward_vwap", boom)
    monkeypatch.setattr(watch, "refresh_closed_bars", lambda *args, **kwargs: ["bars"])
    monkeypatch.setattr(
        watch,
        "dry_entry_checks",
        lambda *args, **kwargs: ["Entry checks for 6 books share one bar cache and run together."],
    )
    watch.LATEST.clear()
    watch._REFRESH_THREAD = None
    code = watch.run_watch(
        _cfg(tmp_path),
        build_parser().parse_args(
            ["forward-watch", "neckline_trapdoor_qqq", "--dry-run", "--once", "--now", f"{DAY}T13:35:05"]
        ),
        ["neckline_trapdoor_qqq"],
    )
    assert code == 0
    assert "Cycle timing:" in capsys.readouterr().out


def _cfg(root):
    class Config:
        def get(self, *keys, default=None):
            if keys == ("journal", "path"):
                return str(root / "journal.sqlite")
            if keys == ("data", "cache_dir"):
                return str(root / "cache")
            return default

    return Config()


def _tiny():
    import pandas as pd

    stamp = pd.Timestamp("2026-10-12 13:30", tz="America/New_York")
    return pd.DataFrame(
        [(100.0, 101.0, 99.0, 100.5, 1000.0)],
        columns=["open", "high", "low", "close", "volume"],
        index=pd.DatetimeIndex([stamp]),
    )


def test_option_chain_shares_one_fetch_and_backs_off(monkeypatch):
    from datetime import date

    from webull_bot.execution.forward_quotes import _list_contracts
    from webull_bot.execution.forward_watch import BudgetExceeded, guard_market_data

    calls = []

    class Client:
        def __init__(self):
            self.instrument = self

        def list_option_contracts(self, **kwargs):
            calls.append(kwargs["underlying_symbols"])
            return {"contracts": [{"option_symbol": "QQQ", "option_type": "PUT", "expiration_date": "2026-10-13"}]}

    client = Client()
    day = date(2026, 10, 12)
    _list_contracts(client, "QQQ", "PUT", 500.0, day)
    _list_contracts(client, "QQQ", "PUT", 501.0, day)
    assert calls == ["QQQ"]

    class Instrument:
        def __init__(self):
            self.calls = 0

        def list_option_contracts(self, **kwargs):
            self.calls += 1
            raise RuntimeError("HTTP 429 Too Many Requests")

    class Data:
        def __init__(self):
            self.instrument = Instrument()

    broker = type("Broker", (), {})()
    broker._data = Data()
    budget = guard_market_data(broker)
    with pytest.raises(RuntimeError):
        broker._data.instrument.list_option_contracts()
    assert budget.cooling("option_chain")
    with pytest.raises(BudgetExceeded):
        broker._data.instrument.list_option_contracts()
    assert broker._data.instrument.calls == 1
