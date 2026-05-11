# agents/urls.py

from django.urls import path
from . import views

app_name = 'agents'

urlpatterns = [
    path('', views.agent_list, name='agent_list'),
    path('create/', views.create_agent, name='create_agent'),
    path('<int:agent_id>/', views.agent_detail, name='agent_detail'),
    path('<int:agent_id>/performance/', views.agent_performance, name='agent_performance'),
    path('<int:agent_id>/update/', views.update_agent, name='update_agent'),
    path('<int:agent_id>/note/', views.add_agent_note, name='add_agent_note'),
    path('<int:agent_id>/targets/', views.set_agent_targets, name='set_agent_targets'),
    path('<int:agent_id>/stats/', views.agent_stats_ajax, name='agent_stats_ajax'),

    # Agent self-service URLs
    path('dashboard/', views.agent_dashboard, name='agent_dashboard'),
    path('my-leads/', views.agent_leads, name='agent_leads'),

    # Time tracking (admin views)
    path('activity/', views.agent_activity_list, name='agent_activity_list'),
    path('activity/<int:agent_id>/', views.agent_activity_detail, name='agent_activity_detail'),
]