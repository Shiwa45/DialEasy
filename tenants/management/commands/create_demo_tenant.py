# tenants/management/commands/create_tenant.py
import os
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from tenants.models import Client, Domain, Plan, TenantSubscription

class Command(BaseCommand):
    help = 'Create a new tenant (Client) and assign a plan.'

    def add_arguments(self, parser):
        parser.add_argument('--name', type=str, default='Demo Company')
        parser.add_argument('--schema', type=str, default='demo')
        parser.add_argument('--domain', type=str, default='demo.localhost')
        parser.add_argument('--email', type=str, default='admin@demo.com')
        parser.add_argument('--plan', type=str, default='enterprise')

    def handle(self, *args, **options):
        name = options['name']
        schema_name = options['schema']
        domain_str = options['domain']
        email = options['email']
        plan_slug = options['plan']

        self.stdout.write(f'Creating tenant "{name}" with schema "{schema_name}"...')

        # 1. Create the Client
        tenant, created = Client.objects.get_or_create(
            schema_name=schema_name,
            defaults={
                'name': name,
                'owner_email': email,
                'is_active': True,
            }
        )

        if not created:
            self.stdout.write(self.style.WARNING(f'  - Tenant with schema "{schema_name}" already exists.'))
        else:
            self.stdout.write(self.style.SUCCESS(f'  [OK] Created tenant: {name}'))

        # 2. Create the Domain
        domain, created = Domain.objects.get_or_create(
            domain=domain_str,
            defaults={
                'tenant': tenant,
                'is_primary': True,
            }
        )
        if not created:
            self.stdout.write(self.style.WARNING(f'  - Domain "{domain_str}" already exists.'))
        else:
            self.stdout.write(self.style.SUCCESS(f'  [OK] Created domain: {domain_str}'))

        # 3. Assign Plan
        try:
            plan = Plan.objects.get(slug=plan_slug)
            subscription, created = TenantSubscription.objects.get_or_create(
                tenant=tenant,
                plan=plan,
                defaults={
                    'status': 'active',
                    'is_active': True,
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'  [OK] Assigned "{plan.name}" plan.'))
        except Plan.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'  ! Plan "{plan_slug}" not found. Run create_public_tenant first.'))

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('Tenant setup complete!'))
        self.stdout.write(f'To access this tenant, use: http://{domain_str}:8000/admin/')
        
        # Note: The admin user (admin_{schema_name}) was automatically created 
        # via the Client model's save() method, along with their AgentProfile.
        
        self.stdout.write(f'Admin Username: admin_{schema_name}')
        self.stdout.write('Admin Password: password123 (Change this immediately!)')
        self.stdout.write(f'Note: You may need to add "{domain_str}" to your hosts file if using subdomains.')
