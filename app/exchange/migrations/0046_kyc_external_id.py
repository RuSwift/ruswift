# Generated by Django 4.2.9 on 2025-01-03 17:37

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('exchange', '0045_account_verified'),
    ]

    operations = [
        migrations.AddField(
            model_name='kyc',
            name='external_id',
            field=models.CharField(db_index=True, max_length=512, null=True),
        ),
    ]
