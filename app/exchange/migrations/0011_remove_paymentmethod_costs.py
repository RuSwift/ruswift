# Generated by Django 4.2.9 on 2024-05-24 23:50

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('exchange', '0010_rename_directionside_payment'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='paymentmethod',
            name='costs',
        ),
    ]
