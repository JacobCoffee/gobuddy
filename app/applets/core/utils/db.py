"""Database utils."""

from decimal import Decimal
from sqlite3 import IntegrityError

from structlog import get_logger

from app.applets.core.db import get_db_connection
from app.applets.core.schemas import Course, Player

logger = get_logger(__name__)


def get_cached_courses() -> list[Course]:
    """Retrieve all cached courses from the database.

    Returns:
        A list of courses.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, latitude, longitude, city, access FROM courses")
        return [
            Course(
                id=row[0], name=row[1], lat=Decimal(str(row[2])), lon=Decimal(str(row[3])), city=row[4], access=row[5]
            )
            for row in cursor.fetchall()
        ]


def add_course(course: Course) -> None:
    """Add a course to the database.

    Args:
        course: The course to add.
    """
    logger.debug("attempting to add course: %s", course)
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO courses (name, latitude, longitude, city, access) VALUES (?, ?, ?, ?, ?)",
                (course.name, float(course.lat), float(course.lon), course.city or None, course.access or None),
            )
            logger.debug("course added successfully")
        except IntegrityError:
            logger.exception("failed to add course")
            raise


def get_players() -> list[Player]:
    """Retrieve all players from the database.

    Returns:
        A list of players.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, address, latitude, longitude FROM players")
        return [
            Player(
                id=row[0],
                name=row[1],
                address=row[2],
                coord=(Decimal(str(row[3])), Decimal(str(row[4]))) if row[3] and row[4] else None,
            )
            for row in cursor.fetchall()
        ]


def add_player(player: Player) -> None:
    """Add a player to the database.

    Args:
        player: The player to add.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO players (name, address, latitude, longitude) VALUES (?, ?, ?, ?)",
            (
                player.name,
                player.address,
                float(player.coord[0]) if player.coord else None,
                float(player.coord[1]) if player.coord else None,
            ),
        )
