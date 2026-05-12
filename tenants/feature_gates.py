# tenants/feature_gates.py
# ─────────────────────────────────────────────────────────────────────────────
# Feature Gating System
#
# Usage in Django MVT views:
#   from tenants.feature_gates import require_feature
#
#   @require_feature('whatsapp_api')
#   def whatsapp_view(request):
#       ...
#
# Usage in DRF API views:
#   from tenants.feature_gates import FeatureRequiredMixin
#
#   class WhatsAppViewSet(FeatureRequiredMixin, viewsets.ModelViewSet):
#       required_feature = 'whatsapp_api'
#
# Usage in templates:
#   {% if request.tenant_features.whatsapp_api %}
#       <a href="...">WhatsApp</a>
#   {% endif %}
# ─────────────────────────────────────────────────────────────────────────────

import functools
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import render
from django_tenants.utils import get_tenant


def get_tenant_from_request(request):
    """Safely retrieve the current tenant from the request."""
    try:
        return get_tenant(request)
    except Exception:
        return None


def tenant_has_feature(request, feature_slug: str) -> bool:
    """
    Returns True if the current request's tenant has the given feature enabled.
    Always returns True for staff/superusers (super admin bypass).
    """
    # Super admin bypass — super admin can access everything
    if hasattr(request, 'user') and request.user.is_authenticated:
        if request.user.is_superuser:
            return True

    tenant = get_tenant_from_request(request)
    if tenant is None:
        return False

    # Public schema (super admin domain) — bypass feature gates
    if tenant.schema_name == 'public':
        return True

    return tenant.has_feature(feature_slug)


# ─── Django MVT Decorator ─────────────────────────────────────────────────────

def require_feature(feature_slug: str, template='tenants/feature_unavailable.html'):
    """
    Decorator for Django MVT views.
    If the tenant doesn't have the feature, renders the upgrade page.

    @require_feature('whatsapp_api')
    def my_view(request):
        ...
    """
    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            if not tenant_has_feature(request, feature_slug):
                return render(request, template, {
                    'feature_slug': feature_slug,
                    'feature_name': feature_slug.replace('_', ' ').title(),
                }, status=403)
            return view_func(request, *args, **kwargs)
        return wrapped_view
    return decorator


# ─── DRF Mixin ───────────────────────────────────────────────────────────────

class FeatureRequiredMixin:
    """
    Mixin for Django REST Framework ViewSets and APIViews.
    Set required_feature = 'feature_slug' on the class.

    class WhatsAppViewSet(FeatureRequiredMixin, viewsets.ModelViewSet):
        required_feature = 'whatsapp_api'
    """
    required_feature = None

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if self.required_feature:
            if not tenant_has_feature(request, self.required_feature):
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied(
                    detail=f"Your current plan does not include '{self.required_feature}'. "
                           f"Please upgrade to access this feature."
                )


# ─── Template Context Processor ──────────────────────────────────────────────

class TenantFeatureProxy:
    """
    A proxy object injected into templates as `request.tenant_features`.
    Allows template checks like: {% if request.tenant_features.whatsapp_api %}
    """
    def __init__(self, tenant):
        self._tenant = tenant
        self._cache = None

    def _get_slugs(self):
        if self._cache is None:
            if self._tenant and hasattr(self._tenant, 'get_enabled_features'):
                self._cache = set(self._tenant.get_enabled_features())
            else:
                self._cache = set()
        return self._cache

    def __getattr__(self, feature_slug):
        # Called when template does {{ request.tenant_features.whatsapp_api }}
        if feature_slug.startswith('_'):
            raise AttributeError(feature_slug)
        return feature_slug in self._get_slugs()

    def as_list(self):
        return list(self._get_slugs())

    def has(self, slug):
        return slug in self._get_slugs()


def tenant_features_context_processor(request):
    """
    Adds `tenant_features` to every template context.
    Register in settings.py TEMPLATES[0]['OPTIONS']['context_processors'].
    """
    tenant = get_tenant_from_request(request)
    return {
        'tenant_features': TenantFeatureProxy(tenant),
        'current_tenant': tenant,
    }
