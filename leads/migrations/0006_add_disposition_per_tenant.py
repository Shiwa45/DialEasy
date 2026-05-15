from django.db import migrations, models


DEFAULT_DISPOSITIONS = [
    # (value, label, color, sort_order, triggers_follow_up, updates_lead_status)
    ('interested',     'Interested',         'success', 1,  True,  'interested'),
    ('callback',       'Callback Later',      'warning', 2,  True,  'callback'),
    ('not_interested', 'Not Interested',      'danger',  3,  False, 'not_interested'),
    ('not_reachable',  'Not Reachable',       'default', 4,  False, ''),
    ('busy',           'Busy',                'default', 5,  False, ''),
    ('wrong_number',   'Wrong Number',        'danger',  6,  False, ''),
    ('voicemail',      'Voicemail',           'info',    7,  False, ''),
    ('follow_up',      'Follow-up Required',  'warning', 8,  True,  ''),
]


def seed_dispositions(apps, schema_editor):
    Disposition = apps.get_model('leads', 'Disposition')
    for value, label, color, sort_order, triggers_follow_up, updates_lead_status in DEFAULT_DISPOSITIONS:
        Disposition.objects.get_or_create(
            value=value,
            defaults={
                'label': label,
                'color': color,
                'sort_order': sort_order,
                'is_active': True,
                'triggers_follow_up': triggers_follow_up,
                'updates_lead_status': updates_lead_status,
            }
        )


class Migration(migrations.Migration):

    dependencies = [
        ('leads', '0005_calllog_disposition_dynamic'),
    ]

    operations = [
        migrations.CreateModel(
            name='Disposition',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('label', models.CharField(
                    help_text='Human-readable label shown to agents. e.g. "Interested"',
                    max_length=100,
                )),
                ('value', models.SlugField(
                    help_text='Machine-readable key stored in call logs. e.g. "interested".',
                    max_length=50,
                    unique=True,
                )),
                ('color', models.CharField(
                    choices=[
                        ('default', 'Grey (Default)'),
                        ('success', 'Green (Positive)'),
                        ('warning', 'Orange (Neutral)'),
                        ('danger',  'Red (Negative)'),
                        ('info',    'Blue (Info)'),
                    ],
                    default='default',
                    max_length=10,
                )),
                ('is_active', models.BooleanField(default=True)),
                ('sort_order', models.IntegerField(default=0)),
                ('triggers_follow_up', models.BooleanField(default=False)),
                ('updates_lead_status', models.CharField(blank=True, max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Disposition',
                'verbose_name_plural': 'Dispositions',
                'ordering': ['sort_order', 'label'],
                'app_label': 'leads',
            },
        ),
        migrations.RunPython(seed_dispositions, migrations.RunPython.noop),
    ]
