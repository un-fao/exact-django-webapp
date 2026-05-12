from django.db.models.signals import post_migrate, post_save
from django.dispatch import receiver
from .models import APIHealth
from django.core.cache import cache

@receiver(post_migrate)
def create_default_api_status(sender, **kwargs):
    # Ensure only one APIStatus instance exists
    if not APIHealth.objects.exists():
        APIHealth.objects.create()

@receiver(post_save, sender=APIHealth)
def invalidate_health_cache(sender, instance, **kwargs):
    cache.delete("api_health_status")