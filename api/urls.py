# api/urls.py (Complete)

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from . import integrations

# Create a router and register our viewsets
router = DefaultRouter()
router.register(r'leads', views.LeadViewSet, basename='lead')
router.register(r'call-logs', views.CallLogViewSet, basename='calllog')
router.register(r'follow-ups', views.FollowUpViewSet, basename='followup')

urlpatterns = [
    # Include router URLs
    path('', include(router.urls)),
    
    # Integrations Webhooks
    path('webhooks/meta/', integrations.meta_webhook, name='meta_webhook'),
    path('webhooks/indiamart/', integrations.indiamart_webhook, name='indiamart_webhook'),
    path('webhooks/justdial/', integrations.justdial_webhook, name='justdial_webhook'),
    path('webhooks/whatsapp/', integrations.whatsapp_webhook, name='whatsapp_webhook'),
    path('whatsapp/send/', integrations.whatsapp_send_message, name='whatsapp_send_message'),
    
    # Authentication endpoints
    path('auth/login/', views.login_view, name='api_login'),
    path('auth/logout/', views.logout_view, name='api_logout'),
    path('auth/profile/', views.profile_view, name='api_profile'),
    
    # Agent dashboard and statistics
    path('agent/dashboard/', views.agent_dashboard, name='agent_dashboard'),
    path('agent/stats/', views.agent_stats, name='agent_stats'),
    
    # Lead action endpoints
    path('leads/<int:lead_id>/call/', views.create_call_log, name='create_call_log'),
    path('leads/<int:lead_id>/follow-up/', views.create_follow_up, name='create_follow_up'),
    
    # Follow-up management
    path('follow-ups/<int:follow_up_id>/complete/', views.complete_follow_up, name='complete_follow_up'),
    
    # Search and filters
    path('search/leads/', views.search_leads, name='search_leads'),
    
    # Bulk operations
    path('leads/bulk-update/', views.bulk_update_leads, name='bulk_update_leads'),
    
    # Utility endpoints
    path('utils/lead-status-choices/', views.lead_status_choices, name='lead_status_choices'),
    path('utils/call-disposition-choices/', views.call_disposition_choices, name='call_disposition_choices'),
    path('utils/app-config/', views.app_config, name='app_config'),
    
    # Offline sync endpoints
    path('sync/upload/', views.sync_offline_data, name='sync_upload'),
    path('sync/download/', views.sync_download_data, name='sync_download'),
    
    # Performance endpoints
    path('performance/summary/', views.performance_summary, name='performance_summary'),
    path('follow-ups/today/', views.today_follow_ups, name='today_follow_ups'),
    path('follow-ups/overdue/', views.overdue_follow_ups, name='overdue_follow_ups'),
    path('follow-ups/upcoming/', views.upcoming_follow_ups, name='upcoming_follow_ups'),
    path('follow-ups/bulk-complete/', views.bulk_complete_follow_ups, name='bulk_complete_follow_ups'),
    path('follow-ups/stats/', views.follow_up_stats, name='follow_up_stats'),
    path('follow-ups/dashboard/', views.follow_up_dashboard, name='follow_up_dashboard'),
    path('follow-ups/<int:follow_up_id>/snooze/', views.snooze_follow_up, name='snooze_follow_up'),

    # Call recording
    path('call-logs/<int:call_log_id>/upload-recording/', views.upload_call_recording, name='upload_call_recording'),

    # Time tracking
    path('activity/session/start/', views.start_dialer_session, name='start_dialer_session'),
    path('activity/session/<int:session_id>/event/', views.log_activity_event, name='log_activity_event'),

]