# Generated by Django 4.2.9 on 2024-06-21 21:59

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('exchange', '0024_account_is_verified'),
    ]

    operations = [
        migrations.AddField(
            model_name='account',
            name='is_organization',
            field=models.BooleanField(default=False),
        ),
    ]
