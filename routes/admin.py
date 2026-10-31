from django.contrib import admin

from .models import City, Station


@admin.register(Station)
class StationAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "city", "state", "price"]
    list_filter = ["state"]
    search_fields = ["name", "city"]


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ["name", "state", "lat", "lon"]
    list_filter = ["state"]
    search_fields = ["name"]
