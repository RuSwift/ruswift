# Generated by Django 4.2.9 on 2024-06-04 21:42

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('exchange', '0020_account_permissions'),
    ]

    operations = [
        migrations.AddField(
            model_name='account',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
        migrations.AddField(
            model_name='account',
            name='updated_at',
            field=models.DateTimeField(auto_now=True, null=True),
        ),
    ]
