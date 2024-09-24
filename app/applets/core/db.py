"""db."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Final

from litestar.config.app import AppConfig
from litestar.utils.module_loader import module_to_os_path

DEFAULT_MODULE_NAME = "gobuddy"
BASE_DIR: Final[Path] = module_to_os_path(DEFAULT_MODULE_NAME)

DATABASE_FILE = f"{BASE_DIR}/gobuddy.db"


@contextmanager
def get_db_connection() -> sqlite3.Connection:
    """Get a database connection.

    Yields:
        A database connection.
    """
    conn = sqlite3.connect(DATABASE_FILE)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def initialize_database(app_config: AppConfig) -> AppConfig:
    """Initialize the database.

    Called on app init by the Litestar constructor.

    Args:
        app_config: The app configuration.

    Returns:
        The app configuration.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS geocode_cache (
                address TEXT PRIMARY KEY,
                latitude REAL,
                longitude REAL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reverse_geocode_cache (
                lat_lon TEXT PRIMARY KEY,
                city TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS golf_courses_cache (
                cache_key TEXT PRIMARY KEY,
                courses BLOB
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS nearby_features_cache (
                lat_lon TEXT PRIMARY KEY,
                name TEXT
            )
        """)
        cursor.execute("""
                    CREATE TABLE IF NOT EXISTS players (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        address TEXT NOT NULL UNIQUE,
                        latitude REAL,
                        longitude REAL
                    )
                """)
        cursor.execute("""
                    CREATE TABLE IF NOT EXISTS courses (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        latitude REAL NOT NULL,
                        longitude REAL NOT NULL,
                        city TEXT,
                        access TEXT
                    )
                """)
    return app_config
