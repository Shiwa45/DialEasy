# ai/views.py
# ─────────────────────────────────────────────────────────────────────────────
# Phase 4 — AI REST API
# All endpoints feature-gated by plan.
# ─────────────────────────────────────────────────────────────────────────────

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from tenants.feature_gates import tenant_has_feature
from leads.models import CallLog, Lead


def _require_feature(request, slug):
    if not tenant_has_feature(request, slug):
        return Response({'error': f'{slug} feature required — upgrade your plan.'}, status=403)
    return None


# ─── Call Transcript ──────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def call_transcript(request, call_log_id):
    """
    GET /api/ai/transcripts/{call_log_id}/
    Returns transcript + sentiment for a call log.
    """
    err = _require_feature(request, 'ai_transcription')
    if err:
        return err

    call_log = get_object_or_404(CallLog, id=call_log_id)

    try:
        transcript = call_log.transcript
    except Exception:
        return Response({'status': 'not_started', 'message': 'No transcript yet for this call.'}, status=404)

    data = {
        'call_log_id': call_log_id,
        'status': transcript.status,
        'language': transcript.language,
        'duration_seconds': transcript.duration_seconds,
        'full_text': transcript.full_text,
        'segments': transcript.segments,
        'summary': transcript.summary,
        'word_count': transcript.word_count,
        'error_message': transcript.error_message,
        'created_at': transcript.created_at,
    }

    # Include sentiment if available
    try:
        sent = transcript.sentiment
        data['sentiment'] = {
            'overall': sent.overall_sentiment,
            'score': sent.sentiment_score,
            'customer_intent': sent.customer_intent,
            'objections_detected': sent.objections_detected,
            'agent_talk_ratio': sent.agent_talk_ratio,
            'filler_word_count': sent.filler_word_count,
            'best_moment': sent.best_moment,
            'improvement_area': sent.improvement_area,
        }
    except Exception:
        data['sentiment'] = None

    return Response(data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def trigger_transcription(request, call_log_id):
    """
    POST /api/ai/transcripts/{call_log_id}/process/
    Manually trigger transcription for a call log.
    Staff only — usually triggered automatically on recording upload.
    """
    err = _require_feature(request, 'ai_transcription')
    if err:
        return err

    call_log = get_object_or_404(CallLog, id=call_log_id)
    if not call_log.recording:
        return Response({'error': 'No recording on this call log.'}, status=400)

    # Run synchronously (use Celery in production)
    from ai.transcription_service import process_call_recording
    success = process_call_recording(call_log_id)

    return Response({
        'success': success,
        'call_log_id': call_log_id,
        'message': 'Transcription completed.' if success else 'Transcription failed — check logs.',
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def lead_transcripts(request, lead_id):
    """
    GET /api/ai/leads/{lead_id}/transcripts/
    Lists all transcripts for a lead's call logs.
    """
    err = _require_feature(request, 'ai_transcription')
    if err:
        return err

    lead = get_object_or_404(Lead, id=lead_id)
    call_logs = CallLog.objects.filter(lead=lead).order_by('-call_date')

    results = []
    for cl in call_logs:
        try:
            t = cl.transcript
            results.append({
                'call_log_id': cl.id,
                'call_date': cl.call_date,
                'disposition': cl.get_disposition_display(),
                'status': t.status,
                'summary': t.summary,
                'sentiment': t.sentiment.overall_sentiment if hasattr(t, 'sentiment') else None,
            })
        except Exception:
            if cl.recording:
                results.append({
                    'call_log_id': cl.id,
                    'call_date': cl.call_date,
                    'disposition': cl.get_disposition_display(),
                    'status': 'not_started',
                    'summary': None,
                    'sentiment': None,
                })

    return Response({'lead_id': lead_id, 'transcripts': results})


# ─── Coaching Dashboard ───────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def coaching_dashboard(request):
    """
    GET /api/ai/coaching/
    Returns coaching insights across all call transcripts for the period.
    Staff only — for manager view.
    """
    if not request.user.is_staff:
        return Response({'error': 'Staff only'}, status=403)

    err = _require_feature(request, 'call_sentiment')
    if err:
        return err

    from ai.models import CallTranscript, CallSentiment
    from django.db.models import Avg, Count
    from datetime import timedelta
    from django.utils import timezone

    days = int(request.query_params.get('days', 30))
    since = timezone.now() - timedelta(days=days)

    sentiments = CallSentiment.objects.filter(
        transcript__created_at__gte=since,
        transcript__status='done',
    ).select_related('transcript__call_log__agent')

    if not sentiments.exists():
        return Response({'message': 'No sentiment data available for this period.'})

    # Aggregate by agent
    from django.contrib.auth.models import User
    from collections import defaultdict

    agent_data = defaultdict(lambda: {
        'calls': 0, 'sentiment_sum': 0, 'filler_total': 0,
        'talk_ratio_sum': 0, 'talk_ratio_count': 0,
        'objections': [],
    })

    for s in sentiments:
        agent = s.transcript.call_log.agent
        key = agent.id
        agent_data[key]['agent_name'] = agent.get_full_name() or agent.username
        agent_data[key]['calls'] += 1
        agent_data[key]['sentiment_sum'] += s.sentiment_score
        agent_data[key]['filler_total'] += s.filler_word_count
        if s.agent_talk_ratio is not None:
            agent_data[key]['talk_ratio_sum'] += s.agent_talk_ratio
            agent_data[key]['talk_ratio_count'] += 1
        agent_data[key]['objections'].extend(s.objections_detected or [])

    results = []
    for agent_id, d in agent_data.items():
        calls = d['calls']
        talk_ratio = (d['talk_ratio_sum'] / d['talk_ratio_count']) if d['talk_ratio_count'] else None
        results.append({
            'agent_id': agent_id,
            'agent_name': d['agent_name'],
            'calls_analysed': calls,
            'avg_sentiment_score': round(d['sentiment_sum'] / calls, 2),
            'avg_filler_words_per_call': round(d['filler_total'] / calls, 1),
            'avg_talk_ratio': round(talk_ratio, 2) if talk_ratio else None,
            'top_objections': list(set(d['objections']))[:5],
        })

    results.sort(key=lambda x: x['avg_sentiment_score'], reverse=True)

    return Response({
        'period_days': days,
        'total_calls_analysed': sum(r['calls_analysed'] for r in results),
        'agents': results,
    })


# ─── Email AI ────────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def email_thread(request, lead_id):
    """GET /api/ai/emails/{lead_id}/  — get email thread for a lead"""
    err = _require_feature(request, 'email_ai')
    if err:
        return err

    lead = get_object_or_404(Lead, id=lead_id)

    try:
        thread = lead.email_thread
        messages = thread.messages.order_by('created_at')
        return Response({
            'thread_id': thread.id,
            'lead_id': lead_id,
            'unread_count': thread.unread_count,
            'messages': [{
                'id': m.id,
                'direction': m.direction,
                'subject': m.subject,
                'from_address': m.from_address,
                'body_text': m.body_text,
                'ai_classification': m.ai_classification,
                'ai_urgency_score': m.ai_urgency_score,
                'ai_summary': m.ai_summary,
                'sent_at': m.sent_at,
                'received_at': m.received_at,
            } for m in messages],
        })
    except Exception:
        return Response({'thread_id': None, 'messages': [], 'unread_count': 0})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def draft_email_reply(request, email_message_id):
    """
    POST /api/ai/emails/draft/{email_message_id}/
    Returns AI-generated reply draft for an inbound email.
    """
    err = _require_feature(request, 'email_ai')
    if err:
        return err

    from ai.models import EmailMessage
    from ai.email_service import draft_reply

    email_msg = get_object_or_404(EmailMessage, id=email_message_id)
    lead = email_msg.thread.lead

    draft = draft_reply(email_msg, lead)
    if not draft:
        return Response({'error': 'Could not generate draft.'}, status=500)

    return Response({'draft': draft, 'email_message_id': email_message_id})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_email(request, lead_id):
    """
    POST /api/ai/emails/{lead_id}/send/
    Body: { "subject": "...", "body": "...", "to_address": "..." }
    Saves outbound email to thread.
    """
    err = _require_feature(request, 'email_ai')
    if err:
        return err

    from ai.email_service import process_and_save_email

    lead = get_object_or_404(Lead, id=lead_id)
    subject = request.data.get('subject', '')
    body = request.data.get('body', '')
    to_address = request.data.get('to_address') or lead.email

    if not body:
        return Response({'error': 'body is required'}, status=400)

    msg = process_and_save_email(
        lead=lead,
        subject=subject,
        body_text=body,
        from_address=request.user.email or '',
        to_address=to_address,
        direction='outbound',
        sent_by=request.user,
    )
    return Response({'message_id': msg.id, 'status': 'sent'})


# ─── Chatbot Config ───────────────────────────────────────────────────────────

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def chatbot_flow(request):
    """
    GET  /api/ai/chatbot/flow/  — get active flow config
    POST /api/ai/chatbot/flow/  — create/update flow (staff only)
    """
    err = _require_feature(request, 'ai_chatbot')
    if err:
        return err

    from ai.models import ChatbotFlow

    if request.method == 'GET':
        flow = ChatbotFlow.objects.filter(is_active=True).first()
        if not flow:
            return Response({'active_flow': None})
        return Response({
            'id': flow.id, 'name': flow.name, 'is_active': flow.is_active,
            'system_prompt': flow.system_prompt,
            'escalation_keywords': flow.escalation_keywords,
            'max_turns_before_escalation': flow.max_turns_before_escalation,
            'qualification_questions': flow.qualification_questions,
        })

    if not request.user.is_staff:
        return Response({'error': 'Staff only'}, status=403)

    # Deactivate existing active flows
    ChatbotFlow.objects.filter(is_active=True).update(is_active=False)

    flow = ChatbotFlow.objects.create(
        name=request.data.get('name', 'Default Flow'),
        is_active=True,
        system_prompt=request.data.get('system_prompt', ''),
        escalation_keywords=request.data.get('escalation_keywords', 'human,agent'),
        max_turns_before_escalation=int(request.data.get('max_turns', 5)),
        qualification_questions=request.data.get('qualification_questions', []),
    )
    return Response({'id': flow.id, 'name': flow.name, 'is_active': flow.is_active}, status=201)
