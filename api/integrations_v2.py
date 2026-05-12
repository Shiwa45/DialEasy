# api/integrations_v2.py
# ─────────────────────────────────────────────────────────────────────────────
# Phase 2 — Full WhatsApp webhook handler replacement
# Replaces the existing api/integrations.py whatsapp_webhook function.
# Meta Lead Ads, IndiaMart, JustDial webhooks remain unchanged.
#
# The new whatsapp_webhook now:
#   1. Stores every inbound message in WAConversation/WAMessage
#   2. Updates delivery/read status receipts
#   3. Runs auto-reply rules
#   4. Handles opt-outs
#   5. Resolves media URLs
# ─────────────────────────────────────────────────────────────────────────────

import json
import logging
import requests

from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone

from leads.models import Lead, LeadActivity
from leads.integration_models import IntegrationConfig, IntegrationLog
from leads.whatsapp_models import WAConversation, WAMessage, WAAutoReply, WATemplate
from leads.whatsapp_service_v2 import (
    send_and_log, send_template_and_log, handle_opt_out_check,
    resolve_media_url, mark_message_read, _get_wa_config,
)
from ai.chatbot_service import handle_chatbot_message

logger = logging.getLogger(__name__)

GRAPH_API_VERSION = "v19.0"
GRAPH_API_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"


# ─── Helpers (unchanged from original) ───────────────────────────────────────

def _get_config(platform: str) -> IntegrationConfig | None:
    try:
        return IntegrationConfig.objects.get(platform=platform, is_active=True)
    except IntegrationConfig.DoesNotExist:
        return None


def _log(platform, payload, created, status, error=''):
    IntegrationLog.objects.create(
        platform=platform, raw_payload=payload[:5000],
        lead_created=created, status=status, error_message=error or None,
    )


# ─── WhatsApp Webhook — Full Implementation ────────────────────────────────────

@csrf_exempt
@require_http_methods(['GET', 'POST'])
def whatsapp_webhook(request):
    """
    GET  — Meta webhook verification
    POST — Incoming messages, status updates, interactive replies
    """
    config = _get_config('whatsapp')

    # ── Verification ──────────────────────────────────────────────────────────
    if request.method == 'GET':
        if not config:
            return HttpResponse('Integration not configured', status=503)
        mode = request.GET.get('hub.mode')
        token = request.GET.get('hub.verify_token')
        challenge = request.GET.get('hub.challenge')
        if mode == 'subscribe' and token == config.whatsapp_verify_token:
            logger.info('WhatsApp webhook verified')
            return HttpResponse(challenge, status=200)
        return HttpResponse('Verification failed', status=403)

    # ── Incoming Notification ─────────────────────────────────────────────────
    raw = request.body.decode('utf-8', errors='replace')
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return HttpResponse('Bad Request', status=400)

    for entry in data.get('entry', []):
        for change in entry.get('changes', []):
            value = change.get('value', {})

            # ── Inbound messages ──────────────────────────────────────────────
            for msg in value.get('messages', []):
                try:
                    _process_inbound_message(msg, value, raw, config)
                except Exception as e:
                    logger.error('Error processing inbound WA message: %s', e)

            # ── Status updates (sent/delivered/read/failed) ───────────────────
            for status_update in value.get('statuses', []):
                try:
                    _process_status_update(status_update)
                except Exception as e:
                    logger.error('Error processing WA status update: %s', e)

    return HttpResponse('EVENT_RECEIVED', status=200)


def _process_inbound_message(msg: dict, value: dict, raw: str, config):
    """
    Process a single inbound WhatsApp message notification.
    Creates/updates WAConversation and WAMessage records.
    """
    sender = msg.get('from', '')        # Phone number (digits only, no +)
    msg_id = msg.get('id', '')
    msg_type = msg.get('type', 'text')
    timestamp = msg.get('timestamp')

    if not sender:
        return

    # ── Get or create Lead ───────────────────────────────────────────────────
    lead, lead_created = Lead.objects.get_or_create(
        phone=sender,
        defaults={
            'name': value.get('contacts', [{}])[0].get('profile', {}).get('name', 'WhatsApp Contact'),
            'source': 'WhatsApp',
        }
    )
    _log('whatsapp', raw, lead_created, 'success' if lead_created else 'duplicate')

    # ── Get or create Conversation ───────────────────────────────────────────
    conv, _ = WAConversation.objects.get_or_create(
        lead=lead,
        defaults={'status': 'open'}
    )

    # ── Extract message content ───────────────────────────────────────────────
    body = ''
    media_id = None
    media_mime = None
    media_url = None
    media_filename = None
    caption = None

    if msg_type == 'text':
        body = msg.get('text', {}).get('body', '')

    elif msg_type in ('image', 'video', 'audio', 'sticker'):
        media_data = msg.get(msg_type, {})
        media_id = media_data.get('id')
        media_mime = media_data.get('mime_type')
        caption = media_data.get('caption')
        # Resolve media URL asynchronously in production; for now log the ID
        if config and media_id:
            try:
                media_url = resolve_media_url(media_id, config.whatsapp_access_token)
            except Exception:
                pass

    elif msg_type == 'document':
        doc = msg.get('document', {})
        media_id = doc.get('id')
        media_mime = doc.get('mime_type')
        media_filename = doc.get('filename')
        caption = doc.get('caption')

    elif msg_type == 'interactive':
        # Handle button reply or list reply
        interactive = msg.get('interactive', {})
        if interactive.get('type') == 'button_reply':
            body = interactive.get('button_reply', {}).get('title', '')
        elif interactive.get('type') == 'list_reply':
            body = interactive.get('list_reply', {}).get('title', '')

    # ── Save message ─────────────────────────────────────────────────────────
    # Prevent duplicates via wa_message_id
    if msg_id and WAMessage.objects.filter(wa_message_id=msg_id).exists():
        return

    wa_msg = WAMessage.objects.create(
        conversation=conv,
        wa_message_id=msg_id,
        direction='inbound',
        message_type=msg_type,
        status='received',
        body=body,
        media_id=media_id,
        media_url=media_url,
        media_mime_type=media_mime,
        media_filename=media_filename,
        caption=caption,
    )

    # ── Update conversation ───────────────────────────────────────────────────
    conv.last_message_at = timezone.now()
    conv.status = 'open'
    conv.unread_count = WAConversation.objects.filter(pk=conv.pk).values_list('unread_count', flat=True)[0] + 1
    conv.save(update_fields=['last_message_at', 'status', 'unread_count'])

    # ── Log activity ─────────────────────────────────────────────────────────
    LeadActivity.objects.create(
        lead=lead,
        activity_type='whatsapp_received',
        description=f'WhatsApp received ({msg_type}): {body[:80]}' if body else f'WhatsApp received ({msg_type})',
    )

    # ── Mark as read ─────────────────────────────────────────────────────────
    if config and msg_id:
        mark_message_read(msg_id, config)

    # ── Opt-out check ─────────────────────────────────────────────────────────
    if body and handle_opt_out_check(conv, body):
        return  # Opted out — no auto-reply

    # ── Chatbot Handling ──────────────────────────────────────────────────────
    if body and conv.status == 'bot':
        bot_reply = handle_chatbot_message(conv, body)
        if bot_reply:
            send_and_log(lead=lead, body=bot_reply)
            return  # Bot handled it — skip standard auto-reply

    # ── Auto-reply rules ──────────────────────────────────────────────────────
    if body:
        _run_auto_reply_rules(body, lead, conv, config)


def _run_auto_reply_rules(message_body: str, lead, conv, config):
    """
    Evaluate all active WAAutoReply rules in priority order.
    Fires the first matching rule (or all if stop_processing=False).
    """
    rules = WAAutoReply.objects.filter(is_active=True).order_by('priority', 'id')

    for rule in rules:
        if not rule.matches(message_body):
            continue

        try:
            if rule.action == 'send_text' and rule.reply_text:
                send_and_log(lead=lead, body=rule.reply_text)

            elif rule.action == 'send_template' and rule.reply_template:
                send_template_and_log(lead=lead, wa_template=rule.reply_template)

            elif rule.action == 'assign_agent' and rule.assign_to_agent:
                lead.assigned_agent = rule.assign_to_agent
                lead.save(update_fields=['assigned_agent'])
                conv.assigned_agent = rule.assign_to_agent
                conv.save(update_fields=['assigned_agent'])

            elif rule.action == 'update_lead_status' and rule.lead_status_update:
                lead.status = rule.lead_status_update
                lead.save(update_fields=['status'])

            elif rule.action == 'escalate':
                conv.status = 'open'
                conv.save(update_fields=['status'])
                logger.info('Escalated conversation %s to human agent.', conv.id)

        except Exception as e:
            logger.error('Auto-reply rule %s failed: %s', rule.id, e)

        if rule.stop_processing:
            break


def _process_status_update(status_update: dict):
    """
    Handle delivery/read receipt updates from Meta.
    Updates WAMessage.status, delivered_at, read_at fields.
    """
    msg_id = status_update.get('id')
    new_status = status_update.get('status')  # sent / delivered / read / failed

    if not msg_id or not new_status:
        return

    try:
        msg = WAMessage.objects.get(wa_message_id=msg_id)
    except WAMessage.DoesNotExist:
        return

    update_fields = ['status']
    msg.status = new_status

    if new_status == 'delivered':
        msg.delivered_at = timezone.now()
        update_fields.append('delivered_at')
    elif new_status == 'read':
        msg.read_at = timezone.now()
        update_fields.append('read_at')
        # Also update broadcast recipient if applicable
        try:
            from leads.whatsapp_models import WABroadcastRecipient
            WABroadcastRecipient.objects.filter(wa_message_id=msg_id).update(status='read')
        except Exception:
            pass
    elif new_status == 'failed':
        errors = status_update.get('errors', [{}])
        msg.failed_reason = errors[0].get('message', 'Unknown error') if errors else 'Unknown error'
        update_fields.append('failed_reason')
        # Update broadcast recipient
        try:
            from leads.whatsapp_models import WABroadcastRecipient
            WABroadcastRecipient.objects.filter(wa_message_id=msg_id).update(
                status='failed', error_message=msg.failed_reason
            )
        except Exception:
            pass

    msg.save(update_fields=update_fields)


# ─── New API endpoints for send/broadcast ────────────────────────────────────

@csrf_exempt
@require_http_methods(['POST'])
def whatsapp_send_message(request):
    """
    POST /api/whatsapp/send/
    Body: { "lead_id": 5, "message": "Hello!", "message_type": "text" }
    Authenticated agents and staff can send messages.
    """
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Forbidden'}, status=403)

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    lead_id = body.get('lead_id')
    message = body.get('message', '').strip()

    if not lead_id or not message:
        return JsonResponse({'error': 'lead_id and message are required'}, status=400)

    try:
        lead = Lead.objects.get(id=lead_id)
    except Lead.DoesNotExist:
        return JsonResponse({'error': 'Lead not found'}, status=404)

    wa_msg = send_and_log(lead=lead, body=message, sent_by=request.user)
    if wa_msg is None:
        return JsonResponse({'error': 'Failed to send message (opt-out or config missing)'}, status=400)

    return JsonResponse({
        'success': True,
        'message_id': wa_msg.id,
        'wa_message_id': wa_msg.wa_message_id,
        'status': wa_msg.status,
    })


@csrf_exempt
@require_http_methods(['POST'])
def whatsapp_send_template_api(request):
    """
    POST /api/whatsapp/send-template/
    Body: { "lead_id": 5, "template_id": 3 }
    """
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Forbidden'}, status=403)

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    lead_id = body.get('lead_id')
    template_id = body.get('template_id')

    if not lead_id or not template_id:
        return JsonResponse({'error': 'lead_id and template_id are required'}, status=400)

    try:
        lead = Lead.objects.get(id=lead_id)
        template = WATemplate.objects.get(id=template_id, is_active=True, status='approved')
    except (Lead.DoesNotExist, WATemplate.DoesNotExist):
        return JsonResponse({'error': 'Lead or template not found'}, status=404)

    wa_msg = send_template_and_log(lead=lead, wa_template=template, sent_by=request.user)
    if wa_msg is None:
        return JsonResponse({'error': 'Failed to send template'}, status=400)

    return JsonResponse({'success': True, 'message_id': wa_msg.id, 'status': wa_msg.status})
