from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('agents', '0005_agentprofile_last_heartbeat'),
    ]

    operations = [
        migrations.AddField(
            model_name='agentprofile',
            name='dialer_last_lead_id',
            field=models.IntegerField(blank=True, null=True),
        ),
    ]
