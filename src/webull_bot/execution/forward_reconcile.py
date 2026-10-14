"""Read sandbox order detail for a forward book.

``reconcile_book`` queries order detail and account positions, then writes
the status it read. It does not place an order. It cancels a buy that is
still unfilled after the fill window, after the price leaves the stop and
the 1R target, or after a rejected sell. The exit chase is separate: a
later cycle steps a working sell down through the bid. A sell is not sent,
replaced, or left working when the entry fill is not confirmed. A limit
price is never stored as a fill. An expired unsold 0DTE is closed in the
journal at intrinsic value, which is zero when the underlying finishes
out of the money.
"""

from __future__ import annotations

import os
import re
import time as time_mod
from datetime import date, datetime, time, timedelta
from typing import Any, Optional
from zoneinfo import ZoneInfo

from webull_bot.calendar import to_ny

NY = ZoneInfo("America/New_York")
# A working sell steps down on this interval, including through the flatten.
EXIT_REPRICE_AFTER_S = 5.0
FLATTEN_REPRICE_AFTER_S = 5.0
FLAT_AT = time(15, 45)
# The limit is already one cent by this clock, before the 15:45 flatten.
FLOOR_AT = time(15, 44)
EXPIRED_AT = time(16, 5)
MIN_SELL = 0.01
# One order-detail read per order, and the calls are spaced across the watch.
DETAIL_GAP_S = 20.0
DETAIL_GLOBAL_GAP_S = 1.0
LIST_GAP_S = 20.0
_DETAIL_BACKOFF_S = (15.0, 30.0, 60.0)
_POLL = {
    "detail_at": {},
    "detail": {},
    "last_detail": 0.0,
    "blocked_until": 0.0,
    "strikes": 0,
    "view": None,
    "view_at": 0.0,
    "list_blocked_until": 0.0,
    "list_strikes": 0,
    "send_at": {},
}

_FILL_KEYS = (
    "avg_filled_price",
    "filled_price",
    "avg_price",
    "fill_price",
    "average_price",
    "avgFilledPrice",
    "filledPrice",
    "avgFillPrice",
)
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
            "It does not place an order. Live trading stays off."
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
    if str(order.get("settlement") or "") == "expiry":
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


def _broker_chain(broker):
    """The broker and every view wrapped around it."""
    seen = set()
    current = broker
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        yield current
        current = getattr(current, "_inner", None)


def _broker_trade(broker):
    """The trade client, including the broker behind an exit view."""
    for current in _broker_chain(broker):
        trade = getattr(current, "_trade", None)
        if trade is not None:
            return trade
    return None


def _watch_armed(broker) -> bool:
    return any(getattr(current, "_watch_armed", False) for current in _broker_chain(broker))


def reset_order_poll() -> None:
    """Drop the watch's order-read cache. Tests start from a clean clock."""
    _POLL["detail_at"] = {}
    _POLL["detail"] = {}
    _POLL["last_detail"] = 0.0
    _POLL["blocked_until"] = 0.0
    _POLL["strikes"] = 0
    _POLL["view"] = None
    _POLL["view_at"] = 0.0
    _POLL["list_blocked_until"] = 0.0
    _POLL["list_strikes"] = 0
    _POLL["send_at"] = {}
    _POLL["read_seq"] = 0


def read_order_detail(broker, client_order_id: str, force: bool = False) -> dict:
    """One order-detail read. An error becomes ``kind=error`` and the text is dropped.

    On the watch, each order is read at most once every 20 seconds, the calls
    are spaced, and HTTP 429 backs off. A skipped read is ``kind=deferred``
    and does not change the journal. ``force`` skips that cache so a cancel
    rejection can see a fill that just happened.
    """
    if not client_order_id or broker is None:
        return {"kind": "unknown"}
    armed = _watch_armed(broker)
    now = time_mod.monotonic()
    if armed and not force:
        cached = _POLL["detail"].get(client_order_id)
        if now < float(_POLL["blocked_until"] or 0.0):
            return cached or {"kind": "deferred"}
        last = _POLL["detail_at"].get(client_order_id)
        if last is not None and now - float(last) < DETAIL_GAP_S:
            return cached or {"kind": "deferred"}
        if now - float(_POLL["last_detail"] or 0.0) < DETAIL_GLOBAL_GAP_S:
            return cached or {"kind": "deferred"}
    trade = _broker_trade(broker)
    account = getattr(broker, "account_id", None)
    if not account:
        account = getattr(getattr(broker, "_inner", None), "account_id", None)
    method = getattr(getattr(trade, "order_v3", None), "get_order_detail", None)
    if method is None or not account:
        return {"kind": "unknown"}
    try:
        payload = _trade_call(broker, method, account, client_order_id, key=f"order_detail:{client_order_id}")
    except Exception as exc:
        if armed and _rate_limited(exc):
            _penalize(_POLL, "blocked_until", "strikes", now)
        return {"kind": "error"}
    parsed = parse_order_detail(payload)
    if armed:
        stamp = time_mod.monotonic()
        _POLL["detail_at"][client_order_id] = stamp
        _POLL["last_detail"] = stamp
        _POLL["detail"][client_order_id] = parsed
        _POLL["strikes"] = 0
    return parsed


def _rate_limited(exc: BaseException) -> bool:
    code = getattr(exc, "status_code", None)
    if code is None:
        code = getattr(exc, "http_status_code", None)
    if code == 429:
        return True
    text = str(exc)
    return "429" in text or "Too Many Requests" in text


def _penalize(box: dict, until_key: str, strike_key: str, now: float) -> None:
    strike = int(box.get(strike_key) or 0)
    delay = _DETAIL_BACKOFF_S[min(strike, len(_DETAIL_BACKOFF_S) - 1)]
    box[strike_key] = strike + 1
    box[until_key] = now + delay


def _trade_call(broker, method, *args, key: str = "", **kwargs):
    """One trade call. The watch and reconcile both decode the JSON body.

    ``bounded_call`` returns the client object. Reconcile's ``_call`` already
    turns that into a dict. Leaving the watch on the raw object made
    ``_position_rows`` see nothing and report an empty account.
    """
    if _watch_armed(broker):
        from webull_bot.execution.forward_watch import bounded_call

        raw = bounded_call(method, *args, key=key or getattr(method, "__name__", "trade"), **kwargs)
        return _decoded_body(raw)
    from webull_bot.execution.forward_quotes import _call

    return _call(method, *args, **kwargs)


def _decoded_body(raw):
    """The JSON body. A client object that does not decode is an error, not an empty list."""
    from webull_bot.execution.forward_quotes import _json

    if raw is None:
        raise RuntimeError("Webull response was empty")
    decoded = _json(raw)
    if decoded is None:
        raise RuntimeError("Webull response was not JSON")
    return decoded


def _last_holdings(cached) -> Optional[dict]:
    """A previous read that actually listed contracts. An empty success is not reused after an error."""
    if isinstance(cached, dict) and cached.get("holdings_ok") and cached.get("holdings"):
        return cached
    return None


def account_view(broker) -> dict:
    """Positions and open orders, once each 20 seconds on the watch.

    ``holdings_ok`` is false when that read did not finish, including HTTP 429
    and a local request budget. That is not an empty account. An empty list
    with ``holdings_ok`` true means the account holds nothing.
    A later error keeps the last list that had contracts.
    """
    empty = {"holdings_ok": False, "orders_ok": False, "holdings": [], "orders": []}
    if broker is None:
        return empty
    armed = _watch_armed(broker)
    now = time_mod.monotonic()
    cached = _POLL.get("view")
    if armed and isinstance(cached, dict) and cached.get("holdings_ok") and now - float(_POLL["view_at"] or 0.0) < LIST_GAP_S:
        return cached
    if armed and now < float(_POLL["list_blocked_until"] or 0.0):
        return _last_holdings(cached) or empty
    view = {"holdings_ok": False, "orders_ok": False, "holdings": [], "orders": []}
    try:
        view["holdings"] = _fetch_position_rows(broker)
        view["holdings_ok"] = True
    except Exception as exc:
        if _rate_limited(exc):
            _penalize(_POLL, "list_blocked_until", "list_strikes", now)
        return _last_holdings(cached) or view
    try:
        view["orders"] = _fetch_open_rows(broker)
        view["orders_ok"] = True
    except Exception as exc:
        if _rate_limited(exc):
            _penalize(_POLL, "list_blocked_until", "list_strikes", now)
    if view["holdings_ok"]:
        _POLL["read_seq"] = int(_POLL.get("read_seq") or 0) + 1
        view["read_token"] = _POLL["read_seq"]
    if armed and view["holdings_ok"]:
        _POLL["view"] = view
        _POLL["view_at"] = time_mod.monotonic()
        if view["orders_ok"]:
            _POLL["list_strikes"] = 0
    return view


def holding_for(contract: str, holdings: list[dict]) -> Optional[dict]:
    """The position row for this OCC symbol."""
    target = str(contract or "").upper()
    if not target:
        return None
    for row in holdings:
        if not isinstance(row, dict):
            continue
        names = [str(row.get("symbol") or "").upper(), *[str(item).upper() for item in row.get("symbols") or []]]
        if target in names:
            return row
    return None


# A bare position row is only the underlying. Its average confirms one order
# when that average sits near the order's limit. $0.50 still leaves the
# 11:00 limits (0.76, 1.26, 2.81) off a $3.53 put.
_PREMIUM_MATCH = 0.50


def match_holding(state: dict, order: dict, holdings: list[dict]) -> Optional[dict]:
    """The position row for this order.

    An OCC symbol matches first. Otherwise the row's strike, expiry, and
    right, or a shared instrument id. A row that is only the underlying
    matches when its average is near this order's premium and this book has
    one unfilled entry on that underlying. The underlying ticker alone does
    not match.
    """
    if not isinstance(order, dict):
        return None
    contract = contract_for(state, order)
    found = holding_for(contract, holdings or [])
    if found is not None:
        return found
    identity = _order_identity(state, order)
    for row in holdings or []:
        if isinstance(row, dict) and _identity_match(row, identity):
            return row
    loose = _loose_match(state, order, holdings or [], identity)
    if loose is not None:
        return loose
    return _premium_match(state, order, holdings or [], identity)


def apply_holding_contract(state: dict, order: dict, holding: dict) -> None:
    """Copy the position row's strike and OCC onto the journal when the row has them.

    A journal strike can disagree with the account. The sell then uses the
    strike on the holding. A row with no strike leaves the journal strike.
    """
    if not isinstance(order, dict) or not isinstance(holding, dict):
        return
    strike = holding.get("strike")
    occ = ""
    names = [holding.get("symbol"), *[item for item in (holding.get("symbols") or [])]]
    for name in names:
        parsed = _parse_occ(str(name or ""))
        if not parsed:
            continue
        occ = str(name).upper()
        if strike in (None, ""):
            strike = parsed.get("strike")
        break
    if not occ and strike not in (None, ""):
        occ = _built_occ(
            holding.get("underlying") or order.get("symbol"),
            holding.get("expiry") or order.get("expiry"),
            holding.get("right") or order.get("right") or order.get("option_type"),
            strike,
        )
    if strike in (None, ""):
        return
    order["strike"] = strike
    if occ:
        order["option_symbol"] = occ
    if not isinstance(state, dict):
        return
    for source in _related(state, _signal_id(str(order.get("key") or ""))):
        source["strike"] = strike
        source["order_strike"] = strike
        if occ:
            source["option_symbol"] = occ
            source["order_symbol"] = occ
        if holding.get("expiry"):
            source["expiry"] = str(holding.get("expiry"))[:10]


def send_cooled(order_id: str) -> bool:
    """A retry of an unsent entry waits 20 seconds. The first send does not."""
    if not order_id:
        return True
    last = _POLL["send_at"].get(order_id)
    if last is None:
        return True
    return time_mod.monotonic() - float(last) >= DETAIL_GAP_S


def mark_send(order_id: str) -> None:
    if order_id:
        _POLL["send_at"][order_id] = time_mod.monotonic()


def _account_id(broker) -> str:
    account = getattr(broker, "account_id", None)
    if account:
        return str(account)
    return str(getattr(getattr(broker, "_inner", None), "account_id", None) or "")


def _fetch_position_rows(broker) -> list[dict]:
    trade = _broker_trade(broker)
    account = _account_id(broker)
    method = getattr(getattr(trade, "account_v2", None), "get_account_position", None)
    if method is not None and account:
        payload = _trade_call(broker, method, account, key="account_position")
        if not isinstance(payload, (dict, list)):
            raise RuntimeError("account positions were not read")
        return _position_rows(payload)
    positions = getattr(broker, "positions", None)
    if not callable(positions):
        raise RuntimeError("no positions")
    held = positions()
    found = []
    for row in held or []:
        parsed = _parse_position(
            {
                "symbol": getattr(row, "symbol", None),
                "quantity": getattr(row, "quantity", None),
                "avg_price": getattr(row, "avg_price", None),
            }
        )
        if parsed:
            found.append(parsed)
    return found


def _fetch_open_rows(broker) -> list[dict]:
    trade = _broker_trade(broker)
    account = _account_id(broker)
    method = getattr(getattr(trade, "order_v3", None), "get_order_open", None)
    if method is None or not account:
        raise RuntimeError("no open orders")
    payload = _trade_call(broker, method, account_id=account, page_size=50, key="open_orders")
    if not isinstance(payload, (dict, list)):
        raise RuntimeError("open orders were not read")
    rows = payload if isinstance(payload, list) else []
    if isinstance(payload, dict):
        for key in ("orders", "data", "items", "result"):
            if isinstance(payload.get(key), list):
                rows = payload[key]
                break
    found = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        client_id = str(row.get("client_order_id") or row.get("clientOrderId") or "")
        detail = parse_order_detail(row)
        symbol = str(row.get("option_symbol") or row.get("symbol") or "").upper()
        quantity = row.get("quantity")
        if quantity in (None, ""):
            quantity = row.get("qty")
        if quantity in (None, ""):
            quantity = row.get("total_quantity")
        if quantity in (None, ""):
            quantity = row.get("totalQuantity")
        parsed = {
            "id": client_id,
            "kind": detail.get("kind"),
            "price": detail.get("price"),
            "symbol": symbol,
            "side": str(row.get("side") or "").upper(),
            "order_type": str(row.get("order_type") or row.get("orderType") or "").upper(),
            "quantity": quantity,
            "strike": row.get("strike_price") or row.get("strikePrice") or row.get("strike"),
            "expiry": row.get("option_expire_date") or row.get("optionExpireDate"),
            "option_type": row.get("option_type") or row.get("optionType"),
        }
        if not client_id and not _blank_order(parsed):
            continue
        found.append(parsed)
    return found


def _qty_filled(filled, total) -> bool:
    """A full filled quantity is a fill even when the status text still says submitted."""
    if filled is None or total is None:
        return False
    try:
        filled_n = float(filled)
        total_n = float(total)
    except (TypeError, ValueError):
        return False
    return total_n > 0 and filled_n + 1e-9 >= total_n


def _blank_order(row: dict) -> bool:
    """A MARKET buy with no symbol and a quantity of 0.

    An option reprice used to call the equity replace with only a client id,
    a quantity, and a limit. The sandbox left that shape open as this order.
    """
    if not isinstance(row, dict):
        return False
    if str(row.get("symbol") or "").strip():
        return False
    if row.get("strike") not in (None, "") or row.get("expiry") or row.get("option_type"):
        return False
    try:
        quantity = float(row.get("quantity"))
    except (TypeError, ValueError):
        return False
    if quantity > 0:
        return False
    side = str(row.get("side") or "BUY").upper()
    order_type = str(row.get("order_type") or "MARKET").upper()
    return side in {"BUY", ""} and order_type in {"MARKET", ""}


def apply_order_detail(order: dict, detail: dict) -> None:
    """Store the broker status. The limit already on the order is left as the limit."""
    kind = str(detail.get("kind") or "unknown")
    if kind in {"unknown", "error", "deferred"}:
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
    trade = _broker_trade(broker)
    account = getattr(broker, "account_id", None) or getattr(getattr(broker, "_inner", None), "account_id", None)
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
        parsed = _parse_position(
            {
                "symbol": getattr(row, "symbol", None),
                "quantity": getattr(row, "quantity", None),
                "avg_price": getattr(row, "avg_price", None),
            }
        )
        if parsed:
            found.append(parsed)
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
    lines = ["Sandbox account positions, read only."]
    if not holdings:
        lines.append("- The account list is empty.")
    for row in holdings:
        lines.append(_describe_holding(row))
    if not orders:
        lines.append("No pending order to match against the account.")
        return lines
    for order in orders:
        contract = contract_for(state, order)
        held = match_holding(state, order, holdings)
        if held is not None:
            label = contract or str(order.get("key") or "order")
            lines.append(f"{label}: the sandbox account still holds {held.get('quantity')}.")
            continue
        if not contract:
            lines.append(
                f"{order.get('side')} {order.get('qty')} {order.get('key')}: "
                "the journal has no contract symbol. Compare the account list above."
            )
            continue
        lines.append(f"{contract}: the sandbox account does not hold this contract.")
    return lines


def reconcile_book(journal, broker, book: str, now: datetime) -> list[str]:
    """Read pending orders for one book and store the status. Does not trade."""
    state, stake = _load(journal, book)
    lines = [
        f"Forward reconcile {book}. Sandbox read only. Live trading stays off.",
        "This command does not place an order. It cancels a buy that never filled "
        "once the fill window ended, the price left the stop and the 1R target, or a sell was rejected.",
    ]
    pending = [order for order in (state.get("orders") or []) if isinstance(order, dict) and order_needs_detail(order)]
    if not pending:
        lines.append("No journaled order is waiting on a fill.")
    lines.extend(apply_pending_details(state, broker))
    from webull_bot.execution.forward_fills import sync_working_entries

    if sync_working_entries(state, broker, now, _underlying_spot(broker, book), lines):
        lines.append("Unfilled entries were matched to the order status. No new order was placed.")
    from webull_bot.execution.forward_cash import prepare_cash

    prepare_cash(state, None, stake, to_ny(now).date())
    holdings = read_holdings(broker)
    closed = settle_expired_unsold(state, broker, now, holdings, lines)
    if closed:
        prepare_cash(state, None, stake, to_ny(now).date())
        for signal in state.get("signals") or []:
            if not isinstance(signal, dict) or signal.get("id") not in closed:
                continue
            pnl = signal.get("fill_pnl")
            if pnl is None:
                lines.append(f"{signal.get('id')}: expiry close has no booked P&L. The premium is unknown.")
                continue
            lines.append(f"Booked fill P&L ${float(pnl):.2f} for {signal.get('id')}.")
    lines.extend(holdings_lines(state, holdings, pending or [order for order in (state.get("orders") or []) if isinstance(order, dict)]))
    _save(journal, book, state)
    lines.append("Reconcile stored the status it read. No order was sent.")
    return lines


NIGHTLY_BOOKS = (
    "vwap_band_15m",
    "vwap_band_15m_qqq_aggr",
    "vwap_band_15m_qqq_aggr_1dte",
    "vwap_band_15m_qqq_compound",
    "neckline_trapdoor_qqq",
    "four_hour_qqq_1dte",
)
_BLANK_TRIED: set = set()


def cancel_blank_orders(broker, lines, view=None) -> int:
    """Cancel a MARKET buy that has no symbol and a quantity of 0.

    That order cannot be a held option. A real working sell is left alone.
    """
    if view is None:
        view = account_view(broker)
    if not view.get("orders_ok"):
        return 0
    cancel = getattr(broker, "cancel_order", None)
    if not callable(cancel):
        inner = getattr(broker, "_inner", None)
        cancel = getattr(inner, "cancel_order", None) if inner is not None else None
    count = 0
    for row in view.get("orders") or []:
        if not _blank_order(row):
            continue
        oid = str(row.get("id") or "")
        lines.append(
            f"Blank open order {oid or 'no id'} {row.get('side') or 'BUY'} "
            f"{row.get('order_type') or 'MARKET'} quantity {row.get('quantity')} symbol empty."
        )
        if not oid:
            lines.append("Blank order has no client id. It was not cancelled.")
            continue
        if oid in _BLANK_TRIED:
            continue
        if not callable(cancel):
            lines.append("Blank order was not cancelled. The broker has no cancel path.")
            _BLANK_TRIED.add(oid)
            continue
        try:
            cancel(oid)
        except Exception as exc:
            lines.append(f"Blank order cancel was rejected. {_rejection_body(exc)} No new order was sent.")
            _BLANK_TRIED.add(oid)
            continue
        _BLANK_TRIED.add(oid)
        lines.append(f"Cancelled blank order {oid}. No new order was sent.")
        count += 1
    return count


def nightly_reconcile(journal, broker, now: datetime) -> list[str]:
    """Compare each watch book with the sandbox. Does not place an order and does not save.

    The one write is cancelling a blank MARKET buy with no symbol and quantity 0.
    """
    lines = [
        "Nightly reconcile. The journal is compared with sandbox holdings and orders. "
        "No order is placed. A blank MARKET buy with no symbol and quantity 0 is cancelled. "
        "Live trading stays off.",
    ]
    view = account_view(broker) if broker is not None else {
        "holdings_ok": False,
        "orders_ok": False,
        "holdings": [],
        "orders": [],
    }
    holdings_ok = bool(view.get("holdings_ok"))
    holdings = list(view.get("holdings") or []) if holdings_ok else []
    if not holdings_ok:
        lines.append(
            "Sandbox position list was not read. It was not treated as empty. No holding mismatches inferred."
        )
    elif not holdings:
        lines.append("Sandbox position list is empty.")
    else:
        for row in holdings:
            lines.append("Sandbox position " + _describe_holding(row))
    if view.get("orders_ok"):
        cancel_blank_orders(broker, lines, view)
        for row in view.get("orders") or []:
            if _blank_order(row):
                continue
            lines.append(
                f"Open order {row.get('id') or 'no id'} {row.get('side') or ''} "
                f"{row.get('order_type') or ''} {row.get('symbol') or 'no symbol'} "
                f"quantity {row.get('quantity')}."
            )
    else:
        lines.append("Open orders were not read. A blank order was not cancelled.")
    mismatches: list[str] = []
    loaded = []
    for book in NIGHTLY_BOOKS:
        try:
            state, _stake = _load(journal, book)
        except Exception:
            mismatches.append(f"{book}: the journal was not read.")
            continue
        if not isinstance(state, dict):
            continue
        loaded.append((book, state))
        mismatches.extend(_book_mismatches(book, state, broker, holdings, holdings_ok))
    if holdings_ok:
        for row in holdings:
            if not _holding_explained(row, loaded):
                mismatches.append("Unexplained holding. " + _describe_holding(row).lstrip("- ").strip())
    if mismatches:
        lines.append("Mismatches:")
        lines.extend(mismatches)
    else:
        lines.append("No mismatches.")
    return lines


def _book_mismatches(book: str, state: dict, broker, holdings: list, holdings_ok: bool) -> list[str]:
    from webull_bot.execution.forward_fills import _was_unfilled, entry_order, position_is_filled

    found = []
    for position in state.get("positions") or []:
        if not isinstance(position, dict) or not position_is_filled(state, position):
            continue
        from webull_bot.execution.forward_quote_touch import position_is_quote_touch

        if position_is_quote_touch(state, position):
            continue
        if not holdings_ok:
            continue
        probe = _position_probe(position)
        if match_holding(state, probe, holdings) is None:
            name = position.get("option_symbol") or position.get("right") or position.get("id")
            found.append(
                f"{book} {position.get('id')}: journal says this position is held ({name}). "
                "The sandbox account does not hold it."
            )
    for signal in state.get("signals") or []:
        if not isinstance(signal, dict) or not _was_unfilled(signal):
            continue
        signal_id = str(signal.get("id") or "")
        order = entry_order(state, signal_id)
        if order is None:
            continue
        if holdings_ok and match_holding(state, order, holdings) is not None:
            found.append(
                f"{book} {signal_id}: journal says skipped unfilled. "
                "The sandbox account holds a matching contract."
            )
        if broker is None:
            continue
        detail = read_order_detail(broker, str(order.get("id") or ""))
        kind = str(detail.get("kind") or "")
        if kind in {"filled", "filled_no_price"} or (kind == "partial" and _known(detail.get("price")) is not None):
            price = detail.get("price")
            found.append(
                f"{book} {signal_id}: journal says skipped unfilled. "
                f"Order detail is filled at {price if price not in (None, '') else 'an unknown price'}."
            )
    for order in state.get("orders") or []:
        if not isinstance(order, dict) or str(order.get("kind") or "") != "entry":
            continue
        if _known(order.get("fill")) is None or not holdings_ok:
            continue
        if str(order.get("fill_source") or "") == "quote_touch":
            continue
        signal_id = ""
        key = str(order.get("key") or "")
        if key.endswith("|entry"):
            signal_id = key[: -len("|entry")]
        if any(isinstance(row, dict) and str(row.get("id") or "") == signal_id for row in state.get("positions") or []):
            continue
        signal = next(
            (row for row in state.get("signals") or [] if isinstance(row, dict) and str(row.get("id") or "") == signal_id),
            None,
        )
        if signal is None or str(signal.get("status") or "") == "closed":
            continue
        if match_holding(state, order, holdings) is not None:
            continue
        found.append(
            f"{book} {signal_id}: order detail fill {order.get('fill')} is on the journal. "
            "The sandbox account does not hold it."
        )
    for order in state.get("orders") or []:
        if not isinstance(order, dict) or str(order.get("kind") or "") != "exit":
            continue
        if _known(order.get("fill")) is not None:
            continue
        status = str(order.get("status") or "")
        broker_status = str(order.get("broker_status") or "")
        if status not in {"submitted", "intent", "partial", "rejected"} and broker_status not in {
            "working",
            "rejected",
            "partial",
        }:
            continue
        if broker is None:
            continue
        detail = read_order_detail(broker, str(order.get("id") or ""))
        kind = str(detail.get("kind") or "")
        label = order.get("id") or order.get("key")
        if kind in {"filled", "filled_no_price"}:
            found.append(
                f"{book} exit {label}: journal says fill pending. "
                f"Order detail is filled at {detail.get('price') or 'an unknown price'}."
            )
        elif (
            holdings_ok
            and status in {"submitted", "partial"}
            and match_holding(state, order, holdings) is None
        ):
            found.append(
                f"{book} exit {label}: journal says fill pending. "
                "The sandbox account does not hold the contract."
            )
        elif kind == "rejected" or status == "rejected" or broker_status == "rejected":
            found.append(
                f"{book} exit {label}: the sell is rejected. "
                f"{order.get('error') or kind or 'no reason was stored'}."
            )
    return found


def _position_probe(position: dict) -> dict:
    return {
        "key": f"{position.get('id')}|entry",
        "kind": "entry",
        "symbol": position.get("symbol"),
        "option_symbol": position.get("option_symbol"),
        "strike": position.get("strike"),
        "expiry": position.get("expiry"),
        "right": position.get("right"),
        "option_type": position.get("option_type") or position.get("right"),
        "qty": position.get("qty") or position.get("quantity"),
        "limit": position.get("fill"),
    }


UNRESOLVED_REASON = "unresolved: not held by sandbox"


def release_unheld_positions(state, broker, lines, now=None) -> bool:
    """Close a journaled contract the sandbox no longer holds.

    Two successful position reads in a row must miss it, and the open-order
    list must show no working order for it. A failed or budgeted read is not
    one of those reads. No fill price is stored. Model P&L stays on the signal.
    The position is removed so the book can take a new signal.
    """
    if broker is None or not isinstance(state, dict):
        return False
    view = account_view(broker)
    if not view.get("holdings_ok"):
        return False
    token = view.get("read_token")
    changed = False
    for sid in _unheld_ids(state):
        if _close_if_unheld(state, sid, view, token, lines, now):
            changed = True
    return changed


def _unheld_ids(state: dict) -> list[str]:
    from webull_bot.execution.forward_fills import _signal_filled, position_is_filled

    found: list[str] = []
    seen: set[str] = set()
    from webull_bot.execution.forward_quote_touch import position_is_quote_touch

    for position in state.get("positions") or []:
        if not isinstance(position, dict) or not position_is_filled(state, position):
            continue
        if position_is_quote_touch(state, position):
            continue
        sid = str(position.get("id") or "")
        if sid and sid not in seen:
            seen.add(sid)
            found.append(sid)
    for order in state.get("orders") or []:
        if not isinstance(order, dict) or str(order.get("kind") or "") != "exit":
            continue
        if not order_needs_detail(order) or _known(order.get("fill")) is not None:
            continue
        sid = _signal_id(str(order.get("key") or ""))
        if sid and sid not in seen and _signal_filled(state, sid):
            if position_is_quote_touch(state, {"id": sid}):
                continue
            seen.add(sid)
            found.append(sid)
    return found


def _close_if_unheld(state, sid: str, view: dict, token, lines, now) -> bool:
    position = _position_by_id(state, sid)
    exits = _exit_orders_for(state, sid)
    if any(_known(order.get("fill")) is not None for order in exits):
        return False
    probe = _unheld_probe(state, sid, position, exits)
    if probe is None or not contract_for(state, probe):
        return False
    rows = _absence_rows(state, sid, position, exits)
    if match_holding(state, probe, view.get("holdings") or []) is not None:
        dirty = any(int(row.get("absent_reads") or 0) for row in rows)
        _reset_absence(rows)
        return dirty
    reads, advanced = _bump_absence(rows, token)
    if not advanced:
        return False
    label = contract_for(state, probe) or sid
    if reads < 2:
        lines.append(
            f"{label}: sandbox holdings do not include this contract ({reads} of 2). "
            "The journal position stays."
        )
        return True
    working = _working_order_for(state, probe, view, _journal_order_ids(state, sid))
    if working is None:
        lines.append(
            f"{label}: absent on {reads} reads, but open orders were not read. "
            "The journal position stays."
        )
        return True
    if working:
        lines.append(
            f"{label}: absent from holdings, but a working order exists. The journal position stays."
        )
        return True
    _mark_unresolved(state, sid, position, exits, lines, now, label, reads)
    return True


def _unheld_probe(state, sid: str, position, exits) -> Optional[dict]:
    if isinstance(position, dict) and (position.get("option_symbol") or position.get("strike")):
        return _position_probe(position)
    for order in exits:
        if contract_for(state, order):
            return order
    signal = _signal_by_id(state, sid)
    if isinstance(signal, dict) and (signal.get("option_symbol") or signal.get("strike")):
        return _position_probe(signal)
    if isinstance(position, dict):
        return _position_probe(position)
    return exits[0] if exits else None


def _absence_rows(state, sid: str, position, exits) -> list:
    rows = []
    signal = _signal_by_id(state, sid)
    if isinstance(signal, dict):
        rows.append(signal)
    if isinstance(position, dict):
        rows.append(position)
    rows.extend(order for order in exits if isinstance(order, dict))
    return rows


def _reset_absence(rows) -> None:
    for row in rows:
        row["absent_reads"] = 0
        row.pop("absent_token", None)


def _bump_absence(rows, token) -> tuple[int, bool]:
    """The running count, and whether this read is a new one."""
    if not rows:
        return 0, False
    if token is not None and any(row.get("absent_token") == token for row in rows):
        current = max(int(row.get("absent_reads") or 0) for row in rows)
        return current, False
    current = max(int(row.get("absent_reads") or 0) for row in rows) + 1
    for row in rows:
        row["absent_reads"] = current
        if token is not None:
            row["absent_token"] = token
    return current, True


def _journal_order_ids(state, sid: str) -> set:
    found = set()
    for order in state.get("orders") or []:
        if not isinstance(order, dict):
            continue
        if _signal_id(str(order.get("key") or "")) != sid:
            continue
        oid = str(order.get("id") or "")
        if oid:
            found.add(oid)
    return found


def _working_order_for(state, probe: dict, view: dict, journal_ids: set) -> Optional[bool]:
    """True when a working order matches. None when that list was not read."""
    if not view.get("orders_ok"):
        return None
    contract = contract_for(state, probe).upper()
    for row in view.get("orders") or []:
        if not isinstance(row, dict) or _blank_order(row):
            continue
        kind = str(row.get("kind") or "")
        if kind in {"cancelled", "canceled", "expired", "rejected", "filled"}:
            continue
        oid = str(row.get("id") or "")
        if oid and oid in journal_ids:
            return True
        names = [str(row.get("symbol") or "").upper(), *[str(item).upper() for item in row.get("symbols") or []]]
        if contract and contract in names:
            return True
    return False


def _mark_unresolved(state, sid: str, position, exits, lines, now, label: str, reads: int) -> None:
    signal = _signal_by_id(state, sid)
    model = None
    if isinstance(signal, dict):
        prior = str(signal.get("reason") or "")
        if prior and prior != UNRESOLVED_REASON and not signal.get("model_reason"):
            signal["model_reason"] = prior
        model = _model_pnl(signal)
        signal["status"] = "closed"
        signal["reason"] = UNRESOLVED_REASON
        signal["fill_pnl"] = None
        if model is not None:
            signal["model_pnl"] = model
        if not signal.get("exit_time"):
            signal["exit_time"] = _unresolved_stamp(now)
    for order in exits:
        if _known(order.get("fill")) is not None:
            continue
        order["status"] = "unresolved"
        order["broker_status"] = "unresolved"
        order["resolution"] = UNRESOLVED_REASON
    state["positions"] = [
        row for row in (state.get("positions") or []) if not (isinstance(row, dict) and str(row.get("id") or "") == sid)
    ]
    found = False
    for row in state.get("exits") or []:
        if not isinstance(row, dict) or str(row.get("id") or "") != sid:
            continue
        found = True
        prior = str(row.get("reason") or "")
        if prior and prior != UNRESOLVED_REASON and not row.get("model_reason"):
            row["model_reason"] = prior
        row["reason"] = UNRESOLVED_REASON
        row["fill_pnl"] = None
        if model is not None:
            row["model_pnl"] = model
        elif row.get("pnl") is not None and row.get("model_pnl") is None:
            row["model_pnl"] = row.get("pnl")
    if not found:
        state.setdefault("exits", []).append(
            {
                "id": sid,
                "time": _unresolved_stamp(now),
                "reason": UNRESOLVED_REASON,
                "right": (position or signal or {}).get("right") if isinstance(position or signal, dict) else None,
                "pnl": None if model is None else model,
                "model_pnl": model,
                "fill_pnl": None,
            }
        )
    if model is None:
        model_txt = "Model P&L was not booked."
    else:
        model_txt = f"Model P&L ${float(model):.2f} stays separate."
    lines.append(
        f"{label}: not in sandbox holdings on {reads} consecutive reads. "
        f"No working order. Closed as {UNRESOLVED_REASON}. No fill P&L booked. {model_txt} Slot freed."
    )


def _model_pnl(signal: dict):
    if signal.get("model_pnl") is not None:
        return signal.get("model_pnl")
    debit = _known(signal.get("model_debit"))
    credit = _known(signal.get("model_credit"))
    if debit is not None and credit is not None:
        return credit - debit
    if signal.get("pnl") is not None:
        return signal.get("pnl")
    return None


def _unresolved_stamp(now) -> str:
    moment = now or datetime.now()
    try:
        return to_ny(moment).isoformat()
    except (TypeError, ValueError):
        return str(moment)


def _position_by_id(state, sid: str):
    for row in state.get("positions") or []:
        if isinstance(row, dict) and str(row.get("id") or "") == sid:
            return row
    return None


def _signal_by_id(state, sid: str):
    for row in state.get("signals") or []:
        if isinstance(row, dict) and str(row.get("id") or "") == sid:
            return row
    return None


def _exit_orders_for(state, sid: str) -> list:
    found = []
    for order in state.get("orders") or []:
        if not isinstance(order, dict) or str(order.get("kind") or "") != "exit":
            continue
        if _signal_id(str(order.get("key") or "")) == sid:
            found.append(order)
    return found


def _holding_explained(row: dict, loaded: list) -> bool:
    from webull_bot.execution.forward_fills import entry_order

    for _book, state in loaded:
        for position in state.get("positions") or []:
            if isinstance(position, dict) and match_holding(state, _position_probe(position), [row]) is not None:
                return True
        for signal in state.get("signals") or []:
            if not isinstance(signal, dict):
                continue
            order = entry_order(state, str(signal.get("id") or ""))
            if order is not None and match_holding(state, order, [row]) is not None:
                return True
    return False


def chase_exit_orders(state: dict, broker, now: datetime, lines: list[str]) -> bool:
    """Re-read a working sell and step the limit down when it is still open.

    A contract whose expiry has passed is not replaced and is not resent.
    The first few seconds after the sell is sent are not repriced. After
    that the limit steps at least one cent, and through the bid when that
    is lower. From 15:44 the limit is one cent.
    """
    if broker is None or not isinstance(state, dict):
        return False
    from webull_bot.execution.forward_quote_touch import apply_quote_touches

    changed = apply_quote_touches(state, broker, now, None, lines)
    for order in list(state.get("orders") or []):
        if not isinstance(order, dict) or order.get("kind") != "exit":
            continue
        if str(order.get("settlement") or "") == "expiry":
            continue
        if _pending_exit(order):
            if _finish_exit_send(state, order, broker, now, lines):
                changed = True
            continue
        if str(order.get("status") or "") not in {"submitted", "partial"}:
            continue
        if _known(order.get("fill")) is not None:
            continue
        detail = read_order_detail(broker, str(order.get("id") or ""))
        kind = str(detail.get("kind") or "unknown")
        if kind in {"error", "unknown", "deferred"}:
            if kind == "error":
                lines.append(
                    "Exit order detail was not read. The reason was not printed. "
                    + limit_fill_text(order.get("limit"), None)
                )
            continue
        if kind == "filled_no_price":
            apply_order_detail(order, detail)
            _fill_from_position(state, order, broker)
            _stamp_fill_row(state, order)
            changed = True
            lines.append(_detail_line(order, detail) + " No new sell.")
            continue
        if kind not in {"unknown"}:
            apply_order_detail(order, detail)
            _stamp_fill_row(state, order)
            changed = True
            lines.append(_detail_line(order, detail))
        if _known(order.get("fill")) is not None or str(order.get("broker_status") or "") in {"filled", "filled_no_price"}:
            continue
        from webull_bot.execution.forward_fills import _signal_filled, _signal_id as _fill_signal

        if not _signal_filled(state, _fill_signal(str(order.get("key") or ""))):
            lines.append(
                f"Exit {order.get('right')} was not replaced. The entry fill is not confirmed. No order."
            )
            if str(order.get("broker_status") or "") in {"working", "partial"}:
                cancel = getattr(broker, "cancel_order", None)
                if callable(cancel):
                    try:
                        cancel(str(order.get("id") or ""))
                    except Exception as exc:
                        body = _rejection_body(exc)
                        lines.append(f"Exit cancel was rejected. {body}")
                        if "OPENAPI_ORDER_CAN_NOT_BE_CANCEL" in body:
                            if _reconcile_stuck_exit(state, order, broker, lines):
                                changed = True
                            continue
            order["status"] = "rejected"
            order["broker_status"] = "rejected"
            order["error"] = "no entry fill"
            changed = True
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
        if str(order.get("order_type") or "") == "MARKET":
            quote = order.get("quote_px") or order.get("sandbox_price") or "n/a"
            lines.append(
                f"Exit working. MARKET, not a fill. Fill pending. "
                f"Quoted {order.get('quote_side') or 'bid'} {quote}."
            )
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
    if order.get("reverse_blocked"):
        lines.append("A sell is already working. No second sell.")
        return _reconcile_stuck_exit(state, order, broker, lines)
    if order.get("modify_rejected"):
        return _resend_exit(state, order, broker, now, lines, limit=new_limit)
    qty = _qty(order)
    if not _replace_available(broker):
        return _resend_exit(state, order, broker, now, lines, limit=new_limit)
    try:
        _call_replace(state, order, broker, qty, new_limit)
    except TimeoutError:
        lines.append("Exit reprice call timed out. No second order was sent while that call is still out.")
        return False
    except Exception as exc:
        order["modify_rejected"] = True
        body = _rejection_body(exc)
        order["error"] = body
        lines.append(f"Exit reprice was rejected. {body}")
        if "OPENAPI_ORDER_CAN_NOT_BE_CANCEL" in body:
            return _reconcile_stuck_exit(state, order, broker, lines)
        return _resend_exit(state, order, broker, now, lines, limit=new_limit)
    order["limit"] = f"{new_limit:.2f}"
    order["submitted_at"] = to_ny(now).isoformat()
    order["broker_status"] = "working"
    order.pop("dispatch", None)
    lines.append(
        f"Repriced SELL {order.get('qty')} {order.get('right')}. "
        f"{limit_fill_text(order.get('limit'), None)}"
    )
    return True


def _resend_exit(state, order, broker, now, lines, limit: Optional[float] = None) -> bool:
    """Cancel a dead or stuck sell and send one new marketable limit."""
    if order.get("reverse_blocked"):
        lines.append("A sell is already working. No second sell.")
        return _reconcile_stuck_exit(state, order, broker, lines)
    if _pending_exit(order):
        return _finish_exit_send(state, order, broker, now, lines)
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
        except TimeoutError:
            lines.append("Exit cancel call timed out. A second sell was not sent.")
            return False
        except Exception as exc:
            body = _rejection_body(exc)
            lines.append(f"Exit cancel was rejected. A second sell was not sent. {body}")
            if "OPENAPI_ORDER_CAN_NOT_BE_CANCEL" in body:
                return _reconcile_stuck_exit(state, order, broker, lines)
            return False
    return _place_exit(state, order, broker, now, lines, new_limit, remember_prior=True)


def _finish_exit_send(state, order, broker, now, lines) -> bool:
    """Collect a sell that already left this tick. The client order id stays the same."""
    limit = _known(order.get("limit"))
    if limit is None:
        lines.append("Exit resend is still out. No second order was sent.")
        return False
    return _place_exit(state, order, broker, now, lines, limit, client_order_id=str(order.get("id") or ""))


def _place_exit(state, order, broker, now, lines, new_limit: float, client_order_id: str = "", remember_prior: bool = False) -> bool:
    sender = getattr(broker, "place_option_order", None)
    if not callable(sender):
        lines.append("The exit was not resent. The broker has no option order path.")
        return False
    payload = _sell_payload(state, order, new_limit, client_order_id=client_order_id or None)
    if payload is None:
        lines.append("The exit was not resent. The journal has no contract for a new order.")
        return False
    if remember_prior:
        prior = list(order.get("prior_ids") or [])
        if order.get("id"):
            prior.append(order.get("id"))
        order["prior_ids"] = prior
        order["id"] = payload["client_order_id"]
    order["limit"] = f"{new_limit:.2f}"
    order["order_type"] = payload.get("order_type") or "LIMIT"
    order["status"] = "intent"
    order["dispatch"] = "timeout"
    order["fill"] = None
    order.pop("slippage_line", None)
    order.pop("slippage", None)
    bid = _bid(broker, contract_for(state, order))
    if bid is not None:
        order["sandbox_price"] = f"{float(bid):.4f}"
    from webull_bot.execution.forward_orders import remember_quote

    remember_quote(order)
    try:
        sender(payload)
    except TimeoutError:
        lines.append("Exit resend call timed out. No second order was sent while that call is still out.")
        return False
    except Exception as exc:
        if payload.get("order_type") == "MARKET" and not order.get("market_rejected"):
            return _exit_limit_fallback(sender, payload, order, now, lines, new_limit, exc)
        body = _rejection_body(exc)
        order["error"] = body
        order.pop("dispatch", None)
        if "OPENAPI_ORDER_NOT_SUPPORT_REVERSE_OPTION" in body or "NOT_SUPPORT_REVERSE" in body:
            _restore_prior_id(order)
            order["status"] = "submitted"
            order["broker_status"] = "working"
            order["reverse_blocked"] = True
            lines.append(f"Exit resend was rejected. {body} No second sell.")
            return False
        if "OPENAPI_ORDER_CAN_NOT_BE_CANCEL" in body:
            _restore_prior_id(order)
            lines.append(f"Exit resend was rejected. {body} No second sell.")
            return _reconcile_stuck_exit(state, order, broker, lines)
        order["status"] = "submitted"
        order["broker_status"] = "rejected"
        lines.append(f"Exit resend was rejected. {body}")
        return False
    _mark_exit_working(order, now, lines)
    return True


def _exit_limit_fallback(sender, payload, order, now, lines, new_limit: float, exc: Exception) -> bool:
    """The sandbox rejected a market sell. One limit uses a new client id."""
    from webull_bot.execution.forward_orders import limit_fallback_payload

    order["market_rejected"] = True
    lines.append(f"Exit MARKET was rejected. {_rejection_body(exc)} Sending the marketable limit.")
    fallback = limit_fallback_payload(payload, new_limit)
    prior = list(order.get("prior_ids") or [])
    if order.get("id"):
        prior.append(order.get("id"))
    order["prior_ids"] = prior
    order["id"] = fallback["client_order_id"]
    order["order_type"] = "LIMIT"
    order["limit"] = f"{float(new_limit):.2f}"
    order["status"] = "intent"
    order["dispatch"] = "timeout"
    try:
        sender(fallback)
    except TimeoutError:
        lines.append("Exit resend call timed out. No second order was sent while that call is still out.")
        return False
    except Exception as second:
        order["status"] = "submitted"
        order["broker_status"] = "rejected"
        order.pop("dispatch", None)
        lines.append(f"Exit resend was rejected. {_rejection_body(second)}")
        return False
    _mark_exit_working(order, now, lines)
    return True


def _mark_exit_working(order, now, lines) -> None:
    order["status"] = "submitted"
    order["broker_status"] = "working"
    order["dispatch"] = "done"
    order["submitted_at"] = to_ny(now).isoformat()
    style = "MARKET, not a fill. Fill pending." if order.get("order_type") == "MARKET" else limit_fill_text(order.get("limit"), None)
    lines.append(f"Resent SELL {order.get('qty')} {order.get('right')}. {style}")


def _pending_exit(order: dict) -> bool:
    return str(order.get("status") or "") == "intent" and order.get("dispatch") == "timeout"


def _marketable_limit(state, order, broker, now, expiry: Optional[date]) -> Optional[float]:
    from webull_bot.execution.forward_vwap import _sell_limit

    previous = _known(order.get("limit"))
    if _force_min_limit(expiry, now, previous):
        return MIN_SELL
    bid = _bid(broker, contract_for(state, order))
    if bid is None:
        bid = _known(order.get("sandbox_price"))
    through = None if bid is None else _sell_limit(float(bid))
    if previous is None:
        return through
    stepped = max(MIN_SELL, round(previous - 0.01, 2))
    if through is None:
        return stepped
    return min(through, stepped)


def at_exit_floor(when, expiry) -> bool:
    """True once the sell must already be at the one-cent floor."""
    try:
        local = to_ny(when)
    except Exception:
        return False
    exp = _as_date(expiry)
    if exp is not None and local.date() != exp:
        return False
    if _contract_expired(exp, local):
        return False
    return local.time() >= FLOOR_AT


def _force_min_limit(expiry: Optional[date], now: datetime, previous: Optional[float]) -> bool:
    """Jump to one cent when the one-cent walk would not finish before 15:45."""
    if previous is not None and previous <= MIN_SELL + 1e-9:
        return False
    local = to_ny(now)
    if expiry is not None and local.date() != expiry:
        return False
    if _contract_expired(expiry, now):
        return False
    if local.time() >= FLOOR_AT:
        return True
    if previous is None:
        return False
    cents = int(round((previous - MIN_SELL) * 100))
    if cents <= 0:
        return False
    needed = cents * EXIT_REPRICE_AFTER_S
    deadline = datetime.combine(local.date(), FLAT_AT, tzinfo=local.tzinfo)
    remaining = (deadline - local).total_seconds()
    return remaining <= needed + 1e-9


def _rejection_body(exc: BaseException) -> str:
    """The broker rejection, with credentials stripped."""
    import os

    from webull_bot.logging_setup import _SECRET_ENV, redact_text

    parts = [type(exc).__name__]
    text = str(exc).strip()
    if text:
        parts.append(text)
    response = getattr(exc, "response", None)
    body = getattr(response, "text", None) if response is not None else None
    if body:
        parts.append(str(body))
    secrets = [os.environ.get(name, "") for name in _SECRET_ENV]
    rendered = redact_text(" ".join(parts), secrets)
    if len(rendered) > 400:
        rendered = rendered[:400]
    return rendered or "The rejection body was empty."


def _replace_available(broker) -> bool:
    option = getattr(broker, "replace_option_order", None)
    equity = getattr(broker, "replace_order", None)
    return callable(option) or callable(equity)


def _call_replace(state, order, broker, qty: float, new_limit: float):
    """Reprice one option sell.

    The equity replace body has no symbol, side, or order type. The sandbox
    accepted that shape as a new MARKET buy with quantity 0 and no symbol.
    An option replace sends the contract. A test double that only implements
    ``replace_order`` still receives the old three arguments.
    """
    option = getattr(broker, "replace_option_order", None)
    if callable(option):
        fields = _option_replace_fields(state, order)
        if not fields.get("symbol"):
            raise RuntimeError("OPENAPI_PARAM_ERR option replace is missing the contract")
        return option(str(order.get("id") or ""), qty, limit_price=new_limit, **fields)
    replacer = getattr(broker, "replace_order", None)
    if not callable(replacer):
        raise RuntimeError("the broker has no replace path")
    return replacer(str(order.get("id") or ""), qty, limit_price=new_limit)


def _option_replace_fields(state, order) -> dict:
    payload = _sell_payload(state, order, 0.01)
    if not isinstance(payload, dict):
        return {}
    leg = (payload.get("legs") or [{}])[0]
    if not isinstance(leg, dict):
        leg = {}
    return {
        "symbol": payload.get("symbol") or "",
        "side": payload.get("side") or "SELL",
        "strike_price": leg.get("strike_price"),
        "option_expire_date": leg.get("option_expire_date"),
        "option_type": leg.get("option_type"),
        "position_intent": payload.get("position_intent") or "SELL_TO_CLOSE",
    }


def _restore_prior_id(order: dict) -> None:
    prior = list(order.get("prior_ids") or [])
    if not prior:
        return
    order["id"] = prior.pop()
    order["prior_ids"] = prior


def _fill_from_position(state, order, broker) -> None:
    if _known(order.get("fill")) is not None or broker is None:
        return
    from webull_bot.execution.forward_fills import _price

    view = account_view(broker)
    if not view.get("holdings_ok"):
        return
    held = match_holding(state, order, view.get("holdings") or [])
    price = _price((held or {}).get("avg"))
    if price is None:
        return
    order["fill"] = price
    order["fill_source"] = "position"
    if str(order.get("broker_status") or "") == "filled_no_price":
        order["broker_status"] = "filled"


def _reconcile_stuck_exit(state, order, broker, lines) -> bool:
    """Read the sell again. A filled or still-working order is not resent."""
    detail = read_order_detail(broker, str(order.get("id") or ""), force=True)
    kind = str(detail.get("kind") or "unknown")
    if kind in {"filled", "filled_no_price"} or (kind == "partial" and _known(detail.get("price")) is not None):
        apply_order_detail(order, detail)
        _fill_from_position(state, order, broker)
        _stamp_fill_row(state, order)
        lines.append(_detail_line(order, detail) + " No new sell.")
        return True
    if kind in {"working", "partial"}:
        order["status"] = "submitted"
        order["broker_status"] = kind if kind == "partial" else "working"
        lines.append("Exit is still working. The cancel was not accepted. No second sell.")
        return True
    lines.append("Exit status was not read. No second sell.")
    return False


def exit_retry_decision(order, broker, lines) -> str:
    """What to do with a rejected flatten or exit.

    ``send`` uses a new client id. ``keep`` leaves the working order alone.
    ``filled`` means order detail already has the fill. A reverse rejection
    never sends a second sell.
    """
    if not isinstance(order, dict):
        return "keep"
    error = str(order.get("error") or "")
    if "NOT_SUPPORT_REVERSE" in error or order.get("reverse_blocked"):
        order["reverse_blocked"] = True
        order["status"] = "submitted"
        order["broker_status"] = "working"
        lines.append(f"Exit was not retried. {error or 'A sell is already working.'} No second sell.")
        _reconcile_stuck_exit({}, order, broker, lines)
        return "keep"
    detail = read_order_detail(broker, str(order.get("id") or ""), force=True)
    kind = str(detail.get("kind") or "unknown")
    if kind in {"filled", "filled_no_price"} or (kind == "partial" and _known(detail.get("price")) is not None):
        apply_order_detail(order, detail)
        lines.append(_detail_line(order, detail) + " No new sell.")
        return "filled"
    if kind in {"working", "partial"}:
        order["status"] = "submitted"
        order["broker_status"] = "working" if kind == "working" else "partial"
        lines.append("Exit is still working. No second sell.")
        return "keep"
    if kind in {"rejected", "cancelled", "expired"} or (error and not order.get("flatten_retried")):
        if kind in {"unknown", "error", "deferred", ""} and not error:
            lines.append("Exit was not retried. Order detail was not read.")
            return "keep"
        from webull_bot.broker.webull import new_client_order_id

        prior = list(order.get("prior_ids") or [])
        if order.get("id"):
            prior.append(order.get("id"))
        order["prior_ids"] = prior
        order["id"] = new_client_order_id()
        order.pop("error", None)
        order["flatten_retried"] = True
        order["status"] = "intent"
        lines.append("Flatten retry with a new order id.")
        return "send"
    lines.append("Exit was not retried. Order detail was not read.")
    return "keep"


def _bid(broker, contract: str) -> Optional[float]:
    """Live bid, walking from a cache-only exit view to the broker behind it."""
    for current in _broker_chain(broker):
        price = _quote_bid(current, contract)
        if price is not None:
            return price
    return None


def _quote_bid(broker, contract: str) -> Optional[float]:
    if not contract or broker is None or not hasattr(broker, "option_contract_quote"):
        return None
    try:
        quote = broker.option_contract_quote(contract)
    except Exception:
        return None
    if not isinstance(quote, dict):
        return None
    return _known(quote.get("bid"))


def _sell_payload(state, order, limit: float, client_order_id: Optional[str] = None) -> Optional[dict]:
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
    from webull_bot.execution.forward_orders import style_option_payload

    payload = build_single_option_order(
        client_order_id=client_order_id or new_client_order_id(),
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
    return style_option_payload(payload)


def _detail_line(order: dict, detail: dict) -> str:
    kind = str(detail.get("kind") or order.get("broker_status") or "")
    base = f"{order.get('side')} {order.get('qty')} {order.get('right')} "
    if kind == "filled":
        from webull_bot.execution.forward_orders import attach_slippage

        attach_slippage(order)
        slip = f" {order['slippage_line']}" if order.get("slippage_line") else ""
        return (
            base
            + limit_fill_text(order.get("limit"), order.get("fill"))
            + f" Status filled at {order.get('fill_time') or 'n/a'}."
            + slip
        )
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
    elif (
        status in _FILLED
        or _qty_filled(filled, total)
        or (price is not None and status is None and not partial_qty)
    ):
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


_OCC_RE = re.compile(r"^([A-Z]{1,6})(\d{6})([CP])(\d{8})$")
_TICKER_RE = re.compile(r"^[A-Z]{1,6}$")
_STRIKE_KEYS = ("strike_price", "strikePrice", "strike", "exercise_price")
_EXPIRY_KEYS = (
    "option_expire_date",
    "optionExpireDate",
    "expiration_date",
    "expirationDate",
    "expire_date",
    "expireDate",
    "expiry",
    "exp_date",
    "maturity_date",
    "maturityDate",
)
_RIGHT_KEYS = ("option_type", "optionType", "put_call", "putCall", "right", "call_put")
_SYMBOL_KEYS = ("option_symbol", "optionSymbol", "occ_symbol", "contract_symbol", "symbol", "symbol_name", "ticker")
_UNDERLYING_KEYS = ("underlying_symbol", "underlying", "symbol", "ticker", "symbol_name")
_ID_KEYS = ("instrument_id", "instrumentId", "contract_id", "contractId")
_AVG_KEYS = (
    "avg_cost",
    "avgPrice",
    "avg_price",
    "cost_price",
    "average_cost",
    "costPrice",
    "unit_cost",
    "averagePrice",
)
_QTY_KEYS = ("quantity", "qty", "position", "position_qty")


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
        parsed = _parse_position(row)
        if parsed:
            found.append(parsed)
    return found


def _parse_position(row: Any) -> Optional[dict]:
    """One held contract. Nested legs supply strike, expiry, and right."""
    if not isinstance(row, dict):
        return None
    bag = {
        "symbols": [],
        "instrument_ids": [],
        "underlying": "",
        "strike": None,
        "expiry": "",
        "right": "",
        "quantity": None,
        "avg": None,
        "occs": [],
        "raw_symbol": "",
        "fields": [],
    }
    _collect_position(row, bag, 0)
    if bag["quantity"] in (None, 0, 0.0):
        return None
    occ = bag["occs"][0] if bag["occs"] else ""
    if not occ:
        occ = _built_occ(bag["underlying"], bag["expiry"], bag["right"], bag["strike"])
        if occ and occ not in bag["symbols"]:
            bag["symbols"].append(occ)
            bag["occs"].append(occ)
    if occ:
        parsed = _parse_occ(occ)
        bag["underlying"] = bag["underlying"] or parsed.get("underlying") or ""
        if bag["strike"] is None:
            bag["strike"] = parsed.get("strike")
        bag["expiry"] = bag["expiry"] or parsed.get("expiry") or ""
        bag["right"] = bag["right"] or parsed.get("right") or ""
    display = occ or bag["underlying"] or (bag["symbols"][0] if bag["symbols"] else "")
    if not display and not bag["instrument_ids"]:
        return None
    if not display:
        display = str(bag["instrument_ids"][0])
    option_known = bool(bag["occs"]) or (
        bag["strike"] is not None and bool(bag["right"]) and bool(bag["expiry"])
    )
    return {
        "symbol": display,
        "quantity": bag["quantity"],
        "symbols": bag["symbols"],
        "avg": bag["avg"],
        "underlying": bag["underlying"],
        "strike": bag["strike"],
        "expiry": str(bag["expiry"])[:10],
        "right": bag["right"],
        "instrument_ids": bag["instrument_ids"],
        "option_known": option_known,
        "raw_symbol": bag.get("raw_symbol") or "",
        "fields": list(bag.get("fields") or []),
    }


def _collect_position(node: dict, bag: dict, depth: int) -> None:
    if depth > 6 or not isinstance(node, dict):
        return
    if bag["quantity"] is None:
        for key in _QTY_KEYS:
            number = _known(node.get(key))
            if number is not None:
                bag["quantity"] = number
                break
    if bag["avg"] is None:
        for key in _AVG_KEYS:
            number = _known(node.get(key))
            if number is not None:
                bag["avg"] = number
                break
    for key in _ID_KEYS:
        value = node.get(key)
        if value in (None, ""):
            continue
        text = str(value)
        if text not in bag["instrument_ids"]:
            bag["instrument_ids"].append(text)
    for key in _SYMBOL_KEYS:
        raw = node.get(key)
        if not raw:
            continue
        _absorb_symbol_text(raw, bag, key)
    _note_row_fields(node, bag)
    if bag["strike"] is None:
        for key, value in node.items():
            if "strike" not in re.sub(r"[^a-z]", "", str(key).lower()) and str(key) not in _STRIKE_KEYS:
                continue
            number = _strike_number(value)
            if number is not None:
                bag["strike"] = number
                break
    if bag["strike"] is None:
        for key in _STRIKE_KEYS:
            number = _strike_number(node.get(key))
            if number is not None:
                bag["strike"] = number
                break
    if not bag["expiry"]:
        for key in _EXPIRY_KEYS:
            found = _as_date(node.get(key))
            if found is not None:
                bag["expiry"] = found.isoformat()
                break
    if not bag["right"]:
        for key in _RIGHT_KEYS:
            right = _norm_right(node.get(key))
            if right:
                bag["right"] = right
                break
    for value in node.values():
        if isinstance(value, dict):
            _collect_position(value, bag, depth + 1)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    _collect_position(item, bag, depth + 1)


def _absorb_symbol_text(raw, bag: dict, key: str) -> None:
    """Pull an OCC symbol out of a ticker or a longer contract string."""
    text = str(raw).upper().strip()
    if key in {"symbol", "ticker", "symbol_name"} and not bag.get("raw_symbol"):
        bag["raw_symbol"] = str(raw).strip()
    compact = re.sub(r"[^A-Z0-9]", "", text)
    match = re.search(r"[A-Z]{1,6}\d{6}[CP]\d{8}", compact)
    if match:
        occ = match.group(0)
        if occ not in bag["occs"]:
            bag["occs"].append(occ)
        if occ not in bag["symbols"]:
            bag["symbols"].append(occ)
        parsed = _parse_occ(occ)
        bag["underlying"] = bag["underlying"] or parsed.get("underlying") or ""
        if bag["strike"] is None:
            bag["strike"] = parsed.get("strike")
        bag["expiry"] = bag["expiry"] or parsed.get("expiry") or ""
        bag["right"] = bag["right"] or parsed.get("right") or ""
        return
    if key in _UNDERLYING_KEYS and _TICKER_RE.match(text):
        bag["underlying"] = bag["underlying"] or text
        if text not in bag["symbols"]:
            bag["symbols"].append(text)


def _strike_number(value) -> Optional[float]:
    number = _known(value)
    if number is None and isinstance(value, dict):
        for inner in value.values():
            number = _known(inner)
            if number is not None:
                break
    if number is None or number >= 20000:
        return None
    return number


def _note_row_fields(node: dict, bag: dict) -> None:
    """Keep the scalar fields that identify the contract, for the watch log."""
    fields = bag.setdefault("fields", [])
    if len(fields) >= 16:
        return
    for key, value in node.items():
        if isinstance(value, (dict, list)) or isinstance(value, bool):
            continue
        low = str(key).lower()
        if any(part in low for part in ("secret", "token", "password")):
            continue
        if not any(
            part in low
            for part in (
                "symbol",
                "strike",
                "expir",
                "expire",
                "option",
                "qty",
                "quant",
                "cost",
                "avg",
                "instrument",
                "right",
                "put",
                "call",
                "type",
            )
        ):
            continue
        shown = f"{key}={value}"
        if shown not in fields and len(fields) < 16:
            fields.append(shown)


def _parse_occ(contract: str) -> dict:
    match = _OCC_RE.match(str(contract or "").upper())
    if match is None:
        return {}
    try:
        expiry = datetime.strptime(match.group(2), "%y%m%d").date().isoformat()
    except ValueError:
        return {}
    return {
        "underlying": match.group(1),
        "expiry": expiry,
        "right": match.group(3),
        "strike": int(match.group(4)) / 1000.0,
    }


def _built_occ(underlying: str, expiry, right: str, strike) -> str:
    if not underlying or strike is None or not expiry or not right:
        return ""
    if not _TICKER_RE.match(str(underlying).upper()):
        return ""
    found = _as_date(expiry)
    if found is None:
        return ""
    try:
        from webull_bot.execution.forward_quotes import occ_symbol

        return occ_symbol(str(underlying), found, str(right), float(strike))
    except Exception:
        return ""


def _norm_right(value) -> str:
    text = str(value or "").strip().upper()
    if text in {"C", "CALL"} or text.startswith("CALL"):
        return "C"
    if text in {"P", "PUT"} or text.startswith("PUT"):
        return "P"
    return ""


def _order_identity(state: dict, order: dict) -> dict:
    contract = contract_for(state, order) if isinstance(state, dict) else ""
    parsed = _parse_occ(contract)
    underlying = str(parsed.get("underlying") or "")
    strike = parsed.get("strike")
    expiry = str(parsed.get("expiry") or "")
    right = str(parsed.get("right") or "")
    ids = set()
    sources = [order]
    if isinstance(state, dict):
        sources.extend(_related(state, _signal_id(str(order.get("key") or ""))))
    for source in sources:
        if not isinstance(source, dict):
            continue
        if not underlying:
            ticker = str(source.get("symbol") or source.get("underlying") or "").upper()
            if _TICKER_RE.match(ticker):
                underlying = ticker
        if strike is None:
            strike = _known(source.get("strike") if source.get("strike") not in (None, "") else source.get("order_strike"))
        if not expiry:
            found = _as_date(source.get("expiry"))
            if found is not None:
                expiry = found.isoformat()
        if not right:
            right = _norm_right(source.get("option_type") or source.get("right"))
        for key in _ID_KEYS:
            if source.get(key) not in (None, ""):
                ids.add(str(source.get(key)))
    return {
        "underlying": underlying,
        "strike": strike,
        "expiry": expiry[:10],
        "right": right,
        "instrument_ids": ids,
        "contract": contract,
    }


def _identity_match(row: dict, identity: dict) -> bool:
    row_ids = {str(item) for item in row.get("instrument_ids") or [] if item not in (None, "")}
    if identity["instrument_ids"] and row_ids and identity["instrument_ids"] & row_ids:
        return True
    if not identity["underlying"] or identity["strike"] is None or not identity["expiry"] or not identity["right"]:
        return False
    if not row.get("option_known") and row.get("strike") in (None, "") and not row.get("right"):
        return False
    row_under = str(row.get("underlying") or "").upper()
    if not row_under:
        row_under = str(_parse_occ(str(row.get("symbol") or "")).get("underlying") or "")
    if row_under != identity["underlying"]:
        return False
    if row.get("strike") in (None, ""):
        return False
    if abs(float(row["strike"]) - float(identity["strike"])) > 0.001:
        return False
    if str(row.get("expiry") or "")[:10] != identity["expiry"]:
        return False
    return _norm_right(row.get("right")) == identity["right"]


def _loose_match(state: dict, order: dict, holdings: list[dict], identity: dict) -> Optional[dict]:
    """Match without a strike: underlying, right, expiry, quantity, and average.

    The sandbox row often names the put and the expiry and leaves the strike
    off the line. Quantity and the average keep a 3-lot at $0.77 off a
    1-lot at $3.53, and off a different limit on the same expiry.
    """
    qty = _order_qty(state, order)
    prices = _order_premiums(order)
    if qty is None or not prices:
        return None
    chosen = None
    chosen_gap = None
    for row in holdings:
        if not isinstance(row, dict) or not _loose_row(identity, qty, prices, row):
            continue
        gap = _premium_gap(prices, row)
        if chosen is None or (gap is not None and (chosen_gap is None or gap < chosen_gap)):
            chosen = row
            chosen_gap = gap
    if chosen is None or not _this_order_is_closest(state, order, chosen):
        return None
    return chosen


def _loose_row(identity: dict, qty: Optional[float], prices: list[float], row: dict) -> bool:
    if qty is None or not prices or not identity.get("underlying") or not identity.get("right") or not identity.get("expiry"):
        return False
    if str(row.get("underlying") or "").upper() != identity["underlying"]:
        return False
    if _norm_right(row.get("right")) != identity["right"]:
        return False
    if str(row.get("expiry") or "")[:10] != identity["expiry"]:
        return False
    held_qty = _known(row.get("quantity"))
    if held_qty is None or abs(held_qty - float(qty)) > 0.01:
        return False
    return _premium_gap(prices, row) is not None


def _premium_gap(prices: list[float], row: dict) -> Optional[float]:
    avg = _known(row.get("avg"))
    if avg is None or not prices:
        return None
    gaps = [abs(avg - price) for price in prices if abs(avg - price) <= _PREMIUM_MATCH]
    if not gaps:
        return None
    return min(gaps)


def _order_qty(state: dict, order: dict) -> Optional[float]:
    sources = [order]
    if isinstance(state, dict):
        sources.extend(_related(state, _signal_id(str(order.get("key") or ""))))
    for source in sources:
        if not isinstance(source, dict):
            continue
        raw = source.get("qty")
        if raw in (None, ""):
            raw = source.get("quantity")
        number = _known(raw)
        if number is not None:
            return number
    return None


def _this_order_is_closest(state: dict, order: dict, row: dict) -> bool:
    """One holding is not adopted by a worse-priced order in the same book."""
    if not isinstance(state, dict):
        return True
    gap = _premium_gap(_order_premiums(order), row)
    if gap is None:
        return False
    for other in state.get("orders") or []:
        if other is order or not isinstance(other, dict) or str(other.get("kind") or "") != "entry":
            continue
        if _known(other.get("fill")) is not None:
            continue
        other_qty = _order_qty(state, other)
        other_prices = _order_premiums(other)
        other_identity = _order_identity(state, other)
        if not _loose_row(other_identity, other_qty, other_prices, row):
            continue
        other_gap = _premium_gap(other_prices, row)
        if other_gap is not None and other_gap + 1e-9 < gap:
            return False
    return True


def _premium_match(state: dict, order: dict, holdings: list[dict], identity: dict) -> Optional[dict]:
    underlying = identity.get("underlying") or ""
    if not underlying or not _sole_open_entry(state, underlying, order):
        return None
    prices = _order_premiums(order)
    if not prices:
        return None
    for row in holdings:
        if not isinstance(row, dict) or not _bare_underlying(row, underlying):
            continue
        avg = _known(row.get("avg"))
        if avg is None:
            continue
        if any(abs(avg - price) <= _PREMIUM_MATCH for price in prices):
            return row
    return None


def _bare_underlying(row: dict, underlying: str) -> bool:
    if str(row.get("underlying") or "").upper() != underlying:
        return False
    if row.get("option_known"):
        return False
    if row.get("strike") not in (None, "") or row.get("right") or row.get("expiry"):
        return False
    for name in row.get("symbols") or []:
        if _OCC_RE.match(str(name).upper()):
            return False
    symbol = str(row.get("symbol") or "").upper()
    return not _OCC_RE.match(symbol)


def _sole_open_entry(state: dict, underlying: str, order: dict) -> bool:
    if not underlying or not isinstance(state, dict):
        return False
    matches = []
    for row in state.get("orders") or []:
        if not isinstance(row, dict) or str(row.get("kind") or "") != "entry":
            continue
        if str(row.get("status") or "") not in {"submitted", "intent", "partial"}:
            continue
        if _known(row.get("fill")) is not None:
            continue
        if str(row.get("broker_status") or "") in {"filled", "cancelled", "canceled", "expired", "rejected"}:
            continue
        if _order_identity(state, row).get("underlying") != underlying:
            continue
        matches.append(row)
    return len(matches) == 1 and matches[0] is order


def _order_premiums(order: dict) -> list[float]:
    found = []
    for key in ("sandbox_price", "quote_px", "limit", "sandbox_ask"):
        number = _known(order.get(key))
        if number is not None:
            found.append(number)
    return found


def _describe_holding(row: dict) -> str:
    bits = ["-", str(row.get("underlying") or row.get("raw_symbol") or row.get("symbol") or "")]
    right = _norm_right(row.get("right"))
    if right:
        bits.append("PUT" if right == "P" else "CALL")
    if row.get("strike") in (None, ""):
        bits.append("strike missing")
    else:
        strike = float(row["strike"])
        shown = str(int(strike)) if strike == int(strike) else str(strike)
        bits.append(f"strike {shown}")
    raw_symbol = row.get("raw_symbol") or row.get("symbol") or ""
    if raw_symbol:
        bits.append(f"symbol {raw_symbol}")
    if row.get("expiry"):
        bits.append(str(row.get("expiry"))[:10])
    bits.append(f"quantity {row.get('quantity')}")
    if row.get("avg") not in (None, ""):
        bits.append(f"avg {row.get('avg')}")
    text = " ".join(bits)
    fields = [str(item) for item in (row.get("fields") or [])]
    if fields:
        text += " [" + ", ".join(fields[:12]) + "]"
    return text


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


def settle_expired_unsold(state: dict, broker, now: datetime, holdings: list[dict], lines: list[str]) -> set:
    """Close a 0DTE that expired without a sale. Does not place an order.

    Out of the money settles at zero, which is a full premium loss. In the
    money settles at intrinsic value. Returns the signal ids that were closed.
    """
    closed: set = set()
    if not isinstance(state, dict):
        return closed
    for signal in state.get("signals") or []:
        if not isinstance(signal, dict) or signal.get("status") not in {"open", "closed"}:
            continue
        if str(signal.get("settlement") or "") == "expiry":
            continue
        if str(signal.get("reason") or "").startswith("unresolved:"):
            continue
        expiry = _as_date(signal.get("expiry"))
        if not _zero_dte(signal, expiry) or not _contract_expired(expiry, now):
            continue
        signal_id = str(signal.get("id") or "")
        order = _exit_order(state, signal_id)
        if order is not None and str(order.get("settlement") or "") == "expiry":
            continue
        if _sold(order):
            continue
        from webull_bot.execution.forward_fills import _signal_filled

        if order is None and not _signal_filled(state, signal_id):
            continue
        if order is not None and order.get("error") == "no entry fill":
            continue
        contract = str(signal.get("option_symbol") or "")
        if not contract and order is not None:
            contract = contract_for(state, order)
        if contract and _held(contract, holdings):
            lines.append(
                f"{contract}: the contract has expired and the account still holds it. "
                "The book was not closed."
            )
            continue
        spot = _settlement_spot(broker, _underlying_symbol(signal, order), expiry, now)
        if spot is None:
            lines.append(
                f"{signal_id}: the contract expired unsold. The expiry price is unknown. "
                "The book was not closed."
            )
            continue
        intrinsic = _intrinsic(signal, order, spot)
        _book_expiry(state, signal, order, spot, intrinsic, now, contract)
        kind = "OTM, full premium loss" if intrinsic <= 1e-9 else f"intrinsic {intrinsic:.2f}"
        lines.append(
            f"Expired unsold {contract or signal_id}. Underlying close {spot:.2f}. {kind}. "
            "No order was sent."
        )
        closed.add(signal_id)
    if closed:
        state["positions"] = [
            row
            for row in (state.get("positions") or [])
            if not (isinstance(row, dict) and str(row.get("id") or "") in closed)
        ]
    return closed


def _book_expiry(state, signal, order, spot: float, intrinsic: float, now: datetime, contract: str) -> None:
    when = to_ny(now).isoformat()
    price = round(max(0.0, intrinsic), 2)
    signal_id = str(signal.get("id") or "")
    if order is None:
        order = {
            "key": f"{signal_id}|exit",
            "id": f"{signal_id}|expiry",
            "kind": "exit",
            "side": "SELL",
            "qty": str(signal.get("qty") or 1),
            "symbol": signal.get("symbol"),
            "right": signal.get("option_type") or signal.get("right"),
            "option_type": signal.get("option_type") or signal.get("right"),
            "strike": signal.get("strike"),
            "expiry": signal.get("expiry"),
            "option_symbol": contract,
            "status": "cancelled",
        }
        state.setdefault("orders", []).append(order)
    order["fill"] = price
    order["settlement"] = "expiry"
    order["settlement_underlying"] = spot
    order["broker_status"] = "expired"
    order["status"] = "cancelled"
    order["fill_time"] = when
    order.pop("dispatch", None)
    signal["status"] = "closed"
    signal["settlement"] = "expiry"
    signal["settlement_underlying"] = spot
    signal["intrinsic"] = price
    if not signal.get("exit_time"):
        signal["exit_time"] = when
    _stamp_expiry_fill(state, signal_id, price, when)
    found = False
    for row in state.get("exits") or []:
        if isinstance(row, dict) and row.get("id") == signal_id:
            row["settlement"] = "expiry"
            row["settlement_underlying"] = spot
            row["intrinsic"] = price
            found = True
    if not found:
        state.setdefault("exits", []).append(
            {
                "id": signal_id,
                "time": when,
                "right": signal.get("right"),
                "reason": "expiry",
                "underlying": spot,
                "settlement": "expiry",
                "intrinsic": price,
            }
        )


def _stamp_expiry_fill(state, signal_id: str, price: float, when: str) -> None:
    for row in state.get("fills") or []:
        if not isinstance(row, dict):
            continue
        if row.get("id") == signal_id and str(row.get("side") or "") == "SELL":
            row["fill"] = price
            row["fill_time"] = when
            row["fill_source"] = "expiry"
            return
    state.setdefault("fills", []).append(
        {
            "id": signal_id,
            "side": "SELL",
            "qty": "1",
            "price": f"{price:.2f}",
            "fill": price,
            "time": when,
            "fill_source": "expiry",
        }
    )


def _exit_order(state: dict, signal_id: str) -> Optional[dict]:
    key = f"{signal_id}|exit"
    for order in state.get("orders") or []:
        if isinstance(order, dict) and str(order.get("key") or "") == key:
            return order
    return None


def _sold(order: Optional[dict]) -> bool:
    if not isinstance(order, dict) or str(order.get("settlement") or "") == "expiry":
        return False
    if _known(order.get("fill")) is not None:
        return True
    qty = _known(order.get("filled_qty"))
    return qty is not None and qty > 0


def _zero_dte(signal: dict, expiry: Optional[date]) -> bool:
    if expiry is None:
        return False
    opened = _as_date(signal.get("entry_time") or signal.get("signal_time") or signal.get("time"))
    if opened is None:
        return True
    return opened == expiry


def _underlying_symbol(signal: dict, order: Optional[dict]) -> str:
    raw = str((signal or {}).get("symbol") or (order or {}).get("symbol") or "")
    upper = raw.upper()
    if upper.startswith("QQQ"):
        return "QQQ"
    if upper.startswith("SPY"):
        return "SPY"
    return upper or "QQQ"


def _intrinsic(signal: dict, order: Optional[dict], spot: float) -> float:
    strike = _known((signal or {}).get("strike") or (order or {}).get("strike"))
    if strike is None:
        strike = _strike_from_occ(str((signal or {}).get("option_symbol") or (order or {}).get("option_symbol") or ""))
    if strike is None:
        return 0.0
    right = str((signal or {}).get("option_type") or (signal or {}).get("right") or (order or {}).get("option_type") or (order or {}).get("right") or "")
    token = right.strip().upper()
    if token in {"P", "PUT"}:
        return max(0.0, strike - spot)
    if token in {"C", "CALL"}:
        return max(0.0, spot - strike)
    return 0.0


def _strike_from_occ(contract: str) -> Optional[float]:
    import re

    match = re.search(r"[CP](\d{8})$", str(contract or "").upper())
    if match is None:
        return None
    return int(match.group(1)) / 1000.0


def _settlement_spot(broker, symbol: str, expiry: Optional[date], now: datetime) -> Optional[float]:
    if expiry is None or not symbol:
        return None
    getter = getattr(broker, "underlying_close", None)
    if callable(getter):
        try:
            price = _known(getter(symbol, expiry.isoformat()))
        except Exception:
            price = None
        if price is not None:
            return price
    local = to_ny(now)
    if local.date() == expiry and local.time() >= time(16, 0):
        from webull_bot.execution.forward_vwap import _positive

        quote = getattr(broker, "underlying_quote", None)
        if callable(quote):
            try:
                price = _positive(quote(symbol))
            except Exception:
                price = None
            if price is not None:
                return price
    return _yahoo_close(symbol, expiry)


def _yahoo_close(symbol: str, expiry: date) -> Optional[float]:
    try:
        import yfinance as yf
    except Exception:
        return None
    try:
        frame = yf.Ticker(symbol).history(
            start=expiry.isoformat(),
            end=(expiry + timedelta(days=1)).isoformat(),
            auto_adjust=False,
        )
    except Exception:
        return None
    if frame is None or getattr(frame, "empty", True) or "Close" not in getattr(frame, "columns", []):
        return None
    return _known(frame["Close"].iloc[-1])


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


def _underlying_spot(broker, book: str):
    """One underlying quote for the stop and 1R check. A failure leaves the price unknown."""
    from webull_bot.execution.forward_four_hour import NAME as HOUR_NAME
    from webull_bot.execution.forward_trapdoor import NAME as TRAP_NAME
    from webull_bot.execution.forward_vwap import BOOKS, _positive

    symbol = "QQQ" if book in {TRAP_NAME, HOUR_NAME} else BOOKS.get(book)
    getter = getattr(broker, "underlying_quote", None)
    if not symbol or not callable(getter):
        return None
    try:
        return _positive(getter(symbol))
    except Exception:
        return None


def _load(journal, book: str):
    from webull_bot.execution.forward_trapdoor import NAME as TRAP_NAME
    from webull_bot.execution.forward_trapdoor import STAKE as TRAP_STAKE
    from webull_bot.execution.forward_trapdoor import load_state as trap_load

    if book == TRAP_NAME:
        return trap_load(journal), TRAP_STAKE
    from webull_bot.execution.forward_four_hour import NAME as HOUR_NAME
    from webull_bot.execution.forward_four_hour import STAKE as HOUR_STAKE
    from webull_bot.execution.forward_four_hour import load_state as hour_load

    if book == HOUR_NAME:
        return hour_load(journal), HOUR_STAKE
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
