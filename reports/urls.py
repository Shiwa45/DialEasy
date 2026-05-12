from django.urls import path
from . import views

urlpatterns = [
    # Basic (all plans)
    path('dashboard/',         views.dashboard_summary,  name='report_dashboard'),
    path('daily-trend/',       views.daily_trend,        name='report_daily_trend'),

    # Advanced (plan feature: advanced_reports)
    path('lead-funnel/',       views.lead_funnel,        name='report_lead_funnel'),
    path('agent-leaderboard/', views.agent_leaderboard,  name='report_agent_leaderboard'),
    path('source-performance/',views.source_performance, name='report_source_performance'),
    path('call-analytics/',    views.call_analytics,     name='report_call_analytics'),
    path('deal-pipeline/',     views.deal_pipeline,      name='report_deal_pipeline'),

    # Exports (staff + advanced_reports)
    path('export/leads/',      views.export_leads_csv,   name='export_leads_csv'),
    path('export/calls/',      views.export_calls_csv,   name='export_calls_csv'),
]
