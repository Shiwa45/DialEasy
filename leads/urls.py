# leads/urls.py - Complete Updated Version

from django.urls import path
from . import views

app_name = 'leads'

urlpatterns = [
    # Dashboard and main views
    path('', views.dashboard, name='dashboard'),
    path('list/', views.lead_list, name='lead_list'),
    path('lead/<int:lead_id>/', views.lead_detail, name='lead_detail'),
    
    # Lead upload functionality
    path('upload/', views.upload_leads, name='upload_leads'),
    path('download-sample/', views.download_sample_csv, name='download_sample_csv'),
    
    # Debug and preview endpoints
    path('debug-csv/', views.debug_csv_upload, name='debug_csv'),
    path('preview-csv/', views.check_file_preview, name='preview_csv'),
    
    # Lead assignment
    path('assign/', views.assign_leads, name='assign_leads'),
    path('bulk-assign/', views.bulk_assign_leads, name='bulk_assign_leads'),
    
    # Integrations
    path('integrations/', views.integrations_view, name='integrations'),
]