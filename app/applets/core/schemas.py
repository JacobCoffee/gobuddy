"""Structures for the core applets."""
from decimal import Decimal
from typing import Any

import msgspec


class Course(msgspec.Struct):
    """Represents a golf course."""

    name: str
    lat: Decimal
    lon: Decimal
    distances: dict[str, Any] = msgspec.field(default_factory=dict)
    total_distance: float = 0.0
    city: str | None = None
    access: str | None = None
    id: int | None = None


class Player(msgspec.Struct):
    """Represents a player."""

    name: str
    address: str
    id: int | None = None
    coord: tuple[Decimal, Decimal] | None = None
