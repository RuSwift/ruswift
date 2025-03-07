# Generated by Django 4.2.9 on 2024-08-01 16:33

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('exchange', '0038_storageitem_signature'),
    ]

    operations = [
        migrations.CreateModel(
            name='MassPaymentBalance',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('type', models.CharField(db_index=True, max_length=64)),
                ('account_uid', models.CharField(db_index=True, max_length=128)),
                ('value', models.FloatField(default=0.0)),
            ],
            options={
                'unique_together': {('account_uid', 'type')},
            },
        ),
    ]
