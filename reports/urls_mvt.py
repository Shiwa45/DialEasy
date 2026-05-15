from django.urls import path
from . import mvt_views

app_name = 'reports'

urlpatterns = [
    path('dashboard/', mvt_views.reports_dashboard_view, name='reports_dashboard'),
]
