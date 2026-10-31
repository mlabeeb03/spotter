import csv
import io
import re
import zipfile

import requests
from django.conf import settings
from django.core.management.base import BaseCommand

from routes.models import City, Station

GAZETTEER_URL = (
    "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/"
    "2026_Gazetteer/2026_Gaz_place_national.zip"
)
# Census place names end with a type, e.g. "Dallas city" or "Abanda CDP".
CENSUS_SUFFIX = re.compile(r"\s+(city|town|village|borough|CDP|municipality)$")
CANADIAN_PROVINCES = {"AB", "BC", "MB", "NB", "NL", "NS", "NT", "NU", "ON", "PE", "QC", "SK", "YT"}


class Command(BaseCommand):
    help = "Load US cities from the Census gazetteer and fuel stations from data/fuel-prices.csv."

    def handle(self, *args, **options):
        cities = self.load_cities()
        self.stdout.write(f"Loaded {len(cities)} cities.")
        self.load_stations(cities, show_missing=options["verbosity"] > 1)

    def load_cities(self):
        zip_path = settings.DATA_DIR / "gazetteer_places.zip"
        if not zip_path.exists():
            self.stdout.write("Downloading Census gazetteer...")
            response = requests.get(GAZETTEER_URL, timeout=60)
            response.raise_for_status()
            zip_path.write_bytes(response.content)

        with zipfile.ZipFile(zip_path) as archive:
            text = archive.read(archive.namelist()[0]).decode("utf-8")
        # Newer files are "|" separated, older ones use tabs.
        delimiter = "|" if "|" in text.splitlines()[0] else "\t"
        rows = csv.DictReader(io.StringIO(text), delimiter=delimiter)

        cities = {}
        for row in rows:
            row = {key.strip(): value.strip() for key, value in row.items()}
            name = CENSUS_SUFFIX.sub("", row["NAME"])
            city = City(name=name, state=row["USPS"], lat=float(row["INTPTLAT"]), lon=float(row["INTPTLONG"]))
            cities.setdefault((city.state, name), city)

        City.objects.all().delete()
        City.objects.bulk_create(cities.values(), batch_size=2000)
        return cities

    def load_stations(self, cities, show_missing):
        cheapest = {}
        with open(settings.DATA_DIR / "fuel-prices.csv", newline="") as file:
            for row in csv.DictReader(file):
                station_id = int(row["OPIS Truckstop ID"])
                price = float(row["Retail Price"])
                if station_id not in cheapest or price < cheapest[station_id]["price"]:
                    cheapest[station_id] = {
                        "id": station_id,
                        "name": row["Truckstop Name"].strip(),
                        "address": row["Address"].strip(),
                        "city": row["City"].strip(),
                        "state": row["State"].strip(),
                        "price": price,
                    }

        stations = []
        in_canada = 0
        not_found = []
        for row in cheapest.values():
            city = cities.get((row["state"], row["city"]))
            if city:
                stations.append(Station(lat=city.lat, lon=city.lon, **row))
            elif row["state"] in CANADIAN_PROVINCES:
                in_canada += 1
            else:
                not_found.append(f'{row["city"]}, {row["state"]}')

        Station.objects.all().delete()
        Station.objects.bulk_create(stations, batch_size=2000)

        us_total = len(stations) + len(not_found)
        self.stdout.write(
            f"Stations: {len(cheapest)} unique, {len(stations)} matched "
            f"({len(stations) / us_total:.1%} of US stations), "
            f"{len(not_found)} skipped (city not found), {in_canada} skipped (Canada)."
        )
        if show_missing:
            self.stdout.write("Not found: " + "; ".join(sorted(set(not_found))))
