# leads/models.py

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

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
    ]

    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=20, unique=True)
    email = models.EmailField(blank=True, null=True)
    company = models.CharField(max_length=200, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')
    assigned_agent = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='assigned_leads'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Additional fields
    source = models.CharField(max_length=100, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ['-created_at']
        
    def __str__(self):
        return f"{self.name} - {self.phone}"
    
    @property
    def last_call_log(self):
        return self.call_logs.first()
    
    @property
    def call_count(self):
        return self.call_logs.count()


class CallLog(models.Model):
    DISPOSITION_CHOICES = [
        ('interested', 'Interested'),
        ('not_interested', 'Not Interested'),
        ('callback', 'Callback Later'),
        ('wrong_number', 'Wrong Number'),
        ('not_reachable', 'Not Reachable'),
        ('busy', 'Busy'),
        ('voicemail', 'Voicemail'),
        ('follow_up', 'Follow-up Required'),
    ]

    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='call_logs')
    agent = models.ForeignKey(User, on_delete=models.CASCADE, related_name='call_logs')
    call_date = models.DateTimeField(default=timezone.now)
    duration = models.DurationField(null=True, blank=True)  # Call duration
    disposition = models.CharField(max_length=20, choices=DISPOSITION_CHOICES)
    remarks = models.TextField(blank=True, null=True)
    # Call recording
    recording = models.FileField(upload_to='call_recordings/', null=True, blank=True)
    recording_size = models.IntegerField(default=0)  # Size in bytes
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-call_date']
        
    def __str__(self):
        return f"{self.lead.name} - {self.disposition} by {self.agent.username}"


class FollowUp(models.Model):
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='follow_ups')
    agent = models.ForeignKey(User, on_delete=models.CASCADE, related_name='follow_ups')
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
        from datetime import datetime, time
        follow_up_datetime = datetime.combine(self.follow_up_date, self.follow_up_time)
        return not self.is_completed and follow_up_datetime < timezone.now()


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
        return f"Upload by {self.uploaded_by.username} - {self.status}"

# Import integration models so they are picked up by migrations
from leads.integration_models import IntegrationConfig, IntegrationLog  # noqa: E402, F401