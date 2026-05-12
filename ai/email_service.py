# ai/email_service.py
# ─────────────────────────────────────────────────────────────────────────────
# Phase 4 — Email AI Service
# - classify_email(): tags inbound emails (inquiry/complaint/follow-up etc.)
# - draft_reply():    AI-generated contextual reply draft
# - sync_gmail():     Pull new emails via Gmail API for a lead
# ─────────────────────────────────────────────────────────────────────────────

import json
import logging
import os
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
CHAT_URL = 'https://api.openai.com/v1/chat/completions'


def _openai_headers() -> dict:
    return {
        'Authorization': f'Bearer {OPENAI_API_KEY}',
        'Content-Type': 'application/json',
    }


def _llm_json(prompt: str, max_tokens: int = 400) -> dict:
    """Call GPT-4o-mini and return parsed JSON response."""
    payload = {
        'model': 'gpt-4o-mini',
        'messages': [{'role': 'user', 'content': prompt}],
        'temperature': 0.2,
        'max_tokens': max_tokens,
        'response_format': {'type': 'json_object'},
    }
    resp = requests.post(CHAT_URL, headers=_openai_headers(), json=payload, timeout=20)
    resp.raise_for_status()
    return json.loads(resp.json()['choices'][0]['message']['content'])


def _llm_text(messages: list, max_tokens: int = 500) -> str:
    """Call GPT-4o-mini and return plain text response."""
    payload = {
        'model': 'gpt-4o-mini',
        'messages': messages,
        'temperature': 0.7,
        'max_tokens': max_tokens,
    }
    resp = requests.post(CHAT_URL, headers=_openai_headers(), json=payload, timeout=20)
    resp.raise_for_status()
    return resp.json()['choices'][0]['message']['content'].strip()


# ─── Email Classification ─────────────────────────────────────────────────────

CLASSIFY_PROMPT = """
Classify this email and return ONLY valid JSON with these keys:
{{
  "classification": "inquiry|complaint|follow_up|unsubscribe|other",
  "urgency_score": <integer 1-10, 10 being most urgent>,
  "summary": "1-sentence plain English summary"
}}

Subject: {subject}
Body: {body}
"""


def classify_email(subject: str, body: str) -> dict:
    """
    Classify an inbound email.
    Returns: {'classification': str, 'urgency_score': int, 'summary': str}
    """
    if not OPENAI_API_KEY:
        return {'classification': 'other', 'urgency_score': 5, 'summary': body[:100]}

    prompt = CLASSIFY_PROMPT.format(
        subject=subject or '',
        body=(body or '')[:2000]
    )
    try:
        result = _llm_json(prompt)
        return {
            'classification': result.get('classification', 'other'),
            'urgency_score': int(result.get('urgency_score', 5)),
            'summary': result.get('summary', '')[:500],
        }
    except Exception as e:
        logger.error('Email classification failed: %s', e)
        return {'classification': 'other', 'urgency_score': 5, 'summary': ''}


# ─── AI Email Draft ───────────────────────────────────────────────────────────

DRAFT_SYSTEM = """You are a professional CRM email writer.
Write a concise, friendly, professional reply to this customer email.
Keep it under 150 words. No placeholders — use the context provided.
Do not start with "Dear [Name]" — use the actual name if known.
"""

DRAFT_PROMPT = """
Lead Name: {lead_name}
Company: {company}
Lead Status: {status}
Previous Notes: {notes}

Email to reply to:
Subject: {subject}
From: {from_address}
Body:
{body}

Write a reply email body only (no subject line, no salutation header).
"""


def draft_reply(email_message, lead) -> str:
    """
    Generate an AI draft reply for an inbound email.
    Returns the draft body text.
    """
    if not OPENAI_API_KEY:
        return ''

    prompt = DRAFT_PROMPT.format(
        lead_name=lead.name,
        company=lead.company or 'their company',
        status=lead.get_status_display(),
        notes=(lead.notes or '')[:300],
        subject=email_message.subject or '(no subject)',
        from_address=email_message.from_address or '',
        body=(email_message.body_text or '')[:2000],
    )
    try:
        return _llm_text(
            [
                {'role': 'system', 'content': DRAFT_SYSTEM},
                {'role': 'user', 'content': prompt},
            ]
        )
    except Exception as e:
        logger.error('Email draft generation failed: %s', e)
        return ''


# ─── Process & Save Email ─────────────────────────────────────────────────────

def process_and_save_email(
    lead,
    subject: str,
    body_text: str,
    from_address: str,
    to_address: str,
    direction: str = 'inbound',
    message_id: str = None,
    sent_by=None,
) -> 'EmailMessage':
    """
    Save an email message and run AI classification on inbound messages.
    Creates EmailThread if it doesn't exist.
    """
    from ai.models import EmailThread, EmailMessage
    from leads.models import LeadActivity
    from django.utils import timezone

    # Get or create thread
    thread, _ = EmailThread.objects.get_or_create(lead=lead)

    # Classify inbound emails
    classification = None
    urgency_score = None
    ai_summary = None

    if direction == 'inbound' and OPENAI_API_KEY:
        try:
            result = classify_email(subject, body_text)
            classification = result['classification']
            urgency_score = result['urgency_score']
            ai_summary = result['summary']
        except Exception:
            pass

    msg = EmailMessage.objects.create(
        thread=thread,
        message_id=message_id,
        direction=direction,
        subject=subject,
        from_address=from_address,
        to_address=to_address,
        body_text=body_text,
        ai_classification=classification,
        ai_urgency_score=urgency_score,
        ai_summary=ai_summary,
        sent_by=sent_by,
        received_at=timezone.now() if direction == 'inbound' else None,
        sent_at=timezone.now() if direction == 'outbound' else None,
    )

    if direction == 'inbound':
        thread.unread_count = EmailMessage.objects.filter(
            thread=thread, direction='inbound'
        ).count()
        thread.last_synced_at = timezone.now()
        thread.save(update_fields=['unread_count', 'last_synced_at'])

    # Log activity
    LeadActivity.objects.create(
        lead=lead,
        actor=sent_by,
        activity_type='whatsapp_received' if direction == 'inbound' else 'whatsapp_sent',
        description=f'Email {"received" if direction == "inbound" else "sent"}: {subject or "(no subject)"}',
        metadata={
            'email_message_id': msg.id,
            'classification': classification,
            'urgency': urgency_score,
        }
    )
    return msg
