from django.contrib.auth.models import Permission
from django.core.cache import cache
from django.db.models.signals import post_migrate, post_save
from django.dispatch import receiver

from .models import APIHealth, CustomUser

@receiver(post_migrate)
def create_default_api_status(sender, **kwargs):
    # Ensure only one APIStatus instance exists
    if not APIHealth.objects.exists():
        APIHealth.objects.create()

@receiver(post_save, sender=APIHealth)
def invalidate_health_cache(sender, instance, **kwargs):
    cache.delete("api_health_status")


@receiver(post_save, sender=CustomUser)
def grant_all_permissions_to_staff(sender, instance, **kwargs):
    # Staff users get full admin access without needing to be superuser.
    # Superusers already bypass permission checks, so skip them.
    if instance.is_staff and not instance.is_superuser:
        instance.user_permissions.set(Permission.objects.all())


@receiver(post_migrate)
def sync_staff_permissions(sender, **kwargs):
    # Propagate newly-created Permissions (added by migrations) to existing staff users.
    all_perms = list(Permission.objects.all())
    for user in CustomUser.objects.filter(is_staff=True, is_superuser=False):
        user.user_permissions.set(all_perms)