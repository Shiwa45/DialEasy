# leads/whatsapp_providers.py
# Provider abstraction for bulk WhatsApp messaging.
# All providers implement BaseWhatsAppProvider so campaigns can swap providers
# without changing any campaign logic.

import logging
import requests
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


def _clean_phone(phone: str) -> str:
    """Normalize to E.164 digits without leading +"""
    cleaned = (
        phone.replace('+', '').replace(' ', '')
             .replace('-', '').replace('(', '').replace(')', '')
    )
    if not cleaned.startswith('91') and len(cleaned) == 10:
        cleaned = '91' + cleaned
    return cleaned


# ─── Abstract base ────────────────────────────────────────────────────────────

class BaseWhatsAppProvider(ABC):
    provider_slug: str = None
    provider_name: str = None

    @abstractmethod
    def send_template(
        self,
        to: str,
        template_name: str,
        language_code: str = 'en_US',
        components: list = None,
    ) -> dict:
        """
        Send an approved template message.
        Returns {'message_id': str, 'status': 'sent'} on success.
        Raises on failure.
        """

    @abstractmethod
    def send_text(self, to: str, body: str) -> dict:
        """Send a plain text message. Returns {'message_id': str, 'status': 'sent'}."""

    @abstractmethod
    def test_connection(self) -> tuple:
        """Test credentials. Returns (ok: bool, message: str)."""


# ─── Meta (WhatsApp Cloud API) ────────────────────────────────────────────────

class MetaProvider(BaseWhatsAppProvider):
    provider_slug = 'meta'
    provider_name = 'Meta (WhatsApp Cloud API)'

    def __init__(self, phone_number_id: str, access_token: str):
        self.phone_number_id = phone_number_id
        self.access_token = access_token
        self._base = 'https://graph.facebook.com/v19.0'

    def _headers(self):
        return {'Authorization': f'Bearer {self.access_token}', 'Content-Type': 'application/json'}

    def send_text(self, to: str, body: str) -> dict:
        resp = requests.post(
            f'{self._base}/{self.phone_number_id}/messages',
            headers=self._headers(),
            json={
                'messaging_product': 'whatsapp',
                'to': _clean_phone(to),
                'type': 'text',
                'text': {'preview_url': False, 'body': body},
            },
            timeout=15,
        )
        resp.raise_for_status()
        msg_id = resp.json().get('messages', [{}])[0].get('id', '')
        return {'message_id': msg_id, 'status': 'sent'}

    def send_template(self, to: str, template_name: str, language_code: str = 'en_US', components: list = None) -> dict:
        tmpl_payload = {'name': template_name, 'language': {'code': language_code}}
        if components:
            tmpl_payload['components'] = components
        resp = requests.post(
            f'{self._base}/{self.phone_number_id}/messages',
            headers=self._headers(),
            json={
                'messaging_product': 'whatsapp',
                'to': _clean_phone(to),
                'type': 'template',
                'template': tmpl_payload,
            },
            timeout=15,
        )
        resp.raise_for_status()
        msg_id = resp.json().get('messages', [{}])[0].get('id', '')
        return {'message_id': msg_id, 'status': 'sent'}

    def test_connection(self) -> tuple:
        try:
            resp = requests.get(
                f'{self._base}/{self.phone_number_id}',
                headers=self._headers(),
                params={'fields': 'display_phone_number,verified_name'},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                return True, f"Connected — {data.get('verified_name', '')} ({data.get('display_phone_number', '')})"
            return False, f'API returned {resp.status_code}: {resp.text[:300]}'
        except Exception as e:
            return False, str(e)


# ─── Twilio ───────────────────────────────────────────────────────────────────

class TwilioProvider(BaseWhatsAppProvider):
    provider_slug = 'twilio'
    provider_name = 'Twilio WhatsApp'

    def __init__(self, account_sid: str, auth_token: str, from_number: str):
        self.account_sid = account_sid
        self.auth_token = auth_token
        # from_number must be in format: whatsapp:+14155238886
        self.from_number = from_number
        self._url = f'https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json'

    def _to(self, phone: str) -> str:
        return f'whatsapp:+{_clean_phone(phone)}'

    def send_text(self, to: str, body: str) -> dict:
        resp = requests.post(
            self._url,
            data={'From': self.from_number, 'To': self._to(to), 'Body': body},
            auth=(self.account_sid, self.auth_token),
            timeout=15,
        )
        resp.raise_for_status()
        return {'message_id': resp.json().get('sid', ''), 'status': 'sent'}

    def send_template(self, to: str, template_name: str, language_code: str = 'en_US', components: list = None) -> dict:
        # Twilio uses Content Templates (ContentSid). template_name is treated as
        # a rendered body string here — callers should pass the rendered body.
        return self.send_text(to, template_name)

    def test_connection(self) -> tuple:
        try:
            resp = requests.get(
                f'https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}.json',
                auth=(self.account_sid, self.auth_token),
                timeout=10,
            )
            if resp.status_code == 200:
                name = resp.json().get('friendly_name', self.account_sid)
                return True, f'Connected — {name}'
            return False, f'Twilio returned {resp.status_code}: {resp.text[:300]}'
        except Exception as e:
            return False, str(e)


# ─── WATI ─────────────────────────────────────────────────────────────────────

class WATIProvider(BaseWhatsAppProvider):
    provider_slug = 'wati'
    provider_name = 'WATI'

    def __init__(self, api_endpoint: str, api_key: str):
        self.api_endpoint = api_endpoint.rstrip('/')
        self.api_key = api_key

    def _headers(self):
        return {'Authorization': f'Bearer {self.api_key}', 'Content-Type': 'application/json'}

    def send_text(self, to: str, body: str) -> dict:
        phone = _clean_phone(to)
        resp = requests.post(
            f'{self.api_endpoint}/v1/sendSessionMessage/{phone}',
            headers=self._headers(),
            json={'messageText': body},
            timeout=15,
        )
        resp.raise_for_status()
        return {'message_id': resp.json().get('id', ''), 'status': 'sent'}

    def send_template(self, to: str, template_name: str, language_code: str = 'en_US', components: list = None) -> dict:
        phone = _clean_phone(to)
        parameters = []
        if components:
            for comp in components:
                if comp.get('type') == 'body':
                    for i, param in enumerate(comp.get('parameters', []), 1):
                        parameters.append({'name': str(i), 'value': param.get('text', '')})
        resp = requests.post(
            f'{self.api_endpoint}/v1/sendTemplateMessage',
            headers=self._headers(),
            json={
                'template_name': template_name,
                'broadcast_name': f'crm_{template_name}',
                'receivers': [{'whatsappNumber': phone, 'customParams': parameters}],
            },
            timeout=15,
        )
        resp.raise_for_status()
        return {'message_id': resp.json().get('id', ''), 'status': 'sent'}

    def test_connection(self) -> tuple:
        try:
            resp = requests.get(
                f'{self.api_endpoint}/v1/getContacts',
                headers=self._headers(),
                params={'pageSize': 1},
                timeout=10,
            )
            if resp.status_code == 200:
                return True, 'WATI connection successful'
            return False, f'WATI returned {resp.status_code}: {resp.text[:300]}'
        except Exception as e:
            return False, str(e)


# ─── AiSensy ──────────────────────────────────────────────────────────────────

class AiSensyProvider(BaseWhatsAppProvider):
    provider_slug = 'aisensy'
    provider_name = 'AiSensy'

    def __init__(self, api_key: str):
        self.api_key = api_key
        self._url = 'https://backend.aisensy.com/campaign/t1/api'

    def _headers(self):
        return {'X-AiSensy-Api-Key': self.api_key, 'Content-Type': 'application/json'}

    def send_text(self, to: str, body: str) -> dict:
        resp = requests.post(
            self._url,
            headers=self._headers(),
            json={
                'apiKey': self.api_key,
                'campaignName': 'OnetoOne',
                'destination': _clean_phone(to),
                'userName': 'CRM',
                'templateParams': [body],
                'source': 'CRM',
            },
            timeout=15,
        )
        resp.raise_for_status()
        return {'message_id': resp.json().get('messageId', ''), 'status': 'sent'}

    def send_template(self, to: str, template_name: str, language_code: str = 'en_US', components: list = None) -> dict:
        params = []
        if components:
            for comp in components:
                if comp.get('type') == 'body':
                    params = [p.get('text', '') for p in comp.get('parameters', [])]
        resp = requests.post(
            self._url,
            headers=self._headers(),
            json={
                'apiKey': self.api_key,
                'campaignName': template_name,
                'destination': _clean_phone(to),
                'userName': 'CRM',
                'templateParams': params,
                'source': 'CRM Broadcast',
                'media': {}, 'buttons': [], 'carouselCards': [], 'location': {},
            },
            timeout=15,
        )
        resp.raise_for_status()
        return {'message_id': resp.json().get('messageId', ''), 'status': 'sent'}

    def test_connection(self) -> tuple:
        try:
            resp = requests.get(
                'https://backend.aisensy.com/user/t1/api/get-user',
                headers=self._headers(),
                timeout=10,
            )
            if resp.status_code == 200:
                return True, 'AiSensy connection successful'
            return False, f'AiSensy returned {resp.status_code}: {resp.text[:300]}'
        except Exception as e:
            return False, str(e)


# ─── Interakt ─────────────────────────────────────────────────────────────────

class InteraktProvider(BaseWhatsAppProvider):
    provider_slug = 'interakt'
    provider_name = 'Interakt'

    def __init__(self, api_key: str):
        self.api_key = api_key
        self._base = 'https://api.interakt.ai/v1/public'

    def _headers(self):
        import base64
        encoded = base64.b64encode(self.api_key.encode()).decode()
        return {'Authorization': f'Basic {encoded}', 'Content-Type': 'application/json'}

    def send_text(self, to: str, body: str) -> dict:
        resp = requests.post(
            f'{self._base}/message/',
            headers=self._headers(),
            json={
                'countryCode': '+91',
                'phoneNumber': f'+{_clean_phone(to)}',
                'callbackData': 'CRM',
                'type': 'Text',
                'data': {'message': body},
            },
            timeout=15,
        )
        resp.raise_for_status()
        return {'message_id': resp.json().get('id', ''), 'status': 'sent'}

    def send_template(self, to: str, template_name: str, language_code: str = 'en_US', components: list = None) -> dict:
        header_vars, body_vars = [], []
        if components:
            for comp in components:
                if comp.get('type') == 'header':
                    header_vars = [p.get('text', '') for p in comp.get('parameters', [])]
                elif comp.get('type') == 'body':
                    body_vars = [p.get('text', '') for p in comp.get('parameters', [])]
        resp = requests.post(
            f'{self._base}/message/',
            headers=self._headers(),
            json={
                'countryCode': '+91',
                'phoneNumber': f'+{_clean_phone(to)}',
                'callbackData': 'CRM Broadcast',
                'type': 'Template',
                'template': {
                    'name': template_name,
                    'languageCode': language_code,
                    'headerValues': header_vars,
                    'bodyValues': body_vars,
                },
            },
            timeout=15,
        )
        resp.raise_for_status()
        return {'message_id': resp.json().get('id', ''), 'status': 'sent'}

    def test_connection(self) -> tuple:
        try:
            resp = requests.get(
                f'{self._base}/track/users/',
                headers=self._headers(),
                params={'limit': 1},
                timeout=10,
            )
            if resp.status_code == 200:
                return True, 'Interakt connection successful'
            return False, f'Interakt returned {resp.status_code}: {resp.text[:300]}'
        except Exception as e:
            return False, str(e)


# ─── Factory ──────────────────────────────────────────────────────────────────

PROVIDER_CHOICES = [
    ('meta',     'Meta (WhatsApp Cloud API)'),
    ('twilio',   'Twilio WhatsApp'),
    ('wati',     'WATI'),
    ('aisensy',  'AiSensy'),
    ('interakt', 'Interakt'),
]


def get_provider(wa_provider) -> BaseWhatsAppProvider:
    """Return an instantiated provider from a WAProvider model instance."""
    slug = wa_provider.provider
    if slug == 'meta':
        return MetaProvider(
            phone_number_id=wa_provider.meta_phone_number_id,
            access_token=wa_provider.meta_access_token,
        )
    if slug == 'twilio':
        return TwilioProvider(
            account_sid=wa_provider.twilio_account_sid,
            auth_token=wa_provider.twilio_auth_token,
            from_number=wa_provider.twilio_from_number,
        )
    if slug == 'wati':
        return WATIProvider(
            api_endpoint=wa_provider.wati_api_endpoint,
            api_key=wa_provider.wati_api_key,
        )
    if slug == 'aisensy':
        return AiSensyProvider(api_key=wa_provider.aisensy_api_key)
    if slug == 'interakt':
        return InteraktProvider(api_key=wa_provider.interakt_api_key)
    raise ValueError(f'Unknown provider slug: {slug}')


def get_default_provider():
    """Return the default WAProvider instance, or None if none configured."""
    from leads.whatsapp_models import WAProvider
    return WAProvider.objects.filter(is_active=True, is_default=True).first() \
        or WAProvider.objects.filter(is_active=True).first()
