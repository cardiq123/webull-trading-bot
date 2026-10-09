"""Read sandbox order detail for a forward book. This module does not trade.

``reconcile_book`` queries order detail and account positions, then writes
the status it read. It does not place an order and it does not cancel one.
The exit chase is separate: a later cycle may replace a sell that is still
working. A limit price is never stored as a fill.
"""

from __future__ import annotations

import os
from datetime import date, datetime, time
from typing import Any, Optional
from zoneinfo import ZoneInfo

from webull_bot.calendar import to_ny

NY = ZoneInfo("America/New_York")
# A working sell is repriced after this long. The 15:45 flatten uses the shorter wait.
EXIT_REPRICE_AFTER_S = 45.0
FLATTEN_REPRICE_AFTER_S = 15.0
FLAT_AT = time(15, 45)
EXPIRED_AT = time(16, 5)

_FILL_KEYS = ("avg_filled_price", "filled_price", "avg_price", "fill_price", "average_price")
_STATUS_KEYS = ("status", "order_status", "orderStatus")
_FILLED_QTY_KEYS = ("filled_quantity", "filledQuantity", "filled_qty", "filledQty")
_TOTAL_QTY_KEYS = ("total_quantity", "totalQuantity", "quantity", "qty", "entrust_quantity")
_TIME_KEYS = ("filled_time", "fill_time", "filled_at", "transaction_time", "last_filled_time")
_LIMIT_KEYS = {"limit_price", "limit", "lmt_price", "lmtPrice", "price"}
_FILLED = {"filled", "fill", "all_filled"}
_PARTIAL = {"partial", "partial_filled", "partially_filled"}
_CANCELLED = {"cancelled", "canceled", "pending_cancel"}
_EXPIRED = {"expired"}
_REJECTED = {"rejected", "failed"}
_WORKING = {"submitted", "pending", "working", "new", "pending_submit", "pending_new"}


def require_sandbox() -> None:
    """Refuse anything except the sandbox environment. Live trading stays off."""
    raw = os.environ.get("WEBULL_ENV", "").strip().lower()
    if raw not in {"sandbox", "uat", "test"}:
        raise SystemExit(
            "Refusing to reconcile without WEBULL_ENV=sandbox. "
            "This command only reads *.sandbox.webull.com. "
            "It does not place or cancel an order. Live trading stays off."
        )


def limit_fill_text(limit, fill) -> str:
    """Say the limit and the fill as two different numbers."""
    shown = "n/a" if limit in (None, "") else limit
    if fill in (None, ""):
        return f"Limit {shown}, not a fill. Fill pending."
    return f"Limit {shown}, not a fill. Fill {fill}."


def order_needs_detail(order: dict) -> bool:
    """True when this journaled order still has no final fill or terminal status."""
    if not isinstance(order, dict):
        return False
    if _known(order.get("fill")) is not None:
        return False
    status = str(order.get("status") or "")
    broker = str(order.get("broker_status") or "")
    if status in {"cancelled", "canceled", "expired", "rejected"} or broker in _CANCELLED | _EXPIRED | _REJECTED:
        return False
    if broker == "partial" or status == "partial":
        return True
    return status in {"submitted", "intent"} or broker in {"working", "filled_no_price"}


def parse_order_detail(payload: Any) -> dict:
    """Status and average fill. A limit price in the payload is ignored."""
    found = {"price": None, "time": None, "status": None, "filled_qty": None, "total_qty": None}
    _walk(payload, found)
    return _classify(found)


def read_order_detail(broker, client_order_id: str) -> dict:
    """One order-detail read. An error becomes ``kind=error`` and the text is dropped."""
    if not client_order_id or broker is None:
        return {"kind": "unknown"}
    trade = getattr(broker, "_trade", None)
    account = getattr(broker, "account_id", None)
    method = getattr(getattr(trade, "order_v3", None), "get_order_detail", None)
    if method is None or not account:
        return {"kind": "unknown"}
    try:
        from webull_bot.execution.forward_quotes import _call

        payload = _call(method, account, client_order_id)
    except Exception:
        return {"kind": "error"}
    parsed = parse_order_detail(payload)
    return parsed


def apply_order_detail(order: dict, detail: dict) -> None:
    """Store the broker status. The limit already on the order is left as the limit."""
    kind = str(detail.get("kind") or "unknown")
    if kind in {"unknown", "error"}:
        return
    order["broker_status"] = kind
    if detail.get("time"):
        order["fill_time"] = detail.get("time")
    filled_qty = detail.get("filled_qty")
    if filled_qty is not None:
        order["filled_qty"] = filled_qty
    if kind == "filled":
        price = _known(detail.get("price"))
        if price is not None:
            order["fill"] = price
        return
    if kind == "partial":
        price = _known(detail.get("price"))
        if price is not None:
            order["partial_fill"] = price
        return
    if kind in {"cancelled", "expired", "rejected"}:
        price = _known(detail.get("price"))
        if price is not None and detail.get("filled_qty"):
            order["partial_fill"] = price
            order["filled_qty"] = detail.get("filled_qty")
        return


def apply_pending_details(state: dict, broker) -> list[str]:
    """Read every journaled order that still has no final result. Read only."""
    lines = []
    for order in state.get("orders") or []:
        if not isinstance(order, dict) or not order_needs_detail(order):
            continue
        detail = read_order_detail(broker, str(order.get("id") or ""))
        kind = str(detail.get("kind") or "unknown")
        if kind == "error":
            lines.append(
                f"{order.get('side')} {order.get('qty')} {order.get('right')} "
                "order detail was not read. The reason was not printed. "
                + limit_fill_text(order.get("limit"), order.get("fill"))
            )
            continue
        if kind == "unknown":
            continue
        apply_order_detail(order, detail)
        _stamp_fill_row(state, order)
        lines.append(_detail_line(order, detail))
    return lines


def read_holdings(broker) -> list[dict]:
    """Option and equity rows the sandbox account currently holds. Read only."""
    if broker is None:
        return []
    trade = getattr(broker, "_trade", None)
    account = getattr(broker, "account_id", None)
    method = getattr(getattr(trade, "account_v2", None), "get_account_position", None)
    payload = None
    if method is not None and account:
        try:
            from webull_bot.execution.forward_quotes import _call

            payload = _call(method, account)
        except Exception:
            payload = None
    rows = _position_rows(payload)
    if rows:
        return rows
    positions = getattr(broker, "positions", None)
    if not callable(positions):
        return []
    try:
        held = positions()
    except Exception:
        return []
    found = []
    for row in held or []:
        symbol = str(getattr(row, "symbol", "") or "")
        quantity = getattr(row, "quantity", None)
        if symbol and quantity not in (None, 0, 0.0):
            found.append({"symbol": symbol.upper(), "quantity": quantity})
    return found


def contract_for(state: dict, order: dict) -> str:
    """OCC symbol for this order, from the journal, not from a new quote."""
    explicit = str(order.get("option_symbol") or "")
    if explicit:
        return explicit.upper()
    signal_id = _signal_id(str(order.get("key") or ""))
    for source in _related(state, signal_id):
        explicit = str(source.get("option_symbol") or source.get("order_symbol") or source.get("contract") or "")
        if explicit:
            return explicit.upper()
        built = _occ_from(source, str(order.get("symbol") or source.get("symbol") or ""))
        if built:
            return built
    return ""


def holdings_lines(state: dict, holdings: list[dict], orders: list[dict]) -> list[str]:
    lines = ["Sandbox account positions, read only. No order was placed or cancelled."]
    if not holdings:
        lines.append("- The account list is empty.")
    for row in holdings:
        lines.append(f"- {row.get('symbol')} quantity {row.get('quantity')}")
    if not orders:
        lines.append("No pending order to match against the account.")
        return lines
    for order in orders:
        contract = contract_for(state, order)
        if not contract:
            lines.append(
                f"{order.get('side')} {order.get('qty')} {order.get('key')}: "
                "the journal has no contract symbol. Compare the account list above."
            )
            continue
        still = _held(contract, holdings)
        if still:
            lines.append(f"{contract}: the sandbox account still holds {still}.")
        else:
            lines.append(f"{contract}: the sandbox account does not hold this contract.")
    return lines


def reconcile_book(journal, broker, book: str, now: datetime) -> list[str]:
    """Read pending orders for one book and store the status. Does not trade."""
    state, stake = _load(journal, book)
    lines = [
        f"Forward reconcile {book}. Sandbox read only. Live trading stays off.",
        "This command does not place an order and does not cancel an order.",
    ]
    pending = [order for order in (state.get("orders") or []) if isinstance(order, dict) and order_needs_detail(order)]
    if not pending:
        lines.append("No journaled order is waiting on a fill.")
    lines.extend(apply_pending_details(state, broker))
    from webull_bot.execution.forward_cash import prepare_cash

    prepare_cash(state, None, stake, to_ny(now).date())
    holdings = read_holdings(broker)
    lines.extend(holdings_lines(state, holdings, pending or [order for order in (state.get("orders") or []) if isinstance(order, dict)]))
    _save(journal, book, state)
    lines.append("Reconcile stored the status it read. No order was sent.")
    return lines


def chase_exit_orders(state: dict, broker, now: datetime, lines: list[str]) -> bool:
    """Re-read a working sell and reprice it when it is still open.

    A contract whose expiry has passed is not replaced and is not resent.
    The first cycle that submits the sell is not repriced: the wait is
    ``EXIT_REPRICE_AFTER_S``, or ``FLATTEN_REPRICE_AFTER_S`` from 15:45.
    """
    if broker is None or not isinstance(state, dict):
        return False
    changed = False
    for order in list(state.get("orders") or []):
        if not isinstance(order, dict) or order.get("kind") != "exit":
            continue
        if str(order.get("status") or "") not in {"submitted", "partial"}:
            continue
        if _known(order.get("fill")) is not None:
            continue
        detail = read_order_detail(broker, str(order.get("id") or ""))
        kind = str(detail.get("kind") or "unknown")
        if kind in {"error", "unknown"}:
            if kind == "error":
                lines.append(
                    "Exit order detail was not read. The reason was not printed. "
                    + limit_fill_text(order.get("limit"), None)
                )
            continue
        if kind not in {"unknown"}:
            apply_order_detail(order, detail)
            _stamp_fill_row(state, order)
            changed = True
            lines.append(_detail_line(order, detail))
        if _known(order.get("fill")) is not None or str(order.get("broker_status") or "") == "filled":
            continue
        expiry = _expiry_of(state, order)
        if _contract_expired(expiry, now):
            lines.append(
                f"Exit {order.get('right')} limit {order.get('limit')} is not a fill. "
                "The contract expiry has passed. No new order was sent."
            )
            continue
        broker_status = str(order.get("broker_status") or "")
        if broker_status in {"cancelled", "expired", "rejected"}:
            if _resend_exit(state, order, broker, now, lines):
                changed = True
            continue
        if broker_status not in {"working", "partial"}:
            continue
        if not _reprice_due(state, order, expiry, now):
            lines.append(
                f"Exit working. {limit_fill_text(order.get('limit'), order.get('fill'))}"
            )
            continue
        if _reprice_exit(state, order, broker, now, lines, expiry):
            changed = True
    return changed


def stamp_submission(order: dict, when, **fields) -> None:
    """Remember when the order was sent, and the contract, without calling the broker."""
    stamp = when.isoformat() if hasattr(when, "isoformat") else str(when)
    order["submitted_at"] = stamp
    for key, value in fields.items():
        if value not in (None, ""):
            order[key] = value


def _reprice_due(state: dict, order: dict, expiry: Optional[date], now: datetime) -> bool:
    sent = _sent_at(state, order)
    local = to_ny(now)
    if sent is None:
        age = EXIT_REPRICE_AFTER_S
    else:
        age = (local - to_ny(sent)).total_seconds()
    wait = FLATTEN_REPRICE_AFTER_S if _flatten_window(expiry, now) else EXIT_REPRICE_AFTER_S
    return age + 1e-9 >= wait


def _reprice_exit(state, order, broker, now, lines, expiry: Optional[date]) -> bool:
    new_limit = _marketable_limit(state, order, broker, now, expiry)
    if new_limit is None:
        lines.append(
            f"Exit still working. {limit_fill_text(order.get('limit'), None)} "
            "No new bid, so the limit was not changed."
        )
        return False
    previous = _known(order.get("limit"))
    if previous is not None and abs(previous - new_limit) < 0.001:
        lines.append(
            f"Exit still working. {limit_fill_text(order.get('limit'), None)} "
            "The marketable limit is unchanged."
        )
        return False
    qty = _qty(order)
    replacer = getattr(broker, "replace_order", None)
    if callable(replacer):
        try:
            replacer(str(order.get("id") or ""), qty, limit_price=new_limit)
        except Exception:
            lines.append("Exit reprice was rejected. The reason was not printed.")
            return False
        order["limit"] = f"{new_limit:.2f}"
        order["submitted_at"] = to_ny(now).isoformat()
        order["broker_status"] = "working"
        lines.append(
            f"Repriced SELL {order.get('qty')} {order.get('right')}. "
            f"{limit_fill_text(order.get('limit'), None)}"
        )
        return True
    return _resend_exit(state, order, broker, now, lines, limit=new_limit)


def _resend_exit(state, order, broker, now, lines, limit: Optional[float] = None) -> bool:
    """Cancel a dead or stuck sell and send one new marketable limit."""
    if _contract_expired(_expiry_of(state, order), now):
        lines.append("The contract expiry has passed. No new order was sent.")
        return False
    new_limit = limit if limit is not None else _marketable_limit(state, order, broker, now, _expiry_of(state, order))
    if new_limit is None:
        lines.append("The exit was not resent. No marketable bid. The limit is not a fill.")
        return False
    cancel = getattr(broker, "cancel_order", None)
    if str(order.get("broker_status") or "") in {"working", "partial"} and callable(cancel):
        try:
            cancel(str(order.get("id") or ""))
        except Exception:
            lines.append("Exit cancel was rejected. A second sell was not sent. The reason was not printed.")
            return False
    sender = getattr(broker, "place_option_order", None)
    if not callable(sender):
        lines.append("The exit was not resent. The broker has no option order path.")
        return False
    payload = _sell_payload(state, order, new_limit)
    if payload is None:
        lines.append("The exit was not resent. The journal has no contract for a new order.")
        return False
    try:
        sender(payload)
    except Exception:
        lines.append("Exit resend was rejected. The reason was not printed.")
        return False
    prior = list(order.get("prior_ids") or [])
    if order.get("id"):
        prior.append(order.get("id"))
    order["prior_ids"] = prior
    order["id"] = payload["client_order_id"]
    order["limit"] = f"{new_limit:.2f}"
    order["status"] = "submitted"
    order["broker_status"] = "working"
    order["fill"] = None
    order["submitted_at"] = to_ny(now).isoformat()
    lines.append(
        f"Resent SELL {order.get('qty')} {order.get('right')}. "
        f"{limit_fill_text(order.get('limit'), None)}"
    )
    return True


def _marketable_limit(state, order, broker, now, expiry: Optional[date]) -> Optional[float]:
    from webull_bot.execution.forward_vwap import _sell_limit

    bid = _bid(broker, contract_for(state, order))
    if bid is None:
        bid = _known(order.get("sandbox_price"))
    flatten = _flatten_window(expiry, now)
    if bid is None and flatten:
        bid = 0.01
    if bid is None:
        return None
    limit = _sell_limit(float(bid))
    previous = _known(order.get("limit"))
    if flatten and previous is not None and limit >= previous - 1e-9:
        limit = max(0.01, round(previous - 0.01, 2))
    return limit


def _bid(broker, contract: str) -> Optional[float]:
    if not contract or broker is None or not hasattr(broker, "option_contract_quote"):
        return None
    try:
        quote = broker.option_contract_quote(contract)
    except Exception:
        return None
    if not isinstance(quote, dict):
        return None
    return _known(quote.get("bid"))


def _sell_payload(state, order, limit: float) -> Optional[dict]:
    from webull_bot.broker.webull import build_single_option_order, new_client_order_id

    signal_id = _signal_id(str(order.get("key") or ""))
    source = {"symbol": order.get("symbol"), "right": order.get("right"), "option_type": order.get("option_type")}
    for row in _related(state, signal_id):
        source.update({key: row.get(key) for key in ("symbol", "strike", "expiry", "option_type", "right") if row.get(key)})
    symbol = str(source.get("symbol") or order.get("symbol") or "")
    strike = _known(source.get("strike") or order.get("strike"))
    expiry = str(source.get("expiry") or order.get("expiry") or "")[:10]
    option_type = str(source.get("option_type") or source.get("right") or order.get("right") or "")
    if not symbol or strike is None or not expiry or not option_type:
        return None
    return build_single_option_order(
        client_order_id=new_client_order_id(),
        symbol=symbol,
        side="SELL",
        quantity=_qty(order),
        strike_price=float(strike),
        option_expire_date=expiry,
        option_type=option_type.upper(),
        limit_price=float(limit),
        order_type="LIMIT",
        position_intent="SELL_TO_CLOSE",
    )


def _detail_line(order: dict, detail: dict) -> str:
    kind = str(detail.get("kind") or order.get("broker_status") or "")
    base = f"{order.get('side')} {order.get('qty')} {order.get('right')} "
    if kind == "filled":
        return base + limit_fill_text(order.get("limit"), order.get("fill")) + f" Status filled at {order.get('fill_time') or 'n/a'}."
    if kind == "partial":
        qty = order.get("filled_qty")
        return (
            base
            + f"Partial fill {order.get('partial_fill')} for {qty}. "
            + limit_fill_text(order.get("limit"), None)
        )
    if kind in {"cancelled", "expired", "rejected"}:
        return base + f"Status {kind}. " + limit_fill_text(order.get("limit"), order.get("fill"))
    if kind == "filled_no_price":
        return base + "Status filled. No average fill price. " + limit_fill_text(order.get("limit"), None)
    return base + "Status working. " + limit_fill_text(order.get("limit"), order.get("fill"))


def _classify(found: dict) -> dict:
    status = _norm(found.get("status"))
    price = _known(found.get("price"))
    filled = found.get("filled_qty")
    total = found.get("total_qty")
    partial_qty = filled is not None and filled > 0 and (total is None or filled + 1e-9 < total)
    kind = "unknown"
    if status in _EXPIRED:
        kind = "expired"
    elif status in _CANCELLED:
        kind = "cancelled"
    elif status in _REJECTED:
        kind = "rejected"
    elif status in _FILLED or (price is not None and status is None and not partial_qty):
        kind = "filled" if price is not None else "filled_no_price"
    elif status in _PARTIAL or partial_qty:
        kind = "partial"
    elif status in _WORKING or status:
        kind = "working"
    return {
        "kind": kind,
        "price": price,
        "time": found.get("time"),
        "filled_qty": filled,
        "total_qty": total,
        "status": status,
    }


def _walk(payload: Any, found: dict) -> None:
    if isinstance(payload, list):
        for item in payload:
            _walk(item, found)
        return
    if not isinstance(payload, dict):
        return
    if found["price"] is None:
        for key in _FILL_KEYS:
            if key in payload and key not in _LIMIT_KEYS:
                price = _known(payload.get(key))
                if price is not None:
                    found["price"] = price
                    break
    if found["status"] is None:
        for key in _STATUS_KEYS:
            if payload.get(key) not in (None, ""):
                found["status"] = str(payload.get(key))
                break
    if found["filled_qty"] is None:
        for key in _FILLED_QTY_KEYS:
            number = _known(payload.get(key))
            if number is not None:
                found["filled_qty"] = number
                break
    if found["total_qty"] is None:
        for key in _TOTAL_QTY_KEYS:
            if key in _FILLED_QTY_KEYS:
                continue
            number = _known(payload.get(key))
            if number is not None:
                found["total_qty"] = number
                break
    if found["time"] is None:
        for key in _TIME_KEYS:
            if payload.get(key):
                found["time"] = str(payload.get(key))
                break
    for key, value in payload.items():
        if key in _LIMIT_KEYS:
            continue
        if isinstance(value, (dict, list)):
            _walk(value, found)


def _position_rows(payload: Any) -> list[dict]:
    rows = payload if isinstance(payload, list) else []
    if isinstance(payload, dict):
        for key in ("positions", "data", "items", "result"):
            if isinstance(payload.get(key), list):
                rows = payload[key]
                break
            if isinstance(payload.get(key), dict):
                nested = _position_rows(payload[key])
                if nested:
                    return nested
    found = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        symbols = []
        for key in ("option_symbol", "symbol", "ticker", "instrument_id", "symbol_name"):
            if row.get(key):
                symbols.append(str(row.get(key)).upper())
        quantity = None
        for key in ("quantity", "qty", "position", "position_qty"):
            number = _known(row.get(key))
            if number is not None:
                quantity = number
                break
        if quantity in (None, 0, 0.0):
            continue
        symbol = next((item for item in symbols if len(item) > 8), symbols[0] if symbols else "")
        if symbol:
            found.append({"symbol": symbol, "quantity": quantity, "symbols": symbols})
    return found


def _held(contract: str, holdings: list[dict]) -> Optional[object]:
    target = contract.upper()
    for row in holdings:
        names = [str(row.get("symbol") or "").upper(), *[str(item).upper() for item in row.get("symbols") or []]]
        if target in names or any(target in name for name in names if name):
            return row.get("quantity")
    return None


def _related(state: dict, signal_id: str) -> list[dict]:
    if not signal_id:
        return []
    found = []
    for key in ("positions", "signals", "exits", "quote_log"):
        for row in state.get(key) or []:
            if isinstance(row, dict) and str(row.get("id") or row.get("signal_id") or "") == signal_id:
                found.append(row)
    return found


def _occ_from(source: dict, underlying: str) -> str:
    from webull_bot.execution.forward_quotes import occ_symbol

    expiry = _as_date(source.get("expiry"))
    strike = _known(source.get("strike") or source.get("order_strike"))
    right = source.get("option_type") or source.get("right")
    symbol = str(source.get("symbol") or underlying or "")
    if expiry is None or strike is None or not right or not symbol:
        return ""
    if symbol.upper().startswith("QQQ") and len(symbol) > 6:
        return ""
    try:
        return occ_symbol(symbol, expiry, str(right), float(strike))
    except Exception:
        return ""


def _expiry_of(state: dict, order: dict) -> Optional[date]:
    explicit = _as_date(order.get("expiry"))
    if explicit is not None:
        return explicit
    for source in _related(state, _signal_id(str(order.get("key") or ""))):
        found = _as_date(source.get("expiry"))
        if found is not None:
            return found
    contract = contract_for(state, order)
    return _expiry_from_occ(contract)


def _expiry_from_occ(contract: str) -> Optional[date]:
    import re

    match = re.search(r"(\d{6})[CP]\d{8}$", str(contract or "").upper())
    if match is None:
        return None
    try:
        return datetime.strptime(match.group(1), "%y%m%d").date()
    except ValueError:
        return None


def _contract_expired(expiry: Optional[date], now: datetime) -> bool:
    if expiry is None:
        return False
    local = to_ny(now)
    if local.date() > expiry:
        return True
    return local.date() == expiry and local.time() >= EXPIRED_AT


def _flatten_window(expiry: Optional[date], now: datetime) -> bool:
    local = to_ny(now)
    if expiry is not None and local.date() != expiry:
        return False
    return local.time() >= FLAT_AT and not _contract_expired(expiry, now)


def _sent_at(state: dict, order: dict) -> Optional[datetime]:
    raw = order.get("submitted_at")
    if not raw:
        for source in _related(state, _signal_id(str(order.get("key") or ""))):
            if source.get("time"):
                raw = source.get("time")
                break
    if not raw:
        return None
    try:
        stamp = datetime.fromisoformat(str(raw))
    except ValueError:
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=NY)
    return stamp


def _stamp_fill_row(state: dict, order: dict) -> None:
    price = _known(order.get("fill"))
    if price is None:
        return
    kind = str(order.get("kind") or "")
    signal_id = _signal_id(str(order.get("key") or ""))
    side = "BUY" if kind == "entry" else "SELL" if kind == "exit" else str(order.get("side") or "")
    if not signal_id or not side:
        return
    for row in state.get("fills") or []:
        if not isinstance(row, dict):
            continue
        if row.get("id") == signal_id and str(row.get("side") or "") == side:
            row["fill"] = price
            if order.get("fill_time"):
                row["fill_time"] = order.get("fill_time")
            row["fill_source"] = "order"
            return


def _signal_id(key: str) -> str:
    for suffix in ("|entry", "|exit"):
        if key.endswith(suffix):
            return key[: -len(suffix)]
    return ""


def _qty(order: dict) -> float:
    number = _known(order.get("qty"))
    if number is None or number <= 0:
        return 1.0
    return number


def _load(journal, book: str):
    from webull_bot.execution.forward_trapdoor import NAME as TRAP_NAME
    from webull_bot.execution.forward_trapdoor import STAKE as TRAP_STAKE
    from webull_bot.execution.forward_trapdoor import load_state as trap_load

    if book == TRAP_NAME:
        return trap_load(journal), TRAP_STAKE
    from webull_bot.execution.forward_vwap import _ACTIVE, _activate, _stake, load_state

    token = _activate(book)
    try:
        return load_state(journal), _stake()
    finally:
        _ACTIVE.reset(token)


def _save(journal, book: str, state: dict) -> None:
    journal.forward_save(book, state)


def _norm(value) -> Optional[str]:
    if value in (None, ""):
        return None
    return str(value).strip().lower().replace("-", "_").replace(" ", "_")


def _known(value) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number <= 0:
        return None
    return number


def _as_date(value) -> Optional[date]:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None
