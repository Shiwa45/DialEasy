# leads/migrations/0001_initial.py
# Fresh migration — replaces all old SQLite migrations

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ── Lead ──────────────────────────────────────────────────────────────
        migrations.CreateModel(
            name='Lead',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=200)),
                ('phone', models.CharField(max_length=20, unique=True)),
                ('email', models.EmailField(blank=True, null=True)),
                ('company', models.CharField(blank=True, max_length=200, null=True)),
                ('status', models.CharField(
                    choices=[
                        ('new','New'),('contacted','Contacted'),('interested','Interested'),
                        ('not_interested','Not Interested'),('callback','Callback Later'),
                        ('wrong_number','Wrong Number'),('not_reachable','Not Reachable'),
                        ('converted','Converted'),('lost','Lost'),
                    ],
                    default='new', max_length=20
                )),
                ('source', models.CharField(blank=True, max_length=100, null=True)),
                ('notes', models.TextField(blank=True, null=True)),
                ('lead_score', models.IntegerField(default=0)),
                ('deal_value', models.DecimalField(decimal_places=2, max_digits=12, null=True, blank=True)),
                ('city', models.CharField(blank=True, max_length=100, null=True)),
                ('state', models.CharField(blank=True, max_length=100, null=True)),
                ('address', models.TextField(blank=True, null=True)),
                ('website', models.URLField(blank=True, null=True)),
                ('designation', models.CharField(blank=True, max_length=100, null=True)),
                ('industry', models.CharField(blank=True, max_length=100, null=True)),
                ('expected_close_date', models.DateField(null=True, blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('assigned_agent', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='assigned_leads', to=settings.AUTH_USER_MODEL
                )),
            ],
            options={'ordering': ['-lead_score', '-created_at']},
        ),

        # ── CallLog ───────────────────────────────────────────────────────────
        migrations.CreateModel(
            name='CallLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('call_date', models.DateTimeField(default=django.utils.timezone.now)),
                ('duration', models.DurationField(blank=True, null=True)),
                ('disposition', models.CharField(
                    choices=[
                        ('interested','Interested'),('not_interested','Not Interested'),
                        ('callback','Callback Later'),('wrong_number','Wrong Number'),
                        ('not_reachable','Not Reachable'),('busy','Busy'),
                        ('voicemail','Voicemail'),('follow_up','Follow-up Required'),
                    ],
                    max_length=20
                )),
                ('remarks', models.TextField(blank=True, null=True)),
                ('recording', models.FileField(blank=True, null=True, upload_to='call_recordings/')),
                ('recording_size', models.IntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('agent', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='call_logs', to=settings.AUTH_USER_MODEL)),
                ('lead', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='call_logs', to='leads.lead')),
            ],
            options={'ordering': ['-call_date']},
        ),

        # ── FollowUp ──────────────────────────────────────────────────────────
        migrations.CreateModel(
            name='FollowUp',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('title', models.CharField(blank=True, max_length=200, null=True)),
                ('priority', models.CharField(
                    choices=[('low','Low'),('medium','Medium'),('high','High'),('urgent','Urgent')],
                    default='medium', max_length=10
                )),
                ('follow_up_date', models.DateField()),
                ('follow_up_time', models.TimeField()),
                ('remarks', models.TextField(blank=True, null=True)),
                ('is_completed', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('agent', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='follow_ups', to=settings.AUTH_USER_MODEL)),
                ('lead', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='follow_ups', to='leads.lead')),
            ],
            options={'ordering': ['follow_up_date', 'follow_up_time']},
        ),

        # ── LeadNote ──────────────────────────────────────────────────────────
        migrations.CreateModel(
            name='LeadNote',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('note_type', models.CharField(
                    choices=[
                        ('general','General'),('call','Call Summary'),('meeting','Meeting'),
                        ('email','Email'),('whatsapp','WhatsApp'),('internal','Internal (Private)'),
                    ],
                    default='general', max_length=20
                )),
                ('content', models.TextField()),
                ('is_pinned', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('author', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='lead_notes', to=settings.AUTH_USER_MODEL)),
                ('lead', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lead_notes', to='leads.lead')),
            ],
            options={'ordering': ['-is_pinned', '-created_at']},
        ),

        # ── LeadTask ──────────────────────────────────────────────────────────
        migrations.CreateModel(
            name='LeadTask',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('title', models.CharField(max_length=300)),
                ('description', models.TextField(blank=True, null=True)),
                ('priority', models.CharField(
                    choices=[('low','Low'),('medium','Medium'),('high','High'),('urgent','Urgent')],
                    default='medium', max_length=10
                )),
                ('status', models.CharField(
                    choices=[('pending','Pending'),('in_progress','In Progress'),('done','Done'),('cancelled','Cancelled')],
                    default='pending', max_length=20
                )),
                ('due_date', models.DateTimeField(blank=True, null=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('lead', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tasks', to='leads.lead')),
                ('assigned_to', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='lead_tasks', to=settings.AUTH_USER_MODEL)),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_tasks', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-priority', 'due_date']},
        ),

        # ── Product ───────────────────────────────────────────────────────────
        migrations.CreateModel(
            name='Product',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=200)),
                ('sku', models.CharField(blank=True, max_length=100, null=True, unique=True)),
                ('description', models.TextField(blank=True, null=True)),
                ('price', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('unit', models.CharField(blank=True, max_length=50, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={'ordering': ['name']},
        ),

        # ── LeadProduct ───────────────────────────────────────────────────────
        migrations.CreateModel(
            name='LeadProduct',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('quantity', models.PositiveIntegerField(default=1)),
                ('discount_percent', models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ('note', models.CharField(blank=True, max_length=300, null=True)),
                ('added_at', models.DateTimeField(auto_now_add=True)),
                ('lead', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lead_products', to='leads.lead')),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lead_products', to='leads.product')),
                ('added_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={'unique_together': {('lead', 'product')}},
        ),

        # ── LeadActivity ──────────────────────────────────────────────────────
        migrations.CreateModel(
            name='LeadActivity',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('activity_type', models.CharField(
                    choices=[
                        ('created','Lead Created'),('status_changed','Status Changed'),
                        ('assigned','Lead Assigned'),('call_logged','Call Logged'),
                        ('note_added','Note Added'),('note_edited','Note Edited'),
                        ('follow_up_created','Follow-up Created'),('follow_up_completed','Follow-up Completed'),
                        ('task_created','Task Created'),('task_completed','Task Completed'),
                        ('product_added','Product Added'),('product_removed','Product Removed'),
                        ('deal_value_updated','Deal Value Updated'),
                        ('whatsapp_sent','WhatsApp Sent'),('whatsapp_received','WhatsApp Received'),
                        ('field_updated','Field Updated'),
                    ],
                    max_length=30
                )),
                ('description', models.TextField()),
                ('old_value', models.CharField(blank=True, max_length=500, null=True)),
                ('new_value', models.CharField(blank=True, max_length=500, null=True)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('actor', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='lead_activities', to=settings.AUTH_USER_MODEL)),
                ('lead', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='activities', to='leads.lead')),
            ],
            options={'ordering': ['-created_at']},
        ),

        # ── AssignmentRule ────────────────────────────────────────────────────
        migrations.CreateModel(
            name='AssignmentRule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('name', models.CharField(default='Default Rule', max_length=100)),
                ('strategy', models.CharField(
                    choices=[
                        ('round_robin','Round Robin'),('load_balanced','Load Balanced'),
                        ('source_based','Source Based'),('manual','Manual'),
                    ],
                    default='round_robin', max_length=20
                )),
                ('is_active', models.BooleanField(default=True)),
                ('source_routing', models.JSONField(blank=True, default=dict)),
                ('last_assigned_agent_id', models.IntegerField(blank=True, null=True)),
                ('eligible_agents', models.ManyToManyField(blank=True, related_name='assignment_rules', to=settings.AUTH_USER_MODEL)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={'ordering': ['-is_active', '-created_at']},
        ),

        # ── LeadUpload (unchanged) ────────────────────────────────────────────
        migrations.CreateModel(
            name='LeadUpload',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('file', models.FileField(upload_to='lead_uploads/')),
                ('status', models.CharField(
                    choices=[('pending','Pending'),('processing','Processing'),('completed','Completed'),('failed','Failed')],
                    default='pending', max_length=20
                )),
                ('total_records', models.IntegerField(default=0)),
                ('processed_records', models.IntegerField(default=0)),
                ('failed_records', models.IntegerField(default=0)),
                ('error_log', models.TextField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('uploaded_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
