# notifications/views.py
# ─────────────────────────────────────────────────────────────────────────────
# REST API endpoints for the Flutter notification centre.
# ─────────────────────────────────────────────────────────────────────────────

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from .models import Notification, FCMToken


def _serialize_notification(n: Notification) -> dict:
    return {
        'id': n.id,
        'type': n.notification_type,
        'type_display': n.get_notification_type_display(),
        'title': n.title,
        'body': n.body,
        'is_read': n.is_read,
        'read_at': n.read_at,
        'action_data': n.action_data,
        'related_lead_id': n.related_lead_id,
        'created_at': n.created_at,
    }


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def notification_list(request):
    """
    GET /api/notifications/
    Query params:
      ?unread_only=true
      ?limit=30
      ?offset=0
    Returns notifications for the current user.
    """
    qs = Notification.objects.filter(recipient=request.user)

    if request.query_params.get('unread_only') == 'true':
        qs = qs.filter(is_read=False)

    limit = int(request.query_params.get('limit', 30))
    offset = int(request.query_params.get('offset', 0))
    total = qs.count()
    unread_count = Notification.objects.filter(recipient=request.user, is_read=False).count()
    notifications = qs[offset: offset + limit]

    return Response({
        'count': total,
        'unread_count': unread_count,
        'results': [_serialize_notification(n) for n in notifications],
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_read(request, notification_id):
    """POST /api/notifications/{id}/read/"""
    try:
        notif = Notification.objects.get(id=notification_id, recipient=request.user)
        notif.mark_read()
        return Response({'success': True})
    except Notification.DoesNotExist:
        return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_all_read(request):
    """POST /api/notifications/mark-all-read/"""
    count = Notification.objects.filter(
        recipient=request.user, is_read=False
    ).update(is_read=True, read_at=timezone.now())
    return Response({'marked_read': count})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def unread_count(request):
    """GET /api/notifications/unread-count/  — lightweight poll for badge"""
    count = Notification.objects.filter(recipient=request.user, is_read=False).count()
    return Response({'unread_count': count})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def register_fcm_token(request):
    """
    POST /api/notifications/fcm-token/
    Body: { "token": "fcm_token_string", "device_type": "android" }
    Called by Flutter after FCM initializes on app start.
    """
    token = request.data.get('token', '').strip()
    device_type = request.data.get('device_type', 'android')

    if not token:
        return Response({'error': 'token is required'}, status=status.HTTP_400_BAD_REQUEST)

    fcm_token, created = FCMToken.objects.update_or_create(
        token=token,
        defaults={
            'agent': request.user,
            'device_type': device_type,
            'is_active': True,
        }
    )
    return Response({'success': True, 'created': created})


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def deregister_fcm_token(request):
    """
    DELETE /api/notifications/fcm-token/
    Body: { "token": "fcm_token_string" }
    Called on logout.
    """
    token = request.data.get('token', '').strip()
    deleted, _ = FCMToken.objects.filter(agent=request.user, token=token).delete()
    return Response({'deleted': deleted > 0})
