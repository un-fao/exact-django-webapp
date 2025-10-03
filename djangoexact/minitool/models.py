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


class ChangeRecord(models.Model):
    """
    Generalized model to store individual change records for all module types.
    Uses custom_filters JSONField to store module-specific filter data.
    """

    module_type = models.CharField(max_length=255)
    region = models.CharField(max_length=255)
    climate = models.CharField(max_length=255)
    moisture = models.CharField(max_length=255)
    soil_type = models.CharField(max_length=255)
    total = models.FloatField()
    field = models.CharField(max_length=255)
    from_value = models.CharField(max_length=255)
    to_value = models.CharField(max_length=255)
    # Store all custom filter columns as JSON
    custom_filters = models.JSONField(default=dict, blank=True)

    class Meta:
        unique_together = ["module_type", "region", "climate", "moisture", "soil_type", "field", "from_value", "to_value", "custom_filters"]
        indexes = [
            models.Index(fields=["module_type"]),
            models.Index(fields=["region"]),
            models.Index(fields=["climate"]),
            models.Index(fields=["moisture"]),
            models.Index(fields=["soil_type"]),
            models.Index(fields=["field"]),
            # Index the JSONField for better performance
            models.Index(fields=["custom_filters"], name="changerecord_custom_idx"),
        ]

    def __str__(self):
        return f"{self.module_type} - {self.region} - {self.field}: {self.from_value} -> {self.to_value}"


class ChangeAggregate(models.Model):
    """
    Generalized model to store pre-aggregated change statistics for all module types.
    Uses custom_filters JSONField to store module-specific filter data.
    """

    module_type = models.CharField(max_length=255)
    field = models.CharField(max_length=255)
    from_value = models.CharField(max_length=255)
    to_value = models.CharField(max_length=255)
    region = models.CharField(max_length=255, null=True, blank=True)
    climate = models.CharField(max_length=255, null=True, blank=True)
    moisture = models.CharField(max_length=255, null=True, blank=True)
    soil_type = models.CharField(max_length=255, null=True, blank=True)
    # Store all custom filter columns as JSON
    custom_filters = models.JSONField(default=dict, blank=True)

    count = models.IntegerField()
    sum_total = models.FloatField()
    mean = models.FloatField()
    median = models.FloatField()
    min_value = models.FloatField()
    max_value = models.FloatField()
    q1 = models.FloatField()
    q3 = models.FloatField()

    class Meta:
        unique_together = ["module_type", "field", "from_value", "to_value", "region", "climate", "moisture", "soil_type", "custom_filters"]
        indexes = [
            models.Index(fields=["module_type"]),
            models.Index(fields=["field"]),
            models.Index(fields=["region"]),
            models.Index(fields=["climate"]),
            models.Index(fields=["moisture"]),
            models.Index(fields=["soil_type"]),
            # Index the JSONField for better performance
            models.Index(fields=["custom_filters"], name="changeaggregate_custom_idx"),
        ]

    def __str__(self):
        return f"{self.field}: {self.from_value} -> {self.to_value} (Count: {self.count})"


class EmissionScenarioCategory(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class EmissionScenario(models.Model):
    name = models.CharField(max_length=255)
    category = models.ForeignKey(EmissionScenarioCategory, on_delete=models.CASCADE, null=True, blank=True)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    metadata = models.JSONField(default=dict, blank=True)

    module_type = models.CharField(max_length=255)
    changes = models.JSONField()

    def __str__(self):
        return self.name
