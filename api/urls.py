from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from .integrations import meta_webhook, indiamart_webhook, justdial_webhook
from .integrations_v2 import whatsapp_webhook, whatsapp_send_message, whatsapp_send_template_api
from .whatsapp_views import (
    conversation_list, conversation_detail, conversation_messages,
    send_message, template_list, template_detail, template_preview,
    broadcast_list, broadcast_pause,
)

router = DefaultRouter()
router.register(r'leads',     views.LeadViewSet,     basename='lead')
router.register(r'call-logs', views.CallLogViewSet,  basename='calllog')
router.register(r'follow-ups',views.FollowUpViewSet, basename='followup')
router.register(r'tasks',     views.LeadTaskViewSet, basename='task')
router.register(r'products',  views.ProductViewSet,  basename='product')

urlpatterns = [
    path('', include(router.urls)),

    # Webhooks
    path('webhooks/meta/',      meta_webhook,      name='meta_webhook'),
    path('webhooks/indiamart/', indiamart_webhook, name='indiamart_webhook'),
    path('webhooks/justdial/',  justdial_webhook,  name='justdial_webhook'),
    path('webhooks/whatsapp/',  whatsapp_webhook,  name='whatsapp_webhook'),

    # WhatsApp send
    path('whatsapp/send/',           whatsapp_send_message,      name='whatsapp_send_message'),
    path('whatsapp/send-template/',  whatsapp_send_template_api, name='whatsapp_send_template'),

    # WhatsApp Conversations
    path('whatsapp/conversations/',                        conversation_list,     name='wa_conversation_list'),
    path('whatsapp/conversations/<int:lead_id>/',          conversation_detail,   name='wa_conversation_detail'),
    path('whatsapp/conversations/<int:lead_id>/messages/', conversation_messages, name='wa_conversation_messages'),
    path('whatsapp/conversations/<int:lead_id>/send/',     send_message,          name='wa_send_message'),

    # WhatsApp Templates
    path('whatsapp/templates/',                          template_list,    name='wa_template_list'),
    path('whatsapp/templates/<int:template_id>/',        template_detail,  name='wa_template_detail'),
    path('whatsapp/templates/<int:template_id>/preview/',template_preview, name='wa_template_preview'),

    # WhatsApp Broadcasts
    path('whatsapp/broadcasts/',                            broadcast_list,  name='wa_broadcast_list'),
    path('whatsapp/broadcasts/<int:broadcast_id>/pause/',   broadcast_pause, name='wa_broadcast_pause'),

    # Auth
    path('auth/login/',   views.login_view,   name='api_login'),
    path('auth/logout/',  views.logout_view,  name='api_logout'),
    path('auth/profile/', views.profile_view, name='api_profile'),

    # Agent
    path('agent/dashboard/',          views.agent_dashboard,          name='agent_dashboard'),
    path('agent/enhanced-dashboard/', views.enhanced_agent_dashboard, name='enhanced_agent_dashboard'),
    path('agent/stats/',              views.agent_stats,              name='agent_stats'),

    # Lead actions
    path('leads/<int:lead_id>/call/',      views.create_call_log,       name='create_call_log'),
    path('leads/<int:lead_id>/follow-up/', views.create_follow_up,      name='create_follow_up'),
    path('leads/<int:lead_id>/recording/', views.upload_call_recording, name='upload_call_recording'),
    path('call-logs/<int:call_log_id>/upload-recording/', views.upload_call_recording_by_log, name='upload_call_recording_by_log'),
    path('leads/<int:lead_id>/notes/',     views.lead_notes,            name='lead_notes'),
    path('leads/<int:lead_id>/notes/<int:note_id>/', views.lead_note_detail, name='lead_note_detail'),
    path('leads/<int:lead_id>/tasks/',     views.lead_tasks,            name='lead_tasks'),
    path('leads/<int:lead_id>/products/',  views.lead_products_view,    name='lead_products'),
    path('leads/<int:lead_id>/activity/',  views.lead_activity,         name='lead_activity'),
    path('leads/<int:lead_id>/score/',     views.recalculate_lead_score,name='recalculate_lead_score'),

    # Follow-ups & Tasks
    path('follow-ups/<int:follow_up_id>/complete/', views.complete_follow_up, name='complete_follow_up'),
    path('tasks/<int:task_id>/complete/',            views.complete_task,       name='complete_task'),

    # Search & Bulk
    path('search/leads/',        views.search_leads,          name='search_leads'),
    path('leads/bulk-update/',   views.bulk_update_leads,     name='bulk_update_leads'),
    path('leads/bulk-assign/',   views.bulk_assign_leads_api, name='bulk_assign_leads_api'),

    # Utils & Sync
    path('utils/lead-status-choices/',       views.lead_status_choices,         name='lead_status_choices'),
    path('utils/call-disposition-choices/',  views.call_disposition_choices,    name='call_disposition_choices'),
    path('utils/app-config/',                views.app_config,                  name='app_config'),
    path('sync/upload/',                     views.sync_offline_data,           name='sync_upload'),
    path('sync/download/',                   views.sync_download_data,          name='sync_download'),

    # Activity tracking (Flutter dialer)
    path('activity/session/start/',                  views.start_dialer_session, name='start_dialer_session'),
    path('activity/session/<int:session_id>/event/', views.log_activity_event,   name='log_activity_event'),
    path('heartbeat/',                               views.agent_heartbeat,      name='agent_heartbeat'),

    # Admin live status (AJAX poll for Live Monitor page)
    path('admin/live-status/',                       views.admin_live_status,    name='admin_live_status'),
]
