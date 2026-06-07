"""
Production Django settings for deployment on EC2.

Imports all common settings and applies production-specific overrides:
  - Secure cookie flags (required for cross-origin auth with Vercel)
  - CORS / CSRF trusted origins for the Vercel deployment domain
  - S3 via django-storages for media files
  - WhiteNoise for static files (no separate S3 bucket for static)
  - Disabled DEBUG

Selected via: DJANGO_SETTINGS_MODULE=config.settings.production
"""

import os

from .common import *  # noqa: F401, F403

# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------

DEBUG = False

ALLOWED_HOSTS = [
    os.environ.get("DOMAIN", ""),
    # Internal Docker hostname so Traefik health-checks resolve
    "api",
]

# ---------------------------------------------------------------------------
# CORS and CSRF
# ---------------------------------------------------------------------------

_domain = os.environ.get("DOMAIN", "")
_vercel_domain = os.environ.get("VERCEL_DOMAIN", "")

# Allow the primary domain and the Vercel preview/production URL.
# Without VERCEL_DOMAIN here, Vercel preview builds fail CSRF checks.
CORS_ALLOWED_ORIGINS = [
    f"https://{_domain}",
    f"https://{_vercel_domain}",
]

CORS_ALLOW_CREDENTIALS = True

CSRF_TRUSTED_ORIGINS = [
    f"https://{_domain}",
    f"https://{_vercel_domain}",
]

# ---------------------------------------------------------------------------
# Secure cookies
# ---------------------------------------------------------------------------

# SameSite=None is required for cross-origin requests from Vercel (different domain).
# Both Secure=True and SameSite=None must be set together; browsers reject
# SameSite=None on non-HTTPS connections.
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_SAMESITE = "None"

CSRF_COOKIE_SECURE = True
CSRF_COOKIE_SAMESITE = "None"

SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True

# Trust the X-Forwarded-Proto header from Traefik so Django treats the
# connection as HTTPS even though Traefik → Django is plain HTTP internally.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# ---------------------------------------------------------------------------
# Storage — media files on S3, static files via WhiteNoise
# ---------------------------------------------------------------------------

# django-storages S3 backend for user-uploaded media.
# Static files are served from the container by WhiteNoise (already in MIDDLEWARE).
DEFAULT_FILE_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"

AWS_STORAGE_BUCKET_NAME = os.environ.get("AWS_S3_BUCKET_NAME", "")
AWS_S3_REGION_NAME = os.environ.get("AWS_S3_REGION_NAME", "eu-west-1")
AWS_S3_FILE_OVERWRITE = False
AWS_DEFAULT_ACL = None  # Use bucket policy for ACL management

# Collect static files into STATIC_ROOT; WhiteNoise serves from there.
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------

# Django sends email via SMTP; React Email templates are rendered by Next.js.
# See docs/05-frontend.md for the cross-stack email pattern.
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.environ.get("EMAIL_HOST", "smtp-relay.brevo.com")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", f"noreply@{_domain}")
