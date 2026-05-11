# leads/integration_models.py
from django.db import models
from django.contrib.auth.models import User


class IntegrationConfig(models.Model):
    """Stores credentials for external lead integrations"""

    PLATFORM_CHOICES = [
        ('meta', 'Meta (Facebook Lead Ads)'),
        ('indiamart', 'IndiaMart'),
        ('justdial', 'JustDial'),
        ('whatsapp', 'WhatsApp Business API'),
    ]

    platform = models.CharField(max_length=30, choices=PLATFORM_CHOICES, unique=True)
    is_active = models.BooleanField(default=False)

    # ─── Meta / WhatsApp shared ─────────────────────────────────
    app_id = models.CharField(
        max_length=200, blank=True, null=True,
        help_text='Meta App ID (used by Meta Lead Ads & WhatsApp)'
    )
    app_secret = models.CharField(
        max_length=300, blank=True, null=True,
        help_text='Meta App Secret'
    )
    # Meta Lead Ads
    page_access_token = models.TextField(
        blank=True, null=True,
        help_text='Meta Page Access Token with leads_retrieval permission'
    )
    verify_token = models.CharField(
        max_length=200, blank=True, null=True,
        help_text='Custom verify token you set when subscribing the webhook in Meta App Dashboard'
    )

    # ─── WhatsApp Cloud API ──────────────────────────────────────
    whatsapp_phone_number_id = models.CharField(
        max_length=200, blank=True, null=True,
        help_text='WhatsApp Business Phone Number ID from Meta Dashboard'
    )
    whatsapp_access_token = models.TextField(
        blank=True, null=True,
        help_text='Permanent WhatsApp Cloud API Access Token'
    )
    whatsapp_verify_token = models.CharField(
        max_length=200, blank=True, null=True,
        help_text='Verify token for the WhatsApp webhook endpoint'
    )

    # ─── Metadata ────────────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='integration_updates'
    )

    class Meta:
        verbose_name = 'Integration Configuration'
        verbose_name_plural = 'Integration Configurations'

    def __str__(self):
        return f"{self.get_platform_display()} ({'Active' if self.is_active else 'Inactive'})"


class IntegrationLog(models.Model):
    """Logs every incoming webhook event for debugging"""

    STATUS_CHOICES = [
        ('success', 'Success'),
        ('duplicate', 'Duplicate (Skipped)'),
        ('error', 'Error'),
    ]

    platform = models.CharField(max_length=30)
    raw_payload = models.TextField(blank=True)
    lead_created = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='success')
    error_message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Integration Log'
        verbose_name_plural = 'Integration Logs'

    def __str__(self):
        return f"[{self.platform}] {self.status} – {self.created_at:%Y-%m-%d %H:%M}"
