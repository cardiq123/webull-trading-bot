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
    ENTRY_BOOKS,
    NAME,
    QQQ_AGGR_1DTE_NAME,
    QQQ_AGGR_NAME,
    QQQ_NAME,
    SKIPS_EVENT_DAYS,
    combined_entries,
    data_problems,
    empty_state,
    in_forward_window,
    _event_line,
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
    assert args.strategy == [NAME]
    assert args.dry_run is True
    both = parser.parse_args(["forward-test", NAME, QQQ_NAME, "--dry-run"])
    assert both.strategy == [NAME, QQQ_NAME]
    runner = parser.parse_args(
        ["forward-test", NAME, QQQ_AGGR_NAME, "neckline_trapdoor_qqq", "--dry-run", "--now", f"{DAY}T11:50:00"]
    )
    assert runner.strategy == [NAME, QQQ_AGGR_NAME, "neckline_trapdoor_qqq"]
    aggr_report = parser.parse_args(["forward-report", QQQ_AGGR_NAME])
    assert aggr_report.strategy == QQQ_AGGR_NAME
    report = parser.parse_args(["forward-report", NAME])
    assert report.strategy == NAME
    qqq_report = parser.parse_args(["forward-report", QQQ_NAME])
    assert qqq_report.strategy == QQQ_NAME
    with pytest.raises(KeyError, match="not in the paper or live book"):
        strategy_by_name(QQQ_NAME)
    with pytest.raises(SystemExit, match="forward-test vwap_band_15m vwap_band_15m_qqq"):
        refuse_if_forward_only([NAME, QQQ_NAME])
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
    assert two[0]["iv_source"] == "VIX1D prior close"
    assert "VIX1D prior close" in _event_line(two[0])
    assert two[1]["skip"] == "overlap"
    missing = plan_day(bars15=_long_day(), bars5=_five(), now=_at("11:50"), iv_points={}, iv_closes={})
    assert missing[0]["skip"] == "iv"
    cached = pd.Series([18.0], index=pd.to_datetime(["2024-01-02"]))
    from_cache = plan_day(
        bars15=_long_day(), bars5=_five(), now=_at("11:50"), iv_points={}, iv_closes={"^VIX1D": cached}
    )
    assert from_cache[0]["status"] == "open"
    assert from_cache[0]["iv_source"] == "cached VIX1D"
    vix_cache = plan_day(
        bars15=_long_day(), bars5=_five(), now=_at("11:50"), iv_points={}, iv_closes={"^VIX": cached}
    )
    assert vix_cache[0]["iv_source"] == "cached VIX"
    vix_prior = plan_day(
        bars15=_long_day(),
        bars5=_five(),
        now=_at("11:50"),
        iv_points={date(2024, 1, 3): (19.0, "VIX")},
        iv_closes={"^VIX1D": cached},
    )
    assert vix_prior[0]["iv_source"] == "VIX prior close"
    quoted = plan_day(
        bars15=_long_day(), bars5=_five(), now=_at("11:50"), iv_points={}, iv_closes={}, broker=Broker()
    )
    assert quoted[0]["status"] == "open"
    assert quoted[0]["iv_source"] == "sandbox option quote"
    preferred = plan_day(
        bars15=_long_day(),
        bars5=_five(),
        now=_at("11:50"),
        iv_points=IV,
        iv_closes={"^VIX": cached},
        broker=Broker(),
    )
    assert preferred[0]["iv_source"] == "VIX1D prior close"
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


def test_qqq_book_keeps_its_own_journal(tmp_path):
    journal = Journal(tmp_path / "both.sqlite")
    broker = Broker()
    qqq = run_cycle(
        journal=journal,
        bars15=_long_day(),
        bars5=_five(),
        now=_at("11:50"),
        iv_points=IV,
        broker=broker,
        book=QQQ_NAME,
    )
    text = "\n".join(qqq)
    assert "vwap_band_15m_qqq" in text
    assert "0 DTE QQQ" in text
    assert broker.orders[-1]["symbol"] == "QQQ"
    assert broker.orders[-1]["quantity"] == "1"
    saved = journal.forward_load(QQQ_NAME)
    assert saved["book"] == QQQ_NAME
    assert saved["positions"][0]["id"].startswith("QQQ|")
    assert journal.forward_load(NAME) is None
    spy = run_cycle(
        journal=journal,
        bars15=_long_day(),
        bars5=_five(),
        now=_at("11:50"),
        iv_points=IV,
        broker=broker,
        book=NAME,
    )
    assert any("0 DTE SPY" in line for line in spy)
    assert journal.forward_load(NAME)["positions"]
    assert journal.forward_load(QQQ_NAME)["positions"]
    assert [order["symbol"] for order in broker.orders] == ["QQQ", "SPY"]
    report = report_text(journal, book=QQQ_NAME)
    assert report.splitlines()[0].startswith("vwap_band_15m_qqq ")
    assert "QQQ" in report
    stale = data_problems(pd.DataFrame(), pd.DataFrame(), _at("11:50"), book=QQQ_NAME)
    assert stale[0].startswith("QQQ ")
    refused = run_cycle(
        journal=journal,
        bars15=pd.DataFrame(),
        bars5=pd.DataFrame(),
        now=_at("11:50"),
        dry_run=True,
        book=QQQ_NAME,
    )
    assert any(line.startswith("Refusing to trade vwap_band_15m_qqq") and "QQQ 15-minute" in line for line in refused)


def test_cli_dry_run_does_not_connect(monkeypatch):
    import webull_bot.broker.webull as broker_mod
    import webull_bot.data.yfinance_provider as provider_mod
    import webull_bot.journal.store as store_mod

    def boom(*_args, **_kwargs):
        raise AssertionError("dry-run connected")

    monkeypatch.setattr(broker_mod, "WebullBroker", boom)
    asked = []

    class Provider:
        def __init__(self, *_args, **_kwargs):
            pass

        def history(self, symbols, start, end, interval="1d"):
            asked.append((tuple(symbols), interval))
            if interval == "15m":
                return {symbol: _long_day() for symbol in symbols}
            if interval == "5m":
                return {symbol: _five() for symbol in symbols}
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

    args = SimpleNamespace(
        strategy=[NAME, QQQ_NAME], dry_run=True, now=f"{DAY}T11:50:00", config="config/default.yaml"
    )
    assert _forward_vwap(load_config("config/default.yaml"), args, [NAME, QQQ_NAME]) == 0
    assert saved == []
    assert ("SPY", "QQQ") in {tuple(sorted(symbols)) for symbols, _interval in asked} or any(
        set(symbols) >= {"SPY", "QQQ"} and interval == "15m" for symbols, interval in asked
    )
    live = SimpleNamespace(strategy=[NAME, QQQ_NAME], dry_run=False, now=f"{DAY}T11:50:00", config="config/default.yaml")
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


def test_a_cycle_after_the_entry_cap_journals_expired_late(tmp_path, monkeypatch):
    """The 11:30 bar closes at 11:45. 12:27 is the same miss as the 10:00 signal."""
    monkeypatch.delenv("VWAP_MAX_ENTRY_DELAY_MIN", raising=False)
    broker = Broker()
    for book in (NAME, QQQ_NAME):
        journal = Journal(tmp_path / f"{book}.sqlite")
        lines = run_cycle(
            journal=journal,
            bars15=_long_day(),
            bars5=_five(),
            now=_at("12:27"),
            iv_points=IV,
            broker=broker,
            book=book,
        )
        text = "\n".join(lines)
        assert "expired, late" in text
        assert broker.orders == []
        saved = journal.forward_load(book)
        assert saved["positions"] == []
        assert saved["signals"][0]["skip"] == "expired"
        assert saved["signals"][0]["detail"] == "expired, late"
        assert saved["signals"][0]["reason"] == "expired, late"
        again = run_cycle(
            journal=journal,
            bars15=_long_day(),
            bars5=_five(),
            now=_at("12:32"),
            iv_points=IV,
            broker=broker,
            book=book,
        )
        assert any("already journaled" in line for line in again)
    assert broker.orders == []


def test_the_entry_cap_is_inclusive_and_configurable(tmp_path, monkeypatch):
    monkeypatch.delenv("VWAP_MAX_ENTRY_DELAY_MIN", raising=False)
    on_time = Journal(tmp_path / "on-time.sqlite")
    broker = Broker()
    _cycle(on_time, _long_day(), _five(), "11:55", broker=broker)
    assert len(broker.orders) == 1
    assert broker.orders[0]["side"] == "BUY"

    monkeypatch.setenv("VWAP_MAX_ENTRY_DELAY_MIN", "0")
    tight = Journal(tmp_path / "tight.sqlite")
    tight_broker = Broker()
    lines = _cycle(tight, _long_day(), _five(), "11:50", broker=tight_broker)
    assert "expired, late" in "\n".join(lines)
    assert tight_broker.orders == []

    monkeypatch.setenv("VWAP_MAX_ENTRY_DELAY_MIN", "180")
    wide = Journal(tmp_path / "wide.sqlite")
    wide_broker = Broker()
    _cycle(wide, _long_day(), _five(), "12:27", broker=wide_broker)
    assert len(wide_broker.orders) == 1
    assert wide_broker.orders[0]["side"] == "BUY"
    assert "12:27" in journal_entry_time(wide)


def test_an_open_late_entry_still_exits_and_is_flagged(tmp_path, monkeypatch):
    monkeypatch.delenv("VWAP_MAX_ENTRY_DELAY_MIN", raising=False)
    journal = Journal(tmp_path / "open-late.sqlite")
    broker = Broker()
    _cycle(journal, _long_day(), _five(), "11:50", broker=broker)
    state = journal.forward_load(NAME)
    position = state["positions"][0]
    stop = position["stop"]
    target = position["target"]
    position["signal_time"] = _at("10:00").isoformat()
    position["entry_time"] = _at("12:27").isoformat()
    for row in state["signals"]:
        row["signal_time"] = position["signal_time"]
        row["entry_time"] = position["entry_time"]
    journal.forward_save(NAME, state)

    held = _cycle(journal, _long_day(), _five(), "12:32", broker=broker)
    assert any("Still open." in line and "Off-plan late entry." in line for line in held)
    assert len(broker.orders) == 1
    kept = journal.forward_load(NAME)["positions"][0]
    assert kept["stop"] == stop
    assert kept["target"] == target

    stopped = _five(special={"12:30": (130.0, 130.4, 90.0, 100.0, 1000.0)})
    lines = _cycle(journal, _long_day(), stopped, "12:35", broker=broker)
    assert any("reason stop" in line for line in lines)
    assert broker.orders[-1]["side"] == "SELL"
    assert journal.forward_load(NAME)["positions"] == []
    report = report_text(journal)
    assert "off-plan late entry" in report
    assert "The stop, the target, and the 15:45 flat still manage that position." in report


def journal_entry_time(journal: Journal) -> str:
    state = journal.forward_load(NAME)
    return str(state["positions"][0]["entry_time"])


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


def test_five_opens_across_the_forward_books_block_another_vwap_entry(tmp_path):
    journal = Journal(tmp_path / "cap.sqlite")
    state = empty_state()
    state["signals"] = [
        {"id": f"seed-{i}", "status": "closed", "entry_time": f"{DAY}T10:0{i}:00"}
        for i in range(5)
    ]
    journal.forward_save(NAME, state)
    broker = Broker()
    lines = _cycle(journal, _long_day(), _five(), "11:50", broker=broker)
    assert any("already opened 5 trades today" in line for line in lines)
    assert broker.orders == []


def test_qqq_aggressive_buys_three_contracts_and_keeps_its_own_mirror(tmp_path, monkeypatch):
    monkeypatch.setenv("WEBULL_APP_SECRET", "super-secret-value")
    assert QQQ_AGGR_NAME == "vwap_band_15m_qqq_aggr"
    assert QQQ_AGGR_NAME in ENTRY_BOOKS
    with pytest.raises(KeyError, match="not in the paper or live book"):
        strategy_by_name(QQQ_AGGR_NAME)
    with pytest.raises(SystemExit, match="Live trading stays off"):
        refuse_if_forward_only([QQQ_AGGR_NAME])
    one = plan_day(bars15=_long_day(), bars5=_five(), now=_at("11:50"), iv_points=IV, book=QQQ_NAME)
    three = plan_day(bars15=_long_day(), bars5=_five(), now=_at("11:50"), iv_points=IV, book=QQQ_AGGR_NAME)
    assert one[0]["status"] == "open" and three[0]["status"] == "open"
    assert three[0]["stop"] == pytest.approx(one[0]["stop"])
    assert three[0]["target"] == pytest.approx(one[0]["target"])
    assert three[0]["direction"] == one[0]["direction"]
    assert one[0]["qty"] == 1
    assert three[0]["qty"] == 3
    assert three[0]["model_debit"] == pytest.approx(one[0]["model_debit"] * 3)
    rich = plan_day(
        bars15=_long_day(), bars5=_five(), now=_at("11:50"), iv_points=IV, settled=1_000_000.0, book=QQQ_AGGR_NAME
    )
    assert rich[0]["qty"] == 3
    short_cash = plan_day(
        bars15=_long_day(),
        bars5=_five(),
        now=_at("11:50"),
        iv_points=IV,
        settled=one[0]["model_debit"] * 2,
        book=QQQ_AGGR_NAME,
    )
    assert short_cash[0]["skip"] == "premium"
    assert short_cash[0]["qty"] == 3
    assert "3 contracts" in short_cash[0]["detail"]

    journal = Journal(tmp_path / "aggr.sqlite")
    journal.forward_save(QQQ_NAME, {"signals": [{"id": "keep-the-one-lot"}]})
    broker = Broker()
    lines = run_cycle(
        journal=journal,
        bars15=_long_day(),
        bars5=_five(),
        now=_at("11:50"),
        iv_points=IV,
        broker=broker,
        book=QQQ_AGGR_NAME,
    )
    text = "\n".join(lines)
    assert "super-secret-value" not in text
    assert "QQQ Aggressive" in text
    assert "vwap_band_15m_qqq_aggr" in text
    assert "$2,500" in text
    assert "3 contracts" in text
    assert len(broker.orders) == 1
    assert broker.orders[0]["symbol"] == "QQQ"
    assert broker.orders[0]["quantity"] == "3"
    assert broker.orders[0]["legs"][0]["quantity"] == "3"
    saved = journal.forward_load(QQQ_AGGR_NAME)
    assert saved["book"] == QQQ_AGGR_NAME
    assert saved["stake"] == 2500.0
    assert saved["positions"][0]["qty"] == 3
    assert journal.forward_load(QQQ_NAME) == {"signals": [{"id": "keep-the-one-lot"}]}
    assert journal.forward_load(NAME) is None

    later = {"12:00": (130.0, 170.0, 129.6, 165.0, 1000.0)}
    closed = run_cycle(
        journal=journal,
        bars15=_long_day(),
        bars5=_five(special=later),
        now=_at("12:05"),
        iv_points=IV,
        broker=broker,
        book=QQQ_AGGR_NAME,
    )
    assert any("Order SELL 3" in line for line in closed)
    assert broker.orders[-1]["side"] == "SELL"
    assert broker.orders[-1]["quantity"] == "3"
    report = report_text(journal, book=QQQ_AGGR_NAME)
    assert report.splitlines()[0].startswith("vwap_band_15m_qqq_aggr ")
    assert "QQQ Aggressive" in report
    assert "$2,500" in report


def test_qqq_aggressive_journals_a_three_lot_it_cannot_afford(tmp_path):
    journal = Journal(tmp_path / "poor.sqlite")
    state = empty_state()
    state["settled"] = 10.0
    journal.forward_save(QQQ_AGGR_NAME, state)
    broker = Broker()
    lines = run_cycle(
        journal=journal,
        bars15=_long_day(),
        bars5=_five(),
        now=_at("11:50"),
        iv_points=IV,
        broker=broker,
        book=QQQ_AGGR_NAME,
    )
    assert broker.orders == []
    assert any("3 contracts" in line for line in lines)
    saved = journal.forward_load(QQQ_AGGR_NAME)
    assert saved["signals"][0]["skip"] == "premium"
    assert saved["signals"][0]["qty"] == 3
    assert saved["positions"] == []


def test_the_one_contract_qqq_journal_still_counts_toward_the_daily_cap(tmp_path):
    journal = Journal(tmp_path / "shared-cap.sqlite")
    journal.forward_save(
        QQQ_NAME,
        {
            "signals": [
                {"id": f"old-{i}", "status": "closed", "entry_time": f"{DAY}T10:0{i}:00"}
                for i in range(4)
            ]
        },
    )
    journal.forward_save(
        "neckline_trapdoor_qqq",
        {"signals": [{"id": "trap", "status": "open", "entry_time": f"{DAY}T11:00:00"}]},
    )
    assert combined_entries(journal, date.fromisoformat(DAY), QQQ_AGGR_NAME, empty_state()) == 5
    broker = Broker()
    lines = run_cycle(
        journal=journal,
        bars15=_long_day(),
        bars5=_five(),
        now=_at("11:50"),
        iv_points=IV,
        broker=broker,
        book=QQQ_AGGR_NAME,
    )
    assert any("already opened 5 trades today" in line for line in lines)
    assert broker.orders == []
    saved = journal.forward_load(QQQ_AGGR_NAME)
    assert saved["signals"][0]["skip"] == "cap"
    assert journal.forward_load(QQQ_NAME)["signals"][0]["id"] == "old-0"


def test_qqq_aggressive_1dte_is_the_next_session_and_flattens_the_same_day(tmp_path, monkeypatch):
    from webull_bot.execution.forward_vwap import _ACTIVE, _activate, _expiry_for

    monkeypatch.setenv("WEBULL_APP_SECRET", "super-secret-value")
    assert QQQ_AGGR_1DTE_NAME == "vwap_band_15m_qqq_aggr_1dte"
    assert QQQ_AGGR_1DTE_NAME in ENTRY_BOOKS
    token = _activate(QQQ_AGGR_1DTE_NAME)
    try:
        assert _expiry_for(date(2024, 1, 3)) == date(2024, 1, 4)
        assert _expiry_for(date(2026, 10, 9)) == date(2026, 10, 12)
    finally:
        _ACTIVE.reset(token)
    with pytest.raises(KeyError, match="not in the paper or live book"):
        strategy_by_name(QQQ_AGGR_1DTE_NAME)
    with pytest.raises(SystemExit, match="Live trading stays off"):
        refuse_if_forward_only([QQQ_AGGR_1DTE_NAME])
    parser = build_parser()
    watch = parser.parse_args(
        [
            "forward-watch",
            NAME,
            QQQ_AGGR_NAME,
            QQQ_AGGR_1DTE_NAME,
            "neckline_trapdoor_qqq",
            "--dry-run",
            "--once",
        ]
    )
    assert watch.strategy == [NAME, QQQ_AGGR_NAME, QQQ_AGGR_1DTE_NAME, "neckline_trapdoor_qqq"]
    assert parser.parse_args(["forward-report", QQQ_AGGR_1DTE_NAME]).strategy == QQQ_AGGR_1DTE_NAME

    zero = plan_day(bars15=_long_day(), bars5=_five(), now=_at("11:50"), iv_points=IV, book=QQQ_AGGR_NAME)
    held = plan_day(bars15=_long_day(), bars5=_five(), now=_at("11:50"), iv_points=IV, book=QQQ_AGGR_1DTE_NAME)
    assert zero[0]["status"] == "open" and held[0]["status"] == "open"
    assert held[0]["stop"] == pytest.approx(zero[0]["stop"])
    assert held[0]["target"] == pytest.approx(zero[0]["target"])
    assert held[0]["direction"] == zero[0]["direction"]
    assert held[0]["entry_time"] == zero[0]["entry_time"]
    assert held[0]["qty"] == 1
    assert held[0]["expiry"] == "2024-01-04"
    assert zero[0]["expiry"] == DAY
    assert held[0]["model_debit"] > zero[0]["model_debit"] / 3
    rich = plan_day(
        bars15=_long_day(),
        bars5=_five(),
        now=_at("11:50"),
        iv_points=IV,
        settled=1_000_000.0,
        book=QQQ_AGGR_1DTE_NAME,
    )
    assert rich[0]["qty"] == 1
    one_lot = plan_day(
        bars15=_long_day(),
        bars5=_five(),
        now=_at("11:50"),
        iv_points=IV,
        settled=held[0]["model_debit"],
        book=QQQ_AGGR_1DTE_NAME,
    )
    assert one_lot[0]["status"] == "open"
    assert one_lot[0]["qty"] == 1
    short_cash = plan_day(
        bars15=_long_day(),
        bars5=_five(),
        now=_at("11:50"),
        iv_points=IV,
        settled=held[0]["model_debit"] / 2,
        book=QQQ_AGGR_1DTE_NAME,
    )
    assert short_cash[0]["skip"] == "premium"
    assert short_cash[0]["qty"] == 1
    assert "does not fit" in short_cash[0]["detail"]

    flat = plan_day(
        bars15=_long_day(),
        bars5=_five(special={"15:45": (131.0, 180.0, 129.0, 179.0, 1000.0)}),
        now=_at("15:50"),
        iv_points=IV,
        book=QQQ_AGGR_1DTE_NAME,
    )
    assert flat[0]["reason"] == "flat"
    assert flat[0]["exit"] == pytest.approx(131.0)
    assert flat[0]["exit_time"].startswith(DAY)
    assert "15:45" in flat[0]["exit_time"]
    assert flat[0]["expiry"] == "2024-01-04"

    journal = Journal(tmp_path / "both.sqlite")
    broker = Broker()
    first = run_cycle(
        journal=journal,
        bars15=_long_day(),
        bars5=_five(),
        now=_at("11:50"),
        iv_points=IV,
        broker=broker,
        book=QQQ_AGGR_NAME,
    )
    second = run_cycle(
        journal=journal,
        bars15=_long_day(),
        bars5=_five(),
        now=_at("11:50"),
        iv_points=IV,
        broker=broker,
        book=QQQ_AGGR_1DTE_NAME,
    )
    text = "\n".join(first + second)
    assert "super-secret-value" not in text
    assert "QQQ Aggressive 1DTE" in text
    assert "not held overnight" in "\n".join(second)
    assert len(broker.orders) == 2
    assert broker.orders[0]["quantity"] == "3"
    assert broker.orders[1]["quantity"] == "1"
    assert broker.orders[1]["symbol"] == "QQQ"
    assert broker.orders[1]["legs"][0]["option_expire_date"] == "2024-01-04"
    assert broker.orders[0]["legs"][0]["option_expire_date"] == DAY
    assert combined_entries(
        journal, date.fromisoformat(DAY), QQQ_AGGR_1DTE_NAME, journal.forward_load(QQQ_AGGR_1DTE_NAME)
    ) == 2
    saved = journal.forward_load(QQQ_AGGR_1DTE_NAME)
    assert saved["book"] == QQQ_AGGR_1DTE_NAME
    assert saved["stake"] == 2500.0
    assert saved["positions"][0]["qty"] == 1
    assert saved["positions"][0]["expiry"] == "2024-01-04"
    assert journal.forward_load(QQQ_AGGR_NAME)["positions"][0]["expiry"] == DAY

    flat_lines = run_cycle(
        journal=journal,
        bars15=_long_day(),
        bars5=_five(special={"15:45": (131.0, 180.0, 129.0, 179.0, 1000.0)}),
        now=_at("15:50"),
        iv_points=IV,
        broker=broker,
        book=QQQ_AGGR_1DTE_NAME,
    )
    assert any("reason flat" in line for line in flat_lines)
    assert any("Order SELL 1" in line for line in flat_lines)
    assert journal.forward_load(QQQ_AGGR_1DTE_NAME)["positions"] == []
    assert broker.orders[-1]["quantity"] == "1"
    assert broker.orders[-1]["legs"][0]["option_expire_date"] == "2024-01-04"
    report = report_text(journal, book=QQQ_AGGR_1DTE_NAME)
    assert report.splitlines()[0].startswith("vwap_band_15m_qqq_aggr_1dte ")
    assert "QQQ Aggressive 1DTE" in report
    assert "1 DTE" in report
    assert "flat at 15:45" in report
    assert "$2,500" in report

    capped = Journal(tmp_path / "cap.sqlite")
    capped.forward_save(
        NAME,
        {
            "signals": [
                {"id": f"seed-{i}", "status": "closed", "entry_time": f"{DAY}T10:0{i}:00"}
                for i in range(4)
            ]
        },
    )
    room = Broker()
    run_cycle(
        journal=capped,
        bars15=_long_day(),
        bars5=_five(),
        now=_at("11:50"),
        iv_points=IV,
        broker=room,
        book=QQQ_AGGR_NAME,
    )
    blocked = run_cycle(
        journal=capped,
        bars15=_long_day(),
        bars5=_five(),
        now=_at("11:50"),
        iv_points=IV,
        broker=room,
        book=QQQ_AGGR_1DTE_NAME,
    )
    assert len(room.orders) == 1
    assert any("already opened 5 trades today" in line for line in blocked)
    assert capped.forward_load(QQQ_AGGR_1DTE_NAME)["signals"][0]["skip"] == "cap"
    assert capped.forward_load(QQQ_AGGR_NAME)["positions"]


def test_an_open_three_lot_still_closes_at_three_after_the_book_is_one(tmp_path):
    journal = Journal(tmp_path / "legacy.sqlite")
    state = empty_state()
    state["book"] = QQQ_AGGR_1DTE_NAME
    state["positions"] = [
        {
            "id": "legacy-3",
            "direction": "long",
            "right": "call",
            "option_type": "CALL",
            "strike": 130.0,
            "model_strike": 130.0,
            "expiry": "2024-01-04",
            "signal_time": f"{DAY}T11:30:00-05:00",
            "fill_time": f"{DAY}T11:45:00-05:00",
            "entry_time": f"{DAY}T11:47:00-05:00",
            "entry": 130.0,
            "stop": 99.0,
            "target": 200.0,
            "qty": 3,
            "model_debit": 300.0,
            "iv": 0.2,
        }
    ]
    journal.forward_save(QQQ_AGGR_1DTE_NAME, state)
    broker = Broker()
    lines = run_cycle(
        journal=journal,
        bars15=_long_day(),
        bars5=_five(),
        now=_at("15:50"),
        iv_points=IV,
        broker=broker,
        book=QQQ_AGGR_1DTE_NAME,
    )
    assert any("Order SELL 3" in line for line in lines)
    assert broker.orders[-1]["side"] == "SELL"
    assert broker.orders[-1]["quantity"] == "3"
    assert broker.orders[-1]["legs"][0]["option_expire_date"] == "2024-01-04"
    assert journal.forward_load(QQQ_AGGR_1DTE_NAME)["positions"] == []
    assert all(order["side"] != "BUY" for order in broker.orders)

