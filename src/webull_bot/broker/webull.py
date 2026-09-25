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
* US equity order types used here: MARKET, LIMIT, STOP_LOSS, STOP_LOSS_LIMIT.
  MARKET_ON_OPEN / MARKET_ON_CLOSE are documented as institutional-only and
  are not sent.
* A protective stop is a separate STOP_LOSS sell, not an OTO combo. Combo
  orders exist in the API and are intentionally not required for the first
  live path.

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
* The single-symbol history endpoint's lookback is whatever the server
  returns. The public example does not document a start date.

Nothing in this module places an order at import time.
"""

from __future__ import annotations

import os
import uuid
from typing import Any, Optional

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
    return payload


def new_client_order_id() -> str:
    return uuid.uuid4().hex  # 32 characters


class WebullBroker:
    """Live or sandbox trading client. Constructing it does not connect."""

    name = "webull"

    def __init__(
        self,
        app_key: Optional[str] = None,
        app_secret: Optional[str] = None,
        account_id: Optional[str] = None,
        environment: Optional[str] = None,
        region: str = "us",
    ) -> None:
        self.app_key = app_key if app_key is not None else os.environ.get("WEBULL_APP_KEY", "")
        self.app_secret = app_secret if app_secret is not None else os.environ.get("WEBULL_APP_SECRET", "")
        self.account_id = account_id if account_id is not None else os.environ.get("WEBULL_ACCOUNT_ID", "")
        self.environment = (environment or os.environ.get("WEBULL_ENV", "sandbox")).lower()
        self.region = (region or os.environ.get("WEBULL_REGION", "us")).lower()
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
        if self.environment in {"sandbox", "uat", "test"}:
            _add_sandbox_endpoints(api, self.region)
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
        if not self.account_id:
            accounts = self.list_accounts()
            if len(accounts) == 1:
                self.account_id = str(accounts[0].get("account_id") or accounts[0].get("accountId") or "")
            elif not accounts:
                raise WebullError("No Webull accounts were returned for these credentials")

    def list_accounts(self) -> list[dict[str, Any]]:
        self._require_trade()
        response = self._trade.account_v2.get_account_list()
        payload = _payload(response)
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            for key in ("accounts", "data", "items"):
                if isinstance(payload.get(key), list):
                    return payload[key]
        raise WebullResponseError(f"Unexpected account list shape: {_keys(payload)}")

    def snapshot(self) -> AccountSnapshot:
        self._require_account()
        response = self._trade.account_v2.get_account_balance(self.account_id)
        payload = _payload(response)
        if not isinstance(payload, dict):
            raise WebullResponseError(f"Unexpected balance shape: {_keys(payload)}")
        equity = _first_number(payload, "net_liquidation", "netLiquidation", "total_asset", "equity")
        cash = _first_number(payload, "cash_balance", "cashBalance", "cash")
        buying_power = _first_number(payload, "buying_power", "buyingPower", "day_buying_power")
        if equity is None:
            raise WebullResponseError(f"Balance response had no equity field. Keys: {sorted(payload)}")
        return AccountSnapshot(
            equity=equity,
            cash=cash if cash is not None else 0.0,
            buying_power=buying_power if buying_power is not None else (cash or 0.0),
            account_type="margin",
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
        )
        response = self._trade.order_v3.place_order(self.account_id, [payload])
        body = _payload(response)
        order.status = OrderStatus.NEW
        order.note = f"submitted keys={_keys(body)}"
        return order

    def cancel_order(self, client_order_id: str) -> None:
        self._require_account()
        self._trade.order_v3.cancel_order(account_id=self.account_id, client_order_id=client_order_id)

    def replace_order(self, client_order_id: str, quantity: float, limit_price: Optional[float] = None) -> None:
        self._require_account()
        modify: dict[str, str] = {"client_order_id": client_order_id, "quantity": _qty(quantity)}
        if limit_price is not None:
            modify["limit_price"] = f"{limit_price:.2f}"
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


def _add_sandbox_endpoints(api, region: str) -> None:
    """Register sandbox hosts.

    Production endpoints come from the SDK's own map. Sandbox does not.
    The hosts below are the ones in the public US getting-started pages.
    """
    try:
        from webull.core.common.api_type import DEFAULT, EVENTS, QUOTES
    except ImportError:
        DEFAULT = QUOTES = EVENTS = None  # type: ignore
    hosts = {
        DEFAULT: "api.sandbox.webull.com",
        QUOTES: "api.sandbox.webull.com",
        EVENTS: "events-api.sandbox.webull.com",
    }
    for api_type, host in hosts.items():
        if api_type is None:
            api.add_endpoint(region, host)
        else:
            try:
                api.add_endpoint(region, host, api_type)
            except TypeError:
                api.add_endpoint(region, host)


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
    )


def _first_number(row: dict, *keys: str) -> Optional[float]:
    for key in keys:
        if key in row and row[key] is not None and row[key] != "":
            try:
                return float(row[key])
            except (TypeError, ValueError):
                continue
    return None


def _qty(quantity: float) -> str:
    if float(quantity).is_integer():
        return str(int(quantity))
    return f"{quantity:.4f}".rstrip("0").rstrip(".")


def _keys(payload: Any) -> str:
    if isinstance(payload, dict):
        return ",".join(sorted(str(key) for key in payload))
    return type(payload).__name__
