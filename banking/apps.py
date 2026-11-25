from django.apps import AppConfig


class BankingConfig(AppConfig):
    """Configuration for the banking application."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'banking'

    def ready(self):
        import banking.signals  # noqa: F401
