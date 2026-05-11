# leads/whatsapp_service.py
"""
WhatsApp Business Cloud API service.
Official docs: https://developers.facebook.com/docs/whatsapp/cloud-api/
"""

import requests
import logging

logger = logging.getLogger(__name__)

GRAPH_API_VERSION = "v19.0"
GRAPH_API_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"


def send_whatsapp_text(phone_number_id: str, access_token: str, to: str, body: str) -> dict:
    """
    Send a free-form text message via WhatsApp Cloud API.

    :param phone_number_id: The WhatsApp Business phone number ID
    :param access_token:    Permanent system-user access token
    :param to:              Recipient's phone number in E.164 format (e.g. +919876543210)
    :param body:            Plain-text message body
    :returns:               API response dict
    :raises:                requests.HTTPError on failure
    """
    # Normalise: strip leading + so Meta receives digits only
    to_clean = to.replace("+", "").replace(" ", "").replace("-", "")

    url = f"{GRAPH_API_BASE}/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_clean,
        "type": "text",
        "text": {"preview_url": False, "body": body},
    }
    response = requests.post(url, headers=headers, json=payload, timeout=15)
    response.raise_for_status()
    return response.json()


def send_whatsapp_template(
    phone_number_id: str,
    access_token: str,
    to: str,
    template_name: str,
    language_code: str = "en_US",
    components: list | None = None,
) -> dict:
    """
    Send a pre-approved WhatsApp template message.
    Required for outbound messages outside the 24-hour session window.
    """
    to_clean = to.replace("+", "").replace(" ", "").replace("-", "")
    url = f"{GRAPH_API_BASE}/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_clean,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": language_code},
        },
    }
    if components:
        payload["template"]["components"] = components

    response = requests.post(url, headers=headers, json=payload, timeout=15)
    response.raise_for_status()
    return response.json()


def get_whatsapp_media_url(media_id: str, access_token: str) -> str:
    """Resolve a media ID to a downloadable URL."""
    url = f"{GRAPH_API_BASE}/{media_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(url, headers=headers, timeout=15)
    response.raise_for_status()
    return response.json().get("url", "")
