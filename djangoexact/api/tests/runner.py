import os

from django.contrib.auth.models import Group, Permission
from django.core.exceptions import ImproperlyConfigured
from django.test.runner import DiscoverRunner

DEPLOYED_APP_MODES = ("production", "review")


def refuse_deployed_settings():
    """
    Refuse to set up test databases under production or review settings.

    settings.py runs load_dotenv(), so a djangoexact/.env with APP_MODE=production
    silently points `manage.py test` at the deployed database unless every DB_* is
    overridden, and with CI=true the test DB is DB_NAME itself. This lives here, not
    in settings.py, because deploy workflows legitimately load production settings
    with CI=true to run `check --deploy`.
    """
    app_mode = os.getenv("APP_MODE")
    if app_mode in DEPLOYED_APP_MODES:
        raise ImproperlyConfigured(
            f"Refusing to run tests with APP_MODE={app_mode!r}: this would use the {app_mode} database. "
            "Set APP_MODE to an empty or local value (an empty export also stops djangoexact/.env from overriding it)."
        )


def seed_group_permissions():
    """
    Give the seeded project groups the permissions the views check.

    Production configures group permissions by hand and no fixture, migration or
    snapshot in the repo records them, so this mirrors the role semantics instead:
    Admin is the project owner role and can do everything (scripts/ipcc_dump.py
    grants it even the custom change_public_project_flag), Second Reviewer is the
    read-only reviewer role (the frontend's Reviewer cannot mutate the project).
    """
    api_permissions = Permission.objects.filter(content_type__app_label="api")
    Group.objects.get_or_create(name="Admin")[0].permissions.set(api_permissions)
    Group.objects.get_or_create(name="Second Reviewer")[0].permissions.set(api_permissions.filter(codename__startswith="view_"))


class SeededTestRunner(DiscoverRunner):
    def setup_databases(self, **kwargs):
        refuse_deployed_settings()
        config = super().setup_databases(**kwargs)
        seed_group_permissions()
        return config
