# tenants/migrations/0001_initial.py

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models
import django_tenants.postgresql_backend.base


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Feature',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('slug', models.SlugField(max_length=100, unique=True, help_text='Machine-readable key e.g. whatsapp_api')),
                ('description', models.TextField(blank=True)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Feature',
                'verbose_name_plural': 'Features',
                'ordering': ['name'],
                'app_label': 'tenants',
            },
        ),
        migrations.CreateModel(
            name='Client',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('schema_name', models.CharField(max_length=63, unique=True, validators=[django_tenants.postgresql_backend.base._check_schema_name])),
                ('name', models.CharField(max_length=200)),
                ('owner_email', models.EmailField()),
                ('phone', models.CharField(blank=True, max_length=20)),
                ('address', models.TextField(blank=True)),
                ('logo', models.ImageField(blank=True, null=True, upload_to='tenant_logos/')),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Tenant',
                'verbose_name_plural': 'Tenants',
                'app_label': 'tenants',
            },
            bases=(django_tenants.models.TenantMixin, models.Model),
        ),
        migrations.CreateModel(
            name='Domain',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('domain', models.CharField(db_index=True, max_length=253, unique=True)),
                ('is_primary', models.BooleanField(db_index=True, default=True)),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='domains', to='tenants.client')),
            ],
            options={
                'verbose_name': 'Domain',
                'verbose_name_plural': 'Domains',
                'app_label': 'tenants',
            },
            bases=(django_tenants.models.DomainMixin, models.Model),
        ),
        migrations.CreateModel(
            name='Plan',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('slug', models.SlugField(max_length=100, unique=True)),
                ('description', models.TextField(blank=True)),
                ('price_monthly', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('price_annual', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('max_agents', models.IntegerField(default=5)),
                ('max_leads', models.IntegerField(default=1000)),
                ('is_active', models.BooleanField(default=True)),
                ('is_public', models.BooleanField(default=True)),
                ('sort_order', models.IntegerField(default=0)),
                ('features', models.ManyToManyField(blank=True, related_name='plans', to='tenants.feature')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Plan',
                'verbose_name_plural': 'Plans',
                'ordering': ['sort_order', 'price_monthly'],
                'app_label': 'tenants',
            },
        ),
        migrations.CreateModel(
            name='TenantSubscription',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(
                    choices=[('active', 'Active'), ('trialing', 'Trialing'), ('past_due', 'Past Due'), ('cancelled', 'Cancelled'), ('expired', 'Expired')],
                    default='trialing', max_length=20
                )),
                ('billing_cycle', models.CharField(
                    choices=[('monthly', 'Monthly'), ('annual', 'Annual')],
                    default='monthly', max_length=10
                )),
                ('is_active', models.BooleanField(default=True)),
                ('trial_ends_at', models.DateTimeField(blank=True, null=True)),
                ('current_period_start', models.DateTimeField(default=django.utils.timezone.now)),
                ('current_period_end', models.DateTimeField(blank=True, null=True)),
                ('cancelled_at', models.DateTimeField(blank=True, null=True)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='subscriptions', to='tenants.client')),
                ('plan', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='subscriptions', to='tenants.plan')),
            ],
            options={
                'verbose_name': 'Tenant Subscription',
                'verbose_name_plural': 'Tenant Subscriptions',
                'ordering': ['-created_at'],
                'app_label': 'tenants',
            },
        ),
    ]
