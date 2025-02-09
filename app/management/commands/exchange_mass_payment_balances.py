import os.path
import asyncio

from django.core.management.base import BaseCommand

from entities import MerchantAccount, Account, MerchantMeta
from api.mass_payment import MassPaymentAssetsResource
from reposiroty import AccountRepository


class Command(BaseCommand):

    """Set merchant balances for mass-payments"""

    def add_arguments(self, parser):
        parser.add_argument(
            "account",
            type=str,
            help="Account UID"
        )
        parser.add_argument(
            "deposit",
            type=float,
            help="Deposit value"
        )
        parser.add_argument(
            "reserved",
            type=float,
            help="Reserved value"
        )

    def handle(self, *args, **options):
        account_uid = options['account']
        deposit = options['deposit']
        reserved = options['reserved']

        account: Account = asyncio.run(
            AccountRepository.get(uid=account_uid)
        )
        if account is None:
            raise RuntimeError(f'Account "{account_uid}" does not exists')
        if not account.merchant_meta:
            raise RuntimeError(f'Account "{account_uid}" is not Merchant')

        meta = MerchantMeta.model_validate(account.merchant_meta)
        merchant = MerchantAccount(meta=meta, **dict(account))
        MassPaymentAssetsResource.set_balances(
            merchant, deposit, reserved
        )
