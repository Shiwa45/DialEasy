# leads/admin.py

from django.contrib import admin
from .models import Lead, CallLog, FollowUp, LeadUpload
from .integration_models import IntegrationConfig, IntegrationLog

@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ['name', 'phone', 'email', 'company', 'status', 'assigned_agent', 'created_at']
    list_filter = ['status', 'assigned_agent', 'created_at']
    search_fields = ['name', 'phone', 'email', 'company']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'phone', 'email', 'company')
        }),
        ('Lead Management', {
            'fields': ('status', 'assigned_agent', 'source', 'notes')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

@admin.register(CallLog)
class CallLogAdmin(admin.ModelAdmin):
    list_display = ['lead', 'agent', 'call_date', 'disposition', 'duration']
    list_filter = ['disposition', 'agent', 'call_date']
    search_fields = ['lead__name', 'lead__phone', 'agent__username']
    readonly_fields = ['created_at']
    
    fieldsets = (
        ('Call Information', {
            'fields': ('lead', 'agent', 'call_date', 'duration')
        }),
        ('Call Outcome', {
            'fields': ('disposition', 'remarks')
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        })
    )

@admin.register(FollowUp)
class FollowUpAdmin(admin.ModelAdmin):
    list_display = ['lead', 'agent', 'follow_up_date', 'follow_up_time', 'is_completed']
    list_filter = ['is_completed', 'follow_up_date', 'agent']
    search_fields = ['lead__name', 'lead__phone', 'agent__username']
    readonly_fields = ['created_at', 'completed_at']
    
    fieldsets = (
        ('Follow-up Details', {
            'fields': ('lead', 'agent', 'follow_up_date', 'follow_up_time', 'remarks')
        }),
        ('Status', {
            'fields': ('is_completed', 'completed_at')
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        })
    )

@admin.register(LeadUpload)
class LeadUploadAdmin(admin.ModelAdmin):
    list_display = ['uploaded_by', 'status', 'total_records', 'processed_records', 'failed_records', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['uploaded_by__username']
    readonly_fields = ['created_at']
    
    fieldsets = (
        ('Upload Information', {
            'fields': ('file', 'uploaded_by', 'status')
        }),
        ('Processing Results', {
            'fields': ('total_records', 'processed_records', 'failed_records', 'error_log')
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        })
    )


@admin.register(IntegrationConfig)
class IntegrationConfigAdmin(admin.ModelAdmin):
    list_display = ['platform', 'is_active', 'updated_by', 'updated_at']
    list_filter  = ['platform', 'is_active']
    readonly_fields = ['created_at', 'updated_at', 'updated_by']

    fieldsets = (
        ('Platform', {
            'fields': ('platform', 'is_active')
        }),
        ('Meta Lead Ads Credentials', {
            'fields': ('app_id', 'app_secret', 'page_access_token', 'verify_token'),
            'classes': ('collapse',),
            'description': 'Required for Meta Facebook Lead Ads webhook integration.'
        }),
        ('WhatsApp Business Cloud API', {
            'fields': ('whatsapp_phone_number_id', 'whatsapp_access_token', 'whatsapp_verify_token'),
            'classes': ('collapse',),
            'description': 'Required for WhatsApp Business Cloud API messaging.'
        }),
        ('Audit', {
            'fields': ('updated_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(IntegrationLog)
class IntegrationLogAdmin(admin.ModelAdmin):
    list_display  = ['platform', 'status', 'lead_created', 'error_message', 'created_at']
    list_filter   = ['platform', 'status', 'lead_created']
    readonly_fields = ['platform', 'raw_payload', 'lead_created', 'status', 'error_message', 'created_at']
    ordering = ['-created_at']

    def has_add_permission(self, request):
        return False  # logs are system-generated only