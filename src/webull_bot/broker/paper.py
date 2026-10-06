"""Paper broker.

Fills are simulated with the same cost model as the backtester. State is
stored in SQLite so a separate ``kill`` process can cancel and flatten.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from webull_bot.broker.base import Broker
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


class PaperBroker(Broker):
    name = "paper"

    def __init__(
        self,
        db_path: str | Path,
        costs: CostModel,
        starting_equity: float = 100_000.0,
        account_type: str = "margin",
        leverage: float = 1.0,
    ) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.costs = costs
        self.starting_equity = float(starting_equity)
        self.account_type = account_type
        # 1.0 debits the full share notional, which is the stock paper account.
        # A higher value reserves notional/leverage so a futures-sized print can
        # be rehearsed through the same fill and stop code. Stock replay leaves this at 1.
        self.leverage = float(leverage) if leverage and leverage > 0 else 1.0
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
        reserved = self._reserved_by_symbol()
        equity = cash
        for pos in positions:
            price = pos.peak_price or pos.avg_price
            margin = reserved.get(pos.symbol, 0.0)
            if margin <= 0:
                margin = pos.avg_price * pos.quantity
            equity += margin + (price - pos.avg_price) * pos.quantity
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
                stop_price, status, strategy, created_at, trail_type, trail_step, trail_peak
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'NEW', ?, ?, ?, ?, ?)
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
                order.trail_type,
                order.trail_step,
                order.trail_peak,
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
        for order in self.open_orders():
            if order.symbol == symbol:
                self.cancel_order(order.client_order_id)
        return self._fill_sell(symbol, float(pos["quantity"]), price, reason, pos["strategy"] or "")

    def set_sector(self, symbol: str, sector: str) -> None:
        self._conn.execute(
            "UPDATE positions SET sector = ? WHERE symbol = ?",
            (sector, symbol),
        )
        self._conn.commit()

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

    def update_stop(self, symbol: str, stop_price: float) -> None:
        self._conn.execute(
            "UPDATE positions SET stop_price = ? WHERE symbol = ?",
            (float(stop_price), symbol),
        )
        self._conn.commit()

    def fill_order_at(self, order: Order, raw_price: float) -> list[Fill]:
        """Fill a market order at a known print, such as a closing price.

        ``process_bar`` fills market orders at the bar open. Spec 8 buys the
        close, so the paper path needs this entry point. It uses the same
        cost model as every other paper fill.
        """
        self.place_order(order)
        if order.side == Side.BUY:
            fills = self._fill_buy(order, raw_price)
        else:
            fills = self._fill_sell(
                order.symbol, order.quantity, raw_price, "fill", order.strategy, order.client_order_id
            )
        self.mark_prices({order.symbol: raw_price})
        self._refresh_equity()
        return fills

    def process_bar(self, symbol: str, open_: float, high: float, low: float, close: float) -> list[Fill]:
        """Fill resting orders against one bar.

        Market orders fill at the open. If the bar trades through a protective
        stop and a profit limit, the stop fills. A gap through the stop fills
        at the open.
        """
        fills: list[Fill] = []
        orders = list(
            self._conn.execute("SELECT * FROM orders WHERE status = 'NEW' AND symbol = ?", (symbol,))
        )
        for row in orders:
            order = self._order_from_row(row)
            if order.order_type != OrderType.MARKET:
                continue
            fill_raw = _paper_fill_price(order, open_, high, low, close)
            if fill_raw is None:
                continue
            if order.side == Side.BUY:
                fills.extend(self._fill_buy(order, fill_raw))
            else:
                fills.extend(
                    self._fill_sell(symbol, order.quantity, fill_raw, "order", order.strategy, order.client_order_id)
                )
        stopped = self._stop_out(symbol, open_, low)
        fills.extend(stopped)
        if stopped:
            self.mark_prices({symbol: close})
            self._refresh_equity()
            return fills
        fills.extend(self._trail_orders(symbol, open_, high, low))
        resting = list(
            self._conn.execute("SELECT * FROM orders WHERE status = 'NEW' AND symbol = ?", (symbol,))
        )
        for row in resting:
            order = self._order_from_row(row)
            if order.order_type == OrderType.MARKET:
                continue
            fill_raw = _paper_fill_price(order, open_, high, low, close)
            if fill_raw is None:
                continue
            if order.side == Side.BUY:
                fills.extend(self._fill_buy(order, fill_raw))
            else:
                fills.extend(
                    self._fill_sell(symbol, order.quantity, fill_raw, "target", order.strategy, order.client_order_id)
                )
        self.mark_prices({symbol: close})
        self._refresh_equity()
        return fills

    def _trail_orders(self, symbol: str, open_: float, high: float, low: float) -> list[Fill]:
        """Fill a DAY trailing stop and remember the high-water mark.

        The stop in force at the open is tested first. The bar's extreme
        then tightens it, and that tighter stop can fill on the same bar.
        """
        fills: list[Fill] = []
        rows = list(
            self._conn.execute(
                "SELECT * FROM orders WHERE status = 'NEW' AND symbol = ? AND order_type = ?",
                (symbol, OrderType.TRAILING.value),
            )
        )
        for row in rows:
            order = self._order_from_row(row)
            if order.side != Side.SELL:
                continue
            if order.trail_step is None or order.trail_step <= 0 or not order.trail_type:
                continue
            peak = float(order.trail_peak) if order.trail_peak is not None else float(open_)
            fill_raw = _trail_fill(order.side, order.trail_type, float(order.trail_step), peak, open_, high, low)
            if fill_raw is None:
                new_peak = _trail_peak(order.side, peak, high, low)
                self._conn.execute(
                    "UPDATE orders SET trail_peak = ? WHERE client_order_id = ?",
                    (new_peak, order.client_order_id),
                )
                self._conn.commit()
                continue
            fills.extend(
                self._fill_sell(symbol, order.quantity, fill_raw, "trail", order.strategy, order.client_order_id)
            )
        return fills

    def _stop_out(self, symbol: str, open_: float, low: float) -> list[Fill]:
        """Fill the protective stop and cancel resting orders when the bar hits it."""
        pos = self._conn.execute("SELECT * FROM positions WHERE symbol = ?", (symbol,)).fetchone()
        if pos is None or pos["stop_price"] is None:
            return []
        stop = float(pos["stop_price"])
        if not (open_ <= stop or low <= stop):
            return []
        raw = open_ if open_ <= stop else stop
        fills = self._fill_sell(symbol, float(pos["quantity"]), raw, "stop", pos["strategy"] or "")
        for order in self.open_orders():
            if order.symbol == symbol:
                self.cancel_order(order.client_order_id)
        return fills

    def _fill_buy(self, order: Order, raw_price: float) -> list[Fill]:
        fill_px = buy_price(raw_price, self.costs)
        fee = buy_fees(self.costs)
        reserve = fill_px * order.quantity / self.leverage
        spent = reserve + fee
        cash = self._cash()
        if spent > cash + 1e-8:
            self.cancel_order(order.client_order_id)
            return []
        self._conn.execute("UPDATE account SET cash = cash - ? WHERE id = 1", (spent,))
        existing = self._conn.execute("SELECT * FROM positions WHERE symbol = ?", (order.symbol,)).fetchone()
        if existing is None:
            self._conn.execute(
                """
                INSERT INTO positions (
                    symbol, quantity, avg_price, strategy, stop_price, last_price, sector, margin_reserved
                ) VALUES (?, ?, ?, ?, ?, ?, '', ?)
                """,
                (order.symbol, order.quantity, fill_px, order.strategy, order.stop_price, fill_px, reserve),
            )
        else:
            new_qty = float(existing["quantity"]) + order.quantity
            new_reserve = float(existing["margin_reserved"] or 0.0) + reserve
            self._conn.execute(
                "UPDATE positions SET quantity = ?, avg_price = ?, last_price = ?, margin_reserved = ? WHERE symbol = ?",
                (new_qty, fill_px, fill_px, new_reserve, order.symbol),
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
        full_qty = float(pos["quantity"])
        fill_px = sell_price(raw_price, self.costs)
        fees = sell_regulatory_fees(fill_px, qty, self.costs)
        reserved = float(pos["margin_reserved"] or 0.0)
        if reserved <= 0:
            reserved = float(pos["avg_price"]) * full_qty
        reserved = reserved * (qty / full_qty) if full_qty else 0.0
        # Give back the reserved margin and book the price change. At 1x
        # leverage the reserve is the full notional, so this is the same
        # cash credit as paying the sale proceeds.
        credit = reserved + (fill_px - float(pos["avg_price"])) * qty - fees
        self._conn.execute("UPDATE account SET cash = cash + ? WHERE id = 1", (credit,))
        left = full_qty - qty
        if left <= 1e-9:
            self._conn.execute("DELETE FROM positions WHERE symbol = ?", (symbol,))
        else:
            left_reserve = float(pos["margin_reserved"] or 0.0) * (left / full_qty)
            self._conn.execute(
                "UPDATE positions SET quantity = ?, margin_reserved = ? WHERE symbol = ?",
                (left, left_reserve, symbol),
            )
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
                sector TEXT,
                margin_reserved REAL DEFAULT 0
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
        columns = {row[1] for row in self._conn.execute("PRAGMA table_info(positions)")}
        if "margin_reserved" not in columns:
            self._conn.execute("ALTER TABLE positions ADD COLUMN margin_reserved REAL DEFAULT 0")
            self._conn.commit()
        order_columns = {row[1] for row in self._conn.execute("PRAGMA table_info(orders)")}
        for name, decl in (("trail_type", "TEXT"), ("trail_step", "REAL"), ("trail_peak", "REAL")):
            if name not in order_columns:
                self._conn.execute(f"ALTER TABLE orders ADD COLUMN {name} {decl}")
        self._conn.commit()

    def _reserved_by_symbol(self) -> dict[str, float]:
        rows = self._conn.execute("SELECT symbol, margin_reserved FROM positions").fetchall()
        return {row["symbol"]: float(row["margin_reserved"] or 0.0) for row in rows}

    @staticmethod
    def _order_from_row(row: sqlite3.Row) -> Order:
        keys = set(row.keys())
        return Order(
            client_order_id=row["client_order_id"],
            symbol=row["symbol"],
            side=Side(row["side"]),
            quantity=row["quantity"],
            order_type=OrderType(row["order_type"]),
            limit_price=row["limit_price"],
            stop_price=row["stop_price"],
            trail_type=row["trail_type"] if "trail_type" in keys else None,
            trail_step=row["trail_step"] if "trail_step" in keys else None,
            trail_peak=row["trail_peak"] if "trail_peak" in keys else None,
            strategy=row["strategy"] or "",
            status=OrderStatus(row["status"]),
        )


def _trail_level(kind: str, peak: float, step: float, *, long_exit: bool) -> float:
    if kind == "PERCENTAGE":
        return peak * (1.0 - step) if long_exit else peak * (1.0 + step)
    return peak - step if long_exit else peak + step


def _trail_peak(side: Side, peak: float, high: float, low: float) -> float:
    if side == Side.SELL:
        return max(peak, high)
    return min(peak, low)


def _trail_fill(side: Side, kind: str, step: float, peak: float, open_: float, high: float, low: float) -> Optional[float]:
    long_exit = side == Side.SELL
    stop = _trail_level(kind, peak, step, long_exit=long_exit)
    if long_exit:
        if open_ <= stop:
            return open_
        if low <= stop:
            return stop
        tightened = _trail_level(kind, max(peak, high), step, long_exit=True)
        if tightened > stop and low <= tightened:
            return tightened
        return None
    if open_ >= stop:
        return open_
    if high >= stop:
        return stop
    tightened = _trail_level(kind, min(peak, low), step, long_exit=False)
    if tightened < stop and high >= tightened:
        return tightened
    return None


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
