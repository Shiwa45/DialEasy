# leads/management/commands/process_broadcasts.py
# ─────────────────────────────────────────────────────────────────────────────
# Processes queued WhatsApp broadcasts.
# Run via cron or manually: python manage.py process_broadcasts
#
# Rate-limiting: WhatsApp Cloud API allows ~80 msgs/sec on tier 1.
# This command sends in batches of 30 with a 1-second pause between batches.
# For production use, replace with a Celery task.
# ─────────────────────────────────────────────────────────────────────────────

import time
import logging
from django.core.management.base import BaseCommand
from django.utils import timezone
from leads.whatsapp_models import WABroadcast, WABroadcastRecipient
from leads.whatsapp_service_v2 import send_template_and_log, _get_wa_config

logger = logging.getLogger(__name__)
BATCH_SIZE = 30
BATCH_PAUSE = 1.0  # seconds between batches


class Command(BaseCommand):
    help = 'Process queued WhatsApp broadcasts. Safe to run repeatedly.'

    def add_arguments(self, parser):
        parser.add_argument('--broadcast-id', type=int, help='Process a specific broadcast by ID')
        parser.add_argument('--dry-run', action='store_true', help='Show what would be sent without actually sending')

    def handle(self, *args, **options):
        cfg = _get_wa_config()
        if not cfg:
            self.stderr.write(self.style.ERROR('WhatsApp not configured or inactive.'))
            return

        qs = WABroadcast.objects.filter(
            status__in=['queued', 'running'],
            scheduled_at__lte=timezone.now(),
        )
        if options['broadcast_id']:
            qs = qs.filter(id=options['broadcast_id'])

        if not qs.exists():
            self.stdout.write('No broadcasts ready to process.')
            return

        for broadcast in qs:
            self._process(broadcast, options['dry_run'])

    def _process(self, broadcast: WABroadcast, dry_run: bool):
        self.stdout.write(self.style.MIGRATE_HEADING(
            f'\nProcessing broadcast #{broadcast.id}: {broadcast.name}'
        ))

        broadcast.status = 'running'
        broadcast.started_at = timezone.now()
        broadcast.save(update_fields=['status', 'started_at'])

        pending = WABroadcastRecipient.objects.filter(
            broadcast=broadcast, status='pending'
        ).select_related('lead')

        total = pending.count()
        sent = 0
        failed = 0
        skipped = 0

        self.stdout.write(f'  Recipients: {total}')

        for i, recipient in enumerate(pending.iterator()):
            lead = recipient.lead

            # Check opt-out
            opted_out = lead.wa_conversation.is_opted_out if hasattr(lead, 'wa_conversation') else False
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
                wa_msg = send_template_and_log(
                    lead=lead,
                    wa_template=broadcast.template,
                    sent_by=None,
                )
                if wa_msg and wa_msg.status in ('sent', 'pending'):
                    recipient.status = 'sent'
                    recipient.wa_message_id = wa_msg.wa_message_id
                    recipient.sent_at = timezone.now()
                    sent += 1
                else:
                    recipient.status = 'failed'
                    recipient.error_message = wa_msg.failed_reason if wa_msg else 'Unknown error'
                    failed += 1

            except Exception as e:
                recipient.status = 'failed'
                recipient.error_message = str(e)[:500]
                failed += 1
                logger.error('Broadcast %s failed for lead %s: %s', broadcast.id, lead.id, e)

            recipient.save(update_fields=['status', 'wa_message_id', 'sent_at', 'error_message'])

            # Rate limiting: pause after each batch
            if (i + 1) % BATCH_SIZE == 0:
                self.stdout.write(f'  Progress: {i + 1}/{total} — sleeping {BATCH_PAUSE}s...')
                time.sleep(BATCH_PAUSE)

        # Update broadcast counters
        WABroadcast.objects.filter(pk=broadcast.pk).update(
            status='completed' if not dry_run else 'queued',
            sent_count=WABroadcastRecipient.objects.filter(broadcast=broadcast, status='sent').count(),
            failed_count=WABroadcastRecipient.objects.filter(broadcast=broadcast, status='failed').count(),
            opted_out_skipped=skipped,
            completed_at=timezone.now() if not dry_run else None,
        )

        self.stdout.write(self.style.SUCCESS(
            f'  Done — Sent: {sent}, Failed: {failed}, Skipped (opt-out): {skipped}'
        ))
