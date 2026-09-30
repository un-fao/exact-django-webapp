"""Validation for the analyst narrative supplied with a report request.

This is the first user-supplied prose the app renders into a generated PDF, and
the PDF engine is version-pinned under a CVE exemption. The caps and types here
are the trust boundary: nothing reaches a template that was not length-capped,
and the one date is parsed into a date rather than carried as text.

Escaping itself is the template's job and Django's autoescaping already does it.
What would break it is a `|safe` added later to make formatting work --
api/tests/reports/test_report_render.py is the guard against that.

Only reports whose template reads the narrative accept one. Passing it to a
report that ignores it would be harmless and silent: the analyst writes six
passages, receives a PDF without them, and has no way to tell.
"""
from __future__ import annotations

from rest_framework import serializers

NARRATIVE_REPORTS = frozenset({"ifad"})


class ActivityNarrativeSerializer(serializers.Serializer):
    wop = serializers.CharField(max_length=4000, allow_blank=True, required=False)
    wp = serializers.CharField(max_length=4000, allow_blank=True, required=False)
    data_source = serializers.CharField(max_length=500, allow_blank=True, required=False)


class ReportNarrativeSerializer(serializers.Serializer):
    tier2_specification = serializers.CharField(max_length=2000, allow_blank=True, required=False)
    data_limitations = serializers.CharField(max_length=4000, allow_blank=True, required=False)
    assumption_set_date = serializers.DateField(required=False)
    top_activity_driver = serializers.CharField(max_length=2000, allow_blank=True, required=False)
    additional_sources = serializers.ListField(
        child=serializers.CharField(max_length=500), max_length=20, required=False,
    )
    activities = serializers.DictField(child=ActivityNarrativeSerializer(), required=False)

    def validate(self, attrs):
        unknown = set(self.initial_data) - set(self.fields)
        if unknown:
            # DRF drops unknown keys without complaint. A typo would otherwise
            # reach an un-editable PDF as a passage the analyst has to notice
            # is missing.
            raise serializers.ValidationError(
                f"Unknown narrative field(s): {', '.join(sorted(unknown))}. "
                f"Available: {', '.join(sorted(self.fields))}"
            )
        return attrs


def clean_narrative(raw, activities) -> dict:
    """Validate a raw narrative payload against the activities it names.

    Raises ``serializers.ValidationError``, which DRF renders as a 400 from a
    view and fails the job from the worker.
    """
    serializer = ReportNarrativeSerializer(data=raw)
    serializer.is_valid(raise_exception=True)
    narrative = serializer.validated_data

    known = {str(activity.pk) for activity in activities}
    unknown = sorted(set(narrative.get("activities", {})) - known)
    if unknown:
        raise serializers.ValidationError(
            f"Narrative supplied for activities that are not in this report: {', '.join(unknown)}."
        )
    return narrative


def narrative_from_request(request, template_name, activities):
    """Return ``(raw, cleaned)`` narrative for a report request, or ``(None, None)``.

    Both forms are returned because both are needed: the synchronous path renders
    ``cleaned``, whose date is a real ``date``, while the async path stores ``raw``
    in ``AsyncJob.params``, which must stay JSON-serializable, and parses it again
    in the worker. Validating here means a malformed body is a 400 at request time
    rather than a job the analyst waits on only to find it failed.
    """
    data = getattr(request, "data", None)
    raw = data.get("narrative") if hasattr(data, "get") else None
    if not raw:
        return None, None
    if template_name not in NARRATIVE_REPORTS:
        raise serializers.ValidationError("This report does not accept analyst narrative.")
    return raw, clean_narrative(raw, activities)
