# api/integrations.py
"""
Webhook handlers for Meta Lead Ads, IndiaMart, JustDial, and WhatsApp.
All implementations follow official vendor documentation.

Meta Lead Ads docs:
  https://developers.facebook.com/docs/marketing-api/guides/lead-ads/retrieving
IndiaMart Push API docs:
  https://stoplight.io/api/v1/projects/indiamart/IndiaMART-CRM-API/nodes/reference/IndiaMART-CRM-API.yaml
JustDial:
  Webhook URL shared with account manager; payload mapped to CRM fields.
WhatsApp Cloud API docs:
  https://developers.facebook.com/docs/whatsapp/cloud-api/
"""

import json
import logging
import requests

from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from leads.models import Lead
from leads.integration_models import IntegrationConfig, IntegrationLog

logger = logging.getLogger(__name__)

GRAPH_API_VERSION = "v19.0"
GRAPH_API_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _get_config(platform: str) -> IntegrationConfig | None:
    """Return the active config for a given platform or None."""
    try:
        return IntegrationConfig.objects.get(platform=platform, is_active=True)
    except IntegrationConfig.DoesNotExist:
        return None


def _log(platform: str, payload: str, created: bool, status: str, error: str = ""):
    IntegrationLog.objects.create(
        platform=platform,
        raw_payload=payload[:5000],  # cap at 5 KB
        lead_created=created,
        status=status,
        error_message=error or None,
    )


def _fetch_meta_lead(lead_id: str, page_access_token: str) -> dict | None:
    """
    Fetch lead field values from Meta Graph API using the lead_id.
    Requires 'leads_retrieval' permission on the Page Access Token.
    """
    url = f"{GRAPH_API_BASE}/{lead_id}?fields=field_data,created_time&access_token={page_access_token}"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.error("Failed to fetch Meta lead %s: %s", lead_id, exc)
        return None


def _parse_meta_field_data(field_data: list) -> dict:
    """Convert Meta's field_data list → flat dict."""
    result = {}
    for item in field_data:
        result[item.get("name", "").lower()] = item.get("values", [""])[0]
    return result


# ─────────────────────────────────────────────────────────────────────────────
# META LEAD ADS WEBHOOK
# ─────────────────────────────────────────────────────────────────────────────

@csrf_exempt
@require_http_methods(["GET", "POST"])
def meta_webhook(request):
    """
    GET  – webhook verification (Meta sends hub.challenge)
    POST – new lead notification; we fetch lead details via Graph API
    """
    config = _get_config("meta")

    # ── Verification ────────────────────────────────────────────
    if request.method == "GET":
        if not config:
            return HttpResponse("Integration not configured", status=503)

        mode = request.GET.get("hub.mode")
        token = request.GET.get("hub.verify_token")
        challenge = request.GET.get("hub.challenge")

        if mode == "subscribe" and token == config.verify_token:
            logger.info("Meta webhook verified successfully")
            return HttpResponse(challenge, status=200)
        return HttpResponse("Verification failed – token mismatch", status=403)

    # ── Event Notification ──────────────────────────────────────
    raw = request.body.decode("utf-8", errors="replace")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        _log("meta", raw, False, "error", "Invalid JSON payload")
        return HttpResponse("Bad Request", status=400)

    if not config:
        _log("meta", raw, False, "error", "Integration not active")
        # Still return 200 so Meta doesn't retry indefinitely
        return HttpResponse("EVENT_RECEIVED", status=200)

    if data.get("object") != "page":
        return HttpResponse("EVENT_RECEIVED", status=200)

    leads_created = 0
    for entry in data.get("entry", []):
        for change in entry.get("changes", []):
            if change.get("field") != "leadgen":
                continue
            value = change.get("value", {})
            lead_id = value.get("leadgen_id") or value.get("lead_id")
            if not lead_id:
                continue

            # Fetch actual lead details from Graph API
            lead_data = _fetch_meta_lead(lead_id, config.page_access_token)
            if not lead_data:
                _log("meta", raw, False, "error", f"Could not fetch lead {lead_id} from Graph API")
                continue

            fields = _parse_meta_field_data(lead_data.get("field_data", []))

            name = (
                fields.get("full_name")
                or f"{fields.get('first_name', '')} {fields.get('last_name', '')}".strip()
                or "Meta Lead"
            )
            phone = fields.get("phone_number") or fields.get("phone", "")
            email = fields.get("email", "")
            company = fields.get("company_name") or fields.get("company", "")

            if not phone:
                _log("meta", raw, False, "error", f"Lead {lead_id} has no phone number")
                continue

            _, created = Lead.objects.get_or_create(
                phone=phone,
                defaults={
                    "name": name,
                    "email": email or None,
                    "company": company or None,
                    "source": "Meta",
                    "notes": f"Meta Lead ID: {lead_id}",
                },
            )
            status = "success" if created else "duplicate"
            _log("meta", raw, created, status)
            if created:
                leads_created += 1

    logger.info("Meta webhook processed – %d new lead(s)", leads_created)
    return HttpResponse("EVENT_RECEIVED", status=200)


# ─────────────────────────────────────────────────────────────────────────────
# INDIAMART PUSH API WEBHOOK
# ─────────────────────────────────────────────────────────────────────────────

@csrf_exempt
@require_http_methods(["POST"])
def indiamart_webhook(request):
    """
    IndiaMART pushes a JSON POST to this URL when a new inquiry arrives.
    Payload fields (official docs):
      UNIQUE_QUERY_ID, QUERY_TYPE, QUERY_TIME,
      SENDER_NAME, SENDER_MOBILE, SENDER_EMAIL,
      SENDER_COMPANY, SENDER_CITY, SENDER_STATE,
      QUERY_PRODUCT_NAME, QUERY_MESSAGE, RECEIVER_CATALOG
    """
    config = _get_config("indiamart")

    raw = request.body.decode("utf-8", errors="replace")
    try:
        data = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        # Some integrations send form-encoded data
        data = request.POST.dict()

    if not config:
        _log("indiamart", raw, False, "error", "Integration not active")
        return HttpResponse("OK", status=200)  # Acknowledge so IndiaMart stops retrying

    name = data.get("SENDER_NAME", "IndiaMart Lead").strip()
    phone = str(data.get("SENDER_MOBILE", "")).strip()
    email = data.get("SENDER_EMAIL", "").strip()
    company = data.get("SENDER_COMPANY", "").strip()
    product = data.get("QUERY_PRODUCT_NAME", "").strip()
    message = data.get("QUERY_MESSAGE", "").strip()

    if not phone:
        _log("indiamart", raw, False, "error", "Missing SENDER_MOBILE in payload")
        return HttpResponse("OK", status=200)

    notes_parts = []
    if product:
        notes_parts.append(f"Product: {product}")
    if message:
        notes_parts.append(f"Message: {message}")

    _, created = Lead.objects.get_or_create(
        phone=phone,
        defaults={
            "name": name or "IndiaMart Lead",
            "email": email or None,
            "company": company or None,
            "source": "IndiaMart",
            "notes": "\n".join(notes_parts) if notes_parts else None,
        },
    )
    status = "success" if created else "duplicate"
    _log("indiamart", raw, created, status)
    return HttpResponse("OK", status=200)


# ─────────────────────────────────────────────────────────────────────────────
# JUSTDIAL PUSH API WEBHOOK
# ─────────────────────────────────────────────────────────────────────────────

@csrf_exempt
@require_http_methods(["GET", "POST"])
def justdial_webhook(request):
    """
    JustDial account manager configures this URL on their backend.
    Payload (GET or POST, form-encoded or JSON):
      name / first_name / last_name, mobile / phone,
      email, company, category, area, city
    """
    config = _get_config("justdial")

    raw = request.body.decode("utf-8", errors="replace")

    # Accept both GET query-string and POST body
    if request.method == "POST":
        try:
            data = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            data = request.POST.dict()
    else:
        data = request.GET.dict()

    if not config:
        _log("justdial", raw or str(data), False, "error", "Integration not active")
        return HttpResponse("OK", status=200)

    first = data.get("first_name", "")
    last = data.get("last_name", "")
    name = data.get("name") or f"{first} {last}".strip() or "JustDial Lead"
    phone = data.get("mobile") or data.get("phone", "")
    email = data.get("email", "")
    company = data.get("company", "")
    category = data.get("category", "")
    city = data.get("city") or data.get("area", "")

    if not phone:
        _log("justdial", raw or str(data), False, "error", "Missing mobile/phone in payload")
        return HttpResponse("OK", status=200)

    notes_parts = []
    if category:
        notes_parts.append(f"Category: {category}")
    if city:
        notes_parts.append(f"City: {city}")

    _, created = Lead.objects.get_or_create(
        phone=phone,
        defaults={
            "name": name,
            "email": email or None,
            "company": company or None,
            "source": "JustDial",
            "notes": "\n".join(notes_parts) if notes_parts else None,
        },
    )
    status = "success" if created else "duplicate"
    _log("justdial", raw or str(data), created, status)
    return HttpResponse("OK", status=200)


# ─────────────────────────────────────────────────────────────────────────────
# WHATSAPP CLOUD API WEBHOOK
# ─────────────────────────────────────────────────────────────────────────────

@csrf_exempt
@require_http_methods(["GET", "POST"])
def whatsapp_webhook(request):
    """
    GET  – Meta webhook verification for WhatsApp Cloud API
    POST – Incoming WhatsApp messages / status updates
    """
    config = _get_config("whatsapp")

    # ── Verification ────────────────────────────────────────────
    if request.method == "GET":
        if not config:
            return HttpResponse("Integration not configured", status=503)
        mode = request.GET.get("hub.mode")
        token = request.GET.get("hub.verify_token")
        challenge = request.GET.get("hub.challenge")
        if mode == "subscribe" and token == config.whatsapp_verify_token:
            logger.info("WhatsApp webhook verified")
            return HttpResponse(challenge, status=200)
        return HttpResponse("Verification failed", status=403)

    # ── Incoming Message Notification ───────────────────────────
    raw = request.body.decode("utf-8", errors="replace")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return HttpResponse("Bad Request", status=400)

    # Process each entry / change
    for entry in data.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            # Incoming messages
            for msg in value.get("messages", []):
                sender = msg.get("from", "")  # Phone number in E.164 without '+'
                msg_type = msg.get("type", "")
                text_body = ""
                if msg_type == "text":
                    text_body = msg.get("text", {}).get("body", "")

                # Auto-create a lead if phone is unknown
                if sender:
                    lead, created = Lead.objects.get_or_create(
                        phone=sender,
                        defaults={
                            "name": "WhatsApp Contact",
                            "source": "WhatsApp",
                            "notes": f"First message: {text_body[:200]}" if text_body else None,
                        },
                    )
                    _log("whatsapp", raw, created, "success" if created else "duplicate")

    return HttpResponse("EVENT_RECEIVED", status=200)


# ─────────────────────────────────────────────────────────────────────────────
# WHATSAPP SEND MESSAGE API (called from Django views)
# ─────────────────────────────────────────────────────────────────────────────

@csrf_exempt
@require_http_methods(["POST"])
def whatsapp_send_message(request):
    """
    Internal endpoint to send a WhatsApp message from the CRM UI.
    POST body (JSON): { "phone": "+919876543210", "message": "Hello!" }
    Must be authenticated (session).
    """
    if not request.user.is_authenticated or not request.user.is_staff:
        return JsonResponse({"error": "Forbidden"}, status=403)

    config = _get_config("whatsapp")
    if not config:
        return JsonResponse({"error": "WhatsApp integration not configured or inactive"}, status=400)

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    phone = body.get("phone", "").replace("+", "").replace(" ", "")
    message = body.get("message", "")

    if not phone or not message:
        return JsonResponse({"error": "phone and message are required"}, status=400)

    url = f"{GRAPH_API_BASE}/{config.whatsapp_phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {config.whatsapp_access_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "text",
        "text": {"preview_url": False, "body": message},
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=15)
        resp.raise_for_status()
        return JsonResponse({"success": True, "data": resp.json()})
    except requests.HTTPError as exc:
        logger.error("WhatsApp send failed: %s", exc)
        return JsonResponse({"error": str(exc), "detail": exc.response.text}, status=502)
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=500)
