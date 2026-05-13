from django.apps import AppConfig


class TenantsApiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "tenants_api"
    verbose_name = "Centralized Tenant API"
