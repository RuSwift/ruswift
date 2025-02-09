import asyncio
import json
import logging
from typing import List, Optional, Dict
from urllib.parse import urljoin

import aiohttp
from pydantic import Field
from aiohttp import ClientSession

from core.utils import utc_now_float
from entities import (
    ExchangePair, P2POrders, P2POrder, BestChangeMethodMapping
)
from ratios import BaseRatioEngine, BaseP2PRatioEngine
from context import context


class HTXEngine(BaseRatioEngine):

    HTX_API_HOST = "https://api.huobi.pro"
    HTX_API_PREFIX = ""
    HTX_API_HEADERS = {'Content-Type': 'application/json'}

    async def market(self) -> List[ExchangePair]:
        if self.refresh_cache:
            data = None
        else:
            data = await self._cache.get('market')
        if not data:
            data = await self.load_from_internet()
            await self._cache.set(
                'market', data, context.config.cache_timeout_sec
            )
        pairs = []
        for item in data['data']:
            b_q = self.__from_exchange_symbol(item["symbol"])
            if b_q:
                quote, base = b_q.split('/')
                p = ExchangePair(
                    base=base,
                    quote=quote,
                    ratio=(float(item["bid"])+float(item["ask"]))/2,
                    utc=float(data['ts'])//1000
                )
                pairs.append(p)
        return pairs

    @classmethod
    async def load_from_internet(cls) -> Optional[Dict]:
        url = cls.HTX_API_HOST + cls.HTX_API_PREFIX + '/market/tickers'
        async with ClientSession(headers=cls.HTX_API_HEADERS) as cli:
            resp = await cli.get(url, allow_redirects=True)
            if resp.ok:
                raw = await resp.text()
                return json.loads(raw)
            else:
                return None

    @staticmethod
    def __from_exchange_symbol(exchange_symbol: str) -> Optional[str]:
        exchange_symbol = exchange_symbol.upper()
        bases = ["USDT", "BTC", "ETH", "USDC", "TUSD", "HT"]
        for base in bases:
            if exchange_symbol.endswith(base):
                return f"{exchange_symbol[0:-len(base)]}/{base}"
        return None


class HTXP2P(BaseP2PRatioEngine):

    class P2PSettings(HTXEngine.EngineSettings):
        base_url: str = 'https://www.htx.com'
        bestchange_mapping: BestChangeMethodMapping = Field(default_factory=BestChangeMethodMapping.default_factory)  # noqa
        cache_config_ttl: int = 60*60  # 1 hr
        retry_429_limit: int = 3
        retry_429_timeout: int = 1

    settings: P2PSettings = P2PSettings()

    @classmethod
    def make_url(cls, path: str) -> str:
        if path.startswith('/'):
            path = path[1:]
        base = urljoin(cls.settings.base_url, '/-/x/otc/v1/')
        return urljoin(base, path)

    async def load_orders(
        self, token: str, fiat: str, page: int = 0, pg_size: int = None
    ) -> Optional[P2POrders]:
        orders: Optional[P2POrders] = None
        cache_orders_key = f'token:{token};fiat:{fiat}'
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
            config = await self.load_config()
            cur_info = self._extract_currency_info(config, fiat)
            coin_info = self._extract_coin_info(config, token)
            async with ClientSession() as cli:
                # asks
                sell = await self._load_pages(
                    coin_id=coin_info['coinId'],
                    currency=cur_info['currencyId'],
                    side='sell', session=cli
                )
                # bids
                buy = await self._load_pages(
                    coin_id=coin_info['coinId'],
                    currency=cur_info['currencyId'],
                    side='buy', session=cli
                )

                orders = P2POrders(
                    asks=[self._extract_order(d) for d in sell],
                    bids=[self._extract_order(d) for d in buy]
                )
                await self._cache.set(
                    key=cache_orders_key,
                    value=orders.model_dump(mode='json'),
                    ttl=context.config.cache_timeout_sec
                )
        return orders

    async def load_config(self) -> Dict:
        cache_key = 'config'
        cached = await self._cache.get(cache_key)
        if cached:
            return cached
        url = self.make_url('/data/config-list')
        async with ClientSession() as cli:
            resp = await cli.get(
                url,
                params={
                    'type': 'currency,marketQuery,pay,allCountry,coin'
                },
                allow_redirects=True
            )
            if resp.ok:
                raw = await resp.text()
                resp = json.loads(raw)
                if resp['code'] == 200:
                    cfg = resp['data']
                    await self._cache.set(
                        key=cache_key, value=cfg,
                        ttl=self.settings.cache_config_ttl
                    )
                    return cfg
                else:
                    raise RuntimeError(resp['message'])
            else:
                err = await resp.text()
                raise RuntimeError(err)

    @classmethod
    async def _load_pages(
        cls, coin_id: int, currency: int, side: str,
        session: aiohttp.ClientSession
    ) -> List[Dict]:
        pg = 1
        items = []

        async def _load_page(pg_no: int) -> Dict:
            for n in range(cls.settings.retry_429_limit):
                resp = await session.get(
                    url=cls.make_url('/data/trade-market'),
                    params={
                        'coinId': coin_id,
                        'currency': currency,
                        'tradeType': side,
                        'currPage': pg_no,
                        'blockType': 'general',
                        'online': 1
                    }
                )
                if resp.ok:
                    raw = await resp.text()
                    data = json.loads(raw)
                    if data['code'] != 200:
                        raise RuntimeError(data['message'])
                    return data
                else:
                    if resp.status == 429:
                        logging.warning(f'HTX: 429 status [{n}], sleep')
                        await asyncio.sleep(cls.settings.retry_429_timeout)
                    else:
                        err = await resp.text()
                        raise RuntimeError(err)

        first_page = await _load_page(pg)
        total_pages = first_page['totalPage']
        items.extend(first_page['data'])
        for pg in range(2, total_pages+1):
            page = await _load_page(pg)
            sub = page['data']
            if sub:
                items.extend(sub)
            else:
                break
        return items

    def _extract_order(self, src: Dict) -> P2POrder:
        order = P2POrder(
            id=str(src['id']),
            trader_nick=src['userName'],
            price=src['price'],
            min_amount=src['minTradeLimit'],
            max_amount=src['maxTradeLimit'],
            pay_methods=[m['name'] for m in src['payMethods']],
            is_merchant=src['merchantLevel'] > 0,
            utc=utc_now_float()
        )
        if self.settings.bestchange_mapping:
            methods = ', '.join(order.pay_methods)
            order.bestchange_codes = self.settings.bestchange_mapping.match_codes(methods)  # noqa
        return order

    @classmethod
    def _extract_currency_info(cls, config: Dict, symbol: str) -> Dict:
        currencies = config.get('currency', [])
        for cur in currencies:
            if cur['nameShort'] == symbol or cur['symbol'] == symbol:
                return cur
        raise RuntimeError(f'Not found currency with symbol "{symbol}"')

    @classmethod
    def _extract_coin_info(cls, config: Dict, symbol: str) -> Dict:
        coins = config.get('coin', [])
        for coin in coins:
            if coin['shortName'] == symbol or coin['coinCode'] == symbol:
                return coin
        raise RuntimeError(f'Not found coin with symbol "{symbol}"')
