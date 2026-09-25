"""Market data through the official Webull OpenAPI.

Historical and streaming US stock data requires an OpenAPI market-data
subscription in addition to the app key. The getting-started guide says a
missing subscription returns HTTP 403. This provider was not executed
against a live key in this repository; see the notes on ``WebullBroker``.
"""

from __future__ import annotations

from typing import Iterable

import pandas as pd

from webull_bot.data.base import DataProvider, normalize_frame

_TIMESPAN = {
    "1m": "M1",
    "5m": "M5",
    "15m": "M15",
    "30m": "M30",
    "1h": "H1",
    "60m": "H1",
    "1d": "D1",
}

class WebullDataProvider(DataProvider):
    def __init__(self, broker_client) -> None:
        """``broker_client`` is a connected ``WebullBroker`` or any object
        with a ``data_client`` attribute exposing ``market_data``.
        """
        self._client = broker_client

    def history(
        self,
        symbols: Iterable[str],
        start: str,
        end: str,
        interval: str = "1d",
    ) -> dict[str, pd.DataFrame]:
        timespan = _TIMESPAN.get(interval)
        if timespan is None:
            raise ValueError(f"Unsupported Webull interval {interval}")
        data_client = self._client.data_client
        frames: dict[str, pd.DataFrame] = {}
        symbol_list = list(symbols)
        # Official example:
        #   get_history_bar(symbol, category, timespan)
        #   get_batch_history_bar(symbols, category, timespan, count)
        # Category US_ETF versus US_STOCK was not verified for every ETF.
        for symbol in symbol_list:
            category = "US_ETF" if _looks_like_etf(symbol) else "US_STOCK"
            response = data_client.market_data.get_history_bar(symbol, category, timespan)
            payload = _json(response)
            frame = _bars_from_payload(payload)
            if frame is None or frame.empty:
                continue
            normal = normalize_frame(frame, "1d" if interval == "1d" else interval)
            start_ts = pd.Timestamp(start)
            end_ts = pd.Timestamp(end)
            if normal.index.tz is not None:
                start_ts = start_ts.tz_localize(normal.index.tz)
                end_ts = end_ts.tz_localize(normal.index.tz)
            frames[symbol] = normal.loc[(normal.index >= start_ts) & (normal.index <= end_ts)]
        return frames


def _looks_like_etf(symbol: str) -> bool:
    return symbol in {
        "SPY", "QQQ", "IWM", "DIA", "EFA", "EEM", "TLT", "GLD", "BIL",
        "XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLI", "XLB", "XLU", "XLRE",
    }


def _json(response):
    if hasattr(response, "json"):
        return response.json()
    return response


def _bars_from_payload(payload) -> pd.DataFrame | None:
    """Defensive parse. The documented response shape was not captured live."""
    rows = payload
    if isinstance(payload, dict):
        for key in ("bars", "data", "result", "candles", "history"):
            if key in payload:
                rows = payload[key]
                break
        else:
            if "close" in payload or "c" in payload:
                rows = [payload]
    if isinstance(rows, dict):
        rows = rows.get("bars") or rows.get("data") or []
    if not isinstance(rows, list) or not rows:
        return None
    records = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        records.append(
            {
                "time": row.get("time") or row.get("timestamp") or row.get("t") or row.get("date"),
                "open": row.get("open") or row.get("o"),
                "high": row.get("high") or row.get("h"),
                "low": row.get("low") or row.get("l"),
                "close": row.get("close") or row.get("c"),
                "volume": row.get("volume") or row.get("v") or 0,
            }
        )
    frame = pd.DataFrame(records)
    if frame.empty or frame["time"].isna().all():
        return None
    frame["time"] = pd.to_datetime(frame["time"], utc=True, errors="coerce")
    frame = frame.dropna(subset=["time"]).set_index("time")
    return frame
