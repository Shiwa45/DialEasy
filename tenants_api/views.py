# tenants_api/views.py
# ─────────────────────────────────────────────────────────────────────────────
# Views for the centralised mobile API gateway.
#
# All views here live under /mobile/ prefix on api.dialeasy.easyian.com.
# The CentralApiTenantMiddleware has already switched the DB schema by
# the time any view runs (for authenticated requests), so view code can
# query the tenant's data transparently via normal Django ORM.
# ─────────────────────────────────────────────────────────────────────────────

import logging

from django.contrib.auth.models import User
from django.db import connection
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from .authentication import JWTTenantAuthentication
from .permissions import IsTenantAuthenticated, IsTenantActive
from .serializers import (
    TenantLoginSerializer,
    TenantInfoSerializer,
    MobileUserProfileSerializer,
    generate_tokens_for_user,
)

logger = logging.getLogger(__name__)


# ── Health Check ──────────────────────────────────────────────────────────────

@api_view(["GET"])
@permission_classes([AllowAny])
@authentication_classes([])
def health_check(request):
    """
    GET /mobile/health/
    Public endpoint. Returns 200 to confirm the API gateway is reachable.
    """
    return Response(
        {
            "status": "ok",
            "api": "DialEasy Centralised API",
            "version": "2.0",
        }
    )


# ── Tenant Login (JWT) ────────────────────────────────────────────────────────

class TenantLoginView(APIView):
    """
    POST /mobile/auth/login/

    Authenticates a user against a specific tenant's schema and returns a JWT
    pair with tenant context embedded in the payload.

    Request body:
        {
            "username": "john.doe",
            "password": "secret",
            "tenant_slug": "demo"          ← OR use X-Tenant-Slug header
            // Aliases also accepted:
            // "workspace": "demo"
            // "company_code": "demo"
        }

    Response:
        {
            "access":  "<jwt_access_token>",
            "refresh": "<jwt_refresh_token>",
            "token_type": "Bearer",
            "access_expires_in":  900,     ← seconds
            "refresh_expires_in": 86400,
            "user": { "id": 1, "username": "...", ... },
            "tenant": { "schema_name": "demo", "name": "Demo Corp", ... }
        }
    """

    permission_classes = [AllowAny]
    authentication_classes = []  # No auth required — this IS the auth endpoint

    def post(self, request):
        # If the middleware already resolved tenant from header and set it,
        # inject that slug into the data so the serializer can use it.
        data = request.data.copy()
        if not data.get("tenant_slug") and hasattr(request, "tenant"):
            data["tenant_slug"] = request.tenant.schema_name

        serializer = TenantLoginSerializer(
            data=data, context={"request": request}
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user   = serializer.validated_data["user"]
        tenant = serializer.validated_data["tenant"]

        tokens = generate_tokens_for_user(user, tenant)

        return Response(
            {
                **tokens,
                "user":   MobileUserProfileSerializer(user).data,
                "tenant": TenantInfoSerializer(tenant, context={"request": request}).data,
            },
            status=status.HTTP_200_OK,
        )


# ── JWT Token Refresh (tenant-aware) ─────────────────────────────────────────

class TenantTokenRefreshView(APIView):
    """
    POST /mobile/auth/refresh/

    Refresh an access token using a refresh token.
    The tenant_slug from the original refresh token is preserved.

    Request body:
        { "refresh": "<refresh_token>" }

    Response:
        { "access": "<new_access_token>", "token_type": "Bearer" }
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response(
                {"error": "refresh_token_required", "detail": "Provide a 'refresh' token."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            token = RefreshToken(refresh_token)
            access = token.access_token

            # Preserve all custom claims from refresh → access
            for claim in ("tenant_slug", "tenant_name", "username", "is_staff", "features"):
                if claim in token:
                    access[claim] = token[claim]

            return Response(
                {
                    "access": str(access),
                    "token_type": "Bearer",
                },
                status=status.HTTP_200_OK,
            )
        except TokenError as e:
            return Response(
                {"error": "token_invalid", "detail": str(e)},
                status=status.HTTP_401_UNAUTHORIZED,
            )


# ── JWT Logout (token blacklist) ──────────────────────────────────────────────

class TenantLogoutView(APIView):
    """
    POST /mobile/auth/logout/

    Blacklists the refresh token so it can no longer be used.
    Requires simplejwt BLACKLIST app to be installed (see settings).

    Request body:
        { "refresh": "<refresh_token>" }
    """

    authentication_classes = [JWTTenantAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response(
                {"error": "refresh_token_required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response(
                {"detail": "Successfully logged out."},
                status=status.HTTP_200_OK,
            )
        except TokenError as e:
            return Response(
                {"error": "token_invalid", "detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )


# ── Current User Profile ──────────────────────────────────────────────────────

class MobileProfileView(APIView):
    """
    GET  /mobile/auth/profile/   — returns user + tenant info
    PATCH /mobile/auth/profile/  — updates first_name, last_name, email
    """

    authentication_classes = [JWTTenantAuthentication]
    permission_classes = [IsTenantAuthenticated]

    def get(self, request):
        user   = request.user
        tenant = request.tenant
        return Response(
            {
                "user":   MobileUserProfileSerializer(user).data,
                "tenant": TenantInfoSerializer(tenant, context={"request": request}).data,
            }
        )

    def patch(self, request):
        user = request.user
        allowed_fields = {"first_name", "last_name", "email"}
        data = {k: v for k, v in request.data.items() if k in allowed_fields}

        for field, value in data.items():
            setattr(user, field, value)
        user.save(update_fields=list(data.keys()))

        return Response(MobileUserProfileSerializer(user).data)


# ── Tenant Info (for mobile splash / onboarding) ──────────────────────────────

@api_view(["GET"])
@permission_classes([AllowAny])
@authentication_classes([])
def tenant_info_public(request):
    """
    GET /mobile/tenant/info/?tenant=demo
    OR with header: X-Tenant-Slug: demo

    Public endpoint — called by mobile app BEFORE login to show tenant
    branding (logo, name, plan) on the login screen.
    """
    slug = (
        request.GET.get("tenant", "")
        or request.META.get("HTTP_X_TENANT_SLUG", "")
    ).strip()

    if not slug:
        return Response(
            {"error": "tenant_required", "detail": "Provide ?tenant=<slug> or X-Tenant-Slug header."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    from tenants.models import Client
    try:
        tenant = Client.objects.get(schema_name=slug)
    except Client.DoesNotExist:
        return Response(
            {"error": "not_found", "detail": f"No tenant with slug '{slug}'."},
            status=status.HTTP_404_NOT_FOUND,
        )

    return Response(
        TenantInfoSerializer(tenant, context={"request": request}).data
    )


# ── Tenant-aware proxy views for existing API endpoints ───────────────────────
# These thin wrapper views call the real logic in api/views.py
# after the middleware has already switched the schema.
# This lets mobile use the centralised domain without duplicating
# any business logic.

@api_view(["GET"])
@authentication_classes([JWTTenantAuthentication])
@permission_classes([IsTenantAuthenticated])
def mobile_agent_dashboard(request):
    """
    GET /mobile/api/agent/dashboard/

    Delegates to the existing agent_dashboard view in api/views.py.
    Schema is already set by middleware + JWT auth.
    """
    from api.views import agent_dashboard
    return agent_dashboard(request)


@api_view(["GET"])
@authentication_classes([JWTTenantAuthentication])
@permission_classes([IsTenantAuthenticated])
def mobile_app_config(request):
    """
    GET /mobile/api/utils/app-config/

    Returns app configuration for the current tenant.
    Delegates to api/views.py::app_config.
    """
    from api.views import app_config
    return app_config(request)
