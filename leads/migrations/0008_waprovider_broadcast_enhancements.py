import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('leads', '0007_calllog_recording_url'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ── WAProvider ────────────────────────────────────────────────────────
        migrations.CreateModel(
            name='WAProvider',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('provider', models.CharField(choices=[
                    ('meta', 'Meta (WhatsApp Cloud API)'),
                    ('twilio', 'Twilio WhatsApp'),
                    ('wati', 'WATI'),
                    ('aisensy', 'AiSensy'),
                    ('interakt', 'Interakt'),
                ], max_length=20)),
                ('is_active', models.BooleanField(default=True)),
                ('is_default', models.BooleanField(default=False)),
                ('meta_phone_number_id', models.CharField(blank=True, max_length=200)),
                ('meta_access_token', models.TextField(blank=True)),
                ('meta_verify_token', models.CharField(blank=True, max_length=200)),
                ('twilio_account_sid', models.CharField(blank=True, max_length=200)),
                ('twilio_auth_token', models.CharField(blank=True, max_length=200)),
                ('twilio_from_number', models.CharField(blank=True, max_length=50)),
                ('wati_api_endpoint', models.URLField(blank=True, max_length=300)),
                ('wati_api_key', models.TextField(blank=True)),
                ('aisensy_api_key', models.TextField(blank=True)),
                ('interakt_api_key', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='wa_providers',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={'ordering': ['-is_default', 'name']},
        ),

        # ── WABroadcast — add new fields ─────────────────────────────────────
        migrations.AddField(
            model_name='wabroadcast',
            name='description',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='wabroadcast',
            name='message_type',
            field=models.CharField(
                choices=[('template', 'Template Message'), ('text', 'Plain Text Message')],
                default='template', max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='wabroadcast',
            name='text_body',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='wabroadcast',
            name='read_count',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='wabroadcast',
            name='replied_count',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='wabroadcast',
            name='provider',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='broadcasts', to='leads.waprovider',
            ),
        ),
        # Make template nullable (broadcasts can now use text_body instead)
        migrations.AlterField(
            model_name='wabroadcast',
            name='template',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='broadcasts', to='leads.watemplate',
            ),
        ),
        # Add 'cancelled' status choice (schema-only, no DB change for CharField)
        migrations.AddField(
            model_name='wabroadcast',
            name='cancelled_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
