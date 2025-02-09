import pytest

from exchange.reports import QugoRegistry
from exchange.microledger import MassPaymentMicroLedger


@pytest.mark.asyncio
@pytest.mark.django_db
class TestReports:

    async def test_qugo(self):
        raw = [
               {
                   'uid': 'uid-1',
                   'transaction': {'order_id': '1', 'description': 'Test description','amount': 10000.0, 'currency': 'RUB'},
                   'customer': {'identifier': 'ivan@sidorov.ru','display_name': 'Ivan Sidorov','email': 'ivan@sidorov.ru', },
                   'card': {'number': '22001112200005555','expiration_date': '10/30'},
               },
               {
                   'uid': 'uid-2',
                   'transaction': {'order_id': '2','description': 'Test description','amount': 20000.0, 'currency': 'RUB'},
                   'customer': {'identifier': 'ivan@sidorov.ru','display_name': 'Ivan Sidorov','email': 'ivan@sidorov.ru', },
                   'card': {'number': '22001112200005555','expiration_date': '10/30'},
               }
        ]
        payments = []
        for src in raw:
            msg = MassPaymentMicroLedger.Message(**src)
            payments.append(msg)
        reporter = QugoRegistry(payments=payments)

        buffer = await reporter.export_to_buffer()
        assert buffer
