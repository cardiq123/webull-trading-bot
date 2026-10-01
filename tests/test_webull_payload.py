import pytest

from webull_bot.broker.webull import (
    WebullCredentialsError,
    build_bull_call_spread,
    build_equity_order,
    build_single_option_order,
    new_client_order_id,
)


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


def test_single_call_matches_the_published_option_fields():
    payload = build_single_option_order(
        client_order_id="b" * 32,
        symbol="AAPL",
        side="BUY",
        quantity=1,
        strike_price=220,
        option_expire_date="2026-06-19",
        option_type="CALL",
        limit_price=11.25,
    )
    assert payload["instrument_type"] == "OPTION"
    assert payload["option_strategy"] == "SINGLE"
    assert payload["combo_type"] == "NORMAL"
    assert payload["market"] == "US"
    assert payload["order_type"] == "LIMIT"
    assert payload["position_intent"] == "BUY_TO_OPEN"
    assert payload["limit_price"] == "11.25"
    assert payload["time_in_force"] == "DAY"
    leg = payload["legs"][0]
    assert leg["option_type"] == "CALL"
    assert leg["strike_price"] == "220.00"
    assert leg["option_expire_date"] == "2026-06-19"
    assert leg["side"] == "BUY"
    assert "TRAILING" not in payload["order_type"]


def test_bull_call_spread_is_a_vertical_debit():
    payload = build_bull_call_spread(
        client_order_id="c" * 32,
        symbol="AAPL",
        quantity=1,
        long_strike=180,
        short_strike=190,
        option_expire_date="2026-06-19",
        limit_price=3.5,
    )
    assert payload["option_strategy"] == "VERTICAL"
    assert payload["side"] == "BUY"
    assert payload["position_intent"] == "BUY_TO_OPEN"
    assert payload["limit_price"] == "3.50"
    buy, sell = payload["legs"]
    assert buy["side"] == "BUY" and buy["strike_price"] == "180.00"
    assert sell["side"] == "SELL" and sell["strike_price"] == "190.00"
    assert buy["option_expire_date"] == sell["option_expire_date"]
    assert buy["option_type"] == sell["option_type"] == "CALL"
    with pytest.raises(ValueError):
        build_bull_call_spread(
            client_order_id="c" * 32,
            symbol="AAPL",
            quantity=1,
            long_strike=190,
            short_strike=180,
            option_expire_date="2026-06-19",
            limit_price=3.5,
        )


def test_missing_credentials_fail_before_any_order(monkeypatch):
    monkeypatch.delenv("WEBULL_APP_KEY", raising=False)
    monkeypatch.delenv("WEBULL_APP_SECRET", raising=False)
    from webull_bot.broker.webull import WebullBroker

    broker = WebullBroker(app_key="", app_secret="")
    with pytest.raises(WebullCredentialsError):
        broker.connect()
