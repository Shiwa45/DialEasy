# tenants_api/management/commands/setup_central_api_domain.py
# ─────────────────────────────────────────────────────────────────────────────
# One-time setup command: registers api.dialeasy.easyian.com (or any custom
# domain) in the Domain table pointing to the PUBLIC schema Client.
#
# This allows TenantMainMiddleware to accept requests from the central API
# domain and route them to the public schema, where CentralApiTenantMiddleware
# then takes over and switches to the correct tenant schema.
#
# Usage:
#   python manage.py setup_central_api_domain
#   python manage.py setup_central_api_domain --domain api.mycrm.com
#   python manage.py setup_central_api_domain --domain api.mycrm.com --force
# ─────────────────────────────────────────────────────────────────────────────

from django.core.management.base import BaseCommand, CommandError
from django.db import connection


class Command(BaseCommand):
    help = (
        "Register the central API domain in the Domain table so that "
        "TenantMainMiddleware routes it to the public schema. "
        "Run this once after deployment."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--domain",
            default="api.dialeasy.easyian.com",
            help="The central API hostname to register (default: api.dialeasy.easyian.com)",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Re-create the domain entry even if it already exists.",
        )

    def handle(self, *args, **options):
        from tenants.models import Client, Domain

        domain_name = options["domain"].strip().lower()
        force       = options["force"]

        self.stdout.write(self.style.MIGRATE_HEADING(
            f"\n=== DialEasy Central API Domain Setup ==="
        ))
        self.stdout.write(f"  Target domain : {domain_name}")

        # ── 1. Find or create the public-schema Client ────────────────────────
        try:
            public_client = Client.objects.get(schema_name="public")
            self.stdout.write(f"  Public tenant : {public_client.name} (schema=public) ✓")
        except Client.DoesNotExist:
            raise CommandError(
                "No Client with schema_name='public' found. "
                "Make sure the public tenant exists (it's created by django-tenants "
                "automatically during initial migrations). "
                "If missing, run: python manage.py create_tenant --schema_name=public"
            )

        # ── 2. Check for existing Domain entry ────────────────────────────────
        existing = Domain.objects.filter(domain=domain_name).first()

        if existing and not force:
            self.stdout.write(self.style.WARNING(
                f"  Domain '{domain_name}' already registered "
                f"(tenant: {existing.tenant.schema_name}). "
                f"Use --force to overwrite."
            ))
            return

        if existing and force:
            self.stdout.write(self.style.WARNING(
                f"  --force: removing existing entry for '{domain_name}'..."
            ))
            existing.delete()

        # ── 3. Create Domain entry ────────────────────────────────────────────
        Domain.objects.create(
            domain=domain_name,
            tenant=public_client,
            is_primary=False,  # Primary domain stays as the admin domain
        )

        self.stdout.write(self.style.SUCCESS(
            f"\n  ✅ Domain '{domain_name}' registered → public schema.\n"
            f"\n  Next steps:"
            f"\n    1. Add DNS A record: {domain_name} → <your server IP>"
            f"\n    2. Get SSL cert:    certbot --nginx -d {domain_name}"
            f"\n    3. Add Nginx block: see deploy/nginx_central_api.conf"
            f"\n    4. Restart Nginx:   sudo systemctl reload nginx"
            f"\n    5. Test:           curl https://{domain_name}/mobile/health/"
        ))
