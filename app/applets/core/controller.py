"""Core controller."""

from typing import Final

from litestar import Controller, Request, get, post
from litestar.response import Template

from app.applets.core.schemas import Course, Player
from app.applets.core.utils.db import get_cached_courses
from app.applets.core.utils.geo import find_best_courses, find_golf_courses
from app.applets.core.utils.players import (
    calculate_center_coordinates,
    calculate_player_distances,
    extract_players_from_form,
    get_cached_players,
)

MINIMUM_PLAYERS: Final[int] = 2


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

    @get("/players")
    async def list_players(self) -> list[Player]:
        """List all players from the database.

        Returns:
            A Template response containing the list of players.
        """
        return get_cached_players()

    @get("/courses")
    async def list_courses(self) -> list[Course]:
        """List all cached courses.

        Returns:
            A JSON response containing the list of courses.
        """
        return get_cached_courses()
