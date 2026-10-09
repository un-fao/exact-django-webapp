"""Validation for the analyst narrative supplied with a report request.

This is the first user-supplied prose the app renders into a generated PDF, and
the PDF engine is version-pinned under a CVE exemption. The caps and types here
are the trust boundary: nothing reaches a template that was not length-capped,
and the one date is parsed into a date rather than carried as text.

Escaping itself is the template's job and Django's autoescaping already does it.
What would break it is a `|safe` added later to make formatting work --
api/tests/reports/test_report_render.py is the guard against that.

``content`` is the exception: analyst notes that arrive as HTML and must render
as markup. It goes through ``clean_content``, an allowlist sanitizer, and
api.reports.pdf refuses any fetch the sanitizer might have missed.

Only reports whose template reads the narrative accept one. Passing it to a
report that ignores it would be harmless and silent: the analyst writes six
passages, receives a PDF without them, and has no way to tell.
"""
from __future__ import annotations

import nh3
from django.utils.safestring import SafeString, mark_safe
from rest_framework import serializers

NARRATIVE_REPORTS = frozenset({"ifad"})

CONTENT_MAX_LENGTH = 20_000
MAX_CELL_SPAN = 50

# No tag here can load a resource, run code or carry styling. Widening this
# list is a security decision: img, style, link, object, iframe and svg are
# what turn a PDF render into a file read or an outbound request.
CONTENT_TAGS = frozenset({
    "p", "br", "b", "strong", "i", "em", "u", "sub", "sup",
    "ul", "ol", "li", "h3", "h4", "blockquote", "a",
    "table", "caption", "thead", "tbody", "tfoot", "tr", "th", "td",
})
_CELL_ATTRIBUTES = {"colspan", "rowspan"}
CONTENT_ATTRIBUTES = {"a": {"href"}, "th": _CELL_ATTRIBUTES, "td": _CELL_ATTRIBUTES}
_LINK_PREFIXES = ("http://", "https://", "mailto:")


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


def _filter_content_attribute(tag: str, attribute: str, value: str) -> str | None:
    if attribute == "href":
        # Explicit absolute links only. A relative or scheme-less href would be
        # resolved by whatever renders the page, which is not ours to predict.
        return value if value.lower().startswith(_LINK_PREFIXES) else None
    # colspan / rowspan: an unbounded span is a cheap way to stall table layout.
    # The length check comes before int(): past 4300 digits int() raises, and
    # nh3 keeps the attribute when this callback raises, so the filter would
    # fail open.
    if value.isascii() and value.isdigit() and len(value) <= 2 and 0 < int(value) <= MAX_CELL_SPAN:
        return value
    return None


def clean_content(raw) -> SafeString:
    """Sanitize analyst HTML notes down to the allowlist and mark the result safe.

    This is the only place report markup is marked safe. Templates output the
    result with a plain ``{{ content }}`` and never ``|safe``, so a string that
    did not pass through here is escaped like any other.

    Markup outside the allowlist is removed, not rejected: an HTML parser
    normalizes harmless input, so comparing input with output would refuse
    valid notes. Size and type are rejected, because truncating would hand back
    a PDF missing prose the analyst wrote.
    """
    if not isinstance(raw, str):
        raise serializers.ValidationError("content must be a string of HTML.")
    if len(raw) > CONTENT_MAX_LENGTH:
        raise serializers.ValidationError(
            f"content is too long: {len(raw)} characters, the limit is {CONTENT_MAX_LENGTH}."
        )
    return mark_safe(  # nosec B308 B703: output of the allowlist sanitizer
        nh3.clean(
            raw,
            tags=set(CONTENT_TAGS),
            attributes=CONTENT_ATTRIBUTES,
            attribute_filter=_filter_content_attribute,
            url_schemes={"http", "https", "mailto"},
        )
    )


def content_from_request(request, template_name) -> SafeString | None:
    """Return the sanitized ``content`` of a report request, or ``None``.

    Refused for reports that do not render it, for the same reason narrative is.
    """
    data = getattr(request, "data", None)
    raw = data.get("content") if hasattr(data, "get") else None
    if raw is None or raw == "":
        return None
    if template_name not in NARRATIVE_REPORTS:
        raise serializers.ValidationError("This report does not accept analyst content.")
    return clean_content(raw)


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
