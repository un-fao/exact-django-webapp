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


class LivestockChange(models.Model):
    """
    Model to store individual livestock change records.
    """
    module_type = models.CharField(max_length=255, default="Livestock")
    region = models.CharField(max_length=255)
    climate = models.CharField(max_length=255)
    moisture = models.CharField(max_length=255)
    soil_type = models.CharField(max_length=255)
    livestock_category_type = models.CharField(max_length=255)
    total = models.FloatField()
    field = models.CharField(max_length=255)
    from_value = models.CharField(max_length=255)
    to_value = models.CharField(max_length=255)

    class Meta:
        unique_together = [
            "module_type", "region", "climate", "moisture", "soil_type", 
            "livestock_category_type", "field", "from_value", "to_value"
        ]
        indexes = [
            models.Index(fields=['module_type']),
            models.Index(fields=['region']),
            models.Index(fields=['climate']),
            models.Index(fields=['moisture']),
            models.Index(fields=['soil_type']),
            models.Index(fields=['livestock_category_type']),
            models.Index(fields=['field']),
        ]

    def __str__(self):
        return f"{self.module_type} - {self.region} - {self.field}: {self.from_value} -> {self.to_value}"


class LivestockChangeAggregate(models.Model):
    """
    Model to store pre-aggregated livestock change statistics.
    """
    field = models.CharField(max_length=255)
    from_value = models.CharField(max_length=255)
    to_value = models.CharField(max_length=255)
    # Filter fields
    region = models.CharField(max_length=255, null=True, blank=True)
    climate = models.CharField(max_length=255, null=True, blank=True)
    moisture = models.CharField(max_length=255, null=True, blank=True)
    soil_type = models.CharField(max_length=255, null=True, blank=True)
    livestock_category_type = models.CharField(max_length=255, null=True, blank=True)
    # Statistics
    count = models.IntegerField()
    sum_total = models.FloatField()
    mean = models.FloatField()
    median = models.FloatField()
    min_value = models.FloatField()
    max_value = models.FloatField()
    q1 = models.FloatField()
    q3 = models.FloatField()

    class Meta:
        unique_together = [
            "field", "from_value", "to_value", "region", "climate", 
            "moisture", "soil_type", "livestock_category_type"
        ]
        indexes = [
            models.Index(fields=['field']),
            models.Index(fields=['region']),
            models.Index(fields=['climate']),
            models.Index(fields=['moisture']),
            models.Index(fields=['soil_type']),
            models.Index(fields=['livestock_category_type']),
        ]

    def __str__(self):
        return f"{self.field}: {self.from_value} -> {self.to_value} (Count: {self.count})"
