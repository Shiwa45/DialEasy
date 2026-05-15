from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('leads', '0006_add_disposition_per_tenant'),
    ]

    operations = [
        migrations.AddField(
            model_name='calllog',
            name='recording_url',
            field=models.URLField(blank=True, max_length=500, null=True),
        ),
    ]
