"""Shared domain types."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Optional


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP_LOSS"
    STOP_LIMIT = "STOP_LOSS_LIMIT"


class OrderStatus(str, Enum):
    NEW = "NEW"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    REJECTED = "REJECTED"
    PARTIAL = "PARTIAL"


class TimeInForce(str, Enum):
    DAY = "DAY"
    GTC = "GTC"


@dataclass(frozen=True)
class Bar:
    symbol: str
    time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

    @property
    def session(self) -> date:
        return self.time.date()


@dataclass
class Order:
    client_order_id: str
    symbol: str
    side: Side
    quantity: float
    order_type: OrderType
    time_in_force: TimeInForce = TimeInForce.DAY
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    strategy: str = ""
    status: OrderStatus = OrderStatus.NEW
    filled_quantity: float = 0.0
    avg_fill_price: Optional[float] = None
    submitted_at: Optional[datetime] = None
    note: str = ""


@dataclass
class Position:
    symbol: str
    quantity: float
    avg_price: float
    strategy: str = ""
    stop_price: Optional[float] = None
    take_profit: Optional[float] = None
    opened_at: Optional[datetime] = None
    opened_on: Optional[date] = None
    bars_held: int = 0
    max_hold_bars: Optional[int] = None
    holds_overnight: bool = True
    peak_price: float = 0.0
    sector: str = ""

    def market_value(self, price: float) -> float:
        return self.quantity * price

    def unrealized(self, price: float) -> float:
        return (price - self.avg_price) * self.quantity


@dataclass
class AccountSnapshot:
    equity: float
    cash: float
    buying_power: float
    account_type: str  # "cash" or "margin"
    positions: list[Position] = field(default_factory=list)
    open_orders: list[Order] = field(default_factory=list)


@dataclass
class Fill:
    client_order_id: str
    symbol: str
    side: Side
    quantity: float
    price: float
    fees: float
    time: datetime
    strategy: str = ""
    reason: str = ""
