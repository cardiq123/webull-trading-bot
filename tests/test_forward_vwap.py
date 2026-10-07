"""Sandbox forward test of the frozen 2 SD VWAP continuation. No network."""

import inspect
from datetime import date, datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from webull_bot.broker.webull import WebullBroker
from webull_bot.chart_reads.vwap_band import walk_exit
from webull_bot.cli import build_parser, refuse_if_forward_only
from webull_bot.config import load_config
from webull_bot.execution.forward_vwap import (
    NAME,
    SKIPS_EVENT_DAYS,
    data_problems,
    in_forward_window,
    plan_day,
    report_text,
    run_cycle,
)
from webull_bot.journal.store import Journal
from webull_bot.strategies.registry import all_strategies, strategy_by_name

NY = ZoneInfo("America/New_York")
DAY = "2024-01-03"
IV = {date(2024, 1, 3): (20.0, "VIX1D")}


def _at(hhmm: str, day: str = DAY) -> datetime:
    return datetime.fromisoformat(f"{day}T{hhmm}:00").replace(tzinfo=NY)


def _fifteen(rows: list[tuple], day: str = DAY) -> pd.DataFrame:
    stamps = []
    cursor = pd.Timestamp(f"{day} 09:30", tz=NY)
    for _row in rows:
        stamps.append(cursor)
        cursor += pd.Timedelta(minutes=15)
    return pd.DataFrame(rows, columns=["open", "high", "low", "close", "volume"], index=pd.DatetimeIndex(stamps))


def _quiet(n: int = 8) -> list[tuple]:
    rows = []
    for i in range(n):
        price = 100.0 + (0.4 if i % 2 == 0 else -0.2)
        rows.append((price, price + 0.05, price - 0.05, price, 1000.0))
    return rows


def _pad(rows: list[tuple], price: float = 130.0) -> pd.DataFrame:
    while len(rows) < 26:
        rows.append((price, price + 0.4, price - 0.4, price + 0.2, 1000.0))
    return _fifteen(rows[:26])


def _long_day() -> pd.DataFrame:
    rows = _quiet()
    rows.append((100.0, 130.0, 100.0, 130.0, 1000.0))
    return _pad(rows, 130.0)


def _two_day() -> pd.DataFrame:
    rows = _quiet()
    rows.append((100.0, 130.0, 100.0, 130.0, 1000.0))
    rows.append((130.0, 130.4, 129.6, 130.2, 1000.0))
    rows.append((110.0, 111.0, 109.0, 110.0, 1000.0))
    rows.append((110.0, 111.0, 109.0, 110.0, 1000.0))
    rows.append((110.0, 160.0, 110.0, 155.0, 1000.0))
    return _pad(rows, 120.0)


def _short_day() -> pd.DataFrame:
    rows = _quiet()
    rows.append((100.0, 100.0, 70.0, 70.0, 1000.0))
    return _pad(rows, 70.0)


def _five(day: str = DAY, special: dict | None = None, late: tuple | None = None) -> pd.DataFrame:
    special = special or {}
    stamps = pd.date_range(f"{day} 09:30", f"{day} 15:55", freq="5min", tz=NY)
    rows = []
    for stamp in stamps:
        key = stamp.strftime("%H:%M")
        if key in special:
            rows.append(special[key])
        elif stamp.time() >= datetime.strptime("11:45", "%H:%M").time():
            rows.append(late or (130.0, 130.4, 129.6, 130.2, 1000.0))
        else:
            rows.append((100.0, 100.2, 99.9, 100.0, 1000.0))
    return pd.DataFrame(rows, columns=["open", "high", "low", "close", "volume"], index=stamps)


class Broker:
    def __init__(self, ask: float = 2.50, bid: float = 1.10, fail: bool = False):
        self.orders = []
        self.ask = ask
        self.bid = bid
        self.fail = fail

    def option_zero_dte_quote(self, symbol, option_type, spot, as_of):
        return {
            "ask": self.ask,
            "bid": self.bid,
            "strike": 130.0,
            "expiry": DAY,
            "option_symbol": "SPY240103C00130000",
            "option_type": option_type,
        }

    def option_contract_quote(self, option_symbol):
        return {"ask": self.ask, "bid": self.bid}

    def place_option_order(self, payload):
        if self.fail:
            raise RuntimeError("super-secret-value")
        self.orders.append(payload)
        return {"client_order_id": payload["client_order_id"]}


def _cycle(journal, bars15, bars5, hhmm, broker=None, dry_run=False, iv=None, special=None, late=None):
    return run_cycle(
        journal=journal,
        bars15=bars15,
        bars5=bars5 if bars5 is not None else _five(special=special, late=late),
        now=_at(hhmm),
        iv_points=IV if iv is None else iv,
        broker=broker,
        dry_run=dry_run,
    )


def test_window_and_the_book_stays_off_the_live_list():
    assert in_forward_window(_at("09:50"))
    assert in_forward_window(_at("15:50"))
    assert not in_forward_window(_at("09:40"))
    assert not in_forward_window(_at("15:55"))
    assert not in_forward_window(_at("10:20", "2024-01-06"))
    assert SKIPS_EVENT_DAYS is False
    assert "event" not in inspect.signature(plan_day).parameters
    assert NAME not in [item.name for item in all_strategies()]
    with pytest.raises(KeyError, match="not in the paper or live book"):
        strategy_by_name(NAME)
    with pytest.raises(SystemExit, match="allow_unproven_strategies does not enable it"):
        refuse_if_forward_only([NAME])
    with pytest.raises(SystemExit, match="Live trading stays off"):
        refuse_if_forward_only(["dual_momentum", NAME])
    parser = build_parser()
    args = parser.parse_args(["forward-test", NAME, "--dry-run", "--now", f"{DAY}T11:50:00"])
    assert args.strategy == NAME
    assert args.dry_run is True
    report = parser.parse_args(["forward-report", NAME])
    assert report.strategy == NAME
    source = inspect.getsource(WebullBroker.option_atm_quote)
    assert "FORWARD_DTE" in source
    assert "FORWARD_DTE" not in inspect.getsource(WebullBroker.option_zero_dte_quote)


def test_idle_and_stale_data_place_nothing(tmp_path):
    journal = Journal(tmp_path / "journal.sqlite")
    broker = Broker()
    idle = _cycle(journal, _long_day(), _five(), "09:40", broker=broker, dry_run=False)
    assert "Outside the 09:50-15:50 ET window" in idle[0]
    assert broker.orders == []
    stale = _cycle(journal, pd.DataFrame(), pd.DataFrame(), "11:50", broker=broker, dry_run=False)
    assert "stale" in stale[-1]
    assert "No orders" in stale[-1]
    assert broker.orders == []
    assert journal.forward_load(NAME) is None
    assert data_problems(_long_day().iloc[:2], _five(), _at("11:50"))


def test_dry_run_replays_the_rule_and_does_not_write(tmp_path, monkeypatch):
    monkeypatch.setenv("WEBULL_APP_SECRET", "super-secret-value")
    journal = Journal(tmp_path / "journal.sqlite")
    journal.forward_save(NAME, {"signals": [{"id": "keep"}]})
    broker = Broker()
    lines = _cycle(journal, _long_day(), _five(), "11:50", broker=broker, dry_run=True)
    text = "\n".join(lines)
    assert "super-secret-value" not in text
    assert "Dry run" in text
    assert "still open" in text
    assert "not sent" in text
    assert "CPI, NFP, and FOMC days are not skipped" in text
    assert broker.orders == []
    assert journal.forward_load(NAME) == {"signals": [{"id": "keep"}]}
    events = plan_day(bars15=_long_day(), bars5=_five(), now=_at("11:50"), iv_points=IV)
    assert len(events) == 1
    event = events[0]
    assert event["direction"] == "long"
    assert event["status"] == "open"
    assert event["entry"] == 130.0
    assert event["stop"] == pytest.approx(99.99)
    assert event["target"] == pytest.approx(160.01)
    assert event["mode"] == "extension"


def test_stop_wins_on_one_five_minute_bar_and_a_target_can_print_first():
    both = {"11:45": (130.0, 170.0, 90.0, 130.0, 1000.0)}
    stopped = plan_day(bars15=_long_day(), bars5=_five(special=both), now=_at("11:50"), iv_points=IV)
    assert stopped[0]["reason"] == "stop"
    assert stopped[0]["exit"] == pytest.approx(99.99)

    early = {"11:45": (130.0, 170.0, 129.6, 160.0, 1000.0), "11:55": (130.0, 131.0, 90.0, 100.0, 1000.0)}
    bars15 = _long_day()
    fill = bars15.index[9]
    bars15.loc[fill, ["open", "high", "low", "close"]] = [130.0, 170.0, 90.0, 130.0]
    targeted = plan_day(bars15=bars15, bars5=_five(special=early), now=_at("11:50"), iv_points=IV)
    assert targeted[0]["reason"] == "target"
    assert targeted[0]["exit"] == pytest.approx(160.01)
    session = bars15.iloc[9:]
    reason, _price, _when = walk_exit(session, 0, "long", 99.99, 160.01)
    assert reason == "stop"


def test_flat_uses_the_1545_open():
    special = {"15:45": (131.0, 180.0, 129.0, 179.0, 1000.0)}
    events = plan_day(bars15=_long_day(), bars5=_five(special=special), now=_at("15:50"), iv_points=IV)
    assert events[0]["reason"] == "flat"
    assert events[0]["exit"] == pytest.approx(131.0)
    assert "15:45" in events[0]["exit_time"]


def test_one_position_iv_premium_and_the_short():
    two = plan_day(bars15=_two_day(), bars5=_five(), now=_at("13:00"), iv_points=IV)
    assert two[0]["status"] == "open"
    assert two[1]["skip"] == "overlap"
    missing = plan_day(bars15=_long_day(), bars5=_five(), now=_at("11:50"), iv_points={})
    assert missing[0]["skip"] == "iv"
    poor = plan_day(bars15=_long_day(), bars5=_five(), now=_at("11:50"), iv_points=IV, settled=10.0)
    assert poor[0]["skip"] == "premium"
    short = plan_day(bars15=_short_day(), bars5=_five(late=(70.0, 70.4, 69.6, 70.1, 1000.0)), now=_at("11:50"), iv_points=IV)
    assert short[0]["direction"] == "short"
    assert short[0]["option_type"] == "PUT"
    assert short[0]["stop"] == pytest.approx(100.01)
    assert short[0]["status"] == "open"


def test_real_cycle_buys_once_and_the_second_signal_is_skipped(tmp_path, monkeypatch):
    monkeypatch.setenv("WEBULL_APP_SECRET", "super-secret-value")
    journal = Journal(tmp_path / "journal.sqlite")
    broker = Broker()
    bars15 = _two_day()
    bars5 = _five()
    first = _cycle(journal, bars15, bars5, "11:50", broker=broker)
    text = "\n".join(first)
    assert "super-secret-value" not in text
    assert len(broker.orders) == 1
    order = broker.orders[0]
    assert order["side"] == "BUY"
    assert order["quantity"] == "1"
    assert order["legs"][0]["option_type"] == "CALL"
    assert order["position_intent"] == "BUY_TO_OPEN"
    assert order["limit_price"] == "2.50"
    assert order["order_type"] == "LIMIT"
    assert "Sandbox ask" in text or "Sandbox ask".lower() in text.lower()
    assert "Model ask" in text
    again = _cycle(journal, bars15, bars5, "11:50", broker=broker)
    assert "Already journaled" in again[-1]
    assert len(broker.orders) == 1
    later = _cycle(journal, bars15, bars5, "12:50", broker=broker)
    assert any("one position already open" in line for line in later)
    assert len(broker.orders) == 1
    saved = journal.forward_load(NAME)
    assert saved["positions"]
    assert saved["orders"][0]["price_source"] == "webull"
    assert "super-secret-value" not in str(saved)


def test_the_bot_sells_at_the_stop_and_flattens(tmp_path):
    journal = Journal(tmp_path / "stop.sqlite")
    broker = Broker()
    bars15 = _long_day()
    calm = _five()
    _cycle(journal, bars15, calm, "11:50", broker=broker)
    stopped = _five(special={"12:00": (130.0, 130.4, 90.0, 100.0, 1000.0)})
    lines = _cycle(journal, bars15, stopped, "12:05", broker=broker)
    assert any("reason stop" in line for line in lines)
    assert len(broker.orders) == 2
    sell = broker.orders[1]
    assert sell["side"] == "SELL"
    assert sell["position_intent"] == "SELL_TO_CLOSE"
    assert sell["limit_price"] == "1.10"
    assert journal.forward_load(NAME)["positions"] == []

    flat_journal = Journal(tmp_path / "flat.sqlite")
    flat_broker = Broker()
    _cycle(flat_journal, bars15, calm, "11:50", broker=flat_broker)
    flat_bars = _five(special={"15:45": (131.0, 180.0, 129.0, 179.0, 1000.0)})
    flat_lines = _cycle(flat_journal, bars15, flat_bars, "15:50", broker=flat_broker)
    assert any("reason flat" in line for line in flat_lines)
    assert flat_broker.orders[-1]["side"] == "SELL"
    assert "15:45" in "\n".join(flat_lines)
    report = report_text(flat_journal)
    assert NAME in report
    assert "reason flat" in report
    assert "model" in report


def test_a_rejected_order_does_not_print_the_exception(tmp_path, monkeypatch):
    monkeypatch.setenv("WEBULL_APP_KEY", "super-secret-value")
    journal = Journal(tmp_path / "journal.sqlite")
    broker = Broker(fail=True)
    lines = _cycle(journal, _long_day(), _five(), "11:50", broker=broker)
    text = "\n".join(lines)
    assert "rejected" in text
    assert "super-secret-value" not in text
    assert broker.orders == []


def test_cli_dry_run_does_not_connect(monkeypatch):
    import webull_bot.broker.webull as broker_mod
    import webull_bot.data.yfinance_provider as provider_mod
    import webull_bot.journal.store as store_mod

    def boom(*_args, **_kwargs):
        raise AssertionError("dry-run connected")

    monkeypatch.setattr(broker_mod, "WebullBroker", boom)

    class Provider:
        def __init__(self, *_args, **_kwargs):
            pass

        def history(self, symbols, start, end, interval="1d"):
            if interval == "15m":
                return {"SPY": _long_day()}
            if interval == "5m":
                return {"SPY": _five()}
            index = pd.to_datetime(["2024-01-02", "2024-01-03"])
            frame = pd.DataFrame({"close": [18.0, 19.0]}, index=index)
            return {"^VIX": frame, "^VIX1D": frame.copy()}

    monkeypatch.setattr(provider_mod, "YFinanceProvider", Provider)
    saved = []

    class Memory:
        def __init__(self, path):
            self.path = path

        def forward_load(self, name):
            return None

        def forward_save(self, name, payload):
            saved.append(payload)

    monkeypatch.setattr(store_mod, "Journal", Memory)
    from webull_bot.cli import _forward_vwap

    args = SimpleNamespace(strategy=NAME, dry_run=True, now=f"{DAY}T11:50:00", config="config/default.yaml")
    assert _forward_vwap(load_config("config/default.yaml"), args) == 0
    assert saved == []
    live = SimpleNamespace(strategy=NAME, dry_run=False, now=f"{DAY}T11:50:00", config="config/default.yaml")
    monkeypatch.delenv("WEBULL_ENV", raising=False)
    with pytest.raises(SystemExit, match="WEBULL_ENV=sandbox"):
        _forward_vwap(load_config("config/default.yaml"), live)


def test_a_late_cycle_enters_inside_the_bracket_and_ignores_the_earlier_stop(tmp_path):
    """The 11:45 bar already traded the stop. The 11:52 price is back inside."""
    journal = Journal(tmp_path / "late.sqlite")
    broker = Broker()
    bars5 = _five(
        special={
            "11:45": (130.0, 170.0, 90.0, 130.0, 1000.0),
            "11:50": (130.0, 131.0, 90.0, 130.0, 1000.0),
            "12:00": (130.0, 170.0, 129.0, 160.0, 1000.0),
        }
    )
    lines = _cycle(journal, _long_day(), bars5, "11:52", broker=broker)
    text = "\n".join(lines)
    assert "no longer between" not in text
    assert "already traded" not in text
    assert len(broker.orders) == 1
    assert broker.orders[0]["side"] == "BUY"
    saved = journal.forward_load(NAME)
    position = saved["positions"][0]
    assert position["modeled_entry"] == pytest.approx(130.0)
    assert position["entry"] == pytest.approx(130.0)
    assert "11:45" in position["fill_time"]
    assert "11:52" in position["entry_time"]
    assert saved["fills"][0]["modeled_entry"] == pytest.approx(130.0)
    later = _cycle(journal, _long_day(), bars5, "12:05", broker=broker)
    assert any("reason target" in line for line in later)
    assert not any("reason stop" in line for line in later)
    assert journal.forward_load(NAME)["positions"] == []


def test_a_price_through_the_stop_is_skipped_once(tmp_path):
    journal = Journal(tmp_path / "out.sqlite")
    broker = Broker()
    bars5 = _five(special={"11:50": (90.0, 91.0, 89.0, 90.0, 1000.0)})
    lines = _cycle(journal, _long_day(), bars5, "11:52", broker=broker)
    text = "\n".join(lines)
    assert "no longer between the stop" in text
    assert broker.orders == []
    saved = journal.forward_load(NAME)
    assert saved["signals"][0]["skip"] == "outside"
    assert saved["signals"][0]["modeled_entry"] == pytest.approx(130.0)
    again = _cycle(journal, _long_day(), _five(), "11:57", broker=broker)
    assert any("already journaled" in line for line in again)
    assert broker.orders == []


def test_the_signal_does_not_wait_for_the_next_fifteen_minute_bar(tmp_path):
    journal = Journal(tmp_path / "early.sqlite")
    broker = Broker()
    bars15 = _long_day().iloc[:9]
    lines = _cycle(journal, bars15, _five(), "11:47", broker=broker)
    assert len(broker.orders) == 1
    assert "waiting on the next open" not in "\n".join(lines)
    position = journal.forward_load(NAME)["positions"][0]
    assert position["entry"] == pytest.approx(130.0)
    assert position["modeled_entry"] == pytest.approx(130.0)
    assert position["target"] == pytest.approx(160.01)
    assert "11:47" in position["entry_time"]


def test_the_replay_records_the_modeled_open_beside_the_actual_entry():
    events = plan_day(bars15=_long_day(), bars5=_five(), now=_at("11:50"), iv_points=IV)
    assert events[0]["status"] == "open"
    assert events[0]["modeled_entry"] == pytest.approx(130.0)
    assert events[0]["entry"] == pytest.approx(130.0)
    assert "11:45" in events[0]["fill_time"]
    assert "11:45" in events[0]["entry_time"]

