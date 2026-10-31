from unittest import mock

from django.core.cache import cache
from django.test import TestCase

from .fuel import FuelPlanError, plan_fuel_stops, stops_summary
from .models import City, Station
from .places import PlaceError, find_place
from .stations import all_stations


def station(name, miles, price):
    return {
        "name": name, "address": "", "city": "", "state": "KS",
        "lat": 39.0, "lon": -100.0, "miles_from_start": miles, "price": price,
    }


def bought(stops):
    return [(stop["name"], round(miles)) for stop, miles in stops]


class PlanFuelStopsTests(TestCase):
    def test_short_trip_needs_no_stop(self):
        stations = [station("A", 200, 3.0)]
        self.assertEqual(plan_fuel_stops(stations, 450), [])
        self.assertEqual(stops_summary([]), ([], 0.0, 0.0))
        self.assertIsInstance(stops_summary([])[2], float)

    def test_buys_only_what_is_needed_to_finish(self):
        stations = [station("A", 300, 3.0)]
        # At mile 300 there are 200 miles left in the tank, so 250 more cover the last 450.
        self.assertEqual(bought(plan_fuel_stops(stations, 750)), [("A", 250)])

    def test_picks_the_cheaper_station(self):
        stations = [station("Pricey", 300, 4.0), station("Cheap", 450, 3.0)]
        # The starting tank reaches Cheap with 50 miles left; nothing is bought at Pricey.
        self.assertEqual(bought(plan_fuel_stops(stations, 800)), [("Cheap", 300)])

    def test_tie_goes_to_the_farthest_station(self):
        stations = [station("Near", 200, 3.0), station("Far", 400, 3.0)]
        self.assertEqual(bought(plan_fuel_stops(stations, 700)), [("Far", 200)])

    def test_skips_a_slightly_cheaper_station_for_the_cheapest(self):
        stations = [station("X", 500, 3.5), station("Y", 520, 3.49), station("Z", 900, 3.0)]
        # From X, go straight to Z instead of stopping at Y to save a cent.
        self.assertEqual(bought(plan_fuel_stops(stations, 1300)), [("X", 400), ("Z", 400)])

    def test_buys_a_little_then_fills_at_the_cheaper_station(self):
        stations = [
            station("A", 100, 3.5),
            station("B", 450, 4.0),
            station("C", 550, 3.0),
            station("D", 1000, 3.8),
        ]
        stops = plan_fuel_stops(stations, 1400)
        # A: only enough to reach the cheaper C. C: fill up. D: the rest to the finish.
        self.assertEqual(bought(stops), [("A", 50), ("C", 500), ("D", 350)])

        fuel_stops, total_gallons, total_cost = stops_summary(stops)
        self.assertEqual(total_gallons, 90.0)
        self.assertEqual(total_cost, round(5 * 3.5 + 50 * 3.0 + 35 * 3.8, 2))
        self.assertEqual(total_cost, sum(stop["cost"] for stop in fuel_stops))

    def test_gap_too_big_raises(self):
        stations = [station("A", 300, 3.0), station("B", 900, 3.0)]
        with self.assertRaises(FuelPlanError):
            plan_fuel_stops(stations, 1200)


class PlaceTests(TestCase):
    def test_city_name_must_match_exactly(self):
        City.objects.create(name="St. Louis", state="MO", lat=38.6, lon=-90.2)
        self.assertEqual(find_place("st. louis, mo")["name"], "St. Louis, MO")
        with self.assertRaises(PlaceError):
            find_place("Saint Louis, MO")


class RouteApiTests(TestCase):
    def setUp(self):
        all_stations.cache_clear()
        cache.clear()
        City.objects.create(name="Startville", state="KS", lat=39.0, lon=-100.0)
        City.objects.create(name="Endtown", state="KS", lat=39.0, lon=-85.0)
        Station.objects.create(
            id=1, name="Midway Fuel", address="I-70 Exit 1", city="Midway", state="KS",
            price=3.25, lat=39.0, lon=-92.0,
        )

    def tearDown(self):
        all_stations.cache_clear()

    @mock.patch("routes.views.get_route")
    def test_route_returns_stops_and_cost(self, get_route):
        # A straight line along latitude 39, about 800 miles long.
        line = [[-100.0 + step * 0.1, 39.0] for step in range(151)]
        get_route.return_value = (800.0, line)

        response = self.client.get("/api/route/", {"start": "Startville, KS", "finish": "39.0,-85.0"})

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["start"]["name"], "Startville, KS")
        self.assertEqual([stop["name"] for stop in data["fuel_stops"]], ["Midway Fuel"])
        self.assertEqual(data["total_fuel_cost"], data["fuel_stops"][0]["cost"])
        self.assertEqual(data["starting_tank_gallons"], 50)
        self.assertEqual(data["fuel_used_gallons"], 80)
        self.assertEqual(data["route"]["type"], "LineString")
        self.assertIn("/api/route/map/?", data["map_url"])

        # The map page reuses the cached trip instead of routing again.
        map_response = self.client.get("/api/route/map/", {"start": "Startville, KS", "finish": "39.0,-85.0"})
        self.assertContains(map_response, "Midway Fuel")
        get_route.assert_called_once()

    @mock.patch("routes.views.get_route")
    def test_no_station_in_range_is_a_422(self, get_route):
        Station.objects.all().delete()
        get_route.return_value = (800.0, [[-100.0 + step * 0.1, 39.0] for step in range(151)])

        response = self.client.get("/api/route/", {"start": "Startville, KS", "finish": "Endtown, KS"})

        self.assertEqual(response.status_code, 422)
        self.assertIn("No fuel station", response.json()["error"])

    def test_unknown_place_is_a_400(self):
        response = self.client.get("/api/route/", {"start": "Nowhere, KS", "finish": "Endtown, KS"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("Could not find", response.json()["error"])

    def test_place_outside_usa_is_a_400(self):
        response = self.client.get("/api/route/", {"start": "51.5,-0.1", "finish": "Endtown, KS"})
        self.assertEqual(response.status_code, 400)
