# notifications/models.py
# ─────────────────────────────────────────────────────────────────────────────
# Phase 3 — In-app Notification System
# One table per tenant (lives in TENANT_APPS).
# FCM push tokens stored on AgentProfile via new field (migration patch).
# ─────────────────────────────────────────────────────────────────────────────

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Notification(models.Model):
    TYPE_CHOICES = [
        ('lead_assigned',        'New Lead Assigned'),
        ('follow_up_due',        'Follow-up Due'),
        ('follow_up_overdue',    'Follow-up Overdue'),
        ('task_due',             'Task Due'),
        ('task_assigned',        'Task Assigned'),
        ('whatsapp_received',    'WhatsApp Message Received'),
        ('call_missed',          'Missed Call'),
        ('lead_status_changed',  'Lead Status Changed'),
        ('broadcast_completed',  'Broadcast Completed'),
        ('daily_summary',        'Daily Summary'),
        ('system',               'System Message'),
    ]

    recipient = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='notifications'
    )
    notification_type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    title = models.CharField(max_length=200)
    body = models.TextField()
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    # Deep-link data for Flutter navigation
    # e.g. {"screen": "lead_detail", "lead_id": 5}
    #      {"screen": "whatsapp_chat", "lead_id": 5}
    #      {"screen": "follow_up_list"}
    action_data = models.JSONField(default=dict, blank=True)

    # Optional link to related objects
    related_lead_id = models.IntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read']),
            models.Index(fields=['recipient', 'created_at']),
        ]

    def __str__(self):
        return f"[{self.notification_type}] → {self.recipient.username}: {self.title}"

    def mark_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            Notification.objects.filter(pk=self.pk).update(
                is_read=True, read_at=self.read_at
            )


class FCMToken(models.Model):
    """
    Stores Firebase Cloud Messaging device tokens per agent.
    One agent can have multiple device tokens (phone + tablet).
    """
    agent = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='fcm_tokens'
    )
    token = models.TextField(unique=True)
    device_type = models.CharField(
        max_length=20,
        choices=[('android', 'Android'), ('ios', 'iOS'), ('web', 'Web')],
        default='android'
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-last_used_at']

    def __str__(self):
        return f"{self.agent.username} — {self.device_type}"
