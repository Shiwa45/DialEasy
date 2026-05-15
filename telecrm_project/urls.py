# telecrm_project/urls.py
# ─────────────────────────────────────────────────────────────────────────────
# URL config served on TENANT subdomains (e.g. acme.telecrm.com).
# Each tenant gets the full CRM application here.
# ─────────────────────────────────────────────────────────────────────────────

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect
from django.contrib.auth import views as auth_views
from tenants.api_views import tenant_features_view, tenant_info_view
from tenants.models import Domain

def super_admin_redirect(request):
    try:
        public_domain = Domain.objects.get(tenant__schema_name='public').domain
        host = request.get_host()
        if ':' in host and ':' not in public_domain:
            port = host.split(':')[1]
            public_domain = f"{public_domain}:{port}"
        return redirect(f"{request.scheme}://{public_domain}/admin/")
    except Exception:
        return redirect('/admin/')

super_admin_patterns = ([
    path('', super_admin_redirect, name='index'),
], 'super_admin')

urlpatterns = [
    # Super Admin Redirect (resolves 'super_admin:index' from tenant templates)
    path('__super_admin/', include(super_admin_patterns)),

    # Tenant-level Django admin (manages agents, leads within this tenant)
    path('admin/', admin.site.urls),

    # Root → CRM dashboard
    path('', lambda request: redirect('leads:dashboard')),

    # CRM apps
    path('leads/', include('leads.urls')),
    path('agents/', include('agents.urls')),
    path('reports/', include('reports.urls_mvt')),

    # REST API (consumed by Flutter app)
    path('api/', include('api.urls')),
    path('api/reports/', include('reports.urls')),
    path('api/notifications/', include('notifications.urls')),
    path('api/ai/', include('ai.urls')),

    # ── Tenant feature API — Flutter calls this on login ─────────────────────
    path('api/tenant/features/', tenant_features_view, name='tenant_features'),
    path('api/tenant/info/', tenant_info_view, name='tenant_info'),

    # Authentication
    path('accounts/login/', auth_views.LoginView.as_view(), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
