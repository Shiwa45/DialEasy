from django.db import migrations


DEFAULT_FEATURES = [
    {
        'name': 'WhatsApp API',
        'slug': 'whatsapp_api',
        'description': 'Send and receive WhatsApp messages via the official Meta Cloud API or third-party providers.',
    },
    {
        'name': 'Bulk WhatsApp Campaigns',
        'slug': 'bulk_whatsapp',
        'description': 'Send bulk WhatsApp messages to large lead lists using campaigns. Supports Meta, Twilio, WATI, AiSensy, and Interakt.',
    },
    {
        'name': 'Call Recordings',
        'slug': 'call_recording',
        'description': 'Record and store agent call audio. Agents can upload recordings and managers can review them.',
    },
    {
        'name': 'AI Transcription',
        'slug': 'ai_transcription',
        'description': 'Automatically transcribe call recordings using AI.',
    },
    {
        'name': 'Call Sentiment Analysis',
        'slug': 'call_sentiment',
        'description': 'AI-powered sentiment analysis on call transcripts to gauge customer interest.',
    },
    {
        'name': 'Email AI',
        'slug': 'email_ai',
        'description': 'AI-assisted email drafting and sending to leads.',
    },
    {
        'name': 'AI Chatbot',
        'slug': 'ai_chatbot',
        'description': 'Automated AI chatbot for engaging leads via WhatsApp.',
    },
    {
        'name': 'Advanced Reports',
        'slug': 'advanced_reports',
        'description': 'In-depth analytics: agent performance, lead funnel, conversion reports, and custom date ranges.',
    },
]


def seed_features(apps, schema_editor):
    Feature = apps.get_model('tenants', 'Feature')
    for data in DEFAULT_FEATURES:
        Feature.objects.get_or_create(
            slug=data['slug'],
            defaults={'name': data['name'], 'description': data['description'], 'is_active': True},
        )


def remove_seeded_features(apps, schema_editor):
    Feature = apps.get_model('tenants', 'Feature')
    slugs = [f['slug'] for f in DEFAULT_FEATURES]
    Feature.objects.filter(slug__in=slugs).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('tenants', '0006_client_extra_features'),
    ]

    operations = [
        migrations.RunPython(seed_features, remove_seeded_features),
    ]
