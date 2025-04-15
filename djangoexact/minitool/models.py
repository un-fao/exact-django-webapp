from django.db import models

# Create your models here.


class Entry(models.Model):
    module_type = models.CharField(max_length=255)
    region = models.CharField(max_length=255)
    climate = models.CharField(max_length=255)
    moisture = models.CharField(max_length=255)
    soil_type = models.CharField(max_length=255)
    total = models.FloatField()
    changes = models.JSONField()
