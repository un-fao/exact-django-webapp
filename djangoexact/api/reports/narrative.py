"""Validation for the analyst notes supplied with a report request.

``content`` is the only user-supplied input a report renders: analyst notes
that arrive as HTML and must render as markup. The PDF engine is version-pinned
under a CVE exemption, so ``clean_content``, an allowlist sanitizer, is the
trust boundary, and api.reports.pdf refuses any fetch the sanitizer might have
missed.

Only reports whose template renders the notes accept them. Passing them to a
report that ignores them would be harmless and silent: the analyst writes the
notes, receives a file without them, and has no way to tell.
"""
from __future__ import annotations

import nh3
from django.utils.safestring import SafeString, mark_safe
from rest_framework import serializers

CONTENT_REPORTS = frozenset({"ifad"})

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

    Refused for reports that do not render it.
    """
    data = getattr(request, "data", None)
    if not hasattr(data, "get"):
        return None
    if data.get("narrative"):
        # The structured narrative was replaced by content. A client still
        # sending it would otherwise get a PDF without the prose it carried.
        raise serializers.ValidationError(
            "narrative is no longer accepted: send the analyst notes as HTML in content."
        )
    raw = data.get("content")
    if raw is None or raw == "":
        return None
    if template_name not in CONTENT_REPORTS:
        raise serializers.ValidationError("This report does not accept analyst content.")
    return clean_content(raw)
