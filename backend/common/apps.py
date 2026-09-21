from django.apps import AppConfig


class CommonConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "common"

    def ready(self):
        # Phase 1: warn operators about unconfigured integrations at
        # startup. Never raises: optional integrations must not break boot.
        try:
            from .integration_status import log_integration_warnings

            log_integration_warnings()
        except Exception:
            pass
