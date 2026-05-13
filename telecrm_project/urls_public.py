# telecrm_project/urls_public.py
# ─────────────────────────────────────────────────────────────────────────────
# URL config served on the PUBLIC schema domain.
#
# Two domains hit this URL conf:
#   1. admin.dialeasy.easyian.com  — super admin interface (unchanged)
#   2. api.dialeasy.easyian.com    — centralised mobile API gateway (NEW)
#
# TenantMainMiddleware routes both to this file because both resolve to the
# public schema. CentralApiTenantMiddleware then switches the schema to the
# correct tenant for /mobile/... requests.
# ─────────────────────────────────────────────────────────────────────────────

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect
from django.contrib.auth import views as auth_views
from tenants.admin import super_admin_site

urlpatterns = [
    # ── Super Admin (superusers only — see tenants/admin.py SuperAdminSite) ──
    path('admin/', super_admin_site.urls),

    # Redirect root to super admin (only hits this on the admin domain, not api domain)
    path('', lambda request: redirect('super_admin:index')),

    # Auth (needed for admin login)
    path('accounts/login/', auth_views.LoginView.as_view(), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),

    # ── Centralised Mobile API ────────────────────────────────────────────────
    # Served at: api.dialeasy.easyian.com/mobile/...
    # Schema is switched by CentralApiTenantMiddleware before views run.
    # No wildcard SSL needed — single fixed subdomain cert.
    path('mobile/', include('tenants_api.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

