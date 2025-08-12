def delete_all_changes():
    from minitool.models import (
        LivestockChange,
        AnnualCroplandChange,
        FloodedRiceChange,
        GrasslandChange,
        LivestockChangeAggregate,
        AnnualCroplandChangeAggregate,
        FloodedRiceChangeAggregate,
        GrasslandChangeAggregate,
    )

    LivestockChange.objects.all().delete()
    AnnualCroplandChange.objects.all().delete()
    FloodedRiceChange.objects.all().delete()
    GrasslandChange.objects.all().delete()

    LivestockChangeAggregate.objects.all().delete()
    AnnualCroplandChangeAggregate.objects.all().delete()
    FloodedRiceChangeAggregate.objects.all().delete()
    GrasslandChangeAggregate.objects.all().delete()

    print("All changes deleted")


def run():
    delete_all_changes()
