from django.contrib.auth.models import Group, Permission
from django.test.runner import DiscoverRunner


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
        config = super().setup_databases(**kwargs)
        seed_group_permissions()
        return config
