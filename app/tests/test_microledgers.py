import pytest

from entities import ExchangeConfig

from context import Context
from entities import Currency, CashMethod
from merchants.entities import (
    load_directions, Direction, Payment
)
from merchants import MerchantRatios, update_merchants_config
from microledger import (
    MassPaymentMicroLedger, DatabasePaymentConsensus
)
from entities import (
    ExchangeConfig, Account, MerchantMeta, Identity, DIDSettings,
    mass_payment
)
from context import Context


@pytest.mark.asyncio
@pytest.mark.django_db
class TestMassPaymentMicroledgers:

    @pytest.fixture
    def merchant(self) -> Account:
        return Account(
            uid='test',
            merchant_meta=MerchantMeta(
                base_currency='RUB',
                url='https://test.com',
                identity=Identity(
                    did=DIDSettings(
                        root='did:web:ruswift.ru:test'
                    )
                )
            ).model_dump(mode='json')
        )

    @pytest.fixture
    def me(self, merchant: Account) -> Identity:
        meta = MerchantMeta.model_validate(merchant.merchant_meta)
        return meta.identity

    @pytest.fixture
    def msg1(self, merchant: Account) -> MassPaymentMicroLedger.Message:
        return MassPaymentMicroLedger.Message(
            transaction=mass_payment.PaymentTransaction(
                order_id='123',
                description='Desc-1',
                amount=20000,
                currency='RUB'
            ),
            customer=mass_payment.PaymentCustomer(
                identifier='user@example.com',
                display_name='Example User',
                email='user@example.com'
            ),
            card=mass_payment.PaymentCard(
                number='2200111144445555',
                expiration_date='11/30'
            )
        )

    @pytest.fixture
    def msg2(self, merchant: Account) -> MassPaymentMicroLedger.Message:
        return MassPaymentMicroLedger.Message(
            transaction=mass_payment.PaymentTransaction(
                order_id='321',
                description='Desc-2',
                amount=200000,
                currency='RUB'
            ),
            customer=mass_payment.PaymentCustomer(
                identifier='demo@example.com',
                display_name='Example Demo',
                email='demo@example.com',
                phone='81112233'
            ),
            card=mass_payment.PaymentCard(
                number='2200111144447777',
                expiration_date='10/30'
            ),
            status=mass_payment.PaymentStatus(
                status='error'
            )
        )

    @pytest.fixture
    def msg2(self, merchant: Account) -> MassPaymentMicroLedger.Message:
        return MassPaymentMicroLedger.Message(
            transaction=mass_payment.PaymentTransaction(
                order_id='321',
                description='Desc-2',
                amount=200000,
                currency='RUB'
            ),
            customer=mass_payment.PaymentCustomer(
                identifier='demo@example.com',
                display_name='Example Demo',
                email='demo@example.com',
                phone='81112233'
            ),
            card=mass_payment.PaymentCard(
                number='2200111144447777',
                expiration_date='10/30'
            ),
            status=mass_payment.PaymentStatus(
                status='error'
            )
        )

    @pytest.fixture
    def status2(self, merchant: Account) -> MassPaymentMicroLedger.Message:
        return MassPaymentMicroLedger.Message(
            type='status',
            transaction=mass_payment.PaymentTransaction(
                order_id='321'
            ),
            status=mass_payment.PaymentStatus(
                status='success'
            )
        )

    async def test_sane(
        self, exchange_config: ExchangeConfig,
        merchant: Account, me: Identity,
        msg1: MassPaymentMicroLedger.Message,
        msg2: MassPaymentMicroLedger.Message
    ):
        with Context.create_context(config=exchange_config, user=merchant):
            ledger = MassPaymentMicroLedger(
                participants=[
                    me.did.root, 'did:web:ruswift.ru'
                ],
                consensus_cls=DatabasePaymentConsensus
            )
            await ledger.send_batch(msgs=[msg1, msg2])

            count, items = await ledger.load()
            assert count == 2
            # check order
            assert items[0].transaction.order_id == msg2.transaction.order_id
            assert items[1].transaction.order_id == msg1.transaction.order_id

            # filter by order-id
            count, items = await ledger.load(
                order_id=msg1.transaction.order_id
            )
            assert count == 1
            assert items[0].transaction.order_id == msg1.transaction.order_id

            # filter by status
            count, items = await ledger.load(
                status='error'
            )
            assert count == 1
            assert items[0].transaction.order_id == msg2.transaction.order_id
            count, items = await ledger.load(
                status=['error', 'pending']
            )
            assert count == 2

            # filter by identifier
            count, items = await ledger.load(
                identifier='demo@example.com'
            )
            assert count == 1
            assert items[0].transaction.order_id == msg2.transaction.order_id

    async def test_statuses(
        self, exchange_config: ExchangeConfig,
        merchant: Account, me: Identity,
        msg2: MassPaymentMicroLedger.Message,
        status2: MassPaymentMicroLedger.Message
    ):
        with Context.create_context(config=exchange_config, user=merchant):
            ledger = MassPaymentMicroLedger(
                participants=[
                    me.did.root, 'did:web:ruswift.ru'
                ],
                consensus_cls=DatabasePaymentConsensus
            )
            await ledger.send_batch(msgs=[msg2])
            status2.status.status = 'pending'
            await ledger.send_batch(msgs=[status2])
            status2.status.status = 'success'
            await ledger.send_batch(msgs=[status2])

            count, items = await ledger.load()
            assert count == 3
            count, statuses = await ledger.load(type_='status')
            assert count == 2
            assert statuses[0].status.status == 'success'
            assert statuses[1].status.status == 'pending'

            count, payments = await ledger.load_payments()
            assert count == 1
            assert payments[0].status.status == 'success'
