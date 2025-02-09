import logging
from copy import copy
from typing import Optional, List

from api.utils import configure_mass_payments_ledger
from entities import (
    ExchangeConfig, MerchantMeta, Account, Ledger
)
from api.auth import BaseAuth
from merchants.ratios import MerchantRatios
from reposiroty import AccountRepository, LedgerRepository


def configure_ledgers(meta: MerchantMeta, cfg: ExchangeConfig) -> List[Ledger]:
    ledgers: List[Ledger] = []
    if meta.mass_payments and meta.mass_payments.enabled:
        configured_ledger = configure_mass_payments_ledger(
            cfg, meta.identity, meta.mass_payments.ledger
        )
        meta.mass_payments.ledger = configured_ledger
        ledgers.append(configured_ledger)

    return ledgers


async def update_merchants_config(cfg: ExchangeConfig):
    if cfg.merchants:
        merchants = copy(cfg.merchants)

        # Вырезаем конфигурацию парсеров курсов и проверяем что
        # структура адекватна
        default = merchants.pop('default', {})
        MerchantRatios.Settings.model_validate(default)

        for uid, settings in merchants.items():
            meta = MerchantMeta.model_validate(settings)
            account: Optional[Account] = await AccountRepository.get(uid=uid)
            if account is None:
                account = Account(
                    uid=uid,
                )
            account.is_active = True
            account.merchant_meta = settings
            account.permissions = list(
                set(account.permissions) | {Account.Permission.MERCHANT.value}
            )
            # Ledgers
            ledgers = configure_ledgers(meta, cfg)
            # hide secrets
            account.merchant_meta = meta.model_dump(exclude={'auth'})
            await AccountRepository.update_or_create(
                e=account, uid=uid
            )
            await LedgerRepository.ensure_exists(
                identity=meta.identity, ledgers=ledgers, remove_others=True
            )
            # Auths
            for auth in meta.auth:
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
