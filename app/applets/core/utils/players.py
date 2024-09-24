"""Player utils."""

from itertools import combinations
from typing import Final

from geopy.distance import geodesic
from structlog import get_logger

from app.applets.core.db import get_db_connection
from app.applets.core.schemas import Player
from app.applets.core.utils.geo import geocode_address

MINIMUM_PLAYERS: Final[int] = 2

logger = get_logger(__name__)


def extract_players_from_form(form_data: dict[str, str]) -> list[Player]:
    """Extract players from form data.

    Args:
        form_data: The form data.

    Returns:
        A list of players.
    """
    player_keys = [key for key in form_data if key.startswith("name")]
    num_players = len(player_keys)
    players = []

    for i in range(1, num_players + 1):
        player_id = form_data.get(f"id{i}")
        name = form_data.get(f"name{i}")
        address = form_data.get(f"address{i}")

        if not name or not address:
            continue

        player = fetch_or_add_player(player_id, name, address)
        players.append(player)

    return players


def fetch_or_add_player(player_id: str | None, name: str, address: str) -> Player:
    """Fetch or add a player to the database.

    Args:
        player_id: The player ID.
        name: The player name.
        address: The player address.

    Returns:
        The player.
    """
    if player_id:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, address, latitude, longitude FROM players WHERE id = ?", (player_id,))
            if result := cursor.fetchone():
                return Player(
                    id=result[0],
                    name=result[1],
                    address=result[2],
                    coord=(result[3], result[4]) if result[3] is not None and result[4] is not None else None,
                )
    return add_player(name, address)


def calculate_center_coordinates(user_coords: list[tuple[float, float]]) -> tuple[float, float]:
    """Calculate the center coordinates of all player coordinates.

    Args:
        user_coords: A list of user coordinates.

    Returns:
        The center coordinates.
    """
    return (
        sum(coord[0] for coord in user_coords) / len(user_coords),
        sum(coord[1] for coord in user_coords) / len(user_coords),
    )


def add_player(name: str, address: str) -> Player:
    """Add a new player or retrieve existing one."""
    # Check if player exists
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, address, latitude, longitude FROM players WHERE address = ?", (address,))
        if result := cursor.fetchone():
            logger.info("Player with address %s already exists", address)
            return Player(
                id=result[0],
                name=result[1],
                address=result[2],
                coord=(result[3], result[4]) if result[3] and result[4] else None,
            )

        coord = geocode_address(address)

        cursor.execute(
            "INSERT INTO players (name, address, latitude, longitude) VALUES (?, ?, ?, ?)",
            (name, address, coord[0] if coord else None, coord[1] if coord else None),
        )
        player_id = cursor.lastrowid
        return Player(id=player_id, name=name, address=address, coord=coord)


def get_cached_players() -> list[Player]:
    """Retrieve all cached players from the database."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, address, latitude, longitude FROM players")
        return [
            Player(
                id=row[0],
                name=row[1],
                address=row[2],
                coord=(row[3], row[4]) if row[3] and row[4] else None,
            )
            for row in cursor.fetchall()
        ]


def calculate_total_distance(course_coord: tuple[float, float], user_coords: list[tuple[float, float]]) -> float:
    """Calculate the total distance from a golf course to a list of user coordinates.

    Args:
        course_coord: A tuple containing the latitude and longitude of the golf course.
        user_coords: A list of tuples containing the latitude and longitude of each user.

    Returns:
        The total distance in miles from the golf course to all user coordinates
    """
    return sum(geodesic(course_coord, user_coord).miles for user_coord in user_coords)


def calculate_player_distances(
    user_coords: list[tuple[float, float]], names: list[str]
) -> list[dict[str, str | float]]:
    """Calculate the distances between all pairs of players.

    Args:
        user_coords: A list of tuples containing the latitude and longitude of each user.
        names: A list of names corresponding to each user.

    Returns:
        A list of dictionaries containing the names of the players and the distance between them.
    """
    distances = []
    for (i, coord1), (j, coord2) in combinations(enumerate(user_coords), 2):
        distance = geodesic(coord1, coord2).miles
        distances.append({"players": f"{names[i]} and {names[j]}", "distance": distance})
    return distances
