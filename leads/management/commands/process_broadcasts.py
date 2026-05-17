# leads/management/commands/process_broadcasts.py
# ─────────────────────────────────────────────────────────────────────────────
# Processes queued WhatsApp broadcast campaigns across all tenants.
#
# Usage:
#   python manage.py process_broadcasts               # all tenants
#   python manage.py process_broadcasts --schema acme # specific tenant
#   python manage.py process_broadcasts --broadcast-id 42
#   python manage.py process_broadcasts --dry-run
#
# Rate-limiting: 30 messages/batch with a 1-second pause between batches.
# For high volume, replace with Celery: process_broadcast.delay(broadcast.id)
# ─────────────────────────────────────────────────────────────────────────────

import time
import logging

from django.core.management.base import BaseCommand
from django.utils import timezone
from django_tenants.utils import schema_context, get_public_schema_name

logger = logging.getLogger(__name__)
BATCH_SIZE = 30
BATCH_PAUSE = 1.0


class Command(BaseCommand):
    help = 'Process queued WhatsApp broadcasts across all tenants.'

    def add_arguments(self, parser):
        parser.add_argument('--schema', type=str, help='Process a single tenant schema only')
        parser.add_argument('--broadcast-id', type=int, help='Process a specific broadcast by ID')
        parser.add_argument('--dry-run', action='store_true', help='Preview sends without sending')

    def handle(self, *args, **options):
        target_schema = options.get('schema')

        if target_schema:
            self._run_for_schema(target_schema, options)
        else:
            # Iterate all active tenants
            from tenants.models import Client
            tenants = Client.objects.exclude(schema_name=get_public_schema_name())
            if not tenants.exists():
                self.stdout.write('No tenants found.')
                return
            for tenant in tenants:
                if not tenant.is_active:
                    continue
                self.stdout.write(self.style.MIGRATE_LABEL(
                    f'\n── Tenant: {tenant.name} ({tenant.schema_name}) ──'
                ))
                self._run_for_schema(tenant.schema_name, options)

    def _run_for_schema(self, schema: str, options: dict):
        with schema_context(schema):
            from leads.whatsapp_models import WABroadcast
            from leads.whatsapp_providers import get_provider, get_default_provider

            qs = WABroadcast.objects.filter(
                status__in=['queued', 'running'],
                scheduled_at__lte=timezone.now(),
            )
            if options.get('broadcast_id'):
                qs = qs.filter(id=options['broadcast_id'])

            if not qs.exists():
                self.stdout.write(f'  No pending broadcasts in schema "{schema}".')
                return

            for broadcast in qs:
                self._process(broadcast, options['dry_run'])

    def _process(self, broadcast, dry_run: bool):
        from leads.whatsapp_models import WABroadcastRecipient
        from leads.whatsapp_providers import get_provider

        self.stdout.write(self.style.MIGRATE_HEADING(
            f'\n  Campaign #{broadcast.id}: {broadcast.name} '
            f'(type={broadcast.message_type}, provider={broadcast.provider})'
        ))

        # Resolve provider
        provider_model = broadcast.provider
        if not provider_model:
            from leads.whatsapp_providers import get_default_provider
            provider_model = get_default_provider()
        if not provider_model:
            self.stderr.write(f'  ERROR: No WhatsApp provider configured for campaign #{broadcast.id}. Skipping.')
            return

        try:
            provider_impl = get_provider(provider_model)
        except Exception as e:
            self.stderr.write(f'  ERROR: Cannot initialise provider: {e}')
            return

        broadcast.status = 'running'
        broadcast.started_at = timezone.now()
        broadcast.save(update_fields=['status', 'started_at'])

        pending = WABroadcastRecipient.objects.filter(
            broadcast=broadcast, status='pending'
        ).select_related('lead')

        total = pending.count()
        sent = failed = skipped = 0
        self.stdout.write(f'  Recipients pending: {total}')

        for i, recipient in enumerate(pending.iterator()):
            lead = recipient.lead

            # Check opt-out
            opted_out = (
                hasattr(lead, 'wa_conversation') and lead.wa_conversation.is_opted_out
            )
            if opted_out:
                recipient.status = 'skipped'
                recipient.save(update_fields=['status'])
                skipped += 1
                continue

            if dry_run:
                self.stdout.write(f'  [DRY RUN] Would send to {lead.name} ({lead.phone})')
                sent += 1
                continue

            try:
                if broadcast.message_type == 'template' and broadcast.template:
                    components = broadcast.template.build_components(lead)
                    result = provider_impl.send_template(
                        to=lead.phone,
                        template_name=broadcast.template.name,
                        language_code=broadcast.template.language_code,
                        components=components,
                    )
                else:
                    body = broadcast.render_text_body(lead)
                    result = provider_impl.send_text(to=lead.phone, body=body)

                recipient.status = 'sent'
                recipient.wa_message_id = result.get('message_id', '')
                recipient.sent_at = timezone.now()
                sent += 1

                # Log WAMessage so conversation history is updated
                self._log_wa_message(lead, broadcast, recipient.wa_message_id)

            except Exception as e:
                recipient.status = 'failed'
                recipient.error_message = str(e)[:500]
                failed += 1
                logger.error('Campaign %s failed for lead %s: %s', broadcast.id, lead.id, e)

            recipient.save(update_fields=['status', 'wa_message_id', 'sent_at', 'error_message'])

            if (i + 1) % BATCH_SIZE == 0:
                self.stdout.write(f'  Progress: {i + 1}/{total} — pausing {BATCH_PAUSE}s...')
                time.sleep(BATCH_PAUSE)

        # Update counters
        from leads.whatsapp_models import WABroadcastRecipient as Rec
        WABroadcast.objects.filter(pk=broadcast.pk).update(
            status='completed' if not dry_run else 'queued',
            sent_count=Rec.objects.filter(broadcast=broadcast, status='sent').count(),
            failed_count=Rec.objects.filter(broadcast=broadcast, status='failed').count(),
            opted_out_skipped=skipped,
            completed_at=timezone.now() if not dry_run else None,
        )

        self.stdout.write(self.style.SUCCESS(
            f'  Done — Sent: {sent}  Failed: {failed}  Skipped (opt-out): {skipped}'
        ))

    def _log_wa_message(self, lead, broadcast, wa_message_id: str):
        """Record the send in WAConversation/WAMessage for conversation history."""
        try:
            from leads.whatsapp_models import WAConversation, WAMessage
            conv, _ = WAConversation.objects.get_or_create(
                lead=lead, defaults={'status': 'waiting'}
            )
            WAMessage.objects.create(
                conversation=conv,
                direction='outbound',
                message_type=broadcast.message_type,
                status='sent',
                body=broadcast.render_text_body(lead) if broadcast.message_type == 'text'
                     else (broadcast.template.render_body(lead) if broadcast.template else ''),
                template=broadcast.template if broadcast.message_type == 'template' else None,
                wa_message_id=wa_message_id,
                sent_at=timezone.now(),
            )
            WAConversation.objects.filter(pk=conv.pk).update(
                last_message_at=timezone.now(), status='waiting'
            )
        except Exception as e:
            logger.warning('Could not log WAMessage for lead %s: %s', lead.id, e)
