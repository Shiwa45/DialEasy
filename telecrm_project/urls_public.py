# telecrm_project/urls_public.py
# ─────────────────────────────────────────────────────────────────────────────
# URL config served on the PUBLIC schema domain (e.g. admin.telecrm.com or localhost).
# This is the super admin interface — tenants do NOT see these URLs.
# ─────────────────────────────────────────────────────────────────────────────

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect
from django.contrib.auth import views as auth_views

urlpatterns = [
    # Super admin Django admin — manages tenants, plans, features
    path('admin/', admin.site.urls),

    # Redirect root to admin
    path('', lambda request: redirect('admin:index')),

    # Auth (needed for admin login)
    path('accounts/login/', auth_views.LoginView.as_view(), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),

    # Tenant management API (optional — for future super admin REST API)
    # path('superadmin/api/', include('tenants.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
