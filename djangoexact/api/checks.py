"""Deploy-time system checks for production configuration safety.

Guards against a misconfigured production deploy silently reaching
App Engine: DEBUG left on, or CORS_ALLOWED_ORIGINS left empty (which,
combined with CORS_ORIGIN_ALLOW_ALL = DEBUG in settings.py, would open
cross-origin access).
"""

import os

from django.conf import settings
from django.core.checks import Error, Tags, register


@register(Tags.security, deploy=True)
def check_production_config(app_configs, **kwargs):
    """Fail manage.py check --deploy when production config is unsafe.

    APP_MODE is read from the environment via os.getenv, not from
    settings.APP_MODE, because APP_MODE is never assigned as a Django
    setting in settings.py, it is only a plain local variable used to
    select which .env.{app_mode} file to load.
    """
    errors = []
    app_mode = os.getenv("APP_MODE")
    if app_mode == "production":
        if settings.DEBUG:
            errors.append(
                Error(
                    "DEBUG is True while APP_MODE is production.",
                    hint="Set DJANGO_DEBUG=False for the production environment.",
                    id="api.E001",
                )
            )
        if not settings.CORS_ALLOWED_ORIGINS:
            errors.append(
                Error(
                    "CORS_ALLOWED_ORIGINS is empty while APP_MODE is production.",
                    hint="Set CORS_ALLOWED_ORIGINS to a comma-separated allowed-origins list.",
                    id="api.E002",
                )
            )
    return errors
