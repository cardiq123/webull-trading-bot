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
    changed = False
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
        if kind == "filled" or (kind == "partial" and _price(detail.get("price")) is not None):
            _store_fill(order, detail)
            _promote(state, order, lines)
            changed = True
            continue
        if kind in {"cancelled", "expired", "rejected"}:
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
        if kind == "working" and _cancel(broker, order, lines):
            order["broker_status"] = "cancelled"
            order["status"] = "cancelled"
            _release(state, signal_id, reason, lines, broker)
            changed = True
        elif kind == "working":
            lines.append("Entry is still working. The cancel was not accepted. No exit was sent.")
        else:
            lines.append(
                "Entry status was not confirmed. No exit was sent and the buy was not cancelled."
            )
    _drop_rejected_exits(state, lines)
    return changed


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


def _read(broker, order_id: str) -> dict:
    if not broker_reports_detail(broker):
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


def _cancel(broker, order, lines) -> bool:
    """Cancel one working buy. A broker with no cancel path is not a success."""
    if not broker_reports_detail(broker):
        return False
    cancel = getattr(broker, "cancel_order", None)
    if not callable(cancel):
        lines.append("Entry cancel was not sent. The broker has no cancel path.")
        return False
    try:
        cancel(str(order.get("id") or ""))
    except Exception:
        lines.append("Entry cancel was rejected. The reason was not printed. No exit was sent.")
        return False
    lines.append(
        f"Cancelled {order.get('side') or 'BUY'} {order.get('qty')} {order.get('right')}. "
        f"Limit {order.get('limit')} was not a fill."
    )
    return True


def _store_fill(order, detail) -> None:
    order["broker_status"] = "filled" if str(detail.get("kind")) == "filled" else "partial"
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
