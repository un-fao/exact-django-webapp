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


class StatisticsModuleTotal(models.Model):
    module_type = models.CharField(max_length=255)
    field = models.CharField(max_length=255)
    from_value = models.CharField(max_length=255)
    to_value = models.CharField(max_length=255)
    mean = models.FloatField()
    median = models.FloatField()
    min = models.FloatField()
    max = models.FloatField()
    q1 = models.FloatField()
    q3 = models.FloatField()

    class Meta:
        unique_together = ["module_type", "field", "from_value", "to_value"]
