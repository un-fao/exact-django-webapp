"""Signed, expiring download links for async report jobs.

Stateless by design: a token carries only the report job's primary key, signed
with SECRET_KEY via django.core.signing, so an email recipient can download
without a session and no server-side token store is needed. Tokens expire after
24 hours; after that django.core.signing.loads raises SignatureExpired and the
link stops working.
"""
import urllib.parse

from django.conf import settings
from django.core.signing import BadSignature, SignatureExpired, dumps, loads

DOWNLOAD_SALT = "report-download"
DOWNLOAD_MAX_AGE = 86400  # 24 hours, in seconds


def make_download_token(job_pk):
    """Return a signed token that encodes the report job's primary key."""
    return dumps({"job": job_pk}, salt=DOWNLOAD_SALT)


def load_download_token(token):
    """Return the job pk carried by a valid token, or None if the token is
    tampered (BadSignature) or older than 24 hours (SignatureExpired)."""
    try:
        payload = loads(token, salt=DOWNLOAD_SALT, max_age=DOWNLOAD_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None
    return payload.get("job")


def build_download_url(job):
    """Build the absolute, tokenized download URL for a completed report job."""
    token = urllib.parse.quote(make_download_token(job.pk))
    return f"{settings.BACKEND_BASE_URL}/api/async-jobs/{job.pk}/download/?token={token}"
