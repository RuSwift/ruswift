import json
import base64
import time
import datetime
import aiohttp
import platform
import os.path
from io import TextIOWrapper
from typing import List, Optional, Dict, Literal, Union, Tuple

from zipfile import ZipFile
from itertools import groupby

from core.utils import utc_now_float
from entities import (
    ExchangePair, P2POrders, P2POrder, BestChangeMethodMapping
)
from ratios import BaseRatioEngine, BaseP2PRatioEngine
from context import context
from .base import CacheableMixin


def creation_date(path_to_file):
    """
    Try to get the date that a file was created, falling back to when it was
    last modified if that isn't possible.
    See http://stackoverflow.com/a/39501288/1709587 for explanation.
    """
    if platform.system() == 'Windows':
        return os.path.getctime(path_to_file)
    else:
        stat = os.stat(path_to_file)
        try:
            return stat.st_birthtime
        except AttributeError:
            # We're probably on Linux. No easy way to get creation dates here,
            # so we'll settle for when its content was last modified.
            return stat.st_mtime


class Rates(CacheableMixin):

    def __init__(self, text, split_reviews):
        self.__data = []
        for row in text.splitlines():
            val = row.split(';')
            try:
                self.__data.append({
                    'give_id': int(val[0]),
                    'get_id': int(val[1]),
                    'exchange_id': int(val[2]),
                    'rate': float(val[3]) / float(val[4]),
                    'reserve': float(val[5]),
                    'reviews': val[6].split('.') if split_reviews else val[6],
                    'min_sum': float(val[8]),
                    'max_sum': float(val[9]),
                    'city_id': int(val[10]),
                    'utc': None
                })
            except ZeroDivisionError:
                # Иногда бывает курс N:0 и появляется ошибка деления на 0.
                pass

    def get(self):
        return self.__data

    def filter(
        self, give_id: Union[int, List[int]], get_id: Union[int, List[int]]
    ):
        data = []
        give_id = [give_id] if isinstance(give_id, int) else give_id
        get_id = [get_id] if isinstance(get_id, int) else get_id
        for val in self.__data:
            if val['give_id'] in give_id and val['get_id'] in get_id:
                val['give'] = 1 if val['rate'] < 1 else val['rate']
                val['get'] = 1 / val['rate'] if val['rate'] < 1 else 1
                data.append(val)

        return sorted(data, key=lambda x: x['rate'])

    def serialize(self) -> Dict:
        return {
            'data': self.__data
        }

    def deserialize(self, dump: Dict):
        self.__data = dump.get('data', [])

    def set_utc(self, value: float):
        for item in self.__data:
            item['utc'] = value


class Common(CacheableMixin):

    def __init__(self):
        self.data = {}

    def get(self):
        return self.data

    @property
    def is_empty(self) -> bool:
        return len(self.data) > 0

    def get_by_id(self, id, only_name=True):
        if id not in self.data:
            return None

        return self.data[id]['name'] if only_name else self.data[id]

    def search_by_name(self, name):
        return {k: val for k, val in self.data.items() if val['name'].lower().count(name.lower())}

    def serialize(self) -> Dict:
        return self.data

    def deserialize(self, dump: Dict):
        self.data.clear()
        for k, v in dump.items():
            if isinstance(k, str) and k.isdigit():
                k = int(k)
            self.data[k] = v


class CurCodes(Common):

    def __init__(self, text):
        super().__init__()
        for row in text.splitlines():
            val = row.split(';')
            self.data[int(val[0])] = {
                'id': int(val[0]),
                'code': val[1],
                'name': val[2]
            }

    def get_code(self, id_) -> Optional[str]:
        d = self.data.get(id_)
        if d:
            return d['code']
        else:
            return None


class PaymentCodes(Common):

    def __init__(self, text):
        super().__init__()
        for row in text.splitlines():
            val = row.split(';')
            self.data[int(val[0])] = {
                'id': int(val[0]),
                'code': val[1]
            }

    def get_code(self, id_) -> Optional[str]:
        d = self.data.get(id_)
        if d:
            return d['code']
        else:
            return None


class Currencies(Common):

    def __init__(self, text):
        super().__init__()
        for row in text.splitlines():
            val = row.split(';')
            self.data[int(val[0])] = {
                'id': int(val[0]),
                'pos_id': int(val[1]),
                'name': val[2],
                'payment_code': None,
                'cur_id': int(val[4]),
                'cur_code': None
            }

        self.data = dict(sorted(self.data.items(), key=lambda x: x[1]['name']))

    def apply_payment_codes(self, codes: PaymentCodes):
        for id_, d in self.data.items():
            d['payment_code'] = codes.get_code(id_)

    def apply_fiat_codes(self, codes: CurCodes):
        for id_, d in self.data.items():
            d['cur_code'] = codes.get_code(d['cur_id'])

    def filter(self, **attrs) -> List[dict]:
        result = []
        for d in self.data.values():
            success = True
            for a, v in attrs.items():
                if a not in d:
                    success = False
                    break
                if d[a] != v:
                    success = False
                    break
            if success:
                result.append(d)
        return result

    def filter_by_name(self, part: str) -> List[dict]:
        result = []
        for d in self.data.values():
            if part.lower() in d['name'].lower():
                result.append(d)
        return result


class Exchangers(Common):

    def __init__(self, text):
        super().__init__()
        for row in text.splitlines():
            val = row.split(';')
            self.data[int(val[0])] = {
                'id': int(val[0]),
                'name': val[1],
                'wmbl': int(val[3]),
                'reserve_sum': float(val[4]),
            }

        self.data = dict(sorted(self.data.items()))

    def extract_reviews(self, rates):
        for k, v in groupby(sorted(rates, key=lambda x: x['exchange_id']), lambda x: x['exchange_id']):
            if k in self.data.keys():
                self.data[k]['reviews'] = list(v)[0]['reviews']


class Cities(Common):

    def __init__(self, text):
        super().__init__()
        for row in text.splitlines():
            val = row.split(';')
            self.data[int(val[0])] = {
                'id': int(val[0]),
                'name': val[1],
            }

        self.data = dict(sorted(self.data.items(), key=lambda x: x[1]['name']))


class BestChangeRatios(BaseP2PRatioEngine):

    REFRESH_TTL_SEC = 5 * 60  # 5 min
    CACHE_VALUES_KEY = 'values'

    class BestChangeSettings(BaseP2PRatioEngine.P2PSettings):
        url: str = 'http://api.bestchange.ru/info.zip'
        enc: str = 'windows-1251'
        file_currencies: str = 'bm_cy.dat'
        file_exchangers: str = 'bm_exch.dat'
        file_rates: str = 'bm_rates.dat'
        file_cities: str = 'bm_cities.dat'
        file_top: str = 'bm_top.dat'
        file_payment_codes: str = 'bm_cycodes.dat'
        file_cur_codes: str = 'bm_bcodes.dat'
        zip_path: str = '/tmp/bestchange.zip'
        split_reviews: bool = False

    settings: BestChangeSettings = BestChangeSettings()

    def __init__(self, refresh_cache: bool = False, forced_zip_file: str = None):
        super().__init__(refresh_cache=refresh_cache)
        self._forced_zip_file = forced_zip_file

    async def load_from_server(self) -> Tuple[Rates, Currencies, Exchangers, Cities]:
        if self._forced_zip_file:
            zip_path = self._forced_zip_file
        else:
            if os.path.isfile(self.settings.zip_path):
                os.remove(self.settings.zip_path)
            async with aiohttp.ClientSession() as session:
                async with session.get(self.settings.url) as response:
                    data = await response.read()
                    with open(self.settings.zip_path, "wb") as f:
                        f.write(data)
            zip_path = self.settings.zip_path

        return await self.load_from_zip(zip_path)

    async def load_from_zip(self, path: str) -> Tuple[Rates, Currencies, Exchangers, Cities]:  # noqa

        if not os.path.isfile(path):
            raise RuntimeError(f'File "{path}" does not exists!')

        zipfile = ZipFile(path)
        files = zipfile.namelist()

        if self.settings.file_rates not in files:
            raise Exception(
                'File "{}" not found'.format(self.settings.file_rates))

        if self.settings.file_currencies not in files:
            raise Exception(
                'File "{}" not found'.format(self.settings.file_currencies))

        if self.settings.file_exchangers not in files:
            raise Exception(
                'File "{}" not found'.format(self.settings.file_exchangers))

        if self.settings.file_cities not in files:
            raise Exception(
                'File "{}" not found'.format(self.settings.file_cities))

        if self.settings.file_top not in files:
            raise Exception(
                'File "{}" not found'.format(self.settings.file_top))

        if self.settings.file_cur_codes not in files:
            raise Exception(
                'File "{}" not found'.format(self.settings.file_cur_codes))

        if self.settings.file_payment_codes not in files:
            raise Exception(
                'File "{}" not found'.format(self.settings.file_payment_codes))

        with zipfile.open(self.settings.file_rates) as f:
            with TextIOWrapper(f, encoding=self.settings.enc) as r:
                rates = Rates(r.read(), self.settings.split_reviews)

        with zipfile.open(self.settings.file_payment_codes) as f:
            with TextIOWrapper(f, encoding=self.settings.enc) as r:
                payment_codes = PaymentCodes(r.read())

        with zipfile.open(self.settings.file_cur_codes) as f:
            with TextIOWrapper(f, encoding=self.settings.enc) as r:
                fiat_codes = CurCodes(r.read())

        with zipfile.open(self.settings.file_currencies) as f:
            with TextIOWrapper(f, encoding=self.settings.enc) as r:
                currencies = Currencies(r.read())
                currencies.apply_payment_codes(payment_codes)
                currencies.apply_fiat_codes(fiat_codes)

        with zipfile.open(self.settings.file_exchangers) as f:
            with TextIOWrapper(f, encoding=self.settings.enc) as r:
                exchangers = Exchangers(r.read())

        with zipfile.open(self.settings.file_cities) as f:
            with TextIOWrapper(f, encoding=self.settings.enc) as r:
                cities = Cities(r.read())

        return rates, currencies, exchangers, cities

    async def save_to_cache(
        self, rates: Rates, currencies: Currencies,
        exchangers: Exchangers, cities: Cities, ttl=None
    ) -> float:
        utc_ = utc_now_float()
        await self._cache.set(
            key=self.CACHE_VALUES_KEY,
            value={
                'rates': rates.serialize(),
                'currencies': currencies.serialize(),
                'exchangers': exchangers.serialize(),
                'cities': cities.serialize(),
                'utc': utc_
            },
            ttl=ttl or self.REFRESH_TTL_SEC
        )
        return utc_

    async def load_metadata(
        self
    ) -> Tuple[Rates, Currencies, Exchangers, Cities]:
        # игнорируем условие "if self.refresh_cache", т.к. оно применяется
        # локально только к ордерам а не метаданным ZIP архива
        # экономия времени выполнения exchange_cron
        cached = await self._cache.get(key=self.CACHE_VALUES_KEY)
        if not cached:
            rates, currencies, exchangers, cities = await self.load_from_server()  # noqa
            utc_stamp = await self.save_to_cache(rates, currencies, exchangers, cities)
            rates.set_utc(utc_stamp)
            return rates, currencies, exchangers, cities
        else:
            utc_stamp = cached['utc']
            rates = Rates('', False)
            rates.set_utc(utc_stamp)
            currencies = Currencies('')
            exchangers = Exchangers('')
            cities = Cities('')
            rates.deserialize(cached['rates'])
            currencies.deserialize(cached['currencies'])
            exchangers.deserialize(cached['exchangers'])
            cities.deserialize(cached['cities'])
            rates.set_utc(utc_stamp)
            return rates, currencies, exchangers, cities

    async def load_orders(
        self, token: str = None, fiat: str = None,
        page: int = 0, pg_size: int = None,
        give: str = None, get: str = None
    ) -> Optional[P2POrders]:
        orders: Optional[P2POrders] = None
        if give and fiat:
            raise RuntimeError(f'Unexpected args configuration')
        if get and token:
            raise RuntimeError(f'Unexpected args configuration')
        if fiat:
            give = fiat
        if token:
            get = token
        cache_orders_key = f'get:{get};give:{give}'
        if self.refresh_cache:
            raw = None
        else:
            raw = await self._cache.get(cache_orders_key)
        if raw:
            try:
                orders = P2POrders.model_validate(raw)
            except ValueError as e:
                pass
        if not orders:
            rates, currencies, exchangers, cities = await self.load_metadata()
            # asks (i give fiat get token)
            asks_gives = currencies.filter(cur_code=give)
            if not asks_gives:
                asks_gives = currencies.filter_by_name(part=give)
            asks_gets = currencies.filter_by_name(part=get)
            asks_give_ids = [d['id'] for d in asks_gives]
            asks_get_ids = [d['id'] for d in asks_gets]
            asks = self._build_orders(
                give_ids=asks_give_ids, get_ids=asks_get_ids,
                src=give, dest=get,
                rates=rates, currencies=currencies, ex=exchangers
            )
            # asks = sorted(asks, key=lambda x: x.price)
            # bids (i give token get fiat)
            bids_gives = currencies.filter_by_name(part=get)
            bids_gets = currencies.filter(cur_code=give)
            if not bids_gets:
                bids_gets = currencies.filter_by_name(part=give)
            bids_give_ids = [d['id'] for d in bids_gives]
            bids_get_ids = [d['id'] for d in bids_gets]
            bids = self._build_orders(
                give_ids=bids_give_ids, get_ids=bids_get_ids,
                src=get, dest=give,
                rates=rates, currencies=currencies, ex=exchangers
            )
            # bids = sorted(bids, key=lambda x: x.price)
            orders = P2POrders(
                asks=asks,
                bids=bids
            )
            await self._cache.set(
                key=cache_orders_key,
                value=orders.model_dump(mode='json'),
                ttl=self.REFRESH_TTL_SEC
            )
        return orders

    @classmethod
    def _build_orders(
        cls, give_ids: List[int], get_ids: List[int], src: str, dest: str,
        rates: Rates, currencies: Currencies, ex: Exchangers
    ) -> List[P2POrder]:
        orders_ids = set()
        rates = rates.filter(give_id=give_ids, get_id=get_ids)
        orders: List[P2POrder] = []
        for r in rates:
            ex_name = ex.get_by_id(r['exchange_id'], only_name=True)
            give_cur = currencies.get_by_id(r['give_id'], only_name=False)
            get_cur = currencies.get_by_id(r['get_id'], only_name=False)
            if give_cur and get_cur and ex_name:
                order_id = f'{ex_name}:{src}-{dest}:' + give_cur['payment_code'] + '-' + get_cur['payment_code']  # noqa
                if order_id not in orders_ids:
                    orders_ids.add(order_id)
                    if r['get'] > r['give']:
                        price = r['get']
                    else:
                        price = r['give']
                    order = P2POrder(
                        id=order_id,
                        trader_nick=ex_name,
                        price=price,
                        min_amount=r['min_sum'],
                        max_amount=r['max_sum'],
                        pay_methods=[give_cur['name'], get_cur['name']],
                        bestchange_codes=[
                            give_cur['payment_code'], get_cur['payment_code']
                        ],
                        utc=r['utc']
                    )
                    orders.append(order)
        return orders
