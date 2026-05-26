"""Gap detection for scenario combinations missing from ChangeRecord."""

from minitool.models import ChangeRecord


def detect_gap(module_type, field, from_value, to_value):
    """Check whether ChangeRecord data exists for a combination.

    Returns True if the combination is a gap (no data), False otherwise.
    """
    return not ChangeRecord.objects.filter(
        module_type=module_type,
        field=field,
        from_value=from_value,
        to_value=to_value,
    ).exists()
