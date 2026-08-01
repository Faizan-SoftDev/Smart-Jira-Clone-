"""Production-only hardening and Redis-backed real-time configuration."""

from .base import *  # noqa: F403

import sentry_sdk

DEBUG = False
if SECRET_KEY == "unsafe-development-key-change-me":  # noqa: F405
    raise RuntimeError("DJANGO_SECRET_KEY must be set in production.")
if not ALLOWED_HOSTS or any(host in {"localhost", "127.0.0.1"} for host in ALLOWED_HOSTS):  # noqa: F405
    raise RuntimeError("DJANGO_ALLOWED_HOSTS must contain only production hostnames.")
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "same-origin"
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31_536_000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True

if SENTRY_DSN:  # noqa: F405
    sentry_sdk.init(dsn=SENTRY_DSN, send_default_pii=False, traces_sample_rate=0.1)  # noqa: F405

if EMAIL_HOST:  # noqa: F405
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [CELERY_BROKER_URL]},  # noqa: F405
    }
}

CACHES = {
    "default": {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": CELERY_BROKER_URL}  # noqa: F405
}
