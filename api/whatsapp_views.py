# api/whatsapp_views.py
# ─────────────────────────────────────────────────────────────────────────────
# Phase 2 — REST API for WhatsApp features consumed by Flutter + Django admin
# ─────────────────────────────────────────────────────────────────────────────

from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q

from leads.models import Lead
from leads.whatsapp_models import (
    WAConversation, WAMessage, WATemplate, WABroadcast, WABroadcastRecipient, WAAutoReply
)
from leads.whatsapp_service_v2 import send_and_log, send_template_and_log
from tenants.feature_gates import FeatureRequiredMixin


# ─── Serializer-less helpers ──────────────────────────────────────────────────

def _serialize_message(msg: WAMessage) -> dict:
    return {
        'id': msg.id,
        'wa_message_id': msg.wa_message_id,
        'direction': msg.direction,
        'message_type': msg.message_type,
        'status': msg.status,
        'body': msg.body,
        'media_url': msg.media_url,
        'media_mime_type': msg.media_mime_type,
        'media_filename': msg.media_filename,
        'caption': msg.caption,
        'template_id': msg.template_id,
        'sent_by': {'id': msg.sent_by.id, 'name': msg.sent_by.get_full_name()} if msg.sent_by else None,
        'sent_at': msg.sent_at,
        'delivered_at': msg.delivered_at,
        'read_at': msg.read_at,
        'created_at': msg.created_at,
    }


def _serialize_conversation(conv: WAConversation, include_messages: bool = False) -> dict:
    data = {
        'id': conv.id,
        'lead': {
            'id': conv.lead.id,
            'name': conv.lead.name,
            'phone': conv.lead.phone,
            'company': conv.lead.company,
            'status': conv.lead.status,
        },
        'status': conv.status,
        'is_opted_out': conv.is_opted_out,
        'unread_count': conv.unread_count,
        'last_message_at': conv.last_message_at,
        'assigned_agent': {
            'id': conv.assigned_agent.id,
            'name': conv.assigned_agent.get_full_name(),
        } if conv.assigned_agent else None,
    }
    if include_messages:
        msgs = conv.messages.order_by('created_at')
        data['messages'] = [_serialize_message(m) for m in msgs]
    else:
        last = conv.messages.order_by('-created_at').first()
        data['last_message'] = _serialize_message(last) if last else None
    return data


def _serialize_template(tmpl: WATemplate) -> dict:
    return {
        'id': tmpl.id,
        'name': tmpl.name,
        'display_name': tmpl.display_name,
        'category': tmpl.category,
        'language_code': tmpl.language_code,
        'status': tmpl.status,
        'body_text': tmpl.body_text,
        'header_text': tmpl.header_text,
        'footer_text': tmpl.footer_text,
        'buttons': tmpl.buttons,
        'is_active': tmpl.is_active,
    }


# ─── Conversation endpoints ───────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def conversation_list(request):
    """
    GET /api/whatsapp/conversations/
    Lists all WA conversations for the agent (or all for staff).
    Query params: ?status=open&search=name&unread_only=true
    """
    if request.user.is_staff:
        qs = WAConversation.objects.all()
    else:
        qs = WAConversation.objects.filter(
            Q(assigned_agent=request.user) | Q(lead__assigned_agent=request.user)
        )

    # Filters
    status_f = request.query_params.get('status')
    if status_f:
        qs = qs.filter(status=status_f)

    search = request.query_params.get('search')
    if search:
        qs = qs.filter(
            Q(lead__name__icontains=search) |
            Q(lead__phone__icontains=search) |
            Q(lead__company__icontains=search)
        )

    if request.query_params.get('unread_only') == 'true':
        qs = qs.filter(unread_count__gt=0)

    qs = qs.select_related('lead', 'assigned_agent').order_by('-last_message_at')[:50]

    return Response([_serialize_conversation(c) for c in qs])


@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated])
def conversation_detail(request, lead_id):
    """
    GET   /api/whatsapp/conversations/{lead_id}/  — get full conversation with messages
    PATCH /api/whatsapp/conversations/{lead_id}/  — update status or assignment
    """
    lead = get_object_or_404(Lead, id=lead_id)

    try:
        conv = WAConversation.objects.select_related('lead', 'assigned_agent').get(lead=lead)
    except WAConversation.DoesNotExist:
        # Create empty conversation if none exists
        conv = WAConversation.objects.create(lead=lead, status='open')

    if request.method == 'GET':
        conv.mark_read()
        return Response(_serialize_conversation(conv, include_messages=True))

    if request.method == 'PATCH':
        new_status = request.data.get('status')
        if new_status in dict(WAConversation.STATUS_CHOICES):
            conv.status = new_status
            conv.save(update_fields=['status'])
        return Response(_serialize_conversation(conv))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def conversation_messages(request, lead_id):
    """
    GET /api/whatsapp/conversations/{lead_id}/messages/
    Paginated message list. ?limit=50&before_id=123
    """
    lead = get_object_or_404(Lead, id=lead_id)
    try:
        conv = WAConversation.objects.get(lead=lead)
    except WAConversation.DoesNotExist:
        return Response({'messages': [], 'has_more': False})

    limit = int(request.query_params.get('limit', 50))
    before_id = request.query_params.get('before_id')

    qs = conv.messages.order_by('-created_at')
    if before_id:
        qs = qs.filter(id__lt=before_id)

    msgs = list(qs[:limit + 1])
    has_more = len(msgs) > limit
    msgs = msgs[:limit]
    msgs.reverse()  # Chronological order for display

    conv.mark_read()

    return Response({
        'messages': [_serialize_message(m) for m in msgs],
        'has_more': has_more,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_message(request, lead_id):
    """
    POST /api/whatsapp/conversations/{lead_id}/send/
    Body: { "message": "Hello!", "template_id": null }
    """
    lead = get_object_or_404(Lead, id=lead_id)
    message_text = request.data.get('message', '').strip()
    template_id = request.data.get('template_id')

    if template_id:
        try:
            tmpl = WATemplate.objects.get(id=template_id, is_active=True, status='approved')
        except WATemplate.DoesNotExist:
            return Response({'error': 'Template not found or not approved'}, status=status.HTTP_404_NOT_FOUND)
        wa_msg = send_template_and_log(lead=lead, wa_template=tmpl, sent_by=request.user)
    elif message_text:
        wa_msg = send_and_log(lead=lead, body=message_text, sent_by=request.user)
    else:
        return Response({'error': 'message or template_id required'}, status=status.HTTP_400_BAD_REQUEST)

    if wa_msg is None:
        return Response({'error': 'Send failed (opted out or config missing)'}, status=status.HTTP_400_BAD_REQUEST)

    return Response(_serialize_message(wa_msg), status=status.HTTP_201_CREATED)


# ─── Template endpoints ───────────────────────────────────────────────────────

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def template_list(request):
    """
    GET  /api/whatsapp/templates/  — list all active approved templates
    POST /api/whatsapp/templates/  — create new template (staff only)
    """
    if request.method == 'GET':
        templates = WATemplate.objects.filter(is_active=True).order_by('display_name')
        return Response([_serialize_template(t) for t in templates])

    if not request.user.is_staff:
        return Response({'error': 'Staff only'}, status=status.HTTP_403_FORBIDDEN)

    data = request.data
    tmpl = WATemplate.objects.create(
        name=data.get('name', ''),
        display_name=data.get('display_name', ''),
        category=data.get('category', 'utility'),
        language_code=data.get('language_code', 'en_US'),
        body_text=data.get('body_text', ''),
        header_text=data.get('header_text'),
        footer_text=data.get('footer_text'),
        variable_mapping=data.get('variable_mapping', {}),
        buttons=data.get('buttons', []),
        status='pending',
        created_by=request.user,
    )
    return Response(_serialize_template(tmpl), status=status.HTTP_201_CREATED)


@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def template_detail(request, template_id):
    """
    GET    /api/whatsapp/templates/{id}/
    PATCH  /api/whatsapp/templates/{id}/
    DELETE /api/whatsapp/templates/{id}/
    """
    tmpl = get_object_or_404(WATemplate, id=template_id)

    if request.method == 'GET':
        return Response(_serialize_template(tmpl))

    if not request.user.is_staff:
        return Response({'error': 'Staff only'}, status=status.HTTP_403_FORBIDDEN)

    if request.method == 'PATCH':
        for field in ('display_name', 'body_text', 'header_text', 'footer_text',
                      'variable_mapping', 'buttons', 'is_active'):
            if field in request.data:
                setattr(tmpl, field, request.data[field])
        tmpl.save()
        return Response(_serialize_template(tmpl))

    if request.method == 'DELETE':
        tmpl.is_active = False
        tmpl.save(update_fields=['is_active'])
        return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def template_preview(request, template_id):
    """
    POST /api/whatsapp/templates/{id}/preview/
    Body: { "lead_id": 5 }
    Returns rendered template body for the given lead.
    """
    tmpl = get_object_or_404(WATemplate, id=template_id)
    lead_id = request.data.get('lead_id')
    lead = get_object_or_404(Lead, id=lead_id) if lead_id else None

    rendered = tmpl.render_body(lead, request.user) if lead else tmpl.body_text
    return Response({'rendered_body': rendered, 'components': tmpl.build_components(lead, request.user) if lead else []})


# ─── Broadcast endpoints ─────────────────────────────────────────────────────

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def broadcast_list(request):
    """
    GET  /api/whatsapp/broadcasts/  — list broadcasts (staff only)
    POST /api/whatsapp/broadcasts/  — create & queue a broadcast
    """
    if not request.user.is_staff:
        return Response({'error': 'Staff only'}, status=status.HTTP_403_FORBIDDEN)

    if request.method == 'GET':
        broadcasts = WABroadcast.objects.select_related('template', 'created_by').order_by('-created_at')[:50]
        return Response([{
            'id': b.id, 'name': b.name, 'status': b.status,
            'template': b.template.display_name,
            'total_leads': b.total_leads, 'sent_count': b.sent_count,
            'delivered_count': b.delivered_count, 'failed_count': b.failed_count,
            'created_at': b.created_at, 'scheduled_at': b.scheduled_at,
        } for b in broadcasts])

    # Create broadcast
    data = request.data
    template_id = data.get('template_id')
    lead_filter = data.get('lead_filter', {})

    try:
        template = WATemplate.objects.get(id=template_id, is_active=True, status='approved')
    except WATemplate.DoesNotExist:
        return Response({'error': 'Template not found or not approved'}, status=status.HTTP_400_BAD_REQUEST)

    # Evaluate lead count
    lead_qs = Lead.objects.all()
    if lead_filter.get('status'):
        lead_qs = lead_qs.filter(status=lead_filter['status'])
    if lead_filter.get('source'):
        lead_qs = lead_qs.filter(source__icontains=lead_filter['source'])
    if lead_filter.get('assigned_agent_id'):
        lead_qs = lead_qs.filter(assigned_agent_id=lead_filter['assigned_agent_id'])

    # Exclude opted-out leads
    opted_out_ids = WAConversation.objects.filter(is_opted_out=True).values_list('lead_id', flat=True)
    lead_qs = lead_qs.exclude(id__in=opted_out_ids)
    total = lead_qs.count()

    broadcast = WABroadcast.objects.create(
        name=data.get('name', f'Broadcast {timezone.now().strftime("%Y-%m-%d")}'),
        template=template,
        lead_filter=lead_filter,
        total_leads=total,
        status='queued',
        scheduled_at=data.get('scheduled_at') or timezone.now(),
        created_by=request.user,
    )

    # Create recipient records
    WABroadcastRecipient.objects.bulk_create([
        WABroadcastRecipient(broadcast=broadcast, lead=lead)
        for lead in lead_qs.iterator()
    ], batch_size=500)

    # TODO: enqueue Celery task: process_broadcast.delay(broadcast.id)
    # For now, mark as queued so it can be processed by the management command

    return Response({
        'id': broadcast.id, 'name': broadcast.name,
        'status': broadcast.status, 'total_leads': total,
        'message': f'Broadcast queued for {total} leads.'
    }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def broadcast_pause(request, broadcast_id):
    """POST /api/whatsapp/broadcasts/{id}/pause/"""
    if not request.user.is_staff:
        return Response({'error': 'Staff only'}, status=status.HTTP_403_FORBIDDEN)
    broadcast = get_object_or_404(WABroadcast, id=broadcast_id)
    broadcast.status = 'paused'
    broadcast.save(update_fields=['status'])
    return Response({'status': 'paused'})
