"""Live option quotes for the sandbox forward books. Logging only.

Nothing in this module places an order, changes a limit, or changes a
size. A quote, a chain, or a fill lookup that fails is recorded and then
ignored. The entry and the exit have already been decided by the caller.
"""

from __future__ import annotations

import csv
import os
import threading
import time as time_mod
from contextvars import ContextVar
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from webull_bot.calendar import to_ny
from webull_bot.chart_reads.vwap_band import _option_mid
from webull_bot.options.fees import option_leg_fees
from webull_bot.options.pricing import listed_strike

NY_FLAT = time(15, 45)
CALL_TIMEOUT_S = 1.5
CYCLE_BUDGET_S = 6.0
_BUDGET: ContextVar[float | None] = ContextVar("forward_quote_budget", default=None)
CSV_COLUMNS = (
    "timestamp",
    "book",
    "symbol",
    "signal_id",
    "phase",
    "expiry_offset",
    "expiry",
    "contract",
    "right",
    "bid",
    "ask",
    "bid_size",
    "ask_size",
    "mid",
    "last",
    "underlying",
    "underlying_time",
    "model",
    "limit",
    "fill",
    "fill_time",
    "error",
)


def quote_dir() -> Path:
    raw = os.environ.get("FORWARD_QUOTE_DIR", "").strip()
    return Path(raw) if raw else Path("data/forward")


def note_quotes(
    state: dict,
    *,
    book: str,
    symbol: str,
    now: datetime,
    underlying: Optional[float],
    broker,
    lines: list[str],
    bars=None,
) -> bool:
    """Journal and append the live quote. Returns whether ``state`` changed.

    Never raises. A missing data client does nothing, so a dry run and a
    unit broker keep the journal they already had. ``bars`` is read only to
    mark the model at a signal-bar close. It does not change an order.
    """
    try:
        if not isinstance(state, dict):
            return False
        client = getattr(broker, "_data", None)
        if client is None:
            return False
        token = _BUDGET.set(time_mod.monotonic())
        try:
            changed = _note(
                state,
                book=book,
                symbol=symbol,
                now=now,
                underlying=underlying,
                broker=broker,
                client=client,
                bars=bars,
            )
        finally:
            _BUDGET.reset(token)
        if changed:
            error = state.get("quote_error")
            if error:
                lines.append(f"Quote log: {error}")
        return changed
    except Exception as exc:
        try:
            state["quote_error"] = _short(exc)
            lines.append(f"Quote log failed ({_short(exc)}). Entry and exit were not changed.")
        except Exception:
            lines.append("Quote log failed. Entry and exit were not changed.")
        return False


def report_lines(state: dict) -> list[str]:
    """Model versus the live mid versus the sandbox fill, plus the shadow expiries."""
    lines = [
        "Option quotes",
        (
            "The bid and ask are the live snapshot at the quote time, not a historical print. "
            "The model uses the underlying stored for that signal when the journal has it. "
            "The cash mirror uses the sandbox fill when the journal has one."
        ),
    ]
    error = state.get("quote_error") if isinstance(state, dict) else None
    if error:
        lines.append(f"Latest quote error: {error}")
    marks = [row for row in (state.get("quote_log") or []) if isinstance(row, dict)] if isinstance(state, dict) else []
    if not marks and not error:
        lines.append("No live option quote has been journaled yet. The model mirror is unchanged.")
        lines.append("")
        return lines
    entry_mid_gaps = []
    entry_fill_gaps = []
    exit_mid_gaps = []
    exit_fill_gaps = []
    for row in marks:
        if row.get("phase") not in {"signal_close", "modeled_entry", "entry", "exit"}:
            continue
        lines.append("- " + _mark_sentence(row))
        gap_mid = _gap(row.get("mid"), row.get("model"))
        gap_fill = _gap(row.get("fill"), row.get("model"))
        if row.get("phase") in {"modeled_entry", "entry"}:
            if gap_mid is not None:
                entry_mid_gaps.append(gap_mid)
            if gap_fill is not None:
                entry_fill_gaps.append(gap_fill)
        elif row.get("phase") == "exit":
            if gap_mid is not None:
                exit_mid_gaps.append(gap_mid)
            if gap_fill is not None:
                exit_fill_gaps.append(gap_fill)
    lines.append(
        "Entry slippage versus the model, live mid minus model: "
        f"{_avg(entry_mid_gaps)}. Sandbox fill minus model: {_avg(entry_fill_gaps)}."
    )
    lines.append(
        "Exit gap, live mid minus model: "
        f"{_avg(exit_mid_gaps)}. Sandbox fill minus model: {_avg(exit_fill_gaps)}."
    )
    lines.append(
        "A positive entry number means the live option was richer than Black-Scholes. "
        "The cash mirror uses the sandbox fill. The model P&L stays beside it."
    )
    lines.extend(_shadow_lines(state if isinstance(state, dict) else {}))
    lines.append("")
    return lines


def pick_expiry_ladder(listed: list[date], day: date) -> list[Optional[date]]:
    """Four expiries: today, then one, two, and three sessions out.

    A missing calendar day takes the next listed expiry that is not already
    used. The same Friday is not repeated for Monday.
    """
    ordered = sorted({item for item in listed if isinstance(item, date) and item >= day})
    used: set[date] = set()
    chosen: list[Optional[date]] = []
    for offset in range(4):
        target = day + timedelta(days=offset)
        pick = next((item for item in ordered if item >= target and item not in used), None)
        if pick is None:
            pick = next((item for item in ordered if item not in used), None)
        if pick is not None:
            used.add(pick)
        chosen.append(pick)
    return chosen


def parse_snapshot(payload: Any) -> dict:
    """Bid, ask, sizes, mid, and last from a snapshot or a level-1 quote."""
    found = {
        "bid": None,
        "ask": None,
        "bid_size": None,
        "ask_size": None,
        "last": None,
        "contract": None,
    }
    _consume(payload, found)
    bid = found["bid"]
    ask = found["ask"]
    mid = None
    if bid is not None and ask is not None and bid > 0 and ask > 0:
        mid = (bid + ask) / 2.0
    elif ask is not None and ask > 0:
        mid = ask
    elif bid is not None and bid > 0:
        mid = bid
    found["mid"] = mid
    return found


def one_contract_pnl(ask: Optional[float], bid: Optional[float]) -> Optional[float]:
    """Buy one contract at the ask and sell it at the bid."""
    if ask is None or bid is None or ask <= 0 or bid < 0:
        return None
    debit = ask * 100.0 + option_leg_fees(1, ask, sell=False)
    credit = bid * 100.0 - option_leg_fees(1, bid, sell=True)
    return credit - debit


def occ_symbol(symbol: str, expiry: date, right: str, strike: float) -> str:
    side = "C" if str(right).lower().startswith("c") else "P"
    return f"{symbol.upper()}{expiry.strftime('%y%m%d')}{side}{int(round(float(strike) * 1000)):08d}"


def _note(state, *, book, symbol, now, underlying, broker, client, bars=None) -> bool:
    changed = False
    local = to_ny(now)
    _ensure_option_quotes(state, client, symbol, underlying, local)
    state.setdefault("quote_log", [])
    state.setdefault("shadow", [])
    for position in list(state.get("positions") or []):
        if isinstance(position, dict) and _log_open(
            state, position, book=book, symbol=symbol, now=local, underlying=underlying, client=client
        ):
            changed = True
    for exit_row in list(state.get("exits") or []):
        if isinstance(exit_row, dict) and not exit_row.get("market"):
            if _log_exit(state, exit_row, book=book, symbol=symbol, now=local, underlying=underlying, client=client):
                changed = True
    if _mark_holds(state, book=book, symbol=symbol, now=local, underlying=underlying, client=client):
        changed = True
    for row in list(state.get("signals") or []):
        if not isinstance(row, dict) or row.get("market"):
            continue
        signal_day = _day(row.get("signal_time"))
        if signal_day is not None and signal_day != local.date() and row.get("status") not in {"open"}:
            row["market"] = {"phase": "older"}
            changed = True
            continue
        if _budget_spent():
            state["quote_error"] = "quote budget exceeded"
            changed = True
            break
        if _log_signal(
            state, row, book=book, symbol=symbol, now=local, underlying=underlying, client=client, bars=bars
        ):
            changed = True
    if _mark_holds(state, book=book, symbol=symbol, now=local, underlying=underlying, client=client):
        changed = True
    if _refresh_fills(state, broker):
        changed = True
    return changed


def _log_signal(state, row, *, book, symbol, now, underlying, client, bars=None) -> bool:
    right = str(row.get("right") or ("call" if row.get("direction") == "long" else "put"))
    option_type = "CALL" if right.lower().startswith("c") else "PUT"
    iv = _float(row.get("iv"))
    close_underlying = _float(row.get("signal_close"))
    if close_underlying is None:
        close_underlying = _close_at(bars, row.get("signal_time"))
    if close_underlying is None:
        close_underlying = underlying
    entry_underlying = _float(row.get("modeled_entry"))
    if entry_underlying is None:
        entry_underlying = _float(row.get("entry")) or underlying
    live = _ladder(client, symbol, option_type, entry_underlying or underlying or 0.0, now.date())
    items = live or [{"offset": 0, "error": "no listed expiry", "quote": {}}]
    entry_fill, entry_fill_time = _fill_for(state, row.get("id"), "entry")
    marks = []
    for phase, spot, when in (
        ("signal_close", close_underlying, row.get("signal_time") or now.isoformat()),
        ("modeled_entry", entry_underlying, row.get("entry_time") or row.get("fill_time") or now.isoformat()),
    ):
        for item in items:
            mark = _mark_from_contract(
                item,
                phase=phase,
                right=right,
                spot=spot,
                when=now,
                underlying_time=str(when),
                iv=iv,
                limit=_order_limit(state, row.get("id"), "entry") if phase == "modeled_entry" and item.get("offset") == 0 else None,
                fill=entry_fill if phase == "modeled_entry" and item.get("offset") == 0 else None,
                fill_time=entry_fill_time if phase == "modeled_entry" and item.get("offset") == 0 else None,
            )
            if phase == "modeled_entry" and item.get("offset") == 0 and _float(row.get("model_ask")) is not None:
                mark["model"] = _float(row.get("model_ask"))
            mark["signal_id"] = row.get("id")
            marks.append(mark)
    if _temporary_only(marks):
        state["quote_error"] = next(item.get("error") for item in marks if item.get("error"))
        return True
    for mark in marks:
        _append_csv(book, symbol, mark, now)
        state["quote_log"].append(dict(mark))
    zero_marks = [item for item in marks if item.get("expiry_offset") == 0]
    row["market"] = dict(zero_marks[-1] if zero_marks else marks[-1])
    row["market_marks"] = marks
    if row.get("status") in {"open", "closed"} and not _shadow_for(state, row.get("id")):
        _start_shadow(state, row, items, now=now, spot=entry_underlying, iv=iv, client=client, book=book, symbol=symbol)
    exit_row = next((item for item in state.get("exits") or [] if item.get("id") == row.get("id")), None)
    shadow = _shadow_for(state, row.get("id"))
    if exit_row is not None and shadow is not None and shadow.get("status") != "closed":
        _close_shadow(state, exit_row, None, now=now, spot=_float(exit_row.get("underlying")) or underlying, book=book, symbol=symbol, client=client)
    error = next((item.get("error") for item in marks if item.get("error")), None)
    if error:
        state["quote_error"] = error
    elif state.get("quote_error") and not any(item.get("error") for item in marks):
        state["quote_error"] = None
    return True


def _log_open(state, position, *, book, symbol, now, underlying, client) -> bool:
    right = str(position.get("right") or "call")
    option_type = "CALL" if right.lower().startswith("c") else "PUT"
    contract = str(position.get("option_symbol") or "")
    spot = underlying if underlying is not None else _float(position.get("entry"))
    quote = _quote_contract(client, contract) if contract else {}
    if not quote.get("bid") and not quote.get("ask"):
        ladder = _ladder(client, symbol, option_type, spot or 0.0, now.date())
        zero = next((item for item in ladder if item.get("offset") == 0), None)
        if zero:
            quote = dict(zero.get("quote") or {})
            quote["contract"] = zero.get("contract")
            quote["expiry"] = zero.get("expiry")
            if zero.get("error"):
                quote["error"] = zero["error"]
    iv = _float(position.get("iv"))
    mark = _mark_from_quote(
        quote,
        phase="open",
        right=right,
        spot=spot,
        when=now,
        underlying_time=now.isoformat(),
        iv=iv,
        expiry=str(position.get("expiry") or quote.get("expiry") or "")[:10] or None,
        offset=0,
        limit=None,
        fill=None,
        fill_time=None,
    )
    mark["signal_id"] = position.get("id")
    _append_csv(book, symbol, mark, now)
    if mark.get("error"):
        state["quote_error"] = mark["error"]
    if not _shadow_for(state, position.get("id")) and not _budget_spent():
        ladder = _ladder(client, symbol, option_type, spot or 0.0, now.date())
        if not _temporary_only([{"error": item.get("error")} for item in ladder]):
            _start_shadow(state, position, ladder, now=now, spot=spot, iv=iv, client=client, book=book, symbol=symbol)
    _touch_shadow(state, position.get("id"), quote, now=now, spot=spot, iv=iv, book=book, symbol=symbol, client=client)
    return True


def _log_exit(state, exit_row, *, book, symbol, now, underlying, client) -> bool:
    signal = next((row for row in state.get("signals") or [] if row.get("id") == exit_row.get("id")), None)
    position_like = signal if isinstance(signal, dict) else {}
    right = str(exit_row.get("right") or position_like.get("right") or "call")
    contract = _contract_for_row(symbol, position_like)
    spot = _float(exit_row.get("underlying")) or underlying
    quote = _quote_contract(client, contract) if contract else {}
    if not quote.get("bid") and not quote.get("ask"):
        option_type = "CALL" if right.lower().startswith("c") else "PUT"
        ladder = _ladder(client, symbol, option_type, spot or 0.0, now.date())
        zero = next((item for item in ladder if item.get("offset") == 0), {})
        quote = dict(zero.get("quote") or {})
        quote["contract"] = zero.get("contract")
        quote["expiry"] = zero.get("expiry")
        if zero.get("error"):
            quote["error"] = zero["error"]
    limit = _order_limit(state, exit_row.get("id"), "exit")
    fill, fill_time = _fill_for(state, exit_row.get("id"), "exit")
    mark = _mark_from_quote(
        quote,
        phase="exit",
        right=right,
        spot=spot,
        when=now,
        underlying_time=str(exit_row.get("time") or now.isoformat()),
        iv=_float(position_like.get("iv")),
        expiry=str(position_like.get("expiry") or quote.get("expiry") or "")[:10] or None,
        offset=0,
        limit=limit,
        fill=fill,
        fill_time=fill_time,
    )
    mark["signal_id"] = exit_row.get("id")
    mark["model"] = _float(exit_row.get("model_bid")) or mark.get("model")
    if _temporary(mark.get("error")) and mark.get("bid") is None and mark.get("ask") is None:
        state["quote_error"] = mark["error"]
        return True
    exit_row["market"] = dict(mark)
    if isinstance(signal, dict):
        signal.setdefault("exit_market", dict(mark))
    state["quote_log"].append(dict(mark))
    _append_csv(book, symbol, mark, now)
    if mark.get("error"):
        state["quote_error"] = mark["error"]
    _close_shadow(state, exit_row, quote, now=now, spot=spot, book=book, symbol=symbol, client=client)
    return True


def _start_shadow(state, row, ladder, *, now, spot, iv, client, book, symbol) -> None:
    legs = []
    for item in ladder:
        quote = item.get("quote") or {}
        model = _model(row.get("right"), spot, item.get("strike"), now, iv, item.get("expiry"))
        leg = {
            "offset": item.get("offset"),
            "expiry": item.get("expiry"),
            "contract": item.get("contract"),
            "strike": item.get("strike"),
            "entry_ask": quote.get("ask"),
            "entry_bid": quote.get("bid"),
            "entry_mid": quote.get("mid"),
            "entry_bid_size": quote.get("bid_size"),
            "entry_ask_size": quote.get("ask_size"),
            "entry_last": quote.get("last"),
            "entry_model": model,
            "entry_time": now.isoformat(),
            "error": item.get("error") or quote.get("error"),
            "exit_bid": None,
            "exit_model": None,
            "flat_bid": None,
            "flat_model": None,
            "next_bid": None,
            "next_model": None,
        }
        legs.append(leg)
        mark = _mark_from_quote(
            {**quote, "contract": item.get("contract"), "error": leg["error"]},
            phase="shadow_entry",
            right=str(row.get("right") or ""),
            spot=spot,
            when=now,
            underlying_time=now.isoformat(),
            iv=iv,
            expiry=item.get("expiry"),
            offset=item.get("offset"),
            limit=None,
            fill=None,
            fill_time=None,
        )
        mark["model"] = model
        mark["signal_id"] = row.get("id")
        _append_csv(book, symbol, mark, now)
    entry_time = row.get("entry_time") or now.isoformat()
    state["shadow"].append(
        {
            "id": row.get("id"),
            "right": row.get("right") or ("call" if row.get("direction") == "long" else "put"),
            "direction": row.get("direction"),
            "stop": row.get("stop"),
            "target": row.get("target"),
            "entry": spot,
            "entry_time": entry_time,
            "iv": iv,
            "status": "open",
            "entry_quote_late": _quote_is_late(entry_time, now),
            "legs": legs,
        }
    )


def _touch_shadow(state, signal_id, quote, *, now, spot, iv, book, symbol, client) -> None:
    shadow = _shadow_for(state, signal_id)
    if not shadow:
        return
    for leg in shadow.get("legs") or []:
        fresh = _fresh_leg_quote(client, leg, quote if leg.get("offset") == 0 else None)
        if not fresh:
            continue
        _remember_latest(leg, fresh, now)
        mark = _mark_from_quote(
            fresh,
            phase="shadow_open",
            right=str(shadow.get("right") or ""),
            spot=spot,
            when=now,
            underlying_time=now.isoformat(),
            iv=iv,
            expiry=leg.get("expiry"),
            offset=leg.get("offset"),
            limit=None,
            fill=None,
            fill_time=None,
        )
        mark["model"] = _model(shadow.get("right"), spot, leg.get("strike"), now, iv, leg.get("expiry"))
        mark["signal_id"] = signal_id
        _append_csv(book, symbol, mark, now)
    if now.time() >= NY_FLAT:
        _stamp_flat(shadow, now=now, spot=spot)


def _close_shadow(state, exit_row, quote, *, now, spot, book, symbol, client) -> None:
    shadow = _shadow_for(state, exit_row.get("id"))
    if not shadow or shadow.get("status") == "closed":
        return
    shadow["status"] = "closed"
    shadow["exit_reason"] = exit_row.get("reason")
    shadow["exit_time"] = str(exit_row.get("time") or now.isoformat())
    iv = _float(shadow.get("iv"))
    for leg in shadow.get("legs") or []:
        fresh = _fresh_leg_quote(client, leg, quote)
        bid = (fresh or {}).get("bid")
        if bid is None:
            bid = leg.get("latest_bid")
        leg["exit_bid"] = bid
        leg["exit_ask"] = (fresh or {}).get("ask")
        leg["exit_mid"] = (fresh or {}).get("mid")
        leg["exit_bid_size"] = (fresh or {}).get("bid_size")
        leg["exit_ask_size"] = (fresh or {}).get("ask_size")
        leg["exit_model"] = _model(shadow.get("right"), spot, leg.get("strike"), now, iv, leg.get("expiry"))
        leg["pnl_exit"] = one_contract_pnl(leg.get("entry_ask"), bid)
        if (fresh or {}).get("error"):
            leg["error"] = fresh["error"]
        mark = _mark_from_quote(
            fresh or {},
            phase="shadow_exit",
            right=str(shadow.get("right") or ""),
            spot=spot,
            when=now,
            underlying_time=shadow["exit_time"],
            iv=iv,
            expiry=leg.get("expiry"),
            offset=leg.get("offset"),
            limit=None,
            fill=None,
            fill_time=None,
        )
        mark["bid"] = bid
        mark["model"] = leg.get("exit_model")
        mark["signal_id"] = shadow.get("id")
        mark["contract"] = leg.get("contract")
        _append_csv(book, symbol, mark, now)
    if now.time() >= NY_FLAT:
        _stamp_flat(shadow, now=now, spot=spot)


def _mark_holds(state, *, book, symbol, now, underlying, client) -> bool:
    changed = False
    today = now.date()
    for shadow in state.get("shadow") or []:
        if not isinstance(shadow, dict):
            continue
        entry_day = _day(shadow.get("entry_time"))
        if now.time() >= NY_FLAT and any(
            leg.get("flat_bid") is None and (leg.get("offset") or 0) > 0 for leg in shadow.get("legs") or []
        ):
            for leg in shadow.get("legs") or []:
                if (leg.get("offset") or 0) == 0 or leg.get("flat_bid") is not None or not leg.get("contract"):
                    continue
                fresh = _quote_contract(client, str(leg["contract"]))
                if fresh.get("bid") is not None:
                    _remember_latest(leg, fresh, now)
                elif fresh.get("error"):
                    leg["flat_error"] = fresh["error"]
                    state["quote_error"] = fresh["error"]
            before = [leg.get("flat_bid") for leg in shadow.get("legs") or []]
            _stamp_flat(shadow, now=now, spot=underlying)
            after = [leg.get("flat_bid") for leg in shadow.get("legs") or []]
            if before != after:
                changed = True
                for leg in shadow.get("legs") or []:
                    if (leg.get("offset") or 0) == 0 or leg.get("flat_bid") is None:
                        continue
                    _append_csv(
                        book,
                        symbol,
                        {
                            "phase": "shadow_flat",
                            "signal_id": shadow.get("id"),
                            "right": shadow.get("right"),
                            "expiry_offset": leg.get("offset"),
                            "expiry": leg.get("expiry"),
                            "contract": leg.get("contract"),
                            "bid": leg.get("flat_bid"),
                            "model": leg.get("flat_model"),
                            "underlying": underlying,
                            "underlying_time": now.isoformat(),
                            "quote_time": now.isoformat(),
                        },
                        now,
                    )
        if entry_day is not None and today > entry_day:
            for leg in shadow.get("legs") or []:
                if (leg.get("offset") or 0) == 0 or leg.get("next_bid") is not None or not leg.get("contract"):
                    continue
                fresh = _quote_contract(client, str(leg["contract"]))
                bid = fresh.get("bid")
                if bid is None:
                    if fresh.get("error"):
                        leg["next_error"] = fresh["error"]
                        state["quote_error"] = fresh["error"]
                    continue
                leg["next_bid"] = bid
                leg["next_model"] = _model(shadow.get("right"), underlying, leg.get("strike"), now, _float(shadow.get("iv")), leg.get("expiry"))
                leg["pnl_next"] = one_contract_pnl(leg.get("entry_ask"), bid)
                changed = True
                _append_csv(
                    book,
                    symbol,
                    {
                        "phase": "shadow_next_open",
                        "signal_id": shadow.get("id"),
                        "right": shadow.get("right"),
                        "expiry_offset": leg.get("offset"),
                        "expiry": leg.get("expiry"),
                        "contract": leg.get("contract"),
                        "bid": bid,
                        "model": leg.get("next_model"),
                        "underlying": underlying,
                        "underlying_time": now.isoformat(),
                    },
                    now,
                )
    return changed


def _stamp_flat(shadow, *, now, spot) -> None:
    iv = _float(shadow.get("iv"))
    for leg in shadow.get("legs") or []:
        if (leg.get("offset") or 0) == 0 or leg.get("flat_bid") is not None:
            continue
        bid = leg.get("flat_source_bid")
        if bid is None:
            continue
        leg["flat_bid"] = bid
        leg["flat_model"] = _model(shadow.get("right"), spot, leg.get("strike"), now, iv, leg.get("expiry"))
        leg["pnl_flat"] = one_contract_pnl(leg.get("entry_ask"), bid)
        leg["flat_time"] = now.isoformat()


# Option snapshot accepts at most 20 symbols. The stock depth endpoint does not.
OPTION_BATCH = 20
_OPTION_CACHE: dict[str, dict] = {}
_PRIMED = False


def clear_option_cache() -> None:
    """Drop quotes from the previous tick. The next read fetches again."""
    global _PRIMED
    _OPTION_CACHE.clear()
    _PRIMED = False


def cached_option(symbol: str) -> dict:
    return dict(_OPTION_CACHE.get(str(symbol or "")) or {})


def prime_forward_quotes(journal, broker, specs, now, include_ladder: bool) -> None:
    """One option snapshot for the open contracts, and the 0-3 DTE shadows when asked.

    ``specs`` is ``(book, underlying symbol, 5-minute bars)``. Underlyings stay
    on the stock snapshot. Options stay on the option snapshot. A failure here
    leaves the cache empty and does not change a position.
    """
    global _PRIMED
    from webull_bot.execution.forward_vwap import _spot

    clear_option_cache()
    client = getattr(broker, "_data", None)
    if client is None or journal is None:
        return
    symbols: list[str] = []
    clock = pd.Timestamp(now)
    for book, symbol, bars in specs:
        try:
            state = journal.forward_load(book) or {}
        except Exception:
            state = {}
        spot = _spot(bars, clock) if bars is not None and len(getattr(bars, "index", ())) else None
        for item in option_symbols_for(state, client, symbol, spot, now, include_ladder):
            if item not in symbols:
                symbols.append(item)
    if symbols:
        _fetch_option_quotes(client, symbols)
    _PRIMED = True


def option_symbols_for(state, client, symbol: str, spot, now, include_ladder: bool) -> list[str]:
    """Contracts this book will read. The ladder is the chain lookup, not a quote."""
    found: list[str] = []

    def add(value) -> None:
        text = str(value or "")
        if text and text not in found:
            found.append(text)

    if not isinstance(state, dict):
        return found
    for position in state.get("positions") or []:
        if isinstance(position, dict):
            add(position.get("option_symbol"))
    for row in list(state.get("signals") or []) + list(state.get("exits") or []):
        if isinstance(row, dict):
            add(row.get("option_symbol") or row.get("order_symbol"))
    if not include_ladder or client is None:
        return found
    local = to_ny(now)
    rights = []
    for row in list(state.get("positions") or []) + list(state.get("signals") or []):
        if not isinstance(row, dict):
            continue
        if row in (state.get("signals") or []) and row.get("market"):
            continue
        right = str(row.get("right") or row.get("option_type") or "")
        kind = "CALL" if right.lower().startswith("c") else "PUT" if right.lower().startswith("p") else ""
        if kind and kind not in rights:
            rights.append(kind)
    for kind in rights:
        for item in _ladder_plan(client, symbol, kind, spot or 0.0, local.date()):
            add(item.get("contract"))
    return found


def _ensure_option_quotes(state, client, symbol: str, spot, now) -> None:
    """One batched option snapshot for this book, unless the tick already took it."""
    if client is None:
        return
    if not _PRIMED:
        _OPTION_CACHE.clear()
    needed = option_symbols_for(state, client, symbol, spot, now, True)
    missing = [item for item in needed if item not in _OPTION_CACHE]
    if missing:
        _fetch_option_quotes(client, missing)


def _fetch_option_quotes(client, symbols: list[str]) -> None:
    """``get_option_snapshot`` with a list. No stock snapshot and no depth."""
    market = getattr(client, "option_market_data", None)
    method = getattr(market, "get_option_snapshot", None)
    wanted = []
    for symbol in symbols:
        text = str(symbol or "")
        if text and text not in wanted:
            wanted.append(text)
    if method is None:
        for symbol in wanted:
            _OPTION_CACHE[symbol] = {"contract": symbol, "error": "no option snapshot"}
        return
    for start in range(0, len(wanted), OPTION_BATCH):
        chunk = wanted[start : start + OPTION_BATCH]
        try:
            payload = _call(method, chunk, "US_OPTION")
        except Exception as exc:
            message = _short(exc)
            for symbol in chunk:
                _OPTION_CACHE[symbol] = {"contract": symbol, "error": f"option snapshot: {message}"}
            continue
        parsed = _parse_option_batch(payload, chunk)
        for symbol in chunk:
            _OPTION_CACHE[symbol] = parsed.get(symbol) or {
                "contract": symbol,
                "error": "option snapshot had no bid or ask",
            }


def _parse_option_batch(payload, symbols: list[str]) -> dict[str, dict]:
    body = _json(payload)
    rows = _snapshot_rows(body)
    found: dict[str, dict] = {}
    for row in rows:
        parsed = parse_snapshot(row)
        key = str(parsed.get("contract") or "")
        if not key and isinstance(row, dict):
            key = str(row.get("symbol") or row.get("option_symbol") or "")
        if not key and len(symbols) == 1:
            key = symbols[0]
        if not key:
            continue
        parsed["contract"] = key
        if parsed.get("bid") is not None or parsed.get("ask") is not None or parsed.get("last") is not None:
            parsed["error"] = None
        found[key] = parsed
    if len(symbols) == 1 and symbols[0] not in found:
        parsed = parse_snapshot(body)
        parsed["contract"] = parsed.get("contract") or symbols[0]
        if parsed.get("bid") is not None or parsed.get("ask") is not None or parsed.get("last") is not None:
            parsed["error"] = None
            found[symbols[0]] = parsed
    return found


def _snapshot_rows(payload) -> list:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("data", "result", "quotes", "items", "records"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            nested = _snapshot_rows(value)
            return nested or [value]
    return [payload]


def _ladder(client, symbol, option_type, spot, day: date) -> list[dict]:
    built = _ladder_plan(client, symbol, option_type, spot, day)
    for item in built:
        occ = str(item.get("contract") or "")
        if not occ:
            continue
        if occ not in _OPTION_CACHE:
            _fetch_option_quotes(client, [occ])
        quote = dict(_OPTION_CACHE.get(occ) or {"error": "no contract symbol"})
        error = quote.get("error")
        if item.get("error") and error:
            error = f"{item['error']}; {error}"
        elif item.get("error") and quote.get("bid") is None and quote.get("ask") is None:
            error = item["error"]
        item["quote"] = quote
        item["error"] = error
    return built


def _ladder_plan(client, symbol, option_type, spot, day: date) -> list[dict]:
    contracts = _list_contracts(client, symbol, option_type, spot, day)
    chain_error = _chain_error(contracts)
    if chain_error:
        contracts = []
    listed = []
    for row in contracts:
        expiry = _day(row.get("expiry") or row.get("expiration_date") or row.get("expire_date"))
        if expiry is not None:
            listed.append(expiry)
    slots = pick_expiry_ladder(listed, day)
    if not any(slots):
        slots = pick_expiry_ladder(_weekday_guess(day), day)
    built = []
    for offset, expiry in enumerate(slots):
        if expiry is None:
            built.append({"offset": offset, "error": chain_error or "no listed expiry"})
            continue
        chosen = _contract_on(contracts, expiry, option_type, spot)
        strike = chosen.get("strike") if chosen else listed_strike(spot, spot) if spot else None
        occ = chosen.get("option_symbol") if chosen else (occ_symbol(symbol, expiry, option_type, strike) if strike else "")
        built.append(
            {
                "offset": offset,
                "expiry": expiry.isoformat() if expiry is not None else None,
                "contract": occ,
                "strike": strike,
                "quote": {},
                "error": chain_error,
            }
        )
    return built


def _chain_error(contracts) -> Optional[str]:
    if len(contracts) == 1 and isinstance(contracts[0], dict) and contracts[0].get("error"):
        if not any(contracts[0].get(key) for key in ("expiry", "expiration_date", "expire_date")):
            return str(contracts[0]["error"])
    return None


def _weekday_guess(day: date) -> list[date]:
    found = []
    cursor = day
    while len(found) < 6:
        if cursor.weekday() < 5:
            found.append(cursor)
        cursor += timedelta(days=1)
    return found


def _list_contracts(client, symbol, option_type, spot, day: date) -> list:
    instrument = getattr(client, "instrument", None)
    method = getattr(instrument, "list_option_contracts", None)
    if method is None or spot is None or spot <= 0:
        return []
    low = round(spot * 0.97, 2)
    high = round(spot * 1.03, 2)
    try:
        payload = _call(
            method,
            category="US_OPTION",
            underlying_symbols=symbol,
            option_type=option_type,
            strike_price_gte=low,
            strike_price_lte=high,
            start_date=day.isoformat(),
            end_date=(day + timedelta(days=14)).isoformat(),
        )
    except Exception as exc:
        return [{"error": _short(exc)}]
    return _rows(payload)


def _contract_on(contracts, expiry: date, option_type: str, spot: float) -> Optional[dict]:
    best = None
    best_gap = None
    wanted = option_type.upper()
    for row in contracts:
        if not isinstance(row, dict):
            continue
        kind = str(row.get("option_type") or row.get("type") or "").upper()
        if kind and kind != wanted:
            continue
        row_expiry = _day(row.get("expiry") or row.get("expiration_date") or row.get("expire_date") or row.get("option_expire_date"))
        if row_expiry != expiry:
            continue
        strike = _float(row.get("strike_price") or row.get("strike") or row.get("exercise_price"))
        occ = str(row.get("option_symbol") or row.get("symbol") or "")
        if strike is None or not occ:
            continue
        gap = abs(strike - spot) if spot else strike
        if best_gap is None or gap < best_gap:
            best_gap = gap
            best = {"option_symbol": occ, "strike": strike}
    return best


def _quote_contract(client, option_symbol: str) -> dict:
    """The option snapshot only. Stock depth is not a quote for an option."""
    if not option_symbol:
        return {"error": "no option symbol"}
    cached = _OPTION_CACHE.get(str(option_symbol))
    if cached is not None:
        return dict(cached)
    _fetch_option_quotes(client, [option_symbol])
    return dict(_OPTION_CACHE.get(str(option_symbol)) or {"contract": option_symbol, "error": "no option snapshot"})


def _fresh_leg_quote(client, leg, fallback) -> dict:
    """Quote this expiry's own contract. The 0DTE quote is only a fallback for that same contract."""
    contract = str(leg.get("contract") or "")
    fallback = fallback or {}
    if contract and contract == str(fallback.get("contract") or "") and (
        fallback.get("bid") is not None or fallback.get("ask") is not None
    ):
        return fallback
    if contract and not _budget_spent():
        fresh = _quote_contract(client, contract)
        if fresh.get("bid") is not None or fresh.get("ask") is not None or fresh.get("error"):
            fresh["contract"] = fresh.get("contract") or contract
            return fresh
    if leg.get("offset") == 0 and (fallback.get("bid") is not None or fallback.get("ask") is not None):
        return fallback
    return {"contract": contract, "error": (fallback or {}).get("error")}


def _temporary(error) -> bool:
    text = str(error or "").lower()
    return "budget exceeded" in text or "timed out" in text


def _temporary_only(marks) -> bool:
    errors = [item.get("error") for item in marks if isinstance(item, dict)]
    return bool(errors) and all(_temporary(item) for item in errors)


def _quote_is_late(entry_time, now) -> bool:
    started = _clock(entry_time)
    clock = _clock(now)
    if started is None or clock is None:
        return False
    return clock - started > timedelta(minutes=3)


def _clock(value) -> Optional[datetime]:
    if isinstance(value, datetime):
        return to_ny(value)
    if value in (None, ""):
        return None
    try:
        stamp = pd.Timestamp(value)
    except (TypeError, ValueError):
        return None
    if stamp.tzinfo is None:
        stamp = stamp.tz_localize("America/New_York")
    return to_ny(stamp.to_pydatetime())


def _close_at(bars, when) -> Optional[float]:
    if bars is None or when in (None, ""):
        return None
    try:
        if getattr(bars, "empty", True):
            return None
        stamp = pd.Timestamp(when)
        index = bars.index
        tz = getattr(index, "tz", None)
        if stamp.tzinfo is None and tz is not None:
            stamp = stamp.tz_localize(tz)
        elif stamp.tzinfo is not None and tz is not None:
            stamp = stamp.tz_convert(tz)
        elif stamp.tzinfo is not None and tz is None:
            stamp = stamp.tz_convert("America/New_York").tz_localize(None)
        if stamp not in index or "close" not in bars.columns:
            return None
        price = float(bars.loc[stamp, "close"])
    except (TypeError, ValueError, KeyError):
        return None
    if price != price or price <= 0:
        return None
    return price


def _contract_for_row(symbol: str, row: dict) -> str:
    explicit = str(row.get("option_symbol") or row.get("order_symbol") or "")
    if explicit:
        return explicit
    expiry = _day(row.get("expiry"))
    strike = _float(row.get("strike"))
    right = row.get("right") or row.get("option_type")
    if expiry is None or strike is None or not right:
        return ""
    return occ_symbol(symbol, expiry, str(right), strike)


def _budget_spent() -> bool:
    started = _BUDGET.get()
    return started is not None and (time_mod.monotonic() - started) > CYCLE_BUDGET_S


def _call(method, *args, **kwargs):
    if _budget_spent():
        raise TimeoutError("quote budget exceeded")
    box: dict[str, Any] = {}

    def run() -> None:
        try:
            box["value"] = method(*args, **kwargs)
        except Exception as exc:
            box["error"] = exc

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    thread.join(CALL_TIMEOUT_S)
    if thread.is_alive():
        raise TimeoutError(f"quote timed out after {CALL_TIMEOUT_S}s")
    if "error" in box:
        raise box["error"]
    return _json(box.get("value"))


def _refresh_fills(state, broker) -> bool:
    changed = False
    for order in state.get("orders") or []:
        if not isinstance(order, dict) or order.get("fill") not in (None, ""):
            continue
        if order.get("status") not in {"submitted", "intent"}:
            continue
        if int(order.get("fill_tries") or 0) >= 5:
            continue
        order["fill_tries"] = int(order.get("fill_tries") or 0) + 1
        changed = True
        fill = _read_fill(broker, str(order.get("id") or ""))
        if not fill:
            continue
        order["fill"] = fill.get("price")
        order["fill_time"] = fill.get("time")
        if fill.get("error"):
            order["fill_error"] = fill["error"]
            state["quote_error"] = fill["error"]
        changed = True
        for row in state.get("quote_log") or []:
            if row.get("signal_id") and order.get("key", "").startswith(str(row.get("signal_id"))):
                phase = "exit" if str(order.get("kind")) == "exit" else "entry"
                if row.get("phase") in {phase, "modeled_entry"} and row.get("fill") in (None, ""):
                    row["fill"] = fill.get("price")
                    row["fill_time"] = fill.get("time")
    return changed


def _read_fill(broker, client_order_id: str) -> dict:
    if not client_order_id or broker is None:
        return {}
    trade = getattr(broker, "_trade", None)
    account = getattr(broker, "account_id", None)
    method = getattr(getattr(trade, "order_v3", None), "get_order_detail", None)
    if method is None or not account:
        return {}
    try:
        payload = _call(method, account, client_order_id)
    except Exception as exc:
        return {"error": _short(exc)}
    return _parse_fill(payload)


def _parse_fill(payload: Any) -> dict:
    found = {"price": None, "time": None}
    _consume_fill(payload, found)
    if found["price"] is None and found["time"] is None:
        return {}
    return found


def _consume_fill(payload: Any, found: dict) -> None:
    if isinstance(payload, list):
        for item in payload:
            _consume_fill(item, found)
        return
    if not isinstance(payload, dict):
        return
    if found["price"] is None:
        found["price"] = _float_first(payload, "avg_filled_price", "filled_price", "avg_price", "fill_price", "average_price")
    if found["time"] is None:
        for key in ("filled_time", "fill_time", "filled_at", "transaction_time", "last_filled_time"):
            if payload.get(key):
                found["time"] = str(payload.get(key))
                break
    for value in payload.values():
        if isinstance(value, (dict, list)):
            _consume_fill(value, found)


def _mark_from_contract(item, **kwargs) -> dict:
    item = item or {}
    quote = dict(item.get("quote") or {})
    quote["contract"] = item.get("contract") or quote.get("contract")
    quote["strike"] = item.get("strike")
    quote["error"] = item.get("error") or quote.get("error")
    return _mark_from_quote(quote, expiry=item.get("expiry"), offset=item.get("offset"), **kwargs)


def _mark_from_quote(quote, *, phase, right, spot, when, underlying_time, iv, expiry, offset, limit, fill, fill_time) -> dict:
    quote = quote or {}
    strike = _float(quote.get("strike"))
    model = _model(right, spot, strike, when, iv, expiry) if strike else _model(right, spot, listed_strike(spot, spot) if spot else None, when, iv, expiry)
    return {
        "phase": phase,
        "right": right,
        "expiry_offset": offset if offset is not None else 0,
        "expiry": expiry,
        "contract": quote.get("contract"),
        "bid": quote.get("bid"),
        "ask": quote.get("ask"),
        "bid_size": quote.get("bid_size"),
        "ask_size": quote.get("ask_size"),
        "mid": quote.get("mid"),
        "last": quote.get("last"),
        "underlying": spot,
        "underlying_time": underlying_time,
        "model": model,
        "limit": limit,
        "fill": fill,
        "fill_time": fill_time,
        "error": quote.get("error"),
        "quote_time": when.isoformat() if hasattr(when, "isoformat") else str(when),
    }


def _model(right, spot, strike, when, iv, expiry) -> Optional[float]:
    if spot is None or strike is None or iv is None or iv <= 0 or spot <= 0 or strike <= 0:
        return None
    day = _day(expiry)
    clock = pd.Timestamp(when)
    if clock.tzinfo is None:
        clock = clock.tz_localize("America/New_York")
    dte = 0 if day is None else max(0, (day - clock.tz_convert("America/New_York").date()).days)
    try:
        return float(_option_mid(str(right or "call"), float(spot), float(strike), clock, float(iv), dte))
    except Exception:
        return None


def _append_csv(book: str, symbol: str, mark: dict, now) -> None:
    try:
        folder = quote_dir()
        folder.mkdir(parents=True, exist_ok=True)
        day = to_ny(now).strftime("%Y%m%d") if not isinstance(now, datetime) else to_ny(now).strftime("%Y%m%d")
        path = folder / f"quotes_{book}_{day}.csv"
        new_file = not path.exists()
        with path.open("a", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS, extrasaction="ignore")
            if new_file:
                writer.writeheader()
            row = {column: mark.get(column, "") for column in CSV_COLUMNS}
            row["timestamp"] = mark.get("quote_time") or (now.isoformat() if hasattr(now, "isoformat") else str(now))
            row["book"] = book
            row["symbol"] = symbol
            row["signal_id"] = mark.get("signal_id") or ""
            writer.writerow(row)
    except Exception:
        return


def _order_limit(state, signal_id, kind: str) -> Optional[float]:
    for order in state.get("orders") or []:
        if not isinstance(order, dict):
            continue
        if str(order.get("key") or "").startswith(f"{signal_id}|") and order.get("kind") == kind:
            return _float(order.get("limit"))
    return None


def _fill_for(state, signal_id, kind: str) -> tuple[Optional[float], Optional[str]]:
    for order in state.get("orders") or []:
        if not isinstance(order, dict):
            continue
        if str(order.get("key") or "").startswith(f"{signal_id}|") and order.get("kind") == kind:
            return _float(order.get("fill")), order.get("fill_time")
    return None, None


def _shadow_for(state, signal_id) -> Optional[dict]:
    for row in state.get("shadow") or []:
        if isinstance(row, dict) and row.get("id") == signal_id:
            return row
    return None


def _remember_latest(leg, quote, now=None) -> None:
    if quote.get("bid") is not None:
        leg["latest_bid"] = quote.get("bid")
    if quote.get("ask") is not None:
        leg["latest_ask"] = quote.get("ask")
    if quote.get("mid") is not None:
        leg["latest_mid"] = quote.get("mid")
    if quote.get("bid_size") is not None:
        leg["latest_bid_size"] = quote.get("bid_size")
    if quote.get("ask_size") is not None:
        leg["latest_ask_size"] = quote.get("ask_size")
    if quote.get("error"):
        leg["error"] = quote["error"]
    if now is not None and getattr(now, "time", None) and now.time() >= NY_FLAT and quote.get("bid") is not None:
        leg["flat_source_bid"] = quote.get("bid")


def _shadow_lines(state: dict) -> list[str]:
    rows = [row for row in (state.get("shadow") or []) if isinstance(row, dict)]
    lines = [
        "Shadow expiries, one contract, buy at the ask and sell at the bid. No order is sent for 1DTE, 2DTE, or 3DTE."
    ]
    if not rows:
        lines.append("No shadow expiry has been recorded yet.")
        return lines
    rolled = {offset: {"exit": [], "flat": [], "next": []} for offset in range(4)}
    for shadow in rows:
        lines.append(
            f"- {shadow.get('id')} {shadow.get('right')} status {shadow.get('status')} "
            f"reason {shadow.get('exit_reason') or 'still open'}"
        )
        if shadow.get("entry_quote_late"):
            lines.append(
                "    The entry ask is the first live quote after this logger started. "
                "It is not the print at the modeled entry."
            )
        for leg in shadow.get("legs") or []:
            offset = leg.get("offset")
            pnl_exit = leg.get("pnl_exit")
            text = (
                f"    {offset}DTE {leg.get('expiry')} {leg.get('contract')} "
                f"entry ask {_money(leg.get('entry_ask'))} model {_money(leg.get('entry_model'))} "
                f"exit bid {_money(leg.get('exit_bid'))} model {_money(leg.get('exit_model'))} "
                f"P&L {_money(pnl_exit)}"
            )
            if (offset or 0) > 0:
                text += (
                    f"; 15:45 bid {_money(leg.get('flat_bid'))} P&L {_money(leg.get('pnl_flat'))}; "
                    f"next session bid {_money(leg.get('next_bid'))} P&L {_money(leg.get('pnl_next'))}"
                )
            if leg.get("error"):
                text += f"; quote {leg.get('error')}"
            lines.append(text)
            if isinstance(offset, int) and offset in rolled:
                if pnl_exit is not None:
                    rolled[offset]["exit"].append(float(pnl_exit))
                if leg.get("pnl_flat") is not None:
                    rolled[offset]["flat"].append(float(leg["pnl_flat"]))
                if leg.get("pnl_next") is not None:
                    rolled[offset]["next"].append(float(leg["pnl_next"]))
    lines.append("Real P&L by expiry. One contract. Buy at the ask, sell at the bid.")
    labels = (
        ("exit", "at the same underlying exit"),
        ("flat", "held to 15:45"),
        ("next", "held to the next session"),
    )
    for offset in range(4):
        for key, label in labels:
            if offset == 0 and key != "exit":
                continue
            values = rolled[offset][key]
            if not values:
                lines.append(f"- {offset}DTE {label}: n/a")
                continue
            lines.append(
                f"- {offset}DTE {label}: average {_money(sum(values) / len(values))} on {len(values)} shadow"
                + ("s" if len(values) != 1 else "")
            )
    return lines


def _mark_sentence(row: dict) -> str:
    return (
        f"{row.get('phase')} {row.get('signal_id') or ''} {row.get('contract') or 'no contract'} "
        f"model {_money(row.get('model'))} mid {_money(row.get('mid'))} "
        f"bid {_money(row.get('bid'))} ask {_money(row.get('ask'))} "
        f"limit {_money(row.get('limit'))} fill {_money(row.get('fill'))} at {row.get('fill_time') or 'n/a'} "
        f"underlying {_money(row.get('underlying'))} quote {row.get('quote_time') or 'n/a'}"
        + (f" error {row.get('error')}" if row.get("error") else "")
    )


def _consume(payload: Any, found: dict) -> None:
    if isinstance(payload, list):
        for item in payload:
            _consume(item, found)
        return
    if not isinstance(payload, dict):
        return
    if found["contract"] is None:
        for key in ("option_symbol", "symbol", "instrument_id"):
            if payload.get(key) and str(payload.get(key)).upper().startswith(("SPY", "QQQ", "AAPL")):
                found["contract"] = str(payload.get(key))
                break
    if found["ask"] is None:
        found["ask"] = _float_first(payload, "ask", "ask_price", "askPrice", "best_ask", "ap")
    if found["bid"] is None:
        found["bid"] = _float_first(payload, "bid", "bid_price", "bidPrice", "best_bid", "bp")
    if found["ask_size"] is None:
        found["ask_size"] = _float_first(payload, "ask_size", "askSize", "ask_volume", "as", "av")
    if found["bid_size"] is None:
        found["bid_size"] = _float_first(payload, "bid_size", "bidSize", "bid_volume", "bs", "bv")
    if found["last"] is None:
        found["last"] = _float_first(payload, "last", "last_price", "lastPrice", "latest_price", "close", "price")
    for side, price_key, size_key in (("asks", "ask", "ask_size"), ("bids", "bid", "bid_size")):
        levels = payload.get(side) or payload.get(side[:-1])
        if isinstance(levels, list) and levels:
            level = levels[0]
            if isinstance(level, dict):
                if found[price_key] is None:
                    found[price_key] = _float_first(level, "price", "px", side[:-1])
                if found[size_key] is None:
                    found[size_key] = _float_first(level, "size", "volume", "qty", "quantity")
            elif isinstance(level, (list, tuple)) and level:
                if found[price_key] is None:
                    found[price_key] = _float(level[0])
                if found[size_key] is None and len(level) > 1:
                    found[size_key] = _float(level[1])
    for value in payload.values():
        if isinstance(value, (dict, list)):
            _consume(value, found)


def _rows(payload: Any) -> list:
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    for key in ("contracts", "data", "items", "result", "records"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            nested = _rows(value)
            if nested:
                return nested
    return []


def _json(response: Any) -> Any:
    if hasattr(response, "json"):
        try:
            return response.json()
        except Exception:
            return None
    return response


def _float(value) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:
        return None
    return number


def _float_first(row: dict, *keys: str) -> Optional[float]:
    for key in keys:
        number = _float(row.get(key))
        if number is not None:
            return number
    return None


def _day(value) -> Optional[date]:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return to_ny(value).date()
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _gap(live, model) -> Optional[float]:
    left = _float(live)
    right = _float(model)
    if left is None or right is None:
        return None
    return left - right


def _avg(values: list[float]) -> str:
    if not values:
        return "n/a"
    return f"${sum(values) / len(values):.4f}"


def _money(value) -> str:
    number = _float(value)
    if number is None:
        return "n/a"
    return f"${number:.4f}" if abs(number) < 1000 else f"${number:,.2f}"


def _short(exc: BaseException) -> str:
    text = f"{type(exc).__name__}: {exc}"
    text = " ".join(text.split())
    if len(text) > 240:
        text = text[:240]
    return text
