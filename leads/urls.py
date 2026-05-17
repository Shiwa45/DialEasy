# leads/urls.py - Complete Updated Version

from django.urls import path
from . import views

app_name = 'leads'

urlpatterns = [
    # Dashboard and main views
    path('', views.dashboard, name='dashboard'),
    path('list/', views.lead_list, name='lead_list'),
    path('lead/<int:lead_id>/', views.lead_detail, name='lead_detail'),
    path('lead/<int:lead_id>/send-whatsapp/', views.send_whatsapp_message, name='send_whatsapp_message'),
    
    # Lead upload functionality
    path('upload/', views.upload_leads, name='upload_leads'),
    path('download-sample/', views.download_sample_csv, name='download_sample_csv'),
    
    # Debug and preview endpoints
    path('debug-csv/', views.debug_csv_upload, name='debug_csv'),
    path('preview-csv/', views.check_file_preview, name='preview_csv'),
    
    # Lead assignment
    path('assign/', views.assign_leads, name='assign_leads'),
    path('bulk-assign/', views.bulk_assign_leads, name='bulk_assign_leads'),

    # Lead deletion
    path('lead/<int:lead_id>/delete/', views.delete_lead, name='delete_lead'),
    path('bulk-delete/', views.bulk_delete_leads, name='bulk_delete_leads'),

    # Funnels
    path('funnels/', views.funnel_list, name='funnel_list'),
    path('funnels/new/', views.funnel_create, name='funnel_create'),
    path('funnels/<int:funnel_id>/edit/', views.funnel_edit, name='funnel_edit'),
    path('funnels/<int:funnel_id>/delete/', views.funnel_delete, name='funnel_delete'),
    
    # Integrations
    path('integrations/', views.integrations_view, name='integrations'),

    # Settings
    path('settings/dispositions/', views.settings_dispositions, name='settings_dispositions'),

    # Call recordings (staff only, feature-gated)
    path('recordings/', views.call_recordings_list, name='call_recordings_list'),

    # Bulk WhatsApp Campaigns (staff + bulk_whatsapp feature)
    path('campaigns/',                                    views.campaign_list,   name='campaign_list'),
    path('campaigns/new/',                                views.campaign_create, name='campaign_create'),
    path('campaigns/<int:campaign_id>/',                  views.campaign_detail, name='campaign_detail'),
    path('campaigns/<int:campaign_id>/pause/',            views.campaign_pause,  name='campaign_pause'),
    path('campaigns/<int:campaign_id>/resume/',           views.campaign_resume, name='campaign_resume'),
    path('campaigns/<int:campaign_id>/cancel/',           views.campaign_cancel, name='campaign_cancel'),

    # WhatsApp Provider Settings (staff + bulk_whatsapp feature)
    path('campaigns/providers/',                          views.provider_settings,    name='provider_settings'),
    path('campaigns/providers/new/',                      views.provider_create,      name='provider_create'),
    path('campaigns/providers/<int:provider_id>/test/',   views.provider_test,        name='provider_test'),
    path('campaigns/providers/<int:provider_id>/default/',views.provider_set_default, name='provider_set_default'),
    path('campaigns/providers/<int:provider_id>/delete/', views.provider_delete,      name='provider_delete'),

    # WhatsApp Template Management (staff + bulk_whatsapp feature)
    path('campaigns/templates/',                             views.wa_template_list,   name='wa_template_list'),
    path('campaigns/templates/new/',                         views.wa_template_create, name='wa_template_create'),
    path('campaigns/templates/<int:template_id>/edit/',      views.wa_template_edit,   name='wa_template_edit'),
    path('campaigns/templates/<int:template_id>/delete/',    views.wa_template_delete, name='wa_template_delete'),
]