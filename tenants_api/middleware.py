# tenants_api/middleware.py
# ─────────────────────────────────────────────────────────────────────────────
# CentralApiTenantMiddleware
#
# Intercepts requests arriving at api.dialeasy.easyian.com/mobile/...
# and switches the PostgreSQL schema to the correct tenant — WITHOUT relying
# on the subdomain (which is how TenantMainMiddleware normally does it).
#
# Tenant resolution priority (highest → lowest):
#   1. JWT access token claim  `tenant_slug`   (authenticated requests)
#   2. Request header          `X-Tenant-Slug` (pre-auth / login)
#   3. POST body field         `tenant_slug`   (login form fallback)
#   4. Query parameter         `?tenant=demo`  (webhook / deep-link fallback)
#
# This middleware runs AFTER TenantMainMiddleware in the stack.
# TenantMainMiddleware already mapped api.dialeasy.easyian.com → public schema.
# This middleware then switches to the real tenant schema.
# ─────────────────────────────────────────────────────────────────────────────

import json
import logging

from django.db import connection
from django.http import JsonResponse

logger = logging.getLogger(__name__)

# URL prefix that activates this middleware.
# All requests to /mobile/... go through tenant resolution.
MOBILE_API_PREFIX = "/mobile/"


def _extract_tenant_slug_from_jwt(request) -> str | None:
    """
    Peek at the Authorization header and decode the JWT payload
    WITHOUT fully validating the signature (validation happens later in
    JWTTenantAuthentication). We just need the tenant_slug claim here
    so we can switch the schema before the view runs.

    Safe because:
    - We only READ the tenant slug (which is low-sensitivity public info)
    - Full token validation + user authentication still happens in
      JWTTenantAuthentication before any data is returned
    """
    auth_header = request.META.get("HTTP_AUTHORIZATION", "")
    if not auth_header.startswith("Bearer "):
        return None

    token = auth_header.split(" ", 1)[1]
    try:
        import base64
        # JWT is three base64url-encoded segments: header.payload.signature
        payload_b64 = token.split(".")[1]
        # base64url → base64 (pad to multiple of 4)
        padding = 4 - len(payload_b64) % 4
        payload_b64 += "=" * (padding % 4)
        payload_bytes = base64.urlsafe_b64decode(payload_b64)
        payload = json.loads(payload_bytes)
        return payload.get("tenant_slug")
    except Exception:
        return None


def _extract_tenant_slug_from_body(request) -> str | None:
    """
    Try to read tenant_slug from the JSON POST body.
    Only attempts this for POST requests with JSON content type.
    Caches the parsed body so the view can still read it.
    """
    if request.method != "POST":
        return None
    content_type = request.META.get("CONTENT_TYPE", "")
    if "application/json" not in content_type:
        return None
    try:
        body = json.loads(request.body)
        return body.get("tenant_slug") or body.get("workspace") or body.get("company_code")
    except Exception:
        return None


class CentralApiTenantMiddleware:
    """
    Schema-switching middleware for the centralised API domain.

    Only activates for paths that start with MOBILE_API_PREFIX (/mobile/).
    All other paths are left untouched (the existing TenantMainMiddleware
    handles subdomain-based requests as before).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Only intercept /mobile/ routes
        if not request.path.startswith(MOBILE_API_PREFIX):
            return self.get_response(request)

        tenant_slug = self._resolve_tenant_slug(request)

        if tenant_slug:
            tenant = self._get_tenant(tenant_slug)
            if tenant is None:
                return JsonResponse(
                    {
                        "error": "invalid_tenant",
                        "detail": f"No active tenant found for slug '{tenant_slug}'. "
                                  "Check the tenant_slug / X-Tenant-Slug value.",
                    },
                    status=400,
                )
            if not tenant.is_active:
                return JsonResponse(
                    {
                        "error": "tenant_inactive",
                        "detail": "This tenant account is currently inactive. "
                                  "Contact support.",
                    },
                    status=403,
                )
            # ── Switch PostgreSQL schema ─────────────────────────────────────
            connection.set_tenant(tenant)
            request.tenant = tenant
            logger.debug(
                "CentralApiTenantMiddleware: schema switched to '%s' for path '%s'",
                tenant.schema_name,
                request.path,
            )
        else:
            # /mobile/auth/login/ is the only endpoint that legitimately
            # arrives without a token — but it MUST provide tenant_slug in body.
            # Any other unauthenticated /mobile/ call without a slug is rejected.
            is_login = request.path.rstrip("/").endswith("/auth/login") or \
                       request.path.rstrip("/").endswith("/auth/token")
            if not is_login:
                return JsonResponse(
                    {
                        "error": "tenant_required",
                        "detail": "Tenant identifier required. Provide 'X-Tenant-Slug' "
                                  "header, a valid JWT Bearer token, or 'tenant_slug' "
                                  "in the request body.",
                    },
                    status=400,
                )
            # Login endpoint without slug — let TenantLoginView handle the error
            # (it will validate tenant_slug from the body with a nicer message)

        response = self.get_response(request)
        return response

    # ── Private helpers ───────────────────────────────────────────────────────

    def _resolve_tenant_slug(self, request) -> str | None:
        """Try every source in priority order and return the first non-empty slug."""
        return (
            _extract_tenant_slug_from_jwt(request)
            or request.META.get("HTTP_X_TENANT_SLUG", "").strip()
            or _extract_tenant_slug_from_body(request)
            or request.GET.get("tenant", "").strip()
        )

    def _get_tenant(self, slug: str):
        """
        Look up the Client (tenant) by schema_name.
        Always queries the PUBLIC schema — no schema switch needed here
        because TenantMainMiddleware already set us to 'public'.
        """
        from tenants.models import Client
        try:
            return Client.objects.get(schema_name=slug, is_active=True)
        except Client.DoesNotExist:
            logger.warning(
                "CentralApiTenantMiddleware: tenant slug '%s' not found.", slug
            )
            return None
