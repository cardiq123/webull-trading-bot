"""Shadow P&L for an option entry that never filled.

The cash mirror and ``fill_pnl`` stay on the sandbox fill. This record
assumes the buy filled at the live ask when the order was sent, then
walks the book's stop, target, and 15:45 flatten on the underlying in
the tick log. The exit credit is the live bid on that tick. The result
is journaled under ``missed_fills`` and printed as missed-fill P&L.
Nothing here places an order.
"""

from __future__ import annotations

import csv
from datetime import date, datetime, time
from pathlib import Path
from typing import Optional

from webull_bot.calendar import to_ny
from webull_bot.execution.forward_cash import option_cash
from webull_bot.execution.forward_quotes import quote_dir

FLAT = time(15, 45)
_TERMINAL = {"cancelled", "canceled", "expired", "rejected", "unfilled"}
_SKIPPED = {"unfilled", "expired"}


def apply_missed_fills(state: dict, book: str, folder: Optional[Path] = None) -> bool:
    """Fill in shadow rows for entries that never filled. Returns whether the journal changed."""
    if not isinstance(state, dict):
        return False
    before = _fingerprint(state.get("missed_fills"))
    rows = list(state.get("missed_fills") or [])
    by_id = {str(row.get("id")): row for row in rows if isinstance(row, dict) and row.get("id")}
    root = Path(folder) if folder is not None else quote_dir()
    for signal, order in _candidates(state):
        signal_id = str(signal.get("id") or "")
        current = by_id.get(signal_id)
        if isinstance(current, dict) and current.get("missed_pnl") is not None:
            continue
        built = _shadow(signal, order, book, root)
        if current is None:
            rows.append(built)
            by_id[signal_id] = built
        else:
            current.clear()
            current.update(built)
    if rows:
        state["missed_fills"] = rows
    return _fingerprint(state.get("missed_fills")) != before


def append_report(lines: list[str], state: dict, journal, book: str, folder: Optional[Path] = None) -> None:
    """Update the shadow from the quote log and print it. Does not change fill P&L."""
    if apply_missed_fills(state, book, folder):
        journal.forward_save(book, state)
    lines.extend(report_lines(state))


def report_lines(state: dict) -> list[str]:
    """Forward-report section. Separate from realized fill P&L."""
    rows = [row for row in (state.get("missed_fills") or []) if isinstance(row, dict)]
    lines = ["Missed fills"]
    if not rows:
        lines.append("(none)")
    for row in rows:
        lines.append("- " + _row_sentence(row))
    lines.append(daily_summary_line(state))
    lines.append("Missed-fill P&L assumes the ask at order time and the bid at the shadow exit. It is not fill P&L.")
    return lines


def daily_summary_line(state: dict) -> str:
    """One line for the daily summary."""
    rows = [row for row in (state.get("missed_fills") or []) if isinstance(row, dict)]
    booked = [row for row in rows if _pnl(row.get("missed_pnl")) is not None]
    waiting = [row for row in rows if _pnl(row.get("missed_pnl")) is None]
    if not rows:
        return "Daily summary: missed-fill P&L $0.00."
    if not booked:
        return "Daily summary: missed-fill P&L waiting on the quote log."
    total = sum(float(row["missed_pnl"]) for row in booked)
    extra = f" {len(waiting)} still waiting on a bid." if waiting else ""
    return f"Daily summary: missed-fill P&L ${total:.2f}.{extra}"


def open_missed(state: dict) -> list[dict]:
    """Shadows that still need a bid. The watch keeps a tick for these."""
    found = []
    for row in state.get("missed_fills") or []:
        if isinstance(row, dict) and row.get("status") == "open" and row.get("option_symbol"):
            found.append(row)
    return found


def _candidates(state: dict) -> list[tuple[dict, Optional[dict]]]:
    orders = {}
    for order in state.get("orders") or []:
        if not isinstance(order, dict) or str(order.get("kind") or "") not in {"", "entry"}:
            continue
        key = str(order.get("key") or "")
        if key.endswith("|exit"):
            continue
        signal_id = key[: -len("|entry")] if key.endswith("|entry") else str(order.get("signal_id") or "")
        if signal_id:
            orders.setdefault(signal_id, order)
    found = []
    for signal in state.get("signals") or []:
        if not isinstance(signal, dict):
            continue
        signal_id = str(signal.get("id") or "")
        order = orders.get(signal_id)
        if _has_fill(order):
            continue
        if not _never_filled(signal, order):
            continue
        found.append((signal, order))
    return found


def _never_filled(signal: dict, order: Optional[dict]) -> bool:
    skip = str(signal.get("skip") or "")
    reason = str(signal.get("reason") or "")
    if skip in _SKIPPED or reason in {"unfilled", "expired", "expired, late"}:
        return True
    if order is None:
        return False
    status = str(order.get("broker_status") or order.get("status") or "").lower()
    return status in _TERMINAL


def _has_fill(order: Optional[dict]) -> bool:
    if not isinstance(order, dict):
        return False
    price = _number(order.get("fill"))
    if price is not None and price > 0:
        return True
    return str(order.get("broker_status") or "") in {"filled", "partial"}


def _shadow(signal: dict, order: Optional[dict], book: str, folder: Path) -> dict:
    signal_id = str(signal.get("id") or "")
    order = order or {}
    when = _clock(order.get("submitted_at") or signal.get("entry_time") or signal.get("seen_at") or signal.get("signal_time"))
    day = when.date() if when is not None else _day(signal.get("signal_time"))
    contract = str(order.get("option_symbol") or signal.get("option_symbol") or "")
    marks = _marks(folder, book, day, signal_id, contract) if day is not None else []
    ask, ask_source = _entry_ask(order, marks, when)
    direction = str(signal.get("direction") or _direction(signal, order))
    stop = _number(signal.get("stop"))
    target = _number(signal.get("target"))
    qty = _qty(order, signal)
    row = {
        "id": signal_id,
        "book": book,
        "right": signal.get("right") or order.get("right"),
        "direction": direction,
        "qty": qty,
        "ask": None if ask is None else round(ask, 4),
        "ask_source": ask_source,
        "option_symbol": contract or _contract_from(marks),
        "order_time": None if when is None else when.isoformat(),
        "status": "no_quote",
        "reason": "",
        "bid": None,
        "exit_time": "",
        "underlying": None,
        "missed_pnl": None,
    }
    if ask is None or when is None:
        row["detail"] = "no live ask at order time"
        return row
    exit_mark = _exit_mark(marks, when, direction, stop, target)
    if exit_mark is None:
        row["status"] = "open"
        row["detail"] = "the stop, target, and 15:45 flatten are not in the quote log yet"
        return row
    bid = _number(exit_mark.get("bid"))
    if bid is None:
        bid = _prior_bid(marks, exit_mark)
    if bid is None:
        bid = _next_bid(marks, exit_mark)
    if bid is None:
        row["status"] = "open"
        row["detail"] = "the exit tick has no bid"
        row["reason"] = str(exit_mark.get("_reason") or "")
        row["exit_time"] = str(exit_mark.get("_stamp") or "")
        return row
    debit = option_cash(ask, qty, sell=False)
    credit = option_cash(bid, qty, sell=True) if bid > 0 else 0.0
    row.update(
        {
            "status": "closed",
            "reason": str(exit_mark.get("_reason") or ""),
            "bid": round(bid, 4),
            "exit_time": str(exit_mark.get("_stamp") or ""),
            "underlying": _number(exit_mark.get("underlying")),
            "missed_pnl": round(credit - debit, 4),
            "detail": "shadow fill at the ask, shadow exit at the bid",
        }
    )
    return row


def _entry_ask(order: dict, marks: list[dict], when: Optional[datetime]) -> tuple[Optional[float], str]:
    if str(order.get("price_source") or "") != "model":
        ask = _number(order.get("quote_px"))
        if ask is None or ask <= 0:
            ask = _number(order.get("sandbox_price"))
        if ask is not None and ask > 0:
            return ask, "order"
    if when is None:
        return None, ""
    best = None
    best_gap = None
    for mark in marks:
        ask = _number(mark.get("ask"))
        stamp = mark.get("_stamp")
        if ask is None or ask <= 0 or not isinstance(stamp, datetime):
            continue
        gap = abs((stamp - when).total_seconds())
        if gap > 120:
            continue
        if best_gap is None or gap < best_gap:
            best = ask
            best_gap = gap
    if best is None:
        return None, ""
    return best, "quote"


def _exit_mark(marks: list[dict], start: datetime, direction: str, stop: Optional[float], target: Optional[float]) -> Optional[dict]:
    chosen = None
    for mark in marks:
        stamp = mark.get("_stamp")
        if not isinstance(stamp, datetime) or stamp < start:
            continue
        underlying = _number(mark.get("underlying"))
        reason = _reason(stamp, underlying, direction, stop, target)
        if reason is None:
            continue
        chosen = dict(mark)
        chosen["_reason"] = reason
        break
    return chosen


def _reason(stamp: datetime, underlying: Optional[float], direction: str, stop: Optional[float], target: Optional[float]) -> Optional[str]:
    if stamp.time() >= FLAT:
        return "flat"
    if underlying is None:
        return None
    if direction == "long":
        if stop is not None and underlying <= stop:
            return "stop"
        if target is not None and underlying >= target:
            return "target"
        return None
    if stop is not None and underlying >= stop:
        return "stop"
    if target is not None and underlying <= target:
        return "target"
    return None


def _next_bid(marks: list[dict], exit_mark: dict) -> Optional[float]:
    stamp = exit_mark.get("_stamp")
    for mark in marks:
        mark_stamp = mark.get("_stamp")
        if not isinstance(stamp, datetime) or not isinstance(mark_stamp, datetime) or mark_stamp < stamp:
            continue
        value = _number(mark.get("bid"))
        if value is not None:
            return value
    return None


def _prior_bid(marks: list[dict], exit_mark: dict) -> Optional[float]:
    stamp = exit_mark.get("_stamp")
    bid = None
    for mark in marks:
        mark_stamp = mark.get("_stamp")
        if not isinstance(stamp, datetime) or not isinstance(mark_stamp, datetime) or mark_stamp > stamp:
            continue
        value = _number(mark.get("bid"))
        if value is not None and value >= 0:
            bid = value
    return bid


def _marks(folder: Path, book: str, day: date, signal_id: str, contract: str) -> list[dict]:
    token = day.strftime("%Y%m%d")
    found = []
    for name in (f"ticks_{book}_{token}.csv", f"quotes_{book}_{token}.csv"):
        path = folder / name
        if not path.exists():
            continue
        try:
            with path.open(newline="") as handle:
                for raw in csv.DictReader(handle):
                    if not isinstance(raw, dict):
                        continue
                    if not _same_trade(raw, signal_id, contract):
                        continue
                    stamp = _clock(raw.get("timestamp") or raw.get("quote_time"))
                    if stamp is None:
                        continue
                    raw["_stamp"] = stamp
                    found.append(raw)
        except OSError:
            continue
    found.sort(key=lambda row: row["_stamp"])
    return found


def _same_trade(raw: dict, signal_id: str, contract: str) -> bool:
    row_signal = str(raw.get("signal_id") or "")
    row_contract = str(raw.get("option_symbol") or raw.get("contract") or "")
    if contract and row_contract:
        return row_contract == contract and (not row_signal or not signal_id or row_signal == signal_id)
    if contract and row_signal:
        return not signal_id or row_signal == signal_id
    if signal_id and row_signal:
        return row_signal == signal_id
    return False


def _contract_from(marks: list[dict]) -> str:
    for mark in marks:
        contract = str(mark.get("option_symbol") or mark.get("contract") or "")
        if contract:
            return contract
    return ""


def _direction(signal: dict, order: dict) -> str:
    right = str(signal.get("right") or signal.get("option_type") or order.get("right") or "").lower()
    if right.startswith("p"):
        return "short"
    if right.startswith("c"):
        return "long"
    return ""


def _qty(order: dict, signal: dict) -> int:
    for value in (order.get("qty"), signal.get("qty")):
        try:
            number = int(float(value))
        except (TypeError, ValueError):
            continue
        if number > 0:
            return number
    return 1


def _row_sentence(row: dict) -> str:
    pnl = _pnl(row.get("missed_pnl"))
    if pnl is None:
        return (
            f"{row.get('id')} {row.get('right')} ask {row.get('ask') or 'n/a'}. "
            f"{row.get('detail') or 'No missed-fill P&L.'}"
        )
    return (
        f"{row.get('id')} {row.get('right')} reason {row.get('reason')} "
        f"ask {row.get('ask')} bid {row.get('bid')} "
        f"missed-fill P&L ${pnl:.2f}."
    )


def _fingerprint(rows) -> str:
    parts = []
    for row in rows or []:
        if isinstance(row, dict):
            parts.append(
                "|".join(
                    str(row.get(key))
                    for key in ("id", "status", "reason", "ask", "bid", "missed_pnl", "exit_time")
                )
            )
    return "\n".join(parts)


def _clock(value) -> Optional[datetime]:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return to_ny(value)
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return to_ny(parsed)


def _day(value) -> Optional[date]:
    clock = _clock(value)
    if clock is not None:
        return clock.date()
    text = str(value or "")[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _pnl(value) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:
        return None
    return number


def _number(value) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number < 0:
        return None
    return number
