# Generated by Django 4.2.9 on 2024-07-21 22:16

import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('exchange', '0034_alter_session_account_uid'),
    ]

    operations = [
        migrations.CreateModel(
            name='StorageItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('uid', models.CharField(max_length=128, unique=True)),
                ('storage_id', models.CharField(db_index=True, max_length=64)),
                ('category', models.CharField(db_index=True, max_length=32)),
                ('tags', django.contrib.postgres.fields.ArrayField(base_field=models.TextField(), db_index=True, default=list, null=True, size=None)),
                ('created_at', models.DateTimeField(auto_now_add=True, null=True)),
                ('updated_at', models.DateTimeField(auto_now=True, null=True)),
                ('payload', models.JSONField()),
            ],
        ),
    ]
