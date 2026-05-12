# leads/admin.py — Phase 1 complete

from django.contrib import admin
from django.utils.html import format_html
from .models import (
    Lead, CallLog, FollowUp, LeadUpload,
    LeadNote, LeadTask, Product, LeadProduct,
    LeadActivity, AssignmentRule,
)
from .integration_models import IntegrationConfig, IntegrationLog
from .whatsapp_admin import *  # noqa


# ─── Inlines ──────────────────────────────────────────────────────────────────

class LeadNoteInline(admin.TabularInline):
    model = LeadNote
    extra = 0
    fields = ['note_type', 'content', 'is_pinned', 'author', 'created_at']
    readonly_fields = ['created_at']


class LeadTaskInline(admin.TabularInline):
    model = LeadTask
    extra = 0
    fields = ['title', 'priority', 'status', 'due_date', 'assigned_to']


class LeadProductInline(admin.TabularInline):
    model = LeadProduct
    extra = 0
    fields = ['product', 'quantity', 'discount_percent', 'total_price_display']
    readonly_fields = ['total_price_display']

    def total_price_display(self, obj):
        return f'₹{obj.total_price:,.2f}'
    total_price_display.short_description = 'Total'


class LeadActivityInline(admin.TabularInline):
    model = LeadActivity
    extra = 0
    fields = ['activity_type', 'description', 'actor', 'created_at']
    readonly_fields = ['activity_type', 'description', 'actor', 'created_at']
    can_delete = False
    max_num = 0  # Read-only


# ─── Lead Admin ───────────────────────────────────────────────────────────────

@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'phone', 'company', 'status', 'score_badge',
        'deal_value_display', 'assigned_agent', 'source', 'created_at'
    ]
    list_filter = ['status', 'assigned_agent', 'source', 'created_at', 'industry']
    search_fields = ['name', 'phone', 'email', 'company']
    readonly_fields = ['created_at', 'updated_at', 'lead_score']
    inlines = [LeadNoteInline, LeadTaskInline, LeadProductInline, LeadActivityInline]

    fieldsets = (
        ('Core', {'fields': ('name', 'phone', 'email', 'company', 'designation', 'industry')}),
        ('Lead Management', {'fields': ('status', 'assigned_agent', 'source', 'lead_score', 'deal_value', 'expected_close_date')}),
        ('Location', {'fields': ('city', 'state', 'address', 'website'), 'classes': ('collapse',)}),
        ('Legacy Notes', {'fields': ('notes',), 'classes': ('collapse',)}),
        ('Timestamps', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )

    actions = ['auto_assign_to_agents', 'recalculate_scores']

    def score_badge(self, obj):
        colors = {'Hot': '#D85A30', 'Warm': '#BA7517', 'Cold': '#888780'}
        color = colors.get(obj.score_label, '#888780')
        return format_html(
            '<span style="color:{};font-weight:bold;">{} ({})</span>',
            color, obj.score_label, obj.lead_score
        )
    score_badge.short_description = 'Score'

    def deal_value_display(self, obj):
        if obj.deal_value:
            return format_html('<span style="color:#1D9E75;font-weight:bold;">₹{:,.0f}</span>', obj.deal_value)
        return '—'
    deal_value_display.short_description = 'Deal Value'

    def auto_assign_to_agents(self, request, queryset):
        try:
            rule = AssignmentRule.objects.filter(is_active=True).first()
            if not rule:
                self.message_user(request, 'No active assignment rule found.', level='warning')
                return
            count = 0
            for lead in queryset.filter(assigned_agent__isnull=True):
                agent = rule.get_next_agent(lead_source=lead.source)
                if agent:
                    lead.assigned_agent = agent
                    lead.save(update_fields=['assigned_agent'])
                    count += 1
            self.message_user(request, f'Auto-assigned {count} leads.')
        except Exception as e:
            self.message_user(request, f'Error: {e}', level='error')
    auto_assign_to_agents.short_description = 'Auto-assign selected leads'

    def recalculate_scores(self, request, queryset):
        for lead in queryset:
            lead.recalculate_score()
        self.message_user(request, f'Recalculated scores for {queryset.count()} leads.')
    recalculate_scores.short_description = 'Recalculate lead scores'


# ─── CallLog Admin ────────────────────────────────────────────────────────────

@admin.register(CallLog)
class CallLogAdmin(admin.ModelAdmin):
    list_display = ['lead', 'agent', 'call_date', 'disposition', 'duration']
    list_filter = ['disposition', 'agent', 'call_date']
    search_fields = ['lead__name', 'lead__phone', 'agent__username']
    readonly_fields = ['created_at']


# ─── FollowUp Admin ───────────────────────────────────────────────────────────

@admin.register(FollowUp)
class FollowUpAdmin(admin.ModelAdmin):
    list_display = ['lead', 'agent', 'title', 'priority', 'follow_up_date', 'follow_up_time', 'is_completed']
    list_filter = ['is_completed', 'priority', 'follow_up_date', 'agent']
    search_fields = ['lead__name', 'lead__phone', 'title']
    readonly_fields = ['created_at', 'completed_at']


# ─── LeadNote Admin ───────────────────────────────────────────────────────────

@admin.register(LeadNote)
class LeadNoteAdmin(admin.ModelAdmin):
    list_display = ['lead', 'note_type', 'author', 'is_pinned', 'created_at']
    list_filter = ['note_type', 'is_pinned', 'author']
    search_fields = ['lead__name', 'content']
    readonly_fields = ['created_at', 'updated_at']


# ─── LeadTask Admin ───────────────────────────────────────────────────────────

@admin.register(LeadTask)
class LeadTaskAdmin(admin.ModelAdmin):
    list_display = ['title', 'lead', 'priority', 'status', 'assigned_to', 'due_date', 'is_overdue_display']
    list_filter = ['priority', 'status', 'assigned_to']
    search_fields = ['title', 'lead__name']
    readonly_fields = ['created_at', 'updated_at', 'completed_at']

    def is_overdue_display(self, obj):
        if obj.is_overdue:
            return format_html('<span style="color:red;">⚠ Overdue</span>')
        return '—'
    is_overdue_display.short_description = 'Overdue?'


# ─── Product Admin ────────────────────────────────────────────────────────────

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'sku', 'price', 'unit', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name', 'sku']


# ─── LeadActivity Admin ───────────────────────────────────────────────────────

@admin.register(LeadActivity)
class LeadActivityAdmin(admin.ModelAdmin):
    list_display = ['lead', 'activity_type', 'actor', 'description_short', 'created_at']
    list_filter = ['activity_type', 'created_at']
    search_fields = ['lead__name', 'description']
    readonly_fields = ['lead', 'actor', 'activity_type', 'description', 'old_value', 'new_value', 'metadata', 'created_at']

    def description_short(self, obj):
        return obj.description[:80] + '…' if len(obj.description) > 80 else obj.description
    description_short.short_description = 'Description'

    def has_add_permission(self, request):
        return False  # Activity log is immutable


# ─── AssignmentRule Admin ─────────────────────────────────────────────────────

@admin.register(AssignmentRule)
class AssignmentRuleAdmin(admin.ModelAdmin):
    list_display = ['name', 'strategy', 'is_active', 'eligible_agents_count', 'updated_at']
    list_filter = ['strategy', 'is_active']
    filter_horizontal = ['eligible_agents']
    readonly_fields = ['last_assigned_agent_id', 'created_at', 'updated_at']

    def eligible_agents_count(self, obj):
        count = obj.eligible_agents.count()
        return f'{count} agents' if count else 'All active agents'
    eligible_agents_count.short_description = 'Agent Pool'


# ─── Legacy models ────────────────────────────────────────────────────────────

@admin.register(LeadUpload)
class LeadUploadAdmin(admin.ModelAdmin):
    list_display = ['uploaded_by', 'status', 'total_records', 'processed_records', 'failed_records', 'created_at']
    list_filter = ['status']
    readonly_fields = ['created_at']


@admin.register(IntegrationConfig)
class IntegrationConfigAdmin(admin.ModelAdmin):
    list_display = ['platform', 'is_active', 'updated_at']
    list_filter = ['platform', 'is_active']


@admin.register(IntegrationLog)
class IntegrationLogAdmin(admin.ModelAdmin):
    list_display = ['platform', 'status', 'lead_created', 'created_at']
    list_filter = ['platform', 'status', 'lead_created']
    readonly_fields = ['platform', 'raw_payload', 'lead_created', 'status', 'error_message', 'created_at']
