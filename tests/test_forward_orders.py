"""Market-order flag, rejection fallback, and fill-versus-quote slippage."""

from webull_bot.broker.webull import build_single_option_order
from webull_bot.execution.forward_orders import attach_slippage, market_orders_enabled, style_option_payload
from webull_bot.execution.forward_vwap import _place


SECRET = "super-secret-value"


def _payload(limit: float = 0.50) -> dict:
    return build_single_option_order(
        client_order_id="entry-1",
        symbol="SPY",
        side="BUY",
        quantity=1,
        strike_price=745.0,
        option_expire_date="2026-10-13",
        option_type="PUT",
        limit_price=limit,
        order_type="LIMIT",
        position_intent="BUY_TO_OPEN",
    )


def test_the_flag_defaults_off(monkeypatch):
    monkeypatch.delenv("FORWARD_OPTION_MARKET", raising=False)
    assert market_orders_enabled() is False
    payload = style_option_payload(_payload())
    assert payload["order_type"] == "LIMIT"
    assert payload["limit_price"] == "0.50"


def test_the_flag_drops_the_limit_price(monkeypatch):
    monkeypatch.setenv("FORWARD_OPTION_MARKET", "1")
    payload = style_option_payload(_payload())
    assert payload["order_type"] == "MARKET"
    assert "limit_price" not in payload


def test_a_rejected_market_buy_is_sent_once_as_a_limit(monkeypatch):
    monkeypatch.setenv("FORWARD_OPTION_MARKET", "1")

    class Broker:
        def __init__(self):
            self.orders = []

        def place_option_order(self, payload):
            self.orders.append(dict(payload))
            if payload.get("order_type") == "MARKET":
                raise RuntimeError(f"UNSUPPORTED_ORDER_TYPE app_secret={SECRET}")

    broker = Broker()
    order = {
        "id": "entry-1",
        "side": "BUY",
        "limit": "0.50",
        "sandbox_price": "0.4900",
        "status": "intent",
    }
    lines = []
    assert _place(broker, _payload(), order, lines, "entry") is True
    text = "\n".join(lines)
    assert "UNSUPPORTED_ORDER_TYPE" in text
    assert SECRET not in text
    assert "[redacted]" in text
    assert "Sending the marketable limit" in text
    assert [row["order_type"] for row in broker.orders] == ["MARKET", "LIMIT"]
    assert "limit_price" not in broker.orders[0]
    assert broker.orders[1]["limit_price"] == "0.50"
    assert order["order_type"] == "LIMIT"
    assert order["id"] == broker.orders[1]["client_order_id"]
    assert order["id"] != "entry-1"
    assert order["market_rejected"] is True
    assert order["quote_side"] == "ask"
    assert order["quote_px"] == "0.4900"


def test_fill_slippage_is_the_fill_minus_the_quoted_ask():
    buy = {"side": "BUY", "fill": 0.48, "quote_side": "ask", "quote_px": "0.4500"}
    line = attach_slippage(buy)
    assert line is not None
    assert "fill 0.4800 against ask 0.4500" in line
    assert "Slippage +0.0300" in line
    assert attach_slippage(buy) is None

    sell = {"side": "SELL", "fill": 0.20, "sandbox_price": "0.2500"}
    sold = attach_slippage(sell)
    assert sold is not None
    assert "against bid 0.2500" in sold
    assert "Slippage +0.0500" in sold

    expiry = {"side": "SELL", "fill": 0, "settlement": "expiry", "quote_px": "0.2500"}
    assert attach_slippage(expiry) is None
