# ai/urls.py

from django.urls import path
from . import views

urlpatterns = [
    # Call transcription
    path('transcripts/<int:call_log_id>/',         views.call_transcript,       name='ai_call_transcript'),
    path('transcripts/<int:call_log_id>/process/', views.trigger_transcription, name='ai_trigger_transcription'),
    path('leads/<int:lead_id>/transcripts/',       views.lead_transcripts,      name='ai_lead_transcripts'),

    # Coaching
    path('coaching/',                              views.coaching_dashboard,    name='ai_coaching_dashboard'),

    # Email AI
    path('emails/<int:lead_id>/',                  views.email_thread,          name='ai_email_thread'),
    path('emails/<int:lead_id>/send/',             views.send_email,            name='ai_send_email'),
    path('emails/draft/<int:email_message_id>/',   views.draft_email_reply,     name='ai_draft_email_reply'),

    # Chatbot
    path('chatbot/flow/',                          views.chatbot_flow,          name='ai_chatbot_flow'),
]
