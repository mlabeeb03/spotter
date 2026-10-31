import re

from .models import City

# Rough box around the contiguous USA (the area OSRM can route and the fuel data covers).
US_MIN_LAT, US_MAX_LAT = 24.0, 50.0
US_MIN_LON, US_MAX_LON = -125.0, -66.0

LAT_LON = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$")


class PlaceError(Exception):
    pass


def in_usa(lat, lon):
    return US_MIN_LAT <= lat <= US_MAX_LAT and US_MIN_LON <= lon <= US_MAX_LON


def find_place(text):
    """Turn "City, ST" or "lat,lon" into {"name", "lat", "lon"}."""
    text = (text or "").strip()
    if not text:
        raise PlaceError("Location is empty.")

    match = LAT_LON.match(text)
    if match:
        lat, lon = float(match.group(1)), float(match.group(2))
        name = f"{lat},{lon}"
    else:
        city_name, _, state = text.rpartition(",")
        state = state.strip().upper()
        if not city_name.strip() or len(state) != 2:
            raise PlaceError(f'"{text}" should look like "City, ST" or "lat,lon".')
        city = City.objects.filter(state=state, name__iexact=city_name.strip()).first()
        if city is None:
            raise PlaceError(f'Could not find "{text}".')
        lat, lon, name = city.lat, city.lon, str(city)

    if not in_usa(lat, lon):
        raise PlaceError(f'"{text}" is outside the contiguous USA.')
    return {"name": name, "lat": lat, "lon": lon}
