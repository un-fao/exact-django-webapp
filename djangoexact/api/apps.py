from django.apps import AppConfig
from django.db.models.signals import post_migrate

class ApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api'

    def ready(self):
        from .signals import create_default_api_status
        post_migrate.connect(create_default_api_status, sender=self)
        from . import checks  # noqa: F401  registers the deploy check