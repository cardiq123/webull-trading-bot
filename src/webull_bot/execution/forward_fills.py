"""An entry is not a position until the sandbox fill is confirmed.

A working buy stays a working order. No sell is sent for it. If that buy is
still unfilled when the fill window ends, the underlying leaves the stop and
the 1R target, or a sell was already rejected, the buy is cancelled and the
signal is marked unfilled. Live trading stays off. This module does not
place an entry.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from webull_bot.calendar import to_ny
from webull_bot.execution.forward_vwap import _inside, max_entry_delay_minutes

UNFILLED = "unfilled"
# One position-row log per book per minute. The first call is startup.
_HOLDING_LOG: dict = {}


def broker_reports_detail(broker) -> bool:
    """True when this broker can read sandbox order detail. A unit broker cannot."""
    if broker is None:
        return False
    if callable(getattr(broker, "order_detail", None)):
        return True
    trade = getattr(broker, "_trade", None)
    method = getattr(getattr(trade, "order_v3", None), "get_order_detail", None)
    return callable(method)


def note_entry_submission(state, built, position, order, now, broker) -> None:
    """Record the buy. A sandbox order stays working until detail says it filled."""
    stamp = to_ny(now).isoformat()
    order["submitted_at"] = stamp
    order["kind"] = "entry"
    if broker_reports_detail(broker):
        built["status"] = "working"
        position["entry_filled"] = False
        lines_debit = False
    else:
        built["status"] = "open"
        position["entry_filled"] = True
        lines_debit = True
    position["submitted_at"] = stamp
    if lines_debit:
        state["settled"] = float(state.get("settled") or 0.0) - float(built.get("model_debit") or 0.0)


def position_is_filled(state, position) -> bool:
    """True only when the entry fill is known, or this position never had an order to read."""
    if not isinstance(position, dict):
        return False
    if position.get("entry_filled") is True:
        return True
    order = entry_order(state, position.get("id"))
    if order is None:
        return position.get("entry_filled") is not False
    if _price(order.get("fill")) is not None:
        return True
    return str(order.get("broker_status") or "") in {"filled", "partial"}


def exit_allowed(state, position, lines) -> bool:
    """A sell waits until the buy has filled."""
    if position_is_filled(state, position):
        return True
    lines.append(
        f"Exit {position.get('right')} was not sent. "
        "The entry fill is not confirmed. No order."
    )
    return False


def sync_working_entries(state, broker, now, spot, lines) -> bool:
    """Read entry status, promote a fill, or cancel a buy that will not fill.

    Does not place an exit and does not place a new entry.
    """
    if not isinstance(state, dict):
        return False
    changed = adopt_held_entries(state, broker, now, lines)
    if restore_from_order_detail(state, broker, lines):
        changed = True
    for order in list(state.get("orders") or []):
        if not isinstance(order, dict) or str(order.get("kind") or "") != "entry":
            continue
        if str(order.get("status") or "") not in {"submitted", "intent", "partial"}:
            continue
        signal_id = _signal_id(str(order.get("key") or ""))
        if not signal_id:
            continue
        held = _position(state, signal_id)
        if held is not None and held.get("entry_filled") is True:
            continue
        if _price(order.get("fill")) is not None or str(order.get("broker_status") or "") == "filled":
            if _promote(state, order, lines):
                changed = True
            continue
        detail = _read(broker, str(order.get("id") or ""))
        kind = str(detail.get("kind") or "unknown")
        if _detail_confirms_fill(kind, detail):
            _store_fill(order, detail)
            if _price(order.get("fill")) is None:
                _confirm_from_account(state, order, broker)
            _promote(state, order, lines)
            changed = True
            continue
        if _confirm_from_account(state, order, broker):
            _promote(state, order, lines)
            changed = True
            continue
        if kind in {"cancelled", "expired", "rejected"}:
            if _keep_because_held(state, order, broker, lines):
                changed = True
                continue
            held, listing = _account_presence(state, order, broker)
            if held is None:
                lines.append(
                    "Order detail says the entry is not working. Positions were not read. "
                    "The buy was not marked unfilled."
                )
                continue
            if held is True or listing in {"working", "filled"}:
                lines.append(
                    "Entry status was not confirmed. No exit was sent and the buy was not cancelled."
                )
                continue
            order["broker_status"] = kind
            order["status"] = kind
            _release(state, signal_id, f"the entry was {kind}", lines, broker)
            changed = True
            continue
        reason = _cancel_reason(state, order, signal_id, now, spot)
        if reason is None:
            if kind == "working":
                if order.get("broker_status") != "working":
                    order["broker_status"] = "working"
                    changed = True
                lines.append(
                    f"Entry working. {_limit_text(order)} No exit until the fill is confirmed."
                )
            continue
        held, listing = _account_presence(state, order, broker)
        if held is True:
            if _keep_because_held(state, order, broker, lines):
                changed = True
            continue
        if listing == "filled":
            lines.append(
                "Entry status was not confirmed. No exit was sent and the buy was not cancelled."
            )
            continue
        if kind in {"unknown", "error", "deferred", ""} and listing != "working":
            lines.append(
                "Order detail was not read. Entry status was not confirmed. "
                "The buy was not marked unfilled. No exit was sent and the buy was not cancelled."
            )
            continue
        if kind == "working" or listing == "working":
            if _keep_because_held(state, order, broker, lines):
                changed = True
                continue
            if _cancel(broker, order, lines):
                if _promote_if_detail_filled(state, order, broker, lines):
                    changed = True
                    continue
                order["broker_status"] = "cancelled"
                order["status"] = "cancelled"
                _release(state, signal_id, reason, lines, broker)
                changed = True
            elif "OPENAPI_ORDER_CAN_NOT_BE_CANCEL" in str(order.get("cancel_error") or ""):
                if _promote_if_detail_filled(state, order, broker, lines):
                    changed = True
                else:
                    lines.append(
                        "Entry is still working. The cancel was not accepted. It was not marked unfilled."
                    )
            else:
                lines.append("Entry is still working. The cancel was not accepted. No exit was sent.")
            continue
        if held is False and listing == "absent" and kind in {"cancelled", "expired", "rejected"}:
            order["broker_status"] = kind
            order["status"] = kind
            _release(state, signal_id, reason, lines, broker)
            changed = True
            continue
        lines.append(
            "Entry status was not confirmed. No exit was sent and the buy was not cancelled."
        )
    _drop_rejected_exits(state, lines)
    return changed


def entry_needs_send(order) -> bool:
    """True when this buy was journaled and the sandbox has not accepted it.

    A model price is still a real order. ``submitted`` and a working broker
    status are left alone so a restart does not send the buy a second time.
    """
    if not isinstance(order, dict) or str(order.get("kind") or "") not in {"", "entry"}:
        return False
    if _price(order.get("fill")) is not None:
        return False
    if str(order.get("broker_status") or "") in {"working", "filled", "partial", "cancelled", "canceled", "expired"}:
        return False
    status = str(order.get("status") or "")
    if status in {"intent", "not_sent"}:
        return True
    return status == "rejected" and str(order.get("price_source") or "") == "model"


def entry_order(state, signal_id) -> Optional[dict]:
    key = f"{signal_id}|entry"
    for order in state.get("orders") or []:
        if isinstance(order, dict) and str(order.get("key") or "") == key:
            return order
    return None


def _promote(state, order, lines) -> bool:
    signal_id = _signal_id(str(order.get("key") or ""))
    position = _position(state, signal_id)
    if position is not None and position.get("entry_filled") is True and (_signal(state, signal_id) or {}).get("status") == "open":
        return False
    for signal in state.get("signals") or []:
        if isinstance(signal, dict) and str(signal.get("id") or "") == signal_id:
            if signal.get("status") != "closed":
                signal["status"] = "open"
    if position is not None:
        position["entry_filled"] = True
    _remember_confirmed_fill(state, order, signal_id)
    if _price(order.get("fill")) is not None:
        from webull_bot.execution.forward_orders import attach_slippage

        lines.append(
            f"Entry filled {order.get('fill')}. "
            f"Limit {order.get('limit')} was not the fill."
        )
        slip = attach_slippage(order)
        if slip:
            lines.append(slip)
    return True


def _remember_confirmed_fill(state, order, signal_id: str) -> None:
    price = _price(order.get("fill"))
    if price is None:
        return
    for row in state.get("fills") or []:
        if not isinstance(row, dict):
            continue
        if str(row.get("id") or "") == signal_id and str(row.get("side") or "") == "BUY":
            row["fill"] = price
            return
    state.setdefault("fills", []).append(
        {
            "time": order.get("fill_time") or order.get("submitted_at"),
            "side": "BUY",
            "qty": str(order.get("qty") or ""),
            "right": order.get("right"),
            "price": f"{price:.2f}",
            "fill": price,
            "price_source": "order",
            "id": signal_id,
        }
    )


def _release(state, signal_id: str, detail: str, lines, broker=None) -> None:
    for signal in state.get("signals") or []:
        if not isinstance(signal, dict) or str(signal.get("id") or "") != signal_id:
            continue
        if signal.get("status") == "closed":
            continue
        signal["status"] = "skip"
        signal["skip"] = UNFILLED
        signal["reason"] = UNFILLED
        signal["detail"] = detail
    state["positions"] = [
        row
        for row in (state.get("positions") or [])
        if not (isinstance(row, dict) and str(row.get("id") or "") == signal_id)
    ]
    state["fills"] = [
        row
        for row in (state.get("fills") or [])
        if not (
            isinstance(row, dict)
            and str(row.get("id") or "") == signal_id
            and str(row.get("side") or "") == "BUY"
            and _price(row.get("fill")) is None
        )
    ]
    for order in state.get("orders") or []:
        if not isinstance(order, dict):
            continue
        if _signal_id(str(order.get("key") or "")) != signal_id:
            continue
        if str(order.get("kind") or "") != "exit":
            continue
        if _price(order.get("fill")) is not None:
            continue
        status = str(order.get("status") or "")
        broker_status = str(order.get("broker_status") or "")
        if (
            broker is not None
            and status in {"submitted", "intent", "partial"}
            and broker_status not in {"rejected", "cancelled", "canceled", "expired"}
        ):
            _cancel(broker, order, lines)
        order["status"] = "rejected"
        order["broker_status"] = "rejected"
        order["error"] = "no entry fill"
    lines.append(f"Entry skipped, unfilled: {detail}")


def _drop_rejected_exits(state, lines) -> None:
    """A sell that was rejected with no entry fill is not sent again."""
    for order in state.get("orders") or []:
        if not isinstance(order, dict) or str(order.get("kind") or "") != "exit":
            continue
        if _price(order.get("fill")) is not None:
            continue
        signal_id = _signal_id(str(order.get("key") or ""))
        if _signal_filled(state, signal_id):
            continue
        if order.get("error") == "no entry fill":
            continue
        status = str(order.get("broker_status") or order.get("status") or "")
        if status not in {"rejected", "cancelled", "canceled", "expired"}:
            continue
        order["status"] = "rejected"
        order["broker_status"] = "rejected"
        order["error"] = "no entry fill"
        lines.append(
            f"Exit {order.get('right')} stays rejected. The entry never filled, so no new sell was sent."
        )


def _cancel_reason(state, order, signal_id, now, spot) -> Optional[str]:
    position = _position(state, signal_id)
    signal = _signal(state, signal_id)
    source = position or signal or {}
    if _rejected_exit(state, signal_id):
        return "a sell was rejected because the entry never filled"
    if _past_window(order, source, now):
        return "the entry was still unfilled when the fill window ended"
    if spot is not None and _outside(source, spot):
        return "the price left the stop and the 1R target before the entry filled"
    return None


def _past_window(order, source, now) -> bool:
    stamp = order.get("submitted_at") or source.get("submitted_at") or source.get("entry_time")
    if not stamp:
        return False
    try:
        sent = to_ny(datetime.fromisoformat(str(stamp)))
    except ValueError:
        return False
    age = (to_ny(now) - sent).total_seconds()
    return age + 1e-9 >= max_entry_delay_minutes() * 60.0


def _outside(source, spot) -> bool:
    try:
        price = float(spot)
        stop = float(source.get("stop"))
        target = float(source.get("target"))
    except (TypeError, ValueError):
        return False
    direction = str(source.get("direction") or "")
    if direction not in {"long", "short"}:
        return False
    return not _inside(direction, price, stop, target)


def _rejected_exit(state, signal_id: str) -> bool:
    for order in state.get("orders") or []:
        if not isinstance(order, dict) or str(order.get("kind") or "") != "exit":
            continue
        if _signal_id(str(order.get("key") or "")) != signal_id:
            continue
        status = str(order.get("broker_status") or order.get("status") or "")
        if status in {"rejected", "cancelled", "canceled", "expired"}:
            return True
    return False


def _signal_filled(state, signal_id: str) -> bool:
    """A missing entry order is an older ticket. A working buy is not a fill."""
    order = entry_order(state, signal_id)
    if order is None:
        return True
    if _price(order.get("fill")) is not None or str(order.get("broker_status") or "") in {"filled", "partial"}:
        return True
    position = _position(state, signal_id)
    if position is not None and position.get("entry_filled") is True:
        return True
    return False


def adopt_held_entries(state, broker, now, lines) -> bool:
    """Re-open a skipped buy when the account still holds that contract.

    Runs on startup and on each later exit check. The book's stop, target,
    and flatten stay on the signal. The missed-fill shadow for that signal
    is removed. No new buy is sent.
    """
    from webull_bot.execution.forward_reconcile import account_view, match_holding

    if broker is None or not isinstance(state, dict):
        return False
    view = account_view(broker)
    if not view.get("holdings_ok"):
        _log_unread(state.get("book"), lines, now)
        return False
    holdings = list(view.get("holdings") or [])
    _log_positions(state.get("book"), holdings, lines, now)
    changed = False
    for signal in list(state.get("signals") or []):
        if not isinstance(signal, dict) or not _was_unfilled(signal):
            continue
        signal_id = str(signal.get("id") or "")
        order = entry_order(state, signal_id)
        if order is None:
            continue
        if _price(order.get("fill")) is not None and _position(state, signal_id) is not None:
            continue
        held = match_holding(state, order, holdings)
        if held is None:
            continue
        _reopen_from_holding(state, signal, order, held, lines)
        changed = True
    return changed


def _was_unfilled(signal: dict) -> bool:
    if str(signal.get("status") or "") == "closed":
        return False
    return str(signal.get("skip") or "") == UNFILLED or str(signal.get("reason") or "") == UNFILLED


def _log_unread(book, lines, now) -> None:
    """A missed position read is not an empty account."""
    stamp = to_ny(now).strftime("%Y%m%d%H%M") if now is not None else ""
    key = str(book or "") + "|unread"
    if stamp and _HOLDING_LOG.get(key) == stamp:
        return
    if stamp:
        _HOLDING_LOG[key] = stamp
    lines.append("Sandbox position list was not read. It was not treated as empty.")


def _log_positions(book, holdings, lines, now) -> None:
    from webull_bot.execution.forward_reconcile import _describe_holding

    stamp = to_ny(now).strftime("%Y%m%d%H%M") if now is not None else ""
    key = str(book or "")
    if stamp and _HOLDING_LOG.get(key) == stamp:
        return
    if stamp:
        _HOLDING_LOG[key] = stamp
    if not holdings:
        lines.append("Sandbox position list is empty.")
        return
    for row in holdings:
        lines.append("Sandbox position " + _describe_holding(row))


def _keep_because_held(state, order, broker, lines) -> bool:
    """True when a holding matches, so this buy is not marked unfilled."""
    from webull_bot.execution.forward_reconcile import (
        _describe_holding,
        account_view,
        apply_holding_contract,
        match_holding,
    )

    if broker is None:
        return False
    view = account_view(broker)
    if not view.get("holdings_ok"):
        return False
    held = match_holding(state, order, view.get("holdings") or [])
    if held is None:
        return False
    apply_holding_contract(state, order, held)
    order["broker_status"] = "filled"
    order["status"] = "filled"
    order["fill_source"] = "position"
    price = _price(held.get("avg"))
    if price is not None:
        order["fill"] = price
    _promote(state, order, lines)
    lines.append("Entry stays open. " + _describe_holding(held))
    return True


def _reopen_from_holding(state, signal, order, holding, lines) -> None:
    from webull_bot.execution.forward_reconcile import _describe_holding, apply_holding_contract

    signal_id = str(signal.get("id") or "")
    journal_strike = signal.get("order_strike") or signal.get("strike") or order.get("strike")
    apply_holding_contract(state, order, holding)
    avg = _price(holding.get("avg"))
    order["broker_status"] = "filled"
    order["status"] = "filled"
    order["fill_source"] = "position"
    if avg is not None:
        order["fill"] = avg
    signal["status"] = "open"
    signal["skip"] = ""
    signal["reason"] = ""
    signal["detail"] = "adopted from the sandbox holding"
    position = _position(state, signal_id)
    if position is None:
        position = _position_from_signal(signal, order)
        state.setdefault("positions", []).append(position)
    position["entry_filled"] = True
    if order.get("strike") not in (None, ""):
        position["strike"] = order.get("strike")
    if order.get("option_symbol"):
        position["option_symbol"] = order.get("option_symbol")
    if order.get("expiry"):
        position["expiry"] = order.get("expiry")
    if avg is not None:
        position["fill"] = avg
    _remember_confirmed_fill(state, order, signal_id)
    state["missed_fills"] = [
        row
        for row in (state.get("missed_fills") or [])
        if not (isinstance(row, dict) and str(row.get("id") or "") == signal_id)
    ]
    state["orders"] = [
        row
        for row in (state.get("orders") or [])
        if not (
            isinstance(row, dict)
            and str(row.get("kind") or "") == "exit"
            and _signal_id(str(row.get("key") or "")) == signal_id
            and row.get("error") == "no entry fill"
            and _price(row.get("fill")) is None
        )
    ]
    strike_note = ""
    row_strike = holding.get("strike")
    if row_strike in (None, ""):
        strike_note = f" Position row has no strike. Journal strike {journal_strike} stays."
    else:
        try:
            changed_strike = journal_strike not in (None, "") and abs(float(row_strike) - float(journal_strike)) > 0.001
        except (TypeError, ValueError):
            changed_strike = False
        if changed_strike:
            strike_note = f" Position strike {row_strike} replaces journal strike {journal_strike}."
    lines.append(
        "Adopted "
        + _describe_holding(holding).lstrip("- ").strip()
        + f" for {signal_id}. Stop {signal.get('stop')} target {signal.get('target')} are back on. "
        + "Missed-fill shadow removed. No new buy."
        + strike_note
    )


def _position_from_signal(signal: dict, order: dict) -> dict:
    raw_qty = signal.get("qty") or order.get("qty") or 1
    try:
        qty = int(float(raw_qty))
    except (TypeError, ValueError):
        qty = 1
    option_type = signal.get("option_type") or signal.get("right") or order.get("option_type") or order.get("right")
    return {
        "id": signal.get("id"),
        "direction": signal.get("direction"),
        "right": signal.get("right") or option_type,
        "option_type": option_type,
        "qty": qty,
        "strike": order.get("strike") or signal.get("order_strike") or signal.get("strike"),
        "model_strike": signal.get("model_strike") or signal.get("strike"),
        "expiry": order.get("expiry") or signal.get("expiry"),
        "option_symbol": order.get("option_symbol") or signal.get("order_symbol") or signal.get("option_symbol") or "",
        "stop": signal.get("stop"),
        "target": signal.get("target"),
        "entry": signal.get("entry"),
        "entry_time": signal.get("entry_time") or order.get("submitted_at"),
        "fill_time": signal.get("fill_time") or signal.get("entry_time"),
        "signal_time": signal.get("signal_time"),
        "modeled_entry": signal.get("modeled_entry"),
        "iv": signal.get("iv"),
        "model_debit": signal.get("model_debit"),
        "model_ask": signal.get("model_ask"),
        "entry_filled": True,
    }


def _confirm_from_account(state, order, broker) -> bool:
    """A held contract or a filled order-list row confirms the buy. The limit is not the fill."""
    from webull_bot.execution.forward_reconcile import account_view, match_holding

    if broker is None:
        return False
    view = account_view(broker)
    client_id = str(order.get("id") or "")
    if view.get("orders_ok"):
        for row in view.get("orders") or []:
            if str(row.get("id") or "") != client_id:
                continue
            if str(row.get("kind") or "") not in {"filled", "partial"}:
                continue
            price = _price(row.get("price"))
            if price is None and str(row.get("kind")) != "filled":
                continue
            order["broker_status"] = "filled" if str(row.get("kind")) == "filled" else "partial"
            if price is not None:
                order["fill"] = price
                order["fill_source"] = "order_list"
            return True
    if not view.get("holdings_ok"):
        return False
    held = match_holding(state, order, view.get("holdings") or [])
    if held is None:
        return False
    from webull_bot.execution.forward_reconcile import apply_holding_contract

    apply_holding_contract(state, order, held)
    order["broker_status"] = "filled"
    price = _price(held.get("avg"))
    if price is not None:
        order["fill"] = price
        order["fill_source"] = "position"
    return True


def _read(broker, order_id: str) -> dict:
    """Order detail, including through the exit view that hides its trade client.

    The watch spaces these reads. A missing client is ``unknown`` and does not cancel.
    """
    if broker is None:
        return {"kind": "unknown"}
    custom = getattr(broker, "order_detail", None)
    if callable(custom):
        try:
            detail = custom(order_id)
        except Exception:
            return {"kind": "error"}
        return detail if isinstance(detail, dict) else {"kind": "unknown"}
    from webull_bot.execution.forward_reconcile import read_order_detail

    return read_order_detail(broker, order_id)


def _account_presence(state, order, broker) -> tuple:
    """``(held, listing)``. None means that account list was not read.

    ``held`` is True or False when positions were read. ``listing`` is
    ``working``, ``filled``, or ``absent`` when open orders were read.
    """
    from webull_bot.execution.forward_reconcile import account_view, match_holding

    if broker is None:
        return None, None
    view = account_view(broker)
    held = None
    if view.get("holdings_ok"):
        held = match_holding(state, order, view.get("holdings") or []) is not None
    listing = None
    if view.get("orders_ok"):
        listing = "absent"
        client_id = str(order.get("id") or "")
        for row in view.get("orders") or []:
            if str(row.get("id") or "") != client_id:
                continue
            kind = str(row.get("kind") or "")
            if kind in {"filled", "partial"}:
                listing = "filled"
            elif kind in {"cancelled", "canceled", "expired", "rejected"}:
                listing = "absent"
            else:
                listing = "working"
            break
    return held, listing


def _cancel(broker, order, lines) -> bool:
    """Cancel one working buy. A broker with no cancel path is not a success."""
    from webull_bot.execution.forward_reconcile import _rejection_body

    cancel = getattr(broker, "cancel_order", None)
    if not callable(cancel):
        inner = getattr(broker, "_inner", None)
        cancel = getattr(inner, "cancel_order", None) if inner is not None else None
    if not callable(cancel):
        lines.append("Entry cancel was not sent. The broker has no cancel path.")
        return False
    try:
        cancel(str(order.get("id") or ""))
    except Exception as exc:
        body = _rejection_body(exc)
        order["cancel_error"] = body
        lines.append(f"Entry cancel was rejected. {body} No exit was sent.")
        return False
    lines.append(
        f"Cancelled {order.get('side') or 'BUY'} {order.get('qty')} {order.get('right')}. "
        f"Limit {order.get('limit')} was not a fill."
    )
    return True


def _detail_confirms_fill(kind: str, detail: dict) -> bool:
    if kind == "filled" or kind == "filled_no_price":
        return True
    return kind == "partial" and _price(detail.get("price")) is not None


def _promote_if_detail_filled(state, order, broker, lines) -> bool:
    """A cancel that the broker refused may already be a fill. Do not skip it."""
    from webull_bot.execution.forward_reconcile import read_order_detail

    detail = read_order_detail(broker, str(order.get("id") or ""), force=True)
    kind = str(detail.get("kind") or "unknown")
    if not _detail_confirms_fill(kind, detail):
        return False
    _store_fill(order, detail)
    if _price(order.get("fill")) is None:
        _confirm_from_account(state, order, broker)
    _promote(state, order, lines)
    lines.append("Entry filled. The cancel was not applied. It was not marked unfilled.")
    return True


def restore_from_order_detail(state, broker, lines) -> bool:
    """Re-open a skipped buy when its own order detail says it filled.

    Two books can share a premium, so the position list is not the tie-break.
    The client order id is. No new buy is sent. A fill the account no longer
    holds is recorded and is not sold again.
    """
    from webull_bot.execution.forward_reconcile import account_view, match_holding, read_order_detail

    if broker is None or not isinstance(state, dict):
        return False
    changed = False
    view = account_view(broker)
    holdings_ok = bool(view.get("holdings_ok"))
    holdings = list(view.get("holdings") or [])
    for signal in list(state.get("signals") or []):
        if not isinstance(signal, dict) or not _was_unfilled(signal):
            continue
        signal_id = str(signal.get("id") or "")
        order = entry_order(state, signal_id)
        if order is None:
            continue
        detail = read_order_detail(broker, str(order.get("id") or ""))
        kind = str(detail.get("kind") or "unknown")
        if not _detail_confirms_fill(kind, detail):
            continue
        _store_fill(order, detail)
        held = match_holding(state, order, holdings) if holdings_ok else None
        if held is not None and _price(order.get("fill")) is None:
            price = _price(held.get("avg"))
            if price is not None:
                order["fill"] = price
                order["fill_source"] = "position"
        if not holdings_ok:
            lines.append(
                f"Order detail says {signal_id} filled"
                + (f" at {order.get('fill')}" if order.get("fill") else "")
                + ". Positions were not read. The buy was not marked unfilled."
            )
            continue
        if held is None:
            signal["status"] = "open"
            signal["skip"] = ""
            signal["reason"] = ""
            signal["detail"] = "order detail filled; the account does not hold it"
            _clear_unfilled_shadow(state, signal_id)
            lines.append(
                f"Restored {signal_id} from order detail fill {order.get('fill') or 'unknown'}. "
                "The sandbox account does not hold it. Missed-fill shadow removed. No new buy. No sell."
            )
            changed = True
            continue
        _reopen_from_holding(state, signal, order, held, lines)
        price = order.get("fill")
        lines.append(
            f"Restored {signal_id} from order detail fill {price}. Missed-fill shadow removed. No new buy."
        )
        changed = True
    return changed


def _clear_unfilled_shadow(state, signal_id: str) -> None:
    state["missed_fills"] = [
        row
        for row in (state.get("missed_fills") or [])
        if not (isinstance(row, dict) and str(row.get("id") or "") == signal_id)
    ]
    state["orders"] = [
        row
        for row in (state.get("orders") or [])
        if not (
            isinstance(row, dict)
            and str(row.get("kind") or "") == "exit"
            and _signal_id(str(row.get("key") or "")) == signal_id
            and row.get("error") == "no entry fill"
            and _price(row.get("fill")) is None
        )
    ]


def carried_overnight(position, now) -> bool:
    """A filled contract from an earlier session that has not expired yet."""
    from datetime import time as clock

    if not isinstance(position, dict) or now is None:
        return False
    local = to_ny(now)
    if local.time() < clock(9, 30):
        return False
    raw = position.get("entry_time") or position.get("submitted_at")
    if not raw:
        return False
    try:
        opened = to_ny(datetime.fromisoformat(str(raw)))
    except ValueError:
        return False
    if opened.date() >= local.date():
        return False
    expiry_raw = position.get("expiry")
    if expiry_raw not in (None, ""):
        try:
            expiry = datetime.fromisoformat(str(expiry_raw)[:10]).date()
        except ValueError:
            expiry = None
        if expiry is not None and expiry < local.date():
            return False
    return True


def account_blocks_sell(state, position, broker, lines) -> bool:
    """True when the account was read and this contract is not in it.

    An unread list is not an empty account, so the sell is left to the caller.
    """
    from webull_bot.execution.forward_reconcile import account_view, match_holding

    if broker is None or not isinstance(position, dict):
        return False
    view = account_view(broker)
    if not view.get("holdings_ok"):
        return False
    probe = {
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
    if match_holding(state, probe, view.get("holdings") or []) is not None:
        return False
    if not position.get("absent_noted"):
        name = position.get("option_symbol") or position.get("right") or position.get("id")
        lines.append(
            f"No sell. The sandbox account does not hold {name}. "
            "The journal position was left in place. No order."
        )
        position["absent_noted"] = True
    return True


def close_preface(state, position, broker, lines, existing) -> str:
    """``send`` places the sell. ``stop`` does not. ``done`` the close is finished."""
    if account_blocks_sell(state, position, broker, lines):
        return "stop"
    if not isinstance(existing, dict):
        return "send"
    if _price(existing.get("fill")) is not None:
        return "done"
    status = str(existing.get("status") or "")
    broker_status = str(existing.get("broker_status") or "")
    if status not in {"rejected", "cancelled", "canceled", "expired"} and broker_status not in {
        "rejected",
        "cancelled",
        "canceled",
        "expired",
    }:
        return "send"
    from webull_bot.execution.forward_reconcile import exit_retry_decision

    decision = exit_retry_decision(existing, broker, lines)
    if decision == "filled":
        return "done"
    if decision != "send":
        if str(existing.get("status") or "") == "submitted":
            return "done"
        return "stop"
    return "send"


def _store_fill(order, detail) -> None:
    kind = str(detail.get("kind"))
    order["broker_status"] = "filled" if kind in {"filled", "filled_no_price"} else "partial"
    price = _price(detail.get("price"))
    if price is not None:
        order["fill"] = price
    if detail.get("time"):
        order["fill_time"] = detail.get("time")


def _position(state, signal_id: str):
    for row in state.get("positions") or []:
        if isinstance(row, dict) and str(row.get("id") or "") == signal_id:
            return row
    return None


def _signal(state, signal_id: str):
    for row in state.get("signals") or []:
        if isinstance(row, dict) and str(row.get("id") or "") == signal_id:
            return row
    return None


def _signal_id(key: str) -> str:
    if key.endswith("|entry"):
        return key[: -len("|entry")]
    if key.endswith("|exit"):
        return key[: -len("|exit")]
    return ""


def _price(value) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number <= 0:
        return None
    return number


def _limit_text(order) -> str:
    return f"Limit {order.get('limit')}, not a fill. Fill pending."
