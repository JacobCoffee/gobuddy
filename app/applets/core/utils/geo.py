"""Golf utilities."""

import pickle
from decimal import Decimal
from typing import Any

import overpy
from geopy.distance import geodesic
from geopy.exc import GeocoderQuotaExceeded, GeocoderTimedOut
from geopy.geocoders import Nominatim
from structlog import get_logger

from app.applets.core.db import get_db_connection
from app.applets.core.schemas import Course
from app.applets.core.utils.db import add_course

logger = get_logger(__name__)
geolocator = Nominatim(user_agent="gobuddy", timeout=10)


def geocode_address(address: str) -> tuple[float, float] | None:
    """Geocode a single address and cache the result.

    Args:
        address: The address to geocode.

    Returns:
        A tuple containing the latitude and longitude of the address, or None if not found.
    """
    if address:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT latitude, longitude FROM geocode_cache WHERE address = ?", (address,))
            if result := cursor.fetchone():
                logger.info("CACHED: using cache for %s", address)
                return result[0], result[1]

        try:
            logger.warning("UNCACHED: geocoding %s", address)
            if location := geolocator.geocode(address):
                coord = (location.latitude, location.longitude)
                with get_db_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "INSERT INTO geocode_cache (address, latitude, longitude) VALUES (?, ?, ?)",
                        (address, location.latitude, location.longitude),
                    )
                return coord
        except GeocoderTimedOut:
            logger.exception("Geocoding timed out for %s", address)
    return None


# -- Courses


def find_golf_courses(center_coord: tuple[float, float], radius: int = 160934) -> list[Course]:
    """Find golf courses within a given radius of a center coordinate.

    Args:
        center_coord: A tuple containing the latitude and longitude of the center coordinate.
        radius: The radius in meters around the center coordinate to search for golf courses.

    Returns:
        A list of dictionaries containing information about each golf course.
    """
    cache_key = f"{round(center_coord[0], 5)}, {round(center_coord[1], 5)}, {radius}"

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT courses FROM golf_courses_cache WHERE cache_key = ?", (cache_key,))
        if result := cursor.fetchone():
            return pickle.loads(result[0])  # noqa: S301

    elements = query_overpass_api(center_coord, radius)
    courses = []

    max_additional_queries = 10
    query_count = {"count": 0}

    max_nearby_queries = 10
    nearby_query_count = [0]

    for element in elements:
        if coords := get_course_coordinates(element):
            lat, lon = coords
            name = get_course_name(element.tags, lat, lon, max_nearby_queries, nearby_query_count)
            city = get_city_name(lat, lon, element.tags, max_additional_queries, query_count)
            course = Course(
                name=name,
                lat=Decimal(str(lat)),
                lon=Decimal(str(lon)),
                city=city,
                access=element.tags.get("access", "unknown"),
            )
            courses.append(course)
            add_course(course)

    logger.info(
        "found %d golf courses within %d miles of %s",
        len(courses),
        radius / 1609.34,
        center_coord,
    )

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO golf_courses_cache (cache_key, courses) VALUES (?, ?)", (cache_key, pickle.dumps(courses))
        )

    return courses


def query_overpass_api(center_coord: tuple[float, float], radius: int) -> list[overpy.Element]:
    """Query the Overpass API to retrieve golf courses.

    Args:
        center_coord: A tuple containing the latitude and longitude of the center coordinate.
        radius: The radius in meters around the center coordinate to search for golf courses.

    Returns:
        A list of Overpass API elements representing golf courses.
    """
    api = overpy.Overpass()
    lat, lon = center_coord
    query = f"""
    (
      node["leisure"="golf_course"](around:{radius},{lat},{lon});
      way["leisure"="golf_course"](around:{radius},{lat},{lon});
      relation["leisure"="golf_course"](around:{radius},{lat},{lon});
    );
    out center tags;
    """
    result = api.query(query)
    return result.nodes + result.ways + result.relations


def get_course_coordinates(element: overpy.Element) -> tuple[Any, Any] | None:
    """Extract latitude and longitude from an Overpass API element.

    Args:
        element: An Overpass API element

    Returns:
        A tuple containing the latitude and longitude of the element.
    """
    if hasattr(element, "lat") and hasattr(element, "lon"):
        return element.lat, element.lon
    if hasattr(element, "center_lat") and hasattr(element, "center_lon"):
        return element.center_lat, element.center_lon
    return None


def query_enclosing_city(lat: float, lon: float) -> str:
    """Query Overpass API to find the smallest enclosing administrative area.

    Args:
        lat: Latitude of the point.
        lon: Longitude of the point.

    Returns:
        The name of the enclosing city or town, or "Unknown City" if not found.
    """
    api = overpy.Overpass()
    query = f"""
    (
      relation["boundary"="administrative"]["admin_level"~"^(6|7|8)$"](around:10, {lat}, {lon});
    );
    out body;
    """
    try:
        result = api.query(query)
        logger.debug("overpass query returned %d relations", len(result.relations))
        relations = sorted(result.relations, key=lambda x: int(x.tags.get("admin_level", 0)), reverse=True)
        for relation in relations:
            admin_level = relation.tags.get("admin_level")
            name = relation.tags.get("name")
            if name and admin_level in ["6", "7", "8"]:
                return name
    except Exception:
        logger.exception("overpass query failed")
        return "Unknown City"
    return "Unknown City"


def get_city_name(
    lat: float, lon: float, element_tags: dict, max_additional_queries: int, query_count: dict[str, int]
) -> str:
    """Get the city name from element tags or by querying nearby features.

    Args:
        lat: Latitude of the golf course.
        lon: Longitude of the golf course.
        element_tags: A dictionary of element tags.
        max_additional_queries: Maximum number of additional queries allowed.
        query_count: A dictionary to keep track of the number of additional queries.

    Returns:
        The city name if found, otherwise "Unknown City".
    """
    city_tags = [
        "addr:city",
        "addr:town",
        "addr:village",
        "addr:hamlet",
        "is_in:city",
        "is_in:town",
        "is_in:village",
        "addr:county",
        "addr:state",
    ]

    for tag in city_tags:
        city = element_tags.get(tag)
        if city:
            return city

    coord_key = f"{round(lat, 5)}, {round(lon, 5)}"

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT city FROM reverse_geocode_cache WHERE lat_lon = ?", (coord_key,))
        if result := cursor.fetchone():
            return result[0]

    if query_count["count"] >= max_additional_queries:
        return "Unknown City"

    query_count["count"] += 1

    city = query_enclosing_city(lat, lon)

    if city == "Unknown City":
        city = reverse_geocode_city(lat, lon)

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO reverse_geocode_cache (lat_lon, city) VALUES (?, ?)", (coord_key, city))

    return city


def reverse_geocode_city(lat: float, lon: float) -> str:
    """Perform reverse geocoding to get the city name.

    Args:
        lat: The latitude of the coordinate.
        lon: The longitude of the coordinate.

    Returns:
        The city name corresponding to the coordinate.
    """
    coord_key = f"{round(lat, 5)}, {round(lon, 5)}"
    # Check the database cache
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT city FROM reverse_geocode_cache WHERE lat_lon = ?", (coord_key,))
        if result := cursor.fetchone():
            return result[0]

    try:
        location = geolocator.reverse((lat, lon), exactly_one=True)
        if location and "address" in location.raw:
            address = location.raw["address"]
            city = (
                address.get("city")
                or address.get("town")
                or address.get("village")
                or address.get("hamlet")
                or address.get("county")
                or "Unknown City"
            )
        else:
            city = "Unknown City"
    except (GeocoderTimedOut, GeocoderQuotaExceeded):
        logger.exception("Reverse geocoding failed for %s, %s", lat, lon)
        city = "Unknown City"

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO reverse_geocode_cache (lat_lon, city) VALUES (?, ?)", (coord_key, city))

    return city


def get_name_from_nearby_features(lat: float, lon: float) -> str | None:
    """Query nearby features to derive a name for the golf course.

    Args:
        lat: Latitude of the course.
        lon: Longitude of the course.

    Returns:
        A name derived from nearby features, or None if no suitable name is found.
    """
    coord_key = f"{round(lat, 5)}, {round(lon, 5)}"

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM nearby_features_cache WHERE lat_lon = ?", (coord_key,))
        if result := cursor.fetchone():
            return result[0]

    query = f"""
        (
          node(around:500,{lat},{lon})[place~"locality|suburb|neighbourhood|hamlet"][name];
          way(around:500,{lat},{lon})[place~"locality|suburb|neighbourhood|hamlet"][name];
          relation(around:500,{lat},{lon})[place~"locality|suburb|neighbourhood|hamlet"][name];
        );
        out tags;
        """
    api = overpy.Overpass()

    try:
        nearby_name = extract_nearby_feature_name(api, query)
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO nearby_features_cache (lat_lon, name) VALUES (?, ?)", (coord_key, nearby_name)
            )
    except Exception:
        logger.exception("overpass query failed")
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO nearby_features_cache (lat_lon, name) VALUES (?, ?)", (coord_key, None)
            )
        return None
    return nearby_name


def extract_nearby_feature_name(api: overpy.Overpass, query: str) -> str | None:
    """Extract the name of a nearby feature from an Overpass API query.

    Args:
        api: An instance of the Overpass API.
        query: The query to execute.

    Returns:
        The name of the nearby feature, or None if no name is found.
    """
    result = api.query(query)
    names = set()
    for element in result.nodes + result.ways + result.relations:
        if name := element.tags.get("name"):
            names.add(name)
    return names.pop() if names else None


def get_course_name(
    element_tags: dict, lat: float, lon: float, max_nearby_queries: int, nearby_query_count: list[int]
) -> str:
    """Get the course name from element tags or nearby features.

    Args:
        element_tags: A dictionary of element tags.
        lat: Latitude of the course.
        lon: Longitude of the course.
        max_nearby_queries: Maximum number of nearby queries allowed.
        nearby_query_count: A list with a single integer element to keep track of the number of queries made.

    Returns:
        The name of the golf course.
    """
    if name := element_tags.get("name"):
        return name

    alternative_tags = [
        "official_name",
        "alt_name",
        "short_name",
        "operator",
        "brand",
        "description",
    ]
    for tag in alternative_tags:
        if name := element_tags.get(tag):
            return name

    if nearby_query_count[0] < max_nearby_queries:
        nearby_name = get_name_from_nearby_features(lat, lon)
        nearby_query_count[0] += 1
        if nearby_name:
            return nearby_name

    leisure = element_tags.get("leisure", "Unknown")
    return f"{leisure.capitalize()}"


def find_best_courses(
    courses: list[Course], user_coords: list[tuple[float, float]], player_names: list[str]
) -> list[Course]:
    """Find the best golf courses based on total distance to all user coordinates.

    Args:
        courses: A list of dictionaries containing information about each golf course.
        user_coords: A list of tuples containing the latitude and longitude of each user.
        player_names: A list of names corresponding to each user.

    Returns:
        A list of dictionaries containing the name, latitude, and longitude of each golf course,
        along with the total distance to all user coordinates and the distance and travel time
        to each user.
    """
    for course in courses:
        course_coord = (course.lat, course.lon)
        total_distance = 0.0
        course.distances = {}
        for coord, name in zip(user_coords, player_names, strict=False):
            distance = geodesic(course_coord, coord).miles
            travel_time = distance / 50 * 60  # Assuming average speed of 50 mph
            course.distances[name] = {
                "distance": distance,
                "travel_time": int(travel_time),
            }
            total_distance += distance
        course.total_distance = total_distance
    courses.sort(key=lambda x: x.total_distance)
    return courses
