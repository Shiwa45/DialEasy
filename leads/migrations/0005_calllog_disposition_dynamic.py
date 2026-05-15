from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Remove the hardcoded choices= constraint from CallLog.disposition and
    widen max_length from 20 → 50 so custom disposition slugs fit.

    Existing data is preserved — stored values like 'interested', 'callback'
    remain valid because the Disposition model (tenants.0003) seeds those
    same values into the DB.
    """

    dependencies = [
        ('leads', '0004_alter_waautoreply_id_alter_waautoreply_keywords_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='calllog',
            name='disposition',
            field=models.CharField(max_length=50),
        ),
    ]
