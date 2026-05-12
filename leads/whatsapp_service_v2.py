# leads/whatsapp_service_v2.py
# ─────────────────────────────────────────────────────────────────────────────
# Phase 2 — Complete WhatsApp Cloud API service
# Replaces the existing leads/whatsapp_service.py
# Handles: text, template, media, interactive messages + delivery tracking
# ─────────────────────────────────────────────────────────────────────────────

import requests
import logging
from django.utils import timezone
from leads.integration_models import IntegrationConfig

logger = logging.getLogger(__name__)

GRAPH_API_VERSION = "v19.0"
GRAPH_API_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"


def _get_wa_config() -> IntegrationConfig | None:
    try:
        return IntegrationConfig.objects.get(platform='whatsapp', is_active=True)
    except IntegrationConfig.DoesNotExist:
        return None


def _clean_phone(phone: str) -> str:
    """Normalize phone to E.164 digits without +"""
    cleaned = phone.replace('+', '').replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
    if not cleaned.startswith('91') and len(cleaned) == 10:
        cleaned = '91' + cleaned
    return cleaned


def _wa_headers(access_token: str) -> dict:
    return {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json',
    }


# ─── Core send functions ──────────────────────────────────────────────────────

def send_text(to: str, body: str, config: IntegrationConfig = None) -> dict:
    """Send a plain text message."""
    cfg = config or _get_wa_config()
    if not cfg:
        raise ValueError('WhatsApp integration not configured or inactive.')

    url = f"{GRAPH_API_BASE}/{cfg.whatsapp_phone_number_id}/messages"
    payload = {
        'messaging_product': 'whatsapp',
        'to': _clean_phone(to),
        'type': 'text',
        'text': {'preview_url': False, 'body': body},
    }
    resp = requests.post(url, headers=_wa_headers(cfg.whatsapp_access_token), json=payload, timeout=15)
    resp.raise_for_status()
    return resp.json()


def send_template(
    to: str,
    template_name: str,
    language_code: str = 'en_US',
    components: list = None,
    config: IntegrationConfig = None,
) -> dict:
    """Send an approved template message."""
    cfg = config or _get_wa_config()
    if not cfg:
        raise ValueError('WhatsApp integration not configured or inactive.')

    url = f"{GRAPH_API_BASE}/{cfg.whatsapp_phone_number_id}/messages"
    template_payload = {
        'name': template_name,
        'language': {'code': language_code},
    }
    if components:
        template_payload['components'] = components

    payload = {
        'messaging_product': 'whatsapp',
        'to': _clean_phone(to),
        'type': 'template',
        'template': template_payload,
    }
    resp = requests.post(url, headers=_wa_headers(cfg.whatsapp_access_token), json=payload, timeout=15)
    resp.raise_for_status()
    return resp.json()


def send_interactive_buttons(
    to: str,
    body_text: str,
    buttons: list,  # [{'id': 'yes', 'title': 'Yes'}, ...]
    header_text: str = None,
    footer_text: str = None,
    config: IntegrationConfig = None,
) -> dict:
    """Send a message with quick-reply buttons (max 3)."""
    cfg = config or _get_wa_config()
    if not cfg:
        raise ValueError('WhatsApp integration not configured or inactive.')

    url = f"{GRAPH_API_BASE}/{cfg.whatsapp_phone_number_id}/messages"

    interactive = {
        'type': 'button',
        'body': {'text': body_text},
        'action': {
            'buttons': [
                {'type': 'reply', 'reply': {'id': b['id'], 'title': b['title'][:20]}}
                for b in buttons[:3]
            ]
        },
    }
    if header_text:
        interactive['header'] = {'type': 'text', 'text': header_text}
    if footer_text:
        interactive['footer'] = {'text': footer_text}

    payload = {
        'messaging_product': 'whatsapp',
        'to': _clean_phone(to),
        'type': 'interactive',
        'interactive': interactive,
    }
    resp = requests.post(url, headers=_wa_headers(cfg.whatsapp_access_token), json=payload, timeout=15)
    resp.raise_for_status()
    return resp.json()


def send_interactive_list(
    to: str,
    body_text: str,
    button_label: str,
    sections: list,   # [{'title': 'Options', 'rows': [{'id': '1', 'title': 'Option A'}]}]
    header_text: str = None,
    footer_text: str = None,
    config: IntegrationConfig = None,
) -> dict:
    """Send a list message (dropdown-style options, max 10 items)."""
    cfg = config or _get_wa_config()
    if not cfg:
        raise ValueError('WhatsApp integration not configured or inactive.')

    url = f"{GRAPH_API_BASE}/{cfg.whatsapp_phone_number_id}/messages"
    interactive = {
        'type': 'list',
        'body': {'text': body_text},
        'action': {'button': button_label[:20], 'sections': sections},
    }
    if header_text:
        interactive['header'] = {'type': 'text', 'text': header_text}
    if footer_text:
        interactive['footer'] = {'text': footer_text}

    payload = {
        'messaging_product': 'whatsapp',
        'to': _clean_phone(to),
        'type': 'interactive',
        'interactive': interactive,
    }
    resp = requests.post(url, headers=_wa_headers(cfg.whatsapp_access_token), json=payload, timeout=15)
    resp.raise_for_status()
    return resp.json()


def resolve_media_url(media_id: str, access_token: str) -> str:
    """Resolve a Meta media_id to a downloadable URL."""
    resp = requests.get(
        f"{GRAPH_API_BASE}/{media_id}",
        headers={'Authorization': f'Bearer {access_token}'},
        timeout=10
    )
    resp.raise_for_status()
    return resp.json().get('url', '')


def mark_message_read(wa_message_id: str, config: IntegrationConfig = None) -> bool:
    """Mark an inbound message as read (shows double blue ticks to sender)."""
    cfg = config or _get_wa_config()
    if not cfg:
        return False
    try:
        url = f"{GRAPH_API_BASE}/{cfg.whatsapp_phone_number_id}/messages"
        payload = {
            'messaging_product': 'whatsapp',
            'status': 'read',
            'message_id': wa_message_id,
        }
        resp = requests.post(url, headers=_wa_headers(cfg.whatsapp_access_token), json=payload, timeout=10)
        resp.raise_for_status()
        return True
    except Exception as e:
        logger.warning('Failed to mark message as read: %s', e)
        return False


# ─── CRM-integrated send helpers ──────────────────────────────────────────────

def send_and_log(
    lead,
    body: str,
    sent_by=None,
    message_type: str = 'text',
    template=None,
) -> 'WAMessage | None':
    """
    Send a WhatsApp text message and record it in WAConversation/WAMessage.
    Returns the WAMessage instance or None on failure.
    """
    from leads.whatsapp_models import WAConversation, WAMessage

    cfg = _get_wa_config()
    if not cfg:
        logger.error('WhatsApp config missing — cannot send message.')
        return None

    # Get or create conversation
    conv, _ = WAConversation.objects.get_or_create(
        lead=lead,
        defaults={'status': 'open', 'assigned_agent': sent_by}
    )

    if conv.is_opted_out:
        logger.info('Lead %s opted out — skipping send.', lead.id)
        return None

    # Create message record (pending)
    msg = WAMessage.objects.create(
        conversation=conv,
        direction='outbound',
        message_type=message_type,
        status='pending',
        body=body,
        template=template,
        sent_by=sent_by,
    )

    try:
        result = send_text(to=lead.phone, body=body, config=cfg)
        wa_id = result.get('messages', [{}])[0].get('id', '')
        msg.wa_message_id = wa_id
        msg.status = 'sent'
        msg.sent_at = timezone.now()
        msg.save(update_fields=['wa_message_id', 'status', 'sent_at'])

        # Update conversation
        conv.last_message_at = timezone.now()
        conv.status = 'waiting'
        conv.save(update_fields=['last_message_at', 'status'])

        # Log activity
        from leads.models import LeadActivity
        LeadActivity.objects.create(
            lead=lead,
            actor=sent_by,
            activity_type='whatsapp_sent',
            description=f'WhatsApp sent: {body[:80]}...' if len(body) > 80 else f'WhatsApp sent: {body}',
        )

    except Exception as e:
        msg.status = 'failed'
        msg.failed_reason = str(e)
        msg.save(update_fields=['status', 'failed_reason'])
        logger.error('WhatsApp send failed for lead %s: %s', lead.id, e)

    return msg


def send_template_and_log(lead, wa_template, sent_by=None) -> 'WAMessage | None':
    """Send an approved template and log it."""
    from leads.whatsapp_models import WAConversation, WAMessage

    cfg = _get_wa_config()
    if not cfg:
        return None

    conv, _ = WAConversation.objects.get_or_create(
        lead=lead,
        defaults={'status': 'open', 'assigned_agent': sent_by}
    )
    if conv.is_opted_out:
        return None

    rendered = wa_template.render_body(lead, sent_by)
    components = wa_template.build_components(lead, sent_by)

    msg = WAMessage.objects.create(
        conversation=conv,
        direction='outbound',
        message_type='template',
        status='pending',
        body=rendered,
        template=wa_template,
        sent_by=sent_by,
    )

    try:
        result = send_template(
            to=lead.phone,
            template_name=wa_template.name,
            language_code=wa_template.language_code,
            components=components,
            config=cfg,
        )
        wa_id = result.get('messages', [{}])[0].get('id', '')
        msg.wa_message_id = wa_id
        msg.status = 'sent'
        msg.sent_at = timezone.now()
        msg.save(update_fields=['wa_message_id', 'status', 'sent_at'])

        conv.last_message_at = timezone.now()
        conv.status = 'waiting'
        conv.save(update_fields=['last_message_at', 'status'])

    except Exception as e:
        msg.status = 'failed'
        msg.failed_reason = str(e)
        msg.save(update_fields=['status', 'failed_reason'])
        logger.error('Template send failed for lead %s: %s', lead.id, e)

    return msg


# ─── Opt-out handler ──────────────────────────────────────────────────────────

STOP_KEYWORDS = {'stop', 'unsubscribe', 'opt out', 'optout', 'cancel', 'quit', 'end'}

def handle_opt_out_check(conversation, message_body: str) -> bool:
    """
    Check if message is an opt-out. If so, mark conversation & return True.
    """
    from leads.whatsapp_models import WAConversation
    body_lower = message_body.strip().lower()
    if any(keyword in body_lower for keyword in STOP_KEYWORDS):
        WAConversation.objects.filter(pk=conversation.pk).update(is_opted_out=True)
        logger.info('Lead %s opted out of WhatsApp.', conversation.lead_id)
        return True
    return False
