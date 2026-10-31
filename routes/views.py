from urllib.parse import urlencode

from django.core.cache import cache
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_GET

from .fuel import MAX_RANGE_MILES, MILES_PER_GALLON, FuelPlanError, plan_fuel_stops, stops_summary
from .osrm import RoutingError, get_route
from .places import PlaceError, find_place
from .stations import stations_along_route, thin_route


class TripError(Exception):
    def __init__(self, message, status):
        super().__init__(message)
        self.status = status


def plan_trip(start_text, finish_text):
    try:
        start = find_place(start_text)
        finish = find_place(finish_text)
    except PlaceError as error:
        raise TripError(str(error), 400)

    # Keyed by coordinates so "Dallas, TX" and "dallas,tx" share one entry.
    cache_key = f"trip:{start['lat']},{start['lon']}:{finish['lat']},{finish['lon']}"
    trip = cache.get(cache_key)
    if trip:
        return trip

    try:
        distance_miles, coordinates = get_route(start, finish)
    except PlaceError as error:
        raise TripError(str(error), 400)
    except RoutingError as error:
        raise TripError(str(error), 502)

    route_points = thin_route(coordinates)
    try:
        stops = plan_fuel_stops(stations_along_route(route_points), distance_miles)
    except FuelPlanError as error:
        raise TripError(str(error), 422)

    fuel_stops, total_gallons, total_cost = stops_summary(stops)
    trip = {
        "start": start,
        "finish": finish,
        "distance_miles": round(distance_miles, 1),
        "starting_tank_gallons": MAX_RANGE_MILES / MILES_PER_GALLON,
        "fuel_used_gallons": round(distance_miles / MILES_PER_GALLON, 2),
        "fuel_stops": fuel_stops,
        "total_gallons": total_gallons,
        "total_fuel_cost": total_cost,
        "route": {
            "type": "LineString",
            "coordinates": [[round(lon, 5), round(lat, 5)] for lat, lon, _ in route_points],
        },
    }
    cache.set(cache_key, trip)
    return trip


@require_GET
def route_api(request):
    start, finish = request.GET.get("start"), request.GET.get("finish")
    if not start or not finish:
        return JsonResponse({"error": 'Both "start" and "finish" are required.'}, status=400)
    try:
        trip = plan_trip(start, finish)
    except TripError as error:
        return JsonResponse({"error": str(error)}, status=error.status)

    data = dict(trip)
    route = data.pop("route")
    map_url = request.build_absolute_uri(reverse("route-map") + "?" + urlencode({"start": start, "finish": finish}))
    return JsonResponse({**data, "map_url": map_url, "route": route})


@require_GET
def route_map(request):
    start, finish = request.GET.get("start"), request.GET.get("finish")
    if not start or not finish:
        return HttpResponse('Both "start" and "finish" are required.', status=400, content_type="text/plain")
    try:
        trip = plan_trip(start, finish)
    except TripError as error:
        return HttpResponse(str(error), status=error.status, content_type="text/plain")
    return render(request, "routes/map.html", {"trip": trip})
