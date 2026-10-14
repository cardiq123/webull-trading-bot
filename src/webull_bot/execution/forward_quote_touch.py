"""Sandbox paper fill when the logged quote touches the limit.

The real sandbox order is still sent. When ``WEBULL_ENV`` is sandbox and the
mode is on, a buy the sandbox has not filled is journaled at our limit once
the logged ask is at or below that limit inside the entry window. A sell the
sandbox has not filled is journaled at the logged bid once the exit condition
or the sell limit is touched. The sandbox order is cancelled. A later sandbox
fill replaces that paper fill. The two are never both booked.

The mode defaults on in the sandbox. It stays off for every other
``WEBULL_ENV``, including when ``FORWARD_QUOTE_TOUCH`` is set.
"""

from __future__ import annotations

import csv
import os
from datetime import date, datetime, time, timedelta, timezone
from typing import Optional

from webull_bot.calendar import to_ny

QUOTE_TOUCH = "quote_touch"
_SANDBOX_SOURCES = {"order", "position", "order_list", "expiry", "journal"}
_FLAT = time(15, 45)


def quote_touch_enabled() -> bool:
    """On only for the sandbox. No other environment can turn it on."""
    env = os.environ.get("WEBULL_ENV", "").strip().lower()
    if env != "sandbox":
        return False
    flag = os.environ.get("FORWARD_QUOTE_TOUCH", "1").strip().lower()
    return flag not in {"0", "false", "no", "off"}


def venue_name(fill_source) -> str:
    """``quote_touch`` or ``sandbox`` when this row has a fill origin."""
    source = str(fill_source or "")
    if source == QUOTE_TOUCH:
        return QUOTE_TOUCH
    if source == "mixed":
        return "mixed"
    if source in _SANDBOX_SOURCES:
        return "sandbox"
    return ""


def venue_suffix(row: dict) -> str:
    """Report column. Empty when this row has no fill origin yet."""
    if not isinstance(row, dict):
        return ""
    name = venue_name(row.get("fill_source"))
    if not name and row.get("fill") not in (None, ""):
        name = "sandbox"
    if not name:
        return ""
    return f" venue {name}"


def is_quote_touch(row: dict) -> bool:
    return isinstance(row, dict) and str(row.get("fill_source") or "") == QUOTE_TOUCH


def position_is_quote_touch(state: dict, position: dict) -> bool:
    """A paper position is not a sandbox holding."""
    if is_quote_touch(position):
        return True
    from webull_bot.execution.forward_fills import entry_order

    order = entry_order(state, str((position or {}).get("id") or ""))
    return is_quote_touch(order)


def apply_quote_touches(state, broker, now, spot, lines) -> bool:
    """Book quote-touch fills and prefer a real sandbox fill. No new order is sent."""
    if not quote_touch_enabled() or not isinstance(state, dict) or now is None:
        return False
    changed = False
    if _prefer_real_fills(state, broker, lines):
        changed = True
    book = str(state.get("book") or "")
    for order in list(state.get("orders") or []):
        if not isinstance(order, dict) or str(order.get("kind") or "") != "entry":
            continue
        if _book_entry_touch(state, order, broker, now, book, lines):
            changed = True
    for order in list(state.get("orders") or []):
        if not isinstance(order, dict) or str(order.get("kind") or "") != "exit":
            continue
        if _book_exit_touch(state, order, broker, now, spot, book, lines):
            changed = True
    return changed


def replay_day(states: dict, ticks: list[dict], day: date) -> list[str]:
    """What quote-touch would have booked. Does not send an order or write a journal.

    ``states`` maps a book name to its journal. ``ticks`` are rows with
    ``timestamp``, ``book``, ``option_symbol``, ``bid``, ``ask``, and
    ``underlying``. One open paper position blocks the next entry in that book.
    """
    lines = [
        f"Quote-touch replay {day.isoformat()}. Read only. No order was sent. Live trading stays off.",
    ]
    if not states:
        lines.append("No journal rows for this day.")
        return lines
    for book, state in states.items():
        lines.extend(_replay_book(str(book), state, ticks, day))
    return lines


def _replay_book(book: str, state: dict, ticks: list[dict], day: date) -> list[str]:
    from webull_bot.execution.forward_cash import prepare_cash

    copy = _copy_state(state, book)
    rows = [row for row in ticks if str(row.get("book") or book) in {book, ""}]
    entries = _replay_entries(copy, day)
    open_until: Optional[datetime] = None
    for order in entries:
        sent = _sent_at(order, _signal_for(copy, order))
        if sent is None or to_ny(sent).date() != day:
            continue
        if open_until is not None and to_ny(sent) < open_until:
            lines_id = str(order.get("key") or "")
            copy.setdefault("_replay_skipped", []).append(lines_id)
            continue
        window_end = sent + timedelta(minutes=_window_minutes())
        touch = _first_ask(rows, _contract(copy, order), sent, window_end, _limit(order))
        if touch is None:
            continue
        _stamp_entry(copy, order, touch[0])
        exit_at = _replay_exit(copy, order, rows, touch[0])
        open_until = exit_at or _session_close(day)
    stake = float(copy.get("stake") or 2500.0)
    prepare_cash(copy, None, stake, day)
    total = 0.0
    booked = 0
    details = []
    for signal in copy.get("signals") or []:
        if not isinstance(signal, dict) or str(signal.get("fill_source") or "") != QUOTE_TOUCH:
            continue
        pnl = signal.get("fill_pnl")
        booked += 1
        if pnl is not None:
            total += float(pnl)
        shown = "n/a" if pnl is None else f"${float(pnl):.2f}"
        details.append(f"{signal.get('id')} {shown}")
    skipped = len(copy.get("_replay_skipped") or [])
    line = f"{book}: quote-touch fill P&L ${total:.2f} from {booked} fills."
    if skipped:
        line += f" {skipped} later entries stayed out because one position was open."
    if not booked:
        line += " No logged ask was at or below the limit inside the entry window."
    out = [line]
    out.extend(f"{book} {item}" for item in details)
    return out


def _replay_entries(state: dict, day: date) -> list[dict]:
    found = []
    for order in state.get("orders") or []:
        if not isinstance(order, dict) or str(order.get("kind") or "") != "entry":
            continue
        sent = _sent_at(order, _signal_for(state, order))
        if sent is None or to_ny(sent).date() != day:
            continue
        found.append(order)
    found.sort(key=lambda row: _sent_at(row, _signal_for(state, row)) or datetime.min)
    return found


def _replay_exit(state, order, ticks, filled_at: datetime) -> Optional[datetime]:
    signal = _signal_for(state, order)
    position = _position_for(state, _signal_id(order))
    source = position or signal or {}
    contract = _contract(state, order)
    exit_order = _exit_for(state, _signal_id(order))
    limit = _limit(exit_order) if exit_order else None
    for row in _sorted_ticks(ticks):
        stamp = _clock(row.get("timestamp"))
        if stamp is None or stamp < filled_at:
            continue
        if contract and str(row.get("option_symbol") or "") not in {"", contract}:
            continue
        bid = _num(row.get("bid"))
        underlying = _num(row.get("underlying"))
        reason = _exit_reason(source, underlying, stamp)
        touched = limit is not None and bid is not None and bid + 1e-9 >= limit
        if reason is None and not touched:
            continue
        if bid is None:
            continue
        if exit_order is None:
            exit_order = {
                "key": f"{_signal_id(order)}|exit",
                "id": f"{_signal_id(order)}-exit",
                "kind": "exit",
                "side": "SELL",
                "qty": order.get("qty"),
                "status": "filled",
                "fill": bid,
                "fill_source": QUOTE_TOUCH,
                "fill_time": stamp.isoformat(),
            }
            state.setdefault("orders", []).append(exit_order)
        else:
            exit_order["fill"] = bid
            exit_order["fill_source"] = QUOTE_TOUCH
            exit_order["fill_time"] = stamp.isoformat()
            exit_order["status"] = "filled"
        _close_signal(state, _signal_id(order), reason or "limit", underlying, stamp, bid)
        return stamp
    return None


def _book_entry_touch(state, order, broker, now, book: str, lines) -> bool:
    if _real_fill(order):
        return False
    if is_quote_touch(order) and _num(order.get("fill")) is not None:
        return False
    if str(order.get("status") or "") not in {"submitted", "intent", "partial", "working"}:
        return False
    signal = _signal_for(state, order)
    sent = _sent_at(order, signal)
    if sent is None or to_ny(now) > sent + timedelta(minutes=_window_minutes()):
        return False
    limit = _limit(order)
    if limit is None:
        return False
    touch = _first_ask(_load_ticks(book, sent, now), _contract(state, order), sent, to_ny(now), limit)
    cached = _cached_ask(_contract(state, order))
    if touch is None and cached is not None and cached <= limit + 1e-9:
        touch = (to_ny(now), cached)
    if touch is None:
        return False
    _stamp_entry(state, order, touch[0])
    order["quote_touch_ask"] = touch[1]
    _cancel_sandbox(broker, order, lines, "buy")
    lines.append(
        f"Quote-touch entry {_contract(state, order) or order.get('key')} "
        f"filled at limit {limit:.2f}. Ask {touch[1]:.2f} was at or below the limit. "
        "The sandbox order was cancelled. venue quote_touch."
    )
    return True


def _book_exit_touch(state, order, broker, now, spot, book: str, lines) -> bool:
    if _real_fill(order):
        return False
    if is_quote_touch(order) and _num(order.get("fill")) is not None:
        return False
    if str(order.get("status") or "") not in {"submitted", "intent", "partial", "working"}:
        return False
    signal_id = _signal_id(order)
    source = _position_for(state, signal_id) or _signal_for(state, order) or {}
    contract = _contract(state, order)
    bid, underlying, stamp = _latest_bid(_load_ticks(book, now, now), contract, now)
    cached_bid = _cached_bid(contract)
    if cached_bid is not None:
        bid = cached_bid
        stamp = to_ny(now)
    if bid is None:
        return False
    if underlying is None and spot is not None:
        underlying = _num(spot)
    limit = _limit(order)
    reason = _exit_reason(source, underlying, to_ny(now))
    limit_touched = limit is not None and bid + 1e-9 >= limit
    if reason is None and not limit_touched:
        return False
    order["fill"] = bid
    order["fill_time"] = (stamp or to_ny(now)).isoformat()
    order["fill_source"] = QUOTE_TOUCH
    order["status"] = "filled"
    order["broker_status"] = "filled"
    _remember_exit_fill(state, order, signal_id)
    _close_signal(state, signal_id, reason or "limit", underlying, stamp or to_ny(now), bid)
    state["positions"] = [
        row for row in (state.get("positions") or []) if not (isinstance(row, dict) and str(row.get("id") or "") == signal_id)
    ]
    _cancel_sandbox(broker, order, lines, "sell")
    lines.append(
        f"Quote-touch exit {contract or signal_id} filled at bid {bid:.2f}. "
        f"Reason {reason or 'limit'}. The sandbox sell was cancelled. venue quote_touch."
    )
    return True


def _prefer_real_fills(state, broker, lines) -> bool:
    from webull_bot.execution.forward_fills import _read
    from webull_bot.execution.forward_reconcile import account_view, match_holding

    changed = False
    view = None
    for order in state.get("orders") or []:
        if not is_quote_touch(order):
            continue
        detail = _read(broker, str(order.get("id") or ""))
        price = _num(detail.get("price")) if isinstance(detail, dict) else None
        kind = str((detail or {}).get("kind") or "")
        source = "order"
        if price is None or kind not in {"filled", "partial", "filled_no_price"}:
            price = None
            if view is None and broker is not None:
                view = account_view(broker)
            if isinstance(view, dict) and view.get("holdings_ok"):
                held = match_holding(state, order, view.get("holdings") or [])
                avg = _num(held.get("avg")) if isinstance(held, dict) else None
                if avg is not None and avg > 0:
                    price = avg
                    source = "position"
        if price is None:
            continue
        order["fill"] = price
        order["fill_source"] = source
        order["broker_status"] = "filled"
        order["status"] = "filled"
        _rewrite_fill(state, order)
        lines.append(
            f"Sandbox fill {price:.2f} replaced the quote-touch fill on {order.get('key')}. "
            "One position. venue sandbox."
        )
        changed = True
    return changed


def _stamp_entry(state, order, when: datetime) -> None:
    from webull_bot.execution.forward_fills import _promote

    limit = _limit(order)
    order["fill"] = limit
    order["fill_time"] = when.isoformat()
    order["fill_source"] = QUOTE_TOUCH
    order["status"] = "filled"
    order["broker_status"] = "filled"
    _promote(state, order, [])
    signal_id = _signal_id(order)
    position = _position_for(state, signal_id)
    if position is not None:
        position["fill_source"] = QUOTE_TOUCH
        position["fill"] = limit
    for signal in state.get("signals") or []:
        if isinstance(signal, dict) and str(signal.get("id") or "") == signal_id:
            signal["fill_source"] = QUOTE_TOUCH
    for row in state.get("fills") or []:
        if isinstance(row, dict) and str(row.get("id") or "") == signal_id and str(row.get("side") or "") == "BUY":
            row["fill_source"] = QUOTE_TOUCH


def _close_signal(state, signal_id: str, reason: str, underlying, when: datetime, bid: float) -> None:
    for signal in state.get("signals") or []:
        if not isinstance(signal, dict) or str(signal.get("id") or "") != signal_id:
            continue
        signal["status"] = "closed"
        signal["reason"] = reason or signal.get("reason") or "quote_touch"
        signal["fill_source"] = QUOTE_TOUCH
        if underlying is not None:
            signal["exit"] = underlying
        signal["exit_time"] = when.isoformat()
        if signal.get("model_pnl") is None and signal.get("pnl") is not None:
            signal["model_pnl"] = signal.get("pnl")
    found = False
    for row in state.get("exits") or []:
        if isinstance(row, dict) and str(row.get("id") or "") == signal_id:
            found = True
            row["fill_source"] = QUOTE_TOUCH
            row["fill"] = bid
            if row.get("reason") in (None, ""):
                row["reason"] = reason
    if not found:
        state.setdefault("exits", []).append(
            {
                "id": signal_id,
                "time": when.isoformat(),
                "reason": reason,
                "underlying": underlying,
                "fill": bid,
                "fill_source": QUOTE_TOUCH,
            }
        )


def _remember_exit_fill(state, order, signal_id: str) -> None:
    price = order.get("fill")
    for row in state.get("fills") or []:
        if isinstance(row, dict) and str(row.get("id") or "") == signal_id and str(row.get("side") or "") == "SELL":
            row["fill"] = price
            row["fill_source"] = QUOTE_TOUCH
            return
    state.setdefault("fills", []).append(
        {
            "id": signal_id,
            "side": "SELL",
            "fill": price,
            "time": order.get("fill_time"),
            "fill_source": QUOTE_TOUCH,
            "qty": order.get("qty"),
            "right": order.get("right"),
        }
    )


def _rewrite_fill(state, order) -> None:
    signal_id = _signal_id(order)
    side = "BUY" if str(order.get("kind") or "") == "entry" else "SELL"
    for row in state.get("fills") or []:
        if isinstance(row, dict) and str(row.get("id") or "") == signal_id and str(row.get("side") or "") == side:
            row["fill"] = order.get("fill")
            row["fill_source"] = order.get("fill_source")


def _cancel_sandbox(broker, order, lines, side: str) -> None:
    if broker is None or order.get("sandbox_cancelled"):
        return
    cancel = getattr(broker, "cancel_order", None)
    if not callable(cancel):
        inner = getattr(broker, "_inner", None)
        cancel = getattr(inner, "cancel_order", None) if inner is not None else None
    if not callable(cancel):
        lines.append(f"Quote-touch {side} was booked. The sandbox order was not cancelled.")
        return
    try:
        cancel(str(order.get("id") or ""))
    except Exception:
        lines.append(f"Quote-touch {side} was booked. The sandbox cancel was rejected.")
        return
    order["sandbox_cancelled"] = True


def _real_fill(order: dict) -> bool:
    if is_quote_touch(order):
        return False
    return _num(order.get("fill")) is not None or str(order.get("broker_status") or "") == "filled"


def _first_ask(ticks, contract: str, start: datetime, end: datetime, limit: Optional[float]):
    if limit is None:
        return None
    found = None
    for row in _sorted_ticks(ticks):
        stamp = _clock(row.get("timestamp"))
        if stamp is None or stamp < to_ny(start) or stamp > to_ny(end):
            continue
        if contract and str(row.get("option_symbol") or row.get("contract") or "") not in {"", contract}:
            continue
        ask = _num(row.get("ask"))
        if ask is None or ask > limit + 1e-9:
            continue
        if found is None or stamp < found[0]:
            found = (stamp, ask)
    return found


def _latest_bid(ticks, contract: str, now) -> tuple:
    bid = None
    underlying = None
    stamp = None
    for row in _sorted_ticks(ticks):
        mark = _clock(row.get("timestamp"))
        if mark is None or mark > to_ny(now):
            continue
        if contract and str(row.get("option_symbol") or row.get("contract") or "") not in {"", contract}:
            continue
        value = _num(row.get("bid"))
        if value is None:
            continue
        bid = value
        underlying = _num(row.get("underlying"))
        stamp = mark
    return bid, underlying, stamp


def _load_ticks(book: str, start, end) -> list[dict]:
    from webull_bot.execution.forward_quotes import quote_dir

    if not book:
        return []
    folder = quote_dir()
    days = {to_ny(start).date(), to_ny(end).date()}
    found = []
    for day in days:
        path = folder / f"ticks_{book}_{day.strftime('%Y%m%d')}.csv"
        found.extend(_read_csv(path))
    return found


def _read_csv(path) -> list[dict]:
    if not path.exists():
        return []
    try:
        with path.open(newline="") as handle:
            return [dict(row) for row in csv.DictReader(handle)]
    except OSError:
        return []


def _sorted_ticks(ticks) -> list[dict]:
    rows = [row for row in ticks or [] if isinstance(row, dict)]
    rows.sort(key=lambda row: _clock(row.get("timestamp")) or _EPOCH)
    return rows


def _session_close(day: date) -> datetime:
    from zoneinfo import ZoneInfo

    return datetime.combine(day, time(16, 0), tzinfo=ZoneInfo("America/New_York"))


_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def _cached_ask(contract: str) -> Optional[float]:
    if not contract:
        return None
    from webull_bot.execution.forward_quotes import cached_option

    return _num(cached_option(contract).get("ask"))


def _cached_bid(contract: str) -> Optional[float]:
    if not contract:
        return None
    from webull_bot.execution.forward_quotes import cached_option

    return _num(cached_option(contract).get("bid"))


def _exit_reason(source: dict, underlying, now: datetime) -> Optional[str]:
    local = to_ny(now)
    if local.time() >= _FLAT:
        return "flat"
    if underlying is None or not isinstance(source, dict):
        return None
    try:
        stop = float(source.get("stop"))
        target = float(source.get("target"))
    except (TypeError, ValueError):
        return None
    direction = str(source.get("direction") or "")
    if direction == "long":
        if underlying <= stop:
            return "stop"
        if underlying >= target:
            return "target"
        return None
    if direction == "short":
        if underlying >= stop:
            return "stop"
        if underlying <= target:
            return "target"
    return None


def _window_minutes() -> float:
    from webull_bot.execution.forward_vwap import max_entry_delay_minutes

    return float(max_entry_delay_minutes())


def _copy_state(state: dict, book: str) -> dict:
    import copy

    copied = copy.deepcopy(state if isinstance(state, dict) else {})
    copied["book"] = book
    return copied


def _signal_id(order: dict) -> str:
    key = str(order.get("key") or "")
    if "|" in key:
        return key.split("|", 1)[0]
    return ""


def _signal_for(state, order):
    sid = _signal_id(order)
    for row in state.get("signals") or []:
        if isinstance(row, dict) and str(row.get("id") or "") == sid:
            return row
    return None


def _position_for(state, signal_id: str):
    for row in state.get("positions") or []:
        if isinstance(row, dict) and str(row.get("id") or "") == signal_id:
            return row
    return None


def _exit_for(state, signal_id: str):
    for row in state.get("orders") or []:
        if isinstance(row, dict) and str(row.get("key") or "") == f"{signal_id}|exit":
            return row
    return None


def _contract(state, order) -> str:
    explicit = str(order.get("option_symbol") or "")
    if explicit:
        return explicit
    signal = _signal_for(state, order)
    if isinstance(signal, dict):
        return str(signal.get("option_symbol") or "")
    return ""


def _sent_at(order, signal):
    raw = order.get("submitted_at") or (signal or {}).get("entry_time") or (signal or {}).get("submitted_at")
    return _clock(raw)


def _limit(order) -> Optional[float]:
    if not isinstance(order, dict):
        return None
    return _num(order.get("limit"))


def _clock(value):
    if isinstance(value, datetime):
        return to_ny(value)
    if value in (None, ""):
        return None
    try:
        return to_ny(datetime.fromisoformat(str(value)))
    except ValueError:
        return None


def _num(value) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:
        return None
    return number
