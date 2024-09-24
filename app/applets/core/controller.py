"""Core controller."""

from typing import Final

from litestar import Controller, Request, get, post
from litestar.response import Template

from app.applets.core.db import get_db_connection
from app.applets.core.schemas import Player
from app.applets.core.utils import (
    add_player,
    calculate_player_distances,
    find_best_courses,
    find_golf_courses,
    get_cached_players,
)

MINIMUM_PLAYERS: Final[int] = 2


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
            cursor.execute(
                "SELECT id, name, address, latitude, longitude FROM players WHERE id = ?",
                (player_id,)
            )
            if result := cursor.fetchone():
                return Player(
                    id=result[0],
                    name=result[1],
                    address=result[2],
                    coord=(result[3], result[4]) if result[3] is not None and result[4] is not None else None,
                )
    return add_player(name, address)


def calculate_center_coordinates(user_coords: list[tuple[float, float]]) -> tuple[float, float]:
    """Calculate the center coordinates of all user coordinates.

    Args:
        user_coords: A list of user coordinates.

    Returns:
        The center coordinates.
    """
    return (
        sum(coord[0] for coord in user_coords) / len(user_coords),
        sum(coord[1] for coord in user_coords) / len(user_coords),
    )


class CoreController(Controller):
    """Houses all routes for core endpoints."""

    path = "/"  # Base path for the controller

    @get("/")
    async def index(self) -> Template:
        """Render the index page.

        Returns:
            A Template response containing the index page.
        """
        players = get_cached_players()
        return Template(
            template_name="index.html",
            context={"players": players},
        )

    @post("/process")
    async def process(self, request: Request) -> Template:
        """Process the form data and render the results page.

        Args:
            request: The incoming HTTP request.

        Returns:
            A Template response containing the results page.
        """
        form_data = await request.form()
        players = extract_players_from_form(form_data)

        if not players:
            return Template(
                template_name="error.html",
                context={"message": "Unable to geocode any of the provided addresses."},
            )

        user_coords = [player.coord for player in players if player.coord is not None]
        player_names = [player.name for player in players]

        center_coord = calculate_center_coordinates(user_coords)

        courses = find_golf_courses(center_coord)
        best_courses = find_best_courses(courses, user_coords, player_names)
        player_distances = calculate_player_distances(user_coords, player_names)

        return Template(
            template_name="results.html",
            context={
                "players": players,
                "best_courses": best_courses,
                "player_distances": player_distances,
            },
        )
