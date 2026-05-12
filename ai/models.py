# ai/models.py
# ─────────────────────────────────────────────────────────────────────────────
# Phase 4 — AI Features Models
# CallTranscript   : Whisper transcription + speaker labels per call
# CallSentiment    : AI sentiment + intent + coaching insights per call
# EmailThread      : Email conversation thread per lead
# EmailMessage     : Individual email (inbound/outbound)
# ChatbotFlow      : Configures the WA chatbot intent→response rules
# ChatbotSession   : Tracks active bot session per WA conversation
# ─────────────────────────────────────────────────────────────────────────────

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


# ─── Call Intelligence ────────────────────────────────────────────────────────

class CallTranscript(models.Model):
    """
    AI-generated transcript of a recorded call.
    Created asynchronously after a call recording is uploaded.
    """
    STATUS_CHOICES = [
        ('pending',    'Pending'),
        ('processing', 'Processing'),
        ('done',       'Done'),
        ('failed',     'Failed'),
    ]

    call_log = models.OneToOneField(
        'leads.CallLog', on_delete=models.CASCADE, related_name='transcript'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    language = models.CharField(max_length=10, default='hi', help_text='Detected language code')
    duration_seconds = models.IntegerField(null=True, blank=True)

    # Raw transcript — full text
    full_text = models.TextField(blank=True, null=True)

    # Structured transcript — list of segments with speaker + timestamps
    # [{"speaker": "agent", "start": 0.0, "end": 3.2, "text": "Hello..."}, ...]
    segments = models.JSONField(default=list, blank=True)

    # AI-generated 2-3 line summary added to LeadActivity
    summary = models.TextField(blank=True, null=True)

    error_message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Transcript: {self.call_log} ({self.status})"

    @property
    def word_count(self):
        return len(self.full_text.split()) if self.full_text else 0


class CallSentiment(models.Model):
    """
    AI sentiment and coaching analysis for a call.
    Created after transcript is ready.
    """
    SENTIMENT_CHOICES = [
        ('positive', 'Positive'),
        ('neutral',  'Neutral'),
        ('negative', 'Negative'),
    ]

    transcript = models.OneToOneField(
        CallTranscript, on_delete=models.CASCADE, related_name='sentiment'
    )
    overall_sentiment = models.CharField(
        max_length=20, choices=SENTIMENT_CHOICES, default='neutral'
    )
    sentiment_score = models.FloatField(
        default=0.0,
        help_text='Score from -1.0 (very negative) to +1.0 (very positive)'
    )
    customer_intent = models.CharField(
        max_length=100, blank=True, null=True,
        help_text='Detected intent e.g. "price inquiry", "complaint", "ready to buy"'
    )
    objections_detected = models.JSONField(
        default=list, blank=True,
        help_text='List of objection strings detected e.g. ["too expensive", "need to think"]'
    )

    # Coaching metrics
    agent_talk_ratio = models.FloatField(
        null=True, blank=True,
        help_text='Fraction of call time agent spoke (0.0–1.0). Ideal: 0.3–0.5'
    )
    filler_word_count = models.IntegerField(
        default=0,
        help_text='Count of filler words (um, uh, basically, you know) in agent speech'
    )
    interruptions_count = models.IntegerField(default=0)

    # Key moments
    best_moment = models.TextField(blank=True, null=True)
    improvement_area = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Sentiment: {self.overall_sentiment} ({self.sentiment_score:+.2f})"


# ─── Email Intelligence ───────────────────────────────────────────────────────

class EmailThread(models.Model):
    """One email thread per lead — synced from Gmail/SMTP."""
    lead = models.OneToOneField(
        'leads.Lead', on_delete=models.CASCADE, related_name='email_thread'
    )
    thread_id = models.CharField(
        max_length=200, blank=True, null=True,
        help_text='Gmail thread ID or SMTP message-ID chain root'
    )
    last_synced_at = models.DateTimeField(null=True, blank=True)
    unread_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Email Thread: {self.lead.name}"


class EmailMessage(models.Model):
    DIRECTION_CHOICES = [
        ('inbound',  'Inbound'),
        ('outbound', 'Outbound'),
    ]
    CLASSIFICATION_CHOICES = [
        ('inquiry',    'Inquiry'),
        ('complaint',  'Complaint'),
        ('follow_up',  'Follow-up'),
        ('unsubscribe','Unsubscribe'),
        ('other',      'Other'),
    ]

    thread = models.ForeignKey(
        EmailThread, on_delete=models.CASCADE, related_name='messages'
    )
    message_id = models.CharField(
        max_length=500, unique=True, blank=True, null=True,
        help_text='Email Message-ID header value'
    )
    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES)
    subject = models.CharField(max_length=500, blank=True, null=True)
    from_address = models.EmailField(blank=True, null=True)
    to_address = models.EmailField(blank=True, null=True)
    body_text = models.TextField(blank=True, null=True)
    body_html = models.TextField(blank=True, null=True)
    ai_classification = models.CharField(
        max_length=20, choices=CLASSIFICATION_CHOICES,
        blank=True, null=True
    )
    ai_urgency_score = models.IntegerField(
        null=True, blank=True,
        help_text='AI-calculated urgency 1-10'
    )
    ai_summary = models.TextField(blank=True, null=True)
    sent_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True
    )
    sent_at = models.DateTimeField(null=True, blank=True)
    received_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Email {'→' if self.direction == 'outbound' else '←'} {self.subject or '(no subject)'}"


# ─── AI Chatbot ───────────────────────────────────────────────────────────────

class ChatbotFlow(models.Model):
    """
    Defines the LLM system prompt and behaviour for the WhatsApp AI chatbot.
    One active flow per tenant at a time.
    """
    name = models.CharField(max_length=200)
    is_active = models.BooleanField(default=True)

    # LLM system prompt defining the bot's persona and task
    system_prompt = models.TextField(
        help_text='LLM system prompt. Variables: {company_name}, {agent_name}. '
                  'Define bot persona, products, escalation triggers.'
    )

    # Keywords that immediately escalate to human agent (bypass LLM)
    escalation_keywords = models.TextField(
        default='human,agent,talk to someone,speak to person,manager',
        help_text='Comma-separated keywords. When detected → escalate to human agent immediately.'
    )

    # Max turns before auto-escalation
    max_turns_before_escalation = models.IntegerField(
        default=5,
        help_text='If bot has not qualified the lead after N turns, escalate.'
    )

    # Lead qualification questions to ask
    qualification_questions = models.JSONField(
        default=list,
        help_text='List of questions to ask sequentially. '
                  'e.g. ["What product are you interested in?", "What is your budget?"]'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_active', '-created_at']

    def __str__(self):
        return f"{self.name} ({'active' if self.is_active else 'inactive'})"

    def get_escalation_keywords(self) -> list:
        return [k.strip().lower() for k in self.escalation_keywords.split(',') if k.strip()]


class ChatbotSession(models.Model):
    """
    Tracks an active bot conversation session.
    One per WAConversation when bot is handling it.
    """
    STATUS_CHOICES = [
        ('active',    'Active'),
        ('escalated', 'Escalated to Human'),
        ('qualified', 'Lead Qualified'),
        ('ended',     'Ended'),
    ]

    conversation = models.OneToOneField(
        'leads.WAConversation', on_delete=models.CASCADE, related_name='chatbot_session'
    )
    flow = models.ForeignKey(
        ChatbotFlow, on_delete=models.SET_NULL, null=True
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    turn_count = models.IntegerField(default=0)

    # Conversation history sent to LLM on each turn
    # [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
    history = models.JSONField(default=list, blank=True)

    # Answers collected from qualification questions
    # {"product_interest": "CRM software", "budget": "50000"}
    qualification_data = models.JSONField(default=dict, blank=True)

    escalated_to = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='chatbot_escalations'
    )
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        return f"Bot session: {self.conversation.lead.name} ({self.status})"
