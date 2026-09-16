from django.apps import AppConfig


class ClimbingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "climbing"
    # Keep the historical label so existing migrations and SQLite tables remain valid.
    label = "frontend_app"
