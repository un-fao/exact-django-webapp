"""Shared SQLite test-DB seeding.

The unit suite has no fixture bootstrap of its own and queries reference
models at *import time* (``api/tests/factories.py``), which Django imports
before ``setup_databases``. So the SQLite file must already exist and be
seeded before ``manage.py test`` runs (then use ``--keepdb``).

Used by both the ``setup_test_db`` management command (the one-time builder)
and ``SqliteReferenceTestRunner`` (idempotent safety net).
"""

import logging

from django.core.management import call_command

log = logging.getLogger(__name__)

ROLE_GROUPS = ("Admin", "Second Reviewer", "Staff")
TEST_USERS = ("testuser@example.com", "test@user.org")

# Fixtures that `load_reference_data` skips wholesale because a *few* of their
# rows reference reference pks the owning fixture omits (a pre-existing
# committed cross-app FK inconsistency, tracked separately). Reloaded here
# row-by-row, skipping only the rows whose FK targets are absent, so the
# overwhelming majority of valid rows (which downstream calculators need —
# e.g. rice nitrous EFs) land and the DB stays referentially consistent
# (required: SQLite re-checks all FKs on every later schema_editor()).
FK_TOLERANT_FIXTURES = ("ipcc/fixtures/cropnitrousestimationdefaultfactor.json",)


def _missing_fk(instance):
    """Return the first (field, pk) whose FK target row does not exist."""
    for field in instance._meta.concrete_fields:
        if not field.many_to_one:
            continue
        value = getattr(instance, field.attname)
        if value is None:
            continue
        if not field.related_model.objects.filter(pk=value).exists():
            return field.name, value
    return None


def _load_fk_tolerant():
    from pathlib import Path

    from django.conf import settings
    from django.core import serializers

    base = Path(settings.BASE_DIR)
    for rel in FK_TOLERANT_FIXTURES:
        path = base / rel
        if not path.exists():
            log.warning("FK-tolerant fixture not found: %s", path)
            continue
        with path.open(encoding="utf-8") as fh:
            objects = list(serializers.deserialize("json", fh, ignorenonexistent=True))
        loaded = skipped = 0
        for obj in objects:
            miss = _missing_fk(obj.object)
            if miss:
                skipped += 1
                log.warning(
                    "skip %s pk=%s: missing FK %s=%s",
                    rel, obj.object.pk, miss[0], miss[1],
                )
                continue
            obj.save()
            loaded += 1
        log.info("loaded %s (%d ok, %d skipped on dangling FK)", rel, loaded, skipped)


def seed_role_groups():
    """Role groups looked up by name across views/serializers/tests, each
    granted every permission so a project member with the group passes
    ``has_project_permission`` (which checks ``group.permissions`` by
    codename)."""
    from django.contrib.auth.models import Group, Permission

    all_perms = list(Permission.objects.all())
    for name in ROLE_GROUPS:
        group, _ = Group.objects.get_or_create(name=name)
        group.permissions.set(all_perms)


def seed_test_users():
    """Canonical users ``APITestCaseMixin`` / ``base_test_classes`` fetch
    with ``.get(email=...)``."""
    from api.models import CustomUser

    for email in TEST_USERS:
        if not CustomUser.objects.filter(email=email).exists():
            CustomUser.objects.create_user(email=email, password="testpass123")


def bootstrap_test_db(force_reference: bool = False):
    """Seed reference data (once) + role groups + test users. Idempotent."""
    from api.models import StatusType

    if force_reference or not StatusType.objects.exists():
        log.info("Loading reference data into the test database...")
        # --continue-on-error: the committed reference fixtures contain a few
        # pre-existing cross-app FK inconsistencies (e.g. ipcc fixtures that
        # reference LandUseType pks absent from landusetype.json). Skipping
        # those individual fixtures still yields a maximally-populated test DB;
        # the gaps are tracked separately.
        call_command("load_reference_data", "--app=all", "--continue-on-error", verbosity=0)
        _load_fk_tolerant()

    seed_role_groups()
    seed_test_users()
