# leads/models.py
# ─────────────────────────────────────────────────────────────────────────────
# PHASE 1 — Enhanced Lead Management
# New models: LeadNote, LeadTask, Product, LeadProduct, LeadActivity
# Enhanced Lead: score, deal_value
# Enhanced FollowUp: priority, title
# Auto-assignment: AssignmentRule
# ─────────────────────────────────────────────────────────────────────────────

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models import Count, Q
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver


# ─── Lead ─────────────────────────────────────────────────────────────────────

class Lead(models.Model):
    STATUS_CHOICES = [
        ('new', 'New'),
        ('contacted', 'Contacted'),
        ('interested', 'Interested'),
        ('not_interested', 'Not Interested'),
        ('callback', 'Callback Later'),
        ('wrong_number', 'Wrong Number'),
        ('not_reachable', 'Not Reachable'),
        ('converted', 'Converted'),
        ('lost', 'Lost'),
    ]

    # ── Core fields (unchanged) ───────────────────────────────────────────────
    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=20, unique=True)
    email = models.EmailField(blank=True, null=True)
    company = models.CharField(max_length=200, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')
    assigned_agent = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='assigned_leads'
    )
    source = models.CharField(max_length=100, blank=True, null=True)

    # ── PHASE 1: kept for backward compat, but prefer LeadNote model ──────────
    notes = models.TextField(
        blank=True, null=True,
        help_text='Legacy notes field. New notes are stored in LeadNote.'
    )

    # ── PHASE 1: New fields ───────────────────────────────────────────────────
    lead_score = models.IntegerField(
        default=0,
        help_text='Auto-calculated engagement score (0-100). Higher = hotter lead.'
    )
    deal_value = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text='Estimated deal/revenue value in INR.'
    )
    city = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    website = models.URLField(blank=True, null=True)
    designation = models.CharField(max_length=100, blank=True, null=True)
    industry = models.CharField(max_length=100, blank=True, null=True)
    expected_close_date = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-lead_score', '-created_at']

    def __str__(self):
        return f"{self.name} — {self.phone}"

    # ── Convenience properties ────────────────────────────────────────────────

    @property
    def last_call_log(self):
        return self.call_logs.first()

    @property
    def call_count(self):
        return self.call_logs.count()

    @property
    def score_label(self):
        if self.lead_score >= 75:
            return 'Hot'
        if self.lead_score >= 40:
            return 'Warm'
        return 'Cold'

    def recalculate_score(self):
        """
        Score formula (max 100):
          - Each call log          : +8  pts (max 30)
          - Completed follow-up    : +10 pts (max 20)
          - Status progression pts : up to 30
          - Has deal_value set     : +10 pts
          - Recent activity <7d    : +10 pts
        """
        score = 0

        # Call activity (max 30)
        call_count = self.call_logs.count()
        score += min(call_count * 8, 30)

        # Follow-ups completed (max 20)
        completed_fups = self.follow_ups.filter(is_completed=True).count()
        score += min(completed_fups * 10, 20)

        # Status score (max 30)
        status_scores = {
            'new': 0, 'contacted': 5, 'callback': 10,
            'interested': 25, 'not_interested': 0,
            'wrong_number': 0, 'not_reachable': 0,
            'converted': 30, 'lost': 0,
        }
        score += status_scores.get(self.status, 0)

        # Deal value set (max 10)
        if self.deal_value and self.deal_value > 0:
            score += 10

        # Recent activity bonus (max 10)
        seven_days_ago = timezone.now() - timezone.timedelta(days=7)
        recent = self.call_logs.filter(call_date__gte=seven_days_ago).exists()
        if recent:
            score += 10

        self.lead_score = min(score, 100)
        Lead.objects.filter(pk=self.pk).update(lead_score=self.lead_score)
        return self.lead_score


# ─── Call Log (unchanged structure, kept here for reference) ─────────────────

class CallLog(models.Model):
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='call_logs')
    agent = models.ForeignKey(User, on_delete=models.CASCADE, related_name='call_logs')
    call_date = models.DateTimeField(default=timezone.now)
    duration = models.DurationField(null=True, blank=True)
    # Disposition slug — validated against tenants.Disposition at the API layer.
    # max_length 50 to support custom disposition values.
    disposition = models.CharField(max_length=50)
    remarks = models.TextField(blank=True, null=True)
    recording = models.FileField(upload_to='call_recordings/', null=True, blank=True)
    recording_size = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-call_date']

    def __str__(self):
        return f"{self.lead.name} — {self.disposition} by {self.agent.username}"


# ─── Follow Up (enhanced with priority + title) ───────────────────────────────

class FollowUp(models.Model):
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]

    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='follow_ups')
    agent = models.ForeignKey(User, on_delete=models.CASCADE, related_name='follow_ups')

    # PHASE 1: new field
    title = models.CharField(max_length=200, blank=True, null=True, help_text='Short title e.g. "Price discussion callback"')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')

    follow_up_date = models.DateField()
    follow_up_time = models.TimeField()
    remarks = models.TextField(blank=True, null=True)
    is_completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['follow_up_date', 'follow_up_time']

    def __str__(self):
        return f"Follow-up: {self.lead.name} on {self.follow_up_date}"

    @property
    def is_overdue(self):
        from datetime import datetime
        follow_up_datetime = datetime.combine(self.follow_up_date, self.follow_up_time)
        return not self.is_completed and timezone.make_aware(follow_up_datetime) < timezone.now()


# ─── Lead Note (replaces single-text notes field) ────────────────────────────

class LeadNote(models.Model):
    NOTE_TYPE_CHOICES = [
        ('general', 'General'),
        ('call', 'Call Summary'),
        ('meeting', 'Meeting'),
        ('email', 'Email'),
        ('whatsapp', 'WhatsApp'),
        ('internal', 'Internal (Private)'),
    ]

    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='lead_notes')
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='lead_notes')
    note_type = models.CharField(max_length=20, choices=NOTE_TYPE_CHOICES, default='general')
    content = models.TextField()
    is_pinned = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_pinned', '-created_at']

    def __str__(self):
        return f"Note on {self.lead.name} by {self.author}"


# ─── Lead Task ────────────────────────────────────────────────────────────────

class LeadTask(models.Model):
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled'),
    ]

    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='tasks')
    assigned_to = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='lead_tasks'
    )
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name='created_tasks'
    )
    title = models.CharField(max_length=300)
    description = models.TextField(blank=True, null=True)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    due_date = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-priority', 'due_date']

    def __str__(self):
        return f"[{self.priority.upper()}] {self.title} — {self.lead.name}"

    @property
    def is_overdue(self):
        return (
            self.status not in ('done', 'cancelled') and
            self.due_date is not None and
            self.due_date < timezone.now()
        )


# ─── Product ──────────────────────────────────────────────────────────────────

class Product(models.Model):
    name = models.CharField(max_length=200)
    sku = models.CharField(max_length=100, unique=True, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    unit = models.CharField(max_length=50, blank=True, null=True, help_text='e.g. pcs, kg, month')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} (₹{self.price})"


class LeadProduct(models.Model):
    """Links products to a lead (what the lead is interested in buying)."""
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='lead_products')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='lead_products')
    quantity = models.PositiveIntegerField(default=1)
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    note = models.CharField(max_length=300, blank=True, null=True)
    added_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['lead', 'product']

    def __str__(self):
        return f"{self.product.name} × {self.quantity} → {self.lead.name}"

    @property
    def total_price(self):
        base = self.product.price * self.quantity
        discount = base * (self.discount_percent / 100)
        return base - discount


# ─── Lead Activity Log ────────────────────────────────────────────────────────

class LeadActivity(models.Model):
    """
    Immutable audit trail. One row per event on a lead.
    Created automatically via signals and explicit calls — never edited.
    """
    ACTIVITY_CHOICES = [
        ('created', 'Lead Created'),
        ('status_changed', 'Status Changed'),
        ('assigned', 'Lead Assigned'),
        ('call_logged', 'Call Logged'),
        ('note_added', 'Note Added'),
        ('note_edited', 'Note Edited'),
        ('follow_up_created', 'Follow-up Created'),
        ('follow_up_completed', 'Follow-up Completed'),
        ('task_created', 'Task Created'),
        ('task_completed', 'Task Completed'),
        ('product_added', 'Product Added'),
        ('product_removed', 'Product Removed'),
        ('deal_value_updated', 'Deal Value Updated'),
        ('whatsapp_sent', 'WhatsApp Sent'),
        ('whatsapp_received', 'WhatsApp Received'),
        ('field_updated', 'Field Updated'),
    ]

    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='activities')
    actor = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='lead_activities'
    )
    activity_type = models.CharField(max_length=30, choices=ACTIVITY_CHOICES)
    description = models.TextField(help_text='Human-readable description of the event.')
    old_value = models.CharField(max_length=500, blank=True, null=True)
    new_value = models.CharField(max_length=500, blank=True, null=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.activity_type}] {self.lead.name} — {self.created_at:%Y-%m-%d %H:%M}"


# ─── Auto-Assignment Rule ─────────────────────────────────────────────────────

class AssignmentRule(models.Model):
    """
    Configures how new leads are automatically assigned to agents.
    Only one rule should be active at a time per tenant.
    """
    STRATEGY_CHOICES = [
        ('round_robin', 'Round Robin (equal rotation)'),
        ('load_balanced', 'Load Balanced (least assigned agent)'),
        ('source_based', 'Source Based (route by lead source)'),
        ('manual', 'Manual (no auto-assignment)'),
    ]

    name = models.CharField(max_length=100, default='Default Rule')
    strategy = models.CharField(max_length=20, choices=STRATEGY_CHOICES, default='round_robin')
    is_active = models.BooleanField(default=True)

    # Pool of agents eligible for auto-assignment (empty = all active agents)
    eligible_agents = models.ManyToManyField(
        User, blank=True, related_name='assignment_rules',
        help_text='Leave empty to include ALL active agents.'
    )

    # Source-based routing: maps source keyword → agent
    source_routing = models.JSONField(
        default=dict, blank=True,
        help_text='For source_based strategy. e.g. {"meta": 3, "indiamart": 5} (agent user IDs)'
    )

    # Internal state for round-robin
    last_assigned_agent_id = models.IntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_active', '-created_at']

    def __str__(self):
        return f"{self.name} ({self.get_strategy_display()})"

    def get_next_agent(self, lead_source=None):
        """
        Returns the User to assign, based on strategy.
        Returns None if no eligible agent is found.
        """
        from django.contrib.auth.models import User as AuthUser

        # Build eligible agent pool
        if self.eligible_agents.exists():
            pool = list(self.eligible_agents.filter(is_active=True))
        else:
            # AgentProfile is a TENANT_APP so this queryset is scoped to the
            # current tenant's schema — only agents belonging to this tenant
            # are returned.
            from agents.models import AgentProfile
            tenant_agent_ids = AgentProfile.objects.filter(
                is_active=True
            ).values_list('user_id', flat=True)
            pool = list(AuthUser.objects.filter(
                id__in=tenant_agent_ids,
                is_active=True,
            ).select_related('agent_profile'))

        if not pool:
            return None

        # Source-based routing
        if self.strategy == 'source_based' and lead_source and self.source_routing:
            for keyword, agent_id in self.source_routing.items():
                if keyword.lower() in (lead_source or '').lower():
                    try:
                        return AuthUser.objects.get(pk=agent_id)
                    except AuthUser.DoesNotExist:
                        pass

        # Load balanced: pick agent with fewest assigned leads
        if self.strategy == 'load_balanced':
            agent_loads = {
                agent: Lead.objects.filter(assigned_agent=agent).count()
                for agent in pool
            }
            return min(agent_loads, key=agent_loads.get)

        # Round-robin (default)
        if not self.last_assigned_agent_id:
            chosen = pool[0]
        else:
            ids = [a.id for a in pool]
            try:
                idx = ids.index(self.last_assigned_agent_id)
                chosen = pool[(idx + 1) % len(pool)]
            except ValueError:
                chosen = pool[0]

        AssignmentRule.objects.filter(pk=self.pk).update(last_assigned_agent_id=chosen.id)
        return chosen


# ─── Legacy models kept unchanged ─────────────────────────────────────────────

class LeadUpload(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    file = models.FileField(upload_to='lead_uploads/')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    total_records = models.IntegerField(default=0)
    processed_records = models.IntegerField(default=0)
    failed_records = models.IntegerField(default=0)
    error_log = models.TextField(blank=True, null=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Upload by {self.uploaded_by.username} — {self.status}"


# ─── Signals ──────────────────────────────────────────────────────────────────

@receiver(pre_save, sender=Lead)
def log_lead_changes(sender, instance, **kwargs):
    """Log status and assignment changes to LeadActivity."""
    if not instance.pk:
        return  # New lead — handled by post_save
    try:
        old = Lead.objects.get(pk=instance.pk)

        if old.status != instance.status:
            LeadActivity.objects.create(
                lead=instance,
                activity_type='status_changed',
                description=f'Status changed from {old.get_status_display()} to {instance.get_status_display()}',
                old_value=old.status,
                new_value=instance.status,
            )

        if old.assigned_agent_id != instance.assigned_agent_id:
            new_agent_name = instance.assigned_agent.get_full_name() if instance.assigned_agent else 'Unassigned'
            old_agent_name = old.assigned_agent.get_full_name() if old.assigned_agent else 'Unassigned'
            LeadActivity.objects.create(
                lead=instance,
                activity_type='assigned',
                description=f'Assigned from {old_agent_name} to {new_agent_name}',
                old_value=str(old.assigned_agent_id),
                new_value=str(instance.assigned_agent_id),
            )

        if old.deal_value != instance.deal_value:
            LeadActivity.objects.create(
                lead=instance,
                activity_type='deal_value_updated',
                description=f'Deal value updated to ₹{instance.deal_value or 0:,.0f}',
                old_value=str(old.deal_value),
                new_value=str(instance.deal_value),
            )
    except Lead.DoesNotExist:
        pass


@receiver(post_save, sender=Lead)
def log_lead_created(sender, instance, created, **kwargs):
    """Log creation and recalculate score."""
    if created:
        LeadActivity.objects.create(
            lead=instance,
            activity_type='created',
            description=f'Lead created from source: {instance.source or "manual"}',
        )
    # Recalculate score on every save (debounced by model-level query)
    instance.recalculate_score()


@receiver(post_save, sender=CallLog)
def on_call_logged(sender, instance, created, **kwargs):
    if created:
        LeadActivity.objects.create(
            lead=instance.lead,
            actor=instance.agent,
            activity_type='call_logged',
            description=f'Call logged: {instance.get_disposition_display()}. Duration: {instance.duration or "unknown"}',
            metadata={'call_log_id': instance.pk, 'disposition': instance.disposition},
        )
        # Recalculate score after new call
        instance.lead.recalculate_score()


@receiver(post_save, sender=LeadNote)
def on_note_added(sender, instance, created, **kwargs):
    if created:
        LeadActivity.objects.create(
            lead=instance.lead,
            actor=instance.author,
            activity_type='note_added',
            description=f'Note added ({instance.get_note_type_display()}): {instance.content[:80]}...' if len(instance.content) > 80 else f'Note added: {instance.content}',
        )


@receiver(post_save, sender=FollowUp)
def on_follow_up(sender, instance, created, **kwargs):
    if created:
        LeadActivity.objects.create(
            lead=instance.lead,
            actor=instance.agent,
            activity_type='follow_up_created',
            description=f'Follow-up scheduled for {instance.follow_up_date} at {instance.follow_up_time}',
        )
    elif instance.is_completed and instance.completed_at:
        # Only log completion once
        if not LeadActivity.objects.filter(
            lead=instance.lead,
            activity_type='follow_up_completed',
            metadata__follow_up_id=instance.pk
        ).exists():
            LeadActivity.objects.create(
                lead=instance.lead,
                actor=instance.agent,
                activity_type='follow_up_completed',
                description=f'Follow-up completed (was scheduled for {instance.follow_up_date})',
                metadata={'follow_up_id': instance.pk},
            )


@receiver(post_save, sender=LeadTask)
def on_task_saved(sender, instance, created, **kwargs):
    if created:
        LeadActivity.objects.create(
            lead=instance.lead,
            actor=instance.created_by,
            activity_type='task_created',
            description=f'Task created: [{instance.get_priority_display()}] {instance.title}',
        )
    elif instance.status == 'done' and instance.completed_at:
        if not LeadActivity.objects.filter(
            lead=instance.lead,
            activity_type='task_completed',
            metadata__task_id=instance.pk
        ).exists():
            LeadActivity.objects.create(
                lead=instance.lead,
                actor=instance.assigned_to,
                activity_type='task_completed',
                description=f'Task completed: {instance.title}',
                metadata={'task_id': instance.pk},
            )


# Keep integration models import
from leads.integration_models import IntegrationConfig, IntegrationLog  # noqa
from leads.whatsapp_models import WAMessage, WAConversation, WATemplate, WABroadcast, WABroadcastRecipient  # noqa
