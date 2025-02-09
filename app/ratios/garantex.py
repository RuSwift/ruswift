import json
import base64
import time
import datetime
import random
from urllib.parse import urljoin
from typing import List, Optional, Dict, Literal, Union

import jwt
from aiohttp import ClientSession
from pydantic import BaseModel, Field

from core.utils import utc_now_float
from entities import (
    ExchangePair, P2POrders, P2POrder, BestChangeMethodMapping
)
from ratios import (
    BaseRatioEngine, BaseP2PRatioEngine
)
from context import context


class GarantexAuthMixin:

    """Документация: https://garantexio.github.io/
    """

    def __init__(self, **kwargs):
        self._token = None
        super().__init__(**kwargs)

    @property
    def is_auth(self) -> bool:
        return self._token is not None

    async def _auth(
        self, host: str, private_key: str, uid: str, exp_ttl: int
    ) -> Optional[str]:
        key = base64.b64decode(private_key)
        iat = int(time.mktime(datetime.datetime.now().timetuple()))
        claims = {
            "exp": iat + exp_ttl,
            "jti": hex(random.getrandbits(12)).upper()
        }

        jwt_token = jwt.encode(claims, key, algorithm="RS256")
        url = f'https://dauth.{host}/api/v1/sessions/generate_jwt'  # noqa
        async with ClientSession() as cli:
            resp = await cli.post(
                url,
                json={'kid': uid, 'jwt_token': jwt_token},
                allow_redirects=True
            )
            if resp.ok:
                d = await resp.json()
                self._token = d.get('token')
                return self._token
            else:
                return None

    async def _make_request(
        self, method: Literal['GET', 'POST'], path: str, host: str,
        cache_timeout: int = None, **params
    ) -> Union[Dict, List, None]:
        suf = json.dumps(params, sort_keys=True)
        cache_key = f'{path}?{suf}'
        if self.refresh_cache:
            value = None
        else:
            value = await self._cache.get(path)
        if value:
            return value
        if not self.is_auth:
            raise RuntimeError('Not Authorized')
        if host.startswith('http'):
            base = host
        else:
            base = f'https://{host}'
        url = urljoin(base, path)
        headers = {'Authorization': 'Bearer ' + self._token}
        async with ClientSession() as cli:
            if method == 'GET':
                coro = cli.get
                kwargs = {'params': params}
            else:
                coro = cli.post
                kwargs = {'json': params}
            resp = await coro(
                url,
                allow_redirects=True,
                headers=headers,
                **kwargs
            )
            if resp.ok:
                value = await resp.json()
                if value and cache_timeout is not None:
                    await self._cache.set(
                        cache_key, value, ttl=cache_timeout
                    )
                return await resp.json()
            else:
                return None


class GarantexEngine(GarantexAuthMixin, BaseRatioEngine):

    CACHE_MARKET_DATA_TTL = 24 * 60 * 60  # 1 day

    class EngineSettings(BaseRatioEngine.EngineSettings):
        # приватный ключ, полученный на этапе создания API ключей
        private_key: str
        # UID, полученный на этапе создания API ключей
        uid: str
        # для тестового сервера используйте stage.garantex.biz
        host: str = 'garantex.org'
        # JWT Request TTL in seconds since epoch
        ttl: int = 1 * 60 * 60

        filter_markets: List[str] = [
            'USDT/RUB', 'ETH/RUB', 'USDC/RUB', 'DAI/RUB', 'BTC/RUB'
        ]

    settings: EngineSettings

    class MarketData(BaseModel):
        id: str
        name: str
        ask_unit: str
        bid_unit: str
        min_ask: float
        min_bid: float

    async def auth(self) -> Optional[str]:
        return await self._auth(
            self.settings.host, self.settings.private_key,
            self.settings.uid, self.settings.ttl
        )

    async def market(self) -> List[ExchangePair]:
        pairs = []
        if not self.refresh_cache:
            cached = await self._cache.get(key='market')
            if cached:
                for d in cached:
                    pairs.append(ExchangePair.model_validate(d))
                return pairs

        if not self._token:
            await self.auth()
        markets = await self.load_markets()
        for market in markets:
            depth = await self.load_depth(market.id)
            if not depth:
                raise RuntimeError(f'Error with fetch {market.id} depth')
            ask = depth['asks'][0]
            bid = depth['bids'][0]
            p = ExchangePair(
                base=market.bid_unit,
                quote=market.ask_unit,
                ratio=(float(ask['price']) + float(bid['price']))/2,
                utc=depth['timestamp']
            )
            pairs.append(p)
        await self._cache.set(
            key='market',
            value=[
                p.model_dump(mode='json') for p in pairs
            ],
            ttl=context.config.cache_timeout_sec
        )
        return pairs

    async def load_markets(self) -> Optional[List[MarketData]]:
        items = await self._make_request(
            method='GET', path='api/v2/markets', host=self.settings.host,
            cache_timeout=self.CACHE_MARKET_DATA_TTL
        )
        if items:
            data = [self.MarketData(**i) for i in items]
            result = []
            for d in data:
                if d.name in self.settings.filter_markets:
                    d.ask_unit = d.ask_unit.upper()
                    d.bid_unit = d.bid_unit.upper()
                    result.append(d)
            return result
        else:
            return None

    async def load_depth(self, market: str) -> Dict:
        depth = await self._make_request(
            method='GET', path='api/v2/depth',
            host=self.settings.host,
            cache_timeout=context.config.cache_timeout_sec,
            market=market
        )
        return depth


class GarantexP2P(GarantexAuthMixin, BaseP2PRatioEngine):

    class P2PSettings(GarantexEngine.EngineSettings):
        bestchange_mapping: BestChangeMethodMapping = Field(default_factory=BestChangeMethodMapping.default_factory)  # noqa

    class GarantexP2POrder(P2POrder):
        premium: float

    settings: P2PSettings

    def __init__(self, refresh_cache: bool = False):
        super().__init__(refresh_cache=refresh_cache)
        self._cex = GarantexEngine()

    async def auth(self) -> Optional[str]:
        token = await self._auth(
            self.settings.host, self.settings.private_key,
            self.settings.uid, self.settings.ttl
        )
        self._cex._token = token
        return token

    async def load_orders(
        self, token: str, fiat: str,
        page: int = 0, pg_size: int = None
    ) -> Optional[P2POrders]:
        if not self._token:
            await self.auth()
        if token != fiat:
            pair = await self._cex.ratio(base=fiat, quote=token)
            if pair is None:
                return None
            rate = pair.ratio
        else:
            rate = 1.0
        # покупают код биржи
        buyers = await self._make_request(
            method='GET', path='api/v2/otc/ads',
            host=self.settings.host,
            direction='buy',
            currency=fiat.lower()
        )
        # продают код биржи
        sellers = await self._make_request(
            method='GET', path='api/v2/otc/ads',
            host=self.settings.host,
            direction='sell',
            currency=fiat.lower()
        )
        return P2POrders(
            bids=[self._extract_order(d, rate=rate) for d in buyers],
            asks=[self._extract_order(d, rate=rate) for d in sellers]
        )

    def _extract_order(self, d: Dict, rate: float) -> GarantexP2POrder:
        order = self.GarantexP2POrder(
            id=str(d['id']),
            trader_nick=d['member'],
            price=float(d['price']) * rate,
            min_amount=float(d['min']),
            max_amount=float(d['max']),
            pay_methods=[d['payment_method']],
            description=d['description'],
            premium=(1 - float(d['price'])) * 100 * -1,
            utc=utc_now_float()
        )
        if self.settings.bestchange_mapping:
            order.bestchange_codes = self.settings.bestchange_mapping.match_codes(d['payment_method'])  # noqa
            order.pay_methods = order.bestchange_codes
        if 'verified_only' in d:
            order.verified_only = d['verified_only']
        if 'member_official_partner' in d:
            order.is_merchant = d['member_official_partner']
        if 'member_verified' in d:
            order.is_verified = d['member_verified']
        return order
