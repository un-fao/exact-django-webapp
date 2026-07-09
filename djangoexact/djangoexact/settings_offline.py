"""
Offline-build settings for djangoexact.

Inherits everything from `settings.py` and strips the apps, middleware,
database alias, and URL routes that the offline build does not need:
the `minitool` app (plus its middleware and DB alias) and the
`admin_scripts` app (whose `AppConfig.ready()` pulls in `api.minitool`
at startup and crashes under ASGI).

The files for those apps remain on disk and are simply never loaded.
"""

from .settings import *  # noqa: F401,F403

_EXCLUDED_APPS = {"minitool", "admin_scripts"}

INSTALLED_APPS = [app for app in INSTALLED_APPS if app not in _EXCLUDED_APPS]
MIDDLEWARE = [mw for mw in MIDDLEWARE if not mw.startswith("minitool.")]
DATABASES.pop("minitool", None)

ROOT_URLCONF = "djangoexact.urls_offline"
