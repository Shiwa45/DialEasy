# api/views.py (Complete & Fixed)

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from rest_framework.pagination import PageNumberPagination
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Count, Q, Sum
from django.http import JsonResponse
from datetime import datetime, timedelta
import json

from leads.models import (
    Lead, CallLog, FollowUp,
    LeadNote, LeadTask, Product, LeadProduct, LeadActivity, AssignmentRule
)
from agents.models import AgentProfile, AgentTarget, DialerSession, CallActivityEvent
from .serializers import (
    LeadSerializer, CallLogSerializer, FollowUpSerializer,
    LeadUpdateSerializer, CallLogCreateSerializer, FollowUpCreateSerializer,
    LeadNoteSerializer, LeadNoteCreateSerializer,
    LeadTaskSerializer, ProductSerializer,
    LeadProductSerializer, LeadActivitySerializer,
    UserSerializer, LeadDetailSerializer
)

# Custom Pagination
class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = None


AUTODIAL_STARTED_DISPOSITION = 'autodial_started'


def _create_autodial_call_log(user, lead, call_date=None):
    """Create the single source-of-truth call row when autodial initiates."""
    return CallLog.objects.create(
        lead=lead,
        agent=user,
        call_date=call_date or timezone.now(),
        disposition=AUTODIAL_STARTED_DISPOSITION,
        remarks='Autodial initiated call',
    )


def _pending_autodial_call_log(user, lead):
    return (
        CallLog.objects
        .filter(
            lead=lead,
            agent=user,
            disposition=AUTODIAL_STARTED_DISPOSITION,
            call_date__date=timezone.now().date(),
        )
        .order_by('-call_date')
        .first()
    )


def _apply_call_disposition_workflow(lead, call_log, request_data):
    from leads.models import Disposition

    triggers_follow_up = False
    try:
        disp_config = Disposition.objects.get(value=call_log.disposition)
        triggers_follow_up = disp_config.triggers_follow_up
        if disp_config.updates_lead_status:
            lead.status = disp_config.updates_lead_status
            lead.save()
        elif request_data.get('lead_status') in dict(Lead.STATUS_CHOICES):
            lead.status = request_data['lead_status']
            lead.save()
    except Disposition.DoesNotExist:
        if request_data.get('lead_status') in dict(Lead.STATUS_CHOICES):
            lead.status = request_data['lead_status']
            lead.save()

    return triggers_follow_up

# ===============================
# AUTHENTICATION ENDPOINTS
# ===============================

@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    """
    Agent login endpoint for mobile app
    
    POST /api/auth/login/
    {
        "username": "agent1",
        "password": "password123"
    }
    """
    try:
        username = request.data.get('username')
        password = request.data.get('password')
        
        if not username or not password:
            return Response(
                {'error': 'Username and password are required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user = authenticate(username=username, password=password)
        
        if user and user.is_active and not user.is_staff:
            # Rotate the token on every login — this invalidates any existing session
            # on another device, enforcing single active session per agent.
            Token.objects.filter(user=user).delete()
            token = Token.objects.create(user=user)

            # Get or create agent profile
            agent_profile, profile_created = AgentProfile.objects.get_or_create(
                user=user,
                defaults={
                    'hire_date': timezone.now().date(),
                    'target_calls_per_day': 50,
                    'target_conversions_per_month': 10
                }
            )

            return Response({
                'token': token.key,
                'user': UserSerializer(user).data,
                'agent_profile': {
                    'department': agent_profile.department or '',
                    'target_calls_per_day': agent_profile.target_calls_per_day,
                    'target_conversions_per_month': agent_profile.target_conversions_per_month,
                    'dialer_last_lead_id': agent_profile.dialer_last_lead_id,
                },
                'message': 'Login successful'
            })
        else:
            return Response(
                {'error': 'Invalid credentials or account not authorized for mobile access'}, 
                status=status.HTTP_401_UNAUTHORIZED
            )
    except Exception as e:
        return Response(
            {'error': f'Login failed: {str(e)}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    """
    Agent logout endpoint
    
    POST /api/auth/logout/
    """
    try:
        # Delete the user's token
        Token.objects.filter(user=request.user).delete()
        return Response({'message': 'Logout successful'})
    except Exception as e:
        return Response({'message': 'Logout successful'})

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def profile_view(request):
    """
    Get current user profile
    
    GET /api/auth/profile/
    """
    try:
        agent_profile, created = AgentProfile.objects.get_or_create(
            user=request.user,
            defaults={
                'hire_date': timezone.now().date(),
                'target_calls_per_day': 50,
                'target_conversions_per_month': 10
            }
        )
        
        return Response({
            'user': UserSerializer(request.user).data,
            'agent_profile': {
                'department': agent_profile.department or '',
                'phone': agent_profile.phone or '',
                'hire_date': agent_profile.hire_date,
                'target_calls_per_day': agent_profile.target_calls_per_day,
                'target_conversions_per_month': agent_profile.target_conversions_per_month,
                'is_active': agent_profile.is_active,
            }
        })
    except Exception as e:
        return Response(
            {'error': f'Profile fetch failed: {str(e)}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

# ===============================
# LEAD MANAGEMENT VIEWSETS
# ===============================

class LeadViewSet(viewsets.ModelViewSet):
    """
    Lead management endpoints
    
    GET /api/leads/ - List leads
    GET /api/leads/{id}/ - Get lead details
    PATCH /api/leads/{id}/ - Update lead
    """
    serializer_class = LeadSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    queryset = Lead.objects.all()
    
    def get_queryset(self):
        try:
            # Agents can only see their assigned leads
            if self.request.user.is_staff:
                return Lead.objects.all().select_related('assigned_agent').prefetch_related('call_logs', 'follow_ups')
            return Lead.objects.filter(assigned_agent=self.request.user).select_related('assigned_agent').prefetch_related('call_logs', 'follow_ups')
        except Exception as e:
            return Lead.objects.none()
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return LeadDetailSerializer
        return LeadSerializer
    
    def list(self, request, *args, **kwargs):
        """
        List leads with filtering
        
        Query parameters:
        - status: Filter by lead status
        - search: Search in name, phone, company
        - ordering: Order by field (created_at, name, status)
        """
        try:
            queryset = self.get_queryset()
            
            # Apply filters
            status_filter = request.query_params.get('status')
            if status_filter:
                queryset = queryset.filter(status=status_filter)
            
            search = request.query_params.get('search')
            if search:
                queryset = queryset.filter(
                    Q(name__icontains=search) |
                    Q(phone__icontains=search) |
                    Q(company__icontains=search) |
                    Q(email__icontains=search)
                )
            
            # Apply ordering
            ordering = request.query_params.get('ordering', '-created_at')
            allowed_orderings = ['created_at', '-created_at', 'name', '-name', 'status', '-status', 'lead_score', '-lead_score']
            if ordering in allowed_orderings:
                queryset = queryset.order_by(ordering)
            else:
                queryset = queryset.order_by('-created_at')
            
            # Paginate
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            
            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data)
        except Exception as e:
            return Response(
                {'error': f'Failed to list leads: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['patch'])
    def update_status(self, request, pk=None):
        """
        Update lead status
        
        PATCH /api/leads/{id}/update_status/
        {
            "status": "contacted",
            "notes": "Customer showed interest"
        }
        """
        try:
            lead = self.get_object()
            serializer = LeadUpdateSerializer(lead, data=request.data, partial=True)
            
            if serializer.is_valid():
                serializer.save()
                return Response(LeadDetailSerializer(lead).data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {'error': f'Failed to update lead: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def my_leads(self, request):
        """
        Get current agent's leads with priority sorting
        
        GET /api/leads/my_leads/
        """
        try:
            if request.user.is_staff:
                return Response({'error': 'This endpoint is for agents only'}, status=status.HTTP_403_FORBIDDEN)
            
            # Get leads with priority: new -> callback -> contacted -> interested
            leads = Lead.objects.filter(assigned_agent=request.user)

            status_filter = request.query_params.get('status')
            if status_filter:
                leads = leads.filter(status=status_filter)

            leads = leads.order_by('status', 'created_at')
            
            page = self.paginate_queryset(leads)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            
            serializer = self.get_serializer(leads, many=True)
            return Response(serializer.data)
        except Exception as e:
            return Response(
                {'error': f'Failed to get leads: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class CallLogViewSet(viewsets.ModelViewSet):
    """
    Call log management
    
    GET /api/call-logs/ - List call logs
    POST /api/call-logs/ - Create call log
    """
    serializer_class = CallLogSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    queryset = CallLog.objects.all()
    
    def get_queryset(self):
        try:
            # Agents can only see their own call logs
            if self.request.user.is_staff:
                return CallLog.objects.all().select_related('lead', 'agent').order_by('-call_date')
            return CallLog.objects.filter(agent=self.request.user).select_related('lead', 'agent').order_by('-call_date')
        except Exception as e:
            return CallLog.objects.none()
    
    def perform_create(self, serializer):
        serializer.save(agent=self.request.user)

class FollowUpViewSet(viewsets.ModelViewSet):
    """
    Follow-up management
    
    GET /api/follow-ups/ - List follow-ups
    POST /api/follow-ups/ - Create follow-up
    PATCH /api/follow-ups/{id}/ - Update follow-up
    """
    serializer_class = FollowUpSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    queryset = FollowUp.objects.all()
    
    def get_queryset(self):
        try:
            # Agents can only see their own follow-ups
            queryset = FollowUp.objects.filter(agent=self.request.user).select_related('lead', 'agent').order_by('follow_up_date', 'follow_up_time')
            
            # Filter by completion status
            completed = self.request.query_params.get('completed')
            if completed == 'true':
                queryset = queryset.filter(is_completed=True)
            elif completed == 'false':
                queryset = queryset.filter(is_completed=False)
            
            # Filter by date
            date_filter = self.request.query_params.get('date')
            if date_filter:
                try:
                    filter_date = datetime.strptime(date_filter, '%Y-%m-%d').date()
                    queryset = queryset.filter(follow_up_date=filter_date)
                except ValueError:
                    pass
            
            return queryset
        except Exception as e:
            return FollowUp.objects.none()
    
    def perform_create(self, serializer):
        serializer.save(agent=self.request.user)
    
    @action(detail=True, methods=['post'])
    def mark_completed(self, request, pk=None):
        """
        Mark follow-up as completed
        
        POST /api/follow-ups/{id}/mark_completed/
        """
        try:
            follow_up = self.get_object()
            follow_up.is_completed = True
            follow_up.completed_at = timezone.now()
            follow_up.save()
            
            return Response(FollowUpSerializer(follow_up).data)
        except Exception as e:
            return Response(
                {'error': f'Failed to complete follow-up: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def today(self, request):
        """
        Get today's follow-ups
        
        GET /api/follow-ups/today/
        """
        try:
            today = timezone.now().date()
            follow_ups = self.get_queryset().filter(
                follow_up_date=today,
                is_completed=False
            )
            
            serializer = self.get_serializer(follow_ups, many=True)
            return Response(serializer.data)
        except Exception as e:
            return Response(
                {'error': f'Failed to get today\'s follow-ups: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def overdue(self, request):
        """
        Get overdue follow-ups
        
        GET /api/follow-ups/overdue/
        """
        try:
            today = timezone.now().date()
            follow_ups = self.get_queryset().filter(
                follow_up_date__lt=today,
                is_completed=False
            )
            
            serializer = self.get_serializer(follow_ups, many=True)
            return Response(serializer.data)
        except Exception as e:
            return Response(
                {'error': f'Failed to get overdue follow-ups: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

# ===============================
# AGENT SPECIFIC ENDPOINTS
# ===============================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def agent_dashboard(request):
    """
    Get agent dashboard data
    
    GET /api/agent/dashboard/
    """
    try:
        if request.user.is_staff:
            return Response({'error': 'This endpoint is for agents only'}, status=status.HTTP_403_FORBIDDEN)
        
        user = request.user
        today = timezone.now().date()
        
        # Basic stats
        total_leads = Lead.objects.filter(assigned_agent=user).count()
        new_leads = Lead.objects.filter(assigned_agent=user, status='new').count()
        contacted_leads = Lead.objects.filter(assigned_agent=user, status='contacted').count()
        converted_leads = Lead.objects.filter(assigned_agent=user, status='converted').count()
        
        # Today's activity
        today_calls = CallLog.objects.filter(agent=user, call_date__date=today).count()
        today_follow_ups = FollowUp.objects.filter(
            agent=user,
            follow_up_date=today,
            is_completed=False
        ).count()
        
        # This week's activity
        week_start = today - timedelta(days=today.weekday())
        week_calls = CallLog.objects.filter(
            agent=user,
            call_date__date__range=[week_start, today]
        ).count()
        
        # Conversion rate
        conversion_rate = round(converted_leads / total_leads * 100, 2) if total_leads > 0 else 0
        
        # Recent activity
        recent_calls = CallLog.objects.filter(agent=user).select_related('lead').order_by('-call_date')[:5]
        upcoming_follow_ups = FollowUp.objects.filter(
            agent=user,
            is_completed=False,
            follow_up_date__gte=today
        ).select_related('lead').order_by('follow_up_date', 'follow_up_time')[:5]
        
        # Lead status breakdown
        status_counts = {
            key: 0
            for key, _label in Lead.STATUS_CHOICES
        }
        status_counts.update({
            row['status']: row['count']
            for row in Lead.objects.filter(assigned_agent=user).values('status').annotate(count=Count('id'))
        })
        lead_statuses = [
            {'status': key, 'label': label, 'count': status_counts.get(key, 0)}
            for key, label in Lead.STATUS_CHOICES
        ]
        
        # Monthly targets
        current_month = today.replace(day=1)
        try:
            current_target = AgentTarget.objects.get(agent=user, month=current_month)
            month_calls = CallLog.objects.filter(
                agent=user,
                call_date__date__range=[current_month, today]
            ).count()
            month_conversions = Lead.objects.filter(
                assigned_agent=user,
                status='converted',
                updated_at__date__range=[current_month, today]
            ).count()
            
            target_data = {
                'target_calls': current_target.target_calls,
                'actual_calls': month_calls,
                'target_conversions': current_target.target_conversions,
                'actual_conversions': month_conversions,
                'calls_percentage': round(month_calls / current_target.target_calls * 100, 1) if current_target.target_calls > 0 else 0,
                'conversions_percentage': round(month_conversions / current_target.target_conversions * 100, 1) if current_target.target_conversions > 0 else 0
            }
        except AgentTarget.DoesNotExist:
            target_data = None
        
        return Response({
            'summary': {
                'total_leads': total_leads,
                'new_leads': new_leads,
                'interested_leads': status_counts.get('interested', 0),
                'contacted_leads': contacted_leads,
                'converted_leads': converted_leads,
                'conversion_rate': conversion_rate,
                'total_calls': CallLog.objects.filter(agent=user).count(),
                'today_calls': today_calls,
                'today_follow_ups': today_follow_ups,
                'week_calls': week_calls,
            },
            'lead_statuses': lead_statuses,
            'status_counts': status_counts,
            'recent_calls': CallLogSerializer(recent_calls, many=True).data,
            'upcoming_follow_ups': FollowUpSerializer(upcoming_follow_ups, many=True).data,
            'monthly_targets': target_data,
        })
    except Exception as e:
        return Response(
            {'error': f'Dashboard fetch failed: {str(e)}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def agent_stats(request):
    """
    Get detailed agent statistics
    
    GET /api/agent/stats/
    """
    try:
        if request.user.is_staff:
            return Response({'error': 'This endpoint is for agents only'}, status=status.HTTP_403_FORBIDDEN)
        
        user = request.user
        today = timezone.now().date()
        
        # Get date range
        days = int(request.query_params.get('days', 30))
        start_date = today - timedelta(days=days)
        
        # Performance data
        calls_in_period = CallLog.objects.filter(
            agent=user,
            call_date__date__range=[start_date, today]
        )
        
        leads_in_period = Lead.objects.filter(
            assigned_agent=user,
            created_at__date__range=[start_date, today]
        )
        
        # Daily performance
        daily_performance = []
        current_date = start_date
        while current_date <= today:
            daily_calls = calls_in_period.filter(call_date__date=current_date).count()
            daily_conversions = Lead.objects.filter(
                assigned_agent=user,
                status='converted',
                updated_at__date=current_date
            ).count()
            
            daily_performance.append({
                'date': current_date.isoformat(),
                'calls': daily_calls,
                'conversions': daily_conversions
            })
            
            current_date += timedelta(days=1)
        
        # Disposition breakdown
        disposition_breakdown = calls_in_period.values('disposition').annotate(
            count=Count('id')
        ).order_by('-count')
        
        return Response({
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': today.isoformat(),
                'days': days
            },
            'summary': {
                'total_calls': calls_in_period.count(),
                'lifetime_total_calls': CallLog.objects.filter(agent=user).count(),
                'total_leads': leads_in_period.count(),
                'total_conversions': leads_in_period.filter(status='converted').count(),
                'avg_calls_per_day': round(calls_in_period.count() / days, 2) if days > 0 else 0,
            },
            'daily_performance': daily_performance,
            'disposition_breakdown': list(disposition_breakdown),
        })
    except Exception as e:
        return Response(
            {'error': f'Stats fetch failed: {str(e)}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

# ===============================
# LEAD ACTION ENDPOINTS
# ===============================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_call_log(request, lead_id):
    """
    Create a call log for a specific lead
    
    POST /api/leads/{lead_id}/call/
    {
        "disposition": "interested",
        "remarks": "Customer wants more information",
        "duration": 300,
        "lead_status": "contacted"
    }
    """
    try:
        lead = get_object_or_404(Lead, id=lead_id, assigned_agent=request.user)
        
        serializer = CallLogCreateSerializer(
            data=request.data,
            context={'request': request, 'lead': lead}
        )
        
        if serializer.is_valid():
            pending_call = None
            call_log_id = request.data.get('call_log_id')
            if call_log_id:
                pending_call = CallLog.objects.filter(
                    id=call_log_id,
                    lead=lead,
                    agent=request.user,
                ).first()
            if pending_call is None:
                pending_call = _pending_autodial_call_log(request.user, lead)

            if pending_call and pending_call.disposition == AUTODIAL_STARTED_DISPOSITION:
                call_log = pending_call
                call_log.disposition = serializer.validated_data['disposition']
                call_log.remarks = serializer.validated_data.get('remarks', '')
                duration = serializer.validated_data.get('duration')
                if duration is not None:
                    call_log.duration = duration
                call_log.save(update_fields=['disposition', 'remarks', 'duration'])
                LeadActivity.objects.create(
                    lead=lead,
                    actor=request.user,
                    activity_type='call_logged',
                    description=f'Call updated: {call_log.get_disposition_display()}. Duration: {call_log.duration or "unknown"}',
                    metadata={'call_log_id': call_log.pk, 'disposition': call_log.disposition},
                )
            else:
                call_log = serializer.save()

            triggers_follow_up = _apply_call_disposition_workflow(lead, call_log, request.data)
            response_data = CallLogSerializer(call_log).data
            response_data['triggers_follow_up'] = triggers_follow_up
            return Response(response_data, status=status.HTTP_201_CREATED)

            call_log = serializer.save()

            # Apply disposition workflow rules
            from leads.models import Disposition
            triggers_follow_up = False
            try:
                disp_config = Disposition.objects.get(value=call_log.disposition)
                triggers_follow_up = disp_config.triggers_follow_up
                # Auto-update lead status from disposition config (takes priority)
                if disp_config.updates_lead_status:
                    lead.status = disp_config.updates_lead_status
                    lead.save()
                elif request.data.get('lead_status') in dict(Lead.STATUS_CHOICES):
                    lead.status = request.data['lead_status']
                    lead.save()
            except Disposition.DoesNotExist:
                # Disposition not in DB yet — fall back to manual status update
                if request.data.get('lead_status') in dict(Lead.STATUS_CHOICES):
                    lead.status = request.data['lead_status']
                    lead.save()

            response_data = CallLogSerializer(call_log).data
            response_data['triggers_follow_up'] = triggers_follow_up
            return Response(response_data, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response(
            {'error': f'Failed to create call log: {str(e)}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_follow_up(request, lead_id):
    """
    Create a follow-up for a specific lead
    
    POST /api/leads/{lead_id}/follow-up/
    {
        "follow_up_date": "2024-01-15",
        "follow_up_time": "14:30",
        "remarks": "Call back to discuss pricing"
    }
    """
    try:
        lead = get_object_or_404(Lead, id=lead_id, assigned_agent=request.user)
        
        serializer = FollowUpCreateSerializer(
            data=request.data,
            context={'request': request, 'lead': lead}
        )
        
        if serializer.is_valid():
            follow_up = serializer.save()
            
            # Update lead status to callback if not already set
            if lead.status == 'new':
                lead.status = 'callback'
                lead.save()
            
            return Response(FollowUpSerializer(follow_up).data, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response(
            {'error': f'Failed to create follow-up: {str(e)}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def complete_follow_up(request, follow_up_id):
    """
    Mark a follow-up as completed
    
    POST /api/follow-ups/{follow_up_id}/complete/
    {
        "completion_notes": "Follow-up completed successfully"
    }
    """
    try:
        follow_up = get_object_or_404(
            FollowUp, 
            id=follow_up_id, 
            agent=request.user,
            is_completed=False
        )
        
        follow_up.is_completed = True
        follow_up.completed_at = timezone.now()
        
        # Add completion notes if provided
        completion_notes = request.data.get('completion_notes')
        if completion_notes:
            follow_up.remarks = f"{follow_up.remarks}\n[Completed: {completion_notes}]"
        
        follow_up.save()
        
        return Response(FollowUpSerializer(follow_up).data)
    except Exception as e:
        return Response(
            {'error': f'Failed to complete follow-up: {str(e)}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

# ===============================
# UTILITY ENDPOINTS
# ===============================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def lead_status_choices(request):
    """
    Get available lead status choices
    
    GET /api/utils/lead-status-choices/
    """
    return Response({
        'choices': [{'value': choice[0], 'label': choice[1]} for choice in Lead.STATUS_CHOICES]
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def call_disposition_choices(request):
    """
    GET /api/utils/call-disposition-choices/
    Returns active dispositions from the DB (managed by super admin).
    """
    from leads.models import Disposition
    dispositions = Disposition.objects.filter(is_active=True).order_by('sort_order', 'label')
    return Response({
        'choices': [
            {
                'value': d.value,
                'label': d.label,
                'color': d.color,
                'triggers_follow_up': d.triggers_follow_up,
                'updates_lead_status': d.updates_lead_status or None,
            }
            for d in dispositions
        ]
    })

# ===============================
# SEARCH AND FILTERS
# ===============================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def search_leads(request):
    """
    Advanced lead search
    
    GET /api/search/leads/?q=john&status=new&source=website
    """
    try:
        query = request.query_params.get('q', '')
        status_filter = request.query_params.get('status')
        source_filter = request.query_params.get('source')
        
        # Base queryset
        if request.user.is_staff:
            leads = Lead.objects.all()
        else:
            leads = Lead.objects.filter(assigned_agent=request.user)
        
        # Apply search
        if query:
            leads = leads.filter(
                Q(name__icontains=query) |
                Q(phone__icontains=query) |
                Q(email__icontains=query) |
                Q(company__icontains=query)
            )
        
        # Apply filters
        if status_filter:
            leads = leads.filter(status=status_filter)
        
        if source_filter:
            leads = leads.filter(source__icontains=source_filter)
        
        # Order by relevance and date
        leads = leads.select_related('assigned_agent').order_by('-created_at')
        
        # Pagination
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(leads, request)
        
        if page is not None:
            serializer = LeadSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)
        
        serializer = LeadSerializer(leads, many=True)
        return Response(serializer.data)
    except Exception as e:
        return Response(
            {'error': f'Search failed: {str(e)}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

# ===============================
# BULK OPERATIONS
# ===============================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def bulk_update_leads(request):
    """
    Bulk update multiple leads
    
    POST /api/leads/bulk-update/
    {
        "lead_ids": [1, 2, 3],
        "updates": {
            "status": "contacted"
        }
    }
    """
    try:
        if request.user.is_staff:
            return Response({'error': 'This endpoint is for agents only'}, status=status.HTTP_403_FORBIDDEN)
        
        lead_ids = request.data.get('lead_ids', [])
        updates = request.data.get('updates', {})
        
        if not lead_ids or not updates:
            return Response(
                {'error': 'lead_ids and updates are required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate that agent owns these leads
        leads = Lead.objects.filter(
            id__in=lead_ids,
            assigned_agent=request.user
        )
        
        if leads.count() != len(lead_ids):
            return Response(
                {'error': 'Some leads not found or not assigned to you'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate updates
        allowed_fields = ['status', 'notes']
        valid_updates = {k: v for k, v in updates.items() if k in allowed_fields}
        
        if not valid_updates:
            return Response(
                {'error': 'No valid update fields provided'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Perform bulk update
        updated_count = leads.update(**valid_updates)
        
        return Response({
            'message': f'Successfully updated {updated_count} leads',
            'updated_count': updated_count
        })
    except Exception as e:
        return Response(
            {'error': f'Bulk update failed: {str(e)}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

# ===============================
# OFFLINE SYNC ENDPOINTS
# ===============================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def sync_offline_data(request):
    """
    Sync offline data to server
    
    POST /api/sync/upload/
    {
        "call_logs": [...],
        "follow_ups": [...],
        "lead_updates": [...]
    }
    """
    try:
        if request.user.is_staff:
            return Response({'error': 'This endpoint is for agents only'}, status=status.HTTP_403_FORBIDDEN)
        
        call_logs_data = request.data.get('call_logs', [])
        follow_ups_data = request.data.get('follow_ups', [])
        lead_updates_data = request.data.get('lead_updates', [])
        
        results = {
            'call_logs': {'success': 0, 'failed': 0, 'errors': []},
            'follow_ups': {'success': 0, 'failed': 0, 'errors': []},
            'lead_updates': {'success': 0, 'failed': 0, 'errors': []}
        }
        
        # Process call logs
        for call_data in call_logs_data:
            try:
                lead = Lead.objects.get(id=call_data['lead_id'], assigned_agent=request.user)
                CallLog.objects.create(
                    lead=lead,
                    agent=request.user,
                    call_date=call_data.get('call_date', timezone.now()),
                    disposition=call_data['disposition'],
                    remarks=call_data.get('remarks', ''),
                    duration=call_data.get('duration')
                )
                results['call_logs']['success'] += 1
            except Exception as e:
                results['call_logs']['failed'] += 1
                results['call_logs']['errors'].append(str(e))
        
        # Process follow-ups
        for followup_data in follow_ups_data:
            try:
                lead = Lead.objects.get(id=followup_data['lead_id'], assigned_agent=request.user)
                FollowUp.objects.create(
                    lead=lead,
                    agent=request.user,
                    follow_up_date=followup_data['follow_up_date'],
                    follow_up_time=followup_data['follow_up_time'],
                    remarks=followup_data.get('remarks', '')
                )
                results['follow_ups']['success'] += 1
            except Exception as e:
                results['follow_ups']['failed'] += 1
                results['follow_ups']['errors'].append(str(e))
        
        # Process lead updates
        for update_data in lead_updates_data:
            try:
                lead = Lead.objects.get(id=update_data['lead_id'], assigned_agent=request.user)
                if 'status' in update_data:
                    lead.status = update_data['status']
                if 'notes' in update_data:
                    lead.notes = update_data['notes']
                lead.save()
                results['lead_updates']['success'] += 1
            except Exception as e:
                results['lead_updates']['failed'] += 1
                results['lead_updates']['errors'].append(str(e))
        
        return Response(results)
    except Exception as e:
        return Response(
            {'error': f'Sync upload failed: {str(e)}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def sync_download_data(request):
    """
    Download updated data for offline sync
    
    GET /api/sync/download/?since=2024-01-01T00:00:00Z
    """
    try:
        if request.user.is_staff:
            return Response({'error': 'This endpoint is for agents only'}, status=status.HTTP_403_FORBIDDEN)
        
        since_param = request.query_params.get('since')
        if since_param:
            try:
                since_date = datetime.fromisoformat(since_param.replace('Z', '+00:00'))
            except ValueError:
                since_date = timezone.now() - timedelta(days=7)
        else:
            since_date = timezone.now() - timedelta(days=7)
        
        leads = Lead.objects.filter(assigned_agent=request.user, updated_at__gte=since_date)
        call_logs = CallLog.objects.filter(agent=request.user, created_at__gte=since_date)
        follow_ups = FollowUp.objects.filter(agent=request.user, created_at__gte=since_date)
        
        return Response({
            'leads': LeadSerializer(leads, many=True).data,
            'call_logs': CallLogSerializer(call_logs, many=True).data,
            'follow_ups': FollowUpSerializer(follow_ups, many=True).data,
            'timestamp': timezone.now().isoformat()
        })
    except Exception as e:
        return Response(
            {'error': f'Sync download failed: {str(e)}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_call_recording(request, lead_id):
    """
    POST /api/leads/{lead_id}/recording/
    Uploads a call recording to Cloudinary and stores the secure URL.
    Falls back to local storage if Cloudinary is not configured.
    """
    try:
        lead = get_object_or_404(Lead, id=lead_id, assigned_agent=request.user)
        recording_file = request.FILES.get('recording')

        if not recording_file:
            return Response({'error': 'No file uploaded'}, status=status.HTTP_400_BAD_REQUEST)

        call_log = CallLog.objects.filter(lead=lead, agent=request.user).first()
        if not call_log:
            return Response({'error': 'No call log found for this lead'}, status=status.HTTP_404_NOT_FOUND)

        call_log.recording_size = recording_file.size

        # Try Cloudinary upload; fall back to local storage if not configured
        from django.conf import settings as dj_settings
        import cloudinary.uploader
        cloud_name = getattr(dj_settings, 'CLOUDINARY_STORAGE', {}).get('CLOUD_NAME') or \
                     (cloudinary.config().cloud_name if cloudinary.config().cloud_name else None)
        # Determine if cloudinary is configured
        import cloudinary as _cloudinary
        _cfg = _cloudinary.config()
        if _cfg.cloud_name and _cfg.api_key and _cfg.api_secret:
            tenant_slug = getattr(request, 'tenant', None)
            tenant_slug = tenant_slug.schema_name if tenant_slug else 'default'
            folder = f'dialeasy/{tenant_slug}/recordings'
            result = cloudinary.uploader.upload(
                recording_file,
                resource_type='video',   # Cloudinary uses 'video' for audio files
                folder=folder,
                public_id=f'calllog_{call_log.pk}',
                overwrite=True,
                format='mp3',
            )
            call_log.recording_url = result['secure_url']
        else:
            # No Cloudinary configured — save locally
            call_log.recording = recording_file

        call_log.save()

        # Trigger AI transcription if tenant has the feature
        try:
            from ai.transcription_service import process_call_recording
            from tenants.feature_gates import tenant_has_feature
            if tenant_has_feature(request, 'ai_transcription'):
                process_call_recording(call_log.id)
        except Exception:
            pass

        url = call_log.recording_url or (call_log.recording.url if call_log.recording else None)
        return Response({'message': 'Recording uploaded successfully', 'url': url})
    except Exception as e:
        return Response({'error': f'Upload failed: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_call_recording_by_log(request, call_log_id):
    """
    POST /api/call-logs/{call_log_id}/upload-recording/
    Mobile app calls this with the call_log_id returned from createCallLog.
    Uploads recording to Cloudinary; falls back to local storage.
    """
    try:
        call_log = get_object_or_404(CallLog, pk=call_log_id, agent=request.user)
        recording_file = request.FILES.get('recording')
        if not recording_file:
            return Response({'error': 'No file uploaded'}, status=status.HTTP_400_BAD_REQUEST)

        call_log.recording_size = recording_file.size

        import cloudinary as _cloudinary
        import cloudinary.uploader
        _cfg = _cloudinary.config()
        if _cfg.cloud_name and _cfg.api_key and _cfg.api_secret:
            tenant_slug = getattr(request, 'tenant', None)
            tenant_slug = tenant_slug.schema_name if tenant_slug else 'default'
            result = cloudinary.uploader.upload(
                recording_file,
                resource_type='video',
                folder=f'dialeasy/{tenant_slug}/recordings',
                public_id=f'calllog_{call_log.pk}',
                overwrite=True,
                format='mp3',
            )
            call_log.recording_url = result['secure_url']
        else:
            call_log.recording = recording_file

        call_log.save()

        try:
            from ai.transcription_service import process_call_recording
            from tenants.feature_gates import tenant_has_feature
            if tenant_has_feature(request, 'ai_transcription'):
                process_call_recording(call_log.id)
        except Exception:
            pass

        url = call_log.recording_url or (call_log.recording.url if call_log.recording else None)
        return Response({'message': 'Recording uploaded successfully', 'url': url})
    except Exception as e:
        return Response({'error': f'Upload failed: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def enhanced_agent_dashboard(request):
    """
    Phase 1: Enhanced dashboard with more insights
    """
    try:
        user = request.user
        today = timezone.now().date()
        
        # Lead priority stats
        hot_leads = Lead.objects.filter(assigned_agent=user, lead_score__gte=75).count()
        warm_leads = Lead.objects.filter(assigned_agent=user, lead_score__range=(40, 74)).count()
        
        # Task stats
        pending_tasks = LeadTask.objects.filter(assigned_to=user, status__in=['pending', 'in_progress']).count()
        overdue_tasks = LeadTask.objects.filter(assigned_to=user, status__in=['pending', 'in_progress'], due_date__lt=timezone.now()).count()
        
        # Revenue stats
        total_pipeline_value = Lead.objects.filter(assigned_agent=user).aggregate(total=Sum('deal_value'))['total'] or 0
        
        return Response({
            'priority_leads': {'hot': hot_leads, 'warm': warm_leads},
            'tasks': {'pending': pending_tasks, 'overdue': overdue_tasks},
            'revenue': {'pipeline_value': total_pipeline_value},
        })
    except Exception as e:
        return Response({'error': str(e)}, status=500)


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 1: LEAD NOTES
# ═══════════════════════════════════════════════════════════════════════════════

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def lead_notes(request, lead_id):
    """
    GET  /api/leads/{id}/notes/  — list all notes for a lead
    POST /api/leads/{id}/notes/  — add a new note
    """
    try:
        if request.user.is_staff:
            lead = get_object_or_404(Lead, id=lead_id)
        else:
            lead = get_object_or_404(Lead, id=lead_id, assigned_agent=request.user)

        if request.method == 'GET':
            notes = lead.lead_notes.select_related('author').all()
            return Response(LeadNoteSerializer(notes, many=True).data)

        serializer = LeadNoteCreateSerializer(
            data=request.data,
            context={'request': request, 'lead': lead}
        )
        if serializer.is_valid():
            note = serializer.save()
            return Response(LeadNoteSerializer(note).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def lead_note_detail(request, lead_id, note_id):
    """
    GET    /api/leads/{id}/notes/{note_id}/  — get single note
    PATCH  /api/leads/{id}/notes/{note_id}/  — edit note
    DELETE /api/leads/{id}/notes/{note_id}/  — delete note
    """
    try:
        note = get_object_or_404(LeadNote, id=note_id, lead_id=lead_id)

        if request.method == 'GET':
            return Response(LeadNoteSerializer(note).data)

        if request.method == 'PATCH':
            serializer = LeadNoteSerializer(note, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                # Log edit activity
                LeadActivity.objects.create(
                    lead=note.lead, actor=request.user,
                    activity_type='note_edited',
                    description=f'Note edited: {note.content[:60]}...' if len(note.content) > 60 else f'Note edited: {note.content}',
                )
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        if request.method == 'DELETE':
            note.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 1: LEAD TASKS
# ═══════════════════════════════════════════════════════════════════════════════

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def lead_tasks(request, lead_id):
    """
    GET  /api/leads/{id}/tasks/  — list tasks for this lead
    POST /api/leads/{id}/tasks/  — create new task
    """
    try:
        if request.user.is_staff:
            lead = get_object_or_404(Lead, id=lead_id)
        else:
            lead = get_object_or_404(Lead, id=lead_id, assigned_agent=request.user)

        if request.method == 'GET':
            tasks = lead.tasks.select_related('assigned_to', 'created_by').all()
            return Response(LeadTaskSerializer(tasks, many=True).data)

        data = request.data.copy()
        data['lead'] = lead_id
        serializer = LeadTaskSerializer(data=data, context={'request': request})
        if serializer.is_valid():
            task = serializer.save(lead=lead, created_by=request.user)
            return Response(LeadTaskSerializer(task).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def complete_task(request, task_id):
    """
    POST /api/tasks/{id}/complete/
    Mark a task as done.
    """
    try:
        task = get_object_or_404(LeadTask, id=task_id)
        task.status = 'done'
        task.completed_at = timezone.now()
        task.save()
        return Response(LeadTaskSerializer(task).data)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class LeadTaskViewSet(viewsets.ModelViewSet):
    """
    ViewSet for global task management (all tasks assigned to current agent).
    GET /api/tasks/          — all my tasks
    GET /api/tasks/my/       — tasks assigned to me
    GET /api/tasks/overdue/  — overdue tasks
    """
    serializer_class = LeadTaskSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return LeadTask.objects.all().select_related('lead', 'assigned_to', 'created_by')
        return LeadTask.objects.filter(
            Q(assigned_to=user) | Q(created_by=user)
        ).select_related('lead', 'assigned_to', 'created_by')

    @action(detail=False, methods=['get'])
    def my(self, request):
        tasks = self.get_queryset().filter(
            assigned_to=request.user,
            status__in=['pending', 'in_progress']
        ).order_by('due_date')
        return Response(self.get_serializer(tasks, many=True).data)

    @action(detail=False, methods=['get'])
    def overdue(self, request):
        tasks = self.get_queryset().filter(
            status__in=['pending', 'in_progress'],
            due_date__lt=timezone.now()
        )
        return Response(self.get_serializer(tasks, many=True).data)


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 1: PRODUCTS
# ═══════════════════════════════════════════════════════════════════════════════

class ProductViewSet(viewsets.ModelViewSet):
    """
    GET /api/products/ — list all active products (for dropdown in Flutter)
    """
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Product.objects.filter(is_active=True).order_by('name')


@api_view(['GET', 'POST', 'DELETE'])
@permission_classes([IsAuthenticated])
def lead_products_view(request, lead_id):
    """
    GET    /api/leads/{id}/products/         — list products linked to lead
    POST   /api/leads/{id}/products/         — link a product to lead
    DELETE /api/leads/{id}/products/?product_id=X — remove product from lead
    """
    try:
        lead = get_object_or_404(Lead, id=lead_id)

        if request.method == 'GET':
            lps = lead.lead_products.select_related('product', 'added_by').all()
            return Response(LeadProductSerializer(lps, many=True).data)

        if request.method == 'POST':
            data = request.data.copy()
            data['lead'] = lead_id
            serializer = LeadProductSerializer(data=data, context={'request': request})
            if serializer.is_valid():
                lp = serializer.save(lead=lead, added_by=request.user)
                LeadActivity.objects.create(
                    lead=lead, actor=request.user,
                    activity_type='product_added',
                    description=f'Product added: {lp.product.name} × {lp.quantity}',
                )
                return Response(LeadProductSerializer(lp).data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        if request.method == 'DELETE':
            product_id = request.query_params.get('product_id')
            lp = get_object_or_404(LeadProduct, lead=lead, product_id=product_id)
            product_name = lp.product.name
            lp.delete()
            LeadActivity.objects.create(
                lead=lead, actor=request.user,
                activity_type='product_removed',
                description=f'Product removed: {product_name}',
            )
            return Response(status=status.HTTP_204_NO_CONTENT)

    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 1: LEAD ACTIVITY
# ═══════════════════════════════════════════════════════════════════════════════

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def lead_activity(request, lead_id):
    """
    GET /api/leads/{id}/activity/  — paginated activity timeline for a lead

    Query params:
      ?limit=30    (default 30)
      ?offset=0
    """
    try:
        lead = get_object_or_404(Lead, id=lead_id)
        limit = int(request.query_params.get('limit', 30))
        offset = int(request.query_params.get('offset', 0))

        activities = lead.activities.select_related('actor').order_by('-created_at')[offset:offset + limit]
        total = lead.activities.count()

        return Response({
            'count': total,
            'results': LeadActivitySerializer(activities, many=True).data,
        })
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 1: LEAD SCORE
# ═══════════════════════════════════════════════════════════════════════════════

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def recalculate_lead_score(request, lead_id):
    """
    POST /api/leads/{id}/score/  — force recalculate score for a lead.
    Returns updated lead score.
    """
    try:
        lead = get_object_or_404(Lead, id=lead_id)
        new_score = lead.recalculate_score()
        return Response({'lead_id': lead.id, 'lead_score': new_score, 'score_label': lead.score_label})
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 1: BULK ASSIGN (API version)
# ═══════════════════════════════════════════════════════════════════════════════

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def bulk_assign_leads_api(request):
    """
    POST /api/leads/bulk-assign/
    Body: { "lead_ids": [1,2,3], "agent_id": 5 }
    Body: { "lead_ids": [1,2,3], "auto": true }  ← uses active AssignmentRule
    """
    try:
        if not request.user.is_staff:
            return Response({'error': 'Only admins can bulk-assign leads.'}, status=status.HTTP_403_FORBIDDEN)

        lead_ids = request.data.get('lead_ids', [])
        if not lead_ids:
            return Response({'error': 'lead_ids required.'}, status=status.HTTP_400_BAD_REQUEST)

        leads = Lead.objects.filter(id__in=lead_ids)

        # Auto-assign via rule — only assign leads that have no agent yet
        if request.data.get('auto'):
            rule = AssignmentRule.objects.filter(is_active=True).first()
            if not rule:
                return Response({'error': 'No active assignment rule found.'}, status=400)
            unassigned = leads.filter(assigned_agent__isnull=True)
            assigned = 0
            skipped = leads.count() - unassigned.count()
            for lead in unassigned:
                agent = rule.get_next_agent(lead_source=lead.source)
                if agent:
                    lead.assigned_agent = agent
                    lead.save(update_fields=['assigned_agent'])
                    assigned += 1
            return Response({'assigned': assigned, 'skipped_already_assigned': skipped, 'total': len(lead_ids)})

        # Manual assign to specific agent
        agent_id = request.data.get('agent_id')
        if not agent_id:
            return Response({'error': 'agent_id or auto=true required.'}, status=400)

        agent = get_object_or_404(
            User,
            pk=agent_id,
            is_active=True,
            pk__in=AgentProfile.objects.values_list('user_id', flat=True),
        )
        count = leads.update(assigned_agent=agent)
        return Response({'assigned': count, 'agent': agent.get_full_name() or agent.username})

    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 1: ENHANCED app_config (adds score + deal fields info)
# ═══════════════════════════════════════════════════════════════════════════════

def _get_dispositions_for_config():
    """Return disposition list from DB for app_config and call-disposition-choices."""
    from leads.models import Disposition
    dispositions = Disposition.objects.filter(is_active=True).order_by('sort_order', 'label')
    return [
        {
            'value': d.value,
            'label': d.label,
            'color': d.color,
            'triggers_follow_up': d.triggers_follow_up,
            'updates_lead_status': d.updates_lead_status or None,
        }
        for d in dispositions
    ]


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def app_config(request):
    """
    GET /api/utils/app-config/
    Returns all config needed for the Flutter app on startup.
    Phase 1: adds products list, task priorities, score thresholds.
    """
    from agents.models import AgentProfile

    try:
        agent_profile, _ = AgentProfile.objects.get_or_create(
            user=request.user,
            defaults={'hire_date': timezone.now().date()}
        )

        products = ProductSerializer(Product.objects.filter(is_active=True), many=True).data

        return Response({
            'lead_statuses': [{'value': k, 'label': v} for k, v in Lead.STATUS_CHOICES],
            'call_dispositions': _get_dispositions_for_config(),
            'follow_up_priorities': [{'value': k, 'label': v} for k, v in [
                ('low', 'Low'), ('medium', 'Medium'), ('high', 'High'), ('urgent', 'Urgent')
            ]],
            'task_priorities': [{'value': k, 'label': v} for k, v in [
                ('low', 'Low'), ('medium', 'Medium'), ('high', 'High'), ('urgent', 'Urgent')
            ]],
            'note_types': [{'value': k, 'label': v} for k, v in LeadNote.NOTE_TYPE_CHOICES],
            'products': products,
            'agent_targets': {
                'daily_calls': agent_profile.target_calls_per_day,
                'monthly_conversions': agent_profile.target_conversions_per_month,
            },
            'app_settings': {
                'auto_dial_enabled': True,
                'notification_enabled': True,
                'offline_mode_enabled': True,
                'lead_scoring_enabled': True,
            },
            'score_thresholds': {
                'hot': 75,
                'warm': 40,
                'cold': 0,
            },
        })
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ─────────────────────────────────────────────────────────────────────────────
# ACTIVITY TRACKING — Session + Event endpoints called by Flutter app
# ─────────────────────────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def start_dialer_session(request):
    """
    POST /api/activity/session/start/
    Creates a new DialerSession and returns its ID.
    Also bumps last_heartbeat so the agent shows as online.
    """
    session = DialerSession.objects.create(agent=request.user)
    AgentProfile.objects.filter(user=request.user).update(last_heartbeat=timezone.now())
    return Response({'session_id': session.pk}, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def log_activity_event(request, session_id):
    """
    POST /api/activity/session/{session_id}/event/
    Records a CallActivityEvent and bumps last_heartbeat.
    Body: { event_type, lead_id?, call_log_id?, metadata? }
    """
    session = get_object_or_404(DialerSession, pk=session_id, agent=request.user)
    event_type = request.data.get('event_type', '')

    valid_types = {c[0] for c in CallActivityEvent.EVENT_CHOICES}
    if event_type not in valid_types:
        return Response({'error': f'Invalid event_type: {event_type}'}, status=status.HTTP_400_BAD_REQUEST)

    lead = None
    lead_id = request.data.get('lead_id')
    if lead_id:
        lead = get_object_or_404(Lead, id=lead_id, assigned_agent=request.user)

    event = CallActivityEvent.objects.create(
        agent=request.user,
        session=session,
        event_type=event_type,
        lead=lead,
        call_log_id=request.data.get('call_log_id'),
        metadata=request.data.get('metadata') or {},
    )

    if event_type == 'call_started':
        if lead and not event.call_log_id:
            call_log = _create_autodial_call_log(request.user, lead)
            event.call_log = call_log
            event.save(update_fields=['call_log'])
        # Increment live so the real-time monitor reflects the call immediately,
        # without waiting for finalize() at session end.
        from django.db.models import F
        DialerSession.objects.filter(pk=session.pk).update(
            total_calls_made=F('total_calls_made') + 1
        )
        AgentProfile.objects.filter(user=request.user).update(last_heartbeat=timezone.now())
    elif event_type == 'session_end':
        session.finalize()
        AgentProfile.objects.filter(user=request.user).update(last_heartbeat=None)
    else:
        AgentProfile.objects.filter(user=request.user).update(last_heartbeat=timezone.now())

    return Response({'event_id': event.pk}, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def agent_heartbeat(request):
    """
    POST /api/heartbeat/
    Keep-alive that marks the agent as online (called every ~60s by Flutter).
    """
    AgentProfile.objects.filter(user=request.user).update(last_heartbeat=timezone.now())
    return Response({'status': 'ok'})


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def dialer_progress_view(request):
    """
    GET  /api/dialer/progress/  — returns the lead ID the agent last stopped on
    POST /api/dialer/progress/  — saves that ID (or null to clear after queue completes)
    """
    try:
        profile = AgentProfile.objects.get(user=request.user)
    except AgentProfile.DoesNotExist:
        return Response({'last_lead_id': None})

    if request.method == 'POST':
        lead_id = request.data.get('last_lead_id')
        AgentProfile.objects.filter(user=request.user).update(
            dialer_last_lead_id=lead_id
        )
        return Response({'status': 'saved'})

    return Response({'last_lead_id': profile.dialer_last_lead_id})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_live_status(request):
    """
    GET /api/admin/live-status/
    Per-agent online status + today's live call counts for the Live Monitor poll.
    Staff only.
    """
    if not request.user.is_staff:
        return Response({'error': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)

    today = timezone.now().date()

    # Aggregate from CallLog so live monitor, lead count, and app stats agree.
    calls_by_agent = (
        CallLog.objects
        .filter(call_date__date=today)
        .values('agent_id')
        .annotate(calls=Count('id'))
    )
    calls_map = {row['agent_id']: row['calls'] or 0 for row in calls_by_agent}

    profiles = AgentProfile.objects.filter(is_active=True).select_related('user')
    data = [{
        'user_id':        p.user_id,
        'name':           p.user.get_full_name() or p.user.username,
        'is_online':      p.is_online,
        'last_heartbeat': p.last_heartbeat.isoformat() if p.last_heartbeat else None,
        'calls_today':    calls_map.get(p.user_id, 0),
    } for p in profiles]

    return Response({
        'agents':            data,
        'online_count':      sum(1 for d in data if d['is_online']),
        'total_calls_today': sum(d['calls_today'] for d in data),
    })
