"""Production settings. Use with DJANGO_SETTINGS_MODULE=config.settings.prod"""
from .base import *  # noqa: F401,F403
from .base import env, env_bool

DEBUG = False
SECRET_KEY = env("DJANGO_SECRET_KEY", required=True)  # app refuses to start without it

# One switch for "this site is served over HTTPS". Keep it True on the internet.
# Set SECURE_SSL_REDIRECT=False ONLY to try the production containers on http://localhost.
_HTTPS = env_bool("SECURE_SSL_REDIRECT", True)

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = _HTTPS
SECURE_REDIRECT_EXEMPT = [r"^healthz/$"]  # container health checks talk plain HTTP
SESSION_COOKIE_SECURE = _HTTPS
CSRF_COOKIE_SECURE = _HTTPS
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30 if _HTTPS else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = _HTTPS
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "same-origin"
