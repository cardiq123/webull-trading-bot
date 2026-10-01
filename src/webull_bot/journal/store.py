"""SQLite trade journal."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class Journal:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path)
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY,
                ts TEXT NOT NULL,
                kind TEXT NOT NULL,
                message TEXT NOT NULL,
                data_json TEXT
            );
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY,
                ts TEXT NOT NULL,
                symbol TEXT,
                strategy TEXT,
                side TEXT,
                quantity REAL,
                price REAL,
                fees REAL,
                pnl REAL,
                reason TEXT,
                mode TEXT
            );
            CREATE TABLE IF NOT EXISTS equity (
                id INTEGER PRIMARY KEY,
                ts TEXT NOT NULL,
                equity REAL,
                cash REAL,
                mode TEXT
            );
            """
        )
        self._conn.commit()

    def event(self, kind: str, message: str, data: dict[str, Any] | None = None) -> None:
        self._conn.execute(
            "INSERT INTO events (ts, kind, message, data_json) VALUES (?, ?, ?, ?)",
            (_now(), kind, message, json.dumps(data or {}, default=str)),
        )
        self._conn.commit()

    def trade(self, **fields: Any) -> None:
        self._conn.execute(
            """
            INSERT INTO trades (ts, symbol, strategy, side, quantity, price, fees, pnl, reason, mode)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _now(),
                fields.get("symbol"),
                fields.get("strategy"),
                fields.get("side"),
                fields.get("quantity"),
                fields.get("price"),
                fields.get("fees"),
                fields.get("pnl"),
                fields.get("reason"),
                fields.get("mode"),
            ),
        )
        self._conn.commit()

    def equity(self, equity: float, cash: float, mode: str) -> None:
        self._conn.execute(
            "INSERT INTO equity (ts, equity, cash, mode) VALUES (?, ?, ?, ?)",
            (_now(), equity, cash, mode),
        )
        self._conn.commit()

    def recent_events(self, limit: int = 20) -> list[sqlite3.Row]:
        self._conn.row_factory = sqlite3.Row
        return list(
            self._conn.execute("SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,))
        )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
