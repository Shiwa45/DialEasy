# tenants_api/permissions.py
# ─────────────────────────────────────────────────────────────────────────────
# Custom DRF permission classes for the centralised tenant API.
# ─────────────────────────────────────────────────────────────────────────────

from rest_framework.permissions import BasePermission, IsAuthenticated


class IsTenantActive(BasePermission):
    """
    Allows access only when request.tenant is set and is_active=True.
    Used as a base guard on all /mobile/ API views.
    """

    message = "This tenant account is inactive. Contact support."

    def has_permission(self, request, view):
        tenant = getattr(request, "tenant", None)
        if tenant is None:
            return False
        return bool(tenant.is_active)


class IsTenantAuthenticated(IsAuthenticated, IsTenantActive):
    """
    Composite permission: user must be authenticated AND tenant must be active.
    Use this instead of plain IsAuthenticated on mobile API views.
    """
    pass


class IsTenantFeatureEnabled(BasePermission):
    """
    Checks whether the current tenant has a specific feature enabled.

    Usage on a view:
        required_feature = "whatsapp_api"
        permission_classes = [IsTenantAuthenticated, IsTenantFeatureEnabled]
    """

    message = "Your current plan does not include this feature."

    def has_permission(self, request, view):
        required_feature = getattr(view, "required_feature", None)
        if required_feature is None:
            return True  # No feature gate declared on this view

        tenant = getattr(request, "tenant", None)
        if tenant is None:
            return False
        return tenant.has_feature(required_feature)


class IsTenantStaff(BasePermission):
    """
    Allows access only to agents with 'admin' or 'manager' roles
    within the current tenant schema.
    """

    message = "Staff access required for this tenant."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
            
        # Check AgentProfile role in current schema
        from agents.models import AgentProfile
        try:
            profile = request.user.agent_profile
            return profile.role in ['admin', 'manager']
        except AgentProfile.DoesNotExist:
            return False
