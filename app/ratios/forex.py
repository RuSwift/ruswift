import json
from typing import List, Optional, Dict

from aiohttp import ClientSession

from entities import ExchangePair

from ratios import BaseRatioEngine
from context import context


class ForexEngine(BaseRatioEngine):

    REFRESH_TTL_SEC = 60*15  # 15 min

    async def market(self) -> List[ExchangePair]:
        if self.refresh_cache:
            data = None
        else:
            data = await self._cache.get('market')
        if not data:
            data = await self.load_from_internet()
            await self._cache.set(
                'market', data, self.REFRESH_TTL_SEC
            )
        base = data['base']
        pairs = []
        for quote, ratio in data['quotes'].items():
            p = ExchangePair(
                base=base,
                quote=quote,
                ratio=ratio,
                utc=data['ts']
            )
            pairs.append(p)
        return pairs

    @classmethod
    async def load_from_internet(cls) -> Optional[Dict]:
        url = 'https://raw.githubusercontent.com/ismartcoding/currency-api/main/latest/data.json'  # noqa
        async with ClientSession() as cli:
            resp = await cli.get(url, allow_redirects=True)
            if resp.ok:
                raw = await resp.text()
                return json.loads(raw)
            else:
                return None
