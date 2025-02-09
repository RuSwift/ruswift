import logging
from abc import abstractmethod
from typing import List, Optional, Dict, Type

from pydantic import BaseModel, Extra
from django.conf import settings

from core.utils import utc_now_float
from entities import ExchangePair, P2POrders
from cache import ImplicitCacheMixin
from context import context
from reposiroty import CacheMixin


class LazySettingsMixin:

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        ratios_cfg = getattr(settings, 'RATIOS', None)
        if ratios_cfg and cls.__name__ in ratios_cfg:
            declared_settings = ratios_cfg[cls.__name__].settings
            if 'settings' in cls.__annotations__ and declared_settings:
                settings_model: Type[BaseModel] = cls.__annotations__['settings']  # noqa
                try:
                    new_settings: BaseModel = settings_model.model_validate(declared_settings)
                except ValueError as e:
                    raise RuntimeError(
                        f'Apply settings for {cls} terminated with error: {e}'
                    )
                old_settings: Optional[BaseModel] = cls.settings
                if old_settings:
                    dump = old_settings.model_dump(by_alias=True)
                    dump |= new_settings.model_dump(by_alias=True)
                    cls.settings = settings_model.model_validate(dump)
                else:
                    cls.settings = new_settings
            else:
                logging.critical(f'{cls} has not annotated settings')


class CacheableMixin:

    @abstractmethod
    def serialize(self) -> Dict:
        ...

    @abstractmethod
    def deserialize(self, dump: Dict):
        ...


class BaseRatioEngine(LazySettingsMixin, CacheMixin, ImplicitCacheMixin):

    CACHE_TTL = 60*5

    class EngineSettings(BaseModel, extra=Extra.ignore):
        ...

    settings: EngineSettings = None

    def __init_subclass__(cls, **kwargs):
        if not cls._namespace:
            cls._namespace = cls.__name__
        super().__init_subclass__(**kwargs)

    def __init__(self, refresh_cache: bool = False):
        self.refresh_cache = refresh_cache

    @abstractmethod
    async def market(self) -> List[ExchangePair]:
        ...

    async def ratio(self, base: str, quote: str) -> Optional[ExchangePair]:
        cached: Optional[Dict]
        if self.refresh_cache:
            cached = None
        else:
            cached = await self._cache.get(f'{quote}/{base}')
        if cached:
            return ExchangePair(**cached)
        if base == quote:
            return ExchangePair(
                utc=utc_now_float(),
                base=base,
                quote=quote,
                ratio=1.0
            )
        pairs = await self.market()
        fwd1: Optional[ExchangePair] = None
        fwd2: Optional[ExchangePair] = None
        revert: Optional[ExchangePair] = None
        for pair in pairs:
            if pair.base == base and pair.quote == quote:
                return pair
            if pair.quote == quote:
                fwd1 = pair
            if pair.quote == base:
                fwd2 = pair
            if pair.quote == base and pair.base == quote:
                revert = pair
        if (fwd1 and fwd2) or revert:
            if fwd1 and fwd2:
                p = ExchangePair(
                    utc=fwd1.utc,
                    base=base,
                    quote=quote,
                    ratio=fwd1.ratio / fwd2.ratio
                )
            else:
                p = ExchangePair(
                    utc=revert.utc,
                    base=base,
                    quote=quote,
                    ratio=1 / revert.ratio
                )
            expire_ttl = p.utc + self.CACHE_TTL
            ttl = round(expire_ttl - utc_now_float())
            await self._cache.set(
                f'{quote}/{base}',
                p.model_dump(mode='json'),
                ttl=ttl if ttl > 0 else 60
            )
            return p
        else:
            return None


class BaseP2PRatioEngine(LazySettingsMixin, CacheMixin, ImplicitCacheMixin):

    class P2PSettings(BaseModel, extra=Extra.ignore):
        ...

    settings: P2PSettings = None

    def __init__(self, refresh_cache: bool = False):
        self.refresh_cache = refresh_cache

    @abstractmethod
    async def load_orders(
        self, token: str, fiat: str, page: int = 0, pg_size: int = None
    ) -> Optional[P2POrders]:
        pass
