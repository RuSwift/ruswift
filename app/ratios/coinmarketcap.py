import json
from typing import List, Optional, Dict
from datetime import datetime

from aiohttp import ClientSession

from entities import ExchangePair
from ratios import BaseRatioEngine
from context import context
from core import datetime_to_float


class CoinMarketCapEngine(BaseRatioEngine):

    class EngineSettings(BaseRatioEngine.EngineSettings):
        api_key: str

    settings: EngineSettings

    async def market(self) -> List[ExchangePair]:
        if self.refresh_cache:
            data = None
        else:
            data = await self._cache.get('market')
        if not data:
            data = await self.load_from_internet()
            if data is None:
                raise RuntimeError('CoinmarketCap Error')
            await self._cache.set(
                'market', data, context.config.cache_timeout_sec
            )
        pairs = []
        for item in data['data']:
            quote = item['symbol']
            for base, desc in item['quote'].items():
                ts = desc['last_updated'].split('.')[0]
                dt = datetime.fromisoformat(ts)
                p = ExchangePair(
                    base=base,
                    quote=quote,
                    ratio=desc['price'],
                    utc=datetime_to_float(dt)
                )
                pairs.append(p)
        return pairs

    async def load_from_internet(self, limit: int = 200) -> Optional[Dict]:
        url = f'https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest?CMC_PRO_API_KEY={self.settings.api_key}&limit={limit}'  # noqa
        async with ClientSession() as cli:
            resp = await cli.get(url, allow_redirects=True, verify_ssl=False)
            if resp.ok:
                raw = await resp.text()
                return json.loads(raw)
            else:
                return None
