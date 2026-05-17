# leads/whatsapp_models.py
# ─────────────────────────────────────────────────────────────────────────────
# Phase 2 — WhatsApp Full Feature Models
# WAConversation  : one thread per lead (all messages in/out)
# WAMessage       : individual message with status tracking
# WATemplate      : approved message templates stored per tenant
# WABroadcast     : bulk send job with per-lead tracking
# WAAutoReply     : keyword-trigger → auto response rules
# ─────────────────────────────────────────────────────────────────────────────

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from leads.models import Lead


# ─── Provider Configuration ───────────────────────────────────────────────────

class WAProvider(models.Model):
    """
    Per-tenant WhatsApp provider credentials.
    Supports Meta Cloud API, Twilio, WATI, AiSensy, and Interakt.
    Only one provider can be marked is_default=True at a time.
    """
    PROVIDER_CHOICES = [
        ('meta',     'Meta (WhatsApp Cloud API)'),
        ('twilio',   'Twilio WhatsApp'),
        ('wati',     'WATI'),
        ('aisensy',  'AiSensy'),
        ('interakt', 'Interakt'),
    ]

    name = models.CharField(max_length=100, help_text='Friendly label, e.g. "Main Meta Account"')
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES)
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False, help_text='Used for new campaigns when no provider is selected')

    # ─── Meta ───────────────────────────────────────────────────────
    meta_phone_number_id = models.CharField(max_length=200, blank=True)
    meta_access_token = models.TextField(blank=True)
    meta_verify_token = models.CharField(max_length=200, blank=True)

    # ─── Twilio ─────────────────────────────────────────────────────
    twilio_account_sid = models.CharField(max_length=200, blank=True)
    twilio_auth_token = models.CharField(max_length=200, blank=True)
    twilio_from_number = models.CharField(max_length=50, blank=True,
        help_text='Format: whatsapp:+14155238886')

    # ─── WATI ───────────────────────────────────────────────────────
    wati_api_endpoint = models.URLField(max_length=300, blank=True,
        help_text='e.g. https://live-mt-server.wati.io/api')
    wati_api_key = models.TextField(blank=True)

    # ─── AiSensy ────────────────────────────────────────────────────
    aisensy_api_key = models.TextField(blank=True)

    # ─── Interakt ───────────────────────────────────────────────────
    interakt_api_key = models.TextField(blank=True)

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
        related_name='wa_providers')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_default', 'name']

    def __str__(self):
        return f'{self.name} ({self.get_provider_display()})'

    def save(self, *args, **kwargs):
        if self.is_default:
            WAProvider.objects.exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)


# ─── Conversation ─────────────────────────────────────────────────────────────

class WAConversation(models.Model):
    """
    One conversation thread per lead.
    Created automatically when the first message (in or out) is sent.
    """
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('closed', 'Closed'),
        ('bot', 'Bot Handling'),          # AI chatbot is managing
        ('waiting', 'Waiting for Reply'), # Outbound sent, no reply yet
    ]

    lead = models.OneToOneField(
        Lead, on_delete=models.CASCADE, related_name='wa_conversation'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    assigned_agent = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='wa_conversations'
    )
    is_opted_out = models.BooleanField(
        default=False,
        help_text='Lead sent STOP / opted out of WhatsApp messages.'
    )
    last_message_at = models.DateTimeField(null=True, blank=True)
    unread_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-last_message_at']

    def __str__(self):
        return f"WA: {self.lead.name} ({self.status})"

    def mark_read(self):
        self.unread_count = 0
        WAConversation.objects.filter(pk=self.pk).update(unread_count=0)


# ─── Message ──────────────────────────────────────────────────────────────────

class WAMessage(models.Model):
    DIRECTION_CHOICES = [
        ('inbound', 'Inbound'),   # From lead to us
        ('outbound', 'Outbound'), # From us to lead
    ]
    TYPE_CHOICES = [
        ('text', 'Text'),
        ('image', 'Image'),
        ('document', 'Document'),
        ('audio', 'Audio'),
        ('video', 'Video'),
        ('template', 'Template'),
        ('interactive', 'Interactive (Button/List)'),
        ('sticker', 'Sticker'),
        ('location', 'Location'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending'),       # Created, not yet sent to Meta
        ('sent', 'Sent'),             # Accepted by Meta API
        ('delivered', 'Delivered'),   # Delivered to device
        ('read', 'Read'),             # Read by recipient
        ('failed', 'Failed'),         # Rejected / error
        ('received', 'Received'),     # Inbound message
    ]

    conversation = models.ForeignKey(
        WAConversation, on_delete=models.CASCADE, related_name='messages'
    )
    # Meta's unique message ID (wamid.xxx) — for status update matching
    wa_message_id = models.CharField(max_length=200, blank=True, null=True, db_index=True)

    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES)
    message_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='text')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    # Content
    body = models.TextField(blank=True, null=True)              # Text body
    media_url = models.URLField(blank=True, null=True)          # Resolved media URL
    media_id = models.CharField(max_length=200, blank=True, null=True)  # Meta media_id
    media_mime_type = models.CharField(max_length=100, blank=True, null=True)
    media_filename = models.CharField(max_length=300, blank=True, null=True)
    caption = models.TextField(blank=True, null=True)           # For image/video captions

    # Template reference (if message_type == 'template')
    template = models.ForeignKey(
        'WATemplate', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sent_messages'
    )

    # Who sent outbound messages (null for inbound)
    sent_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='wa_messages_sent'
    )

    # Timestamps from Meta webhook
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    failed_reason = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        direction = '→' if self.direction == 'outbound' else '←'
        preview = (self.body or '')[:50]
        return f"{direction} {preview}"


# ─── Template ─────────────────────────────────────────────────────────────────

class WATemplate(models.Model):
    """
    Stores Meta-approved WhatsApp message templates per tenant.
    Templates are required for outbound messages outside the 24-hour session window.
    """
    CATEGORY_CHOICES = [
        ('marketing', 'Marketing'),
        ('utility', 'Utility'),
        ('authentication', 'Authentication'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('paused', 'Paused'),
    ]

    name = models.CharField(
        max_length=200,
        help_text='Template name as registered in Meta Business Manager (e.g. follow_up_v1)'
    )
    display_name = models.CharField(max_length=200, help_text='Friendly name shown in CRM')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='utility')
    language_code = models.CharField(max_length=20, default='en_US')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    # The template body with variable placeholders {{1}}, {{2}}, etc.
    body_text = models.TextField(
        help_text='Template body. Use {{1}}, {{2}} for variables. '
                  'Variable names: {{name}}, {{company}}, {{agent_name}}, {{date}}'
    )
    header_text = models.CharField(max_length=300, blank=True, null=True)
    footer_text = models.CharField(max_length=300, blank=True, null=True)

    # Variable definitions — maps position to field on Lead/Agent
    # e.g. {"1": "lead.name", "2": "agent.first_name", "3": "custom"}
    variable_mapping = models.JSONField(
        default=dict, blank=True,
        help_text='Maps template variable positions to Lead/Agent fields.'
    )

    # Button definitions for interactive templates
    buttons = models.JSONField(
        default=list, blank=True,
        help_text='List of button dicts. e.g. [{"type": "QUICK_REPLY", "text": "Yes"}]'
    )

    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='wa_templates')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['display_name']

    def __str__(self):
        return f"{self.display_name} ({self.language_code}) — {self.status}"

    def render_body(self, lead: 'Lead', agent: User = None) -> str:
        """
        Substitute template variables with actual lead/agent data.
        Supports: {{name}}, {{company}}, {{agent_name}}, {{1}}, {{2}}, etc.
        """
        text = self.body_text
        replacements = {
            '{{name}}': lead.name,
            '{{company}}': lead.company or '',
            '{{phone}}': lead.phone,
            '{{agent_name}}': agent.get_full_name() if agent else '',
            '{{1}}': lead.name,
            '{{2}}': lead.company or '',
        }
        for placeholder, value in replacements.items():
            text = text.replace(placeholder, str(value))
        return text

    def build_components(self, lead: 'Lead', agent: User = None) -> list:
        """Build the Meta API components array for template messages."""
        components = []
        body_params = []

        # Build body component parameters from variable_mapping
        for pos in sorted(self.variable_mapping.keys()):
            field_path = self.variable_mapping[pos]
            value = ''
            if field_path.startswith('lead.'):
                attr = field_path.split('.', 1)[1]
                value = str(getattr(lead, attr, '') or '')
            elif field_path.startswith('agent.') and agent:
                attr = field_path.split('.', 1)[1]
                value = str(getattr(agent, attr, '') or '')
            body_params.append({'type': 'text', 'text': value or '—'})

        if body_params:
            components.append({'type': 'body', 'parameters': body_params})

        # Add buttons if defined
        if self.buttons:
            for i, btn in enumerate(self.buttons):
                if btn.get('type') == 'QUICK_REPLY':
                    components.append({
                        'type': 'button',
                        'sub_type': 'quick_reply',
                        'index': str(i),
                        'parameters': [{'type': 'payload', 'payload': btn.get('payload', btn.get('text', ''))}]
                    })

        return components


# ─── Broadcast ────────────────────────────────────────────────────────────────

class WABroadcast(models.Model):
    """
    A bulk WhatsApp broadcast campaign sent to a segment of leads.
    Supports template and text messages across multiple providers.
    Rate-limited: processed by management command (30 msgs/batch) or Celery.
    """
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('queued', 'Queued'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('paused', 'Paused'),
        ('cancelled', 'Cancelled'),
        ('failed', 'Failed'),
    ]
    MESSAGE_TYPE_CHOICES = [
        ('template', 'Template Message'),
        ('text', 'Plain Text Message'),
    ]

    name = models.CharField(max_length=200, help_text='Campaign name shown in dashboard')
    description = models.TextField(blank=True, help_text='Optional internal notes about this campaign')
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPE_CHOICES, default='template')

    # Template message
    template = models.ForeignKey(WATemplate, on_delete=models.PROTECT,
        related_name='broadcasts', null=True, blank=True)

    # Text message (used when message_type='text')
    text_body = models.TextField(blank=True,
        help_text='Plain text body. Supports {{name}}, {{company}}, {{phone}} placeholders.')

    # Provider — null falls back to default provider
    provider = models.ForeignKey('WAProvider', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='broadcasts',
        help_text='WhatsApp provider to use. Leave blank to use the default provider.')

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')

    # Lead filter snapshot at creation time
    lead_filter = models.JSONField(
        default=dict,
        help_text='{"status": "interested", "source": "Meta", "assigned_agent_id": 5}'
    )

    # Progress counters
    total_leads = models.IntegerField(default=0)
    sent_count = models.IntegerField(default=0)
    delivered_count = models.IntegerField(default=0)
    read_count = models.IntegerField(default=0)
    replied_count = models.IntegerField(default=0)
    failed_count = models.IntegerField(default=0)
    opted_out_skipped = models.IntegerField(default=0)

    scheduled_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='wa_broadcasts')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} ({self.status}) — {self.sent_count}/{self.total_leads}'

    @property
    def delivery_rate(self):
        return round(self.delivered_count / self.sent_count * 100, 1) if self.sent_count else 0

    @property
    def read_rate(self):
        return round(self.read_count / self.delivered_count * 100, 1) if self.delivered_count else 0

    def render_text_body(self, lead) -> str:
        """Substitute {{name}}, {{company}}, {{phone}} in text_body."""
        text = self.text_body
        for placeholder, value in {
            '{{name}}': lead.name,
            '{{company}}': lead.company or '',
            '{{phone}}': lead.phone,
        }.items():
            text = text.replace(placeholder, str(value))
        return text


class WABroadcastRecipient(models.Model):
    """Tracks the per-lead send status of a broadcast."""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('read', 'Read'),
        ('failed', 'Failed'),
        ('skipped', 'Skipped (opted-out)'),
    ]

    broadcast = models.ForeignKey(WABroadcast, on_delete=models.CASCADE, related_name='recipients')
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='broadcast_receipts')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    wa_message_id = models.CharField(max_length=200, blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ['broadcast', 'lead']
        ordering = ['id']


# ─── Auto Reply Rules ─────────────────────────────────────────────────────────

class WAAutoReply(models.Model):
    """
    Keyword-trigger rules for automatic WhatsApp responses.
    Evaluated in priority order when an inbound message arrives.
    """
    ACTION_CHOICES = [
        ('send_text', 'Send Text Message'),
        ('send_template', 'Send Template Message'),
        ('assign_agent', 'Assign to Agent'),
        ('update_lead_status', 'Update Lead Status'),
        ('escalate', 'Escalate to Human Agent'),
    ]

    name = models.CharField(max_length=200)
    is_active = models.BooleanField(default=True)
    priority = models.IntegerField(default=0, help_text='Lower = evaluated first')

    # Trigger conditions
    keywords = models.TextField(
        help_text='Comma-separated keywords that trigger this rule. '
                  'e.g. "price,pricing,cost,quote". Case-insensitive.'
    )
    match_exact = models.BooleanField(
        default=False,
        help_text='If True, full message must exactly match. If False, keyword search within message.'
    )

    # Action
    action = models.CharField(max_length=30, choices=ACTION_CHOICES, default='send_text')
    reply_text = models.TextField(
        blank=True, null=True,
        help_text='Text to send (for send_text action).'
    )
    reply_template = models.ForeignKey(
        WATemplate, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='auto_reply_rules',
        help_text='Template to send (for send_template action).'
    )
    assign_to_agent = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='wa_auto_reply_assignments'
    )
    lead_status_update = models.CharField(
        max_length=20, blank=True, null=True,
        help_text='New lead status to set (for update_lead_status action).'
    )

    # Stop processing further rules after this one fires
    stop_processing = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['priority', 'id']

    def __str__(self):
        return f"[P{self.priority}] {self.name} → {self.get_action_display()}"

    def matches(self, message_body: str) -> bool:
        """Check if the incoming message triggers this rule."""
        if not message_body:
            return False
        body = message_body.strip().lower()
        keywords = [k.strip().lower() for k in self.keywords.split(',') if k.strip()]
        if self.match_exact:
            return body in keywords
        return any(kw in body for kw in keywords)
