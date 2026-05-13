# tenants_api/authentication.py
# ─────────────────────────────────────────────────────────────────────────────
# JWTTenantAuthentication
#
# Extends SimpleJWT's standard JWTAuthentication with tenant-awareness:
#   1. Validates the JWT signature and expiry (standard SimpleJWT behaviour)
#   2. Extracts `tenant_slug` from the verified payload
#   3. Re-switches the PostgreSQL schema (belt-and-suspenders — the middleware
#      already did this, but authentication may run in contexts where the
#      middleware didn't fire, e.g. DRF browsable API)
#   4. Validates the user exists in THAT tenant's schema
#   5. Returns (user, validated_token) — standard DRF auth contract
# ─────────────────────────────────────────────────────────────────────────────

import logging

from django.db import connection
from rest_framework import exceptions
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

logger = logging.getLogger(__name__)


class JWTTenantAuthentication(JWTAuthentication):
    """
    Drop-in replacement for JWTAuthentication that also enforces
    tenant schema isolation.

    Usage in settings.py:
        REST_FRAMEWORK = {
            'DEFAULT_AUTHENTICATION_CLASSES': [
                'tenants_api.authentication.JWTTenantAuthentication',
                'rest_framework.authentication.SessionAuthentication',  # web fallback
            ],
        }
    """

    def authenticate(self, request):
        # Let SimpleJWT do its normal header + token extraction
        result = super().authenticate(request)
        if result is None:
            # No Authorization header — not our problem, let other auth classes try
            return None

        user, validated_token = result

        # ── Extract tenant_slug from the verified payload ─────────────────────
        tenant_slug = validated_token.get("tenant_slug")
        if not tenant_slug:
            raise exceptions.AuthenticationFailed(
                "JWT payload is missing 'tenant_slug' claim. "
                "Please log in again via /mobile/auth/login/."
            )

        # ── Re-switch schema (idempotent if middleware already did it) ────────
        tenant = self._get_and_switch_tenant(tenant_slug)

        # ── Verify Membership (Belt and suspenders) ──────────────────────────
        from agents.models import AgentProfile
        if not AgentProfile.objects.filter(user=user).exists():
            raise exceptions.AuthenticationFailed(
                f"You are no longer a member of tenant '{tenant_slug}'."
            )

        # ── Attach tenant to request for use in views ─────────────────────────
        request.tenant = tenant

        logger.debug(
            "JWTTenantAuthentication: authenticated user '%s' in schema '%s'",
            user.username,
            tenant.schema_name,
        )
        return (user, validated_token)

    # ── Private helpers ───────────────────────────────────────────────────────

    def _get_and_switch_tenant(self, slug: str):
        from tenants.models import Client
        from django_tenants.utils import schema_context

        try:
            # Client lives in the public schema — temporarily switch there to look it up,
            # then switch to the real tenant schema below.
            with schema_context("public"):
                tenant = Client.objects.get(schema_name=slug)
        except Client.DoesNotExist:
            raise exceptions.AuthenticationFailed(
                f"Tenant '{slug}' in JWT token no longer exists. Re-authenticate."
            )

        if not tenant.is_active:
            raise exceptions.AuthenticationFailed(
                f"Tenant '{slug}' is inactive. Contact support."
            )

        # Switch the DB connection to the tenant's schema for the remainder
        # of this request. This is idempotent — middleware may have already done it.
        connection.set_tenant(tenant)
        return tenant
