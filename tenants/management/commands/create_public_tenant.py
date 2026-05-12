# tenants/management/commands/create_public_tenant.py
# ─────────────────────────────────────────────────────────────────────────────
# Run ONCE after first migration to set up the public schema tenant.
#
#   python manage.py create_public_tenant --domain=localhost
#
# This also seeds the default Feature list and starter Plans.
# ─────────────────────────────────────────────────────────────────────────────

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from tenants.models import Client, Domain, Feature, Plan


FEATURES = [
    # slug, name, description
    ('lead_management',     'Lead Management',          'Core lead CRUD, assignment, CSV upload'),
    ('call_logging',        'Call Logging',             'Log calls with disposition and remarks'),
    ('follow_ups',          'Follow-Ups',               'Schedule and manage follow-up reminders'),
    ('auto_dialer',         'Auto Dialer',              'Auto-dialing queue for telecallers'),
    ('basic_reports',       'Basic Reports',            'Dashboard metrics and agent stats'),
    ('integrations_basic',  'Basic Integrations',       'IndiaMart, JustDial, Meta lead webhooks'),
    ('whatsapp_api',        'WhatsApp API',             'Full WhatsApp Cloud API — send/receive messages, templates, broadcasts'),
    ('call_recording',      'Call Recording',           'Record and store agent calls'),
    ('advanced_reports',    'Advanced Reports',         'Full analytics: funnel, revenue pipeline, agent leaderboard, exports'),
    ('lead_scoring',        'Lead Scoring',             'Auto-calculate lead scores based on engagement'),
    ('deal_pipeline',       'Deal Pipeline',            'Deal value tracking and pipeline view'),
    ('products',            'Products Catalogue',       'Link products to leads and track interest'),
    ('tasks',               'Tasks',                    'Create and assign tasks linked to leads'),
    ('bulk_broadcast',      'Bulk WA Broadcast',        'Send WhatsApp template messages to filtered lead segments'),
    ('email_ai',            'Email AI',                 'AI email drafting and classification'),
    ('ai_chatbot',          'AI Chatbot',               'LLM-powered WhatsApp chatbot for lead qualification'),
    ('ai_transcription',    'AI Call Transcription',    'Transcribe call recordings using Whisper AI'),
    ('call_sentiment',      'Call Sentiment Analysis',  'AI sentiment and intent analysis on call transcripts'),
    ('cloud_recording',     'Cloud Call Recording',     'Store recordings on S3/GCS with playback'),
    ('notifications_push',  'Push Notifications',       'FCM push notifications for agents'),
]

PLANS = [
    # (name, slug, price_monthly, price_annual, max_agents, max_leads, feature_slugs, sort)
    (
        'Free', 'free', 0, 0, 2, 200, 0,
        ['lead_management', 'call_logging', 'follow_ups', 'basic_reports']
    ),
    (
        'Starter', 'starter', 999, 9990, 10, 2000, 1,
        ['lead_management', 'call_logging', 'follow_ups', 'auto_dialer',
         'basic_reports', 'integrations_basic', 'call_recording', 'tasks']
    ),
    (
        'Pro', 'pro', 2499, 24990, 30, 20000, 2,
        ['lead_management', 'call_logging', 'follow_ups', 'auto_dialer',
         'basic_reports', 'integrations_basic', 'call_recording', 'tasks',
         'whatsapp_api', 'advanced_reports', 'lead_scoring', 'deal_pipeline',
         'products', 'bulk_broadcast', 'notifications_push', 'cloud_recording']
    ),
    (
        'Enterprise', 'enterprise', 4999, 49990, -1, -1, 3,
        [f[0] for f in FEATURES]  # All features
    ),
]


class Command(BaseCommand):
    help = 'Create the public tenant, seed default features and plans.'

    def add_arguments(self, parser):
        parser.add_argument('--domain', default='localhost', help='Primary domain for the public tenant')
        parser.add_argument('--skip-plans', action='store_true', help='Skip seeding plans and features')

    def handle(self, *args, **options):
        domain_name = options['domain']

        # ── 1. Create public tenant ───────────────────────────────────────────
        self.stdout.write(self.style.MIGRATE_HEADING('Creating public tenant...'))

        public_tenant, created = Client.objects.get_or_create(
            schema_name='public',
            defaults={
                'name': 'TeleCRM Super Admin',
                'owner_email': 'admin@telecrm.com',
                'is_active': True,
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS('  OK Public tenant created.'))
        else:
            self.stdout.write('  - Public tenant already exists.')

        # ── 2. Create domain ─────────────────────────────────────────────────
        domain, created = Domain.objects.get_or_create(
            domain=domain_name,
            defaults={'tenant': public_tenant, 'is_primary': True}
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'  OK Domain "{domain_name}" created for public tenant.'))
        else:
            self.stdout.write(f'  - Domain "{domain_name}" already exists.')

        if options['skip_plans']:
            self.stdout.write(self.style.WARNING('Skipping plan/feature seeding.'))
            return

        # ── 3. Seed Features ─────────────────────────────────────────────────
        self.stdout.write(self.style.MIGRATE_HEADING('\nSeeding features...'))
        feature_objects = {}

        for slug, name, description in FEATURES:
            feature, created = Feature.objects.get_or_create(
                slug=slug,
                defaults={'name': name, 'description': description, 'is_active': True}
            )
            feature_objects[slug] = feature
            status = '✓ Created' if created else '— Exists'
            self.stdout.write(f'  {status}: {name}')

        # ── 4. Seed Plans ─────────────────────────────────────────────────────
        self.stdout.write(self.style.MIGRATE_HEADING('\nSeeding plans...'))

        for name, slug, price_m, price_a, max_agents, max_leads, sort_order, feature_slugs in PLANS:
            plan, created = Plan.objects.get_or_create(
                slug=slug,
                defaults={
                    'name': name,
                    'price_monthly': price_m,
                    'price_annual': price_a,
                    'max_agents': max_agents,
                    'max_leads': max_leads,
                    'sort_order': sort_order,
                    'is_active': True,
                    'is_public': slug != 'enterprise',
                }
            )
            # Assign features
            plan.features.set([feature_objects[s] for s in feature_slugs if s in feature_objects])
            status = '✓ Created' if created else '~ Updated'
            self.stdout.write(self.style.SUCCESS(f'  {status}: {name} plan ({len(feature_slugs)} features)'))

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('Phase 0 setup complete!'))
        self.stdout.write('')
        self.stdout.write('Next steps:')
        self.stdout.write('  1. Create a superuser:  python manage.py createsuperuser')
        self.stdout.write('  2. Create your first tenant via Django admin or:')
        self.stdout.write('     python manage.py create_tenant')
        self.stdout.write('')
