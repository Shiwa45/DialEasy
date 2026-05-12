# notifications/service.py
# ─────────────────────────────────────────────────────────────────────────────
# Central notification service.
# All notification creation goes through create_notification().
# FCM push is attempted after every in-app notification is created.
# ─────────────────────────────────────────────────────────────────────────────

import logging
import requests
from django.conf import settings
from django.contrib.auth.models import User
from .models import Notification, FCMToken

logger = logging.getLogger(__name__)

# ── FCM v1 API ────────────────────────────────────────────────────────────────
# Set in settings.py:
#   FCM_SERVER_KEY = 'your-fcm-server-key'        ← legacy HTTP v1
#   FCM_PROJECT_ID = 'your-firebase-project-id'   ← for v1 OAuth
FCM_LEGACY_URL = 'https://fcm.googleapis.com/fcm/send'


def _send_fcm_push(recipient: User, title: str, body: str, action_data: dict = None) -> bool:
    """
    Send a Firebase push notification to all active FCM tokens of the user.
    Uses FCM Legacy HTTP API (simplest setup — no OAuth required).
    Returns True if at least one push succeeded.
    """
    server_key = getattr(settings, 'FCM_SERVER_KEY', None)
    if not server_key:
        logger.debug('FCM_SERVER_KEY not set — skipping push notification.')
        return False

    tokens = list(
        FCMToken.objects.filter(agent=recipient, is_active=True)
        .values_list('token', flat=True)
    )
    if not tokens:
        return False

    payload = {
        'registration_ids': tokens,
        'notification': {
            'title': title,
            'body': body,
            'sound': 'default',
            'badge': '1',
        },
        'data': action_data or {},
        'priority': 'high',
        'content_available': True,
    }
    headers = {
        'Authorization': f'key={server_key}',
        'Content-Type': 'application/json',
    }
    try:
        resp = requests.post(FCM_LEGACY_URL, json=payload, headers=headers, timeout=10)
        result = resp.json()

        # Deactivate invalid tokens
        if 'results' in result:
            for token, res in zip(tokens, result['results']):
                if res.get('error') in ('NotRegistered', 'InvalidRegistration'):
                    FCMToken.objects.filter(token=token).update(is_active=False)
                    logger.info('Deactivated invalid FCM token for %s', recipient.username)

        success_count = result.get('success', 0)
        logger.info('FCM push to %s: %d/%d succeeded', recipient.username, success_count, len(tokens))
        return success_count > 0

    except Exception as e:
        logger.error('FCM push failed for %s: %s', recipient.username, e)
        return False


# ── Main factory ──────────────────────────────────────────────────────────────

def create_notification(
    recipient: User,
    notification_type: str,
    title: str,
    body: str,
    action_data: dict = None,
    related_lead_id: int = None,
    send_push: bool = True,
) -> Notification:
    """
    Create an in-app notification and optionally send an FCM push.

    Usage:
        from notifications.service import create_notification

        create_notification(
            recipient=agent_user,
            notification_type='lead_assigned',
            title='New Lead Assigned',
            body='Raj Kumar (9876543210) has been assigned to you.',
            action_data={'screen': 'lead_detail', 'lead_id': 42},
            related_lead_id=42,
        )
    """
    notif = Notification.objects.create(
        recipient=recipient,
        notification_type=notification_type,
        title=title,
        body=body,
        action_data=action_data or {},
        related_lead_id=related_lead_id,
    )

    if send_push:
        _send_fcm_push(recipient, title, body, action_data or {})

    return notif


# ── Convenience helpers ───────────────────────────────────────────────────────

def notify_lead_assigned(lead, agent: User):
    create_notification(
        recipient=agent,
        notification_type='lead_assigned',
        title='New Lead Assigned 👤',
        body=f'{lead.name} ({lead.phone}) has been assigned to you.',
        action_data={'screen': 'lead_detail', 'lead_id': lead.id},
        related_lead_id=lead.id,
    )


def notify_follow_up_due(follow_up, agent: User):
    create_notification(
        recipient=agent,
        notification_type='follow_up_due',
        title='Follow-up Due 📅',
        body=f'{follow_up.lead.name} — scheduled at {follow_up.follow_up_time.strftime("%I:%M %p")}',
        action_data={'screen': 'lead_detail', 'lead_id': follow_up.lead.id},
        related_lead_id=follow_up.lead.id,
    )


def notify_follow_up_overdue(follow_up, agent: User):
    create_notification(
        recipient=agent,
        notification_type='follow_up_overdue',
        title='Overdue Follow-up ⚠️',
        body=f'{follow_up.lead.name} — was due {follow_up.follow_up_date}',
        action_data={'screen': 'lead_detail', 'lead_id': follow_up.lead.id},
        related_lead_id=follow_up.lead.id,
    )


def notify_task_assigned(task, agent: User):
    create_notification(
        recipient=agent,
        notification_type='task_assigned',
        title='New Task Assigned ✅',
        body=f'[{task.get_priority_display()}] {task.title}',
        action_data={'screen': 'lead_detail', 'lead_id': task.lead.id, 'tab': 'tasks'},
        related_lead_id=task.lead.id,
    )


def notify_whatsapp_received(lead, agent: User, message_preview: str = ''):
    create_notification(
        recipient=agent,
        notification_type='whatsapp_received',
        title=f'WhatsApp from {lead.name} 💬',
        body=message_preview[:100] if message_preview else 'New WhatsApp message',
        action_data={'screen': 'whatsapp_chat', 'lead_id': lead.id},
        related_lead_id=lead.id,
    )


def notify_task_due(task, agent: User):
    create_notification(
        recipient=agent,
        notification_type='task_due',
        title='Task Due Soon ⏰',
        body=f'[{task.get_priority_display()}] {task.title} — due {task.due_date.strftime("%I:%M %p") if task.due_date else "today"}',
        action_data={'screen': 'tasks'},
    )
