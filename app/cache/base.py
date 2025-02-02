import json
from typing import Optional, AsyncIterator, Union, List, Dict
from contextlib import asynccontextmanager

from django.conf import settings

import aioredis


class Cache:

    _namespace_sep = '::'
    _ignore_pool = True  # ошибка из-за смены event-loop

    def __init__(self, pool: aioredis.ConnectionPool, namespace: str = None):
        self.__pool = pool
        self.__namespace = namespace

    async def set(
        self, key: Union[str, List[str]],
        value: Union[Dict, List[Dict]],
        ttl: int = None
    ):
        async with self.allocate_connection() as conn:
            if isinstance(key, str):
                await conn.set(self._full_key(key), json.dumps(value), ex=ttl)
            else:
                if not isinstance(value, List):
                    raise RuntimeError(f'Unexpected value type!')
                if len(key) != len(value):
                    raise RuntimeError(
                        f'Keys and Values arrays must to '
                        f'have the same lengths!'
                    )
                keys_ = self._full_keys(key)
                mapping = {k: json.dumps(v) for k, v in zip(keys_, value)}
                await conn.mset(mapping)
                if ttl:
                    for k in key:
                        await conn.expire(k, ttl)

    async def get(self, key: Union[str, List[str]]) -> Optional[Dict]:
        async with self.allocate_connection() as conn:
            if isinstance(key, str):
                raw = await conn.get(self._full_key(key))
                if raw is None:
                    return None
                else:
                    return json.loads(raw)
            else:
                keys_ = self._full_keys(key)
                raws = await conn.mget(keys=keys_)
                result = {
                    self._extract_key(k): json.loads(v) if v else v
                    for k, v in zip(key, raws)
                }
                return result

    def namespace(self, value: str) -> 'Cache':
        if value:
            if self.__namespace:
                namespace = self.__namespace + self._namespace_sep + value
            else:
                namespace = value
            return Cache(pool=self.__pool, namespace=namespace)
        else:
            return self

    async def delete(self, key: Union[str, List[str]]):
        if not key:
            return
        async with self.allocate_connection() as conn:
            if isinstance(key, str):
                await conn.delete(self._full_key(key))
            else:
                await conn.delete(*[self._full_key(k) for k in key])

    async def keys(self, pattern: str = '*') -> List[str]:
        async with self.allocate_connection() as conn:
            keys = await conn.keys(self._full_key(pattern))
            if self.__namespace:
                return [self._extract_key(k.decode()) for k in keys]
            else:
                return [k.decode() for k in keys]

    async def flush(self):
        async with self.allocate_connection() as conn:
            await conn.flushdb()

    @asynccontextmanager
    async def allocate_connection(self) -> AsyncIterator[aioredis.Redis]:
        if self._ignore_pool:
            conn = aioredis.Redis(**self.__pool.connection_kwargs)
        else:
            conn = aioredis.Redis(connection_pool=self.__pool)
        try:
            yield conn
        finally:
            await conn.close()

    def _full_key(self, key: str) -> str:
        if self.__namespace:
            return f'{self.__namespace}{self._namespace_sep}{key}'
        else:
            return key

    def _full_keys(self, keys: List[str]) -> List[str]:
        return [self._full_key(k) for k in keys]

    def _extract_key(self, full_key: str) -> str:
        if self._namespace_sep in full_key:
            return full_key.split(self._namespace_sep)[-1]
        else:
            return full_key


class ImplicitCacheMixin:

    _namespace: str = None
    _cache = Cache(pool=settings.REDIS_CONN_POOL)

    def __init_subclass__(cls, **kwargs):
        namespace = cls._namespace or cls.__name__
        cls._cache = cls._cache.namespace(namespace)
        super().__init_subclass__(**kwargs)
