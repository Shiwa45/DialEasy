# tenants/admin.py
# ─────────────────────────────────────────────────────────────────────────────
# Super Admin site — only accessible by is_superuser users.
# Uses a SEPARATE AdminSite instance so tenant admins NEVER see these models.
#
# Previous approach used `if connection.schema_name == get_public_schema_name()`
# at module import time, which always evaluated True at Django startup and
# registered super-admin models into the shared admin.site — making them
# visible to all tenant admins. That check has been removed entirely.
# ─────────────────────────────────────────────────────────────────────────────

from django.contrib.admin import AdminSite
from django.contrib import admin
from django.utils.html import format_html
from .models import Client, Domain, Plan, Feature, TenantSubscription


# ─── Super Admin Site ────────────────────────────────────────────────────────

class SuperAdminSite(AdminSite):
    """
    Separate admin site for platform-level management.
    Only users with is_superuser=True can log in here.
    Tenant admins (is_staff=True, is_superuser=False) are blocked at the gate.
    """
    site_header = 'DialEasy Super Admin'
    site_title = 'DialEasy Super Admin'
    index_title = 'Tenant & Plan Management'

    def has_permission(self, request):
        return request.user.is_active and request.user.is_superuser


super_admin_site = SuperAdminSite(name='super_admin')


# ─── Feature Admin ────────────────────────────────────────────────────────────

class FeatureAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'is_active', 'plans_count', 'updated_at']
    list_filter = ['is_active']
    search_fields = ['name', 'slug', 'description']
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('Feature Details', {
            'fields': ('name', 'slug', 'description', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def plans_count(self, obj):
        count = obj.plans.count()
        return format_html('<span style="color: #1D9E75; font-weight: bold;">{}</span>', count)
    plans_count.short_description = 'Used in Plans'


# ─── Plan Admin ───────────────────────────────────────────────────────────────

class FeatureInline(admin.TabularInline):
    model = Plan.features.through
    extra = 1
    verbose_name = 'Included Feature'
    verbose_name_plural = 'Included Features'


class PlanAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'slug', 'price_monthly', 'price_annual',
        'max_agents', 'max_leads', 'feature_count',
        'active_subscribers', 'is_active', 'is_public', 'sort_order'
    ]
    list_filter = ['is_active', 'is_public']
    search_fields = ['name', 'slug', 'description']
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ['created_at', 'updated_at']
    filter_horizontal = ['features']

    fieldsets = (
        ('Plan Details', {
            'fields': ('name', 'slug', 'description', 'sort_order')
        }),
        ('Pricing', {
            'fields': ('price_monthly', 'price_annual')
        }),
        ('Limits', {
            'fields': ('max_agents', 'max_leads')
        }),
        ('Features Included', {
            'fields': ('features',),
            'description': 'Select which features are available in this plan.'
        }),
        ('Visibility', {
            'fields': ('is_active', 'is_public')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def feature_count(self, obj):
        return obj.features.filter(is_active=True).count()
    feature_count.short_description = 'Features'

    def active_subscribers(self, obj):
        count = obj.subscriptions.filter(is_active=True).count()
        return format_html('<span style="font-weight: bold;">{}</span>', count)
    active_subscribers.short_description = 'Active Tenants'


# ─── Subscription Inline ──────────────────────────────────────────────────────

class TenantSubscriptionInline(admin.StackedInline):
    model = TenantSubscription
    extra = 0
    readonly_fields = ['created_at', 'updated_at']
    fields = [
        'plan', 'status', 'billing_cycle', 'is_active',
        'trial_ends_at', 'current_period_start', 'current_period_end',
        'notes', 'created_at', 'updated_at'
    ]


# ─── Domain Inline ───────────────────────────────────────────────────────────

class DomainInline(admin.TabularInline):
    model = Domain
    extra = 1
    fields = ['domain', 'is_primary']


# ─── Client (Tenant) Admin ───────────────────────────────────────────────────

class ClientAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'schema_name', 'owner_email',
        'current_plan_display', 'subscription_status',
        'agent_limit_display', 'feature_addons_display',
        'is_active', 'created_at'
    ]
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'schema_name', 'owner_email']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [DomainInline, TenantSubscriptionInline]

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return self.readonly_fields + ['schema_name']
        return self.readonly_fields

    filter_horizontal = ['extra_features']

    fieldsets = (
        ('Tenant Information', {
            'fields': ('name', 'schema_name', 'owner_email', 'phone', 'address', 'logo', 'is_active')
        }),
        ('Agent Limit Override', {
            'fields': ('max_agents_override',),
            'description': (
                'Set a custom agent limit for this tenant that overrides the plan\'s default. '
                'Leave blank to use the plan limit. Set -1 for unlimited.'
            ),
        }),
        ('Feature Add-ons', {
            'fields': ('extra_features',),
            'description': (
                'Grant specific features directly to this tenant, on top of their plan. '
                'Use this to enable premium features (e.g. bulk_whatsapp) per tenant '
                'without upgrading their entire plan.'
            ),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def current_plan_display(self, obj):
        plan = obj.current_plan
        if plan:
            return format_html('<span style="color: #185FA5; font-weight: bold;">{}</span>', plan.name)
        return format_html('<span style="color: #A32D2D;">No Plan</span>')
    current_plan_display.short_description = 'Current Plan'

    def subscription_status(self, obj):
        sub = obj.active_subscription
        if not sub:
            return format_html('<span style="color: #A32D2D;">No Subscription</span>')
        colors = {
            'active': '#1D9E75',
            'trialing': '#BA7517',
            'past_due': '#D85A30',
            'cancelled': '#A32D2D',
            'expired': '#888780',
        }
        color = colors.get(sub.status, '#888780')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, sub.get_status_display()
        )
    subscription_status.short_description = 'Subscription'

    def feature_addons_display(self, obj):
        addons = list(obj.extra_features.filter(is_active=True).values_list('slug', flat=True))
        if not addons:
            return format_html('<span style="color:#94A3B8;font-size:11px;">none</span>')
        badges = ' '.join(
            format_html('<span style="background:#E0F2FE;color:#0369A1;padding:1px 6px;border-radius:10px;font-size:10px;">{}</span>', s)
            for s in addons
        )
        return format_html(badges)
    feature_addons_display.short_description = 'Add-on Features'

    def agent_limit_display(self, obj):
        limit = obj.effective_agent_limit
        override = obj.max_agents_override
        if limit == -1:
            label = 'Unlimited'
            color = '#1D9E75'
        else:
            label = str(limit)
            color = '#185FA5'
        tag = format_html('<span style="font-weight:bold;color:{}">{}</span>', color, label)
        if override is not None:
            tag = format_html('{} <span style="font-size:10px;color:#BA7517;">(override)</span>', tag)
        return tag
    agent_limit_display.short_description = 'Agent Limit'


# ─── Subscription Admin ───────────────────────────────────────────────────────

class TenantSubscriptionAdmin(admin.ModelAdmin):
    list_display = [
        'tenant', 'plan', 'status', 'billing_cycle',
        'is_active', 'current_period_start', 'current_period_end'
    ]
    list_filter = ['status', 'billing_cycle', 'is_active', 'plan']
    search_fields = ['tenant__name', 'plan__name']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['tenant', 'plan']

    fieldsets = (
        ('Subscription Details', {
            'fields': ('tenant', 'plan', 'status', 'billing_cycle', 'is_active')
        }),
        ('Billing Period', {
            'fields': ('trial_ends_at', 'current_period_start', 'current_period_end', 'cancelled_at')
        }),
        ('Notes', {
            'fields': ('notes',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    actions = ['mark_active', 'mark_cancelled']

    def mark_active(self, request, queryset):
        queryset.update(status='active', is_active=True)
        self.message_user(request, f'{queryset.count()} subscription(s) marked as active.')
    mark_active.short_description = 'Mark selected as Active'

    def mark_cancelled(self, request, queryset):
        queryset.update(status='cancelled', is_active=False)
        self.message_user(request, f'{queryset.count()} subscription(s) cancelled.')
    mark_cancelled.short_description = 'Mark selected as Cancelled'


# ─── Register on super_admin_site ONLY — never on admin.site ─────────────────

super_admin_site.register(Feature, FeatureAdmin)
super_admin_site.register(Plan, PlanAdmin)
super_admin_site.register(Client, ClientAdmin)
super_admin_site.register(TenantSubscription, TenantSubscriptionAdmin)


# ─── User Management on Super Admin Site ─────────────────────────────────────
# Since django.contrib.auth lives in SHARED_APPS (public schema), ALL users
# from ALL tenants are visible here. Super admin can create, edit and delete
# any user account across the entire platform.

from django.contrib.auth.models import User, Group
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin, GroupAdmin as BaseGroupAdmin


class SuperAdminUserAdmin(BaseUserAdmin):
    """
    Full user management for the super admin.
    Inherits all default UserAdmin features (password hash, permissions, etc.)
    and adds a tenant column derived from the username convention.
    """
    list_display = [
        'username', 'email', 'first_name', 'last_name',
        'tenant_hint', 'is_staff', 'is_superuser', 'is_active', 'date_joined',
    ]
    list_filter = ['is_superuser', 'is_staff', 'is_active', 'date_joined']
    search_fields = ['username', 'email', 'first_name', 'last_name']
    ordering = ['username']

    # Keep all standard fieldsets from BaseUserAdmin (password, permissions, etc.)
    # Just add a readonly informational field at the top.
    readonly_fields = ['date_joined', 'last_login', 'tenant_hint']

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'email')}),
        ('Tenant', {
            'fields': ('tenant_hint',),
            'description': (
                'Which tenant this user belongs to (inferred from username). '
                'Users whose username starts with "admin_" are auto-created tenant admins.'
            ),
        }),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        ('Important Dates', {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2', 'is_staff', 'is_superuser', 'is_active'),
        }),
    )

    def tenant_hint(self, obj):
        """
        Infer tenant from the username convention used when auto-creating tenant admins:
            admin_<schema_name>  →  schema = <schema_name>
        For regular agents, we cross-reference Client records by schema prefix matching.
        """
        username = obj.username
        if username.startswith('admin_'):
            schema = username[len('admin_'):]
            try:
                tenant = Client.objects.get(schema_name=schema)
                return format_html(
                    '<span style="color:#185FA5;font-weight:bold;">{}</span> '
                    '<span style="color:#888;font-size:11px;">({})</span>',
                    tenant.name, schema
                )
            except Client.DoesNotExist:
                return format_html('<span style="color:#888;">{}</span>', schema)

        if obj.is_superuser:
            return format_html('<span style="color:#1D9E75;font-weight:bold;">Super Admin</span>')

        # Try to find by checking all tenant schemas (expensive — only shown in detail view)
        return format_html('<span style="color:#94A3B8;font-size:12px;">— unknown —</span>')

    tenant_hint.short_description = 'Tenant'


super_admin_site.register(User, SuperAdminUserAdmin)
super_admin_site.register(Group, BaseGroupAdmin)
