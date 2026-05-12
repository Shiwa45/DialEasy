# api/serializers.py — Phase 1 complete
# Adds: LeadNoteSerializer, LeadTaskSerializer, ProductSerializer,
#        LeadProductSerializer, LeadActivitySerializer
# Enhances: LeadSerializer (score, deal_value), LeadDetailSerializer (full nested)

from rest_framework import serializers
from django.contrib.auth.models import User
from django.utils import timezone
from leads.models import (
    Lead, CallLog, FollowUp,
    LeadNote, LeadTask, Product, LeadProduct, LeadActivity,
)


# ─── User ─────────────────────────────────────────────────────────────────────

class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email', 'full_name']

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip() or obj.username


# ─── Lead Note ────────────────────────────────────────────────────────────────

class LeadNoteSerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)
    note_type_display = serializers.CharField(source='get_note_type_display', read_only=True)

    class Meta:
        model = LeadNote
        fields = [
            'id', 'lead', 'author', 'note_type', 'note_type_display',
            'content', 'is_pinned', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'author', 'created_at', 'updated_at']

    def create(self, validated_data):
        validated_data['author'] = self.context['request'].user
        return super().create(validated_data)


class LeadNoteCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeadNote
        fields = ['note_type', 'content', 'is_pinned']

    def create(self, validated_data):
        validated_data['author'] = self.context['request'].user
        validated_data['lead'] = self.context['lead']
        return super().create(validated_data)


# ─── Lead Task ────────────────────────────────────────────────────────────────

class LeadTaskSerializer(serializers.ModelSerializer):
    assigned_to = UserSerializer(read_only=True)
    assigned_to_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), source='assigned_to', write_only=True, required=False, allow_null=True
    )
    created_by = UserSerializer(read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)

    class Meta:
        model = LeadTask
        fields = [
            'id', 'lead', 'title', 'description', 'priority', 'priority_display',
            'status', 'status_display', 'assigned_to', 'assigned_to_id',
            'created_by', 'due_date', 'completed_at', 'is_overdue',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_by', 'completed_at', 'created_at', 'updated_at']

    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)

    def update(self, instance, validated_data):
        # Auto-set completed_at when status flips to done
        new_status = validated_data.get('status', instance.status)
        if new_status == 'done' and instance.status != 'done':
            validated_data['completed_at'] = timezone.now()
        return super().update(instance, validated_data)


# ─── Product ──────────────────────────────────────────────────────────────────

class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ['id', 'name', 'sku', 'description', 'price', 'unit', 'is_active', 'created_at']
        read_only_fields = ['id', 'created_at']


class LeadProductSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.filter(is_active=True),
        source='product', write_only=True
    )
    total_price = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    added_by = UserSerializer(read_only=True)

    class Meta:
        model = LeadProduct
        fields = [
            'id', 'lead', 'product', 'product_id', 'quantity',
            'discount_percent', 'total_price', 'note', 'added_by', 'added_at'
        ]
        read_only_fields = ['id', 'added_by', 'added_at']

    def create(self, validated_data):
        validated_data['added_by'] = self.context['request'].user
        return super().create(validated_data)


# ─── Lead Activity ────────────────────────────────────────────────────────────

class LeadActivitySerializer(serializers.ModelSerializer):
    actor = UserSerializer(read_only=True)
    activity_type_display = serializers.CharField(source='get_activity_type_display', read_only=True)

    class Meta:
        model = LeadActivity
        fields = [
            'id', 'lead', 'actor', 'activity_type', 'activity_type_display',
            'description', 'old_value', 'new_value', 'metadata', 'created_at'
        ]
        read_only_fields = fields


# ─── Lead (list view — lightweight) ──────────────────────────────────────────

class LeadSerializer(serializers.ModelSerializer):
    assigned_agent = UserSerializer(read_only=True)
    call_count = serializers.SerializerMethodField()
    last_call_date = serializers.SerializerMethodField()
    last_call_disposition = serializers.SerializerMethodField()
    follow_up_count = serializers.SerializerMethodField()
    next_follow_up = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    score_label = serializers.CharField(read_only=True)

    class Meta:
        model = Lead
        fields = [
            'id', 'name', 'phone', 'email', 'company', 'status', 'status_display',
            'assigned_agent', 'source', 'notes',
            # Phase 1 additions
            'lead_score', 'score_label', 'deal_value',
            'city', 'state', 'industry', 'designation',
            'created_at', 'updated_at',
            'call_count', 'last_call_date', 'last_call_disposition',
            'follow_up_count', 'next_follow_up',
        ]
        read_only_fields = ['created_at', 'updated_at', 'assigned_agent', 'lead_score']

    def get_call_count(self, obj):
        return obj.call_logs.count()

    def get_last_call_date(self, obj):
        last = obj.call_logs.first()
        return last.call_date if last else None

    def get_last_call_disposition(self, obj):
        last = obj.call_logs.first()
        return last.get_disposition_display() if last else None

    def get_follow_up_count(self, obj):
        return obj.follow_ups.filter(is_completed=False).count()

    def get_next_follow_up(self, obj):
        nfu = obj.follow_ups.filter(
            is_completed=False,
            follow_up_date__gte=timezone.now().date()
        ).order_by('follow_up_date', 'follow_up_time').first()
        if nfu:
            return {
                'id': nfu.id,
                'date': str(nfu.follow_up_date),
                'time': str(nfu.follow_up_time),
                'priority': nfu.priority,
                'title': nfu.title,
            }
        return None


# ─── Lead Detail (full nested view) ──────────────────────────────────────────

class LeadDetailSerializer(LeadSerializer):
    call_logs = serializers.SerializerMethodField()
    follow_ups = serializers.SerializerMethodField()
    lead_notes = LeadNoteSerializer(many=True, read_only=True)
    tasks = LeadTaskSerializer(many=True, read_only=True)
    lead_products = LeadProductSerializer(many=True, read_only=True)
    activities = serializers.SerializerMethodField()

    class Meta(LeadSerializer.Meta):
        fields = LeadSerializer.Meta.fields + [
            'address', 'website', 'expected_close_date',
            'call_logs', 'follow_ups', 'lead_notes',
            'tasks', 'lead_products', 'activities',
        ]

    def get_call_logs(self, obj):
        logs = obj.call_logs.select_related('agent').order_by('-call_date')[:20]
        return CallLogSerializer(logs, many=True).data

    def get_follow_ups(self, obj):
        fups = obj.follow_ups.order_by('is_completed', 'follow_up_date')
        return FollowUpSerializer(fups, many=True).data

    def get_activities(self, obj):
        acts = obj.activities.select_related('actor').order_by('-created_at')[:30]
        return LeadActivitySerializer(acts, many=True).data


# ─── Lead Update ─────────────────────────────────────────────────────────────

class LeadUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lead
        fields = [
            'status', 'notes', 'deal_value',
            'city', 'state', 'industry', 'designation',
            'expected_close_date',
        ]

    def validate_status(self, value):
        valid = [c[0] for c in Lead.STATUS_CHOICES]
        if value not in valid:
            raise serializers.ValidationError(f'Invalid status. Choose from: {valid}')
        return value


# ─── CallLog ──────────────────────────────────────────────────────────────────

class CallLogSerializer(serializers.ModelSerializer):
    agent = UserSerializer(read_only=True)
    lead = serializers.SerializerMethodField()
    lead_id = serializers.IntegerField(write_only=True, required=False)
    disposition_display = serializers.CharField(source='get_disposition_display', read_only=True)
    duration_display = serializers.SerializerMethodField()

    class Meta:
        model = CallLog
        fields = [
            'id', 'lead', 'lead_id', 'agent', 'call_date',
            'duration', 'duration_display', 'disposition', 'disposition_display',
            'remarks', 'recording', 'created_at'
        ]
        read_only_fields = ['created_at', 'agent']

    def get_lead(self, obj):
        return {'id': obj.lead.id, 'name': obj.lead.name, 'phone': obj.lead.phone}

    def get_duration_display(self, obj):
        if obj.duration:
            total = int(obj.duration.total_seconds())
            return f"{total // 60}:{total % 60:02d}"
        return None

    def create(self, validated_data):
        validated_data['agent'] = self.context['request'].user
        if 'lead_id' in validated_data:
            validated_data['lead_id'] = validated_data.pop('lead_id')
        return super().create(validated_data)


class CallLogCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CallLog
        fields = ['disposition', 'remarks', 'duration']

    def validate_disposition(self, value):
        valid = [c[0] for c in CallLog.DISPOSITION_CHOICES]
        if value not in valid:
            raise serializers.ValidationError(f'Invalid disposition. Choose from: {valid}')
        return value

    def create(self, validated_data):
        validated_data['agent'] = self.context['request'].user
        validated_data['lead'] = self.context['lead']
        return super().create(validated_data)


# ─── FollowUp ─────────────────────────────────────────────────────────────────

class FollowUpSerializer(serializers.ModelSerializer):
    agent = UserSerializer(read_only=True)
    lead = serializers.SerializerMethodField()
    lead_id = serializers.IntegerField(write_only=True, required=False)
    is_overdue = serializers.BooleanField(read_only=True)
    is_today = serializers.SerializerMethodField()
    formatted_datetime = serializers.SerializerMethodField()
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)

    class Meta:
        model = FollowUp
        fields = [
            'id', 'lead', 'lead_id', 'agent',
            'title', 'priority', 'priority_display',
            'follow_up_date', 'follow_up_time', 'remarks',
            'is_completed', 'created_at', 'completed_at',
            'is_overdue', 'is_today', 'formatted_datetime'
        ]
        read_only_fields = ['created_at', 'completed_at', 'agent']

    def get_lead(self, obj):
        return {'id': obj.lead.id, 'name': obj.lead.name, 'phone': obj.lead.phone, 'company': obj.lead.company}

    def get_is_today(self, obj):
        return obj.follow_up_date == timezone.now().date()

    def get_formatted_datetime(self, obj):
        return f"{obj.follow_up_date.strftime('%b %d, %Y')} at {obj.follow_up_time.strftime('%I:%M %p')}"

    def create(self, validated_data):
        validated_data['agent'] = self.context['request'].user
        return super().create(validated_data)


class FollowUpCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = FollowUp
        fields = ['title', 'priority', 'follow_up_date', 'follow_up_time', 'remarks']

    def validate_follow_up_date(self, value):
        if value < timezone.now().date():
            raise serializers.ValidationError('Follow-up date cannot be in the past.')
        return value

    def create(self, validated_data):
        validated_data['agent'] = self.context['request'].user
        validated_data['lead'] = self.context['lead']
        return super().create(validated_data)
