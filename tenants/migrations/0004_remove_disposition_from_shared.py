from django.db import migrations


class Migration(migrations.Migration):
    """
    Remove the Disposition model from the shared (public) schema.
    Dispositions are now per-tenant, living in leads.Disposition
    inside each tenant's private schema.

    Run leads.0006_add_disposition_per_tenant FIRST on all tenant
    schemas before applying this migration.
    """

    dependencies = [
        ('tenants', '0003_disposition'),
    ]

    operations = [
        migrations.DeleteModel(
            name='Disposition',
        ),
    ]
