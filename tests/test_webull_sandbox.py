"""Offline tests for the Webull sandbox response shapes. No network."""

import logging

import pandas as pd
import pytest

from webull_bot.broker.base import Broker
from webull_bot.broker.webull import (
    WebullBroker,
    WebullError,
    WebullResponseError,
    assert_sandbox_hosts,
    buying_power_from_balance,
    configure_sdk_client,
    default_token_dir,
    sandbox_hosts,
    select_account,
)
from webull_bot.data.webull_provider import (
    WebullDataProvider,
    _bars_from_payload,
    webull_timespan,
)
from webull_bot.execution.live import _cycle, run_sandbox
from webull_bot.logging_setup import SdkSecretFilter
from webull_bot.models import AccountSnapshot, Order, OrderType, Position, Side

MARGIN_ID = "A" * 26
CASH_ID = "B" * 26

ACCOUNTS = [
    {
        "account_id": MARGIN_ID,
        "account_number": "DEV123456",
        "account_class": "INDIVIDUAL_MARGIN",
        "account_type": "MARGIN",
    },
    {
        "account_id": CASH_ID,
        "account_number": "DEV654321",
        "account_class": "INDIVIDUAL_CASH",
        "account_type": "CASH",
    },
    {
        "account_id": "C" * 26,
        "account_number": "DEV111111",
        "account_class": "FUTURES",
        "account_type": "MARGIN",
    },
    {
        "account_id": "D" * 26,
        "account_number": "DEV222222",
        "account_class": "EVENTS_CASH",
        "account_type": "CASH",
    },
    {
        "account_id": "E" * 26,
        "account_number": "DEV333333",
        "account_class": "CRYPTO",
        "account_type": "CASH",
    },
]

BALANCE = {
    "total_net_liquidation_value": "100000.50",
    "total_cash_balance": "25000.25",
    "account_currency_assets": [
        {
            "currency": "USD",
            "day_buying_power": "50000.00",
            "buying_power": "40000.00",
            "overnight_buying_power": "30000.00",
        }
    ],
}

BARS = {
    "result": [
        {
            "symbol": "SPY",
            "result": [
                {
                    "time": 1720000000000,
                    "open": 500,
                    "high": 501,
                    "low": 499,
                    "close": 500.5,
                    "volume": 1000,
                }
            ],
        }
    ]
}


class _AccountV2:
    def __init__(self, balance):
        self.balance = balance

    def get_account_balance(self, account_id):
        return self.balance

    def get_account_position(self, account_id):
        return []


class _OrderV3:
    def __init__(self):
        self.placed = []

    def get_order_open(self, account_id, page_size=50):
        return []

    def place_order(self, account_id, payload):
        self.placed.append(payload)
        raise AssertionError("place_order should not be reached")


class _Trade:
    def __init__(self, balance=None):
        self.account_v2 = _AccountV2(balance or BALANCE)
        self.order_v3 = _OrderV3()


def _broker(**kwargs) -> WebullBroker:
    broker = WebullBroker(app_key="k" * 8, app_secret="s" * 8, account_id=MARGIN_ID, **kwargs)
    broker._trade = _Trade()
    return broker


def test_snapshot_reads_sandbox_balance_fields():
    broker = _broker()
    broker.account_type = "margin"
    snap = broker.snapshot()
    assert snap.equity == 100000.50
    assert snap.cash == 25000.25
    assert snap.buying_power == 50000.00
    assert snap.account_type == "margin"
    assert "equity" not in BALANCE


def test_buying_power_falls_through_currency_assets():
    day = {"account_currency_assets": [{"buying_power": "40000.00", "overnight_buying_power": "30000.00"}]}
    overnight = {"account_currency_assets": [{"overnight_buying_power": "30000.00"}]}
    assert buying_power_from_balance(day) == 40000.00
    assert buying_power_from_balance(overnight) == 30000.00


def test_snapshot_uses_cash_account_type_from_the_list():
    broker = _broker()
    broker.account_type = "cash"
    assert broker.snapshot().account_type == "cash"


def test_snapshot_refuses_to_assume_margin():
    broker = _broker()
    broker.account_type = ""
    with pytest.raises(WebullResponseError):
        broker.snapshot()


def test_five_accounts_select_margin_by_class():
    account_id, account_type = select_account(ACCOUNTS, account_id="", account_class="INDIVIDUAL_MARGIN")
    assert account_id == MARGIN_ID
    assert len(account_id) == 26
    assert account_type == "margin"


def test_account_class_can_select_cash():
    account_id, account_type = select_account(ACCOUNTS, account_id="", account_class="INDIVIDUAL_CASH")
    assert account_id == CASH_ID
    assert account_type == "cash"


def test_account_number_maps_to_internal_id():
    account_id, account_type = select_account(ACCOUNTS, account_id="DEV123456")
    assert account_id == MARGIN_ID
    assert account_id != "DEV123456"
    assert account_type == "margin"


def test_explicit_internal_id_is_kept():
    account_id, _account_type = select_account(ACCOUNTS, account_id=CASH_ID, account_class="INDIVIDUAL_MARGIN")
    assert account_id == CASH_ID


def test_futures_is_not_the_default_class():
    account_id, _account_type = select_account(ACCOUNTS)
    row = next(row for row in ACCOUNTS if row["account_id"] == account_id)
    assert row["account_class"] == "INDIVIDUAL_MARGIN"


def test_timespans_match_the_sandbox():
    assert webull_timespan("1d") == "D"
    assert webull_timespan("1h") == "M60"
    assert webull_timespan("60m") == "M60"
    with pytest.raises(ValueError):
        webull_timespan("D1")


def test_batch_bars_unwrap_nested_result_and_pass_milliseconds():
    class Market:
        def __init__(self):
            self.calls = []

        def get_history_bar(self, *args, **kwargs):
            raise AssertionError("get_history_bar is unavailable")

        def get_batch_history_bar(self, symbols, category, timespan, count="200", start_time=None, end_time=None, **kwargs):
            self.calls.append(
                {
                    "symbols": symbols,
                    "category": category,
                    "timespan": timespan,
                    "count": count,
                    "start_time": start_time,
                    "end_time": end_time,
                }
            )
            return BARS

    market = Market()

    class Data:
        market_data = market

    class Client:
        data_client = Data()

    frames = WebullDataProvider(Client()).history(["SPY"], "2020-01-01", "2026-12-31", "1d")
    assert market.calls[0]["timespan"] == "D"
    assert int(market.calls[0]["count"]) <= 1200
    assert isinstance(market.calls[0]["start_time"], int)
    assert isinstance(market.calls[0]["end_time"], int)
    assert market.calls[0]["start_time"] >= 10**12
    assert market.calls[0]["end_time"] > market.calls[0]["start_time"]
    assert "SPY" in frames
    assert frames["SPY"]["close"].iloc[-1] == 500.5
    unwrapped = _bars_from_payload(BARS)
    assert unwrapped is not None
    assert float(unwrapped["close"].iloc[0]) == 500.5


def test_broker_cancel_all_comes_from_the_base_class():
    assert issubclass(WebullBroker, Broker)

    class Recording(WebullBroker):
        def __init__(self):
            super().__init__(app_key="k" * 8, app_secret="s" * 8, account_id=MARGIN_ID)
            self.canceled = []
            self.placed = []

        def open_orders(self):
            return [
                Order(
                    client_order_id="abc",
                    symbol="SPY",
                    side=Side.BUY,
                    quantity=1,
                    order_type=OrderType.MARKET,
                )
            ]

        def cancel_order(self, client_order_id: str) -> None:
            self.canceled.append(client_order_id)

        def positions(self):
            return [Position(symbol="SPY", quantity=2, avg_price=100)]

        def place_order(self, order):
            self.placed.append(order)
            return order

    broker = Recording()
    assert broker.cancel_all() == 1
    assert broker.canceled == ["abc"]
    assert broker.flatten() == []
    assert broker.placed[0].side == Side.SELL
    assert broker.placed[0].symbol == "SPY"


def test_live_environment_is_never_silently_production(monkeypatch):
    from webull_bot.cli import resolve_live_environment

    monkeypatch.delenv("WEBULL_ENV", raising=False)
    with pytest.raises(SystemExit) as missing:
        resolve_live_environment()
    assert "production" in str(missing.value).lower()
    monkeypatch.setenv("WEBULL_ENV", "sandbox")
    with pytest.raises(SystemExit):
        resolve_live_environment()
    monkeypatch.setenv("WEBULL_ENV", "production")
    assert resolve_live_environment() == "production"


def test_live_sleep_is_the_time_module():
    import time as time_mod

    from webull_bot.execution import live

    assert live.time.sleep is time_mod.sleep


def test_sdk_filter_hides_key_secret_and_token():
    redactor = SdkSecretFilter(["appkeyvalue1", "appsecretvalue", "tokensecret1"])
    record = logging.LogRecord(
        "webull.core",
        logging.DEBUG,
        __file__,
        1,
        "headers x-app-key: appkeyvalue1 secret appsecretvalue token=tokensecret1",
        (),
        None,
    )
    assert redactor.filter(record)
    assert "appkeyvalue1" not in record.msg
    assert "appsecretvalue" not in record.msg
    assert "tokensecret1" not in record.msg
    assert "[redacted]" in record.msg


def test_sdk_loggers_are_warning_and_token_dir_is_outside_the_repo(monkeypatch, tmp_path):
    monkeypatch.setenv("WEBULL_OPENAPI_TOKEN_DIR", str(tmp_path))
    assert default_token_dir() == str(tmp_path)
    monkeypatch.delenv("WEBULL_OPENAPI_TOKEN_DIR", raising=False)
    assert default_token_dir() == str(__import__("pathlib").Path.home() / ".webull-openapi-token")
    assert not default_token_dir().endswith("/conf")

    class FakeApi:
        def __init__(self):
            self.levels = []
            self.token_dir = ""

        def set_token_dir(self, token_dir):
            self.token_dir = token_dir

        def set_stream_logger(self, log_level=logging.DEBUG, **kwargs):
            self.levels.append(("stream", log_level))

        def set_file_logger(self, path, log_level=logging.DEBUG, **kwargs):
            self.levels.append(("file", log_level, path))

    monkeypatch.setenv("WEBULL_OPENAPI_TOKEN_DIR", str(tmp_path))
    api = FakeApi()
    configure_sdk_client(api, app_key="appkeyvalue1", app_secret="appsecretvalue", token="tokensecret1")
    assert api.token_dir == str(tmp_path)
    assert api.levels[0] == ("stream", logging.WARNING)
    assert api.levels[1][0] == "file"
    assert api.levels[1][1] == logging.WARNING
    assert "conf" not in api.levels[1][2]


def test_quotes_host_is_the_sandbox_data_api():
    hosts = sandbox_hosts()
    assert hosts["quotes-api"] == "data-api.sandbox.webull.com"
    assert hosts["api"] == "api.sandbox.webull.com"
    assert_sandbox_hosts(hosts.values())
    with pytest.raises(WebullError, match="api.webull.com"):
        assert_sandbox_hosts(["api.webull.com"])
    with pytest.raises(WebullError):
        assert_sandbox_hosts(["https://api.webull.com/openapi"])


def test_sandbox_mode_refuses_the_production_host_before_any_order():
    broker = _broker(environment="sandbox")
    broker.sandbox_only = True
    broker.hosts = ["api.webull.com"]
    order = Order(
        client_order_id="a" * 32,
        symbol="SPY",
        side=Side.BUY,
        quantity=1,
        order_type=OrderType.MARKET,
    )
    with pytest.raises(WebullError, match="sandbox"):
        broker.place_order(order)
    assert broker._trade.order_v3.placed == []

    broker.hosts = ["api.webull.com"]
    broker.environment = "sandbox"
    with pytest.raises(WebullError):
        run_sandbox(
            broker=broker,
            data_provider=None,
            strategies=[],
            journal=None,
            limits=None,
            symbols=[],
            webhook="",
            poll_seconds=30,
            max_cycles=1,
            dry_run=False,
        )


def test_sandbox_dry_run_builds_an_order_without_sending():
    index = pd.bdate_range("2024-01-02", periods=5)
    frame = pd.DataFrame(
        {"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0, "volume": 1_000_000.0},
        index=index,
    )

    class Provider:
        def latest(self, symbols, interval="1d", lookback_days=500):
            return {"SPY": frame}

    class Snapshot(AccountSnapshot):
        pass

    sent = []

    class PaperHost:
        hosts = list(sandbox_hosts().values())
        environment = "sandbox"
        sandbox_only = True

        def snapshot(self):
            return AccountSnapshot(
                equity=100_000,
                cash=100_000,
                buying_power=100_000,
                account_type="margin",
            )

        def place_order(self, order):
            sent.append(order)
            return order

    class Strategy:
        name = "dual_momentum"
        custom_universe = False
        holds_overnight = True
        default_params = {}

        def universe(self, kind):
            return ["SPY"]

        def generate(self, bars, regime, params):
            out = bars["SPY"].copy()
            out["entry_next_open"] = True
            out["entry_this_open"] = False
            out["stop_price"] = 90.0
            return {"SPY": out}

    class Journal:
        def __init__(self):
            self.events = []

        def event(self, kind, message, payload):
            self.events.append(kind)

    journal = Journal()
    from webull_bot.risk.manager import RiskLimits

    _cycle(
        PaperHost(),
        Provider(),
        [Strategy()],
        journal,
        RiskLimits(),
        ["SPY"],
        "",
        dry_run=True,
        sandbox=True,
    )
    assert sent == []
    assert "dry_run" in journal.events


def test_check_report_redacts_secrets():
    from webull_bot.cli import build_parser, format_check_report

    text = format_check_report(
        environment="sandbox",
        accounts=ACCOUNTS[:1],
        snapshot=AccountSnapshot(equity=1, cash=2, buying_power=3, account_type="margin"),
        quote={"symbol": "SPY", "price": 500, "x-app-key": "appkeyvalue12345"},
        bars=[{"close": 500.5}],
        secrets=["appkeyvalue12345", "supersecretvalue99"],
    )
    assert "appkeyvalue12345" not in text
    assert "DEV123456" in text
    assert "SPY" in text
    assert "[redacted]" in text
    args = build_parser().parse_args(
        ["paper", "--broker", "webull-sandbox", "--dry-run", "--max-cycles", "1"]
    )
    assert args.broker == "webull-sandbox"
    assert args.dry_run is True
    assert args.max_cycles == 1
    check = build_parser().parse_args(["check", "--env", "sandbox"])
    assert check.env == "sandbox"
    with pytest.raises(SystemExit):
        build_parser().parse_args(["check"])


def test_sandbox_kill_does_not_require_the_live_phrase(monkeypatch):
    from webull_bot.config import load_config
    from webull_bot.execution.kill import kill

    monkeypatch.delenv("WEBULL_LIVE_CONFIRM", raising=False)

    class FakeBroker:
        def __init__(self, environment=None, **kwargs):
            assert environment == "sandbox"
            self.hosts = ["api.sandbox.webull.com", "data-api.sandbox.webull.com"]
            self.sandbox_only = False

        def connect(self):
            return None

        def cancel_all(self):
            return 2

        def flatten(self):
            return []

    class Journal:
        def __init__(self, path):
            self.path = path

        def event(self, *args, **kwargs):
            return None

    monkeypatch.setattr("webull_bot.execution.kill.WebullBroker", FakeBroker)
    monkeypatch.setattr("webull_bot.execution.kill.Journal", Journal)
    message = kill(load_config("config/default.yaml"), mode="sandbox", flatten=False)
    assert "Sandbox kill" in message
    with pytest.raises(SystemExit):
        kill(load_config("config/default.yaml"), mode="live", flatten=False)


def test_parser_local_paper_stays_the_default():
    from webull_bot.cli import build_parser

    args = build_parser().parse_args(["paper"])
    assert args.broker == "local"
    assert args.dry_run is False
