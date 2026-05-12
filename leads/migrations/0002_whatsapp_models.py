# leads/migrations/0002_whatsapp_models.py

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('leads', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [

        # ── WATemplate ────────────────────────────────────────────────────────
        migrations.CreateModel(
            name='WATemplate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=200)),
                ('display_name', models.CharField(max_length=200)),
                ('category', models.CharField(
                    choices=[('marketing','Marketing'),('utility','Utility'),('authentication','Authentication')],
                    default='utility', max_length=20
                )),
                ('language_code', models.CharField(default='en_US', max_length=20)),
                ('status', models.CharField(
                    choices=[('pending','Pending Approval'),('approved','Approved'),('rejected','Rejected'),('paused','Paused')],
                    default='pending', max_length=20
                )),
                ('body_text', models.TextField()),
                ('header_text', models.CharField(blank=True, max_length=300, null=True)),
                ('footer_text', models.CharField(blank=True, max_length=300, null=True)),
                ('variable_mapping', models.JSONField(blank=True, default=dict)),
                ('buttons', models.JSONField(blank=True, default=list)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(
                    null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='wa_templates', to=settings.AUTH_USER_MODEL
                )),
            ],
            options={'ordering': ['display_name']},
        ),

        # ── WAConversation ────────────────────────────────────────────────────
        migrations.CreateModel(
            name='WAConversation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('status', models.CharField(
                    choices=[('open','Open'),('closed','Closed'),('bot','Bot Handling'),('waiting','Waiting for Reply')],
                    default='open', max_length=20
                )),
                ('is_opted_out', models.BooleanField(default=False)),
                ('last_message_at', models.DateTimeField(blank=True, null=True)),
                ('unread_count', models.IntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('lead', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='wa_conversation', to='leads.lead'
                )),
                ('assigned_agent', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='wa_conversations', to=settings.AUTH_USER_MODEL
                )),
            ],
            options={'ordering': ['-last_message_at']},
        ),

        # ── WAMessage ─────────────────────────────────────────────────────────
        migrations.CreateModel(
            name='WAMessage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('wa_message_id', models.CharField(blank=True, db_index=True, max_length=200, null=True)),
                ('direction', models.CharField(choices=[('inbound','Inbound'),('outbound','Outbound')], max_length=10)),
                ('message_type', models.CharField(
                    choices=[
                        ('text','Text'),('image','Image'),('document','Document'),
                        ('audio','Audio'),('video','Video'),('template','Template'),
                        ('interactive','Interactive (Button/List)'),('sticker','Sticker'),('location','Location'),
                    ],
                    default='text', max_length=20
                )),
                ('status', models.CharField(
                    choices=[
                        ('pending','Pending'),('sent','Sent'),('delivered','Delivered'),
                        ('read','Read'),('failed','Failed'),('received','Received'),
                    ],
                    default='pending', max_length=20
                )),
                ('body', models.TextField(blank=True, null=True)),
                ('media_url', models.URLField(blank=True, null=True)),
                ('media_id', models.CharField(blank=True, max_length=200, null=True)),
                ('media_mime_type', models.CharField(blank=True, max_length=100, null=True)),
                ('media_filename', models.CharField(blank=True, max_length=300, null=True)),
                ('caption', models.TextField(blank=True, null=True)),
                ('sent_at', models.DateTimeField(blank=True, null=True)),
                ('delivered_at', models.DateTimeField(blank=True, null=True)),
                ('read_at', models.DateTimeField(blank=True, null=True)),
                ('failed_reason', models.TextField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('conversation', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='messages', to='leads.waconversation'
                )),
                ('template', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='sent_messages', to='leads.watemplate'
                )),
                ('sent_by', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='wa_messages_sent', to=settings.AUTH_USER_MODEL
                )),
            ],
            options={'ordering': ['created_at']},
        ),

        # ── WABroadcast ───────────────────────────────────────────────────────
        migrations.CreateModel(
            name='WABroadcast',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=200)),
                ('status', models.CharField(
                    choices=[('draft','Draft'),('queued','Queued'),('running','Running'),
                             ('completed','Completed'),('paused','Paused'),('failed','Failed')],
                    default='draft', max_length=20
                )),
                ('lead_filter', models.JSONField(default=dict)),
                ('total_leads', models.IntegerField(default=0)),
                ('sent_count', models.IntegerField(default=0)),
                ('delivered_count', models.IntegerField(default=0)),
                ('failed_count', models.IntegerField(default=0)),
                ('opted_out_skipped', models.IntegerField(default=0)),
                ('scheduled_at', models.DateTimeField(blank=True, null=True)),
                ('started_at', models.DateTimeField(blank=True, null=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('template', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='broadcasts', to='leads.watemplate'
                )),
                ('created_by', models.ForeignKey(
                    null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='wa_broadcasts', to=settings.AUTH_USER_MODEL
                )),
            ],
            options={'ordering': ['-created_at']},
        ),

        # ── WABroadcastRecipient ──────────────────────────────────────────────
        migrations.CreateModel(
            name='WABroadcastRecipient',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('status', models.CharField(
                    choices=[('pending','Pending'),('sent','Sent'),('delivered','Delivered'),
                             ('read','Read'),('failed','Failed'),('skipped','Skipped (opted-out)')],
                    default='pending', max_length=20
                )),
                ('wa_message_id', models.CharField(blank=True, max_length=200, null=True)),
                ('error_message', models.TextField(blank=True, null=True)),
                ('sent_at', models.DateTimeField(blank=True, null=True)),
                ('broadcast', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='recipients', to='leads.wabroadcast'
                )),
                ('lead', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='broadcast_receipts', to='leads.lead'
                )),
            ],
            options={
                'ordering': ['id'],
                'unique_together': {('broadcast', 'lead')},
            },
        ),

        # ── WAAutoReply ───────────────────────────────────────────────────────
        migrations.CreateModel(
            name='WAAutoReply',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=200)),
                ('is_active', models.BooleanField(default=True)),
                ('priority', models.IntegerField(default=0)),
                ('keywords', models.TextField()),
                ('match_exact', models.BooleanField(default=False)),
                ('action', models.CharField(
                    choices=[('send_text','Send Text Message'),('send_template','Send Template Message'),
                             ('assign_agent','Assign to Agent'),('update_lead_status','Update Lead Status'),
                             ('escalate','Escalate to Human Agent')],
                    default='send_text', max_length=30
                )),
                ('reply_text', models.TextField(blank=True, null=True)),
                ('lead_status_update', models.CharField(blank=True, max_length=20, null=True)),
                ('stop_processing', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('reply_template', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='auto_reply_rules', to='leads.watemplate'
                )),
                ('assign_to_agent', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='wa_auto_reply_assignments', to=settings.AUTH_USER_MODEL
                )),
            ],
            options={'ordering': ['priority', 'id']},
        ),
    ]
