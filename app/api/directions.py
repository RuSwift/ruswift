import logging
from typing import Any, List, Optional, Dict, Union
from collections import defaultdict

import pydantic
from pydantic import BaseModel
from api.lib import BaseResource
from api.lib.mixins import MixinUpdateOne, MixinDeleteOne, MixinCreateOne
from django.conf import settings
from django.http import HttpResponseBadRequest

from exchange.core import float_to_datetime, secs_delta, utc_now_float
from exchange.cache import Cache
from exchange.entities import (
    Direction, Payment, Currency, PaymentMethod, CashMethod, Network
)
from exchange.reposiroty import (
    DirectionRepository, CurrencyRepository, PaymentMethodRepository,
    NetworkRepository, PaymentRepository, CashMethodRepository
)
from exchange.merchants import (
    MerchantRatios, EngineVariable, P2PEngineVariable
)
from exchange.api import BaseExchangeController, AuthControllerMixin


class ComplexPayment(BaseModel):
    code: str
    cur: Currency
    method: Union[PaymentMethod, CashMethod, Network]


class ExternalRatio(BaseModel):
    rate: float
    scope: str
    engine: str
    src: str
    dest: str
    utc: Optional[str] = None
    secs_ago: Optional[float] = None


class OwnerIdMixin:

    def owner_id_filters(self) -> dict:
        filters = {}
        if str(self.identity) == str(self.context.config.identity):
            filters['owner_did__in'] = [None, self.identity.did.root]
        else:
            filters['owner_did'] = self.identity.did.root
        return filters


class DirectionResource(BaseResource):

    pk = 'id'

    class Create(BaseResource.Create):
        src: ComplexPayment
        dest: ComplexPayment

    class Update(Create):
        ...

    class Retrieve(Update):
        id: str
        externals: List[ExternalRatio] = pydantic.Field(default_factory=list)


class DirectionController(OwnerIdMixin, BaseExchangeController):

    Resource = DirectionResource
    _cache = Cache(
        pool=settings.REDIS_CONN_POOL, namespace='exchange-directions'
    )

    async def get_one(self, pk: str, **filters) -> Optional[Resource.Retrieve]:
        parts = pk.split('-')
        if len(parts) != 2:
            return None
        src, dest = parts
        filters['src'] = src
        filters['dest'] = dest
        res = await self.get_many(**filters)
        return res[0] if res else None

    async def get_many(
        self, order_by: Any = 'order_id', limit: int = None,
        offset: int = None, **filters
    ) -> List[Resource.Retrieve]:
        owner_filter = self.owner_id_filters()
        filters.update(owner_filter)

        self.metadata.total_count, dirs = await DirectionRepository.get_many(
            order_by=order_by, limit=limit, **filters
        )
        result = await self._build_for_dirs(dirs)
        if 'clean' in filters:
            self.__clean(result)
        return result

    async def _build_for_dirs(
        self, directions: List[Direction]
    ) -> Optional[List[Resource.Retrieve]]:
        if not directions:
            return None

        owner_did = directions[0].owner_did

        def _build_dir_id(src_: str, dest_: str) -> str:
            return f'{src_}-{dest_}'

        ratios = await self._load_ratios(directions)
        ratios_map: Dict[
            str, Union[EngineVariable, P2PEngineVariable]
        ] = defaultdict(list)
        for r in ratios:
            rid = _build_dir_id(r.src, r.dest)
            ratios_map[rid].append(r)

        if owner_did is None or owner_did == self.context.config.identity.did.root:
            filters = {
                'owner_did__in': [None, self.context.config.identity.did.root]
            }
        else:
            filters = {'owner_did': owner_did}
        # containers
        currencies_map: Dict[str, Currency] = {}
        payment_methods_map: Dict[str, Union[PaymentMethod, CashMethod, Network]] = {}  # noqa
        payments_map: Dict[str, Payment] = {}
        # currencies
        _, currencies = await CurrencyRepository.get_many(**filters)
        currencies: List[Currency]
        self.__lazy_fill_empty_attrs(currencies)
        for cur in currencies:
            currencies_map[cur.symbol] = cur

        # payment methods
        _, payment_methods = await PaymentMethodRepository.get_many(**filters)
        payment_methods: List[PaymentMethod]
        self.__lazy_fill_empty_attrs(payment_methods)
        for pm in payment_methods:
            payment_methods_map[pm.code] = pm

        # networks
        _, networks = await NetworkRepository.get_many(**filters)
        networks: List[Network]
        self.__lazy_fill_empty_attrs(networks)
        for net in networks:
            payment_methods_map[net.code] = net

        # cash
        _, caches = await CashMethodRepository.get_many(**filters)
        caches: List[CashMethod]
        self.__lazy_fill_empty_attrs(caches)
        for cash in caches:
            payment_methods_map[cash.code] = cash

        # payments
        _, payments = await PaymentRepository.get_many(**filters)
        payments: List[Payment]
        self.__lazy_fill_empty_attrs(payments)
        for p in payments:
            payments_map[p.code] = p

        result: List[DirectionResource.Retrieve] = []
        utc = utc_now_float()
        for item in directions:
            src_payment = payments_map[item.src]
            src = ComplexPayment(
                code=item.src,
                method=payment_methods_map[src_payment.method],
                cur=currencies_map[src_payment.cur]
            )
            dest_payment = payments_map[item.dest]
            dest = ComplexPayment(
                code=item.dest,
                method=payment_methods_map[dest_payment.method],
                cur=currencies_map[dest_payment.cur]
            )
            externals: List[ExternalRatio] = []
            ratios = ratios_map[
                _build_dir_id(
                    src_payment.cur, dest_payment.cur
                )
            ]
            for r in ratios:
                sm = payments_map.get(r.src_method)
                if sm:
                    ratio_src = payment_methods_map[sm.method].name
                else:
                    ratio_src = r.src_method
                dm = payments_map.get(r.dest_method)
                if dm:
                    ratio_dest = payment_methods_map[dm.method].name
                else:
                    ratio_dest = r.dest_method
                _ = r.engine.split('.')
                rate = r.rate if r.rate >= 1 else 1/r.rate
                externals.append(
                    ExternalRatio(
                        rate=round(rate, 2),
                        scope=r.scope,
                        engine=_[-1],
                        src=ratio_src,
                        dest=ratio_dest,
                        utc=str(float_to_datetime(r.utc)),
                        secs_ago=secs_delta(utc, r.utc)
                    )
                )

            res = DirectionResource.Retrieve(
                id=_build_dir_id(item.src, item.dest),
                src=src,
                dest=dest,
                externals=sorted(externals, key=lambda x: x.rate)
            )
            result.append(res)
        return result

    async def _load_ratios(
        self, directions: List[Direction]
    ) -> List[Union[EngineVariable, P2PEngineVariable]]:
        owner_did = directions[0].owner_did
        cache = self._cache.namespace('ratios')
        engine = MerchantRatios()
        try:
            ratios = await engine.engine_ratios(directions, cache_only=True) or []
        except Exception as e:
            logging.exception('ERR')
            ratios = None

        if owner_did is None:
            owner_did = self.context.config.identity.did.root
        if ratios:
            await cache.set(
                key=owner_did,
                value=dict(
                    ratios=[f.model_dump(mode='json') for f in ratios]
                )
            )
        else:
            container = await cache.get(key=owner_did)
            if container:
                ratios_data = container['ratios']
                ratios = []
                for d in ratios_data:
                    if 'method' in d:
                        m = P2PEngineVariable.model_validate(d)
                    else:
                        m = EngineVariable.model_validate(d)
                ratios.append(m)
            else:
                ratios = []
        return ratios

    @classmethod
    def __clean(cls, items: List[Resource.Retrieve]):
        for item in items:
            item.src.cur.icon = None
            item.dest.cur.icon = None
            item.src.method.icon = None
            item.dest.method.icon = None

    def __lazy_fill_empty_attrs(
        self, items: List[
                Union[Currency, PaymentMethod, Network, Payment, CashMethod]
            ]
    ):
        for item in items:
            if item.owner_did is None:
                item.owner_did = self.context.config.identity.did.root


class CurrencyResource(BaseResource):

    pk = 'id'

    class Create(BaseResource.Create):
        symbol: str
        icon: Optional[str] = None
        is_fiat: bool
        is_enabled: Optional[bool] = True

    class Update(Create):
        ...

    class Retrieve(Update):
        id: int
        owner_did: str
        payments_count: int = 0


class CurrenciesController(
    AuthControllerMixin, OwnerIdMixin,
    MixinUpdateOne, MixinDeleteOne, MixinCreateOne,
    BaseExchangeController
):

    Resource = CurrencyResource

    async def get_one(self, pk: Any, **filters) -> Optional[Resource.Retrieve]:
        resp = await self.get_many(id=pk)
        return resp[0] if resp else None

    async def get_many(
        self, order_by: Any = 'id', limit: int = None,
        offset: int = None, **filters
    ) -> List[Resource.Retrieve]:
        self.metadata.total_count, curs = await CurrencyRepository.get_many(
            order_by=order_by, limit=limit, offset=offset, **filters
        )
        for cur in curs:
            self.__fill_owner_id(cur)
        result = [
            CurrencyResource.Retrieve.model_validate(
                cur.model_dump()
            ) for cur in curs
        ]
        await self.__fill_extra_attrs(result)
        return result

    async def update_one(
        self, pk: Any, data: Resource.Update, **extra
    ) -> Union[Resource.Retrieve, HttpResponseBadRequest, None]:
        res = await self.get_one(pk)
        if res is None:
            return None
        obj = {
            k: v for k, v in res.model_dump().items()
            if k in Currency.__fields__
        }
        new_ = {
            k: v for k, v in data.model_dump().items()
            if k in Currency.__fields__
        }
        obj |= new_

        cur = Currency.model_validate(obj)
        unique = await self.__check_unique(cur.symbol, pk=pk)
        if not unique:
            return HttpResponseBadRequest(
                content=f'Валюта "{cur.symbol}" уже существует'.encode()
            )
        self.__fill_owner_id(cur)
        extra_filters = self.owner_id_filters()
        cur: Currency = await CurrencyRepository.update(
            e=cur, id=pk, **extra_filters
        )
        if cur:
            res = self.Resource.Retrieve.model_validate(cur.model_dump())
            await self.__fill_extra_attrs([res])
            return res
        else:
            return None

    async def delete_one(
        self, pk: Any, **extra
    ) -> Optional[Resource.Retrieve]:
        res = await self.get_one(pk)
        if not res:
            return None
        extra.update(self.owner_id_filters())
        count = await CurrencyRepository.delete(id=pk, **extra)
        return res if count > 0 else None

    async def create_one(
        self, data: Resource.Create, **extra
    ) -> Union[Resource.Retrieve, HttpResponseBadRequest]:
        obj = {
            k: v for k, v in data.model_dump().items()
            if k in Currency.__fields__
        }
        cur = Currency.model_validate(obj)
        unique = await self.__check_unique(cur.symbol)
        if not unique:
            return HttpResponseBadRequest(
                content=f'Валюта "{cur.symbol}" уже существует'.encode()
            )
        self.__fill_owner_id(cur)
        e: Currency = await CurrencyRepository.create(**cur.model_dump())
        return self.Resource.Retrieve.model_validate(e.model_dump())

    def __fill_owner_id(self, res: Union[Currency, Resource.Create]):
        if res.owner_did is None:
            res.owner_did = self.context.config.identity.did.root

    async def __fill_extra_attrs(self, items: List[Resource.Retrieve]):
        filters = self.owner_id_filters()
        _, payments = await PaymentRepository.get_many(**filters)
        payments: List[Payment]
        counters = defaultdict(lambda: 0)
        for p in payments:
            counters[p.cur] += 1
        for item in items:
            item.payments_count = counters[item.symbol]

    async def __check_unique(self, symbol: str, pk: int = None) -> bool:
        filters = {'symbol': symbol}
        filters.update(self.owner_id_filters())
        _, curs = await CurrencyRepository.get_many(**filters)
        if pk is None:
            return len(curs) == 0
        curs: List[Currency]
        for cur in curs:
            if cur.id != pk:
                return False
        return True
