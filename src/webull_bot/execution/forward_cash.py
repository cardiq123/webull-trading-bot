"""Cash mirror from the sandbox fill, with the model P&L kept beside it.

A live cycle reads the average fill from order detail and stores it on the
order. The next load, and a report that only has the journal, use that
journaled fill. Until a fill is known the mirror keeps the model debit and
credit for that leg. Sale proceeds still settle the next session.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from webull_bot.calendar import next_trading_day
from webull_bot.options.fees import CONTRACT_MULTIPLIER, option_leg_fees


def option_cash(price: float, qty: int, *, sell: bool) -> float:
    """Premium cash for one ticket, including the research option fees."""
    contracts = int(qty)
    premium = float(price)
    if contracts <= 0 or premium <= 0:
        return 0.0
    notional = premium * CONTRACT_MULTIPLIER * contracts
    if sell:
        return notional - option_leg_fees(contracts, premium, sell=True)
    return notional + option_leg_fees(contracts, premium, sell=False)


def prepare_cash(state: dict, broker, stake: float, session: date) -> bool:
    """Refresh missing fills, rebuild the mirror, and settle through ``session``.

    Returns whether the journaled cash or the stored fill changed. A book
    with no opened trade keeps the settled cash it already has, then still
    settles credits that are due.
    """
    if not isinstance(state, dict):
        return False
    before = _fingerprint(state)
    refresh_missing_fills(state, broker, session)
    if _has_cash_basis(state):
        rebuild_fill_mirror(state, float(state.get("stake") or stake))
    settle_cash(state, session)
    state["cash_session"] = session.isoformat()
    return _fingerprint(state) != before


def refresh_missing_fills(state: dict, broker, session: date) -> None:
    """Read order detail again until the order is filled or terminal.

    A working order is not skipped for the rest of the session. The limit
    on the order is never written down as the fill.
    """
    from webull_bot.execution.forward_reconcile import apply_order_detail, order_needs_detail, read_order_detail

    mark = session.isoformat()
    for order in state.get("orders") or []:
        if not isinstance(order, dict):
            continue
        if not order_needs_detail(order):
            if _known_fill(order.get("fill")) is not None:
                _stamp_fill_row(state, order)
            continue
        order["fill_session"] = mark
        detail = read_order_detail(broker, str(order.get("id") or ""))
        apply_order_detail(order, detail)
        _stamp_fill_row(state, order)


def rebuild_fill_mirror(state: dict, stake: float) -> None:
    """Replace settled cash and unsettled credits from each opened trade.

    The entry debit and the exit credit use the order-detail fill when the
    order has one, otherwise the fill stored on the journal row. A leg that
    has neither keeps its model debit or credit. ``pnl`` on the signal stays
    the model figure. ``fill_pnl`` is set only when both legs have a sandbox
    fill.
    """
    settled = float(stake)
    unsettled: list[dict[str, Any]] = []
    signals = [row for row in (state.get("signals") or []) if isinstance(row, dict)]
    exits = [row for row in (state.get("exits") or []) if isinstance(row, dict)]
    for signal in signals:
        if signal.get("status") not in {"open", "closed"}:
            continue
        qty = _qty(state, signal)
        entry_px, entry_src = _leg_price(state, signal, "entry")
        if entry_px is None:
            debit = _number(signal.get("model_debit")) or 0.0
            signal["fill_price"] = None
            signal["fill_debit"] = None
            signal["fill_source"] = ""
        else:
            debit = option_cash(entry_px, qty, sell=False)
            signal["fill_price"] = entry_px
            signal["fill_debit"] = debit
            signal["fill_source"] = entry_src
        settled -= debit
        model_debit = _number(signal.get("model_debit"))
        model_credit = _number(signal.get("model_credit"))
        if model_debit is not None and model_credit is not None:
            signal["model_pnl"] = model_credit - model_debit
        else:
            signal["model_pnl"] = _number(signal.get("pnl"))
        if signal.get("status") != "closed":
            signal["fill_credit"] = None
            signal["fill_pnl"] = None
            continue
        exit_px, exit_src = _leg_price(state, signal, "exit")
        if exit_px is None:
            credit = model_credit or 0.0
            signal["fill_exit"] = None
            signal["fill_credit"] = None
        else:
            credit = option_cash(exit_px, qty, sell=True)
            signal["fill_exit"] = exit_px
            signal["fill_credit"] = credit
            if entry_src:
                signal["fill_source"] = entry_src if entry_src == exit_src else "order"
        due = next_trading_day(_day(signal.get("exit_time")) or session_day(state))
        unsettled.append({"date": due.isoformat(), "amount": credit, "id": signal.get("id")})
        if entry_px is not None and exit_px is not None:
            signal["fill_pnl"] = credit - debit
        else:
            signal["fill_pnl"] = None
        _stamp_exit(exits, signal)
    state["settled"] = settled
    state["unsettled"] = unsettled


def settle_cash(state: dict, day: date) -> None:
    """Move credits whose due date is on or before ``day`` into settled cash."""
    still = []
    settled = float(state.get("settled") or 0.0)
    for item in state.get("unsettled") or []:
        if not isinstance(item, dict):
            continue
        due = _day(item.get("date"))
        amount = float(item.get("amount") or 0.0)
        if due is not None and due <= day:
            settled += amount
        else:
            still.append(item)
    state["settled"] = settled
    state["unsettled"] = still
    pending = sum(float(item.get("amount") or 0.0) for item in still if isinstance(item, dict))
    if settled + pending <= 1.0:
        state["stopped"] = True


def session_day(state: dict) -> date:
    raw = str(state.get("cash_session") or state.get("last_cycle") or "")[:10]
    parsed = _day(raw)
    if parsed is not None:
        return parsed
    latest = None
    for row in list(state.get("exits") or []) + list(state.get("signals") or []):
        if not isinstance(row, dict):
            continue
        for key in ("exit_time", "entry_time", "time"):
            found = _day(row.get(key))
            if found is not None and (latest is None or found > latest):
                latest = found
    return latest or date.today()


def pnl_phrase(row: dict) -> str:
    """Fill P&L first, model P&L second."""
    model = _number(row.get("model_pnl"))
    if model is None:
        model = _number(row.get("pnl"))
    model_txt = "model P&L n/a" if model is None else f"model P&L ${model:.2f}"
    fill = _number(row.get("fill_pnl"))
    if fill is None:
        return f"fill P&L waiting on the order. The limit is not a fill. {model_txt}"
    return f"fill P&L ${fill:.2f}. {model_txt}"


def mirror_sentence(state: dict, stake: float) -> str:
    settled = float(state.get("settled") or 0.0)
    pending = 0.0
    for item in state.get("unsettled") or []:
        if isinstance(item, dict):
            pending += float(item.get("amount") or 0.0)
    equity = settled + pending
    return (
        f"Cash mirror settled ${settled:.2f} of a ${float(stake):,.0f} start. "
        f"Unsettled credits ${pending:.2f}. Fill equity ${equity:.2f}. "
        "The cash mirror uses the sandbox fill from order detail, or the journaled fill. "
        "The model P&L is the second figure."
    )


def _has_cash_basis(state: dict) -> bool:
    for signal in state.get("signals") or []:
        if not isinstance(signal, dict) or signal.get("status") not in {"open", "closed"}:
            continue
        if _number(signal.get("model_debit")) is not None or _number(signal.get("model_credit")) is not None:
            return True
        if _leg_price(state, signal, "entry")[0] is not None:
            return True
        if _leg_price(state, signal, "exit")[0] is not None:
            return True
    return False


def _leg_price(state: dict, signal: dict, kind: str) -> tuple[Optional[float], str]:
    order = _order_for(state, str(signal.get("id") or ""), kind)
    if order is not None:
        price = _known_fill(order.get("fill"))
        if price is not None:
            return price, "order"
    side = "BUY" if kind == "entry" else "SELL"
    for row in state.get("fills") or []:
        if not isinstance(row, dict):
            continue
        if row.get("id") != signal.get("id") or str(row.get("side") or "") != side:
            continue
        price = _known_fill(row.get("fill"))
        if price is not None:
            return price, "journal"
    return None, ""


def _order_for(state: dict, signal_id: str, kind: str) -> Optional[dict]:
    if not signal_id:
        return None
    suffix = f"|{kind}"
    matches = []
    for order in state.get("orders") or []:
        if not isinstance(order, dict):
            continue
        key = str(order.get("key") or "")
        if order.get("kind") not in (None, kind) and order.get("kind") != kind:
            continue
        if key.endswith(suffix) and key[: -len(suffix)] == signal_id:
            matches.append(order)
    for order in matches:
        if _known_fill(order.get("fill")) is not None:
            return order
    for order in matches:
        if order.get("status") == "submitted":
            return order
    return matches[-1] if matches else None


def _stamp_fill_row(state: dict, order: dict) -> None:
    price = _known_fill(order.get("fill"))
    if price is None:
        return
    kind = str(order.get("kind") or "")
    signal_id = _signal_id_from_key(str(order.get("key") or ""), kind)
    side = "BUY" if kind == "entry" else "SELL" if kind == "exit" else ""
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


def _stamp_exit(exits: list[dict], signal: dict) -> None:
    for row in exits:
        if row.get("id") != signal.get("id"):
            continue
        row["model_pnl"] = signal.get("model_pnl")
        row["fill_pnl"] = signal.get("fill_pnl")
        if signal.get("fill_exit") is not None:
            row["fill"] = signal.get("fill_exit")
        if signal.get("fill_price") is not None:
            row["fill_entry"] = signal.get("fill_price")


def _qty(state: dict, signal: dict) -> int:
    for source in (signal, _position(state, signal.get("id")), _order_for(state, str(signal.get("id") or ""), "entry")):
        if not isinstance(source, dict):
            continue
        try:
            qty = int(source.get("qty"))
        except (TypeError, ValueError):
            continue
        if qty > 0:
            return qty
    return 1


def _position(state: dict, signal_id) -> Optional[dict]:
    for row in state.get("positions") or []:
        if isinstance(row, dict) and row.get("id") == signal_id:
            return row
    return None


def _signal_id_from_key(key: str, kind: str) -> str:
    suffix = f"|{kind}"
    if kind and key.endswith(suffix):
        return key[: -len(suffix)]
    return ""


def _known_fill(value) -> Optional[float]:
    number = _number(value)
    if number is None or number <= 0:
        return None
    return number


def _number(value) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:
        return None
    return number


def _day(value) -> Optional[date]:
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


def _fingerprint(state: dict) -> tuple:
    unsettled = []
    for item in state.get("unsettled") or []:
        if not isinstance(item, dict):
            continue
        unsettled.append((str(item.get("date")), round(float(item.get("amount") or 0.0), 6), item.get("id")))
    fills = []
    for order in state.get("orders") or []:
        if isinstance(order, dict):
            fills.append(
                (
                    order.get("id"),
                    order.get("fill"),
                    order.get("fill_session"),
                    order.get("broker_status"),
                    order.get("status"),
                )
            )
    return (
        round(float(state.get("settled") or 0.0), 6),
        tuple(unsettled),
        tuple(fills),
        state.get("cash_session"),
    )
