import json
from typing import Any, List, Optional

import pydantic
from lib import BaseResource
from lib.mixins import MixinUpdateOne, MixinDeleteOne, MixinCreateOne
from django.conf import settings

from cache import Cache
from api import BaseExchangeController, AuthControllerMixin
from entities import Currency
from reposiroty import CurrencyRepository
from ratios.bestchange import BestChangeRatios, Currencies as BCCurrencies


class BestChangeCodeResource(BaseResource):

    pk = 'value'

    class Create(BaseResource.Create):
        ...

    class Update(Create):
        ...

    class Retrieve(Update):
        value: str
        label: str
        cur: str


class BestChangeCodeController(AuthControllerMixin, BaseExchangeController):

    Resource = BestChangeCodeResource
    _cache = Cache(
        pool=settings.REDIS_CONN_POOL, namespace='bestchange-codes'
    )

    async def get_one(self, pk: str, **filters) -> Optional[Resource.Retrieve]:
        values = await self.get_many()
        found = [v for v in values if v.value == pk]
        return found[0] if found else None

    async def get_many(
        self, order_by: Any = 'id', limit: int = None,
        offset: int = None, **filters
    ) -> List[Resource.Retrieve]:
        term = filters.get('term')
        try_cache= await self._cache.get('curs')
        if try_cache:
            curs = BCCurrencies(text='')
            curs.data = try_cache
        else:
            engine = BestChangeRatios()
            _, curs, _, _ = await engine.load_metadata()
            await self._cache.set(key='curs', value=curs.data, ttl=60*60)
        result = []
        for id_, meta in curs.data.items():
            if term and not any(term.lower() in s.lower() for s in [meta['name'], meta['payment_code'], meta['payment_code']]):
                continue
            for label in [meta['name']]:
                result.append(
                    BestChangeCodeResource.Retrieve(
                        value=meta['payment_code'],
                        label=label,
                        cur=meta['cur_code']
                    )
                )
        return result


class ActiveCurrencyResource(BaseResource):

    pk = 'value'

    class Create(BaseResource.Create):
        ...

    class Update(Create):
        ...

    class Retrieve(Update):
        value: str
        label: str


class ActiveCurrencyController(AuthControllerMixin, BaseExchangeController):
    """Autocomplete для активных валют обменника
    """

    Resource = ActiveCurrencyResource
    _cache = Cache(
        pool=settings.REDIS_CONN_POOL, namespace='active-currencies'
    )

    async def get_one(self, pk: str, **filters) -> Optional[Resource.Retrieve]:
        values = await self.get_many()
        found = [v for v in values if v.value == pk]
        return found[0] if found else None

    async def get_many(
        self, order_by: Any = 'id', limit: int = None,
        offset: int = None, **filters
    ) -> List[Resource.Retrieve]:
        term = filters.get('term')
        owner_did = self.context.config.identity.did.root
        if owner_did is None or owner_did == self.context.config.identity.did.root:
            filters = {
                'owner_did__in': [None, self.context.config.identity.did.root]
            }
        else:
            filters = {'owner_did': owner_did}
            
        _, currencies = await CurrencyRepository.get_many(**filters)
        result: List[ActiveCurrencyResource.Retrieve] = []
        for cur in currencies:
            cur: Currency
            result.append(
                ActiveCurrencyResource.Retrieve(
                    value=cur.symbol,
                    label=cur.symbol
                )
            )
        return result
