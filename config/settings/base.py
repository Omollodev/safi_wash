"""
Settings shared by every environment.

Environment-specific tweaks live in dev.py and prod.py.
All secrets come from environment variables (see .env.example) -- never
write a real password, key or token in this file.
"""
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv
import os

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")


def env(name, default=None, required=False):
    # A blank value (e.g. "DATABASE_URL=" copied from .env.example) counts as "not set".
    value = os.environ.get(name) or default
    if required and not value:
        raise ImproperlyConfigured(f"Set the {name} environment variable (see .env.example).")
    return value


def env_bool(name, default=False):
    return str(os.environ.get(name) or default).strip().lower() in {"1", "true", "yes", "on"}


def env_list(name, default=""):
    return [item.strip() for item in (os.environ.get(name) or default).split(",") if item.strip()]


# ---------------------------------------------------------------- core
DEBUG = False
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "whitenoise.runserver_nostatic",
    "django.contrib.staticfiles",
    # Our apps -- each one owns one part of the business (see ARCHITECTURE.md)
    "apps.core",
    "apps.accounts",
    "apps.customers",
    "apps.catalog",
    "apps.workforce",
    "apps.jobs",
    "apps.payments",
    "apps.notifications",
    "apps.portal",
    "apps.dashboard",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.site",
            ],
        },
    },
]

# ---------------------------------------------------------------- database
# SQLite works out of the box (great for students). Set DATABASE_URL to use
# PostgreSQL/MySQL in production.
DATABASES = {
    "default": dj_database_url.parse(
        env("DATABASE_URL", f"sqlite:///{BASE_DIR / 'db.sqlite3'}"), conn_max_age=600
    )
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------- auth
AUTH_USER_MODEL = "accounts.User"
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "dashboard:home"
LOGOUT_REDIRECT_URL = "dashboard:landing"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------- i18n
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Nairobi"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------- static / media
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
WHITENOISE_MIMETYPES = {".webmanifest": "application/manifest+json"}
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# ---------------------------------------------------------------- business info
# Shown on the landing page and printed job cards. Override in .env.
BUSINESS = {
    "name": env("BUSINESS_NAME", "Safi Wash"),
    "phone": env("BUSINESS_PHONE", "+254700000000"),
    "email": env("BUSINESS_EMAIL", "info@example.com"),
    "address": env("BUSINESS_ADDRESS", "Your town, Kenya"),
    "hours": env("BUSINESS_HOURS", "Mon-Sat 8:00-18:00"),
    "currency": env("CURRENCY", "KES"),
}

# ---------------------------------------------------------------- email
EMAIL_BACKEND = env("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", "localhost")
EMAIL_PORT = int(env("EMAIL_PORT", 587))
EMAIL_HOST_USER = env("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", BUSINESS["email"])
EMAIL_VERIFICATION_MAX_AGE = 60 * 60 * 24  # verification links last 24 hours

# ---------------------------------------------------------------- SMS (optional)
SMS_ENABLED = env_bool("SMS_ENABLED", False)
AT_USERNAME = env("AT_USERNAME", "sandbox")
AT_API_KEY = env("AT_API_KEY", "")
AT_SENDER_ID = env("AT_SENDER_ID", "")

# ---------------------------------------------------------------- M-Pesa (optional)
# MPESA_MODE=fake  -> no network calls; payments are simulated (default, safe for learning)
# MPESA_MODE=sandbox / production -> real Safaricom Daraja STK Push
MPESA_MODE = env("MPESA_MODE", "fake")
MPESA_CONSUMER_KEY = env("MPESA_CONSUMER_KEY", "")
MPESA_CONSUMER_SECRET = env("MPESA_CONSUMER_SECRET", "")
MPESA_SHORTCODE = env("MPESA_SHORTCODE", "174379")
MPESA_PASSKEY = env("MPESA_PASSKEY", "")
MPESA_CALLBACK_BASE_URL = env("MPESA_CALLBACK_BASE_URL", "")  # public https URL of your site
# Random string added to the callback URL so strangers cannot fake payments.
MPESA_CALLBACK_TOKEN = env("MPESA_CALLBACK_TOKEN", "")

# ---------------------------------------------------------------- misc
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", "INFO")},
}
