from django.apps import AppConfig


class SocialConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.social"
    label = "social"

    def ready(self):
        from . import checks, signals  # noqa: F401
