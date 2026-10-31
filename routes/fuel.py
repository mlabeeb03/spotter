import math

MAX_RANGE_MILES = 500
MILES_PER_GALLON = 10


class FuelPlanError(Exception):
    pass


def plan_fuel_stops(stations, total_miles, max_range=MAX_RANGE_MILES):
    """
    Pick where to buy fuel and how much, starting with a full tank.

    `stations` must be sorted by "miles_from_start" and have a "price".
    Returns a list of (station, miles of fuel bought).
    """
    stops = []
    position = 0.0
    fuel = max_range  # measured in miles the tank can still drive
    price = math.inf  # the starting tank is already paid for
    index = -1  # -1 means we are at the start, not at a station

    while total_miles - position > fuel:
        reachable = []
        for next_index in range(index + 1, len(stations)):
            if stations[next_index]["miles_from_start"] - position > max_range:
                break
            reachable.append(next_index)

        # Cheapest reachable station; on a tie, the farthest one.
        target = None
        if reachable:
            target = min(reachable, key=lambda i: (stations[i]["price"], -stations[i]["miles_from_start"]))

        if target is not None and stations[target]["price"] < price:
            # Cheaper ahead: buy just enough to get there.
            needed = stations[target]["miles_from_start"] - position
        elif total_miles - position <= max_range:
            # Nothing cheaper and the finish is in range: buy only what's left.
            target = None
            needed = total_miles - position
        elif target is not None:
            # Nothing cheaper ahead: fill up.
            needed = max_range
        else:
            raise FuelPlanError(
                f"No fuel station within {max_range} miles after mile {position:.0f} of the route."
            )

        bought = needed - fuel
        if bought > 0:  # never true at the start, where the tank is full
            stops.append((stations[index], bought))
            fuel += bought

        if target is None:
            break
        fuel -= stations[target]["miles_from_start"] - position
        position = stations[target]["miles_from_start"]
        price = stations[target]["price"]
        index = target

    return stops


def stops_summary(stops, mpg=MILES_PER_GALLON):
    """Format stops for the API and add up gallons and cost."""
    fuel_stops = []
    for station, miles_of_fuel in stops:
        gallons = miles_of_fuel / mpg
        fuel_stops.append(
            {
                "name": station["name"],
                "address": station["address"],
                "city": station["city"],
                "state": station["state"],
                "price_per_gallon": round(station["price"], 3),
                "lat": station["lat"],
                "lon": station["lon"],
                "miles_from_start": round(station["miles_from_start"], 1),
                "gallons": round(gallons, 2),
                "cost": round(gallons * station["price"], 2),
            }
        )
    total_gallons = sum((miles_of_fuel for _, miles_of_fuel in stops), 0.0) / mpg
    total_cost = sum((stop["cost"] for stop in fuel_stops), 0.0)
    return fuel_stops, round(total_gallons, 2), round(total_cost, 2)
