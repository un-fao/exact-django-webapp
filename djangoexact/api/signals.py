from django.contrib.auth.models import Group, Permission
from django.core.cache import cache
from django.db.models.signals import post_migrate, post_save
from django.dispatch import receiver

from .models import APIHealth, CustomUser

STAFF_GROUP_NAME = "Staff"

@receiver(post_migrate)
def create_default_api_status(sender, **kwargs):
    # Ensure only one APIStatus instance exists
    if not APIHealth.objects.exists():
        APIHealth.objects.create()

@receiver(post_save, sender=APIHealth)
def invalidate_health_cache(sender, instance, **kwargs):
    cache.delete("api_health_status")


@receiver(post_migrate)
def ensure_staff_group(sender, **kwargs):
    # Maintain a "Staff" Group that holds every Permission in the system.
    # post_migrate re-runs whenever migrations add new Permissions, keeping the
    # Group in sync without manual intervention.
    group, _ = Group.objects.get_or_create(name=STAFF_GROUP_NAME)
    group.permissions.set(Permission.objects.all())


@receiver(post_save, sender=CustomUser)
def sync_staff_group_membership(sender, instance, **kwargs):
    # is_staff=True → member of "Staff" Group (full admin via group perms).
    # is_staff=False → removed from the Group. Superusers bypass perm checks already.
    if instance.is_superuser:
        return
    group, _ = Group.objects.get_or_create(name=STAFF_GROUP_NAME)
    if instance.is_staff:
        instance.groups.add(group)
    else:
        instance.groups.remove(group)