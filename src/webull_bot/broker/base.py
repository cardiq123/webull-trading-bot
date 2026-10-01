"""Broker interface shared by paper trading and Webull."""

from __future__ import annotations

from abc import ABC, abstractmethod

from webull_bot.models import AccountSnapshot, Fill, Order, Position


class Broker(ABC):
    name: str

    @abstractmethod
    def connect(self) -> None:
        """Open sessions or load state. Must not place orders."""

    @abstractmethod
    def snapshot(self) -> AccountSnapshot:
        ...

    @abstractmethod
    def positions(self) -> list[Position]:
        ...

    @abstractmethod
    def open_orders(self) -> list[Order]:
        ...

    @abstractmethod
    def place_order(self, order: Order) -> Order:
        ...

    @abstractmethod
    def cancel_order(self, client_order_id: str) -> None:
        ...

    def cancel_all(self) -> int:
        count = 0
        for order in self.open_orders():
            self.cancel_order(order.client_order_id)
            count += 1
        return count

    @abstractmethod
    def flatten(self) -> list[Fill]:
        """Cancel resting orders and close positions. Returns fills if the
        adapter can fill immediately (paper). A live adapter submits market
        exits and returns an empty fill list until the broker reports them.
        """
