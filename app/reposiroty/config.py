import os.path
from typing import Dict, Optional

from pydantic import BaseModel, Extra
from pydantic_yaml import parse_yaml_file_as

from entities import (
    Currency, PaymentMethod, Network, BasePaymentMethod, Correction, Payment,
    ExchangeConfig, CashMethod
)
from exchange.models import AppSettings as DBAppSettings
from reposiroty import (
    CurrencyRepository, PaymentMethodRepository, NetworkRepository,
    CorrectionRepository, DirectionRepository, PaymentRepository,
    BaseEntityRepository, CacheMixin, CashMethodRepository
)


class ExchangeConfigRepository(CacheMixin, BaseEntityRepository):

    Entity = ExchangeConfig

    class AnyCfg(BaseModel, extra=Extra.allow):
        ...

    class AppSettings:

        @classmethod
        async def get(cls) -> Dict:
            obj = await DBAppSettings.objects.afirst()
            if obj:
                obj: DBAppSettings
                return obj.storage
            else:
                return {}

        @classmethod
        async def set(cls, data: Dict):
            await DBAppSettings.objects.aupdate_or_create(
                defaults={'storage': data}
            )

    @classmethod
    async def get(cls) -> ExchangeConfig:
        obj: Optional[Dict] = await cls._cache.get('config')
        if obj:
            cfg = ExchangeConfig.model_validate(obj)
            return cfg
        _, directions = await DirectionRepository.get_many()
        _, payments = await PaymentRepository.get_many()
        _, cors = await CorrectionRepository.get_many()
        _, pm_methods = await PaymentMethodRepository.get_many()
        _, net_methods = await NetworkRepository.get_many()
        _, cash_methods = await CashMethodRepository.get_many()
        methods = []
        methods.extend(pm_methods)
        methods.extend(net_methods)
        methods.extend(cash_methods)
        _, curs = await CurrencyRepository.get_many()
        app_sett = await cls.AppSettings.get()
        extra = {}
        if 'refresh_timeout_sec' in app_sett:
            extra['refresh_timeout_sec'] = app_sett['refresh_timeout_sec']
        if 'cache_timeout_sec' in app_sett:
            extra['cache_timeout_sec'] = app_sett['cache_timeout_sec']
        if 'merchants' in app_sett:
            extra['merchants'] = app_sett['merchants']
        if 'paths' in app_sett:
            extra['paths'] = app_sett['paths']
        if 'identity' in app_sett:
            extra['identity'] = app_sett['identity']
        if 'reports' in app_sett:
            extra['reports'] = app_sett['reports']
        cfg = ExchangeConfig(
            costs={corr.uid: corr for corr in cors},
            methods={meth.uid: meth for meth in methods},
            currencies=curs,
            payments=payments,
            directions=directions,
            **extra
        )
        await cls._cache.set(
            'config', cfg.model_dump(mode='json'), ttl=cfg.cache_timeout_sec
        )
        return cfg

    @classmethod
    async def set(cls, cfg: ExchangeConfig):
        symbol_to_cur: Dict[str, Currency] = {}
        uid_to_meth: Dict[str, BasePaymentMethod] = {}
        uid_to_corr: Dict[str, Correction] = {}
        code_to_pay: Dict[str, Payment] = {}

        await ExchangeConfigRepository.invalidate_cache()
        await cls.AppSettings.set(
            {
                'refresh_timeout_sec': cfg.refresh_timeout_sec,
                'cache_timeout_sec': cfg.cache_timeout_sec,
                'merchants': cfg.merchants,
                'paths': cfg.paths.model_dump(mode='json'),
                'identity': cfg.identity.model_dump(mode='json') if cfg.identity else None,  # noqa
                'reports': cfg.reports.model_dump(mode='json') if cfg.reports else None  # noqa
            }
        )

        for cur in cfg.currencies:
            await CurrencyRepository.update_or_create(
                cur, symbol=cur.symbol
            )
            symbol_to_cur[cur.symbol] = cur
        for code, meth in cfg.methods.items():
            if isinstance(meth, PaymentMethod):
                meth.code = code
                await PaymentMethodRepository.update_or_create(
                    meth, uid=code
                )
            elif isinstance(meth, Network):
                meth.code = code
                await NetworkRepository.update_or_create(
                    meth, uid=code
                )
            elif isinstance(meth, CashMethod):
                meth.code = code
                await CashMethodRepository.update_or_create(
                    meth, uid=code
                )
            else:
                raise RuntimeError(f'Unexpected method type {meth}')
            uid_to_meth[code] = meth
        for uid, corr in cfg.costs.items():
            await CorrectionRepository.update_or_create(
                corr, uid=uid
            )
            uid_to_corr[uid] = corr
        for payment in cfg.payments:
            if payment.cur not in symbol_to_cur:
                raise RuntimeError(f'Unknown payment cur: {payment.cur}')
            if payment.method not in uid_to_meth:
                raise RuntimeError(f'Unknown payment meth: {payment.method}')
            for cost in (payment.costs.outcome or []) + (
                    payment.costs.income or []):
                if cost not in uid_to_corr:
                    raise RuntimeError(f'Unknown cost: {cost}')
            await PaymentRepository.update_or_create(payment,
                                                     code=payment.code)
            code_to_pay[payment.code] = payment
        for direction in cfg.directions:
            await DirectionRepository.update_or_create(
                direction, src=direction.src, dest=direction.dest
            )

    @classmethod
    async def init_from_yaml(
        cls, path: str, section: str = None
    ) -> ExchangeConfig:
        if not os.path.isfile(path):
            raise RuntimeError(f'path "{path}" not exists')
        settings = parse_yaml_file_as(cls.AnyCfg, path)
        if section:
            values = getattr(settings, section)
        else:
            values = settings
        cfg = cls.Entity.model_validate(values)
        await cls.set(cfg)
        return cfg
