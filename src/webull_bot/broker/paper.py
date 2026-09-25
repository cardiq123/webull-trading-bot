"""Paper broker.

Fills are simulated with the same cost model as the backtester. State is
stored in SQLite so a separate ``kill`` process can cancel and flatten.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from webull_bot.costs import CostModel, buy_fees, buy_price, sell_price, sell_regulatory_fees
from webull_bot.models import (
    AccountSnapshot,
    Fill,
    Order,
    OrderStatus,
    OrderType,
    Position,
    Side,
)


class PaperBroker:
    name = "paper"

    def __init__(
        self,
        db_path: str | Path,
        costs: CostModel,
        starting_equity: float = 100_000.0,
        account_type: str = "margin",
    ) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.costs = costs
        self.starting_equity = float(starting_equity)
        self.account_type = account_type
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row
        self._init()

    def connect(self) -> None:
        row = self._conn.execute("SELECT cash FROM account WHERE id = 1").fetchone()
        if row is None:
            self._conn.execute(
                "INSERT INTO account (id, cash, equity, peak_equity) VALUES (1, ?, ?, ?)",
                (self.starting_equity, self.starting_equity, self.starting_equity),
            )
            self._conn.commit()

    def snapshot(self) -> AccountSnapshot:
        cash = self._cash()
        positions = self.positions()
        equity = cash
        for pos in positions:
            price = pos.peak_price or pos.avg_price
            equity += pos.quantity * price
        return AccountSnapshot(
            equity=equity,
            cash=cash,
            buying_power=cash,
            account_type=self.account_type,
            positions=positions,
            open_orders=self.open_orders(),
        )

    def positions(self) -> list[Position]:
        rows = self._conn.execute("SELECT * FROM positions").fetchall()
        return [
            Position(
                symbol=row["symbol"],
                quantity=row["quantity"],
                avg_price=row["avg_price"],
                strategy=row["strategy"] or "",
                stop_price=row["stop_price"],
                opened_on=None,
                sector=row["sector"] or "",
                peak_price=row["last_price"] or row["avg_price"],
            )
            for row in rows
        ]

    def open_orders(self) -> list[Order]:
        rows = self._conn.execute("SELECT * FROM orders WHERE status = 'NEW'").fetchall()
        return [self._order_from_row(row) for row in rows]

    def place_order(self, order: Order) -> Order:
        order.status = OrderStatus.NEW
        self._conn.execute(
            """
            INSERT OR REPLACE INTO orders (
                client_order_id, symbol, side, quantity, order_type, limit_price,
                stop_price, status, strategy, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'NEW', ?, ?)
            """,
            (
                order.client_order_id,
                order.symbol,
                order.side.value,
                order.quantity,
                order.order_type.value,
                order.limit_price,
                order.stop_price,
                order.strategy,
                _now(),
            ),
        )
        self._conn.commit()
        return order

    def cancel_order(self, client_order_id: str) -> None:
        self._conn.execute(
            "UPDATE orders SET status = 'CANCELED' WHERE client_order_id = ? AND status = 'NEW'",
            (client_order_id,),
        )
        self._conn.commit()

    def fill_exit(self, symbol: str, price: float, reason: str) -> list[Fill]:
        pos = self._conn.execute("SELECT * FROM positions WHERE symbol = ?", (symbol,)).fetchone()
        if pos is None:
            return []
        return self._fill_sell(symbol, float(pos["quantity"]), price, reason, pos["strategy"] or "")

    def flatten(self) -> list[Fill]:
        """Cancel resting orders and fill market exits at the last marked price."""
        self.cancel_all()
        fills: list[Fill] = []
        for pos in self.positions():
            if pos.quantity <= 0:
                continue
            price = pos.peak_price or pos.avg_price
            fills.extend(self._fill_sell(pos.symbol, pos.quantity, price, "flatten", pos.strategy))
        return fills

    def mark_prices(self, prices: dict[str, float]) -> None:
        for symbol, price in prices.items():
            self._conn.execute(
                "UPDATE positions SET last_price = ? WHERE symbol = ?",
                (float(price), symbol),
            )
        self._conn.commit()

    def process_bar(self, symbol: str, open_: float, high: float, low: float, close: float) -> list[Fill]:
        """Fill resting orders against one bar. Stops gap through to the open."""
        fills: list[Fill] = []
        orders = [
            row
            for row in self._conn.execute("SELECT * FROM orders WHERE status = 'NEW' AND symbol = ?", (symbol,))
        ]
        for row in orders:
            order = self._order_from_row(row)
            fill_raw = _paper_fill_price(order, open_, high, low, close)
            if fill_raw is None:
                continue
            if order.side == Side.BUY:
                fills.extend(self._fill_buy(order, fill_raw))
            else:
                fills.extend(self._fill_sell(symbol, order.quantity, fill_raw, "order", order.strategy, order.client_order_id))
        # Protective stops stored on the position, if no resting stop order filled them.
        pos = self._conn.execute("SELECT * FROM positions WHERE symbol = ?", (symbol,)).fetchone()
        if pos is not None and pos["stop_price"] is not None:
            stop = float(pos["stop_price"])
            if open_ <= stop or low <= stop:
                raw = open_ if open_ <= stop else stop
                fills.extend(self._fill_sell(symbol, float(pos["quantity"]), raw, "stop", pos["strategy"] or ""))
        self.mark_prices({symbol: close})
        self._refresh_equity()
        return fills

    def _fill_buy(self, order: Order, raw_price: float) -> list[Fill]:
        fill_px = buy_price(raw_price, self.costs)
        fee = buy_fees(self.costs)
        spent = fill_px * order.quantity + fee
        cash = self._cash()
        if spent > cash + 1e-8:
            self.cancel_order(order.client_order_id)
            return []
        self._conn.execute("UPDATE account SET cash = cash - ? WHERE id = 1", (spent,))
        existing = self._conn.execute("SELECT * FROM positions WHERE symbol = ?", (order.symbol,)).fetchone()
        if existing is None:
            self._conn.execute(
                """
                INSERT INTO positions (symbol, quantity, avg_price, strategy, stop_price, last_price, sector)
                VALUES (?, ?, ?, ?, ?, ?, '')
                """,
                (order.symbol, order.quantity, fill_px, order.strategy, order.stop_price, fill_px),
            )
        else:
            new_qty = float(existing["quantity"]) + order.quantity
            self._conn.execute(
                "UPDATE positions SET quantity = ?, avg_price = ?, last_price = ? WHERE symbol = ?",
                (new_qty, fill_px, fill_px, order.symbol),
            )
        self._conn.execute(
            "UPDATE orders SET status = 'FILLED', fill_price = ? WHERE client_order_id = ?",
            (fill_px, order.client_order_id),
        )
        self._conn.commit()
        return [
            Fill(
                client_order_id=order.client_order_id,
                symbol=order.symbol,
                side=Side.BUY,
                quantity=order.quantity,
                price=fill_px,
                fees=fee,
                time=datetime.now(timezone.utc),
                strategy=order.strategy,
                reason="fill",
            )
        ]

    def _fill_sell(
        self,
        symbol: str,
        quantity: float,
        raw_price: float,
        reason: str,
        strategy: str,
        client_order_id: str = "",
    ) -> list[Fill]:
        pos = self._conn.execute("SELECT * FROM positions WHERE symbol = ?", (symbol,)).fetchone()
        if pos is None:
            return []
        qty = min(float(quantity), float(pos["quantity"]))
        fill_px = sell_price(raw_price, self.costs)
        fees = sell_regulatory_fees(fill_px, qty, self.costs)
        proceeds = fill_px * qty - fees
        self._conn.execute("UPDATE account SET cash = cash + ? WHERE id = 1", (proceeds,))
        left = float(pos["quantity"]) - qty
        if left <= 1e-9:
            self._conn.execute("DELETE FROM positions WHERE symbol = ?", (symbol,))
        else:
            self._conn.execute("UPDATE positions SET quantity = ? WHERE symbol = ?", (left, symbol))
        if client_order_id:
            self._conn.execute(
                "UPDATE orders SET status = 'FILLED', fill_price = ? WHERE client_order_id = ?",
                (fill_px, client_order_id),
            )
        self._conn.commit()
        return [
            Fill(
                client_order_id=client_order_id or f"paper-{symbol}",
                symbol=symbol,
                side=Side.SELL,
                quantity=qty,
                price=fill_px,
                fees=fees,
                time=datetime.now(timezone.utc),
                strategy=strategy,
                reason=reason,
            )
        ]

    def _cash(self) -> float:
        row = self._conn.execute("SELECT cash FROM account WHERE id = 1").fetchone()
        if row is None:
            self.connect()
            row = self._conn.execute("SELECT cash FROM account WHERE id = 1").fetchone()
        return float(row["cash"])

    def _refresh_equity(self) -> None:
        snap = self.snapshot()
        self._conn.execute(
            "UPDATE account SET equity = ?, peak_equity = MAX(peak_equity, ?) WHERE id = 1",
            (snap.equity, snap.equity),
        )
        self._conn.commit()

    def _init(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS account (
                id INTEGER PRIMARY KEY,
                cash REAL NOT NULL,
                equity REAL NOT NULL,
                peak_equity REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS positions (
                symbol TEXT PRIMARY KEY,
                quantity REAL NOT NULL,
                avg_price REAL NOT NULL,
                strategy TEXT,
                stop_price REAL,
                last_price REAL,
                sector TEXT
            );
            CREATE TABLE IF NOT EXISTS orders (
                client_order_id TEXT PRIMARY KEY,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                quantity REAL NOT NULL,
                order_type TEXT NOT NULL,
                limit_price REAL,
                stop_price REAL,
                status TEXT NOT NULL,
                strategy TEXT,
                fill_price REAL,
                created_at TEXT
            );
            """
        )
        self._conn.commit()

    @staticmethod
    def _order_from_row(row: sqlite3.Row) -> Order:
        return Order(
            client_order_id=row["client_order_id"],
            symbol=row["symbol"],
            side=Side(row["side"]),
            quantity=row["quantity"],
            order_type=OrderType(row["order_type"]),
            limit_price=row["limit_price"],
            stop_price=row["stop_price"],
            strategy=row["strategy"] or "",
            status=OrderStatus(row["status"]),
        )


def _paper_fill_price(order: Order, open_: float, high: float, low: float, close: float) -> Optional[float]:
    if order.order_type == OrderType.MARKET:
        return open_
    if order.order_type == OrderType.LIMIT and order.limit_price is not None:
        if order.side == Side.BUY and low <= order.limit_price:
            return order.limit_price if open_ > order.limit_price else open_
        if order.side == Side.SELL and high >= order.limit_price:
            return order.limit_price if open_ < order.limit_price else open_
        return None
    if order.order_type == OrderType.STOP and order.stop_price is not None:
        if order.side == Side.SELL and (open_ <= order.stop_price or low <= order.stop_price):
            return open_ if open_ <= order.stop_price else order.stop_price
        if order.side == Side.BUY and (open_ >= order.stop_price or high >= order.stop_price):
            return open_ if open_ >= order.stop_price else order.stop_price
    return None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
