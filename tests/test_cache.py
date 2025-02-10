import uuid
import asyncio

import pytest
from aioredis import ConnectionPool as RedisConnectionPool

from cache import Cache


@pytest.mark.asyncio
class TestCache:

    @pytest.fixture
    def cache(self, redis_dsn: str) -> Cache:
        return Cache(
            pool=RedisConnectionPool.from_url(redis_dsn)
        )

    async def test_sane(self, cache: Cache):
        key = 'some-key-' + uuid.uuid4().hex
        # 1.
        val = await cache.get(key)
        assert val is None
        # 2.
        val = {'key1': 'value-1', 'key2': 123}
        await cache.set(key, val)
        fetched_val = await cache.get(key)
        assert val == fetched_val
        # 3. check ttl timeouts
        await cache.set(key, val, ttl=1)
        await asyncio.sleep(1.1)
        fetched_val = await cache.get(key)
        assert fetched_val is None

    async def test_multiple_get(self, cache: Cache):
        key1 = 'some-key-' + uuid.uuid4().hex
        key2 = 'some-key-' + uuid.uuid4().hex
        val1 = {'key': 'value-1'}
        val2 = {'key': 'value-2'}
        # step1
        ret = await cache.get(key=[key1, key2])
        assert len(ret) == 2
        assert key1 in ret and key2 in ret
        assert all(v is None for v in ret.values())
        # step2
        for k, v in zip([key1, key2], [val1, val2]):
            await cache.set(k, v)
        ret = await cache.get(key=[key1, key2])
        assert len(ret) == 2
        assert key1 in ret and key2 in ret
        assert ret[key1] == val1
        assert ret[key2] == val2

    async def test_multiple_set(self, cache: Cache):
        key1 = 'some-key-' + uuid.uuid4().hex
        key2 = 'some-key-' + uuid.uuid4().hex
        val1 = {'key': 'value-1'}
        val2 = {'key': 'value-2'}
        await cache.set(key=[key1, key2], value=[val1, val2])
        for k, expected in zip([key1, key2], [val1, val2]):
            actual = await cache.get(k)
            assert expected == actual

    async def test_delete(self, cache: Cache):
        # 1. set if value empty
        key1 = 'some-key-' + uuid.uuid4().hex
        key2 = 'some-key-' + uuid.uuid4().hex
        for key in [key1, key2]:
            await cache.set(key, value={'on': True})
        await cache.delete(key1)
        await cache.delete([key2])
        val1 = await cache.get(key1)
        val2 = await cache.get(key2)
        assert val1 is None
        assert val2 is None

    async def test_keys(self, cache: Cache):
        await cache.flush()
        await cache.set('key', {'value': 1})
        ns = cache.namespace('namespace')
        await ns.set('key', {'value': 1})
        ks = await cache.keys('*')
        kns = await ns.keys('*')
        assert len(ks) == 2
        assert len(kns) == 1
