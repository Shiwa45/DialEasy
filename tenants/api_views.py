# tenants/api_views.py
# ─────────────────────────────────────────────────────────────────────────────
# API endpoints consumed by the Flutter app.
# Called once after login; Flutter stores the feature list in Riverpod state
# and conditionally renders nav items / screens.
# ─────────────────────────────────────────────────────────────────────────────

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django_tenants.utils import get_tenant


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def tenant_features_view(request):
    """
    Returns the list of feature slugs enabled for the current tenant.

    GET /api/tenant/features/

    Response:
    {
        "tenant": "Acme Corp",
        "plan": "Pro",
        "features": ["whatsapp_api", "call_recording", "advanced_reports"],
        "limits": {
            "max_agents": 20,
            "max_leads": 10000
        }
    }

    Flutter usage:
        On login success, call this endpoint and store `features` in a
        Riverpod StateProvider<Set<String>>.
        Then gate every screen/nav item with:
            ref.watch(tenantFeaturesProvider).contains('whatsapp_api')
    """
    try:
        tenant = get_tenant(request)

        # Super admin or public schema — return all features
        if tenant.schema_name == 'public' or request.user.is_superuser:
            return Response({
                'tenant': 'Super Admin',
                'plan': 'Enterprise (Super Admin)',
                'features': ['all'],  # Flutter treats 'all' as bypass
                'limits': {'max_agents': -1, 'max_leads': -1},
            })

        subscription = tenant.active_subscription
        plan = tenant.current_plan

        features = tenant.get_enabled_features() if plan else []
        limits = {
            'max_agents': plan.max_agents if plan else 0,
            'max_leads': plan.max_leads if plan else 0,
        }

        return Response({
            'tenant': tenant.name,
            'plan': plan.name if plan else None,
            'plan_slug': plan.slug if plan else None,
            'subscription_status': subscription.status if subscription else 'none',
            'trial_ends_at': subscription.trial_ends_at if subscription else None,
            'features': features,
            'limits': limits,
        })

    except Exception as e:
        return Response(
            {'error': f'Failed to fetch tenant features: {str(e)}'},
            status=500
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def tenant_info_view(request):
    """
    Returns basic tenant branding info for the Flutter app.

    GET /api/tenant/info/

    Response:
    {
        "name": "Acme Corp",
        "logo_url": "https://...",
        "schema_name": "acme"
    }
    """
    try:
        tenant = get_tenant(request)
        logo_url = None
        if hasattr(tenant, 'logo') and tenant.logo:
            logo_url = request.build_absolute_uri(tenant.logo.url)

        return Response({
            'name': tenant.name,
            'schema_name': tenant.schema_name,
            'logo_url': logo_url,
            'is_active': tenant.is_active,
        })
    except Exception as e:
        return Response({'error': str(e)}, status=500)
