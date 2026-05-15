# reports/views.py
# ─────────────────────────────────────────────────────────────────────────────
# Phase 3 — Reports & Analytics API
# All endpoints return JSON consumed by Flutter and Django MVT dashboard.
# Feature-gated: basic_reports (always) | advanced_reports (plan feature)
# ─────────────────────────────────────────────────────────────────────────────

import csv
from datetime import timedelta
from django.contrib.auth.models import User
from agents.models import AgentProfile
from django.db.models import Count, Q, Sum, Avg, F, ExpressionWrapper, DurationField
from django.http import HttpResponse
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from leads.models import Lead, CallLog, FollowUp
from tenants.feature_gates import tenant_has_feature


def _date_range(request, default_days=30):
    """Parse ?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD from request."""
    today = timezone.now().date()
    try:
        from datetime import date
        start = date.fromisoformat(request.query_params.get('start_date', ''))
    except (ValueError, TypeError):
        start = today - timedelta(days=default_days)
    try:
        from datetime import date
        end = date.fromisoformat(request.query_params.get('end_date', ''))
    except (ValueError, TypeError):
        end = today
    return start, end


def _agent_filter(request):
    """Returns agent queryset — staff sees all, agents see only themselves."""
    if request.user.is_staff:
        agent_id = request.query_params.get('agent_id')
        if agent_id:
            return User.objects.filter(id=agent_id)
        return User.objects.filter(is_active=True, is_staff=False)
    return User.objects.filter(id=request.user.id)


# ═══════════════════════════════════════════════════════════════════════════════
# 1. DASHBOARD SUMMARY  (basic_reports)
# ═══════════════════════════════════════════════════════════════════════════════

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_summary(request):
    """
    GET /api/reports/dashboard/
    Returns the main KPI cards for both agent and admin dashboards.
    """
    today = timezone.now().date()
    start, end = _date_range(request, default_days=30)
    agents = _agent_filter(request)

    leads_qs = Lead.objects.filter(assigned_agent__in=agents)
    calls_qs = CallLog.objects.filter(agent__in=agents)

    # Period slices
    period_leads = leads_qs.filter(created_at__date__range=[start, end])
    period_calls = calls_qs.filter(call_date__date__range=[start, end])
    today_calls = calls_qs.filter(call_date__date=today).count()

    total_leads = leads_qs.count()
    converted = leads_qs.filter(status='converted').count()
    conversion_rate = round(converted / total_leads * 100, 2) if total_leads else 0

    # Deal pipeline value
    pipeline_value = leads_qs.filter(
        status__in=['interested', 'callback']
    ).aggregate(total=Sum('deal_value'))['total'] or 0

    won_value = leads_qs.filter(
        status='converted'
    ).aggregate(total=Sum('deal_value'))['total'] or 0

    return Response({
        'period': {'start': start, 'end': end},
        'leads': {
            'total': total_leads,
            'period_new': period_leads.count(),
            'converted': converted,
            'conversion_rate': conversion_rate,
            'by_status': list(
                leads_qs.values('status').annotate(count=Count('id')).order_by('-count')
            ),
        },
        'calls': {
            'today': today_calls,
            'period_total': period_calls.count(),
            'avg_per_day': round(
                period_calls.count() / max((end - start).days, 1), 1
            ),
        },
        'pipeline': {
            'active_value': float(pipeline_value),
            'won_value': float(won_value),
        },
        'follow_ups': {
            'due_today': FollowUp.objects.filter(
                agent__in=agents, follow_up_date=today, is_completed=False
            ).count(),
            'overdue': FollowUp.objects.filter(
                agent__in=agents, follow_up_date__lt=today, is_completed=False
            ).count(),
        },
    })


# ═══════════════════════════════════════════════════════════════════════════════
# 2. LEAD FUNNEL  (advanced_reports)
# ═══════════════════════════════════════════════════════════════════════════════

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def lead_funnel(request):
    """
    GET /api/reports/lead-funnel/
    Returns leads at each stage with conversion rates between stages.
    """
    if not tenant_has_feature(request, 'advanced_reports'):
        return Response({'error': 'advanced_reports feature required'}, status=403)

    start, end = _date_range(request)
    agents = _agent_filter(request)
    leads = Lead.objects.filter(assigned_agent__in=agents, created_at__date__range=[start, end])

    funnel_order = ['new', 'contacted', 'callback', 'interested', 'converted']
    stages = []
    for i, s in enumerate(funnel_order):
        count = leads.filter(status=s).count()
        prev_count = stages[i - 1]['count'] if i > 0 else count
        stages.append({
            'status': s,
            'label': dict(Lead.STATUS_CHOICES).get(s, s),
            'count': count,
            'drop_off_rate': round((1 - count / prev_count) * 100, 1) if prev_count else 0,
        })

    lost = leads.filter(status__in=['not_interested', 'wrong_number', 'not_reachable', 'lost']).count()

    return Response({
        'period': {'start': start, 'end': end},
        'funnel': stages,
        'lost': lost,
        'total_entered': leads.count(),
    })


# ═══════════════════════════════════════════════════════════════════════════════
# 3. AGENT LEADERBOARD  (advanced_reports)
# ═══════════════════════════════════════════════════════════════════════════════

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def agent_leaderboard(request):
    """
    GET /api/reports/agent-leaderboard/
    Ranks agents by calls, conversions, deal value won.
    """
    if not tenant_has_feature(request, 'advanced_reports'):
        return Response({'error': 'advanced_reports feature required'}, status=403)

    start, end = _date_range(request)

    _tenant_agent_ids = AgentProfile.objects.values_list('user_id', flat=True)
    agents = User.objects.filter(id__in=_tenant_agent_ids, is_active=True).annotate(
        period_calls=Count(
            'call_logs',
            filter=Q(call_logs__call_date__date__range=[start, end])
        ),
        period_conversions=Count(
            'assigned_leads',
            filter=Q(
                assigned_leads__status='converted',
                assigned_leads__updated_at__date__range=[start, end]
            )
        ),
        total_leads=Count('assigned_leads'),
        deal_value_won=Sum(
            'assigned_leads__deal_value',
            filter=Q(assigned_leads__status='converted')
        ),
    ).order_by('-period_conversions', '-period_calls')

    board = []
    for rank, agent in enumerate(agents, start=1):
        total = agent.total_leads
        conv = agent.period_conversions
        board.append({
            'rank': rank,
            'agent_id': agent.id,
            'name': agent.get_full_name() or agent.username,
            'period_calls': agent.period_calls,
            'period_conversions': conv,
            'conversion_rate': round(conv / total * 100, 1) if total else 0,
            'deal_value_won': float(agent.deal_value_won or 0),
        })

    return Response({'period': {'start': start, 'end': end}, 'leaderboard': board})


# ═══════════════════════════════════════════════════════════════════════════════
# 4. SOURCE PERFORMANCE  (advanced_reports)
# ═══════════════════════════════════════════════════════════════════════════════

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def source_performance(request):
    """GET /api/reports/source-performance/"""
    if not tenant_has_feature(request, 'advanced_reports'):
        return Response({'error': 'advanced_reports feature required'}, status=403)

    start, end = _date_range(request)
    leads = Lead.objects.filter(created_at__date__range=[start, end])

    sources = leads.values('source').annotate(
        total=Count('id'),
        converted=Count('id', filter=Q(status='converted')),
        deal_value=Sum('deal_value', filter=Q(status='converted')),
        avg_score=Avg('lead_score'),
    ).order_by('-total')

    data = []
    for s in sources:
        total = s['total']
        conv = s['converted']
        data.append({
            'source': s['source'] or 'Unknown',
            'total': total,
            'converted': conv,
            'conversion_rate': round(conv / total * 100, 1) if total else 0,
            'deal_value_won': float(s['deal_value'] or 0),
            'avg_lead_score': round(float(s['avg_score'] or 0), 1),
        })

    return Response({'period': {'start': start, 'end': end}, 'sources': data})


# ═══════════════════════════════════════════════════════════════════════════════
# 5. CALL ANALYTICS  (advanced_reports)
# ═══════════════════════════════════════════════════════════════════════════════

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def call_analytics(request):
    """GET /api/reports/call-analytics/"""
    if not tenant_has_feature(request, 'advanced_reports'):
        return Response({'error': 'advanced_reports feature required'}, status=403)

    start, end = _date_range(request)
    agents = _agent_filter(request)
    calls = CallLog.objects.filter(
        agent__in=agents,
        call_date__date__range=[start, end]
    )

    # Disposition breakdown
    dispositions = list(
        calls.values('disposition')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    for d in dispositions:
        d['label'] = dict(CallLog.DISPOSITION_CHOICES).get(d['disposition'], d['disposition'])

    # Calls by hour of day
    from django.db.models.functions import ExtractHour
    by_hour = list(
        calls.annotate(hour=ExtractHour('call_date'))
        .values('hour')
        .annotate(count=Count('id'))
        .order_by('hour')
    )

    # Calls by day of week
    from django.db.models.functions import ExtractWeekDay
    by_weekday = list(
        calls.annotate(weekday=ExtractWeekDay('call_date'))
        .values('weekday')
        .annotate(count=Count('id'))
        .order_by('weekday')
    )
    day_names = {1: 'Sun', 2: 'Mon', 3: 'Tue', 4: 'Wed', 5: 'Thu', 6: 'Fri', 7: 'Sat'}
    for d in by_weekday:
        d['day_name'] = day_names.get(d['weekday'], '')

    total = calls.count()
    with_recording = calls.exclude(recording='').exclude(recording__isnull=True).count()

    return Response({
        'period': {'start': start, 'end': end},
        'total_calls': total,
        'with_recording': with_recording,
        'recording_rate': round(with_recording / total * 100, 1) if total else 0,
        'dispositions': dispositions,
        'by_hour': by_hour,
        'by_weekday': by_weekday,
    })


# ═══════════════════════════════════════════════════════════════════════════════
# 6. REVENUE / DEAL PIPELINE  (advanced_reports)
# ═══════════════════════════════════════════════════════════════════════════════

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def deal_pipeline(request):
    """GET /api/reports/deal-pipeline/"""
    if not tenant_has_feature(request, 'advanced_reports'):
        return Response({'error': 'advanced_reports feature required'}, status=403)

    agents = _agent_filter(request)
    leads = Lead.objects.filter(assigned_agent__in=agents)

    pipeline_stages = ['new', 'contacted', 'callback', 'interested']
    pipeline = []
    for s in pipeline_stages:
        qs = leads.filter(status=s)
        pipeline.append({
            'stage': s,
            'label': dict(Lead.STATUS_CHOICES).get(s, s),
            'count': qs.count(),
            'total_value': float(qs.aggregate(v=Sum('deal_value'))['v'] or 0),
        })

    won = leads.filter(status='converted')
    lost = leads.filter(status__in=['not_interested', 'lost'])
    start, end = _date_range(request)

    return Response({
        'pipeline': pipeline,
        'won': {
            'count': won.count(),
            'total_value': float(won.aggregate(v=Sum('deal_value'))['v'] or 0),
        },
        'lost': {
            'count': lost.count(),
            'total_value': float(lost.aggregate(v=Sum('deal_value'))['v'] or 0),
        },
        'total_pipeline_value': float(
            leads.filter(status__in=pipeline_stages).aggregate(v=Sum('deal_value'))['v'] or 0
        ),
    })


# ═══════════════════════════════════════════════════════════════════════════════
# 7. DAILY TREND  (basic_reports — used by existing performance screen)
# ═══════════════════════════════════════════════════════════════════════════════

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def daily_trend(request):
    """
    GET /api/reports/daily-trend/
    Returns day-by-day calls and conversions for the period.
    Compatible with existing fl_chart bar chart in performance_screen.dart.
    """
    start, end = _date_range(request, default_days=14)
    agents = _agent_filter(request)

    days = []
    current = start
    while current <= end:
        calls = CallLog.objects.filter(
            agent__in=agents, call_date__date=current
        ).count()
        conversions = Lead.objects.filter(
            assigned_agent__in=agents,
            status='converted', updated_at__date=current
        ).count()
        days.append({
            'date': str(current),
            'date_display': current.strftime('%b %d'),
            'calls': calls,
            'conversions': conversions,
        })
        current += timedelta(days=1)

    return Response({'period': {'start': start, 'end': end}, 'daily': days})


# ═══════════════════════════════════════════════════════════════════════════════
# 8. CSV EXPORT  (advanced_reports)
# ═══════════════════════════════════════════════════════════════════════════════

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def export_leads_csv(request):
    """
    GET /api/reports/export/leads/?start_date=&end_date=&status=
    Downloads a CSV of leads for the given period.
    Staff only.
    """
    if not request.user.is_staff:
        return Response({'error': 'Staff only'}, status=403)
    if not tenant_has_feature(request, 'advanced_reports'):
        return Response({'error': 'advanced_reports feature required'}, status=403)

    start, end = _date_range(request)
    status_filter = request.query_params.get('status')

    qs = Lead.objects.filter(
        created_at__date__range=[start, end]
    ).select_related('assigned_agent').order_by('-created_at')
    if status_filter:
        qs = qs.filter(status=status_filter)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="leads_{start}_{end}.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'ID', 'Name', 'Phone', 'Email', 'Company', 'Status',
        'Source', 'Assigned Agent', 'Lead Score', 'Deal Value',
        'Created At', 'Updated At',
    ])
    for lead in qs.iterator():
        writer.writerow([
            lead.id, lead.name, lead.phone, lead.email or '',
            lead.company or '', lead.get_status_display(),
            lead.source or '', lead.assigned_agent.get_full_name() if lead.assigned_agent else '',
            lead.lead_score, lead.deal_value or '',
            lead.created_at.strftime('%Y-%m-%d %H:%M'),
            lead.updated_at.strftime('%Y-%m-%d %H:%M'),
        ])
    return response


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def export_calls_csv(request):
    """GET /api/reports/export/calls/"""
    if not request.user.is_staff:
        return Response({'error': 'Staff only'}, status=403)
    if not tenant_has_feature(request, 'advanced_reports'):
        return Response({'error': 'advanced_reports feature required'}, status=403)

    start, end = _date_range(request)
    qs = CallLog.objects.filter(
        call_date__date__range=[start, end]
    ).select_related('lead', 'agent').order_by('-call_date')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="calls_{start}_{end}.csv"'
    writer = csv.writer(response)
    writer.writerow(['ID', 'Lead Name', 'Phone', 'Agent', 'Date', 'Duration', 'Disposition', 'Remarks'])

    for call in qs.iterator():
        dur = ''
        if call.duration:
            secs = int(call.duration.total_seconds())
            dur = f'{secs // 60}:{secs % 60:02d}'
        writer.writerow([
            call.id, call.lead.name, call.lead.phone,
            call.agent.get_full_name() or call.agent.username,
            call.call_date.strftime('%Y-%m-%d %H:%M'),
            dur, call.get_disposition_display(), call.remarks or '',
        ])
    return response
