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

# Timespans the sandbox accepts. D1 and H1 return HTTP 417 UNSUPPORTED_TIMESPAN.
ALLOWED_TIMESPANS = ("M1", "M5", "M15", "M30", "M60", "M120", "M240", "D", "W", "M", "Y")
MAX_BARS = 1200

_TIMESPAN = {
    "1m": "M1",
    "5m": "M5",
    "15m": "M15",
    "30m": "M30",
    "1h": "M60",
    "60m": "M60",
    "120m": "M120",
    "2h": "M120",
    "240m": "M240",
    "4h": "M240",
    "1d": "D",
    "1w": "W",
    "1mo": "M",
    "1y": "Y",
}

_INTERVAL_SECONDS = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "60m": 3600,
    "120m": 7200,
    "2h": 7200,
    "240m": 14400,
    "4h": 14400,
    "1d": 86400,
    "1w": 7 * 86400,
    "1mo": 30 * 86400,
    "1y": 365 * 86400,
}


def webull_timespan(interval: str) -> str:
    timespan = _TIMESPAN.get(interval)
    if timespan not in ALLOWED_TIMESPANS:
        raise ValueError(
            f"Unsupported Webull interval {interval}. "
            f"Timespan must be one of {', '.join(ALLOWED_TIMESPANS)}."
        )
    return timespan


def bar_request_count(start: str, end: str, interval: str) -> int:
    """How many bars to request. The server caps a call at 1200."""
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)
    seconds = max((end_ts - start_ts).total_seconds(), 0.0)
    step = _INTERVAL_SECONDS.get(interval, 86400)
    estimate = int(seconds / step) + 1
    return max(1, min(MAX_BARS, estimate))


def to_epoch_ms(value: str, *, inclusive_end: bool = False) -> int:
    """UTC epoch milliseconds. A date-only end includes that whole UTC day."""
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    else:
        ts = ts.tz_convert("UTC")
    if inclusive_end and ts == ts.normalize():
        ts = ts + pd.Timedelta(days=1) - pd.Timedelta(milliseconds=1)
    return int(ts.timestamp() * 1000)

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
        timespan = webull_timespan(interval)
        data_client = self._client.data_client
        frames: dict[str, pd.DataFrame] = {}
        grouped: dict[str, list[str]] = {}
        for symbol in list(symbols):
            category = "US_ETF" if _looks_like_etf(symbol) else "US_STOCK"
            grouped.setdefault(category, []).append(symbol)
        start_ms = to_epoch_ms(start)
        end_ms = to_epoch_ms(end, inclusive_end=True)
        count = str(bar_request_count(start, end, interval))
        # get_history_bar is marked unavailable in SDK 3.0.2. The batch
        # endpoint returns {"result":[{"symbol":"SPY","result":[bars...]}]}.
        for category, names in grouped.items():
            response = data_client.market_data.get_batch_history_bar(
                names,
                category,
                timespan,
                count=count,
                start_time=start_ms,
                end_time=end_ms,
            )
            payload = _json(response)
            parsed = _frames_from_payload(payload)
            if set(parsed) == {""} and len(names) == 1:
                parsed = {names[0]: parsed[""]}
            for symbol, frame in parsed.items():
                if frame is None or frame.empty:
                    continue
                normal = normalize_frame(frame, "1d" if interval == "1d" else interval)
                start_ts = pd.Timestamp(start)
                end_ts = pd.Timestamp(end)
                if normal.index.tz is not None:
                    start_ts = start_ts.tz_localize(normal.index.tz)
                    end_ts = end_ts.tz_localize(normal.index.tz)
                elif interval == "1d":
                    end_ts = end_ts.normalize()
                    start_ts = start_ts.normalize()
                frames[symbol] = normal.loc[(normal.index >= start_ts) & (normal.index <= end_ts)]
        return frames

    def quote(self, symbol: str) -> dict:
        """Latest snapshot for one symbol. Read-only."""
        category = "US_ETF" if _looks_like_etf(symbol) else "US_STOCK"
        response = self._client.data_client.market_data.get_snapshot([symbol], category)
        payload = _json(response)
        if isinstance(payload, dict):
            return payload
        return {"result": payload}


def _looks_like_etf(symbol: str) -> bool:
    return symbol in {
        "SPY", "QQQ", "IWM", "DIA", "EFA", "EEM", "TLT", "GLD", "BIL",
        "XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLI", "XLB", "XLU", "XLRE",
    }


def _json(response):
    if hasattr(response, "json"):
        return response.json()
    return response


def _unwrap_symbol_results(payload) -> dict[str, list] | None:
    """Turn ``{"result":[{"symbol","result":[bars]}]}`` into symbol -> bars."""
    rows = None
    if isinstance(payload, dict) and isinstance(payload.get("result"), list):
        rows = payload["result"]
    elif isinstance(payload, list):
        rows = payload
    if not rows or not isinstance(rows[0], dict):
        return None
    if "symbol" in rows[0] and isinstance(rows[0].get("result"), list):
        return {
            str(item.get("symbol")): list(item.get("result") or [])
            for item in rows
            if isinstance(item, dict)
        }
    return None


def _frames_from_payload(payload) -> dict[str, pd.DataFrame]:
    nested = _unwrap_symbol_results(payload)
    if nested is not None:
        frames = {}
        for symbol, rows in nested.items():
            frame = _frame_from_rows(rows)
            if frame is not None and not frame.empty:
                frames[symbol] = frame
        return frames
    frame = _bars_from_payload(payload)
    if frame is None or frame.empty:
        return {}
    return {"": frame}


def _bars_from_payload(payload) -> pd.DataFrame | None:
    """Parse one bar list. A nested per-symbol result is unwrapped first."""
    nested = _unwrap_symbol_results(payload)
    if nested is not None:
        if len(nested) != 1:
            return None
        return _frame_from_rows(next(iter(nested.values())))
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
    return _frame_from_rows(rows)


def _frame_from_rows(rows) -> pd.DataFrame | None:
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
    frame["time"] = _parse_bar_times(frame["time"])
    frame = frame.dropna(subset=["time"]).set_index("time")
    return frame


def _parse_bar_times(series: pd.Series) -> pd.Series:
    """Epoch milliseconds from the batch endpoint, or an ordinary timestamp."""
    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.notna().any() and float(numeric.dropna().abs().median()) > 10**11:
        return pd.to_datetime(numeric, unit="ms", utc=True, errors="coerce")
    return pd.to_datetime(series, utc=True, errors="coerce")
