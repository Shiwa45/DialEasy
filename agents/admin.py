# agents/admin.py

from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from .models import AgentProfile, AgentTarget, AgentNote, DialerSession, CallActivityEvent

class AgentProfileInline(admin.StackedInline):
    model = AgentProfile
    can_delete = False
    verbose_name_plural = 'Agent Profile'
    extra = 0

# Extend the existing User admin
class UserAdmin(BaseUserAdmin):
    inlines = (AgentProfileInline,)

    def get_queryset(self, request):
        # Users live in the public schema shared across all tenants.
        # Filter to only users who have an AgentProfile in the CURRENT tenant
        # schema (AgentProfile is a TENANT_APP, so the queryset is automatically
        # scoped to the active schema by django-tenants).
        tenant_user_ids = AgentProfile.objects.values_list('user_id', flat=True)
        return super().get_queryset(request).filter(
            id__in=tenant_user_ids,
            is_staff=False,
        )

    def delete_view(self, request, object_id, extra_context=None):
        if str(request.user.pk) == str(object_id):
            from django.contrib import messages
            from django.shortcuts import redirect
            messages.error(request, "You cannot delete your own account while you are logged in.")
            return redirect('..')
        return super().delete_view(request, object_id, extra_context)

    def get_deleted_objects(self, objs, request):
        from django.db import ProgrammingError, OperationalError, transaction
        try:
            with transaction.atomic():
                return super().get_deleted_objects(objs, request)
        except (ProgrammingError, OperationalError):
            obj_display = [str(obj) for obj in objs]
            model_count = {str(objs[0]._meta.verbose_name): len(objs)} if objs else {}
            return obj_display, model_count, set(), []

    def delete_model(self, request, obj):
        from django.db import ProgrammingError, OperationalError, transaction
        try:
            with transaction.atomic():
                obj.delete()
        except (ProgrammingError, OperationalError):
            type(obj)._default_manager.filter(pk=obj.pk)._raw_delete(
                using=obj._state.db
            )

# Re-register UserAdmin for the tenant admin panel
admin.site.unregister(User)
admin.site.register(User, UserAdmin)

@admin.register(AgentProfile)
class AgentProfileAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'department', 'hire_date', 'is_active', 
        'total_leads_assigned', 'total_calls_made', 'conversion_rate'
    ]
    list_filter = ['department', 'is_active', 'hire_date']
    search_fields = ['user__username', 'user__first_name', 'user__last_name', 'department']
    readonly_fields = [
        'total_leads_assigned', 'total_calls_made', 'total_conversions',
        'created_at', 'updated_at'
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('user', 'phone', 'department', 'hire_date', 'is_active')
        }),
        ('Performance Targets', {
            'fields': ('target_calls_per_day', 'target_conversions_per_month')
        }),
        ('Statistics (Auto-calculated)', {
            'fields': (
                'total_leads_assigned', 'total_calls_made', 'total_conversions'
            ),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    actions = ['update_agent_stats']
    
    def update_agent_stats(self, request, queryset):
        """Update statistics for selected agents"""
        updated = 0
        for profile in queryset:
            profile.update_stats()
            updated += 1
        
        self.message_user(request, f'Updated statistics for {updated} agent(s).')
    
    update_agent_stats.short_description = "Update agent statistics"

@admin.register(AgentTarget)
class AgentTargetAdmin(admin.ModelAdmin):
    list_display = [
        'agent', 'month', 'target_calls', 'actual_calls', 'calls_achievement_percentage',
        'target_conversions', 'actual_conversions', 'conversions_achievement_percentage'
    ]
    list_filter = ['month', 'agent__agent_profile__department']
    search_fields = ['agent__username', 'agent__first_name', 'agent__last_name']
    date_hierarchy = 'month'
    
    fieldsets = (
        ('Target Information', {
            'fields': ('agent', 'month')
        }),
        ('Targets', {
            'fields': ('target_calls', 'target_conversions', 'target_revenue')
        }),
        ('Achievements', {
            'fields': ('actual_calls', 'actual_conversions', 'actual_revenue')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    readonly_fields = ['created_at', 'updated_at']

@admin.register(AgentNote)
class AgentNoteAdmin(admin.ModelAdmin):
    list_display = ['agent', 'created_by', 'note_preview', 'is_private', 'created_at']
    list_filter = ['is_private', 'created_at', 'created_by']
    search_fields = ['agent__username', 'agent__first_name', 'agent__last_name', 'note']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Note Information', {
            'fields': ('agent', 'created_by', 'note', 'is_private')
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        })
    )
    
    readonly_fields = ['created_at']
    
    def note_preview(self, obj):
        """Show first 50 characters of the note"""
        return obj.note[:50] + '...' if len(obj.note) > 50 else obj.note
    
    note_preview.short_description = 'Note Preview'
    
    def save_model(self, request, obj, form, change):
        """Automatically set created_by to current user when creating"""
        if not change:  # Only when creating
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


# ─── Time Tracking Admin ─────────────────────────────────────────────────────

class CallActivityEventInline(admin.TabularInline):
    model = CallActivityEvent
    extra = 0
    readonly_fields = ['event_type', 'timestamp', 'lead', 'call_log']
    can_delete = False
    ordering = ['timestamp']
    fields = ['event_type', 'timestamp', 'lead']


@admin.register(DialerSession)
class DialerSessionAdmin(admin.ModelAdmin):
    list_display = [
        'agent', 'session_start', 'session_end_display',
        'session_duration_col', 'talk_time_col',
        'disposition_time_col', 'idle_time_col',
        'total_calls_made', 'status_badge',
    ]
    list_filter = ['agent', 'session_start']
    search_fields = ['agent__username', 'agent__first_name', 'agent__last_name']
    date_hierarchy = 'session_start'
    readonly_fields = [
        'session_start', 'session_end',
        'total_call_time_seconds', 'total_disposition_time_seconds',
        'total_calls_made', 'session_duration_col',
        'talk_time_col', 'disposition_time_col', 'idle_time_col',
    ]
    inlines = [CallActivityEventInline]

    def session_end_display(self, obj):
        if obj.session_end:
            return obj.session_end.strftime('%H:%M:%S, %d %b')
        return format_html('<span style="color:green;font-weight:bold;">● Live</span>')
    session_end_display.short_description = 'Session End'

    def session_duration_col(self, obj):
        return obj.session_duration_display
    session_duration_col.short_description = 'Total Duration'

    def talk_time_col(self, obj):
        return format_html('<span style="color:#27ae60;">{}</span>', obj.talk_time_display)
    talk_time_col.short_description = 'Talk Time'

    def disposition_time_col(self, obj):
        return format_html('<span style="color:#e67e22;">{}</span>', obj.disposition_time_display)
    disposition_time_col.short_description = 'Disposition Time'

    def idle_time_col(self, obj):
        return format_html('<span style="color:#e74c3c;">{}</span>', obj.idle_time_display)
    idle_time_col.short_description = 'Idle Time'

    def status_badge(self, obj):
        if obj.session_end:
            return format_html('<span class="badge" style="background:#6c757d;color:white;padding:3px 8px;border-radius:4px;">Ended</span>')
        return format_html('<span class="badge" style="background:#27ae60;color:white;padding:3px 8px;border-radius:4px;">Active</span>')
    status_badge.short_description = 'Status'


@admin.register(CallActivityEvent)
class CallActivityEventAdmin(admin.ModelAdmin):
    list_display = ['agent', 'event_type', 'timestamp', 'session', 'lead']
    list_filter = ['event_type', 'agent', 'timestamp']
    search_fields = ['agent__username', 'agent__first_name', 'agent__last_name']
    date_hierarchy = 'timestamp'
    readonly_fields = ['agent', 'session', 'event_type', 'timestamp', 'lead', 'call_log', 'metadata']