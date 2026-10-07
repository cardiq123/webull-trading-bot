"""14 DTE at-the-money contract from a Webull option chain and snapshot.

The expiry is the listed date closest to the target. The strike is the one
nearest the spot on that expiry. A tie on the strike takes the lower price.
This module does not connect. The caller passes a data client.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Optional


def atm_from_client(data_client, symbol: str, option_type: str, spot: float, target: date) -> Optional[dict]:
    """Ask of the nearest listed contract. None when the chain or the ask is missing."""
    if data_client is None or spot <= 0:
        return None
    rows = _contracts(data_client, symbol, option_type, spot, target)
    chosen = pick_atm(rows, spot=spot, target=target, option_type=option_type)
    if chosen is None:
        return None
    ask, delta = _snapshot_ask(data_client, chosen["option_symbol"])
    if ask is None or ask <= 0:
        return None
    chosen["ask"] = ask
    if delta is not None:
        chosen["delta"] = delta
    return chosen


def pick_atm(rows: list, *, spot: float, target: date, option_type: str) -> Optional[dict]:
    """Expiry closest to ``target``, then the strike closest to ``spot``."""
    best = None
    best_key = None
    wanted = option_type.upper()
    for row in rows:
        if not isinstance(row, dict):
            continue
        kind = str(row.get("option_type") or row.get("type") or "").upper()
        if kind and kind != wanted:
            continue
        expiry = _expiry(row)
        strike = _number(row, "strike_price", "strike", "exercise_price")
        occ = str(row.get("option_symbol") or row.get("symbol") or row.get("ticker") or "")
        if expiry is None or strike is None or strike <= 0 or not occ:
            continue
        key = (abs((expiry - target).days), abs(strike - spot), strike)
        if best_key is None or key < best_key:
            best_key = key
            best = {
                "option_symbol": occ,
                "strike": float(strike),
                "expiry": expiry.isoformat(),
                "option_type": wanted,
            }
    return best


def _contracts(data_client, symbol: str, option_type: str, spot: float, target: date) -> list:
    instrument = getattr(data_client, "instrument", None)
    if instrument is None or not hasattr(instrument, "list_option_contracts"):
        return []
    low = round(spot * 0.8, 2)
    high = round(spot * 1.2, 2)
    windows = (
        {
            "start_date": (target - timedelta(days=10)).isoformat(),
            "end_date": (target + timedelta(days=10)).isoformat(),
        },
        {"end_date": (target - timedelta(days=21)).isoformat()},
    )
    for extra in windows:
        try:
            rows = _pages(
                instrument.list_option_contracts,
                category="US_OPTION",
                underlying_symbols=symbol,
                option_type=option_type,
                strike_price_gte=low,
                strike_price_lte=high,
                **extra,
            )
        except Exception:
            rows = []
        if rows:
            return rows
    return []


def _pages(method, **kwargs) -> list:
    rows: list = []
    key = None
    for _ in range(5):
        call = dict(kwargs)
        if key:
            call["pagination_key"] = key
        payload = _json(method(**call))
        rows.extend(_rows(payload))
        key = payload.get("pagination_key") if isinstance(payload, dict) else None
        if not key:
            break
    return rows


def _snapshot_ask(data_client, option_symbol: str) -> tuple[Optional[float], Optional[float]]:
    market = getattr(data_client, "option_market_data", None)
    if market is None or not hasattr(market, "get_option_snapshot"):
        return None, None
    try:
        payload = _json(market.get_option_snapshot(option_symbol, "US_OPTION"))
    except Exception:
        return None, None
    for row in _rows(payload) or ([payload] if isinstance(payload, dict) else []):
        if not isinstance(row, dict):
            continue
        ask = _number(row, "ask", "ask_price", "askPrice", "best_ask")
        delta = _number(row, "delta", "option_delta")
        quote = row.get("quote") if isinstance(row.get("quote"), dict) else None
        if ask is None and quote is not None:
            ask = _number(quote, "ask", "ask_price", "ap")
        if ask is not None:
            return ask, delta
    return None, None


def _json(response: Any) -> Any:
    if hasattr(response, "json"):
        try:
            return response.json()
        except Exception:
            return None
    return response


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


def _expiry(row: dict) -> Optional[date]:
    for key in ("expiration_date", "expire_date", "expiry", "option_expire_date", "exp_date"):
        value = row.get(key)
        if not value:
            continue
        try:
            return date.fromisoformat(str(value)[:10])
        except ValueError:
            continue
    return None


def _number(row: dict, *keys: str) -> Optional[float]:
    for key in keys:
        value = row.get(key)
        if value in (None, ""):
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if number == number:
            return number
    return None
