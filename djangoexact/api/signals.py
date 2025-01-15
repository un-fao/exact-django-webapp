from django.db.models.signals import post_migrate
from django.dispatch import receiver
from .models import APIStatus

@receiver(post_migrate)
def create_default_api_status(sender, **kwargs):
    # Ensure only one APIStatus instance exists
    if not APIStatus.objects.exists():
        APIStatus.objects.create()
