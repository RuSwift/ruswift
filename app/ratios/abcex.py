import json
from typing import Literal, Union, Dict, List
from urllib.parse import urljoin

class ABCExAuthMixin:

    """Документация: https://apidocs.abcex.io/
    """

    async def _make_request(
        self, method: Literal['GET', 'POST'], path: str, host: str,
        token: str, cache_timeout: int = None, **params
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
        headers = {'Authorization': 'Bearer ' + token}
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