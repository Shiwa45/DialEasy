from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('agents', '0004_agentprofile_role'),
    ]

    operations = [
        migrations.AddField(
            model_name='agentprofile',
            name='last_heartbeat',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
