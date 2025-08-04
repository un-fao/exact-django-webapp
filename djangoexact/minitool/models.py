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
    # New aggregation fields
    region = models.CharField(max_length=255, null=True, blank=True)
    climate = models.CharField(max_length=255, null=True, blank=True)
    moisture = models.CharField(max_length=255, null=True, blank=True)
    soil_type = models.CharField(max_length=255, null=True, blank=True)
    # Statistics fields
    mean = models.FloatField()
    median = models.FloatField()
    min = models.FloatField()
    max = models.FloatField()
    q1 = models.FloatField()
    q3 = models.FloatField()

    class Meta:
        unique_together = ["module_type", "field", "from_value", "to_value", "region", "climate", "moisture", "soil_type"]


class EmissionStatisticsByModule(models.Model):
    module_type = models.CharField(max_length=255)
    region = models.CharField(max_length=255)
    climate = models.CharField(max_length=255)
    moisture = models.CharField(max_length=255)
    soil_type = models.CharField(max_length=255)
    # Statistical measures
    count = models.IntegerField()
    total = models.FloatField()
    mean = models.FloatField()
    median = models.FloatField()
    min = models.FloatField()
    max = models.FloatField()
    q1 = models.FloatField()
    q3 = models.FloatField()

    class Meta:
        unique_together = ["module_type", "region", "climate", "moisture", "soil_type"]
