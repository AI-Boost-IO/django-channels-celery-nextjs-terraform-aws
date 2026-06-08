"""
Django common settings shared across all environments.

Environment-specific overrides live in:
  - development.py  (local dev — DEBUG on, permissive CORS)
  - production.py   (AWS EC2 — secure cookies, S3, domain CORS)
  - ci.py           (GitHub Actions — InMemoryChannelLayer, eager Celery)

Replace 'myproject' with your Django project name throughout.
"""

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

# api/ directory — the Django project root
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------

SECRET_KEY = os.environ.get("SECRET_KEY", "insecure-dev-key-DO-NOT-USE-IN-PRODUCTION")

DEBUG = False  # Each environment file sets this explicitly

ALLOWED_HOSTS: list[str] = []

# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------

INSTALLED_APPS = [
    # daphne MUST be first — it patches Django's dev server to accept ASGI.
    # Without this, `manage.py runserver` serves WSGI and Channels won't work.
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "channels",              # WebSocket + ASGI routing
    "corsheaders",           # CORS headers for cross-origin requests from Vercel
    "strawberry_django",     # Strawberry GraphQL + Django ORM integration
    "django_celery_beat",    # DB-backed periodic task scheduler (visible in admin)
    "storages",              # django-storages: S3Boto3Storage backend in production
    # Local apps — add yours here
    "apps.authentication",
    "apps.yourapp",
]

MIDDLEWARE = [
    # CorsMiddleware must be as high as possible — before any middleware
    # that generates responses (e.g. CommonMiddleware, SessionMiddleware).
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    # WhiteNoise serves static files directly in production (no S3 for static).
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# ---------------------------------------------------------------------------
# ASGI / Channels
# ---------------------------------------------------------------------------

# Points Django to the ASGI application that handles both HTTP and WebSocket.
ASGI_APPLICATION = "config.asgi.application"

_redis_host = os.environ.get("CACHE_URL", "localhost")

# Redis channel layer: the pub/sub bus for WebSocket subscriptions.
# Workers call group_send() on this layer; subscription generators receive the events.
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [(_redis_host, 6379)],
        },
    }
}

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "myproject"),
        "USER": os.environ.get("POSTGRES_USER", "myproject"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "myproject"),
        "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

# Custom user model — must be set before the first migration.
AUTH_USER_MODEL = "authentication.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------------------
# Celery
# ---------------------------------------------------------------------------

# Broker on Redis DB 0, results on Redis DB 1.
# Separate DBs prevent result keys from polluting the task queue namespace.
CELERY_BROKER_URL = f"redis://{_redis_host}:6379/0"
CELERY_RESULT_BACKEND = f"redis://{_redis_host}:6379/1"

# Use the DB scheduler so periodic tasks survive restarts and are visible in admin.
# Tasks are registered via management command, not hardcoded here.
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]

# acks_late: acknowledge the task only after it completes successfully.
# If the worker crashes mid-task, the broker re-queues it automatically.
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_TASK_TRACK_STARTED = True
CELERY_RESULT_EXPIRES = 60 * 60 * 24  # 24 hours

# ---------------------------------------------------------------------------
# Static and media files
# ---------------------------------------------------------------------------

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "mediafiles"

# ---------------------------------------------------------------------------
# Internationalisation
# ---------------------------------------------------------------------------

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": os.environ.get("DJANGO_LOG_LEVEL", "INFO"),
            "propagate": False,
        },
    },
}
