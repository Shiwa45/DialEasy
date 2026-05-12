# leads/whatsapp_admin.py
# ─────────────────────────────────────────────────────────────────────────────
# Register in leads/admin.py:
#   from leads.whatsapp_admin import *   # noqa
# ─────────────────────────────────────────────────────────────────────────────

from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from .whatsapp_models import (
    WAConversation, WAMessage, WATemplate,
    WABroadcast, WABroadcastRecipient, WAAutoReply,
)


# ─── WATemplate ───────────────────────────────────────────────────────────────

@admin.register(WATemplate)
class WATemplateAdmin(admin.ModelAdmin):
    list_display = ['display_name', 'name', 'category', 'language_code', 'status_badge', 'is_active', 'created_at']
    list_filter = ['category', 'status', 'is_active', 'language_code']
    search_fields = ['name', 'display_name', 'body_text']
    readonly_fields = ['created_at', 'updated_at', 'created_by']

    fieldsets = (
        ('Identity', {'fields': ('name', 'display_name', 'category', 'language_code', 'status', 'is_active')}),
        ('Content', {'fields': ('header_text', 'body_text', 'footer_text')}),
        ('Variables & Buttons', {'fields': ('variable_mapping', 'buttons'), 'classes': ('collapse',)}),
        ('Meta', {'fields': ('created_by', 'created_at', 'updated_at'), 'classes': ('collapse',)}),
    )

    def status_badge(self, obj):
        colors = {'approved': '#1D9E75', 'pending': '#BA7517', 'rejected': '#D85A30', 'paused': '#888780'}
        color = colors.get(obj.status, '#888780')
        return format_html('<span style="color:{};font-weight:bold;">{}</span>', color, obj.get_status_display())
    status_badge.short_description = 'Status'

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


# ─── WAConversation ───────────────────────────────────────────────────────────

class WAMessageInline(admin.TabularInline):
    model = WAMessage
    extra = 0
    max_num = 0
    readonly_fields = ['direction', 'message_type', 'status', 'body_preview', 'sent_by', 'created_at']
    fields = ['direction', 'message_type', 'status', 'body_preview', 'sent_by', 'created_at']
    can_delete = False

    def body_preview(self, obj):
        return (obj.body or '')[:80] + '…' if obj.body and len(obj.body) > 80 else (obj.body or '—')
    body_preview.short_description = 'Message'


@admin.register(WAConversation)
class WAConversationAdmin(admin.ModelAdmin):
    list_display = ['lead', 'status', 'unread_count', 'is_opted_out', 'assigned_agent', 'last_message_at']
    list_filter = ['status', 'is_opted_out']
    search_fields = ['lead__name', 'lead__phone']
    readonly_fields = ['created_at', 'updated_at', 'last_message_at', 'unread_count']
    inlines = [WAMessageInline]
    raw_id_fields = ['lead', 'assigned_agent']

    actions = ['mark_as_closed', 'mark_as_open', 'remove_opt_out']

    def mark_as_closed(self, request, queryset):
        queryset.update(status='closed')
    mark_as_closed.short_description = 'Mark selected as Closed'

    def mark_as_open(self, request, queryset):
        queryset.update(status='open')
    mark_as_open.short_description = 'Mark selected as Open'

    def remove_opt_out(self, request, queryset):
        queryset.update(is_opted_out=False)
        self.message_user(request, 'Opt-out removed for selected conversations.')
    remove_opt_out.short_description = 'Remove opt-out (re-enable messaging)'


# ─── WAAutoReply ──────────────────────────────────────────────────────────────

@admin.register(WAAutoReply)
class WAAutoReplyAdmin(admin.ModelAdmin):
    list_display = ['name', 'priority', 'keywords_preview', 'action', 'is_active', 'stop_processing']
    list_filter = ['action', 'is_active']
    search_fields = ['name', 'keywords']
    readonly_fields = ['created_at']

    fieldsets = (
        ('Rule', {'fields': ('name', 'priority', 'is_active')}),
        ('Trigger', {'fields': ('keywords', 'match_exact')}),
        ('Action', {'fields': ('action', 'reply_text', 'reply_template', 'assign_to_agent', 'lead_status_update')}),
        ('Behaviour', {'fields': ('stop_processing',)}),
        ('Meta', {'fields': ('created_at',), 'classes': ('collapse',)}),
    )

    def keywords_preview(self, obj):
        return obj.keywords[:60] + '…' if len(obj.keywords) > 60 else obj.keywords
    keywords_preview.short_description = 'Keywords'


# ─── WABroadcast ──────────────────────────────────────────────────────────────

class WABroadcastRecipientInline(admin.TabularInline):
    model = WABroadcastRecipient
    extra = 0
    max_num = 0
    readonly_fields = ['lead', 'status', 'wa_message_id', 'error_message', 'sent_at']
    can_delete = False
    show_change_link = False

    def get_queryset(self, request):
        return super().get_queryset(request)[:50]  # Show max 50 inline


@admin.register(WABroadcast)
class WABroadcastAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'template', 'status_badge', 'total_leads',
        'sent_count', 'delivered_count', 'failed_count',
        'created_by', 'created_at'
    ]
    list_filter = ['status', 'created_at']
    search_fields = ['name']
    readonly_fields = ['sent_count', 'delivered_count', 'failed_count', 'opted_out_skipped',
                       'total_leads', 'started_at', 'completed_at', 'created_at', 'updated_at']
    inlines = [WABroadcastRecipientInline]

    fieldsets = (
        ('Broadcast Details', {'fields': ('name', 'template', 'status', 'lead_filter')}),
        ('Schedule', {'fields': ('scheduled_at',)}),
        ('Progress', {
            'fields': ('total_leads', 'sent_count', 'delivered_count', 'failed_count', 'opted_out_skipped'),
        }),
        ('Timestamps', {'fields': ('started_at', 'completed_at', 'created_at', 'updated_at'), 'classes': ('collapse',)}),
    )

    actions = ['pause_broadcast']

    def status_badge(self, obj):
        colors = {
            'draft': '#888780', 'queued': '#BA7517', 'running': '#378ADD',
            'completed': '#1D9E75', 'paused': '#BA7517', 'failed': '#D85A30',
        }
        color = colors.get(obj.status, '#888780')
        return format_html('<span style="color:{};font-weight:bold;">{}</span>', color, obj.get_status_display())
    status_badge.short_description = 'Status'

    def pause_broadcast(self, request, queryset):
        queryset.filter(status='running').update(status='paused')
        self.message_user(request, 'Selected running broadcasts paused.')
    pause_broadcast.short_description = 'Pause selected broadcasts'
