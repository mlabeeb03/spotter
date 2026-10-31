# Fuel Route API

Give it a start and finish in the USA. It returns the driving route, the cheapest places to buy fuel along the way, and the total fuel cost.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py load_data
python manage.py runserver
```

`load_data` prints how many stations it matched to a city. Run it with `-v 2` to list the ones it skipped.

To browse stations and cities in the admin, run `python manage.py createsuperuser` and open http://127.0.0.1:8000/admin/.

Run the tests with `python manage.py test routes`.

## Usage

`start` and `finish` can be `"City, ST"` or `"lat,lon"`.

```bash
curl "http://127.0.0.1:8000/api/route/?start=New%20York,%20NY&finish=Los%20Angeles,%20CA"
```

```json
{
  "start": {"name": "New York, NY", "lat": 40.662712, "lon": -73.938677},
  "finish": {"name": "Los Angeles, CA", "lat": 34.019394, "lon": -118.410825},
  "distance_miles": 2810.4,
  "starting_tank_gallons": 50.0,
  "fuel_used_gallons": 281.04,
  "fuel_stops": [
    {
      "name": "SHEETZ #639", "address": "I-80 Exit 223", "city": "Youngstown", "state": "OH",
      "price_per_gallon": 3.059, "lat": 41.099095, "lon": -80.645902,
      "miles_from_start": 395.5, "gallons": 36.32, "cost": 111.1
    }
  ],
  "total_gallons": 231.04,
  "total_fuel_cost": 700.78,
  "map_url": "http://127.0.0.1:8000/api/route/map/?start=New+York%2C+NY&finish=Los+Angeles%2C+CA",
  "route": {"type": "LineString", "coordinates": [[-73.93872, 40.6631], "..."]}
}
```

`total_gallons` is what was bought on the way. The rest of `fuel_used_gallons` came from the starting tank, so a short trip costs $0.

The first call for a trip depends on the public OSRM server (usually 1–3 s). Repeat calls come from the cache.

Open `map_url` in a browser to see the route and fuel stops on a map.

Errors come back as `{"error": "..."}`: 400 for a missing or unknown place (or one more than 5 miles from a road), 502 if the routing service fails, and 422 if a stretch of the route has no station within 500 miles.

## How it works

- **Places and stations.** The fuel price file has no coordinates. `load_data` loads the free US Census Gazetteer places file (city name, state, lat/lon) and puts each station at the center of its city. Stations sit along highways near those towns, so this is close enough for planning. Stations whose city isn't in the Census file are skipped. That includes the Canadian stations and some small New England towns.
- **Routing.** One call to the public OSRM server per trip. The returned route is thinned to about one point per mile. Results are cached in memory for an hour, so the map page and repeat requests don't call OSRM again.
- **Stations on the route.** A station counts if it is within 10 miles of the route. Its position on the route is the distance from the start to the closest route point.
- **Choosing stops.** From each stop, head for the cheapest station reachable on a full tank (the farthest one on a tie). If it is cheaper than the current station, buy just enough to reach it. Otherwise fill up, or buy only what's needed to finish. Each station sits at a city center, so saving a few cents on a nearer, slightly cheaper station isn't worth an extra stop.

## Assumptions

- The vehicle starts with a full tank (500 miles of range). That fuel is not counted in the cost.
- 10 miles per gallon and a 50 gallon tank.
- The small detour from the highway to a station isn't counted.
- If a station appears more than once in the price file, its lowest price is used.
- Only the contiguous USA is supported.
