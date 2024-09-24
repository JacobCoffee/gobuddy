"""Structures for the core applets."""

from typing import Any

import msgspec


class Course(msgspec.Struct):
    """Represents a golf course."""

    name: str
    city: str
    lat: float
    lon: float
    access: str
    distances: dict[str, Any] = msgspec.field(default_factory=dict)
    total_distance: float = 0.0


class Player(msgspec.Struct):
    """Represents a player."""

    name: str
    address: str
    id: int | None = None
    coord: tuple[float, float] | None = None
