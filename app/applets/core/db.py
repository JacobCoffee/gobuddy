"""db."""

import sqlite3
from contextlib import contextmanager

from litestar.config.app import AppConfig

DATABASE_FILE = "cache.db"


@contextmanager
def get_db_connection() -> sqlite3.Connection:
    """Get a database connection.

    Yields:
        A database connection.
    """
    conn = sqlite3.connect(DATABASE_FILE)
    try:
        yield conn
    finally:
        conn.commit()
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
    return app_config
