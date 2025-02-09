import os.path
import asyncio
import logging
from io import StringIO

from ruamel.yaml import YAML
from django.core.management.base import BaseCommand

from entities import Account, MerchantMeta
from reposiroty import (
    AccountRepository, ExchangeConfigRepository, LedgerRepository
)
from merchants.config import configure_ledgers
from api.auth import BaseAuth


class Command(BaseCommand):

    """Ensure account exists"""

    def add_arguments(self, parser):
        parser.add_argument(
            "yaml",
            type=str,
            help="Path to YAML file"
        )

    def handle(self, *args, **options):
        asyncio.run(
            self.run(options['yaml'])
        )

    async def run(self, path: str):
        if not os.path.isfile(path):
            raise RuntimeError(f'File {path} does not exists!')
        with open(path, 'r') as f:
            raw = f.read()
        stream = StringIO(raw)
        reader = YAML(typ="safe", pure=True)
        obj = reader.load(stream)
        account = Account(**obj)
        cfg = await ExchangeConfigRepository.get()
        if account.merchant_meta:
            merchant_meta = MerchantMeta.model_validate(account.merchant_meta)
            auth = account.merchant_meta.pop('auth', None)
            account.permissions = list(set(account.permissions) | {Account.Permission.MERCHANT.value})  # noqa
            ledgers = configure_ledgers(merchant_meta, cfg)

            mp_ledgers = [
                ledger for ledger in ledgers if 'payments' in ledger.tags
            ]
            if mp_ledgers:
                merchant_meta.mass_payments.ledger = mp_ledgers[0]
            account.merchant_meta = merchant_meta.model_dump()
        else:
            merchant_meta = None
            auth = None
            ledgers = None
        await AccountRepository.update_or_create(account, uid=account.uid)
        if ledgers is not None and merchant_meta:
            await LedgerRepository.ensure_exists(
                merchant_meta.identity, ledgers, remove_others=False
            )
        if auth:
            for auth in merchant_meta.auth:
                found_classes = [
                    c for c in BaseAuth.Descendants
                    if auth.class_ in [c.Name, c.__name__]
                ]
                if found_classes:
                    for cls in found_classes:
                        if cls.validate(auth.settings):
                            await cls.register(account.uid, auth.settings)
                            print('')
                else:
                    logging.critical(f'Not fount auth class {auth.class_}')
