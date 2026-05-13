# tenants_api/urls.py
# ─────────────────────────────────────────────────────────────────────────────
# URL patterns for the centralised mobile API.
#
# Served at:  api.dialeasy.easyian.com/mobile/...
# Mounted in: telecrm_project/urls_public.py → path('mobile/', include('tenants_api.urls'))
#
# Design decision: We do NOT re-register the api/ ViewSets here.
# Instead we delegate straight to api.urls (which already has every route
# defined). By the time Django hits those views the schema is already switched
# by CentralApiTenantMiddleware + JWTTenantAuthentication, so they transparently
# query the correct tenant's data.
#
# Existing subdomain API is completely unchanged:
#   demo.dialeasy.easyian.com/api/...  ← still works
# ─────────────────────────────────────────────────────────────────────────────

from django.urls import path, include
from . import views
from tenants.api_views import tenant_features_view, tenant_info_view

# ── Auth URL block ────────────────────────────────────────────────────────────
auth_urlpatterns = [
    path("login/",   views.TenantLoginView.as_view(),        name="mobile_login"),
    path("refresh/", views.TenantTokenRefreshView.as_view(), name="mobile_token_refresh"),
    path("logout/",  views.TenantLogoutView.as_view(),       name="mobile_logout"),
    path("profile/", views.MobileProfileView.as_view(),      name="mobile_profile"),
]

urlpatterns = [
    # ── Health & Discovery ────────────────────────────────────────────────────
    path("health/",      views.health_check,       name="mobile_health"),
    path("tenant/info/", views.tenant_info_public, name="mobile_tenant_info"),

    # ── Authentication ────────────────────────────────────────────────────────
    path("auth/", include(auth_urlpatterns)),

    # ── CRM API ───────────────────────────────────────────────────────────────
    # Delegates to the EXISTING api/urls.py — every endpoint defined there
    # (leads, call-logs, follow-ups, tasks, products, whatsapp, reports, AI…)
    # is automatically available here too.
    #
    # Schema switching happens BEFORE these views run via:
    #   1. CentralApiTenantMiddleware  — reads JWT claim / X-Tenant-Slug header
    #   2. JWTTenantAuthentication     — validates JWT + re-confirms schema
    #
    # No code duplication. No URL name collisions (api.urls uses its own names).
    path("api/", include("api.urls")),
    path("api/reports/", include("reports.urls")),
    path("api/notifications/", include("notifications.urls")),
    path("api/ai/", include("ai.urls")),

    # Tenant feature/info endpoints (reuse the existing view functions directly)
    path("api/tenant/features/", tenant_features_view, name="mobile_tenant_features"),
    path("api/tenant/info/",     tenant_info_view,     name="mobile_tenant_info_auth"),
]
