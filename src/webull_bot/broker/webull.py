"""Official Webull OpenAPI adapter.

This uses ``webull-openapi-python-sdk`` (package ``webull-openapi-python-sdk``,
repository webull-inc/webull-openapi-python-sdk). It does not use unofficial
reverse-engineered clients.

What the public docs support, and what this class calls:

* Credentials are an app key and app secret created after the brokerage
  account is open and the API application is approved. US management page:
  https://www.webull.com/center#openApiManagement
  The review is documented as 1–2 business days. Keys are read from
  ``WEBULL_APP_KEY`` and ``WEBULL_APP_SECRET`` only.
* ``ApiClient(app_key, app_secret, region)`` and ``TradeClient``.
* Sandbox HTTP host ``api.sandbox.webull.com``. Production trading host
  ``api.webull.com`` is the SDK default; this adapter does not override it
  when ``WEBULL_ENV=production``.
* Accounts: ``trade_client.account_v2.get_account_list()``,
  ``get_account_balance(account_id)``, ``get_account_position(account_id)``.
* Orders: ``trade_client.order_v3.place_order``, ``replace_order``,
  ``cancel_order``, ``get_order_open``, ``get_order_detail``.
* US equity order types used here: MARKET, LIMIT, STOP_LOSS, STOP_LOSS_LIMIT,
  and TRAILING_STOP_LOSS. MARKET_ON_OPEN / MARKET_ON_CLOSE are documented as
  institutional-only and are not sent. A trailing stop needs ``trailing_type``
  ``AMOUNT`` or ``PERCENTAGE`` and ``trailing_stop_step``, and it is DAY only.
* A take-profit plus stop-loss bracket is MASTER + STOP_PROFIT + STOP_LOSS
  with one ``client_combo_order_id``. That is the documented equity bracket.
  ``OTOCO`` is a different pattern (a master that triggers two linked limits)
  and is not the bracket this study sends. ``place_order`` still sends one
  NORMAL equity order. The chart-exit helper builds these payloads and stages
  them on the paper broker. It does not enable live trading.
* Options, from the options trade page: MARKET, LIMIT, STOP_LOSS, and
  STOP_LOSS_LIMIT. ``TRAILING_STOP_LOSS`` is not supported. ``OTO``, ``OCO``,
  and ``OTOCO`` are equity-only. Single-leg MASTER / STOP_PROFIT / STOP_LOSS
  exists, and its stop price is the option premium. This study's stop is the
  underlying, so option exits stay bot-managed and are not sent.
* Options are in the public trade API (``instrument_type=OPTION``,
  ``option_strategy`` ``SINGLE`` or ``VERTICAL``). ``build_single_option_order``
  and ``build_bull_call_spread`` match those published examples.
  ``place_order`` does not send them. This process does not submit option
  orders. The blue-chip options column is a Black-Scholes estimate, and
  paper mode fills the underlying stock.

What could not be verified without the owner's keys
----------------------------------------------------
* The SDK's first ``TradeClient`` construction can require an interactive
  token / 2FA approval in the Webull app (the official MCP adapter treats
  ``ERROR_INIT_TOKEN`` and ``NO_AVAILABLE_DEVICE`` as setup errors). That
  flow was not executed here.
* Live JSON field names for balances, positions, and order acknowledgements
  are parsed defensively. A mismatch will raise ``WebullResponseError``
  with the raw keys rather than guessing a fill.
* Whether a retail account may send ``side=SHORT`` was not tested. Shorts
  stay disabled in the risk config.
* Whether Webull still blocks a fourth day trade during the FINRA
  transition (through 2027-10-20) was not tested. The risk layer still
  enforces the legacy rule by default in that window.
* OpenAPI market data is a separate subscription. ``WebullDataProvider``
  will 403 without it. Streaming (gRPC order events, MQTT quotes) is not
  required; the session loop polls.
* History bars go through ``get_batch_history_bar`` (``get_history_bar``
  is unavailable). Allowed timespans are M1, M5, M15, M30, M60, M120,
  M240, D, W, M, and Y. The batch body is nested per symbol.

Nothing in this module places an order at import time.
"""

from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path
from typing import Any, Optional

from webull_bot.broker.base import Broker
from webull_bot.logging_setup import SdkSecretFilter
from webull_bot.models import (
    AccountSnapshot,
    Fill,
    Order,
    OrderStatus,
    OrderType,
    Position,
    Side,
    TimeInForce,
)


class WebullError(RuntimeError):
    pass


class WebullResponseError(WebullError):
    pass


class WebullCredentialsError(WebullError):
    pass


_ORDER_TYPE = {
    OrderType.MARKET: "MARKET",
    OrderType.LIMIT: "LIMIT",
    OrderType.STOP: "STOP_LOSS",
    OrderType.STOP_LIMIT: "STOP_LOSS_LIMIT",
    OrderType.TRAILING: "TRAILING_STOP_LOSS",
}


def build_equity_order(
    *,
    client_order_id: str,
    symbol: str,
    side: str,
    order_type: str,
    quantity: float,
    limit_price: Optional[float] = None,
    stop_price: Optional[float] = None,
    time_in_force: str = "DAY",
    trading_session: str = "CORE",
    trailing_type: Optional[str] = None,
    trailing_stop_step: Optional[float | str] = None,
) -> dict[str, str]:
    """Body for one US equity order, matching the published place_order example."""
    if len(client_order_id) > 32:
        raise ValueError("client_order_id must be at most 32 characters")
    if order_type not in {"MARKET", "LIMIT", "STOP_LOSS", "STOP_LOSS_LIMIT", "TRAILING_STOP_LOSS"}:
        raise ValueError(f"Unsupported order type {order_type}")
    payload: dict[str, str] = {
        "combo_type": "NORMAL",
        "client_order_id": client_order_id,
        "symbol": symbol,
        "instrument_type": "EQUITY",
        "market": "US",
        "order_type": order_type,
        "quantity": _qty(quantity),
        "support_trading_session": trading_session,
        "side": side,
        "time_in_force": time_in_force,
        "entrust_type": "QTY",
    }
    if order_type in {"LIMIT", "STOP_LOSS_LIMIT"}:
        if limit_price is None:
            raise ValueError(f"{order_type} requires limit_price")
        payload["limit_price"] = f"{limit_price:.2f}"
    if order_type in {"STOP_LOSS", "STOP_LOSS_LIMIT"}:
        if stop_price is None:
            raise ValueError(f"{order_type} requires stop_price")
        payload["stop_price"] = f"{stop_price:.2f}"
    if order_type == "TRAILING_STOP_LOSS":
        if time_in_force != "DAY":
            raise ValueError("TRAILING_STOP_LOSS supports DAY time in force only")
        if trailing_type not in {"AMOUNT", "PERCENTAGE"}:
            raise ValueError("TRAILING_STOP_LOSS requires trailing_type AMOUNT or PERCENTAGE")
        payload["trailing_type"] = trailing_type
        payload["trailing_stop_step"] = _trail_step(trailing_stop_step)
    return payload


def build_trailing_stop_order(
    *,
    client_order_id: str,
    symbol: str,
    side: str,
    quantity: float,
    trailing_type: str,
    trailing_stop_step: float | str,
) -> dict[str, str]:
    """Equity TRAILING_STOP_LOSS. DAY only. This does not send the order.

    ``trailing_stop_step`` is dollars for AMOUNT (``"5"`` trails by $5) or a
    fraction for PERCENTAGE (``"0.01"`` is 1%). A multi-day swing has to be
    renewed, because the native order expires at the end of the day.
    """
    return build_equity_order(
        client_order_id=client_order_id,
        symbol=symbol,
        side=side,
        order_type="TRAILING_STOP_LOSS",
        quantity=quantity,
        time_in_force="DAY",
        trailing_type=trailing_type,
        trailing_stop_step=trailing_stop_step,
    )


def build_bracket_orders(
    *,
    symbol: str,
    quantity: float,
    take_profit: float,
    stop_loss: float,
    direction: str = "long",
    entry_type: str = "MARKET",
    limit_price: Optional[float] = None,
    client_combo_order_id: Optional[str] = None,
) -> dict[str, Any]:
    """Equity take-profit and stop-loss: MASTER + STOP_PROFIT + STOP_LOSS.

    This is the published bracket. It is not combo type OTOCO. The combo id
    is the ``client_combo_order_id`` argument of ``place_order``, not a field
    on each leg. Nothing here calls the network. The legs are DAY orders, so
    a multi-day hold is renewed by the bot. The backtest keeps the stop and
    the target until one fills or the time stop hits.
    """
    if direction not in {"long", "short"}:
        raise ValueError("direction must be long or short")
    if take_profit <= stop_loss and direction == "long":
        raise ValueError("A long bracket needs the take-profit above the stop")
    if take_profit >= stop_loss and direction == "short":
        raise ValueError("A short bracket needs the take-profit below the stop")
    combo_id = client_combo_order_id or new_client_order_id()
    if len(combo_id) > 32:
        raise ValueError("client_combo_order_id must be at most 32 characters")
    entry_side = "BUY" if direction == "long" else "SHORT"
    exit_side = "SELL" if direction == "long" else "BUY"
    master = build_equity_order(
        client_order_id=new_client_order_id(),
        symbol=symbol,
        side=entry_side,
        order_type=entry_type,
        quantity=quantity,
        limit_price=limit_price,
        time_in_force="DAY",
    )
    profit = build_equity_order(
        client_order_id=new_client_order_id(),
        symbol=symbol,
        side=exit_side,
        order_type="LIMIT",
        quantity=quantity,
        limit_price=take_profit,
        time_in_force="DAY",
    )
    stop = build_equity_order(
        client_order_id=new_client_order_id(),
        symbol=symbol,
        side=exit_side,
        order_type="STOP_LOSS",
        quantity=quantity,
        stop_price=stop_loss,
        time_in_force="DAY",
    )
    master["combo_type"] = "MASTER"
    profit["combo_type"] = "STOP_PROFIT"
    stop["combo_type"] = "STOP_LOSS"
    return {"client_combo_order_id": combo_id, "new_orders": [master, profit, stop]}


def build_option_trailing_stop_order(**_ignored: Any) -> dict[str, Any]:
    """Options do not accept TRAILING_STOP_LOSS. See the options trade page."""
    raise ValueError(
        "TRAILING_STOP_LOSS is not supported for options. "
        "The options trade page lists MARKET, LIMIT, STOP_LOSS, and STOP_LOSS_LIMIT."
    )


def build_option_otoco_orders(**_ignored: Any) -> dict[str, Any]:
    """OTO, OCO, and OTOCO are equity-only."""
    raise ValueError("OTO, OCO, and OTOCO are equity-only and are not supported for options.")


def build_single_option_order(
    *,
    client_order_id: str,
    symbol: str,
    side: str,
    quantity: float,
    strike_price: float,
    option_expire_date: str,
    option_type: str,
    limit_price: Optional[float] = None,
    order_type: str = "LIMIT",
    time_in_force: str = "DAY",
    position_intent: str = "BUY_TO_OPEN",
) -> dict[str, Any]:
    """One US option leg, matching the published single-leg example.

    The payload is for tests and for a later paper path. Nothing here
    calls the network.
    """
    _check_option_id(client_order_id)
    if order_type == "TRAILING_STOP_LOSS":
        raise ValueError("TRAILING_STOP_LOSS is not supported for options")
    if order_type not in {"MARKET", "LIMIT", "STOP_LOSS", "STOP_LOSS_LIMIT"}:
        raise ValueError(f"Unsupported option order type {order_type}")
    if option_type not in {"CALL", "PUT"}:
        raise ValueError("option_type must be CALL or PUT")
    if side not in {"BUY", "SELL"}:
        raise ValueError("side must be BUY or SELL")
    _check_expiry(option_expire_date)
    if order_type in {"LIMIT", "STOP_LOSS_LIMIT"} and limit_price is None:
        raise ValueError(f"{order_type} requires limit_price")
    leg_side = side
    payload: dict[str, Any] = {
        "combo_type": "NORMAL",
        "client_order_id": client_order_id,
        "symbol": symbol,
        "instrument_type": "OPTION",
        "market": "US",
        "order_type": order_type,
        "quantity": _qty(quantity),
        "option_strategy": "SINGLE",
        "side": side,
        "time_in_force": time_in_force,
        "entrust_type": "QTY",
        "position_intent": position_intent,
        "legs": [
            {
                "side": leg_side,
                "quantity": _qty(quantity),
                "symbol": symbol,
                "strike_price": f"{strike_price:.2f}",
                "option_expire_date": option_expire_date,
                "instrument_type": "OPTION",
                "option_type": option_type,
                "market": "US",
            }
        ],
    }
    if limit_price is not None:
        payload["limit_price"] = f"{limit_price:.2f}"
    return payload


def build_bull_call_spread(
    *,
    client_order_id: str,
    symbol: str,
    quantity: float,
    long_strike: float,
    short_strike: float,
    option_expire_date: str,
    limit_price: float,
    time_in_force: str = "DAY",
) -> dict[str, Any]:
    """Bull call debit spread: buy the lower call, sell the higher call.

    ``limit_price`` is the net debit, as in the published VERTICAL example.
    This function does not send the order.
    """
    _check_option_id(client_order_id)
    _check_expiry(option_expire_date)
    if short_strike <= long_strike:
        raise ValueError("A bull call spread sells the higher strike")
    if limit_price <= 0:
        raise ValueError("limit_price is the net debit and must be positive")
    qty = _qty(quantity)
    return {
        "combo_type": "NORMAL",
        "client_order_id": client_order_id,
        "symbol": symbol,
        "instrument_type": "OPTION",
        "market": "US",
        "order_type": "LIMIT",
        "quantity": qty,
        "option_strategy": "VERTICAL",
        "side": "BUY",
        "time_in_force": time_in_force,
        "entrust_type": "QTY",
        "position_intent": "BUY_TO_OPEN",
        "limit_price": f"{limit_price:.2f}",
        "legs": [
            {
                "side": "BUY",
                "quantity": qty,
                "symbol": symbol,
                "strike_price": f"{long_strike:.2f}",
                "option_expire_date": option_expire_date,
                "instrument_type": "OPTION",
                "option_type": "CALL",
                "market": "US",
            },
            {
                "side": "SELL",
                "quantity": qty,
                "symbol": symbol,
                "strike_price": f"{short_strike:.2f}",
                "option_expire_date": option_expire_date,
                "instrument_type": "OPTION",
                "option_type": "CALL",
                "market": "US",
            },
        ],
    }


def _check_option_id(client_order_id: str) -> None:
    if len(client_order_id) > 32:
        raise ValueError("client_order_id must be at most 32 characters")


def _check_expiry(option_expire_date: str) -> None:
    parts = option_expire_date.split("-")
    if len(parts) != 3 or len(parts[0]) != 4 or len(parts[1]) != 2 or len(parts[2]) != 2:
        raise ValueError("option_expire_date must be YYYY-MM-DD")


def new_client_order_id() -> str:
    return uuid.uuid4().hex  # 32 characters


STOCK_ACCOUNT_CLASSES = ("INDIVIDUAL_MARGIN", "INDIVIDUAL_CASH")


def default_token_dir() -> str:
    """Directory for the SDK session token.

    The SDK otherwise writes ``conf/token.txt`` in the working directory.
    ``WEBULL_OPENAPI_TOKEN_DIR`` overrides the default ``~/.webull-openapi-token``.
    """
    override = os.environ.get("WEBULL_OPENAPI_TOKEN_DIR", "").strip()
    if override:
        return str(Path(override).expanduser())
    return str(Path.home() / ".webull-openapi-token")


def configure_sdk_client(api, *, app_key: str = "", app_secret: str = "", token: str = "") -> str:
    """Quiet the official SDK and point its token file outside the repo.

    TradeClient and DataClient install a DEBUG console logger and
    ``webull_trade_sdk.log`` when neither logger flag is set. That DEBUG
    line includes request headers, so the app key is printed in plaintext.
    Both loggers are set to WARNING, and a filter redacts the key, secret,
    and token, before either client is constructed.
    """
    directory = default_token_dir()
    token_path = Path(directory)
    token_path.mkdir(parents=True, exist_ok=True)
    token_path.chmod(0o700)
    os.environ.setdefault("WEBULL_OPENAPI_TOKEN_DIR", directory)
    api.set_token_dir(directory)
    if getattr(api, "_webull_bot_sdk_configured", False):
        return directory
    api.set_stream_logger(log_level=logging.WARNING, logger_name="webull.core")
    api.set_file_logger(
        path=str(Path(directory) / "webull_trade_sdk.log"),
        log_level=logging.WARNING,
        logger_name="webull.core",
    )
    redactor = SdkSecretFilter([app_key, app_secret, token])
    sdk_log = logging.getLogger("webull.core")
    sdk_log.setLevel(logging.WARNING)
    sdk_log.addFilter(redactor)
    for handler in list(sdk_log.handlers):
        handler.setLevel(logging.WARNING)
        handler.addFilter(redactor)
    api._webull_bot_sdk_configured = True
    return directory


def run_initializer_once(api, original) -> None:
    """TradeClient and DataClient each call the SDK initializer.

    That fetches the token config. The second client in one ``connect``
    must not fetch it again.
    """
    if getattr(api, "_webull_bot_client_ready", False):
        return
    original(api)
    api._webull_bot_client_ready = True


def install_single_client_init() -> None:
    try:
        from webull.core.http.initializer.client_initializer import ClientInitializer
    except ImportError:
        return
    if getattr(ClientInitializer, "_webull_bot_deduped", False):
        return
    original = ClientInitializer.initializer

    def initializer(api_client):
        run_initializer_once(api_client, original)

    ClientInitializer.initializer = staticmethod(initializer)
    ClientInitializer._webull_bot_deduped = True


def sandbox_hosts() -> dict[str, str]:
    """HTTP hosts for the Webull paper sandbox.

    Quote streaming is ``data-api.sandbox.webull.com``. The trade and
    events hosts are the ones on the public US getting-started pages.
    """
    return {
        "api": "api.sandbox.webull.com",
        "quotes-api": "data-api.sandbox.webull.com",
        "events-api": "events-api.sandbox.webull.com",
    }


def host_is_sandbox(host: str) -> bool:
    name = str(host).strip().lower()
    if "://" in name:
        name = name.split("://", 1)[1]
    name = name.split("/", 1)[0].split(":", 1)[0]
    return bool(name) and name.endswith(".sandbox.webull.com") and ".." not in name


def assert_sandbox_hosts(hosts) -> None:
    """Refuse any host that is not ``*.sandbox.webull.com``.

    An empty list is also refused. The SDK's own default is
    ``api.webull.com``, and a sandbox session must not fall through to it.
    """
    found = [str(host) for host in hosts]
    if not found:
        raise WebullError(
            "Sandbox mode has no registered hosts. Refusing to fall through to api.webull.com."
        )
    blocked = [host for host in found if not host_is_sandbox(host)]
    if blocked:
        raise WebullError(
            "Sandbox mode refuses hosts that are not *.sandbox.webull.com: " + ", ".join(blocked)
        )


def select_account(
    accounts: list[dict[str, Any]],
    account_id: str = "",
    account_class: str = "INDIVIDUAL_MARGIN",
) -> tuple[str, str]:
    """Pick the internal ``account_id`` and a lowercase cash/margin type.

    ``WEBULL_ACCOUNT_ID`` may be the internal id or the ``DEVxxxx``
    ``account_number``. The number is mapped to the id. Using the number
    as the id returns HTTP 403 ACCOUNT_ACCESS_DENIED. When no id is given,
    the account whose ``account_class`` is ``INDIVIDUAL_MARGIN`` or
    ``INDIVIDUAL_CASH`` is used. Futures, events, and crypto accounts are
    not selected by that default.
    """
    rows = [row for row in accounts if isinstance(row, dict)]
    wanted = (account_id or "").strip()
    if wanted:
        for row in rows:
            internal = str(row.get("account_id") or row.get("accountId") or "")
            number = str(row.get("account_number") or row.get("accountNumber") or "")
            if wanted == internal or wanted == number:
                if not internal:
                    raise WebullError("Account row matched but had no account_id")
                return internal, normalize_account_type(row.get("account_type") or row.get("accountType"))
        raise WebullError(
            "WEBULL_ACCOUNT_ID did not match an account_id or account_number. "
            "Use the internal account_id (about 26 characters). "
            "A DEVxxxx account_number is not the id and returns HTTP 403 ACCOUNT_ACCESS_DENIED."
        )
    preferred = (account_class or "INDIVIDUAL_MARGIN").strip().upper()
    if preferred not in STOCK_ACCOUNT_CLASSES:
        raise WebullError(
            "WEBULL_ACCOUNT_CLASS must be INDIVIDUAL_MARGIN or INDIVIDUAL_CASH. "
            f"Got {preferred or '(empty)'}."
        )
    matches = [
        row
        for row in rows
        if str(row.get("account_class") or row.get("accountClass") or "").upper() == preferred
    ]
    if len(matches) != 1:
        seen = sorted(
            {
                str(row.get("account_class") or row.get("accountClass") or "?")
                for row in rows
            }
        )
        raise WebullError(
            f"Expected one {preferred} account, found {len(matches)}. "
            f"Account classes returned: {', '.join(seen) or '(none)'}. "
            "Set WEBULL_ACCOUNT_ID to the internal account_id, or set "
            "WEBULL_ACCOUNT_CLASS to INDIVIDUAL_MARGIN or INDIVIDUAL_CASH."
        )
    internal = str(matches[0].get("account_id") or matches[0].get("accountId") or "")
    if not internal:
        raise WebullError(f"{preferred} account had no account_id")
    account_type = normalize_account_type(matches[0].get("account_type") or matches[0].get("accountType"))
    return internal, account_type


def normalize_account_type(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {"margin", "individual_margin"}:
        return "margin"
    if text in {"cash", "individual_cash"}:
        return "cash"
    return text


def buying_power_from_balance(payload: dict) -> Optional[float]:
    """Day buying power, then buying power, then overnight, on the USD asset row."""
    assets = payload.get("account_currency_assets")
    if assets is None:
        assets = payload.get("accountCurrencyAssets")
    if isinstance(assets, list) and assets and isinstance(assets[0], dict):
        value = _first_number(
            assets[0],
            "day_buying_power",
            "buying_power",
            "overnight_buying_power",
        )
        if value is not None:
            return value
    return _first_number(payload, "day_buying_power", "buying_power", "buyingPower", "overnight_buying_power")


class WebullBroker(Broker):
    """Live or sandbox trading client. Constructing it does not connect."""

    name = "webull"

    def __init__(
        self,
        app_key: Optional[str] = None,
        app_secret: Optional[str] = None,
        account_id: Optional[str] = None,
        environment: Optional[str] = None,
        region: str = "us",
        account_class: Optional[str] = None,
    ) -> None:
        self.app_key = app_key if app_key is not None else os.environ.get("WEBULL_APP_KEY", "")
        self.app_secret = app_secret if app_secret is not None else os.environ.get("WEBULL_APP_SECRET", "")
        self.account_id = account_id if account_id is not None else os.environ.get("WEBULL_ACCOUNT_ID", "")
        self.account_class = (
            account_class if account_class is not None else os.environ.get("WEBULL_ACCOUNT_CLASS", "INDIVIDUAL_MARGIN")
        )
        self.environment = (environment or os.environ.get("WEBULL_ENV", "sandbox")).lower()
        self.region = (region or os.environ.get("WEBULL_REGION", "us")).lower()
        self.account_type = ""
        self.hosts: list[str] = []
        self.sandbox_only = False
        self._account_rows: list[dict[str, Any]] | None = None
        self._trade = None
        self._data = None
        self._api = None

    @property
    def data_client(self):
        if self._data is None:
            raise WebullError("Webull data client is not connected")
        return self._data

    def connect(self) -> None:
        if not self.app_key or not self.app_secret:
            raise WebullCredentialsError(
                "WEBULL_APP_KEY and WEBULL_APP_SECRET are required. "
                "Generate them at https://www.webull.com/center#openApiManagement "
                "after the API application is approved. They are never read from a committed file."
            )
        try:
            from webull.core.client import ApiClient
            from webull.data.data_client import DataClient
            from webull.trade.trade_client import TradeClient
        except ImportError as exc:
            raise WebullError(
                "Install the official SDK: pip install webull-openapi-python-sdk"
            ) from exc
        kwargs: dict[str, Any] = {}
        # The SDK constructor accepts token-check knobs in current official
        # examples used by Webull's own MCP server. If this version does not,
        # fall back to the three-argument form.
        try:
            api = ApiClient(
                self.app_key,
                self.app_secret,
                self.region,
                token_check_duration_seconds=30,
                token_check_interval_seconds=5,
            )
        except TypeError:
            api = ApiClient(self.app_key, self.app_secret, self.region)
        configure_sdk_client(api, app_key=self.app_key, app_secret=self.app_secret)
        install_single_client_init()
        if self.sandbox_only and self.environment not in {"sandbox", "uat", "test"}:
            raise WebullError(
                "Sandbox paper mode refuses a non-sandbox environment. "
                "Orders are sent only to *.sandbox.webull.com."
            )
        if self.environment in {"sandbox", "uat", "test"}:
            self.hosts = _add_sandbox_endpoints(api, self.region)
        if self.sandbox_only:
            assert_sandbox_hosts(self.hosts)
        self._api = api
        try:
            self._trade = TradeClient(api)
            self._data = DataClient(api)
        except Exception as exc:
            message = str(exc)
            if "TOKEN" in message or "DEVICE" in message or "2FA" in message:
                raise WebullError(
                    "Webull rejected the session before a token was approved. "
                    "The official SDK can require an in-app 2FA / device registration "
                    "on first use. Approve it in the Webull app and retry. "
                    f"Underlying error: {message}"
                ) from exc
            raise
        accounts = self.list_accounts()
        if not accounts:
            raise WebullError("No Webull accounts were returned for these credentials")
        self.account_id, self.account_type = select_account(
            accounts,
            self.account_id,
            self.account_class,
        )

    def list_accounts(self, *, refresh: bool = False) -> list[dict[str, Any]]:
        if self._account_rows is not None and not refresh:
            return self._account_rows
        self._require_trade()
        response = self._trade.account_v2.get_account_list()
        payload = _payload(response)
        if isinstance(payload, list):
            rows = payload
        elif isinstance(payload, dict):
            rows = None
            for key in ("accounts", "data", "items"):
                if isinstance(payload.get(key), list):
                    rows = payload[key]
                    break
            if rows is None:
                raise WebullResponseError(f"Unexpected account list shape: {_keys(payload)}")
        else:
            raise WebullResponseError(f"Unexpected account list shape: {_keys(payload)}")
        self._account_rows = rows
        return rows

    def snapshot(self) -> AccountSnapshot:
        self._require_account()
        response = self._trade.account_v2.get_account_balance(self.account_id)
        payload = _payload(response)
        if not isinstance(payload, dict):
            raise WebullResponseError(f"Unexpected balance shape: {_keys(payload)}")
        equity = _first_number(
            payload,
            "total_net_liquidation_value",
            "net_liquidation",
            "netLiquidation",
            "total_asset",
            "equity",
        )
        cash = _first_number(payload, "total_cash_balance", "cash_balance", "cashBalance", "cash")
        buying_power = buying_power_from_balance(payload)
        if equity is None:
            raise WebullResponseError(f"Balance response had no equity field. Keys: {sorted(payload)}")
        account_type = self.account_type or normalize_account_type(
            payload.get("account_type") or payload.get("accountType")
        )
        if account_type not in {"cash", "margin"}:
            raise WebullResponseError(
                "Account type was not resolved from the account list. "
                "Refusing to assume margin. Keys: " + ", ".join(sorted(payload))
            )
        return AccountSnapshot(
            equity=equity,
            cash=cash if cash is not None else 0.0,
            buying_power=buying_power if buying_power is not None else (cash or 0.0),
            account_type=account_type,
            positions=self.positions(),
            open_orders=self.open_orders(),
        )

    def positions(self) -> list[Position]:
        self._require_account()
        response = self._trade.account_v2.get_account_position(self.account_id)
        payload = _payload(response)
        rows = payload if isinstance(payload, list) else []
        if isinstance(payload, dict):
            for key in ("positions", "data", "items"):
                if isinstance(payload.get(key), list):
                    rows = payload[key]
                    break
        positions: list[Position] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            symbol = str(row.get("symbol") or row.get("ticker") or "")
            quantity = _first_number(row, "quantity", "qty", "position")
            if not symbol or quantity is None or abs(quantity) < 1e-9:
                continue
            avg = _first_number(row, "avg_cost", "avgPrice", "cost_price", "average_cost") or 0.0
            positions.append(
                Position(
                    symbol=symbol,
                    quantity=float(quantity),
                    avg_price=float(avg),
                )
            )
        return positions

    def open_orders(self) -> list[Order]:
        self._require_account()
        response = self._trade.order_v3.get_order_open(account_id=self.account_id, page_size=50)
        return [_order_from_row(row) for row in _rows(response) if isinstance(row, dict)]

    def place_order(self, order: Order) -> Order:
        self._require_account()
        self._guard_sandbox()
        if not order.client_order_id:
            order.client_order_id = new_client_order_id()
        payload = build_equity_order(
            client_order_id=order.client_order_id,
            symbol=order.symbol,
            side=order.side.value,
            order_type=_ORDER_TYPE[order.order_type],
            quantity=order.quantity,
            limit_price=order.limit_price,
            stop_price=order.stop_price,
            time_in_force=order.time_in_force.value,
            trailing_type=order.trail_type,
            trailing_stop_step=order.trail_step,
        )
        response = self._trade.order_v3.place_order(self.account_id, [payload])
        body = _payload(response)
        order.status = OrderStatus.NEW
        order.note = f"submitted keys={_keys(body)}"
        return order

    def option_atm_quote(self, symbol: str, option_type: str, spot: float, as_of) -> Optional[dict]:
        """Expiry closest to 14 DTE and the strike nearest spot. None if the API has no ask."""
        if self._data is None:
            return None
        try:
            from datetime import date as date_cls
            from datetime import timedelta

            from webull_bot.execution.forward_options import FORWARD_DTE
            from webull_bot.execution.option_quote import atm_from_client

            day = as_of if isinstance(as_of, date_cls) else date_cls.fromisoformat(str(as_of)[:10])
            return atm_from_client(self._data, symbol, option_type, float(spot), day + timedelta(days=FORWARD_DTE))
        except Exception:
            return None

    def place_option_order(self, payload: dict) -> dict:
        """One option payload. Sandbox forward test only. Live trading does not call this."""
        self._require_account()
        self._guard_sandbox()
        if payload.get("instrument_type") != "OPTION":
            raise WebullError("place_option_order accepts an option payload only")
        response = self._trade.order_v3.place_order(self.account_id, [payload])
        return _payload(response)

    def cancel_order(self, client_order_id: str) -> None:
        self._require_account()
        self._guard_sandbox()
        self._trade.order_v3.cancel_order(account_id=self.account_id, client_order_id=client_order_id)

    def _guard_sandbox(self) -> None:
        if not self.sandbox_only:
            return
        assert_sandbox_hosts(self.hosts)
        if self.environment not in {"sandbox", "uat", "test"}:
            raise WebullError(
                "Sandbox paper mode refuses a non-sandbox environment. "
                "Orders are sent only to *.sandbox.webull.com."
            )

    def replace_order(
        self,
        client_order_id: str,
        quantity: float,
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
    ) -> None:
        self._require_account()
        self._guard_sandbox()
        modify: dict[str, str] = {"client_order_id": client_order_id, "quantity": _qty(quantity)}
        if limit_price is not None:
            modify["limit_price"] = f"{limit_price:.2f}"
        if stop_price is not None:
            modify["stop_price"] = f"{stop_price:.2f}"
        self._trade.order_v3.replace_order(self.account_id, [modify])

    def flatten(self) -> list[Fill]:
        """Cancel open orders and submit market sells for long stock positions.

        Fills are not invented. The caller polls ``positions`` to see what
        the broker actually closed. Returns an empty list.
        """
        self.cancel_all()
        for position in self.positions():
            if position.quantity <= 0:
                continue
            order = Order(
                client_order_id=new_client_order_id(),
                symbol=position.symbol,
                side=Side.SELL,
                quantity=position.quantity,
                order_type=OrderType.MARKET,
                time_in_force=TimeInForce.DAY,
                strategy="kill_switch",
            )
            self.place_order(order)
        return []

    def _require_trade(self) -> None:
        if self._trade is None:
            raise WebullError("Call connect() before using the Webull broker")

    def _require_account(self) -> None:
        self._require_trade()
        if not self.account_id:
            raise WebullError("WEBULL_ACCOUNT_ID is not set and could not be inferred")


def _add_sandbox_endpoints(api, region: str) -> list[str]:
    """Register sandbox hosts and return the hostnames that were registered.

    Production endpoints come from the SDK's own map. Sandbox does not.
    Quote streaming uses ``data-api.sandbox.webull.com``.
    """
    hosts = sandbox_hosts()
    assert_sandbox_hosts(hosts.values())
    try:
        from webull.core.common.api_type import DEFAULT, EVENTS, QUOTES
    except ImportError:
        DEFAULT = QUOTES = EVENTS = None  # type: ignore
    mapping = {
        DEFAULT: hosts["api"],
        QUOTES: hosts["quotes-api"],
        EVENTS: hosts["events-api"],
    }
    recorded: list[str] = []
    for api_type, host in mapping.items():
        if api_type is None and DEFAULT is None:
            continue
        if api_type is None:
            api.add_endpoint(region, host)
        else:
            try:
                api.add_endpoint(region, host, api_type)
            except TypeError:
                api.add_endpoint(region, host)
        recorded.append(host)
    if not recorded:
        for host in hosts.values():
            api.add_endpoint(region, host)
            recorded.append(host)
    return recorded


def _payload(response: Any) -> Any:
    status = getattr(response, "status_code", None)
    if status is not None and int(status) >= 400:
        text = getattr(response, "text", "")
        raise WebullResponseError(f"Webull HTTP {status}: {text[:400]}")
    if hasattr(response, "json"):
        try:
            return response.json()
        except Exception as exc:
            raise WebullResponseError("Webull response was not JSON") from exc
    return response


def _rows(response: Any) -> list:
    payload = _payload(response)
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("orders", "data", "items", "result"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
    return []


def _order_from_row(row: dict) -> Order:
    side_raw = str(row.get("side") or "BUY").upper()
    type_raw = str(row.get("order_type") or row.get("orderType") or "MARKET").upper()
    type_map = {
        "MARKET": OrderType.MARKET,
        "LIMIT": OrderType.LIMIT,
        "STOP_LOSS": OrderType.STOP,
        "STOP_LOSS_LIMIT": OrderType.STOP_LIMIT,
        "TRAILING_STOP_LOSS": OrderType.TRAILING,
    }
    quantity = _first_number(row, "quantity", "qty") or 0.0
    return Order(
        client_order_id=str(row.get("client_order_id") or row.get("clientOrderId") or ""),
        symbol=str(row.get("symbol") or ""),
        side=Side.SELL if side_raw == "SELL" else Side.BUY,
        quantity=float(quantity),
        order_type=type_map.get(type_raw, OrderType.MARKET),
        status=OrderStatus.NEW,
        limit_price=_first_number(row, "limit_price", "limitPrice"),
        stop_price=_first_number(row, "stop_price", "stopPrice"),
        trail_type=(str(row.get("trailing_type") or row.get("trailingType") or "") or None),
        trail_step=_first_number(row, "trailing_stop_step", "trailingStopStep"),
    )


def _first_number(row: dict, *keys: str) -> Optional[float]:
    for key in keys:
        if key in row and row[key] is not None and row[key] != "":
            try:
                return float(row[key])
            except (TypeError, ValueError):
                continue
    return None


def _trail_step(step: float | str | None) -> str:
    if step is None or step == "":
        raise ValueError("TRAILING_STOP_LOSS requires trailing_stop_step")
    if isinstance(step, str):
        text = step.strip()
        if not text:
            raise ValueError("TRAILING_STOP_LOSS requires trailing_stop_step")
        return text
    value = float(step)
    if value <= 0 or value != value or value == float("inf"):
        raise ValueError("trailing_stop_step must be positive")
    return f"{value:.4f}".rstrip("0").rstrip(".")


def _qty(quantity: float) -> str:
    if float(quantity).is_integer():
        return str(int(quantity))
    return f"{quantity:.4f}".rstrip("0").rstrip(".")


def _keys(payload: Any) -> str:
    if isinstance(payload, dict):
        return ",".join(sorted(str(key) for key in payload))
    return type(payload).__name__
