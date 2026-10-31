from django.db import models


class City(models.Model):
    name = models.CharField(max_length=120)
    state = models.CharField(max_length=2)
    lat = models.FloatField()
    lon = models.FloatField()

    class Meta:
        indexes = [models.Index(fields=["state", "name"])]

    def __str__(self):
        return f"{self.name}, {self.state}"


class Station(models.Model):
    id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=200)
    address = models.CharField(max_length=200)
    city = models.CharField(max_length=120)
    state = models.CharField(max_length=2)
    price = models.FloatField()
    lat = models.FloatField()
    lon = models.FloatField()

    def __str__(self):
        return f"{self.name} ({self.city}, {self.state})"
