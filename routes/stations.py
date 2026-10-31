import math
from collections import defaultdict
from functools import cache

from .models import Station

EARTH_RADIUS_MILES = 3958.8
MAX_MILES_FROM_ROUTE = 10
# Grid cell size in degrees. A cell is wider than MAX_MILES_FROM_ROUTE across the
# contiguous USA, so a station only needs to check its own cell and the 8 around it.
CELL_DEGREES = 0.5


def haversine_miles(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(math.radians, (lat1, lon1, lat2, lon2))
    a = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS_MILES * math.asin(math.sqrt(a))


@cache
def all_stations():
    """Loaded once per process so requests don't query the database."""
    return list(Station.objects.values("id", "name", "address", "city", "state", "price", "lat", "lon"))


def thin_route(coordinates, step_miles=1.0):
    """Keep about one route point per step_miles, as (lat, lon, miles from start)."""
    points = []
    miles = 0.0
    previous = None
    for lon, lat in coordinates:
        if previous:
            miles += haversine_miles(previous[0], previous[1], lat, lon)
        if not points or miles - points[-1][2] >= step_miles:
            points.append((lat, lon, miles))
        previous = (lat, lon)
    if previous and points[-1][:2] != previous:
        points.append((previous[0], previous[1], miles))
    return points


def grid_cell(lat, lon):
    return math.floor(lat / CELL_DEGREES), math.floor(lon / CELL_DEGREES)


def stations_along_route(route_points):
    """Stations within MAX_MILES_FROM_ROUTE of the thinned route, sorted by miles from start."""
    grid = defaultdict(list)
    for point in route_points:
        grid[grid_cell(point[0], point[1])].append(point)

    found = []
    for station in all_stations():
        row, col = grid_cell(station["lat"], station["lon"])
        closest = None
        for nearby_row in (row - 1, row, row + 1):
            for nearby_col in (col - 1, col, col + 1):
                for lat, lon, miles in grid.get((nearby_row, nearby_col), ()):
                    distance = haversine_miles(station["lat"], station["lon"], lat, lon)
                    if distance <= MAX_MILES_FROM_ROUTE and (closest is None or distance < closest[0]):
                        closest = (distance, miles)
        if closest:
            found.append({**station, "miles_from_start": closest[1]})

    # Cheapest first when several stations share a spot (same city center).
    found.sort(key=lambda station: (station["miles_from_start"], station["price"]))
    return found
