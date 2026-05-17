from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tenants', '0005_add_max_agents_override_to_client'),
    ]

    operations = [
        migrations.AddField(
            model_name='client',
            name='extra_features',
            field=models.ManyToManyField(
                blank=True,
                help_text='Features granted directly to this tenant (in addition to their plan).',
                related_name='direct_tenants',
                to='tenants.feature',
            ),
        ),
    ]
