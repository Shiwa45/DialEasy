# api/serializers.py (Complete)

from rest_framework import serializers
from django.contrib.auth.models import User
from django.utils import timezone
from leads.models import Lead, CallLog, FollowUp

class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email', 'full_name', 'date_joined']
    
    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip() or obj.username

class LeadSerializer(serializers.ModelSerializer):
    assigned_agent = UserSerializer(read_only=True)
    call_count = serializers.SerializerMethodField()
    last_call_date = serializers.SerializerMethodField()
    last_call_disposition = serializers.SerializerMethodField()
    follow_up_count = serializers.SerializerMethodField()
    next_follow_up = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = Lead
        fields = [
            'id', 'name', 'phone', 'email', 'company', 'status', 'status_display',
            'assigned_agent', 'source', 'notes', 'created_at', 'updated_at',
            'call_count', 'last_call_date', 'last_call_disposition',
            'follow_up_count', 'next_follow_up'
        ]
        read_only_fields = ['created_at', 'updated_at', 'assigned_agent']
    
    def get_call_count(self, obj):
        return obj.call_logs.count()
    
    def get_last_call_date(self, obj):
        last_call = obj.call_logs.first()
        return last_call.call_date if last_call else None
    
    def get_last_call_disposition(self, obj):
        last_call = obj.call_logs.first()
        return last_call.get_disposition_display() if last_call else None
    
    def get_follow_up_count(self, obj):
        return obj.follow_ups.filter(is_completed=False).count()
    
    def get_next_follow_up(self, obj):
        next_followup = obj.follow_ups.filter(
            is_completed=False,
            follow_up_date__gte=timezone.now().date()
        ).order_by('follow_up_date', 'follow_up_time').first()
        
        if next_followup:
            return {
                'id': next_followup.id,
                'date': next_followup.follow_up_date,
                'time': next_followup.follow_up_time,
                'remarks': next_followup.remarks
            }
        return None

class LeadDetailSerializer(LeadSerializer):
    """Detailed lead serializer with full call logs and follow-ups"""
    recent_call_logs = serializers.SerializerMethodField()
    upcoming_follow_ups = serializers.SerializerMethodField()
    
    class Meta(LeadSerializer.Meta):
        fields = LeadSerializer.Meta.fields + ['recent_call_logs', 'upcoming_follow_ups']
    
    def get_recent_call_logs(self, obj):
        recent_calls = obj.call_logs.order_by('-call_date')[:5]
        return CallLogSerializer(recent_calls, many=True).data
    
    def get_upcoming_follow_ups(self, obj):
        upcoming = obj.follow_ups.filter(
            is_completed=False,
            follow_up_date__gte=timezone.now().date()
        ).order_by('follow_up_date', 'follow_up_time')[:3]
        return FollowUpSerializer(upcoming, many=True).data

class CallLogSerializer(serializers.ModelSerializer):
    agent = UserSerializer(read_only=True)
    lead = serializers.SerializerMethodField()
    lead_id = serializers.IntegerField(write_only=True, required=False)
    disposition_display = serializers.CharField(source='get_disposition_display', read_only=True)
    duration_display = serializers.SerializerMethodField()
    
    class Meta:
        model = CallLog
        fields = [
            'id', 'lead', 'lead_id', 'agent', 'call_date', 'duration', 'duration_display',
            'disposition', 'disposition_display', 'remarks', 'created_at'
        ]
        read_only_fields = ['created_at', 'agent']
    
    def get_lead(self, obj):
        return {
            'id': obj.lead.id,
            'name': obj.lead.name,
            'phone': obj.lead.phone,
            'company': obj.lead.company,
        }
    
    def get_duration_display(self, obj):
        if obj.duration:
            total_seconds = int(obj.duration.total_seconds())
            minutes = total_seconds // 60
            seconds = total_seconds % 60
            return f"{minutes}:{seconds:02d}"
        return None
    
    def create(self, validated_data):
        validated_data['agent'] = self.context['request'].user
        if 'lead_id' in validated_data:
            validated_data['lead_id'] = validated_data.pop('lead_id')
        return super().create(validated_data)

class FollowUpSerializer(serializers.ModelSerializer):
    agent = UserSerializer(read_only=True)
    lead = serializers.SerializerMethodField()
    lead_id = serializers.IntegerField(write_only=True, required=False)
    is_overdue = serializers.SerializerMethodField()
    is_today = serializers.SerializerMethodField()
    formatted_datetime = serializers.SerializerMethodField()
    
    class Meta:
        model = FollowUp
        fields = [
            'id', 'lead', 'lead_id', 'agent', 'follow_up_date', 'follow_up_time',
            'remarks', 'is_completed', 'created_at', 'completed_at',
            'is_overdue', 'is_today', 'formatted_datetime'
        ]
        read_only_fields = ['created_at', 'completed_at', 'agent']
    
    def get_lead(self, obj):
        return {
            'id': obj.lead.id,
            'name': obj.lead.name,
            'phone': obj.lead.phone,
            'company': obj.lead.company,
        }
    
    def get_is_overdue(self, obj):
        if obj.is_completed:
            return False
        follow_up_datetime = timezone.datetime.combine(obj.follow_up_date, obj.follow_up_time)
        return timezone.make_aware(follow_up_datetime) < timezone.now()
    
    def get_is_today(self, obj):
        return obj.follow_up_date == timezone.now().date()
    
    def get_formatted_datetime(self, obj):
        return f"{obj.follow_up_date.strftime('%b %d, %Y')} at {obj.follow_up_time.strftime('%I:%M %p')}"
    
    def create(self, validated_data):
        validated_data['agent'] = self.context['request'].user
        if 'lead_id' in validated_data:
            validated_data['lead_id'] = validated_data.pop('lead_id')
        return super().create(validated_data)

# Simplified serializers for creating records
class LeadUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating lead status and notes"""
    
    class Meta:
        model = Lead
        fields = ['status', 'notes']
    
    def validate_status(self, value):
        valid_statuses = [choice[0] for choice in Lead.STATUS_CHOICES]
        if value not in valid_statuses:
            raise serializers.ValidationError(f"Invalid status. Must be one of: {', '.join(valid_statuses)}")
        return value

class CallLogCreateSerializer(serializers.ModelSerializer):
    """Simplified serializer for creating call logs from mobile app"""
    
    class Meta:
        model = CallLog
        fields = ['disposition', 'remarks', 'duration']
    
    def validate_disposition(self, value):
        valid_dispositions = [choice[0] for choice in CallLog.DISPOSITION_CHOICES]
        if value not in valid_dispositions:
            raise serializers.ValidationError(f"Invalid disposition. Must be one of: {', '.join(valid_dispositions)}")
        return value
    
    def create(self, validated_data):
        # These will be set in the view context
        validated_data['agent'] = self.context['request'].user
        validated_data['lead'] = self.context['lead']
        return super().create(validated_data)

class FollowUpCreateSerializer(serializers.ModelSerializer):
    """Simplified serializer for creating follow-ups from mobile app"""
    
    class Meta:
        model = FollowUp
        fields = ['follow_up_date', 'follow_up_time', 'remarks']
    
    def validate_follow_up_date(self, value):
        if value < timezone.now().date():
            raise serializers.ValidationError("Follow-up date cannot be in the past")
        return value
    
    def validate(self, data):
        """Validate that follow-up datetime is in the future"""
        follow_up_date = data.get('follow_up_date')
        follow_up_time = data.get('follow_up_time')
        
        if follow_up_date and follow_up_time:
            follow_up_datetime = timezone.datetime.combine(follow_up_date, follow_up_time)
            if timezone.make_aware(follow_up_datetime) <= timezone.now():
                raise serializers.ValidationError("Follow-up must be scheduled for a future time")
        
        return data
    
    def create(self, validated_data):
        # These will be set in the view context
        validated_data['agent'] = self.context['request'].user
        validated_data['lead'] = self.context['lead']
        return super().create(validated_data)

# Statistics and dashboard serializers
class AgentStatsSerializer(serializers.Serializer):
    """Serializer for agent statistics and dashboard data"""
    
    # Summary stats
    total_leads = serializers.IntegerField()
    new_leads = serializers.IntegerField()
    contacted_leads = serializers.IntegerField()
    converted_leads = serializers.IntegerField()
    conversion_rate = serializers.FloatField()
    
    # Activity stats
    today_calls = serializers.IntegerField()
    today_follow_ups = serializers.IntegerField()
    week_calls = serializers.IntegerField()
    pending_follow_ups = serializers.IntegerField()
    overdue_follow_ups = serializers.IntegerField()
    
    # Recent activity
    recent_calls = CallLogSerializer(many=True)
    upcoming_follow_ups = FollowUpSerializer(many=True)
    
    # Lead status breakdown
    lead_statuses = serializers.ListField(child=serializers.DictField())

class DashboardSerializer(serializers.Serializer):
    """Serializer for mobile app dashboard"""
    
    summary = serializers.DictField()
    lead_statuses = serializers.ListField(child=serializers.DictField())
    recent_calls = CallLogSerializer(many=True)
    upcoming_follow_ups = FollowUpSerializer(many=True)
    monthly_targets = serializers.DictField(allow_null=True)

class PerformanceMetricsSerializer(serializers.Serializer):
    """Serializer for performance metrics"""
    
    period = serializers.CharField()
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    
    total_calls = serializers.IntegerField()
    total_leads = serializers.IntegerField()
    total_conversions = serializers.IntegerField()
    conversion_rate = serializers.FloatField()
    avg_calls_per_day = serializers.FloatField()
    
    daily_performance = serializers.ListField(child=serializers.DictField())
    disposition_breakdown = serializers.ListField(child=serializers.DictField())

# Utility serializers
class ChoiceSerializer(serializers.Serializer):
    """Serializer for choice fields"""
    value = serializers.CharField()
    label = serializers.CharField()

class AppConfigSerializer(serializers.Serializer):
    """Serializer for app configuration"""
    
    lead_statuses = ChoiceSerializer(many=True)
    call_dispositions = ChoiceSerializer(many=True)
    agent_targets = serializers.DictField()
    app_settings = serializers.DictField()

# Bulk operation serializers
class BulkUpdateSerializer(serializers.Serializer):
    """Serializer for bulk operations"""
    
    lead_ids = serializers.ListField(child=serializers.IntegerField())
    updates = serializers.DictField()
    
    def validate_lead_ids(self, value):
        if not value:
            raise serializers.ValidationError("At least one lead ID is required")
        if len(value) > 100:
            raise serializers.ValidationError("Cannot update more than 100 leads at once")
        return value
    
    def validate_updates(self, value):
        allowed_fields = ['status', 'notes']
        invalid_fields = set(value.keys()) - set(allowed_fields)
        if invalid_fields:
            raise serializers.ValidationError(f"Invalid update fields: {', '.join(invalid_fields)}")
        return value

# Sync serializers
class SyncUploadSerializer(serializers.Serializer):
    """Serializer for offline sync upload"""
    
    call_logs = serializers.ListField(child=serializers.DictField(), required=False, default=list)
    follow_ups = serializers.ListField(child=serializers.DictField(), required=False, default=list)
    lead_updates = serializers.ListField(child=serializers.DictField(), required=False, default=list)

class SyncDownloadSerializer(serializers.Serializer):
    """Serializer for offline sync download"""
    
    leads = LeadSerializer(many=True)
    call_logs = CallLogSerializer(many=True)
    follow_ups = FollowUpSerializer(many=True)
    sync_timestamp = serializers.DateTimeField()

# Error response serializers
class ErrorSerializer(serializers.Serializer):
    """Serializer for error responses"""
    
    error = serializers.CharField()
    details = serializers.DictField(required=False)
    code = serializers.CharField(required=False)

class ValidationErrorSerializer(serializers.Serializer):
    """Serializer for validation error responses"""
    
    field_errors = serializers.DictField()
    non_field_errors = serializers.ListField(child=serializers.CharField(), required=False)