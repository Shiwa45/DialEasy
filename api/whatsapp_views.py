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
    WAConversation, WAMessage, WATemplate, WABroadcast, WABroadcastRecipient, WAAutoReply, WAProvider
)
from leads.whatsapp_service_v2 import send_and_log, send_template_and_log
from leads.whatsapp_providers import get_provider, get_default_provider, PROVIDER_CHOICES
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


# ─── Provider helpers ─────────────────────────────────────────────────────────

def _serialize_provider(p: WAProvider) -> dict:
    return {
        'id': p.id,
        'name': p.name,
        'provider': p.provider,
        'provider_display': p.get_provider_display(),
        'is_active': p.is_active,
        'is_default': p.is_default,
        # Return masked credentials for display only
        'meta_phone_number_id': p.meta_phone_number_id,
        'twilio_account_sid': p.twilio_account_sid,
        'twilio_from_number': p.twilio_from_number,
        'wati_api_endpoint': p.wati_api_endpoint,
        'created_at': p.created_at,
    }


# ─── Provider endpoints ───────────────────────────────────────────────────────

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def provider_list(request):
    """
    GET  /api/whatsapp/providers/  — list configured providers (staff)
    POST /api/whatsapp/providers/  — add a new provider (staff)
    """
    if not request.user.is_staff:
        return Response({'error': 'Staff only'}, status=status.HTTP_403_FORBIDDEN)

    if request.method == 'GET':
        providers = WAProvider.objects.all()
        return Response([_serialize_provider(p) for p in providers])

    d = request.data
    provider = WAProvider(
        name=d.get('name', ''),
        provider=d.get('provider', ''),
        is_active=d.get('is_active', True),
        is_default=d.get('is_default', False),
        meta_phone_number_id=d.get('meta_phone_number_id', ''),
        meta_access_token=d.get('meta_access_token', ''),
        meta_verify_token=d.get('meta_verify_token', ''),
        twilio_account_sid=d.get('twilio_account_sid', ''),
        twilio_auth_token=d.get('twilio_auth_token', ''),
        twilio_from_number=d.get('twilio_from_number', ''),
        wati_api_endpoint=d.get('wati_api_endpoint', ''),
        wati_api_key=d.get('wati_api_key', ''),
        aisensy_api_key=d.get('aisensy_api_key', ''),
        interakt_api_key=d.get('interakt_api_key', ''),
        created_by=request.user,
    )
    if not provider.name or not provider.provider:
        return Response({'error': 'name and provider are required'}, status=status.HTTP_400_BAD_REQUEST)
    provider.save()
    return Response(_serialize_provider(provider), status=status.HTTP_201_CREATED)


@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def provider_detail(request, provider_id):
    """GET/PATCH/DELETE /api/whatsapp/providers/{id}/"""
    if not request.user.is_staff:
        return Response({'error': 'Staff only'}, status=status.HTTP_403_FORBIDDEN)
    p = get_object_or_404(WAProvider, id=provider_id)

    if request.method == 'GET':
        return Response(_serialize_provider(p))

    if request.method == 'PATCH':
        allowed = [
            'name', 'is_active', 'is_default',
            'meta_phone_number_id', 'meta_access_token', 'meta_verify_token',
            'twilio_account_sid', 'twilio_auth_token', 'twilio_from_number',
            'wati_api_endpoint', 'wati_api_key',
            'aisensy_api_key', 'interakt_api_key',
        ]
        for field in allowed:
            if field in request.data:
                setattr(p, field, request.data[field])
        p.save()
        return Response(_serialize_provider(p))

    # DELETE
    p.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def provider_test(request, provider_id):
    """POST /api/whatsapp/providers/{id}/test/ — test connectivity"""
    if not request.user.is_staff:
        return Response({'error': 'Staff only'}, status=status.HTTP_403_FORBIDDEN)
    p = get_object_or_404(WAProvider, id=provider_id)
    try:
        impl = get_provider(p)
        ok, message = impl.test_connection()
        return Response({'ok': ok, 'message': message})
    except Exception as e:
        return Response({'ok': False, 'message': str(e)})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def provider_choices(request):
    """GET /api/whatsapp/provider-choices/ — list available provider types"""
    return Response([{'value': v, 'label': l} for v, l in PROVIDER_CHOICES])


# ─── Broadcast / Campaign helpers ─────────────────────────────────────────────

def _build_lead_qs(lead_filter: dict):
    qs = Lead.objects.all()
    if lead_filter.get('status'):
        qs = qs.filter(status=lead_filter['status'])
    if lead_filter.get('source'):
        qs = qs.filter(source__icontains=lead_filter['source'])
    if lead_filter.get('assigned_agent_id'):
        qs = qs.filter(assigned_agent_id=lead_filter['assigned_agent_id'])
    if lead_filter.get('tags'):
        qs = qs.filter(tags__icontains=lead_filter['tags'])
    # Exclude opted-out leads
    opted_out = WAConversation.objects.filter(is_opted_out=True).values_list('lead_id', flat=True)
    return qs.exclude(id__in=opted_out)


def _serialize_broadcast(b: WABroadcast) -> dict:
    return {
        'id': b.id,
        'name': b.name,
        'description': b.description,
        'status': b.status,
        'status_display': b.get_status_display(),
        'message_type': b.message_type,
        'template': {'id': b.template.id, 'name': b.template.display_name} if b.template else None,
        'text_body': b.text_body,
        'provider': {'id': b.provider.id, 'name': b.provider.name, 'provider': b.provider.provider} if b.provider else None,
        'lead_filter': b.lead_filter,
        'total_leads': b.total_leads,
        'sent_count': b.sent_count,
        'delivered_count': b.delivered_count,
        'read_count': b.read_count,
        'replied_count': b.replied_count,
        'failed_count': b.failed_count,
        'opted_out_skipped': b.opted_out_skipped,
        'delivery_rate': b.delivery_rate,
        'read_rate': b.read_rate,
        'scheduled_at': b.scheduled_at,
        'started_at': b.started_at,
        'completed_at': b.completed_at,
        'created_by': b.created_by.get_full_name() if b.created_by else None,
        'created_at': b.created_at,
    }


# ─── Broadcast endpoints ─────────────────────────────────────────────────────

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def broadcast_list(request):
    """
    GET  /api/whatsapp/broadcasts/  — list campaigns (staff only)
    POST /api/whatsapp/broadcasts/  — create & queue a campaign
    """
    if not request.user.is_staff:
        return Response({'error': 'Staff only'}, status=status.HTTP_403_FORBIDDEN)

    if request.method == 'GET':
        qs = WABroadcast.objects.select_related('template', 'provider', 'created_by').order_by('-created_at')
        # Filter by status
        status_f = request.query_params.get('status')
        if status_f:
            qs = qs.filter(status=status_f)
        return Response([_serialize_broadcast(b) for b in qs[:100]])

    # ─── Create campaign ─────────────────────────────────────────────
    data = request.data
    message_type = data.get('message_type', 'template')
    lead_filter = data.get('lead_filter', {})

    template = None
    text_body = ''

    if message_type == 'template':
        template_id = data.get('template_id')
        if not template_id:
            return Response({'error': 'template_id required for template campaigns'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            template = WATemplate.objects.get(id=template_id, is_active=True, status='approved')
        except WATemplate.DoesNotExist:
            return Response({'error': 'Template not found or not approved'}, status=status.HTTP_400_BAD_REQUEST)
    else:
        text_body = data.get('text_body', '').strip()
        if not text_body:
            return Response({'error': 'text_body required for text campaigns'}, status=status.HTTP_400_BAD_REQUEST)

    # Resolve provider
    provider = None
    provider_id = data.get('provider_id')
    if provider_id:
        provider = get_object_or_404(WAProvider, id=provider_id, is_active=True)
    else:
        provider = WAProvider.objects.filter(is_active=True, is_default=True).first() \
            or WAProvider.objects.filter(is_active=True).first()

    lead_qs = _build_lead_qs(lead_filter)
    total = lead_qs.count()

    if total == 0:
        return Response({'error': 'No eligible leads match the selected filter (all opted out or none found)'}, status=status.HTTP_400_BAD_REQUEST)

    scheduled_at = data.get('scheduled_at')
    broadcast = WABroadcast.objects.create(
        name=data.get('name', f'Campaign {timezone.now().strftime("%Y-%m-%d")}'),
        description=data.get('description', ''),
        message_type=message_type,
        template=template,
        text_body=text_body,
        provider=provider,
        lead_filter=lead_filter,
        total_leads=total,
        status='queued' if not scheduled_at else 'draft',
        scheduled_at=scheduled_at or timezone.now(),
        created_by=request.user,
    )

    WABroadcastRecipient.objects.bulk_create(
        [WABroadcastRecipient(broadcast=broadcast, lead=lead) for lead in lead_qs.iterator()],
        batch_size=500,
    )

    return Response({
        **_serialize_broadcast(broadcast),
        'message': f'Campaign created for {total} leads. Run "process_broadcasts" to send.',
    }, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def broadcast_detail(request, broadcast_id):
    """GET /api/whatsapp/broadcasts/{id}/"""
    if not request.user.is_staff:
        return Response({'error': 'Staff only'}, status=status.HTTP_403_FORBIDDEN)
    b = get_object_or_404(WABroadcast, id=broadcast_id)
    return Response(_serialize_broadcast(b))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def broadcast_pause(request, broadcast_id):
    """POST /api/whatsapp/broadcasts/{id}/pause/"""
    if not request.user.is_staff:
        return Response({'error': 'Staff only'}, status=status.HTTP_403_FORBIDDEN)
    b = get_object_or_404(WABroadcast, id=broadcast_id)
    if b.status not in ('queued', 'running'):
        return Response({'error': f'Cannot pause a campaign with status "{b.status}"'}, status=status.HTTP_400_BAD_REQUEST)
    b.status = 'paused'
    b.save(update_fields=['status'])
    return Response(_serialize_broadcast(b))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def broadcast_resume(request, broadcast_id):
    """POST /api/whatsapp/broadcasts/{id}/resume/"""
    if not request.user.is_staff:
        return Response({'error': 'Staff only'}, status=status.HTTP_403_FORBIDDEN)
    b = get_object_or_404(WABroadcast, id=broadcast_id)
    if b.status != 'paused':
        return Response({'error': 'Only paused campaigns can be resumed'}, status=status.HTTP_400_BAD_REQUEST)
    b.status = 'queued'
    b.save(update_fields=['status'])
    return Response(_serialize_broadcast(b))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def broadcast_cancel(request, broadcast_id):
    """POST /api/whatsapp/broadcasts/{id}/cancel/"""
    if not request.user.is_staff:
        return Response({'error': 'Staff only'}, status=status.HTTP_403_FORBIDDEN)
    b = get_object_or_404(WABroadcast, id=broadcast_id)
    if b.status in ('completed', 'cancelled'):
        return Response({'error': f'Campaign is already {b.status}'}, status=status.HTTP_400_BAD_REQUEST)
    b.status = 'cancelled'
    b.save(update_fields=['status'])
    return Response(_serialize_broadcast(b))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def broadcast_recipients(request, broadcast_id):
    """GET /api/whatsapp/broadcasts/{id}/recipients/ — paginated recipient list"""
    if not request.user.is_staff:
        return Response({'error': 'Staff only'}, status=status.HTTP_403_FORBIDDEN)
    b = get_object_or_404(WABroadcast, id=broadcast_id)

    qs = b.recipients.select_related('lead').order_by('id')
    status_f = request.query_params.get('status')
    if status_f:
        qs = qs.filter(status=status_f)

    page_size = min(int(request.query_params.get('page_size', 50)), 200)
    offset = int(request.query_params.get('offset', 0))
    total = qs.count()
    recipients = qs[offset:offset + page_size]

    return Response({
        'count': total,
        'offset': offset,
        'page_size': page_size,
        'results': [{
            'id': r.id,
            'lead': {'id': r.lead.id, 'name': r.lead.name, 'phone': r.lead.phone},
            'status': r.status,
            'wa_message_id': r.wa_message_id,
            'error_message': r.error_message,
            'sent_at': r.sent_at,
        } for r in recipients],
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def broadcast_estimate(request):
    """
    GET /api/whatsapp/broadcasts/estimate/?status=interested&source=Meta
    Returns estimated recipient count for a given filter (before creating campaign).
    """
    if not request.user.is_staff:
        return Response({'error': 'Staff only'}, status=status.HTTP_403_FORBIDDEN)
    lead_filter = {
        'status': request.query_params.get('status'),
        'source': request.query_params.get('source'),
        'assigned_agent_id': request.query_params.get('assigned_agent_id'),
    }
    lead_filter = {k: v for k, v in lead_filter.items() if v}
    count = _build_lead_qs(lead_filter).count()
    return Response({'estimated_recipients': count, 'filter': lead_filter})
