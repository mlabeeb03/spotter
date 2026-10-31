import requests

from .places import PlaceError

OSRM_URL = "https://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}"
METERS_PER_MILE = 1609.344
# OSRM moves each point to the nearest road; farther than this means it isn't near a road.
MAX_MILES_TO_ROAD = 5


class RoutingError(Exception):
    pass


def get_route(start, finish):
    """One OSRM call. Returns (distance in miles, list of [lon, lat] points)."""
    url = OSRM_URL.format(lon1=start["lon"], lat1=start["lat"], lon2=finish["lon"], lat2=finish["lat"])
    try:
        response = requests.get(url, params={"overview": "full", "geometries": "geojson"}, timeout=20)
        data = response.json()
    except (requests.RequestException, ValueError) as error:
        raise RoutingError(f"Routing service is unavailable: {error}") from error

    if data.get("code") != "Ok" or not data.get("routes"):
        raise RoutingError(f"Routing service could not find a route: {data.get('message', data.get('code'))}")

    for place, waypoint in zip((start, finish), data["waypoints"]):
        miles_to_road = waypoint["distance"] / METERS_PER_MILE
        if miles_to_road > MAX_MILES_TO_ROAD:
            raise PlaceError(f'"{place["name"]}" is {miles_to_road:.0f} miles from the nearest road.')

    route = data["routes"][0]
    return route["distance"] / METERS_PER_MILE, route["geometry"]["coordinates"]
