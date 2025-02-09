import pytest

from entities import ExchangeConfig

from context import Context
from entities import Currency, CashMethod
from merchants.entities import (
    load_directions, Direction, Payment
)
from merchants import MerchantRatios, update_merchants_config


@pytest.mark.asyncio
class TestMerchantEntities:

    @pytest.fixture
    def engine(self) -> MerchantRatios:
        return MerchantRatios(
            uid='babapay', settings=MerchantRatios.Settings()
        )

    async def test_load(self, exchange_config: ExchangeConfig):
        merchant_dirs = load_directions(exchange_config)
        assert merchant_dirs

    async def test_engines(
        self, engine: MerchantRatios, exchange_config: ExchangeConfig
    ):
        await engine.invalidate_cache()
        with Context.create_context(exchange_config):
            ratios1 = await engine.engine_ratios(
                load_directions(exchange_config)
            )
            assert ratios1
            # cached
            ratios2 = await engine.engine_ratios(
                load_directions(exchange_config)
            )
            assert ratios2

    async def test_ratios(
        self, engine: MerchantRatios, exchange_config: ExchangeConfig
    ):
        await engine.invalidate_cache()
        with Context.create_context(exchange_config):
            directions = load_directions(exchange_config)
            await engine.build_ratios(
                load_directions(exchange_config)
            )
            # Token-To-Token
            token_to_token_dir = [
                d for d in directions
                if d.src.cur.is_fiat is False and d.dest.cur.is_fiat is False
            ][0]
            ratio = await engine.ratio(token_to_token_dir)
            assert ratio
            # Fiat-To-Fiat
            fiat_to_fiat_dir = Direction(
                src=Payment(
                    code='CASHRUB',
                    cur=Currency(
                        symbol='RUB',
                        is_fiat=True
                    ),
                    method=CashMethod(
                        sub='cash',
                        name='cash'
                    )
                ),
                dest=Payment(
                    code='CASHUSD',
                    cur=Currency(
                        symbol='USD',
                        is_fiat=True
                    ),
                    method=CashMethod(
                        sub='cash',
                        name='cash'
                    )
                )
            )
            print('')
            ratio = await engine.ratio(fiat_to_fiat_dir)
            assert ratio
            # Fiat-To-Token
            fiat_to_token_dir = [
                d for d in directions
                if d.src.cur.is_fiat is True and d.dest.cur.is_fiat is False
            ][0]
            ratio = await engine.ratio(fiat_to_token_dir)
            assert ratio

    async def test_detail(
        self, engine: MerchantRatios, exchange_config: ExchangeConfig
    ):
        with Context.create_context(exchange_config):
            directions = load_directions(exchange_config)
            # Token-To-Token
            direction = [
                d for d in directions
                if d.src.code == 'SBERRUB' and d.dest.code == 'USDTTRC20'
            ][0]
            ratio = await engine.ratio(direction)
            assert ratio


@pytest.mark.asyncio
@pytest.mark.django_db
class TestMerchantUtils:

    async def test_update_merchant_configs(
        self, exchange_config: ExchangeConfig
    ):
        await update_merchants_config(exchange_config)
        # check update side-effects
        await update_merchants_config(exchange_config)
