# Generated by Django 4.2.9 on 2024-06-05 20:43

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('exchange', '0022_kyc'),
    ]

    operations = [
        migrations.AlterField(
            model_name='kyc',
            name='image_b64_document',
            field=models.BinaryField(null=True),
        ),
        migrations.AlterField(
            model_name='kyc',
            name='image_b64_selfie',
            field=models.BinaryField(null=True),
        ),
    ]
