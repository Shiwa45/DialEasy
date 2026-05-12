# ai/migrations/0001_initial.py

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('leads', '0003_merge_0002_integration_models_0002_whatsapp_models'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CallTranscript',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('status', models.CharField(
                    choices=[('pending','Pending'),('processing','Processing'),('done','Done'),('failed','Failed')],
                    default='pending', max_length=20
                )),
                ('language', models.CharField(default='hi', max_length=10)),
                ('duration_seconds', models.IntegerField(blank=True, null=True)),
                ('full_text', models.TextField(blank=True, null=True)),
                ('segments', models.JSONField(blank=True, default=list)),
                ('summary', models.TextField(blank=True, null=True)),
                ('error_message', models.TextField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('call_log', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='transcript', to='leads.calllog'
                )),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='CallSentiment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('overall_sentiment', models.CharField(
                    choices=[('positive','Positive'),('neutral','Neutral'),('negative','Negative')],
                    default='neutral', max_length=20
                )),
                ('sentiment_score', models.FloatField(default=0.0)),
                ('customer_intent', models.CharField(blank=True, max_length=100, null=True)),
                ('objections_detected', models.JSONField(blank=True, default=list)),
                ('agent_talk_ratio', models.FloatField(blank=True, null=True)),
                ('filler_word_count', models.IntegerField(default=0)),
                ('interruptions_count', models.IntegerField(default=0)),
                ('best_moment', models.TextField(blank=True, null=True)),
                ('improvement_area', models.TextField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('transcript', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='sentiment', to='ai.calltranscript'
                )),
            ],
        ),
        migrations.CreateModel(
            name='EmailThread',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('thread_id', models.CharField(blank=True, max_length=200, null=True)),
                ('last_synced_at', models.DateTimeField(blank=True, null=True)),
                ('unread_count', models.IntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('lead', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='email_thread', to='leads.lead'
                )),
            ],
        ),
        migrations.CreateModel(
            name='EmailMessage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('message_id', models.CharField(blank=True, max_length=500, null=True, unique=True)),
                ('direction', models.CharField(choices=[('inbound','Inbound'),('outbound','Outbound')], max_length=10)),
                ('subject', models.CharField(blank=True, max_length=500, null=True)),
                ('from_address', models.EmailField(blank=True, null=True)),
                ('to_address', models.EmailField(blank=True, null=True)),
                ('body_text', models.TextField(blank=True, null=True)),
                ('body_html', models.TextField(blank=True, null=True)),
                ('ai_classification', models.CharField(
                    blank=True,
                    choices=[('inquiry','Inquiry'),('complaint','Complaint'),('follow_up','Follow-up'),
                             ('unsubscribe','Unsubscribe'),('other','Other')],
                    max_length=20, null=True
                )),
                ('ai_urgency_score', models.IntegerField(blank=True, null=True)),
                ('ai_summary', models.TextField(blank=True, null=True)),
                ('sent_at', models.DateTimeField(blank=True, null=True)),
                ('received_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('thread', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='messages', to='ai.emailthread'
                )),
                ('sent_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to=settings.AUTH_USER_MODEL
                )),
            ],
            options={'ordering': ['created_at']},
        ),
        migrations.CreateModel(
            name='ChatbotFlow',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=200)),
                ('is_active', models.BooleanField(default=True)),
                ('system_prompt', models.TextField()),
                ('escalation_keywords', models.TextField(default='human,agent,talk to someone,speak to person,manager')),
                ('max_turns_before_escalation', models.IntegerField(default=5)),
                ('qualification_questions', models.JSONField(default=list)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={'ordering': ['-is_active', '-created_at']},
        ),
        migrations.CreateModel(
            name='ChatbotSession',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('status', models.CharField(
                    choices=[('active','Active'),('escalated','Escalated to Human'),
                             ('qualified','Lead Qualified'),('ended','Ended')],
                    default='active', max_length=20
                )),
                ('turn_count', models.IntegerField(default=0)),
                ('history', models.JSONField(blank=True, default=list)),
                ('qualification_data', models.JSONField(blank=True, default=dict)),
                ('started_at', models.DateTimeField(auto_now_add=True)),
                ('ended_at', models.DateTimeField(blank=True, null=True)),
                ('conversation', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='chatbot_session', to='leads.waconversation'
                )),
                ('escalated_to', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='chatbot_escalations', to=settings.AUTH_USER_MODEL
                )),
                ('flow', models.ForeignKey(
                    null=True, on_delete=django.db.models.deletion.SET_NULL,
                    to='ai.chatbotflow'
                )),
            ],
            options={'ordering': ['-started_at']},
        ),
    ]
