from django.urls import path
from . import views

urlpatterns = [
    path('',                        views.notification_list,    name='notification_list'),
    path('unread-count/',           views.unread_count,         name='notification_unread_count'),
    path('mark-all-read/',          views.mark_all_read,        name='notification_mark_all_read'),
    path('<int:notification_id>/read/', views.mark_read,        name='notification_mark_read'),
    path('fcm-token/',              views.register_fcm_token,   name='fcm_token_register'),
    path('fcm-token/remove/',       views.deregister_fcm_token, name='fcm_token_remove'),
]
