# tenants/models.py
# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC SCHEMA MODELS — these live in the shared (public) PostgreSQL schema.
# They are visible to ALL tenants and the super admin.
# ─────────────────────────────────────────────────────────────────────────────

from django.db import models
from django.contrib.auth.models import User
from django_tenants.models import TenantMixin, DomainMixin
from django.utils import timezone


# ─── Feature ─────────────────────────────────────────────────────────────────

class Feature(models.Model):
    """
    Represents a single CRM feature that can be included in a Plan.
    Super admin manages this list.

    Examples:
        whatsapp_api, ai_chatbot, call_recording, email_ai,
        ai_transcription, advanced_reports, bulk_broadcast
    """
    name = models.CharField(max_length=100)
    slug = models.SlugField(
        max_length=100,
        unique=True,
        help_text='Machine-readable key used in @require_feature decorator and Flutter feature checks. e.g. whatsapp_api'
    )
    description = models.TextField(blank=True)
    is_active = models.BooleanField(
        default=True,
        help_text='Inactive features are hidden from all plans globally.'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'tenants'
        ordering = ['name']
        verbose_name = 'Feature'
        verbose_name_plural = 'Features'

    def __str__(self):
        return f'{self.name} ({self.slug})'


# ─── Plan ─────────────────────────────────────────────────────────────────────

class Plan(models.Model):
    """
    A subscription plan (e.g. Free, Starter, Pro, Enterprise).
    Super admin creates plans and assigns features to them.
    """
    BILLING_CYCLE_CHOICES = [
        ('monthly', 'Monthly'),
        ('annual', 'Annual'),
    ]

    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    price_monthly = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    price_annual = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    max_agents = models.IntegerField(
        default=5,
        help_text='Maximum number of agent accounts allowed for this plan. -1 = unlimited.'
    )
    max_leads = models.IntegerField(
        default=1000,
        help_text='Maximum leads per tenant. -1 = unlimited.'
    )
    is_active = models.BooleanField(default=True)
    is_public = models.BooleanField(
        default=True,
        help_text='Public plans show on the pricing page. Private plans are enterprise-only.'
    )
    sort_order = models.IntegerField(default=0)
    features = models.ManyToManyField(
        Feature,
        blank=True,
        related_name='plans',
        help_text='Features included in this plan.'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'tenants'
        ordering = ['sort_order', 'price_monthly']
        verbose_name = 'Plan'
        verbose_name_plural = 'Plans'

    def __str__(self):
        return self.name

    def get_feature_slugs(self):
        """Returns a set of feature slugs included in this plan."""
        return set(self.features.filter(is_active=True).values_list('slug', flat=True))


# ─── Client (Tenant) ──────────────────────────────────────────────────────────

class Client(TenantMixin):
    """
    Represents one tenant (a company that subscribes to TeleCRM).
    Each Client gets its own isolated PostgreSQL schema.

    TenantMixin provides:
        schema_name  — the PostgreSQL schema name (e.g. 'acme')
        auto_create_schema — set True to create schema on save
    """
    name = models.CharField(max_length=200, help_text='Company / Organisation name')
    owner_email = models.EmailField(help_text='Primary contact email of the tenant owner')
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    logo = models.ImageField(upload_to='tenant_logos/', null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Super-admin override: set a custom agent limit for this tenant, regardless of plan.
    # Leave blank (null) to fall back to the plan's max_agents value.
    max_agents_override = models.IntegerField(
        null=True,
        blank=True,
        help_text=(
            'Custom max agent limit for this tenant. '
            'Overrides the Plan\'s max_agents value. '
            'Leave blank to use the Plan\'s limit. '
            'Set to -1 for unlimited.'
        )
    )

    # TenantMixin requires this
    auto_create_schema = True

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        # Auto-fix schema name to be PostgreSQL compatible
        if self.schema_name:
            import re
            # Lowercase and replace non-alphanumeric with underscores
            self.schema_name = re.sub(r'[^a-z0-9_]', '_', self.schema_name.lower())
            # Ensure it starts with a letter
            if self.schema_name and not self.schema_name[0].isalpha():
                self.schema_name = 't_' + self.schema_name
        
        super().save(*args, **kwargs)

        # If it's a new tenant, automatically create an admin user for them
        if is_new and self.schema_name != 'public':
            import secrets
            import logging
            from django_tenants.utils import schema_context
            from django.contrib.auth.models import User

            logger = logging.getLogger(__name__)

            with schema_context(self.schema_name):
                # ── Create tenant admin user ──────────────────────────────────
                admin_username = f"admin_{self.schema_name}"
                if not User.objects.filter(username=admin_username).exists():
                    temp_password = secrets.token_urlsafe(16)
                    user = User.objects.create_user(
                        username=admin_username,
                        email=self.owner_email,
                        password=temp_password,
                        is_staff=True,
                        is_superuser=False
                    )
                    from agents.models import AgentProfile
                    AgentProfile.objects.create(
                        user=user,
                        role='admin',
                        is_active=True
                    )
                    logger.warning(
                        "New tenant '%s' created. Temporary admin credentials — "
                        "username: %s  password: %s  — share securely and require a reset.",
                        self.name, admin_username, temp_password
                    )

                # ── Seed default dispositions for this tenant ─────────────────
                from leads.models import Disposition
                DEFAULT_DISPOSITIONS = [
                    ('interested',     'Interested',         'success', 1,  True,  'interested'),
                    ('callback',       'Callback Later',      'warning', 2,  True,  'callback'),
                    ('not_interested', 'Not Interested',      'danger',  3,  False, 'not_interested'),
                    ('not_reachable',  'Not Reachable',       'default', 4,  False, ''),
                    ('busy',           'Busy',                'default', 5,  False, ''),
                    ('wrong_number',   'Wrong Number',        'danger',  6,  False, ''),
                    ('voicemail',      'Voicemail',           'info',    7,  False, ''),
                    ('follow_up',      'Follow-up Required',  'warning', 8,  True,  ''),
                ]
                for value, label, color, sort_order, triggers_follow_up, updates_lead_status in DEFAULT_DISPOSITIONS:
                    Disposition.objects.get_or_create(
                        value=value,
                        defaults={
                            'label': label, 'color': color, 'sort_order': sort_order,
                            'is_active': True, 'triggers_follow_up': triggers_follow_up,
                            'updates_lead_status': updates_lead_status,
                        }
                    )

    class Meta:
        app_label = 'tenants'
        verbose_name = 'Tenant'
        verbose_name_plural = 'Tenants'

    def __str__(self):
        return self.name

    @property
    def active_subscription(self):
        return self.subscriptions.filter(is_active=True).select_related('plan').first()

    @property
    def current_plan(self):
        sub = self.active_subscription
        return sub.plan if sub else None

    @property
    def effective_agent_limit(self) -> int:
        """
        Returns the effective max agents limit for this tenant.
        Priority: tenant-level override > plan limit > fallback of 5.
        Returns -1 for unlimited.
        """
        if self.max_agents_override is not None:
            return self.max_agents_override
        plan = self.current_plan
        if plan is not None:
            return plan.max_agents
        return 5  # Sensible fallback when no plan is assigned

    def has_feature(self, feature_slug: str) -> bool:
        """Check if this tenant's active plan includes the given feature slug."""
        plan = self.current_plan
        if plan is None:
            return False
        return feature_slug in plan.get_feature_slugs()

    def get_enabled_features(self):
        """Return list of feature slugs enabled for this tenant."""
        plan = self.current_plan
        if plan is None:
            return []
        return list(plan.get_feature_slugs())


# ─── Domain ───────────────────────────────────────────────────────────────────

class Domain(DomainMixin):
    """
    Maps a hostname/subdomain to a tenant.
    DomainMixin provides:
        tenant (FK to Client)
        domain  (the hostname string, e.g. 'acme.telecrm.com')
        is_primary (bool)
    """
    class Meta:
        app_label = 'tenants'
        verbose_name = 'Domain'
        verbose_name_plural = 'Domains'

    def __str__(self):
        return self.domain


# ─── TenantSubscription ───────────────────────────────────────────────────────

class TenantSubscription(models.Model):
    """
    Links a tenant to a plan with billing lifecycle tracking.
    """
    BILLING_CYCLE_CHOICES = [
        ('monthly', 'Monthly'),
        ('annual', 'Annual'),
    ]
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('trialing', 'Trialing'),
        ('past_due', 'Past Due'),
        ('cancelled', 'Cancelled'),
        ('expired', 'Expired'),
    ]

    tenant = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='subscriptions')
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name='subscriptions')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='trialing')
    billing_cycle = models.CharField(max_length=10, choices=BILLING_CYCLE_CHOICES, default='monthly')
    is_active = models.BooleanField(default=True)
    trial_ends_at = models.DateTimeField(null=True, blank=True)
    current_period_start = models.DateTimeField(default=timezone.now)
    current_period_end = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, help_text='Internal super-admin notes about this subscription.')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'tenants'
        ordering = ['-created_at']
        verbose_name = 'Tenant Subscription'
        verbose_name_plural = 'Tenant Subscriptions'

    def __str__(self):
        return f'{self.tenant.name} → {self.plan.name} ({self.status})'

    @property
    def is_expired(self):
        if self.current_period_end:
            return timezone.now() > self.current_period_end
        return False

