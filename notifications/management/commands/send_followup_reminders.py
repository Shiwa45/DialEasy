# notifications/management/commands/send_followup_reminders.py
# ─────────────────────────────────────────────────────────────────────────────
# Cron command — run every 5 minutes via cron or Task Scheduler.
# Sends push notifications for follow-ups due in the next 15 minutes
# and for overdue follow-ups (once per day, not spammed).
#
#   */5 * * * * python manage.py send_followup_reminders
# ─────────────────────────────────────────────────────────────────────────────

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime, timedelta


class Command(BaseCommand):
    help = 'Send push notifications for follow-ups due soon or overdue.'

    def handle(self, *args, **options):
        from leads.models import FollowUp
        from notifications.service import notify_follow_up_due, notify_follow_up_overdue
        from notifications.models import Notification

        now = timezone.now()
        today = now.date()
        window_start = now
        window_end = now + timedelta(minutes=15)

        # ── Due soon (within 15 mins) ─────────────────────────────────────────
        due_soon = FollowUp.objects.filter(
            is_completed=False,
            follow_up_date=today,
        ).select_related('lead', 'agent')

        sent_due = 0
        for fup in due_soon:
            # Build datetime for this follow-up
            fup_dt = timezone.make_aware(
                datetime.combine(fup.follow_up_date, fup.follow_up_time)
            )
            if window_start <= fup_dt <= window_end:
                # Check we haven't already sent this reminder today
                already_sent = Notification.objects.filter(
                    recipient=fup.agent,
                    notification_type='follow_up_due',
                    related_lead_id=fup.lead.id,
                    created_at__date=today,
                ).exists()
                if not already_sent:
                    notify_follow_up_due(fup, fup.agent)
                    sent_due += 1

        # ── Overdue (send once per day) ───────────────────────────────────────
        overdue = FollowUp.objects.filter(
            is_completed=False,
            follow_up_date__lt=today,
        ).select_related('lead', 'agent')

        sent_overdue = 0
        for fup in overdue:
            already_sent_today = Notification.objects.filter(
                recipient=fup.agent,
                notification_type='follow_up_overdue',
                related_lead_id=fup.lead.id,
                created_at__date=today,
            ).exists()
            if not already_sent_today:
                notify_follow_up_overdue(fup, fup.agent)
                sent_overdue += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Reminders sent — Due soon: {sent_due}, Overdue: {sent_overdue}'
            )
        )
