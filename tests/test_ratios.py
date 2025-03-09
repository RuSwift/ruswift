import pytest

from ratios import (
    ForexEngine, HTXEngine, CoinMarketCapEngine,
    GarantexEngine, GarantexP2P, BestChangeRatios, HTXP2P
)
from context import Context
from entities import (
    ExchangeConfig, Account, BestChangeMethodMapping, BestChangeCodeRule,
    P2POrders
)


@pytest.mark.asyncio
class TestForexEngine:

    @pytest.fixture()
    def engine(self) -> ForexEngine:
        return ForexEngine()

    async def test_load_from_internet(self):
        data = await ForexEngine.load_from_internet()
        assert isinstance(data, dict)
        assert len(data) > 0

    async def test_market(
        self, exchange_config: ExchangeConfig, user: Account,
        engine: ForexEngine
    ):
        await ForexEngine.invalidate_cache()
        with Context.create_context(exchange_config, user):
            market = await engine.market()
            assert isinstance(market, list)
            assert len(market) > 0

    async def test_ratio(
        self, exchange_config: ExchangeConfig, user: Account,
        engine: ForexEngine
    ):
        await ForexEngine.invalidate_cache()
        with Context.create_context(exchange_config, user):
            p1 = await engine.ratio(base='RUB', quote='THB')
            assert p1
            p2 = await engine.ratio(base='USD', quote='THB')
            assert p2
            p3 = await engine.ratio(base='EUR', quote='RUB')
            assert p3


@pytest.mark.asyncio
class TestHTXEngine:

    @pytest.fixture()
    def engine(self) -> HTXEngine:
        return HTXEngine()

    @pytest.fixture()
    def p2p(self) -> HTXP2P:
        HTXP2P.settings = HTXP2P.P2PSettings(
            bestchange_mapping=BestChangeMethodMapping(
                codes={
                    'SBERRUB': BestChangeCodeRule(
                        **{'or': ['Sber']}
                    ),
                    'RFBRUB': BestChangeCodeRule(
                        **{'or': ['Raif']}
                    )
                }
            )
        )
        return HTXP2P()

    async def test_load_from_internet(self):
        data = await HTXEngine.load_from_internet()
        assert isinstance(data, dict)
        assert len(data) > 0

    async def test_market(
        self, exchange_config: ExchangeConfig, user: Account,
        engine: HTXEngine
    ):
        await HTXEngine.invalidate_cache()
        with Context.create_context(exchange_config, user):
            market = await engine.market()
            assert isinstance(market, list)
            assert len(market) > 0

    async def test_ratio(
        self, exchange_config: ExchangeConfig, user: Account,
        engine: ForexEngine
    ):
        await HTXEngine.invalidate_cache()
        with Context.create_context(exchange_config, user):
            p1 = await engine.ratio(base='USDT', quote='BTC')
            assert p1
            p2 = await engine.ratio(base='XRP', quote='BTC')
            assert p2

    async def test_p2p_orders(
        self, exchange_config: ExchangeConfig, user: Account,
        p2p: HTXP2P
    ):
        await p2p.invalidate_cache()
        with Context.create_context(exchange_config, user):
            cfg = await p2p.load_config()
            assert cfg
            orders = await p2p.load_orders(token='USDT', fiat='RUB')
            assert orders
            assert orders.asks and orders.bids
            filled_pm = [o for o in orders.asks if o.bestchange_codes]
            assert filled_pm


@pytest.mark.asyncio
class TestCoinMarketCapEngine:

    @pytest.fixture()
    def engine(self) -> CoinMarketCapEngine:
        CoinMarketCapEngine.settings = CoinMarketCapEngine.EngineSettings(
            api_key='83f6af9b-dcbc-445f-83aa-930a7255bc6e'
        )
        return CoinMarketCapEngine()

    async def test_load_from_internet(self, engine: CoinMarketCapEngine):
        data = await engine.load_from_internet()
        assert isinstance(data, dict)
        assert len(data) > 0

    async def test_market(
        self, exchange_config: ExchangeConfig, user: Account,
        engine: CoinMarketCapEngine
    ):
        await CoinMarketCapEngine.invalidate_cache()
        with Context.create_context(exchange_config, user):
            market = await engine.market()
            assert isinstance(market, list)
            assert len(market) > 0

    async def test_ratio(
        self, exchange_config: ExchangeConfig, user: Account,
        engine: CoinMarketCapEngine
    ):
        await CoinMarketCapEngine.invalidate_cache()
        with Context.create_context(exchange_config, user):
            p1 = await engine.ratio(base='USD', quote='BTC')
            assert p1
            p2 = await engine.ratio(base='XRP', quote='BTC')
            assert p2


@pytest.mark.asyncio
class TestGarantexEngine:

    PK = 'LS0tLS1CRUdJTiBSU0EgUFJJVkFURSBLRVktLS0tLQpNSUlFcEFJQkFBS0NBUUVBcE84ZGowQVZJaTREOVJFek1od1lWS01WUlhSRzF5aTZPS3Y0QXc3REw3Ni9FOE85CiszZnA1aGVKWkRhZG9FUWVENlIxOEgvSVNTNnFJUHFua2JzM2wxa2M1d3JaVnVyaXZGQjBqUmc2Y1B2Z1YrdkIKZHEyckl5Uys1RnREVS9mYzYzUkJ2SWxkNEhkN2tsZnpMWkpSSE5LMkpxZzk5TVZqN3Znc1ArTStlTS9yeGhTVgpYWFBkMVdhS216VnQ1RE8wR29sZmZkYTZRT3NiM1c0UDF3REtmZ0U1WUxlb09LNExhS0pFVE1sSnhQRDhTRzcwCmRwbTA2WWduVURaY05sZmVSZ2pvUTRUd210Qm1KRHk3YjJ4QTFOZ2ZZQkRRTmtXZW5OZWNCMkY0S2xRKy94NVgKaGppdEYvVHJEdWxqQTBvcTlrZk5ZNEwvblYrQW9RbjYzN0t6Y1FJREFRQUJBb0lCQUFadVFVbUt6dGdpa2FwdQpOWUFNYXVGdjYxNG1JclgwWTFCZTJpQnFaSzlab1ZNWXRIRlgwMUdTbE51SXFwd3JVNzI1NUpSUU15T3hVMVpPClY1YTl4VFRjTjEyRnhZUVhTK2hhUGJVYm52bTFSR0hCTWkyWnAxekxLN3MxR0xxdkpSaTBFM1VScVF5ZHMvNTQKZWVXS3VTbGx5TTdZaS9QZGQyQkRvbHdLVk83NllsZU8wQVhhdGV5UUJZS3VOOHRjekJHakdNWHpwRHM0c09Zdgo1WmYwQW5sVDlQWmVIMnEvdmxxYmw1d0QyQTNhb3ZGWlN1ZXdUc0tNUU5FeHNUNnNrbUxDT2tRUnRzSkhVSnhuCklRVnJUWk9Tc3ZKRDdoamV2L3NNMjU1ekRFQnoyMGZwUTQ4WjRSRHFzVUhyWlJZUkF0YjRma1NPWU55Znp6aGQKc2xidnIxRUNnWUVBMUR2QmhMdWRPa0JLaXg2UG85TVp2M1J2dkx3UWVkdzN2dUNka1UzQzJUakZ5NHdNRUJjeQpya0hMYmZicm5DOHc0OTVuKzk3ZjdkL0pVM0dMSVR3akMwaXVVbkw0SjRGekhKYWx6QjJYSk85MEJ4MmxrUzRNClhZZ0NmejNVVXZ1Q0MrSFBURXlFUGFTV0QyR3NPZVdlWUtGSkN0TDVreWZEOHlGMGg5NzY5VmtDZ1lFQXh2SlQKdFVWZVZvTWJQVUdkZ0Y4OHVoOHU2TUhJYi9IKzNjT0E1TDJnKzhmN1RsY0E3Sk5HNS8vTUVnOTljVTJseEU5QgpCMFdUdGtWNjNYRmRkNXBzQlVaZ3hPd2d6V2huVjQ2cTU0em8zdjdWN2RXVVQ2aHZxNHlGVENUNnRCS3UzRm9LCnZyODcyRXBreHRPcmc4bTdCeXYxOGQ5WDZqNFdaVzUxMkZQWU05a0NnWUVBMGxENVFBRHdHVmEyeUZDYnhad2YKeXVPbkN5QlBMNE8wMW5vZWkyekU1NkJrR29jSk9UVFQ2MjJXRzczeTFFN0xvelMyVlJvVFROWlUyMVVNcS8yOQpPS1JvNDVtOUl1RWNZcnREU0JnV3ZPcHlUODdvVVF1U0Eyb1NGMmY5TGRMQmwrYkpGL0pIcGhLaEJsTWphaWlMCkgzVVZQaDIrWno2ajV4OURMSllpbWRrQ2dZRUFuWXBkb1NrYWFGV1A1M1VqUFBtdHhCRlhlemVnK296ZWIwd1cKc0l3OWc4UThEREEzYWgvQ1FZczlWWHZ3c1IxMHpEeWFXU0RPdE1MV1phOFUvZFpKL2U5YVIvWllqM0JDallKTApjZXNTcVN1UnlyR2JyV3pMYVVSd2RmaStrb1JNOWU5VG5QTWdkOG1KZmkwMkg3bEtvb1k4VDFtMmE2Ylk0MStTCmNFa001eGtDZ1lBcnpDeEFLdjZIWVphZktrVmdrQUw2VXg3VlU0MmtvY3BrMjJOOTNCbCtUdjVDa2NzQ2FNamQKS0ZySm9jSjhYTG45ZXNNZXhhZERWN3FMRG90ZlVLN0t1bVg1WmpMaFRmOWtOZ0VCVkJZbmNpMlZ4SG5hbmxhTwprNzZtS011WkdoMnJUQUU4MkZ5U3N3SUpsNDdZZEZGVG54RHFVS1A5WGpSMnNQYzRsZlIyQkE9PQotLS0tLUVORCBSU0EgUFJJVkFURSBLRVktLS0tLQo='  # noqa
    UID = 'e8065c6a-29f4-4fde-9372-adc0054b8270'

    @pytest.fixture()
    def engine(self) -> GarantexEngine:
        GarantexEngine.settings = GarantexEngine.EngineSettings(
            private_key=self.PK,
            uid=self.UID,
        )
        return GarantexEngine()

    @pytest.fixture()
    def p2p(self, engine) -> GarantexP2P:
        GarantexP2P.settings = GarantexP2P.P2PSettings(
            private_key=self.PK,
            uid=self.UID,
            bestchange_mapping = BestChangeMethodMapping(
                codes={
                    'SBERRUB': BestChangeCodeRule(
                        **{'or': ['Сбер', 'SBER']}
                    ),
                    'RFBRUB': BestChangeCodeRule(
                        **{'or': ['Райф', 'Raif']}
                    )
                },
                ignores=[
                    BestChangeCodeRule(
                        **{'or': ['CNY', 'AliPay']}
                    )
                ]
            )
        )
        return GarantexP2P()

    async def test_sane(
        self, exchange_config: ExchangeConfig, user: Account,
        engine: GarantexEngine
    ):
        await GarantexEngine.invalidate_cache()
        with Context.create_context(exchange_config, user):
            token = await engine.auth()
            assert isinstance(token, str)
            assert len(token) > 0
            assert engine.is_auth

            markets = await engine.load_markets()
            assert markets and len(markets) > 0

            depth = await engine.load_depth(market=markets[0].id)
            assert depth

    async def test_market(
        self, exchange_config: ExchangeConfig, user: Account,
        engine: GarantexEngine
    ):
        with Context.create_context(exchange_config, user):
            await engine.auth()
            market = await engine.market()
            assert market

            ratio1 = await engine.ratio(base='USDT', quote='RUB')
            assert ratio1
            ratio2 = await engine.ratio(base='RUB', quote='USDT')
            assert ratio2
            ratio3 = await engine.ratio(base='BTC', quote='RUB')
            assert ratio3

    async def test_p2p_orders(
        self, exchange_config: ExchangeConfig, user: Account,
        p2p: GarantexP2P
    ):
        with Context.create_context(exchange_config, user):
            await p2p.auth()
            orders = await p2p.load_orders(token='RUB', fiat='RUB')
            assert orders
            assert len(orders.asks) > 0
            assert len(orders.bids) > 0
            filled_pm = [o for o in orders.asks if o.bestchange_codes]
            assert filled_pm

            orders2 = await p2p.load_orders(token='USDT', fiat='RUB')
            assert orders2
            assert len(orders2.asks) > 0
            assert len(orders2.bids) > 0


@pytest.mark.asyncio
class TestBestChange:

    @pytest.fixture()
    def engine(self) -> BestChangeRatios:
        return BestChangeRatios()

    async def test_load_from_server(self, engine: BestChangeRatios):
        data = await engine.load_from_server()
        assert data
        assert isinstance(data, tuple)
        assert len(data) == 4

    async def test_load_orders(self, engine: BestChangeRatios):
        await engine.invalidate_cache()
        for n in range(2):
            orders = await engine.load_orders(token='USDT', fiat='RUB')
            assert orders
            assert orders.asks and orders.bids
            assert orders.asks[0].model_dump(exclude={'id'}) != orders.bids[0].model_dump(exclude={'id'})  # noqa
            self._check_orders_price(orders)
            orders2 = await engine.load_orders(get='USDT', give='RUB')
            assert orders2 == orders
            orders3 = await engine.load_orders(get='RUB', give='USDT')
            assert orders3.asks and orders3.bids

    @classmethod
    def _check_orders_price(cls, orders: P2POrders, limit=100):
        prev_ = orders.asks[0]
        for next_ in orders.asks[1:limit]:
            assert next_.price >= prev_.price
        prev_ = orders.bids[0]
        for next_ in orders.bids[1:limit]:
            assert next_.price <= prev_.price