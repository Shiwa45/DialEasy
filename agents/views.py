# agents/views.py - FIXED VERSION

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.contrib import messages
from django.db.models import Count, Q, Avg, Sum
from django.utils import timezone
from django.core.paginator import Paginator
from django.http import JsonResponse
from datetime import datetime, timedelta
from calendar import monthrange

from leads.models import Lead, CallLog, FollowUp
from .models import AgentProfile, AgentTarget, AgentNote, DialerSession, CallActivityEvent

def is_admin(user):
    """Check if user is admin/staff for this tenant"""
    if not user.is_authenticated or not user.is_active:
        return False
    
    # Global superusers always have access
    if user.is_superuser:
        return True
        
    # Check tenant-specific role in AgentProfile
    try:
        return user.agent_profile.role in ['admin', 'manager']
    except Exception:
        # Fallback to is_staff for legacy users or non-agent admins
        return user.is_staff

@login_required
@user_passes_test(is_admin)
def agent_list(request):
    """Display all agents with their basic stats"""
    
    # Scope to this tenant: AgentProfile is in the tenant schema so values_list
    # returns only IDs belonging to the current tenant.
    tenant_agent_ids = AgentProfile.objects.values_list('user_id', flat=True)
    agents = User.objects.filter(
        id__in=tenant_agent_ids,
        is_active=True,
    ).prefetch_related(
        'assigned_leads', 'call_logs', 'follow_ups', 'agent_profile'
    ).annotate(
        total_leads=Count('assigned_leads'),
        total_calls=Count('call_logs'),
        converted_leads=Count('assigned_leads', filter=Q(assigned_leads__status='converted')),
        pending_follow_ups=Count('follow_ups', filter=Q(follow_ups__is_completed=False))
    ).order_by('-date_joined')
    
    # Get today's call counts and calculate conversion rates
    today = timezone.now().date()
    for agent in agents:
        agent.today_calls = CallLog.objects.filter(
            agent=agent, 
            call_date__date=today
        ).count()
        
        # Calculate conversion rate
        if agent.total_leads > 0:
            agent.conversion_rate = round((agent.converted_leads / agent.total_leads) * 100, 2)
        else:
            agent.conversion_rate = 0
    
    # Pagination
    paginator = Paginator(agents, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Summary statistics
    total_agents = agents.count()
    total_leads_assigned = sum(agent.total_leads for agent in agents)
    total_calls_made = sum(agent.total_calls for agent in agents)
    total_conversions = sum(agent.converted_leads for agent in agents)
    
    context = {
        'page_obj': page_obj,
        'total_agents': total_agents,
        'total_leads_assigned': total_leads_assigned,
        'total_calls_made': total_calls_made,
        'total_conversions': total_conversions,
        'avg_conversion_rate': round(total_conversions / total_leads_assigned * 100, 2) if total_leads_assigned > 0 else 0,
    }
    
    return render(request, 'agents/agent_list.html', context)


@login_required
@user_passes_test(is_admin)
def agent_detail(request, agent_id):
    """Display detailed view of an agent"""
    
    # Ensure agent exists and HAS a profile in this tenant
    agent = get_object_or_404(User, id=agent_id, agent_profile__isnull=False)
    agent_profile = agent.agent_profile
    agent_profile.update_stats()
    
    # Get agent's leads with status breakdown
    agent_leads = Lead.objects.filter(assigned_agent=agent)
    lead_status_breakdown = agent_leads.values('status').annotate(count=Count('id'))
    
    # Get recent activity
    recent_calls = CallLog.objects.filter(agent=agent).select_related('lead').order_by('-call_date')[:10]
    upcoming_follow_ups = FollowUp.objects.filter(
        agent=agent,
        is_completed=False,
        follow_up_date__gte=timezone.now().date()
    ).select_related('lead').order_by('follow_up_date', 'follow_up_time')[:10]
    
    # Get monthly performance for last 6 months
    monthly_performance = []
    current_date = timezone.now().date().replace(day=1)
    
    for i in range(6):
        month_start = current_date.replace(day=1)
        month_end = current_date.replace(day=monthrange(current_date.year, current_date.month)[1])
        
        calls_count = CallLog.objects.filter(
            agent=agent,
            call_date__date__range=[month_start, month_end]
        ).count()
        
        conversions_count = Lead.objects.filter(
            assigned_agent=agent,
            status='converted',
            updated_at__date__range=[month_start, month_end]
        ).count()
        
        monthly_performance.append({
            'month': current_date.strftime('%B %Y'),
            'calls': calls_count,
            'conversions': conversions_count,
            'conversion_rate': round(conversions_count / calls_count * 100, 2) if calls_count > 0 else 0
        })
        
        # Move to previous month
        if current_date.month == 1:
            current_date = current_date.replace(year=current_date.year - 1, month=12)
        else:
            current_date = current_date.replace(month=current_date.month - 1)
    
    monthly_performance.reverse()
    
    # Get agent notes
    agent_notes = AgentNote.objects.filter(agent=agent).select_related('created_by').order_by('-created_at')[:5]
    
    # Calculate performance metrics
    total_leads = agent_leads.count()
    total_calls = CallLog.objects.filter(agent=agent).count()
    converted_leads = agent_leads.filter(status='converted').count()
    conversion_rate = round(converted_leads / total_leads * 100, 2) if total_leads > 0 else 0
    
    # Today's stats
    today = timezone.now().date()
    today_calls = CallLog.objects.filter(agent=agent, call_date__date=today).count()
    
    # This week's stats
    week_start = today - timedelta(days=today.weekday())
    week_calls = CallLog.objects.filter(
        agent=agent,
        call_date__date__range=[week_start, today]
    ).count()
    
    context = {
        'agent': agent,
        'agent_profile': agent_profile,
        'agent_leads': agent_leads,
        'lead_status_breakdown': lead_status_breakdown,
        'recent_calls': recent_calls,
        'upcoming_follow_ups': upcoming_follow_ups,
        'monthly_performance': monthly_performance,
        'agent_notes': agent_notes,
        'total_leads': total_leads,
        'total_calls': total_calls,
        'converted_leads': converted_leads,
        'conversion_rate': conversion_rate,
        'today_calls': today_calls,
        'week_calls': week_calls,
    }
    
    return render(request, 'agents/agent_detail.html', context)


@login_required
@user_passes_test(is_admin)
def create_agent(request):
    """Create a new agent"""
    
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        phone = request.POST.get('phone', '').strip()
        department = request.POST.get('department', '').strip()
        role = request.POST.get('role', 'agent').strip()
        
        # Get targets with default values
        try:
            target_calls = int(request.POST.get('target_calls_per_day', 50))
        except (ValueError, TypeError):
            target_calls = 50
            
        try:
            target_conversions = int(request.POST.get('target_conversions_per_month', 10))
        except (ValueError, TypeError):
            target_conversions = 10
        
        # ── Agent Limit Check ──────────────────────────────────────────────────
        # Look up this tenant's effective limit from the public schema.
        try:
            from django.db import connection
            from django_tenants.utils import get_public_schema_name
            current_schema = connection.schema_name
            if current_schema != get_public_schema_name():
                from tenants.models import Client
                tenant = Client.objects.using('default').get(schema_name=current_schema)
                limit = tenant.effective_agent_limit
                if limit != -1:
                    # Count only actual agent accounts (AgentProfile records),
                    # excluding tenant admins (is_staff=True) and superusers.
                    current_count = AgentProfile.objects.filter(
                        user__is_staff=False,
                        user__is_superuser=False,
                        is_active=True,
                    ).count()
                    if current_count >= limit:
                        messages.error(
                            request,
                            f'Agent limit reached ({current_count}/{limit}). '
                            f'Please contact your provider to increase your plan limit.'
                        )
                        return render(request, 'agents/create_agent.html')
        except Exception:
            pass  # Fail open — don't block creation if limit check errors

        # Validation
        if not username:
            messages.error(request, 'Username is required.')
            return render(request, 'agents/create_agent.html')
        
        if not password:
            messages.error(request, 'Password is required.')
            return render(request, 'agents/create_agent.html')
        
        if len(username) < 3:
            messages.error(request, 'Username must be at least 3 characters long.')
            return render(request, 'agents/create_agent.html')
        
        if len(password) < 8:
            messages.error(request, 'Password must be at least 8 characters long.')
            return render(request, 'agents/create_agent.html')
        
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists.')
            return render(request, 'agents/create_agent.html')
        
        if email and User.objects.filter(email=email).exists():
            messages.error(request, 'Email already exists.')
            return render(request, 'agents/create_agent.html')
        
        try:
            # Create user
            user = User.objects.create_user(
                username=username,
                first_name=first_name,
                last_name=last_name,
                email=email,
                password=password,
                is_staff=False,
                is_active=True
            )
            
            # Create agent profile
            AgentProfile.objects.create(
                user=user,
                phone=phone,
                department=department,
                role=role,
                hire_date=timezone.now().date(),
                target_calls_per_day=target_calls,
                target_conversions_per_month=target_conversions,
                is_active=True
            )
            
            messages.success(request, f'Agent "{username}" created successfully.')
            return redirect('agents:agent_detail', agent_id=user.id)
            
        except Exception as e:
            messages.error(request, f'Error creating agent: {str(e)}')
            return render(request, 'agents/create_agent.html')
    
    return render(request, 'agents/create_agent.html')


@login_required
@user_passes_test(is_admin)
def agent_performance(request, agent_id):
    """Display detailed agent performance metrics"""
    
    agent = get_object_or_404(User, id=agent_id, is_staff=False)
    
    # Get date range from request (default to last 30 days)
    end_date = timezone.now().date()
    start_date_param = request.GET.get('start_date')
    end_date_param = request.GET.get('end_date')
    
    if start_date_param and end_date_param:
        try:
            start_date = datetime.strptime(start_date_param, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_param, '%Y-%m-%d').date()
        except ValueError:
            start_date = end_date - timedelta(days=30)
    else:
        start_date = end_date - timedelta(days=30)
    
    # Get performance data
    calls_in_period = CallLog.objects.filter(
        agent=agent,
        call_date__date__range=[start_date, end_date]
    )
    
    leads_in_period = Lead.objects.filter(
        assigned_agent=agent,
        created_at__date__range=[start_date, end_date]
    )
    
    # Daily performance data
    daily_performance = []
    current_date = start_date
    while current_date <= end_date:
        daily_calls = calls_in_period.filter(call_date__date=current_date).count()
        daily_conversions = Lead.objects.filter(
            assigned_agent=agent,
            status='converted',
            updated_at__date=current_date
        ).count()
        
        daily_performance.append({
            'date': current_date.strftime('%Y-%m-%d'),
            'date_display': current_date.strftime('%b %d'),
            'calls': daily_calls,
            'conversions': daily_conversions
        })
        
        current_date += timedelta(days=1)
    
    # Disposition breakdown
    disposition_breakdown = calls_in_period.values('disposition').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # Lead source performance
    source_performance = leads_in_period.values('source').annotate(
        total=Count('id'),
        converted=Count('id', filter=Q(status='converted'))
    ).order_by('-total')
    
    for source in source_performance:
        if source['total'] > 0:
            source['conversion_rate'] = round(source['converted'] / source['total'] * 100, 2)
        else:
            source['conversion_rate'] = 0
    
    # Performance summary
    total_calls = calls_in_period.count()
    total_leads = leads_in_period.count()
    total_conversions = leads_in_period.filter(status='converted').count()
    avg_calls_per_day = round(total_calls / ((end_date - start_date).days + 1), 2)
    conversion_rate = round(total_conversions / total_leads * 100, 2) if total_leads > 0 else 0
    
    # Target comparison (if targets exist)
    current_month = timezone.now().date().replace(day=1)
    try:
        current_target = AgentTarget.objects.get(agent=agent, month=current_month)
    except AgentTarget.DoesNotExist:
        current_target = None
    
    context = {
        'agent': agent,
        'start_date': start_date,
        'end_date': end_date,
        'daily_performance': daily_performance,
        'disposition_breakdown': disposition_breakdown,
        'source_performance': source_performance,
        'total_calls': total_calls,
        'total_leads': total_leads,
        'total_conversions': total_conversions,
        'avg_calls_per_day': avg_calls_per_day,
        'conversion_rate': conversion_rate,
        'current_target': current_target,
    }
    
    return render(request, 'agents/agent_performance.html', context)


@login_required
@user_passes_test(is_admin)
def update_agent(request, agent_id):
    """Update agent information"""
    
    agent = get_object_or_404(User, id=agent_id, is_staff=False)
    
    # Get or create agent profile - FIXED
    try:
        agent_profile = agent.agent_profile
    except AgentProfile.DoesNotExist:
        agent_profile = AgentProfile.objects.create(
            user=agent,
            hire_date=timezone.now().date(),
            target_calls_per_day=50,
            target_conversions_per_month=10
        )
    
    if request.method == 'POST':
        try:
            # Update user fields
            agent.first_name = request.POST.get('first_name', '').strip()
            agent.last_name = request.POST.get('last_name', '').strip()
            agent.email = request.POST.get('email', '').strip()
            
            # Update profile fields
            agent_profile.phone = request.POST.get('phone', '').strip()
            agent_profile.department = request.POST.get('department', '').strip()
            agent_profile.target_calls_per_day = int(request.POST.get('target_calls_per_day', 50))
            agent_profile.target_conversions_per_month = int(request.POST.get('target_conversions_per_month', 10))
            agent_profile.is_active = request.POST.get('is_active') == 'on'
            
            agent.save()
            agent_profile.save()
            
            messages.success(request, 'Agent information updated successfully.')
            
        except Exception as e:
            messages.error(request, f'Error updating agent: {str(e)}')
        
        return redirect('agents:agent_detail', agent_id=agent.id)
    
    context = {
        'agent': agent,
        'agent_profile': agent_profile,
    }
    
    return render(request, 'agents/update_agent.html', context)


@login_required
@user_passes_test(is_admin)
def add_agent_note(request, agent_id):
    """Add a note about an agent"""
    
    if request.method == 'POST':
        agent = get_object_or_404(User, id=agent_id, is_staff=False)
        note_text = request.POST.get('note', '').strip()
        is_private = request.POST.get('is_private') == 'on'
        
        if note_text:
            try:
                AgentNote.objects.create(
                    agent=agent,
                    created_by=request.user,
                    note=note_text,
                    is_private=is_private
                )
                messages.success(request, 'Note added successfully.')
            except Exception as e:
                messages.error(request, f'Error adding note: {str(e)}')
        else:
            messages.error(request, 'Note text is required.')
    
    return redirect('agents:agent_detail', agent_id=agent_id)


@login_required
@user_passes_test(is_admin)
def set_agent_targets(request, agent_id):
    """Set monthly targets for an agent"""
    
    agent = get_object_or_404(User, id=agent_id, is_staff=False)
    
    if request.method == 'POST':
        month_str = request.POST.get('month', '')  # Format: YYYY-MM
        
        try:
            target_calls = int(request.POST.get('target_calls', 0))
            target_conversions = int(request.POST.get('target_conversions', 0))
            target_revenue = float(request.POST.get('target_revenue', 0))
        except (ValueError, TypeError):
            messages.error(request, 'Invalid target values.')
            return redirect('agents:agent_detail', agent_id=agent_id)
        
        try:
            month_date = datetime.strptime(month_str, '%Y-%m').date().replace(day=1)
            
            target, created = AgentTarget.objects.get_or_create(
                agent=agent,
                month=month_date,
                defaults={
                    'target_calls': target_calls,
                    'target_conversions': target_conversions,
                    'target_revenue': target_revenue
                }
            )
            
            if not created:
                target.target_calls = target_calls
                target.target_conversions = target_conversions
                target.target_revenue = target_revenue
                target.save()
            
            messages.success(request, f'Targets set for {month_date.strftime("%B %Y")}.')
            
        except ValueError:
            messages.error(request, 'Invalid month format. Use YYYY-MM.')
        except Exception as e:
            messages.error(request, f'Error setting targets: {str(e)}')
    
    return redirect('agents:agent_detail', agent_id=agent_id)


# Agent Self-Service Views (for agents to view their own data)

@login_required
def agent_dashboard(request):
    """Dashboard for individual agents to view their own performance"""
    
    if request.user.is_staff:
        return redirect('leads:dashboard')
    
    agent = request.user
    today = timezone.now().date()
    
    # Get agent's basic stats
    total_leads = Lead.objects.filter(assigned_agent=agent).count()
    new_leads = Lead.objects.filter(assigned_agent=agent, status='new').count()
    contacted_leads = Lead.objects.filter(assigned_agent=agent, status='contacted').count()
    converted_leads = Lead.objects.filter(assigned_agent=agent, status='converted').count()
    
    # Today's stats
    today_calls = CallLog.objects.filter(agent=agent, call_date__date=today).count()
    today_follow_ups = FollowUp.objects.filter(
        agent=agent,
        follow_up_date=today,
        is_completed=False
    ).count()
    
    # Recent activity
    recent_calls = CallLog.objects.filter(agent=agent).select_related('lead').order_by('-call_date')[:10]
    upcoming_follow_ups = FollowUp.objects.filter(
        agent=agent,
        is_completed=False,
        follow_up_date__gte=today
    ).select_related('lead').order_by('follow_up_date', 'follow_up_time')[:10]
    
    # Performance metrics
    conversion_rate = round(converted_leads / total_leads * 100, 2) if total_leads > 0 else 0
    
    # This week's performance
    week_start = today - timedelta(days=today.weekday())
    week_calls = CallLog.objects.filter(
        agent=agent,
        call_date__date__range=[week_start, today]
    ).count()
    
    # Get agent profile and targets - FIXED
    try:
        agent_profile = agent.agent_profile
    except AgentProfile.DoesNotExist:
        agent_profile = AgentProfile.objects.create(
            user=agent,
            hire_date=timezone.now().date(),
            target_calls_per_day=50,
            target_conversions_per_month=10
        )
    
    current_month = today.replace(day=1)
    
    try:
        current_target = AgentTarget.objects.get(agent=agent, month=current_month)
        # Update actual achievements
        current_target.actual_calls = CallLog.objects.filter(
            agent=agent,
            call_date__date__range=[current_month, today]
        ).count()
        current_target.actual_conversions = Lead.objects.filter(
            assigned_agent=agent,
            status='converted',
            updated_at__date__range=[current_month, today]
        ).count()
        current_target.save()
    except AgentTarget.DoesNotExist:
        current_target = None
    
    context = {
        'agent': agent,
        'agent_profile': agent_profile,
        'total_leads': total_leads,
        'new_leads': new_leads,
        'contacted_leads': contacted_leads,
        'converted_leads': converted_leads,
        'today_calls': today_calls,
        'today_follow_ups': today_follow_ups,
        'recent_calls': recent_calls,
        'upcoming_follow_ups': upcoming_follow_ups,
        'conversion_rate': conversion_rate,
        'week_calls': week_calls,
        'current_target': current_target,
    }
    
    return render(request, 'agents/agent_dashboard.html', context)


@login_required
def agent_leads(request):
    """View agent's assigned leads"""
    
    if request.user.is_staff:
        return redirect('leads:lead_list')
    
    agent = request.user
    leads = Lead.objects.filter(assigned_agent=agent)
    
    # Apply filters
    status_filter = request.GET.get('status')
    if status_filter:
        leads = leads.filter(status=status_filter)
    
    search_query = request.GET.get('search')
    if search_query:
        leads = leads.filter(
            Q(name__icontains=search_query) |
            Q(phone__icontains=search_query) |
            Q(company__icontains=search_query)
        )
    
    # Order leads by priority
    leads = leads.order_by('status', '-created_at')
    
    # Pagination
    paginator = Paginator(leads, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'status_filter': status_filter,
        'search_query': search_query,
        'status_choices': Lead.STATUS_CHOICES,
    }
    
    return render(request, 'agents/agent_leads.html', context)


# AJAX Views
@login_required
def agent_stats_ajax(request, agent_id):
    """Get agent statistics via AJAX"""
    
    agent = get_object_or_404(User, id=agent_id, is_staff=False)
    today = timezone.now().date()
    
    try:
        stats = {
            'total_leads': Lead.objects.filter(assigned_agent=agent).count(),
            'total_calls': CallLog.objects.filter(agent=agent).count(),
            'today_calls': CallLog.objects.filter(agent=agent, call_date__date=today).count(),
            'converted_leads': Lead.objects.filter(assigned_agent=agent, status='converted').count(),
            'pending_follow_ups': FollowUp.objects.filter(
                agent=agent, 
                is_completed=False
            ).count(),
        }
        
        # Calculate conversion rate
        if stats['total_leads'] > 0:
            stats['conversion_rate'] = round(stats['converted_leads'] / stats['total_leads'] * 100, 2)
        else:
            stats['conversion_rate'] = 0
        
        return JsonResponse(stats)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ─── Agent Activity / Time Tracking ────────────────────────────────────────────

@login_required
@user_passes_test(is_admin)
def agent_activity_list(request):
    """Admin view: time-tracking summary for all agents."""
    today       = timezone.now().date()
    date_str    = request.GET.get('date', str(today))
    agent_id    = request.GET.get('agent')

    try:
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        selected_date = today

    # Scope to this tenant's agents only
    tenant_agent_ids = AgentProfile.objects.values_list('user_id', flat=True)
    agents = User.objects.filter(id__in=tenant_agent_ids, is_active=True).order_by('first_name', 'username')

    # Pre-fetch online status from AgentProfile (keyed by user_id)
    online_map = {
        p.user_id: p.is_online
        for p in AgentProfile.objects.filter(user_id__in=tenant_agent_ids)
    }

    # Build per-agent summary for the selected date
    summary_rows = []
    for agent in agents:
        sessions = DialerSession.objects.filter(
            agent=agent,
            session_start__date=selected_date
        )
        total_session_secs   = sum(s.session_duration_seconds for s in sessions)
        total_call_secs      = sum(s.total_call_time_seconds   for s in sessions)
        total_disp_secs      = sum(s.total_disposition_time_seconds for s in sessions)
        total_idle_secs      = max(0, total_session_secs - total_call_secs - total_disp_secs)
        total_calls          = sum(s.total_calls_made          for s in sessions)

        summary_rows.append({
            'agent':               agent,
            'session_count':       sessions.count(),
            'total_session':       _fmt(total_session_secs),
            'total_call':          _fmt(total_call_secs),
            'total_disposition':   _fmt(total_disp_secs),
            'total_idle':          _fmt(total_idle_secs),
            'total_calls_made':    total_calls,
            'efficiency_pct':      round(total_call_secs / total_session_secs * 100, 1) if total_session_secs else 0,
            'is_online':           online_map.get(agent.pk, False),
        })

    active_agents_count  = sum(1 for row in summary_rows if row['is_online'])
    total_calls_today    = sum(row['total_calls_made'] for row in summary_rows)

    context = {
        'summary_rows':       summary_rows,
        'selected_date':      selected_date,
        'agents':             agents,
        'selected_agent_id':  agent_id,
        'active_agents_count': active_agents_count,
        'total_calls_today':  total_calls_today,
    }
    return render(request, 'agents/agent_activity_list.html', context)


@login_required
@user_passes_test(is_admin)
def agent_activity_detail(request, agent_id):
    """Admin view: per-session timeline for one agent."""
    agent = get_object_or_404(User, id=agent_id, is_staff=False)
    today = timezone.now().date()

    start_str = request.GET.get('start', str(today - timedelta(days=6)))
    end_str   = request.GET.get('end',   str(today))
    try:
        start_date = datetime.strptime(start_str, '%Y-%m-%d').date()
        end_date   = datetime.strptime(end_str,   '%Y-%m-%d').date()
    except ValueError:
        start_date = today - timedelta(days=6)
        end_date   = today

    sessions = DialerSession.objects.filter(
        agent=agent,
        session_start__date__range=[start_date, end_date]
    ).prefetch_related('events').order_by('-session_start')

    # Daily roll-up for chart
    daily_data = []
    cur = start_date
    while cur <= end_date:
        day_sessions = sessions.filter(session_start__date=cur)
        daily_data.append({
            'date':          cur.strftime('%b %d'),
            'session_secs':  sum(s.session_duration_seconds for s in day_sessions),
            'call_secs':     sum(s.total_call_time_seconds   for s in day_sessions),
            'disp_secs':     sum(s.total_disposition_time_seconds for s in day_sessions),
        })
        cur += timedelta(days=1)

    context = {
        'agent':       agent,
        'sessions':    sessions,
        'daily_data':  daily_data,
        'start_date':  start_date,
        'end_date':    end_date,
    }
    return render(request, 'agents/agent_activity_detail.html', context)


def _fmt(secs):
    """HH:MM:SS helper for templates."""
    h = secs // 3600; m = (secs % 3600) // 60; s = secs % 60
    return f"{h:02d}:{m:02d}:{s:02d}"
