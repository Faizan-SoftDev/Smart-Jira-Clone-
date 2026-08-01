"""Development settings with safe local defaults."""

from .base import *  # noqa: F403

DEBUG = True
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

if env.bool("USE_REDIS_CHANNEL_LAYER", default=False):  # noqa: F405
    CHANNEL_LAYERS = {  # noqa: F405
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {"hosts": [CELERY_BROKER_URL]},  # noqa: F405
        }
    }
    CACHES = {  # noqa: F405
        "default": {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": CELERY_BROKER_URL}  # noqa: F405
    }
