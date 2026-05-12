# tenants/admin.py
# ─────────────────────────────────────────────────────────────────────────────
# Super Admin panel — only accessible from the public schema (admin.telecrm.com
# or /superadmin/). Regular tenant admins NEVER see these models.
# ─────────────────────────────────────────────────────────────────────────────

from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from .models import Client, Domain, Plan, Feature, TenantSubscription


# ─── Feature Admin ────────────────────────────────────────────────────────────

@admin.register(Feature)
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


@admin.register(Plan)
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

@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'schema_name', 'owner_email',
        'current_plan_display', 'subscription_status',
        'is_active', 'created_at'
    ]
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'schema_name', 'owner_email']
    readonly_fields = ['schema_name', 'created_at', 'updated_at']
    inlines = [DomainInline, TenantSubscriptionInline]

    fieldsets = (
        ('Tenant Information', {
            'fields': ('name', 'schema_name', 'owner_email', 'phone', 'address', 'logo', 'is_active')
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


# ─── Subscription Admin ───────────────────────────────────────────────────────

@admin.register(TenantSubscription)
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
        queryset.update(status='cancelled', is_active=False, cancelled_at=timezone.now())
        self.message_user(request, f'{queryset.count()} subscription(s) cancelled.')
    mark_cancelled.short_description = 'Cancel selected subscriptions'
