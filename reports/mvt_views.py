import json
from datetime import timedelta
from django.contrib.auth.models import User
from django.db.models import Count, Q, Sum, Avg
from django.shortcuts import render
from django.utils import timezone
from django.contrib.auth.decorators import login_required

from leads.models import Lead, CallLog
from agents.models import AgentProfile
from tenants.feature_gates import require_feature

@login_required
def reports_dashboard_view(request):
    """
    MVT View for rendering the full reports dashboard HTML template.
    Combines logic from various API endpoints into a single context.
    """
    today = timezone.now().date()
    
    # Parse date range
    days_param = request.GET.get('days')
    start_param = request.GET.get('start_date')
    end_param = request.GET.get('end_date')
    
    if start_param and end_param:
        try:
            from datetime import date
            start_date = date.fromisoformat(start_param)
            end_date = date.fromisoformat(end_param)
        except ValueError:
            start_date = today - timedelta(days=30)
            end_date = today
    elif days_param and days_param.isdigit():
        start_date = today - timedelta(days=int(days_param))
        end_date = today
    else:
        start_date = today - timedelta(days=30)
        end_date = today

    # Agents filter — scoped to this tenant only
    _tenant_agent_ids = AgentProfile.objects.values_list('user_id', flat=True)
    agents_qs = User.objects.filter(id__in=_tenant_agent_ids, is_active=True).order_by('first_name', 'username')
    selected_agent = request.GET.get('agent')
    if selected_agent and selected_agent.isdigit():
        target_agents = agents_qs.filter(id=int(selected_agent))
    else:
        target_agents = agents_qs

    # Base QuerySets
    leads_qs = Lead.objects.filter(assigned_agent__in=target_agents)
    calls_qs = CallLog.objects.filter(agent__in=target_agents)

    period_leads = leads_qs.filter(created_at__date__range=[start_date, end_date])
    period_calls = calls_qs.filter(call_date__date__range=[start_date, end_date])

    # ── KPI ──
    total_leads = leads_qs.count()
    converted_leads = leads_qs.filter(status='converted').count()
    
    pipeline_val = leads_qs.filter(status__in=['interested', 'callback']).aggregate(v=Sum('deal_value'))['v'] or 0
    won_val = leads_qs.filter(status='converted').aggregate(v=Sum('deal_value'))['v'] or 0
    
    period_calls_count = period_calls.count()
    days_count = max((end_date - start_date).days, 1)

    kpi = {
        'total_leads': total_leads,
        'period_new': period_leads.count(),
        'converted': converted_leads,
        'conversion_rate': round(converted_leads / total_leads * 100, 1) if total_leads else 0,
        'period_calls': period_calls_count,
        'avg_calls_per_day': round(period_calls_count / days_count, 1),
        'pipeline_value': float(pipeline_val),
        'won_value': float(won_val),
    }

    # ── FUNNEL ──
    funnel_stages_list = ['new', 'contacted', 'callback', 'interested', 'converted']
    funnel_colors = ['bg-blue', 'bg-orange', 'bg-yellow', 'bg-green', 'bg-teal'] # Generic classes, base.html uses custom classes
    color_map = {
        'new': 'crm-progress-blue',
        'contacted': 'crm-progress-orange',
        'callback': 'crm-progress-orange',
        'interested': 'crm-progress-green',
        'converted': 'crm-progress-green'
    }
    
    funnel_stages = []
    funnel_data = []
    
    total_period_leads = period_leads.count() or 1
    
    for stage_val in funnel_stages_list:
        count = period_leads.filter(status=stage_val).count()
        label = dict(Lead.STATUS_CHOICES).get(stage_val, stage_val)
        funnel_stages.append({
            'label': label,
            'count': count,
            'pct': round(count / total_period_leads * 100, 1),
            'color_class': color_map.get(stage_val, 'crm-progress-blue')
        })
        funnel_data.append({'stage': label, 'count': count})

    # ── SOURCE PERFORMANCE ──
    sources = period_leads.values('source').annotate(count=Count('id')).order_by('-count')
    source_data = [{'source': s['source'] or 'Unknown', 'count': s['count']} for s in sources]

    # ── LEADERBOARD ──
    leaderboard = []
    for ag in target_agents:
        ag_calls = period_calls.filter(agent=ag)
        ag_leads = leads_qs.filter(assigned_agent=ag)
        ag_total_leads = ag_leads.count()
        ag_conv = ag_leads.filter(status='converted').count()
        
        # Calculate avg duration manually
        calls_with_dur = ag_calls.exclude(duration__isnull=True)
        avg_dur_secs = 0
        if calls_with_dur.exists():
            total_secs = sum(c.duration.total_seconds() for c in calls_with_dur)
            avg_dur_secs = total_secs / calls_with_dur.count()
            
        avg_dur_str = f"{int(avg_dur_secs // 60)}m {int(avg_dur_secs % 60)}s" if avg_dur_secs > 0 else "—"

        leaderboard.append({
            'agent': ag,
            'total_calls': ag_calls.count(),
            'total_leads': ag_total_leads,
            'conversions': ag_conv,
            'conversion_rate': round(ag_conv / ag_total_leads * 100, 1) if ag_total_leads else 0,
            'avg_duration': avg_dur_str
        })
    leaderboard.sort(key=lambda x: (-x['conversions'], -x['total_calls']))

    # ── CALL ANALYTICS ──
    disps = period_calls.values('disposition').annotate(count=Count('id')).order_by('-count')
    total_calls_pd = period_calls_count or 1
    disposition_breakdown = []
    for d in disps:
        label = dict(CallLog.DISPOSITION_CHOICES).get(d['disposition'], d['disposition'])
        disposition_breakdown.append({
            'label': label,
            'count': d['count'],
            'pct': round(d['count'] / total_calls_pd * 100, 1)
        })

    # Hourly
    from django.db.models.functions import ExtractHour, ExtractWeekDay
    hourly = period_calls.annotate(hour=ExtractHour('call_date')).values('hour').annotate(count=Count('id')).order_by('hour')
    hourly_data = [{'hour': h['hour'], 'count': h['count']} for h in hourly if h['hour'] is not None]

    # Weekday
    weekday = period_calls.annotate(weekday=ExtractWeekDay('call_date')).values('weekday').annotate(count=Count('id')).order_by('weekday')
    day_names = {1: 'Sun', 2: 'Mon', 3: 'Tue', 4: 'Wed', 5: 'Thu', 6: 'Fri', 7: 'Sat'}
    weekday_data = [{'day_name': day_names.get(w['weekday'], ''), 'count': w['count']} for w in weekday if w['weekday'] is not None]

    # ── PIPELINE ──
    pipe_stages = ['new', 'contacted', 'callback', 'interested']
    pipeline_stages_json = []
    for s in pipe_stages:
        qs = leads_qs.filter(status=s)
        val = qs.aggregate(v=Sum('deal_value'))['v'] or 0
        pipeline_stages_json.append({
            'label': dict(Lead.STATUS_CHOICES).get(s, s),
            'value': float(val)
        })

    pipeline = {
        'active_value': float(pipeline_val),
        'won_value': float(won_val),
        'avg_deal': float(won_val / converted_leads) if converted_leads else 0
    }

    # ── TREND DATA ──
    trend_data = []
    current = start_date
    while current <= end_date:
        d_calls = period_calls.filter(call_date__date=current).count()
        d_leads = period_leads.filter(created_at__date=current).count()
        trend_data.append({
            'date': current.strftime('%b %d'),
            'calls': d_calls,
            'new_leads': d_leads
        })
        current += timedelta(days=1)

    context = {
        'start_date': start_date,
        'end_date': end_date,
        'agents': agents_qs,
        'selected_agent': str(selected_agent) if selected_agent else '',
        
        'kpi': kpi,
        'funnel_stages': funnel_stages,
        'leaderboard': leaderboard,
        'disposition_breakdown': disposition_breakdown,
        'pipeline': pipeline,
        
        'trend_data': json.dumps(trend_data),
        'funnel_data': json.dumps(funnel_data),
        'source_data': json.dumps(source_data),
        'hourly_data': json.dumps(hourly_data),
        'weekday_data': json.dumps(weekday_data),
        'pipeline_stages': json.dumps(pipeline_stages_json),
    }

    return render(request, 'reports/reports_dashboard.html', context)
