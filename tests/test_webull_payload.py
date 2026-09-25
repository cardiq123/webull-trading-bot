import pytest

from webull_bot.broker.webull import WebullCredentialsError, build_equity_order, new_client_order_id


def test_equity_order_matches_the_published_fields():
    payload = build_equity_order(
        client_order_id="a" * 32,
        symbol="AAPL",
        side="BUY",
        order_type="LIMIT",
        quantity=1,
        limit_price=180,
    )
    assert payload["combo_type"] == "NORMAL"
    assert payload["instrument_type"] == "EQUITY"
    assert payload["market"] == "US"
    assert payload["order_type"] == "LIMIT"
    assert payload["time_in_force"] == "DAY"
    assert payload["entrust_type"] == "QTY"
    assert payload["support_trading_session"] == "CORE"
    assert payload["limit_price"] == "180.00"
    assert payload["quantity"] == "1"
    assert "stop_price" not in payload


def test_stop_order_requires_a_stop_and_client_id_is_32_chars():
    with pytest.raises(ValueError):
        build_equity_order(
            client_order_id="x" * 32,
            symbol="AAPL",
            side="SELL",
            order_type="STOP_LOSS",
            quantity=2,
        )
    payload = build_equity_order(
        client_order_id=new_client_order_id(),
        symbol="SPY",
        side="SELL",
        order_type="STOP_LOSS",
        quantity=3,
        stop_price=500.5,
    )
    assert len(payload["client_order_id"]) == 32
    assert payload["stop_price"] == "500.50"
    assert payload["order_type"] == "STOP_LOSS"


def test_missing_credentials_fail_before_any_order(monkeypatch):
    monkeypatch.delenv("WEBULL_APP_KEY", raising=False)
    monkeypatch.delenv("WEBULL_APP_SECRET", raising=False)
    from webull_bot.broker.webull import WebullBroker

    broker = WebullBroker(app_key="", app_secret="")
    with pytest.raises(WebullCredentialsError):
        broker.connect()
