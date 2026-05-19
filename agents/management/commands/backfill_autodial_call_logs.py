from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django_tenants.utils import schema_context

from agents.models import AgentProfile, CallActivityEvent
from leads.models import CallLog
from tenants.models import Client


AUTODIAL_STARTED_DISPOSITION = "autodial_started"


class Command(BaseCommand):
    help = (
        "Backfill missing CallLog rows from historical autodial call_started "
        "events so agent/lead call counts match actual dial attempts."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Write changes. Without this flag the command only reports counts.",
        )
        parser.add_argument(
            "--schema",
            help="Limit repair to one tenant schema.",
        )
        parser.add_argument(
            "--agent-id",
            type=int,
            help="Limit repair to one auth_user id.",
        )
        parser.add_argument(
            "--match-window-minutes",
            type=int,
            default=30,
            help="Window for linking an existing unlinked CallLog to a call_started event.",
        )

    def handle(self, *args, **options):
        apply_changes = options["apply"]
        schema_filter = options.get("schema")
        agent_id = options.get("agent_id")
        window = timedelta(minutes=options["match_window_minutes"])

        schemas = Client.objects.exclude(schema_name="public").values_list("schema_name", flat=True)
        if schema_filter:
            schemas = [schema_filter]

        grand_created = 0
        grand_linked = 0
        grand_skipped_no_lead = 0

        for schema_name in schemas:
            with schema_context(schema_name):
                events = CallActivityEvent.objects.filter(
                    event_type="call_started",
                    call_log__isnull=True,
                ).select_related("agent", "lead").order_by("timestamp", "id")

                if agent_id:
                    events = events.filter(agent_id=agent_id)

                created = 0
                linked = 0
                skipped_no_lead = 0

                with transaction.atomic():
                    for event in events:
                        if not event.lead_id:
                            skipped_no_lead += 1
                            continue

                        existing = (
                            CallLog.objects
                            .filter(
                                agent_id=event.agent_id,
                                lead_id=event.lead_id,
                                call_date__gte=event.timestamp - window,
                                call_date__lte=event.timestamp + window,
                            )
                            .exclude(activity_events__event_type="call_started")
                            .order_by("call_date", "id")
                            .first()
                        )

                        if existing:
                            linked += 1
                            if apply_changes:
                                event.call_log = existing
                                event.save(update_fields=["call_log"])
                            continue

                        created += 1
                        if apply_changes:
                            call_log = CallLog.objects.create(
                                lead_id=event.lead_id,
                                agent_id=event.agent_id,
                                call_date=event.timestamp,
                                disposition=AUTODIAL_STARTED_DISPOSITION,
                                remarks="Backfilled from autodial call_started event",
                            )
                            event.call_log = call_log
                            event.save(update_fields=["call_log"])

                    if not apply_changes:
                        transaction.set_rollback(True)

                if apply_changes:
                    profiles = AgentProfile.objects.all()
                    if agent_id:
                        profiles = profiles.filter(user_id=agent_id)
                    for profile in profiles:
                        profile.update_stats()

                grand_created += created
                grand_linked += linked
                grand_skipped_no_lead += skipped_no_lead
                mode = "APPLIED" if apply_changes else "DRY RUN"
                self.stdout.write(
                    f"{mode} schema={schema_name}: create={created}, "
                    f"link_existing={linked}, skipped_no_lead={skipped_no_lead}"
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. create={grand_created}, link_existing={grand_linked}, "
                f"skipped_no_lead={grand_skipped_no_lead}"
            )
        )
