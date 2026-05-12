# ai/chatbot_service.py
# ─────────────────────────────────────────────────────────────────────────────
# Phase 4 — WhatsApp AI Chatbot Service
# LLM-powered chatbot that handles inbound WA messages, qualifies leads,
# and escalates to human agents when needed.
# Integrates with integrations_v2.py auto-reply pipeline.
# ─────────────────────────────────────────────────────────────────────────────

import json
import logging
import os
import requests
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
CHAT_URL = 'https://api.openai.com/v1/chat/completions'

DEFAULT_SYSTEM_PROMPT = """
You are a helpful CRM assistant for {company_name}. Your job is to:
1. Greet the customer warmly
2. Understand what product/service they are interested in
3. Collect basic qualification info (name if not known, product interest, budget range, timeline)
4. Answer common questions about products if asked
5. Schedule follow-ups if the customer is interested
6. Escalate to a human agent if: customer is angry, request is complex, or they ask for a human

Keep responses SHORT (max 2-3 sentences). Be conversational and professional.
Respond in the same language the customer writes in.
If customer writes in Hindi, reply in Hindi. If English, reply in English.

Do not make promises about pricing or delivery that you cannot guarantee.
If unsure, say you will have an agent follow up.
"""


def _openai_headers() -> dict:
    return {
        'Authorization': f'Bearer {OPENAI_API_KEY}',
        'Content-Type': 'application/json',
    }


def _should_escalate(message: str, flow) -> bool:
    """Check if message contains escalation keywords."""
    keywords = flow.get_escalation_keywords()
    message_lower = message.lower()
    return any(kw in message_lower for kw in keywords)


def _call_llm(messages: list, system_prompt: str, max_tokens: int = 200) -> str:
    """Call OpenAI GPT-4o-mini with conversation history."""
    if not OPENAI_API_KEY:
        return "Thank you for your message. An agent will contact you shortly."

    all_messages = [{'role': 'system', 'content': system_prompt}] + messages

    payload = {
        'model': 'gpt-4o-mini',
        'messages': all_messages,
        'temperature': 0.7,
        'max_tokens': max_tokens,
    }
    try:
        resp = requests.post(CHAT_URL, headers=_openai_headers(), json=payload, timeout=15)
        resp.raise_for_status()
        return resp.json()['choices'][0]['message']['content'].strip()
    except Exception as e:
        logger.error('LLM call failed: %s', e)
        return "Thank you for reaching out. Our team will respond shortly."


def _extract_qualification_data(history: list, flow) -> dict:
    """
    Ask LLM to extract qualification answers from conversation history.
    Returns dict of question→answer pairs.
    """
    if not OPENAI_API_KEY or not flow.qualification_questions:
        return {}

    questions_str = '\n'.join(f'- {q}' for q in flow.qualification_questions)
    conversation_str = '\n'.join(
        f"{'Customer' if m['role'] == 'user' else 'Bot'}: {m['content']}"
        for m in history[-10:]  # Last 10 turns
    )

    prompt = f"""Extract answers to these qualification questions from the conversation.
Return ONLY valid JSON with question keys (snake_case) and string values.
If not answered, use null.

Questions:
{questions_str}

Conversation:
{conversation_str}"""

    try:
        payload = {
            'model': 'gpt-4o-mini',
            'messages': [{'role': 'user', 'content': prompt}],
            'temperature': 0.1,
            'max_tokens': 300,
            'response_format': {'type': 'json_object'},
        }
        resp = requests.post(CHAT_URL, headers=_openai_headers(), json=payload, timeout=15)
        resp.raise_for_status()
        return json.loads(resp.json()['choices'][0]['message']['content'])
    except Exception as e:
        logger.error('Qualification extraction failed: %s', e)
        return {}


# ─── Main handler ─────────────────────────────────────────────────────────────

def handle_chatbot_message(conversation, inbound_message: str) -> str | None:
    """
    Process an inbound WA message through the AI chatbot pipeline.

    Returns:
        str: The bot's reply to send back (caller sends it via WA API)
        None: If the conversation should be escalated (caller assigns to agent)

    Called from api/integrations_v2.py after auto-reply rules when
    conversation.status == 'bot'.
    """
    from ai.models import ChatbotFlow, ChatbotSession
    from leads.whatsapp_models import WAConversation

    lead = conversation.lead

    # ── Get active flow ───────────────────────────────────────────────────────
    try:
        flow = ChatbotFlow.objects.filter(is_active=True).first()
        if not flow:
            logger.info('No active chatbot flow — skipping bot handling.')
            return None
    except Exception:
        return None

    # ── Get or create session ─────────────────────────────────────────────────
    session, created = ChatbotSession.objects.get_or_create(
        conversation=conversation,
        defaults={'flow': flow, 'status': 'active', 'turn_count': 0}
    )

    if session.status in ('escalated', 'ended'):
        return None  # Human is handling — bot stays silent

    # ── Escalation keyword check ─────────────────────────────────────────────
    if _should_escalate(inbound_message, flow):
        _escalate_session(session, conversation)
        return "I'm connecting you with one of our team members right away. Please hold on! 🙏"

    # ── Max turns check ──────────────────────────────────────────────────────
    if session.turn_count >= flow.max_turns_before_escalation:
        _escalate_session(session, conversation)
        return "I'll have one of our specialists reach out to you directly. Thanks for your patience!"

    # ── Build system prompt ───────────────────────────────────────────────────
    company_name = getattr(settings, 'COMPANY_NAME', 'our company')
    system_prompt = flow.system_prompt.replace('{company_name}', company_name)

    # ── Append user message to history ───────────────────────────────────────
    history = session.history or []
    history.append({'role': 'user', 'content': inbound_message})

    # ── Call LLM ─────────────────────────────────────────────────────────────
    bot_reply = _call_llm(history, system_prompt)

    # ── Append bot reply to history ───────────────────────────────────────────
    history.append({'role': 'assistant', 'content': bot_reply})

    # ── Update session ────────────────────────────────────────────────────────
    session.history = history
    session.turn_count += 1

    # ── Check if lead is qualified ────────────────────────────────────────────
    qualification = _extract_qualification_data(history, flow)
    if qualification:
        session.qualification_data = qualification
        # If all key questions answered, mark as qualified
        answered = sum(1 for v in qualification.values() if v is not None)
        if answered >= max(1, len(flow.qualification_questions) - 1):
            session.status = 'qualified'
            # Update lead score and notes
            _apply_qualification_to_lead(lead, qualification)

    session.save(update_fields=['history', 'turn_count', 'status', 'qualification_data'])

    return bot_reply


def _escalate_session(session, conversation):
    """Mark session as escalated, set conversation status to open for human."""
    from leads.whatsapp_models import WAConversation
    session.status = 'escalated'
    session.ended_at = timezone.now()
    session.save(update_fields=['status', 'ended_at'])
    WAConversation.objects.filter(pk=conversation.pk).update(status='open')
    logger.info('Bot session escalated for lead %d', conversation.lead_id)


def _apply_qualification_to_lead(lead, qualification: dict):
    """Write qualification data back to the lead model."""
    try:
        updates = {}
        if qualification.get('budget') and not lead.deal_value:
            # Try to extract a number from budget string
            import re
            numbers = re.findall(r'\d+', str(qualification['budget']).replace(',', ''))
            if numbers:
                updates['deal_value'] = float(numbers[0])
        if qualification.get('product_interest') and not lead.notes:
            updates['notes'] = f"Bot qualified: {qualification}"
        if updates:
            from leads.models import Lead
            Lead.objects.filter(pk=lead.pk).update(**updates)
    except Exception as e:
        logger.error('Failed to apply qualification to lead %d: %s', lead.id, e)
