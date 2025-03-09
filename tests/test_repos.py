import asyncio
import uuid
from typing import Optional, Tuple, List, Any

import pytest
from django.conf import settings
from django.db import IntegrityError

from cache import Cache
from core import utc_now_float
from exchange.models import (
    Currency as DBCurrency, KYCPhoto as DBKYCPhoto
)
from entities import (
    Currency, Account, DocumentPhoto, SelfiePhoto, Session,
    StorageItem, AccountKYC, VerifiedDocument
)
from reposiroty import (
    BaseEntityRepository, ExchangeConfigRepository,
    CorrectionRepository, PaymentRepository, KYCPhotoRepository,
    AccountRepository, AccountSessionRepository, AccountCredentialRepository,
    StorageRepository, CurrencyRepository
)


class TestEntityRepository(BaseEntityRepository):

    Model = DBCurrency
    Entity = Currency

    @classmethod
    async def get(cls, **filters) -> Optional[Entity]:
        return await cls._get_one(**filters)

    @classmethod
    async def get_many(
        cls, order_by: Any = None, limit: int = None,
        offset: Any = None, **filters
    ) -> Tuple[int, List[Entity]]:
        return await cls._get_many(
            order_by, limit, offset,
            **filters
        )

    @classmethod
    async def create(
        cls, symbol: str, icon: str, is_fiat: bool, is_enabled: bool = True
    ) -> Entity:
        return await cls._create_one(
            symbol=symbol, icon=icon, is_fiat=is_fiat, is_enabled=is_enabled
        )

    @classmethod
    async def update(cls, e: Entity, **filters) -> Entity:
        return await cls._update_one(e, **filters)

    @classmethod
    async def delete(cls, **filters) -> int:
        return await cls._delete_one(**filters)


@pytest.mark.asyncio
@pytest.mark.django_db
class TestRepos:

    async def test_sane(self):
        created = await TestEntityRepository.create(
            symbol='RUB', icon='https://server.com/icon.png',
            is_fiat=True
        )
        rec = await DBCurrency.objects.filter(symbol='RUB').afirst()
        assert rec

        assert created.symbol == 'RUB'
        assert created.is_fiat is True

        loaded = await TestEntityRepository.get(symbol='RUB')
        assert loaded

        await TestEntityRepository.create(
            symbol='USD', icon='https://server.com/icon.png',
            is_fiat=True
        )
        count, loads = await TestEntityRepository.get_many()
        assert count == 2
        assert len(loads) == 2

        new = Currency(**created.model_dump())
        new.is_fiat = False
        updated = await TestEntityRepository.update(new, symbol='RUB')
        assert updated.is_fiat is False

        del_num = await TestEntityRepository.delete(symbol='RUB')
        assert del_num == 1

    async def test_many_filters(self):
        await TestEntityRepository.delete()

        created1 = await TestEntityRepository.create(
            symbol='RUB', icon='https://server.com/icon.png',
            is_fiat=True
        )
        created2 = await TestEntityRepository.create(
            symbol='CNY', icon='https://server.com/icon.png',
            is_fiat=True
        )
        created3 = await TestEntityRepository.create(
            symbol='USD', icon='https://server.com/icon.png',
            is_fiat=True
        )

        # check limit
        count, loads = await TestEntityRepository.get_many(
            limit=2
        )
        assert count == 3
        assert len(loads) == 2
        # check offset
        count, loads = await TestEntityRepository.get_many(
            offset=2
        )
        assert count == 3
        assert len(loads) == 1
        # check order-by
        _, direct = await TestEntityRepository.get_many(
            order_by='symbol'
        )
        _, reverse = await TestEntityRepository.get_many(
            order_by='-symbol'
        )
        direct = [e.symbol for e in direct]
        reverse = [e.symbol for e in reverse]
        assert direct == list(reversed(reverse))
        # check filters
        count, loads = await TestEntityRepository.get_many(
            symbol='RUB'
        )
        assert count == 1
        assert loads[0].symbol == 'RUB'

    async def test_cache_intersection(self):
        cache = Cache(pool=settings.REDIS_CONN_POOL)
        await cache.flush()
        ks = await cache.keys()
        assert len(ks) == 0
        await CorrectionRepository._cache.set('key', 'value', 60)
        await PaymentRepository._cache.set('key', 'value', 60)
        keys = await cache.keys()
        assert len(keys) == 2
        await PaymentRepository._cache.delete('key')
        keys = await cache.keys()
        assert len(keys) == 1


@pytest.mark.asyncio
@pytest.mark.django_db
class TestConfigRepo:

    async def test_config(self):
        await ExchangeConfigRepository.invalidate_cache()
        cfg1 = await ExchangeConfigRepository.init_from_yaml(
            '/workspaces/ruswift/tests/files/init.example.yml', 'exchange'
        )
        cfg2 = await ExchangeConfigRepository.get()
        assert cfg1
        assert cfg2
        assert cfg1.refresh_timeout_sec == cfg2.refresh_timeout_sec
        assert cfg1.cache_timeout_sec == cfg2.cache_timeout_sec
        assert cfg1.merchants is not None
        assert cfg1.merchants == cfg2.merchants
        assert cfg1.paths and cfg1.paths == cfg2.paths
        assert cfg1.identity and cfg1.identity == cfg2.identity

        for n in range(3):
            await ExchangeConfigRepository.get()


@pytest.mark.asyncio
@pytest.mark.django_db
class TestKYCPhotoRepo:

    @pytest.fixture
    def pdf(self) -> str:
        return '/app/exchange/tests/files/kyc/beorg/success_passport.pdf'

    @pytest.fixture
    def jpg(self) -> str:
        return '/app/exchange/tests/files/kyc/beorg/selfie_with_passport.jpg'

    @pytest.fixture
    def kyc_id(self) -> str:
        return uuid.uuid4().hex

    async def test_sane(self, pdf: str, jpg: str, kyc_id: str):
        # Селфи и док можно держать под одним uid
        doc = DocumentPhoto()
        doc.from_file(pdf)
        assert doc.mime_type == 'application/pdf'

        e1 = await KYCPhotoRepository.create(uid=kyc_id, **doc.model_dump())
        rec1 = await DBKYCPhoto.objects.filter(
            uid=kyc_id, type=doc.type
        ).afirst()

        assert e1.image == bytes(rec1.image) == doc.image
        assert e1.mime_type == rec1.mime_type == doc.mime_type

        selfie = SelfiePhoto()
        selfie.from_file(jpg)
        assert selfie.mime_type == 'image/jpeg'

        e2 = await KYCPhotoRepository.create(uid=kyc_id, **selfie.model_dump())
        rec2 = await DBKYCPhoto.objects.filter(
            uid=kyc_id, type=selfie.type
        ).afirst()

        assert e2.image == bytes(rec2.image) == selfie.image
        assert e2.mime_type == rec2.mime_type == selfie.mime_type

        await KYCPhotoRepository.delete(uid=kyc_id)
        cnt = await DBKYCPhoto.objects.acount()
        assert cnt == 0

    async def test_update(self, pdf: str, jpg: str, kyc_id: str):
        doc = DocumentPhoto()
        doc.from_file(pdf)
        assert doc.mime_type == 'application/pdf'

        e1 = await KYCPhotoRepository.create(uid=kyc_id, **doc.model_dump())
        e2 = await KYCPhotoRepository.update_or_create(doc, uid=kyc_id)
        assert e1 == e2

        doc.from_file(jpg)
        e3 = await KYCPhotoRepository.update(doc, uid=kyc_id)
        assert e3.uid == e1.uid == e2.uid
        assert e3.image != e1.image

    async def test_remove_expired(self, pdf: str):
        doc1 = DocumentPhoto(
            remove_after=utc_now_float()-1000
        )
        doc1.from_file(pdf)
        doc2 = DocumentPhoto(
            remove_after=None
        )
        doc2.from_file(pdf)

        for doc in [doc1, doc2]:
            await KYCPhotoRepository.create(**doc.model_dump())
        cnt1, _ = await KYCPhotoRepository.get_many()
        assert cnt1 > 0
        await KYCPhotoRepository.remove_expired_files()

        cnt2, _ = await KYCPhotoRepository.get_many()
        assert cnt1 - cnt2 == 1


@pytest.mark.asyncio
@pytest.mark.django_db
class TestAccountRepo:

    async def test_sane(self):
        e1: Account = await AccountRepository.update_or_create(
            e=Account(
                uid=uuid.uuid4().hex
            ),
            telegram='@unknown'
        )
        assert e1.telegram == '@unknown'

        e2 = await AccountRepository.get(telegram='@unknown')
        assert e2.uid == e1.uid
        assert e2.is_verified is False

        await AccountRepository.delete(telegram='@unknown')
        e3 = await AccountRepository.get(telegram='@unknown')
        assert e3 is None

    async def test_extra_fields(self):
        await AccountRepository.update_or_create(
            e=Account(
                uid=uuid.uuid4().hex
            )
        )
        e1 = await AccountRepository.update_or_create(
            e=Account(
                uid=uuid.uuid4().hex
            ),
            some_extra_field='some-value'
        )
        assert e1.some_extra_field == 'some-value'

        e2 = await AccountRepository.get(some_extra_field='some-value')
        assert e2
        assert e2.uid == e1.uid

        await AccountRepository.delete(some_extra_field='some-value')
        e3 = await AccountRepository.get(some_extra_field='some-value')
        assert not e3

    async def test_kyc_methods(self):
        account = await AccountRepository.create(uid=uuid.uuid4().hex)
        print('')
        kyc = AccountKYC(
            document_id='xxx',
            provider='fake',
            verify=VerifiedDocument(
                id='xxx',
                kyc_provider='fake',
                issued_by='issuedBy',
                issued_date='issuedDate',
                issued_id='divisionCode',
                series="series",
                number="number",
                gender='M',
                last_name='surname',
                first_name='firstName',
                middle_name='middleName',
                birth_date='birthdate',
                birth_place='birthplace',
            ),
            inn='INN',
            source='ESIA'
        )
        await AccountRepository.update_kyc(
            kyc=kyc,
            account=account
        )
        loaded = await AccountRepository.load_kyc(account)
        assert loaded.model_dump(
            exclude={'created_at', 'updated_at'}
        ) == kyc.model_dump(
            exclude={'created_at', 'updated_at'}
        )


@pytest.mark.asyncio
@pytest.mark.django_db
class TestAccountSessionRepo:

    @pytest.fixture
    def account(self) -> Account:
        return Account(
            uid='test'
        )

    async def test_sane(self, account: Account):
        await AccountRepository.update_or_create(
            e=account, uid=account.uid
        )
        session: Session = await AccountSessionRepository.create(
            uid='session-id',
            class_name='auth',
            account_uid=account.uid
        )
        assert session.last_access_utc is not None

        await asyncio.sleep(0.5)

        upd: Session = await AccountSessionRepository.update_or_create(
            e=session, uid=session.uid
        )
        assert upd.last_access_utc.time() > session.last_access_utc.time()

        await AccountRepository.delete(uid=account.uid)
        session = await AccountSessionRepository.get(uid=session.uid)
        assert session is None

    async def test_caching(self, account: Account):
        await AccountRepository.update_or_create(
            e=account, uid=account.uid
        )
        session1: Session = await AccountSessionRepository.create(
            uid='session-id' + uuid.uuid4().hex,
            class_name='auth',
            account_uid=account.uid
        )
        for n in range(5):
            s: Session = await AccountSessionRepository.get(uid=session1.uid)
            assert s
            assert s.last_access_utc.time() == session1.last_access_utc.time()

        await AccountSessionRepository.delete(uid=session1.uid)
        session = await AccountSessionRepository.get(uid=session1.uid)
        assert session is None

        session2: Session = await AccountSessionRepository.create(
            uid='session-id' + uuid.uuid4().hex,
            class_name='auth',
            account_uid=account.uid
        )
        await AccountSessionRepository.delete(account_uid=account.uid)
        session = await AccountSessionRepository.get(uid=session2.uid)
        assert session is None


@pytest.mark.asyncio
@pytest.mark.django_db
class TestAccountCredRepo:

    @pytest.fixture
    def account(self) -> Account:
        return Account(
            uid='test'
        )

    async def test_sane(self, account: Account):
        await AccountRepository.update_or_create(
            e=account, uid=account.uid
        )

        cred1 = await AccountCredentialRepository.create(
            class_name='auth1',
            account_uid=account.uid,
            schema={},
            payload={'attr': 'val1', 'attr2': 'value'}
        )
        cred2 = await AccountCredentialRepository.create(
            class_name='auth2',
            account_uid=account.uid,
            schema={},
            payload={'attr': 'val2', 'attr2': 'value'}
        )

        count1, many1 = await AccountCredentialRepository.get_many(
            **{'payload.attr': 'val1'}
        )
        assert count1 == 1
        assert many1[0].class_name == 'auth1'

        count2, _ = await AccountCredentialRepository.get_many(
            payload__attr2='value'
        )
        assert count2 == 2


@pytest.mark.asyncio
@pytest.mark.django_db
class TestStorageRepo:

    async def test_sane(self):
        create = StorageItem(
            storage_id='babapay',
            category='check',
            payload={
                'method': 'AliPay',
                'fields': [
                    {'attr': 'id', 'label': 'AliPay ID'},
                    {'attr': 'full_name', 'label': 'Full Name'},
                ]
            }
        )
        created: StorageItem = await StorageRepository.create(**dict(create))
        assert created.uid
        assert created.updated_at
        assert created.created_at
        assert created.storage_ids == []

        await asyncio.sleep(0.5)

        upd = StorageItem.model_validate(created)
        upd.payload = {'method': 'Sber'}

        updated: StorageItem = await StorageRepository.update(
            e=upd, uid=created.uid
        )
        assert updated.payload == upd.payload
        assert updated.updated_at.time() > updated.created_at.time()
        assert updated.created_at.time() == created.created_at.time()

    async def test_tags(self):
        create1 = StorageItem(
            storage_id='babapay',
            category='check',
            tags=['tag1', 'tag2', 'tag3'],
            payload={}
        )
        create2 = StorageItem(
            storage_id='babapay',
            category='check',
            tags=['tag1', 'tag4', 'tag5'],
            payload={}
        )

        await StorageRepository.create_many([create1, create2])

        count, search = await StorageRepository.get_many(tag=['tag1', 'tag2'])
        assert count == 1

        count, search = await StorageRepository.get_many(tag='tag1')
        assert count == 2

        count, search = await StorageRepository.get_many(tag='tag')
        assert count == 0

    async def test_filter_by_storage_id(self):
        create1 = StorageItem(
            storage_id=None,
            category='check1',
            payload={}
        )
        create2 = StorageItem(
            storage_id='babapay2',
            category='check2',
            payload={}
        )

        await StorageRepository.create_many([create1, create2])

        count, search = await StorageRepository.get_many(storage_id='babapay2')
        assert count == 1
        assert search[0].category == 'check2'

        count, search = await StorageRepository.get_many(storage_id=None)
        assert count == 1
        assert search[0].category == 'check1'

    async def test_storage_ids(self):
        category = uuid.uuid4().hex
        create = StorageItem(
            storage_id='did:ruswift:merchant:babapay',
            category=category,
            payload={},
            storage_ids=['did:ruswift:merchant:babapay', 'did:ruswift:exchange']
        )

        await StorageRepository.create_many([create])
        loaded = await StorageRepository.get(category=category)
        assert loaded.storage_ids == ['did:ruswift:merchant:babapay', 'did:ruswift:exchange']  # noqa


@pytest.mark.asyncio
@pytest.mark.django_db
class TestIntegrity:

    async def test_payment_cur__foreign(self):
        cur1 = await CurrencyRepository.create(
            symbol='RUB',
            is_fiat=True,
            owner_did='did:owner1'
        )
        cur2 = await CurrencyRepository.create(
            symbol='RUB',
            is_fiat=True,
            owner_did=None
        )

        payment = await PaymentRepository.create(
            code='test',
            cur='RUB',
            method='sber',
            owner_did='did:owner1'
        )

        with pytest.raises(IntegrityError):
            await CurrencyRepository.delete(id=cur1.id)

        await CurrencyRepository.delete(id=cur2.id)

        await PaymentRepository.delete(id=payment.id)
        await CurrencyRepository.delete(id=cur1.id)
