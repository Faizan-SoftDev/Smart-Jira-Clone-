from django.apps import AppConfig


class CoreConfig(AppConfig):
    """Register shared core application components."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"
