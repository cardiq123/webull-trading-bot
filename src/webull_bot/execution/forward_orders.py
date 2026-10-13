"""Option order style for the sandbox forward books.

``FORWARD_OPTION_MARKET`` defaults off. Unset, ``0``, ``false``, ``no``, and
``off`` keep a limit. ``1``, ``true``, ``yes``, and ``on`` send ``MARKET``
and omit ``limit_price``.

The Trading API FAQ lists options as ``LIMIT``, ``STOP_LOSS``, and
``STOP_LOSS_LIMIT``, and says ``MARKET`` is not supported. The options
markdown page lists ``MARKET``. The Python SDK posts the payload and does
not reject ``MARKET`` locally. This flag is the switch. A rejected market
order is not sent again as a market order. Live trading stays off.
"""

from __future__ import annotations

import os
from typing import Optional

ENV = "FORWARD_OPTION_MARKET"
_ON = {"1", "true", "yes", "on"}


def market_orders_enabled() -> bool:
    return os.environ.get(ENV, "").strip().lower() in _ON


def style_option_payload(payload: dict) -> dict:
    """Limit unless the flag is on. A market payload has no limit price."""
    if not market_orders_enabled():
        payload["order_type"] = "LIMIT"
        return payload
    payload["order_type"] = "MARKET"
    payload.pop("limit_price", None)
    return payload


def limit_fallback_payload(payload: dict, limit: float) -> dict:
    """One limit order after the sandbox rejects MARKET. New client id."""
    from webull_bot.broker.webull import new_client_order_id

    out = dict(payload)
    out["order_type"] = "LIMIT"
    out["limit_price"] = f"{float(limit):.2f}"
    out["client_order_id"] = new_client_order_id()
    return out


def sent_clause(limit: float) -> str:
    if market_orders_enabled():
        return "MARKET, not a fill. Fill is pending until order detail."
    return f"Limit {limit:.2f}, not a fill. Fill is pending until order detail."


def remember_quote(order: dict) -> None:
    """Keep the ask or bid from the moment the order was sent."""
    side = str(order.get("side") or "").upper()
    order["quote_side"] = "bid" if side == "SELL" else "ask"
    quote = order.get("sandbox_price")
    if quote not in (None, ""):
        order["quote_px"] = quote


def attach_slippage(order: dict) -> Optional[str]:
    """Fill versus the quote stored at send. Empty until both prices exist.

    A buy's slippage is fill minus the ask. A sell's slippage is the bid
    minus the fill. Positive means the fill was worse than that quote.
    """
    if order.get("slippage_line") or str(order.get("settlement") or "") == "expiry":
        return None
    fill = _positive(order.get("fill"))
    quote = _positive(order.get("quote_px") if order.get("quote_px") not in (None, "") else order.get("sandbox_price"))
    if fill is None or quote is None:
        return None
    side = str(order.get("side") or "").upper()
    versus = str(order.get("quote_side") or ("bid" if side == "SELL" else "ask"))
    if side == "SELL" or versus == "bid":
        slip = quote - fill
        versus = "bid"
    else:
        slip = fill - quote
        versus = "ask"
    order["slippage"] = round(slip, 4)
    text = (
        f"Fill vs quote: {side.lower() or 'order'} fill {fill:.4f} against {versus} {quote:.4f}. "
        f"Slippage {slip:+.4f} per share."
    )
    order["slippage_line"] = text
    return text


def _positive(value) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number <= 0:
        return None
    return number
