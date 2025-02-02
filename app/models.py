from django.db import models
from django.contrib.postgres.fields import ArrayField
from django.db.models.signals import pre_delete
from django.dispatch import receiver
from django.db import IntegrityError


class Currency(models.Model):
    symbol = models.CharField(max_length=8, db_index=True)
    icon = models.TextField(null=True)
    is_fiat = models.BooleanField()
    is_enabled = models.BooleanField(default=True)
    owner_did = models.CharField(max_length=128, db_index=True, null=True)

    class Meta:
        unique_together = ('symbol', 'owner_did')


class Network(models.Model):
    uid = models.CharField(max_length=64, unique=True, null=True)
    name = models.CharField(max_length=64, db_index=True)
    explorer = models.TextField()
    icon = models.TextField(null=True)
    is_enabled = models.BooleanField(default=True)
    category = models.CharField(max_length=64, null=True)
    code = models.CharField(max_length=32, null=True, db_index=True)
    owner_did = models.CharField(max_length=128, db_index=True, null=True)


class PaymentMethod(models.Model):
    uid = models.CharField(max_length=64, unique=True, null=True)
    name = models.CharField(max_length=64, db_index=True)
    icon = models.TextField(null=True)
    is_enabled = models.BooleanField(default=True)
    category = models.CharField(max_length=64, null=True)
    explorer = models.TextField(null=True)
    sub = models.TextField(null=True)
    code = models.CharField(max_length=32, null=True, db_index=True)
    owner_did = models.CharField(max_length=128, db_index=True, null=True)


class CashMethod(models.Model):
    uid = models.CharField(max_length=64, unique=True, null=True)
    name = models.CharField(max_length=64, db_index=True)
    icon = models.TextField(null=True)
    is_enabled = models.BooleanField(default=True)
    category = models.CharField(max_length=64, null=True)
    explorer = models.TextField(null=True)
    sub = models.TextField(null=True)
    code = models.CharField(max_length=32, null=True, db_index=True)
    owner_did = models.CharField(max_length=128, db_index=True, null=True)


class Account(models.Model):
    uid = models.CharField(max_length=128, unique=True)
    icon = models.TextField(null=True)
    is_active = models.BooleanField(default=True)
    first_name = models.TextField(null=True)
    last_name = models.TextField(null=True)
    phone = models.TextField(null=True)
    email = models.TextField(null=True)
    telegram = models.TextField(null=True)
    extra = models.JSONField(null=True)
    permissions = ArrayField(
        base_field=models.TextField(), null=True, default=list, db_index=True
    )
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)
    is_verified = models.BooleanField(default=False)
    is_organization = models.BooleanField(default=False)
    merchant_meta = models.JSONField(null=True, db_index=True)
    verified = models.JSONField(null=True)


class KYC(models.Model):
    document_id = models.CharField(max_length=256, db_index=True)
    provider = models.CharField(max_length=36, db_index=True)
    account = models.OneToOneField(
        Account, related_name='kyc', on_delete=models.CASCADE
    )
    image_b64_document = models.BinaryField(null=True)
    image_b64_selfie = models.BinaryField(null=True)
    verified_data = models.JSONField()
    inn = models.CharField(max_length=64, null=True)
    source = models.CharField(max_length=64, null=True)

    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)
    external_id = models.CharField(max_length=512, db_index=True, null=True)


class OrganizationDocument(models.Model):
    account = models.OneToOneField(
        Account, related_name='documents', on_delete=models.CASCADE
    )
    image_b64 = models.BinaryField(null=True)
    attrs = models.JSONField()
    type = models.CharField(max_length=36, null=True)


class Correction(models.Model):
    uid = models.CharField(max_length=128, unique=True)
    cost = models.FloatField()
    is_percents = models.BooleanField()
    cur = models.CharField(max_length=12, db_index=True)
    limits = models.JSONField(null=True)


class Payment(models.Model):
    code = models.CharField(max_length=24, unique=True)
    cur = models.CharField(max_length=8, db_index=True)
    method = models.CharField(max_length=64, db_index=True)
    costs_income = ArrayField(
        base_field=models.TextField(), null=True, default=list, db_index=True
    )
    costs_outcome = ArrayField(
        base_field=models.TextField(), null=True, default=list, db_index=True
    )
    owner_did = models.CharField(max_length=128, db_index=True, null=True)


class Direction(models.Model):
    order_id = models.IntegerField(default=0)
    src = models.CharField(max_length=64, db_index=True)
    dest = models.CharField(max_length=64, db_index=True)
    ratio_calculator_class = models.TextField()
    owner_did = models.CharField(max_length=128, db_index=True, null=True)

    class Meta:
        unique_together = ('src', 'dest')


class Order(models.Model):
    uid = models.CharField(max_length=128, unique=True)
    status = models.CharField(max_length=64)
    account = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True)


class AppSettings(models.Model):
    storage = models.JSONField()


class KYCPhoto(models.Model):
    uid = models.CharField(max_length=128, db_index=True)
    mime_type = models.CharField(max_length=56, null=True)
    type = models.CharField(max_length=36, db_index=True)
    image = models.BinaryField()
    remove_after = models.FloatField(null=True)

    class Meta:
        unique_together = ('uid', 'type')


class Credential(models.Model):
    class_name = models.CharField(max_length=128, db_index=True)
    account_uid = models.CharField(max_length=128, db_index=True, null=True)
    schema = models.JSONField()
    payload = models.JSONField(db_index=True)
    ttl = models.IntegerField(null=True)


class Session(models.Model):
    uid = models.CharField(max_length=128, unique=True)
    class_name = models.CharField(max_length=128, db_index=True)
    account_uid = models.CharField(max_length=128, db_index=True, null=True)
    last_access_utc = models.DateTimeField(db_index=True)
    kill_after_utc = models.DateTimeField(null=True, db_index=True)


class StorageItem(models.Model):
    uid = models.CharField(max_length=128, unique=True)
    storage_id = models.CharField(max_length=512, db_index=True, null=True)
    category = models.CharField(max_length=512, db_index=True)
    tags = ArrayField(
        base_field=models.TextField(), null=True, default=list, db_index=True
    )
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)
    payload = models.JSONField()
    storage_ids = ArrayField(
        base_field=models.TextField(), null=True, db_index=True
    )
    signature = models.CharField(max_length=512, db_index=True, null=True)


class MassPaymentBalance(models.Model):
    type = models.CharField(max_length=64, db_index=True)
    account_uid = models.CharField(max_length=128, db_index=True)
    value = models.FloatField(default=0.0)

    class Meta:
        unique_together = ('account_uid', 'type')


@receiver(pre_delete, sender=Currency, dispatch_uid='currency_delete_signal')
def log_deleted_question(sender, instance: Currency, using, **kwargs):
    exists = Payment.objects.filter(
        cur=instance.symbol, owner_did=instance.owner_did
    ).exists()
    if exists:
        raise IntegrityError(
            'There are exists payment records with same cur symbol'
        )
