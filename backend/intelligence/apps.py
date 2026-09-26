from django.apps import AppConfig


class IntelligenceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "intelligence"
    verbose_name = "Competitive intelligence"

    def ready(self):
        # No signals to connect yet. Product history cascades from Monitor
        # (ProductWatch is a OneToOne with on_delete=CASCADE), so deleting a
        # monitor needs no cleanup hook here.
        return
