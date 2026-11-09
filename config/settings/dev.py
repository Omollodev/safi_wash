"""Local development settings (the default for manage.py)."""
from .base import *  # noqa: F401,F403
from .base import BASE_DIR, env  # noqa: F401

DEBUG = True
# A throwaway key is fine on your own laptop. Production refuses to start without a real one.
SECRET_KEY = env("DJANGO_SECRET_KEY", "dev-only-not-a-secret")
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]", "testserver"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
