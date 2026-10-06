"""Paper plans for the chart-read exits. This module does not send orders.

Equity trails and brackets are native Webull payloads. Options are not.
The options trade page has no trailing stop and no OTO, OCO, or OTOCO.
A single-leg option stop is a premium price, and these exits are prices
on the underlying, so the bot watches the stock and closes the option
when that watch hits. Live trading stays off. The dual-momentum cycle
does not call this.
"""

from __future__ import annotations

from typing import Any, Optional

from webull_bot.broker.paper import PaperBroker
from webull_bot.broker.webull import (
    build_bracket_orders,
    build_equity_order,
    build_trailing_stop_order,
    new_client_order_id,
)
from webull_bot.models import Order, OrderType, Side


def plan_chart_exit(
    *,
    instrument: str,
    style: str,
    symbol: str,
    quantity: float,
    direction: str = "long",
    stop_price: Optional[float] = None,
    take_profit: Optional[float] = None,
    trail_type: Optional[str] = None,
    trail_step: Optional[float] = None,
) -> dict[str, Any]:
    """Build the order that would be sent. ``style`` is bracket, trail, or hybrid.

    A level target and a fixed R target are both brackets. The hybrid is a
    half-size limit plus a half-size DAY trail. The split, the time stop,
    and any multi-day renewal are bot-managed.
    """
    if instrument not in {"equity", "option"}:
        raise ValueError("instrument must be equity or option")
    if style not in {"bracket", "trail", "hybrid"}:
        raise ValueError("style must be bracket, trail, or hybrid")
    if direction not in {"long", "short"}:
        raise ValueError("direction must be long or short")
    if instrument == "option":
        return _bot_plan(
            style,
            symbol,
            quantity,
            direction,
            stop_price,
            take_profit,
            trail_type,
            trail_step,
            "option",
            "Option trailing stops and OTO, OCO, and OTOCO are not in the options trade API. "
            "A single-leg option stop would be a premium, and this exit is a price on the underlying. "
            "The bot watches the stock and closes the option when that watch hits. No option order is sent.",
        )
    if direction == "short":
        return _bot_plan(
            style,
            symbol,
            quantity,
            direction,
            stop_price,
            take_profit,
            trail_type,
            trail_step,
            "equity",
            "The paper book is long-only. A short exit is watched by the bot. "
            "The equity payload for a long bracket or trail is what the API accepts.",
        )
    if style == "bracket":
        if stop_price is None or take_profit is None:
            raise ValueError("A bracket needs stop_price and take_profit")
        combo = build_bracket_orders(
            symbol=symbol,
            quantity=quantity,
            take_profit=take_profit,
            stop_loss=stop_price,
            direction=direction,
        )
        return {
            "native": True,
            "management": "broker",
            "instrument": "equity",
            "style": style,
            "client_combo_order_id": combo["client_combo_order_id"],
            "payloads": combo["new_orders"],
            "note": (
                "Equity bracket is MASTER plus STOP_PROFIT plus STOP_LOSS, not OTOCO. "
                "The legs are DAY orders. A multi-day hold is renewed by the bot."
            ),
        }
    if style == "trail":
        if trail_type not in {"AMOUNT", "PERCENTAGE"} or trail_step is None:
            raise ValueError("A trail needs trail_type AMOUNT or PERCENTAGE and trail_step")
        payload = build_trailing_stop_order(
            client_order_id=new_client_order_id(),
            symbol=symbol,
            side="SELL" if direction == "long" else "BUY",
            quantity=quantity,
            trailing_type=trail_type,
            trailing_stop_step=trail_step,
        )
        return {
            "native": True,
            "management": "broker",
            "instrument": "equity",
            "style": style,
            "payloads": [payload],
            "note": "Equity trailing stop is DAY only. The bot renews it for a multi-day hold.",
        }
    if stop_price is None or take_profit is None or trail_type not in {"AMOUNT", "PERCENTAGE"} or trail_step is None:
        raise ValueError("A hybrid needs a target, a stop, and a trail step")
    half = quantity / 2.0
    limit_id = new_client_order_id()
    trail = build_trailing_stop_order(
        client_order_id=new_client_order_id(),
        symbol=symbol,
        side="SELL",
        quantity=half,
        trailing_type=trail_type,
        trailing_stop_step=trail_step,
    )
    limit = build_equity_order(
        client_order_id=limit_id,
        symbol=symbol,
        side="SELL",
        order_type="LIMIT",
        quantity=half,
        limit_price=take_profit,
        time_in_force="DAY",
    )
    return {
        "native": True,
        "management": "bot",
        "instrument": "equity",
        "style": style,
        "payloads": [limit, trail],
        "stop_price": float(stop_price),
        "note": (
            "The half-size limit and the half-size DAY trail are native equity orders. "
            "The split, the original stop, and renewing the trail are bot-managed. "
            "One option contract cannot be split, so that position exits in full at the target."
        ),
    }


def _bot_plan(
    style, symbol, quantity, direction, stop_price, take_profit, trail_type, trail_step, instrument, note
) -> dict[str, Any]:
    return {
        "native": False,
        "management": "bot",
        "instrument": instrument,
        "style": style,
        "symbol": symbol,
        "quantity": float(quantity),
        "direction": direction,
        "payloads": [],
        "watch": {
            "underlying_stop": stop_price,
            "underlying_target": take_profit,
            "trail_type": trail_type,
            "trail_step": trail_step,
        },
        "note": note,
    }


def stage_on_paper(broker: PaperBroker, plan: dict[str, Any], *, peak: Optional[float] = None) -> list[Order]:
    """Rest the exit on the paper broker. Refuses any other broker. No network."""
    if not isinstance(broker, PaperBroker):
        raise TypeError("Chart exits are staged on the paper broker only. Live trading stays off.")
    if not plan.get("native"):
        return []
    staged: list[Order] = []
    for payload in plan.get("payloads") or []:
        if payload.get("combo_type") == "MASTER":
            continue
        order = _order_from_payload(payload, peak)
        if order is None:
            continue
        staged.append(broker.place_order(order))
    return staged


def _order_from_payload(payload: dict, peak: Optional[float]) -> Optional[Order]:
    order_type = str(payload.get("order_type"))
    side = Side(str(payload.get("side")))
    if side != Side.SELL:
        return None
    quantity = float(payload["quantity"])
    if order_type == "TRAILING_STOP_LOSS":
        return Order(
            client_order_id=str(payload["client_order_id"]),
            symbol=str(payload["symbol"]),
            side=side,
            quantity=quantity,
            order_type=OrderType.TRAILING,
            trail_type=str(payload["trailing_type"]),
            trail_step=float(payload["trailing_stop_step"]),
            trail_peak=peak,
            strategy="chart_exit",
        )
    if order_type == "LIMIT":
        return Order(
            client_order_id=str(payload["client_order_id"]),
            symbol=str(payload["symbol"]),
            side=side,
            quantity=quantity,
            order_type=OrderType.LIMIT,
            limit_price=float(payload["limit_price"]),
            strategy="chart_exit",
        )
    if order_type == "STOP_LOSS":
        return Order(
            client_order_id=str(payload["client_order_id"]),
            symbol=str(payload["symbol"]),
            side=side,
            quantity=quantity,
            order_type=OrderType.STOP,
            stop_price=float(payload["stop_price"]),
            strategy="chart_exit",
        )
    return None
