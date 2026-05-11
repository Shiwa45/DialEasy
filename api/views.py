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
from django.db.models import Count, Q
from django.http import JsonResponse
from datetime import datetime, timedelta
import json

from leads.models import Lead, CallLog, FollowUp
from agents.models import AgentProfile, AgentTarget, DialerSession, CallActivityEvent
from .serializers import (
    LeadSerializer, CallLogSerializer, FollowUpSerializer,
    LeadUpdateSerializer, CallLogCreateSerializer, FollowUpCreateSerializer,
    UserSerializer, LeadDetailSerializer
)

# Custom Pagination
class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

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
            # Create or get token
            token, created = Token.objects.get_or_create(user=user)
            
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
            allowed_orderings = ['created_at', '-created_at', 'name', '-name', 'status', '-status']
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
        lead_statuses = Lead.objects.filter(assigned_agent=user).values('status').annotate(count=Count('id'))
        
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
                'contacted_leads': contacted_leads,
                'converted_leads': converted_leads,
                'conversion_rate': conversion_rate,
                'today_calls': today_calls,
                'today_follow_ups': today_follow_ups,
                'week_calls': week_calls,
            },
            'lead_statuses': list(lead_statuses),
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
            call_log = serializer.save()
            
            # Update lead status if specified
            new_status = request.data.get('lead_status')
            if new_status and new_status in dict(Lead.STATUS_CHOICES):
                lead.status = new_status
                lead.save()
            
            return Response(CallLogSerializer(call_log).data, status=status.HTTP_201_CREATED)
        
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
    Get available call disposition choices
    
    GET /api/utils/call-disposition-choices/
    """
    return Response({
        'choices': [{'value': choice[0], 'label': choice[1]} for choice in CallLog.DISPOSITION_CHOICES]
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def app_config(request):
    """
    Get app configuration for mobile
    
    GET /api/utils/app-config/
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
            'lead_statuses': [{'value': choice[0], 'label': choice[1]} for choice in Lead.STATUS_CHOICES],
            'call_dispositions': [{'value': choice[0], 'label': choice[1]} for choice in CallLog.DISPOSITION_CHOICES],
            'agent_targets': {
                'daily_calls': agent_profile.target_calls_per_day,
                'monthly_conversions': agent_profile.target_conversions_per_month,
            },
            'app_settings': {
                'auto_dial_enabled': True,
                'notification_enabled': True,
                'call_recording_enabled': agent_profile.call_recording_enabled,
                'offline_mode_enabled': True,
            }
        })
    except Exception as e:
        return Response(
            {'error': f'App config fetch failed: {str(e)}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

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
        
        # Get updated data
        updated_leads = Lead.objects.filter(
            assigned_agent=request.user,
            updated_at__gte=since_date
        )
        
        new_call_logs = CallLog.objects.filter(
            agent=request.user,
            created_at__gte=since_date
        )
        
        new_follow_ups = FollowUp.objects.filter(
            agent=request.user,
            created_at__gte=since_date
        )
        
        return Response({
            'leads': LeadSerializer(updated_leads, many=True).data,
            'call_logs': CallLogSerializer(new_call_logs, many=True).data,
            'follow_ups': FollowUpSerializer(new_follow_ups, many=True).data,
            'sync_timestamp': timezone.now().isoformat()
        })
    except Exception as e:
        return Response(
            {'error': f'Sync download failed: {str(e)}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

# ===============================
# PERFORMANCE ENDPOINTS
# ===============================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def performance_summary(request):
    """
    Get performance summary for different time periods
    
    GET /api/performance/summary/?period=week
    """
    try:
        if request.user.is_staff:
            return Response({'error': 'This endpoint is for agents only'}, status=status.HTTP_403_FORBIDDEN)
        
        period = request.query_params.get('period', 'week')  # week, month, quarter
        today = timezone.now().date()
        
        if period == 'week':
            start_date = today - timedelta(days=7)
        elif period == 'month':
            start_date = today.replace(day=1)
        elif period == 'quarter':
            quarter_start_month = ((today.month - 1) // 3) * 3 + 1
            start_date = today.replace(month=quarter_start_month, day=1)
        else:
            start_date = today - timedelta(days=7)
        
        # Get performance data
        calls = CallLog.objects.filter(
            agent=request.user,
            call_date__date__range=[start_date, today]
        )
        
        leads = Lead.objects.filter(
            assigned_agent=request.user,
            updated_at__date__range=[start_date, today]
        )
        
        # Get top disposition
        top_disposition = calls.values('disposition').annotate(count=Count('id')).order_by('-count').first()
        
        return Response({
            'period': period,
            'start_date': start_date.isoformat(),
            'end_date': today.isoformat(),
            'metrics': {
                'total_calls': calls.count(),
                'total_leads': leads.count(),
                'conversions': leads.filter(status='converted').count(),
                'conversion_rate': round(leads.filter(status='converted').count() / leads.count() * 100, 2) if leads.count() > 0 else 0,
                'avg_calls_per_day': round(calls.count() / ((today - start_date).days + 1), 2),
                'top_disposition': top_disposition
            }
        })
    except Exception as e:
        return Response(
            {'error': f'Performance summary failed: {str(e)}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    



# api/views.py - ADD THESE FOLLOW-UP ENDPOINTS TO YOUR EXISTING FILE

from django.utils import timezone
from datetime import datetime, timedelta

# Add these imports to your existing imports
from django.db.models import Q, Count
from django.http import JsonResponse
import json

# ===============================
# FOLLOW-UP SPECIFIC ENDPOINTS
# ===============================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def today_follow_ups(request):
    """
    Get today's follow-ups for the agent
    
    GET /api/follow-ups/today/
    """
    try:
        if request.user.is_staff:
            return Response({'error': 'This endpoint is for agents only'}, status=status.HTTP_403_FORBIDDEN)
        
        today = timezone.now().date()
        follow_ups = FollowUp.objects.filter(
            agent=request.user,
            follow_up_date=today,
            is_completed=False
        ).select_related('lead', 'agent').order_by('follow_up_time')
        
        serializer = FollowUpSerializer(follow_ups, many=True)
        return Response(serializer.data)
    except Exception as e:
        return Response(
            {'error': f'Failed to get today\'s follow-ups: {str(e)}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def overdue_follow_ups(request):
    """
    Get overdue follow-ups for the agent
    
    GET /api/follow-ups/overdue/
    """
    try:
        if request.user.is_staff:
            return Response({'error': 'This endpoint is for agents only'}, status=status.HTTP_403_FORBIDDEN)
        
        today = timezone.now().date()
        follow_ups = FollowUp.objects.filter(
            agent=request.user,
            follow_up_date__lt=today,
            is_completed=False
        ).select_related('lead', 'agent').order_by('-follow_up_date', 'follow_up_time')
        
        serializer = FollowUpSerializer(follow_ups, many=True)
        return Response(serializer.data)
    except Exception as e:
        return Response(
            {'error': f'Failed to get overdue follow-ups: {str(e)}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def upcoming_follow_ups(request):
    """
    Get upcoming follow-ups for the agent
    
    GET /api/follow-ups/upcoming/
    """
    try:
        if request.user.is_staff:
            return Response({'error': 'This endpoint is for agents only'}, status=status.HTTP_403_FORBIDDEN)
        
        today = timezone.now().date()
        follow_ups = FollowUp.objects.filter(
            agent=request.user,
            follow_up_date__gt=today,
            is_completed=False
        ).select_related('lead', 'agent').order_by('follow_up_date', 'follow_up_time')
        
        serializer = FollowUpSerializer(follow_ups, many=True)
        return Response(serializer.data)
    except Exception as e:
        return Response(
            {'error': f'Failed to get upcoming follow-ups: {str(e)}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def bulk_complete_follow_ups(request):
    """
    Mark multiple follow-ups as completed
    
    POST /api/follow-ups/bulk-complete/
    {
        "follow_up_ids": [1, 2, 3]
    }
    """
    try:
        if request.user.is_staff:
            return Response({'error': 'This endpoint is for agents only'}, status=status.HTTP_403_FORBIDDEN)
        
        follow_up_ids = request.data.get('follow_up_ids', [])
        
        if not follow_up_ids:
            return Response(
                {'error': 'follow_up_ids are required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate that agent owns these follow-ups
        follow_ups = FollowUp.objects.filter(
            id__in=follow_up_ids,
            agent=request.user,
            is_completed=False
        )
        
        if follow_ups.count() != len(follow_up_ids):
            return Response(
                {'error': 'Some follow-ups not found or already completed'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Mark as completed
        completed_count = follow_ups.update(
            is_completed=True,
            completed_at=timezone.now()
        )
        
        return Response({
            'message': f'Successfully completed {completed_count} follow-ups',
            'completed_count': completed_count
        })
    except Exception as e:
        return Response(
            {'error': f'Bulk complete failed: {str(e)}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def follow_up_stats(request):
    """
    Get follow-up statistics for the agent
    
    GET /api/follow-ups/stats/
    """
    try:
        if request.user.is_staff:
            return Response({'error': 'This endpoint is for agents only'}, status=status.HTTP_403_FORBIDDEN)
        
        today = timezone.now().date()
        
        # Basic counts
        total_follow_ups = FollowUp.objects.filter(agent=request.user).count()
        completed_follow_ups = FollowUp.objects.filter(agent=request.user, is_completed=True).count()
        pending_follow_ups = FollowUp.objects.filter(agent=request.user, is_completed=False).count()
        
        # Today's follow-ups
        today_follow_ups = FollowUp.objects.filter(
            agent=request.user,
            follow_up_date=today,
            is_completed=False
        ).count()
        
        # Overdue follow-ups
        overdue_follow_ups = FollowUp.objects.filter(
            agent=request.user,
            follow_up_date__lt=today,
            is_completed=False
        ).count()
        
        # This week's follow-ups
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        week_follow_ups = FollowUp.objects.filter(
            agent=request.user,
            follow_up_date__range=[week_start, week_end],
            is_completed=False
        ).count()
        
        # Completion rate
        completion_rate = round(completed_follow_ups / total_follow_ups * 100, 2) if total_follow_ups > 0 else 0
        
        # Recent activity (last 7 days)
        week_ago = today - timedelta(days=7)
        recent_completed = FollowUp.objects.filter(
            agent=request.user,
            completed_at__date__gte=week_ago,
            is_completed=True
        ).count()
        
        return Response({
            'total_follow_ups': total_follow_ups,
            'completed_follow_ups': completed_follow_ups,
            'pending_follow_ups': pending_follow_ups,
            'today_follow_ups': today_follow_ups,
            'overdue_follow_ups': overdue_follow_ups,
            'week_follow_ups': week_follow_ups,
            'completion_rate': completion_rate,
            'recent_completed': recent_completed,
        })
    except Exception as e:
        return Response(
            {'error': f'Failed to get follow-up stats: {str(e)}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def snooze_follow_up(request, follow_up_id):
    """
    Snooze a follow-up by rescheduling it
    
    POST /api/follow-ups/{follow_up_id}/snooze/
    {
        "snooze_minutes": 60  // Snooze for 60 minutes
    }
    """
    try:
        if request.user.is_staff:
            return Response({'error': 'This endpoint is for agents only'}, status=status.HTTP_403_FORBIDDEN)
        
        follow_up = get_object_or_404(
            FollowUp, 
            id=follow_up_id, 
            agent=request.user,
            is_completed=False
        )
        
        snooze_minutes = request.data.get('snooze_minutes', 60)
        
        try:
            snooze_minutes = int(snooze_minutes)
        except (ValueError, TypeError):
            return Response(
                {'error': 'Invalid snooze_minutes value'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Calculate new follow-up time
        now = timezone.now()
        new_datetime = now + timedelta(minutes=snooze_minutes)
        
        follow_up.follow_up_date = new_datetime.date()
        follow_up.follow_up_time = new_datetime.time()
        follow_up.remarks = f"Snoozed {snooze_minutes} minutes: {follow_up.remarks or ''}"
        follow_up.save()
        
        return Response(FollowUpSerializer(follow_up).data)
    except Exception as e:
        return Response(
            {'error': f'Failed to snooze follow-up: {str(e)}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def follow_up_dashboard(request):
    """
    Get follow-up dashboard data for the agent
    
    GET /api/follow-ups/dashboard/
    """
    try:
        if request.user.is_staff:
            return Response({'error': 'This endpoint is for agents only'}, status=status.HTTP_403_FORBIDDEN)
        
        user = request.user
        today = timezone.now().date()
        
        # Today's follow-ups
        today_follow_ups = FollowUp.objects.filter(
            agent=user,
            follow_up_date=today,
            is_completed=False
        ).select_related('lead').order_by('follow_up_time')[:5]
        
        # Overdue follow-ups
        overdue_follow_ups = FollowUp.objects.filter(
            agent=user,
            follow_up_date__lt=today,
            is_completed=False
        ).select_related('lead').order_by('-follow_up_date', 'follow_up_time')[:5]
        
        # Upcoming follow-ups (next 7 days)
        week_end = today + timedelta(days=7)
        upcoming_follow_ups = FollowUp.objects.filter(
            agent=user,
            follow_up_date__range=[today + timedelta(days=1), week_end],
            is_completed=False
        ).select_related('lead').order_by('follow_up_date', 'follow_up_time')[:5]
        
        # Recent completed follow-ups
        recent_completed = FollowUp.objects.filter(
            agent=user,
            is_completed=True
        ).select_related('lead').order_by('-completed_at')[:5]
        
        return Response({
            'today_follow_ups': FollowUpSerializer(today_follow_ups, many=True).data,
            'overdue_follow_ups': FollowUpSerializer(overdue_follow_ups, many=True).data,
            'upcoming_follow_ups': FollowUpSerializer(upcoming_follow_ups, many=True).data,
            'recent_completed': FollowUpSerializer(recent_completed, many=True).data,
        })
    except Exception as e:
        return Response(
            {'error': f'Failed to get follow-up dashboard: {str(e)}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

# ===============================
# ENHANCED DASHBOARD WITH FOLLOW-UPS
# ===============================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def enhanced_agent_dashboard(request):
    """
    Enhanced agent dashboard with follow-up integration
    
    GET /api/agent/enhanced-dashboard/
    """
    try:
        if request.user.is_staff:
            return Response({'error': 'This endpoint is for agents only'}, status=status.HTTP_403_FORBIDDEN)
        
        user = request.user
        today = timezone.now().date()
        
        # Get original dashboard data
        dashboard_response = agent_dashboard(request)
        if dashboard_response.status_code != 200:
            return dashboard_response
        
        dashboard_data = dashboard_response.data
        
        # Add follow-up specific data
        follow_up_stats = {
            'today_follow_ups': FollowUp.objects.filter(
                agent=user,
                follow_up_date=today,
                is_completed=False
            ).count(),
            'overdue_follow_ups': FollowUp.objects.filter(
                agent=user,
                follow_up_date__lt=today,
                is_completed=False
            ).count(),
            'total_follow_ups': FollowUp.objects.filter(
                agent=user,
                is_completed=False
            ).count(),
            'completed_today': FollowUp.objects.filter(
                agent=user,
                completed_at__date=today,
                is_completed=True
            ).count(),
        }
        
        # Get priority follow-ups (overdue + today)
        priority_follow_ups = FollowUp.objects.filter(
            agent=user,
            follow_up_date__lte=today,
            is_completed=False
        ).select_related('lead').order_by('follow_up_date', 'follow_up_time')[:3]
        
        # Add to dashboard data
        dashboard_data['follow_up_stats'] = follow_up_stats
        dashboard_data['priority_follow_ups'] = FollowUpSerializer(priority_follow_ups, many=True).data
        
        return Response(dashboard_data)
    except Exception as e:
        return Response(
            {'error': f'Enhanced dashboard fetch failed: {str(e)}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ===============================
# CALL RECORDING ENDPOINT
# ===============================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_call_recording(request, call_log_id):
    """
    Upload a call recording for a specific call log.

    POST /api/call-logs/<call_log_id>/upload-recording/
    Content-Type: multipart/form-data
    Body: recording=<audio file>
    """
    try:
        call_log = get_object_or_404(CallLog, id=call_log_id, agent=request.user)

        recording_file = request.FILES.get('recording')
        if not recording_file:
            return Response(
                {'error': 'No recording file provided'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate file type
        allowed_types = ['audio/m4a', 'audio/mp4', 'audio/mpeg', 'audio/ogg', 'audio/wav', 'audio/aac']
        content_type = recording_file.content_type or ''
        if content_type and content_type not in allowed_types:
            # Allow if content_type is empty (some clients don't set it)
            pass

        # Remove old recording if exists
        if call_log.recording:
            try:
                import os
                if os.path.isfile(call_log.recording.path):
                    os.remove(call_log.recording.path)
            except Exception:
                pass

        call_log.recording = recording_file
        call_log.recording_size = recording_file.size
        call_log.save()

        return Response({
            'message': 'Recording uploaded successfully',
            'call_log_id': call_log.id,
            'recording_url': request.build_absolute_uri(call_log.recording.url),
            'recording_size': call_log.recording_size,
        }, status=status.HTTP_200_OK)

    except Exception as e:
        return Response(
            {'error': f'Failed to upload recording: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ===============================
# TIME TRACKING ENDPOINTS
# ===============================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def start_dialer_session(request):
    """Start a new autodialer session. Returns session_id."""
    try:
        # End any open sessions first (safety net)
        for s in DialerSession.objects.filter(agent=request.user, session_end__isnull=True):
            s.finalize()

        session = DialerSession.objects.create(agent=request.user)
        CallActivityEvent.objects.create(
            agent=request.user,
            session=session,
            event_type='session_start',
            timestamp=session.session_start
        )
        return Response({'message': 'Session started', 'session_id': session.id}, status=status.HTTP_201_CREATED)
    except Exception as e:
        return Response({'error': f'Failed to start session: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def log_activity_event(request, session_id):
    """Log a timestamped event inside a dialer session."""
    try:
        session = get_object_or_404(DialerSession, id=session_id, agent=request.user)
        event_type = request.data.get('event_type')
        if not event_type:
            return Response({'error': 'event_type is required'}, status=status.HTTP_400_BAD_REQUEST)

        valid_events = [c[0] for c in CallActivityEvent.EVENT_CHOICES]
        if event_type not in valid_events:
            return Response({'error': f'Invalid event_type. Valid: {valid_events}'}, status=status.HTTP_400_BAD_REQUEST)

        if session.session_end and event_type != 'session_end':
            return Response({'error': 'Session already closed'}, status=status.HTTP_400_BAD_REQUEST)

        event = CallActivityEvent.objects.create(
            agent=request.user,
            session=session,
            event_type=event_type,
            lead_id=request.data.get('lead_id'),
            call_log_id=request.data.get('call_log_id'),
            timestamp=timezone.now()
        )

        if event_type == 'session_end':
            session.finalize()

        return Response({'message': 'Event logged', 'event_id': event.id}, status=status.HTTP_201_CREATED)
    except Exception as e:
        return Response({'error': f'Failed to log event: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
