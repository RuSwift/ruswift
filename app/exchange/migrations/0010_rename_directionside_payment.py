# Generated by Django 4.2.9 on 2024-05-24 23:28

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('exchange', '0009_directionside_alter_direction_dest_and_more'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='DirectionSide',
            new_name='Payment',
        ),
    ]
