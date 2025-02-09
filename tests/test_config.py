import pytest

from exchange.ratios import (
    ForexEngine, HTXEngine, CoinMarketCapEngine,
    GarantexEngine, GarantexP2P
)
from exchange.context import Context
from exchange.entities import ExchangeConfig, Account
from exchange.entities import BestChangeMethodMapping, BestChangeCodeRule


@pytest.mark.asyncio
class TestConfig:

    @pytest.fixture()
    def default_config(self) -> BestChangeMethodMapping:
        return BestChangeMethodMapping(
            codes={
                'SBERRUB': BestChangeCodeRule(
                    **{'or': ['Сбер', 'SBER']}
                ),
                'TCSBRUB': BestChangeCodeRule(
                    **{'and': ['Тинь', 'Tinkoff']}
                )
            },
            ignores=[
                BestChangeCodeRule(
                    **{'or': ['CNY', 'AliPay']}
                )
            ]
        )

    async def test_or(self, default_config: BestChangeMethodMapping):
        s1 = 'Сбербанк /Сбер Тинькофф/Tinkoff'
        codes1 = default_config.match_codes(s1)
        assert codes1 == ['SBERRUB', 'TCSBRUB']

        s2 = 'СБП;СБЕР;АЛЬФА'
        codes2 = default_config.match_codes(s2)
        assert codes2 == ['SBERRUB']

        s3 = 'НАЛИЧНЫЕ ПО МИРУ RUB CNY USD AED EUR KRW THB'
        codes3 = default_config.match_codes(s3)
        assert codes3 == []

    async def test_and(self, default_config: BestChangeMethodMapping):
        s1 = 'Тинькофф/Tinkoff'
        codes1 = default_config.match_codes(s1)
        assert codes1 == ['TCSBRUB']

        s2 = 'Тинькофф'
        codes2 = default_config.match_codes(s2)
        assert codes2 == []

    async def test_ignore(self, default_config: BestChangeMethodMapping):
        s1 = ' ПЕРЕВОДЫ В КИТАЙ 🇨🇳🥡 ЮАНЬ 🥟 ЛУЧШИЙ КУРС 🥡 CNY 🧧 Alipay Wechat Union pay Uni... Сбер'
        codes1 = default_config.match_codes(s1)
        assert codes1 == []
