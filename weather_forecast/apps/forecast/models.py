from django.contrib.gis.db import models

class Waypoint(models.Model):
    name = models.CharField(max_length=50)
    geometry = models.PointField(srid=4326)
    objects = models.GeoManager()

    def __str__(self):
        return "{0} {1} {2}".format(self.name, self.geometry_x, geometry_y)
