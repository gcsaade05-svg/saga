from django.apps import AppConfig


class ApiConfig(AppConfig):
    """API REST do SAGA (aula 5): serializadores, views genéricas e rotas em /api/v1/."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "api"
    verbose_name = "API REST"
