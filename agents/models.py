# agents/models.py

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class AgentProfile(models.Model):
    """Extended profile for agents with additional information"""
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='agent_profile')
    phone = models.CharField(max_length=20, blank=True, null=True)
    department = models.CharField(max_length=100, blank=True, null=True)
    hire_date = models.DateField(default=timezone.now)
    is_active = models.BooleanField(default=True)
    target_calls_per_day = models.IntegerField(default=50)
    target_conversions_per_month = models.IntegerField(default=10)
    call_recording_enabled = models.BooleanField(default=False)  # Admin toggle for call recording
    
    # Performance tracking
    total_leads_assigned = models.IntegerField(default=0)
    total_calls_made = models.IntegerField(default=0)
    total_conversions = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} - Agent Profile"
    
    @property
    def conversion_rate(self):
        if self.total_leads_assigned > 0:
            return round((self.total_conversions / self.total_leads_assigned) * 100, 2)
        return 0
    
    @property
    def calls_per_lead(self):
        if self.total_leads_assigned > 0:
            return round(self.total_calls_made / self.total_leads_assigned, 2)
        return 0
    
    def update_stats(self):
        """Update agent statistics from related models"""
        from leads.models import Lead, CallLog
        
        try:
            # Update lead count
            self.total_leads_assigned = Lead.objects.filter(assigned_agent=self.user).count()
            
            # Update call count
            self.total_calls_made = CallLog.objects.filter(agent=self.user).count()
            
            # Update conversion count
            self.total_conversions = Lead.objects.filter(
                assigned_agent=self.user, 
                status='converted'
            ).count()
            
            self.save()
        except Exception as e:
            # Handle any database errors gracefully
            pass


class AgentTarget(models.Model):
    """Monthly targets for agents"""
    
    agent = models.ForeignKey(User, on_delete=models.CASCADE, related_name='targets')
    month = models.DateField()  # First day of the month
    target_calls = models.IntegerField(default=0)
    target_conversions = models.IntegerField(default=0)
    target_revenue = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Achievements
    actual_calls = models.IntegerField(default=0)
    actual_conversions = models.IntegerField(default=0)
    actual_revenue = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['agent', 'month']
        ordering = ['-month']
    
    def __str__(self):
        return f"{self.agent.username} - {self.month.strftime('%B %Y')}"
    
    @property
    def calls_achievement_percentage(self):
        if self.target_calls > 0:
            return min(round((self.actual_calls / self.target_calls) * 100, 1), 100)
        return 0
    
    @property
    def conversions_achievement_percentage(self):
        if self.target_conversions > 0:
            return min(round((self.actual_conversions / self.target_conversions) * 100, 1), 100)
        return 0
    
    @property
    def revenue_achievement_percentage(self):
        if self.target_revenue > 0:
            return min(round((float(self.actual_revenue) / float(self.target_revenue)) * 100, 1), 100)
        return 0


class AgentNote(models.Model):
    """Internal notes about agents"""
    
    agent = models.ForeignKey(User, on_delete=models.CASCADE, related_name='agent_notes')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_agent_notes')
    note = models.TextField()
    is_private = models.BooleanField(default=False)  # Only visible to managers
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Note for {self.agent.username} by {self.created_by.username}"


# ─── Agent Time Tracking ───────────────────────────────────────────────────────

class DialerSession(models.Model):
    """Tracks each autodialer session an agent runs."""

    agent = models.ForeignKey(User, on_delete=models.CASCADE, related_name='dialer_sessions')
    session_start = models.DateTimeField(default=timezone.now)
    session_end = models.DateTimeField(null=True, blank=True)
    # Computed on session_end (in seconds)
    total_call_time_seconds = models.IntegerField(default=0)
    total_disposition_time_seconds = models.IntegerField(default=0)
    total_calls_made = models.IntegerField(default=0)

    class Meta:
        ordering = ['-session_start']

    def __str__(self):
        return f"{self.agent.username} session @ {self.session_start.strftime('%Y-%m-%d %H:%M')}"

    @property
    def session_duration_seconds(self):
        end = self.session_end or timezone.now()
        return max(0, int((end - self.session_start).total_seconds()))

    @property
    def idle_time_seconds(self):
        return max(0, self.session_duration_seconds
                   - self.total_call_time_seconds
                   - self.total_disposition_time_seconds)

    @property
    def session_duration_display(self):
        return _fmt_seconds(self.session_duration_seconds)

    @property
    def talk_time_display(self):
        return _fmt_seconds(self.total_call_time_seconds)

    @property
    def disposition_time_display(self):
        return _fmt_seconds(self.total_disposition_time_seconds)

    @property
    def idle_time_display(self):
        return _fmt_seconds(self.idle_time_seconds)

    def finalize(self):
        """Close the session and compute aggregates from events."""
        self.session_end = timezone.now()

        events = list(self.events.order_by('timestamp'))
        call_secs = 0
        disp_secs = 0
        calls = 0

        call_start_ts = None
        disp_start_ts = None

        for ev in events:
            if ev.event_type == 'call_started':
                call_start_ts = ev.timestamp
                calls += 1
            elif ev.event_type == 'call_ended' and call_start_ts:
                call_secs += int((ev.timestamp - call_start_ts).total_seconds())
                call_start_ts = None
            elif ev.event_type == 'disposition_started':
                disp_start_ts = ev.timestamp
            elif ev.event_type == 'disposition_submitted' and disp_start_ts:
                disp_secs += int((ev.timestamp - disp_start_ts).total_seconds())
                disp_start_ts = None

        self.total_call_time_seconds = call_secs
        self.total_disposition_time_seconds = disp_secs
        self.total_calls_made = calls
        self.save()


class CallActivityEvent(models.Model):
    """Lightweight event log for agent activity during a dialer session."""

    EVENT_CHOICES = [
        ('session_start', 'Session Started'),
        ('session_end', 'Session Ended'),
        ('call_started', 'Call Started'),
        ('call_ended', 'Call Ended'),
        ('disposition_started', 'Disposition Started'),
        ('disposition_submitted', 'Disposition Submitted'),
    ]

    agent = models.ForeignKey(User, on_delete=models.CASCADE, related_name='activity_events')
    session = models.ForeignKey(
        DialerSession, on_delete=models.CASCADE, related_name='events',
        null=True, blank=True
    )
    event_type = models.CharField(max_length=30, choices=EVENT_CHOICES)
    timestamp = models.DateTimeField(default=timezone.now)
    lead = models.ForeignKey(
        'leads.Lead', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='activity_events'
    )
    call_log = models.ForeignKey(
        'leads.CallLog', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='activity_events'
    )
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"{self.agent.username} – {self.event_type} @ {self.timestamp.strftime('%H:%M:%S')}"


def _fmt_seconds(secs):
    """Format seconds as HH:MM:SS."""
    h = secs // 3600
    m = (secs % 3600) // 60
    s = secs % 60
    return f"{h:02d}:{m:02d}:{s:02d}"