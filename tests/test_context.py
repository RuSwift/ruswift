import pytest

from context import context, Context
from entities import ExchangeConfig, Account


@pytest.mark.asyncio
@pytest.mark.django_db
class TestContext:

    @pytest.fixture
    def config(self) -> ExchangeConfig:
        return ExchangeConfig(
            costs={},
            methods={},
            currencies=[],
            payments=[],
            directions=[]
        )

    @pytest.fixture
    def account(self) -> Account:
        return Account(
            uid='test',
            icon='https://x.com/icon.png',
            first_name='John',
            last_name='Don'
        )

    async def test_sane(self, config: ExchangeConfig, account: Account):
        with Context.create_context(config, account):
            ctx_config = context.config
            ctx_user = context.user
            assert ctx_config == config
            assert ctx_user == account
