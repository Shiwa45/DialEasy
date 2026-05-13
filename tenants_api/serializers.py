# tenants_api/serializers.py
# ─────────────────────────────────────────────────────────────────────────────
# Serializers for the centralised tenant API.
# ─────────────────────────────────────────────────────────────────────────────

from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken


# ── Tenant Login ──────────────────────────────────────────────────────────────

class TenantLoginSerializer(serializers.Serializer):
    """
    Validates credentials + tenant_slug and returns a JWT pair.

    Fields:
        username     — Django username
        password     — Django password
        tenant_slug  — The Client.schema_name value (e.g. "demo")
                       Also accepts `workspace` or `company_code` as aliases.
    """

    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, style={"input_type": "password"})
    tenant_slug = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
        help_text="Tenant schema name / workspace slug (e.g. 'demo'). "
                  "Also accepted via X-Tenant-Slug header.",
    )
    # Aliases for tenant_slug — mobile devs sometimes use different names
    workspace    = serializers.CharField(max_length=100, required=False, allow_blank=True, write_only=True)
    company_code = serializers.CharField(max_length=100, required=False, allow_blank=True, write_only=True)

    def validate(self, attrs):
        # Resolve tenant_slug from any alias
        tenant_slug = (
            attrs.get("tenant_slug")
            or attrs.get("workspace")
            or attrs.get("company_code")
            or ""
        ).strip()

        if not tenant_slug:
            raise serializers.ValidationError(
                {"tenant_slug": "Tenant identifier is required. Provide 'tenant_slug', 'workspace', or 'company_code'."}
            )

        # ── Fetch tenant (public schema) ──────────────────────────────────────
        from tenants.models import Client
        try:
            tenant = Client.objects.get(schema_name=tenant_slug)
        except Client.DoesNotExist:
            raise serializers.ValidationError(
                {"tenant_slug": f"No tenant found with slug '{tenant_slug}'."}
            )

        if not tenant.is_active:
            raise serializers.ValidationError(
                {"tenant_slug": "This tenant account is inactive. Contact support."}
            )

        # ── Switch to tenant schema and authenticate user ─────────────────────
        from django.db import connection
        connection.set_tenant(tenant)

        user = authenticate(
            request=self.context.get("request"),
            username=attrs["username"],
            password=attrs["password"],
        )
        if user is None:
            raise serializers.ValidationError(
                {"non_field_errors": "Invalid username or password."}
            )
        if not user.is_active:
            raise serializers.ValidationError(
                {"non_field_errors": "This user account has been disabled."}
            )

        # ── Verify Membership (Is the user actually in this tenant?) ──────────
        from agents.models import AgentProfile
        if not AgentProfile.objects.filter(user=user).exists():
            raise serializers.ValidationError(
                {"non_field_errors": f"Access denied. You are not a member of '{tenant.name}'."}
            )

        attrs["user"]        = user
        attrs["tenant"]      = tenant
        attrs["tenant_slug"] = tenant_slug
        return attrs


# ── Custom JWT Token with tenant claims ───────────────────────────────────────

class TenantTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Extends SimpleJWT's token serializer to embed tenant context into the JWT.
    The resulting access token payload looks like:

    {
        "token_type": "access",
        "exp": ...,
        "user_id": 42,
        "username": "john.doe",
        "tenant_slug": "demo",
        "tenant_name": "Demo Corp",
        "is_staff": false,
        "features": ["whatsapp_api", "ai_chatbot"]
    }
    """

    @classmethod
    def get_token(cls, user, tenant=None):
        token = super().get_token(user)

        # Standard claims
        token["username"] = user.username
        token["is_staff"] = user.is_staff

        # Tenant claims — added when tenant context is available
        if tenant:
            token["tenant_slug"] = tenant.schema_name
            token["tenant_name"] = tenant.name
            # Embed enabled features so mobile doesn't need a separate call
            token["features"] = tenant.get_enabled_features()

        return token


def generate_tokens_for_user(user, tenant) -> dict:
    """
    Generate a JWT access + refresh token pair with tenant claims embedded.
    Called by TenantLoginView after successful authentication.
    """
    refresh = TenantTokenObtainPairSerializer.get_token(user, tenant=tenant)
    return {
        "refresh": str(refresh),
        "access":  str(refresh.access_token),
        "token_type": "Bearer",
        "access_expires_in":  int(refresh.access_token.lifetime.total_seconds()),
        "refresh_expires_in": int(refresh.lifetime.total_seconds()),
    }


# ── Tenant Info ───────────────────────────────────────────────────────────────

class TenantInfoSerializer(serializers.Serializer):
    """Read-only serializer for tenant metadata returned to mobile on login."""

    schema_name  = serializers.CharField()
    name         = serializers.CharField()
    owner_email  = serializers.EmailField()
    is_active    = serializers.BooleanField()
    logo         = serializers.SerializerMethodField()
    current_plan = serializers.SerializerMethodField()
    features     = serializers.SerializerMethodField()

    def get_logo(self, obj):
        request = self.context.get("request")
        if obj.logo and request:
            return request.build_absolute_uri(obj.logo.url)
        return None

    def get_current_plan(self, obj):
        plan = obj.current_plan
        if plan:
            return {"name": plan.name, "slug": plan.slug}
        return None

    def get_features(self, obj):
        return obj.get_enabled_features()


# ── User Profile ──────────────────────────────────────────────────────────────

class MobileUserProfileSerializer(serializers.ModelSerializer):
    """Minimal user profile for mobile app."""

    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "last_name", "full_name", "is_staff"]

    def get_full_name(self, obj):
        return obj.get_full_name() or obj.username
