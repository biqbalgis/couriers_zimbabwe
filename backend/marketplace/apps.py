from django.apps import AppConfig
class MarketplaceConfig(AppConfig):
    def ready(self):
        from . import signals
        from . import audit_context
    default_auto_field = "django.db.models.BigAutoField"
    name = "marketplace"
