import base64
from typing import Union, Dict, List, Optional, Tuple

from django.db import transaction
from channels.db import database_sync_to_async

from core.utils import utc_now_float, float_to_datetime
from exchange.models import (
    Currency as DBCurrency, Network as DBNetwork,
    Account as DBAccount, PaymentMethod as DBPaymentMethod,
    Correction as DBCorrection, Direction as DBDirection,
    Payment as DBPayment, KYC as DBKYC,
    OrganizationDocument as DBOrganizationDocument,
    CashMethod as DBCashMethod, Credential as DBCredential,
    Session as DBSession, StorageItem as DBStorageItem
)
from entities import (
    Currency, Network, Account, PaymentMethod, Correction, Payment,
    Direction, Costs, AccountKYC, VerifiedDocument, DocumentPhoto, SelfiePhoto,
    OrganizationDocument, CashMethod, Credential, Session, MerchantAccount,
    MerchantMeta, Ledger, Identity, AnonymousAccount
)

from .base import (
    BaseEntityRepository, EntityRetrieveMixin, EntityUpdateMixin,
    EntityCreateMixin, EntityDeleteMixin
)


class CurrencyRepository(
    EntityCreateMixin, EntityRetrieveMixin,
    EntityUpdateMixin, BaseEntityRepository
):
    Model = DBCurrency
    Entity = Currency

    @classmethod
    async def delete(cls, **filters) -> int:

        def __atomic_delete(**kw):
            with transaction.atomic():
                return cls.sync_delete(**kw)

        return await database_sync_to_async(__atomic_delete)(**filters)

    @classmethod
    def sync_delete(cls, **filters) -> int:
        queryset = DBCurrency.objects.filter(**filters)
        if queryset.exists():
            symbols = [cur.symbol for cur in queryset.all()]
            symbols = list(set(symbols))
            count, *extra = queryset.delete()
            if symbols:
                PaymentRepository.sync_delete(cur__in=symbols)
            return count
        else:
            return 0


class BasePaymentMethodMixin:

    @classmethod
    async def delete(cls, **filters) -> int:

        def __atomic_delete():
            with transaction.atomic():
                return cls.sync_delete(**filters)

        return await database_sync_to_async(__atomic_delete)(**filters)

    @classmethod
    def sync_delete(cls, **filters) -> int:
        queryset = cls.Model.objects.filter(**filters)
        if queryset.exists():
            ids = [getattr(meth, 'uid') for meth in queryset.all()]
            ids = [i for i in set(ids) if i]
            count, *extra = queryset.delete()
            if ids:
                PaymentRepository.sync_delete(method__in=ids)
            return count
        else:
            return 0


class NetworkRepository(
    EntityCreateMixin, EntityRetrieveMixin, EntityUpdateMixin,
    BasePaymentMethodMixin, BaseEntityRepository
):
    Model = DBNetwork
    Entity = Network


class PaymentMethodRepository(
    EntityCreateMixin, EntityRetrieveMixin, EntityUpdateMixin,
    BasePaymentMethodMixin, BaseEntityRepository
):
    Model = DBPaymentMethod
    Entity = PaymentMethod


class CashMethodRepository(
    EntityCreateMixin, EntityRetrieveMixin, EntityUpdateMixin,
    BasePaymentMethodMixin, BaseEntityRepository
):
    Model = DBCashMethod
    Entity = CashMethod


class AccountRepository(
    EntityCreateMixin, EntityRetrieveMixin, EntityUpdateMixin,
    EntityDeleteMixin, BaseEntityRepository
):
    Model = DBAccount
    Entity = Account

    _cache_merchants_ttl = 5*60
    _cache_merchants_key = 'merchants'
    _cache_anonymous_ttl = 60*60

    @classmethod
    async def get(cls, **filters) -> Optional[BaseEntityRepository.Entity]:
        acc = await super().get(**filters)
        if acc:
            return acc
        else:
            uid = filters.get('uid')
            if uid:
                anon = await cls.load_anonymous_account(uid)
                return anon
            else:
                return None

    @classmethod
    async def update_kyc(
        cls, kyc: AccountKYC, account: Union[str, Account]
    ) -> AccountKYC:
        if isinstance(account, AnonymousAccount):
            account.kyc = kyc
            await cls.save_anonymous_account(account)
            return kyc
        if isinstance(account, Account):
            account_uid = account.uid
        else:
            account_uid = account

        rec_account = await DBAccount.objects.aget(uid=account_uid)
        await DBKYC.objects.aupdate_or_create(
            defaults={
                'document_id': kyc.document_id,
                'provider': kyc.provider,
                'image_b64_document': kyc.photos.document.image if kyc.photos.document else None,
                'image_b64_selfie': kyc.photos.selfie.image if kyc.photos.selfie else None,
                'verified_data': kyc.verify.model_dump(mode='json'),
                'inn': kyc.inn,
                'source': kyc.source
            },
            account=rec_account
        )
        await DBAccount.objects.filter(uid=account_uid).aupdate(
            is_verified=True
        )
        kyc = await cls.load_kyc(account)
        return kyc

    @classmethod
    async def load_kyc(
        cls, account: Union[str, Account]
    ) -> Optional[AccountKYC]:
        if isinstance(account, AnonymousAccount):
            anon = await cls.load_anonymous_account(account.uid)
            raw = anon.kyc
            try:
                if raw:
                    obj = AccountKYC.model_validate(raw)
                    return obj
            except ValueError:
                return None

        if isinstance(account, Account):
            account = account.uid
        rec: DBKYC = await DBKYC.objects.filter(account__uid=account).afirst()
        if rec:
            kyc = AccountKYC(
                document_id=rec.document_id,
                provider=rec.provider,
                verify=VerifiedDocument.model_validate(rec.verified_data),
                inn=rec.inn,
                source=rec.source,
                created_at=rec.created_at,
                updated_at=rec.updated_at
            )
            if rec.image_b64_document:
                kyc.photos.document = DocumentPhoto()
                kyc.photos.document.from_image(
                    base64.b64decode(bytes(rec.image_b64_document))
                )
            if rec.image_b64_selfie:
                kyc.photos.selfie = SelfiePhoto()
                kyc.photos.selfie.from_image(
                    base64.b64decode(bytes(rec.image_b64_selfie))
                )
            return kyc
        else:
            return None

    @classmethod
    async def create_document(
        cls, account: Union[str, Account], doc: OrganizationDocument
    ) -> OrganizationDocument:
        if isinstance(account, str):
            uid = account
        else:
            uid = account.uid
        account = await DBAccount.objects.filter(uid=uid).afirst()
        if account is None:
            raise ValueError(f'Unknown account uid[{uid}]')
        rec = await DBOrganizationDocument.objects.acreate(
            account=account,
            image_b64=doc.document.image,
            attrs=doc.attrs,
            type=doc.type
        )
        _, docs = await cls.get_documents(account.uid, id=rec.id)
        if docs:
            return docs[0]
        else:
            raise ValueError(f'Unknown error while store document to db')

    @classmethod
    async def remove_document(
        cls, account: Union[str, Account], id_: int
    ) -> Optional[OrganizationDocument]:
        if isinstance(account, Account):
            account = account.uid
        _, docs = await cls.get_documents(account, id=id_)
        if docs:
            await DBOrganizationDocument.objects.filter(
                account__uid=account, id=id_
            ).adelete()
            return docs[0]
        else:
            return None

    @classmethod
    async def update_document(
        cls, account: Union[str, Account], doc: OrganizationDocument, id_: int
    ) -> Optional[OrganizationDocument]:
        if isinstance(account, Account):
            account = account.uid
        filters = dict(account__uid=account, id=id_)
        if await DBOrganizationDocument.objects.filter(**filters).aexists():
            await DBOrganizationDocument.objects.filter(**filters).aupdate(
                image_b64=doc.document.image if doc.document else None,
                attrs=doc.attrs,
                type=doc.type
            )
            _, docs = await cls.get_documents(account, id=id_)
            return docs[0] if docs else None
        else:
            return None

    @classmethod
    async def get_documents(
        cls, account: Union[str, Account], **filters
    ) -> Tuple[int, List[OrganizationDocument]]:
        if isinstance(account, Account):
            account = account.uid
        q = DBOrganizationDocument.objects.filter(account__uid=account)
        count: int = await q.acount()
        if filters:
            q = q.filter(**filters)
        results = []
        async for m in q.all():
            m: DBOrganizationDocument
            if m.image_b64:
                document = DocumentPhoto()
                document.from_image(base64.b64decode(bytes(m.image_b64)))
            else:
                document = None
            results.append(
                OrganizationDocument(
                    id=m.id,
                    type=m.type,
                    attrs=m.attrs,
                    document=document
                )
            )
        return count, results

    @classmethod
    async def get_merchants(
        cls, ignore_cache: bool = False
    ) -> List[MerchantAccount]:
        if not ignore_cache:
            cached = await cls._cache.get(key=cls._cache_merchants_key)
            if cached:
                values = cached.get('values')
                if values:
                    metas = [
                        MerchantAccount.model_validate(d)
                        for d in values
                    ]
                    return metas
        q = DBAccount.objects.filter(merchant_meta__isnull=False)
        merchants = []
        async for a in q.all():
            a: DBAccount
            if Account.Permission.MERCHANT.value in a.permissions:
                meta = MerchantMeta.model_validate(a.merchant_meta)
                account_kwargs = cls._model_to_dict(a)
                merchants.append(MerchantAccount(meta=meta, **account_kwargs))
        await cls._cache.set(
            key=cls._cache_merchants_key,
            value={
                'values': [m.model_dump(mode='json') for m in merchants]
            },
            ttl=cls._cache_merchants_ttl
        )
        return merchants

    @classmethod
    async def create(cls, **kwargs) -> BaseEntityRepository.Entity:
        await cls._cache.delete(key=cls._cache_merchants_key)
        return await super().create(**kwargs)

    @classmethod
    async def update(
        cls, e: BaseEntityRepository.Entity, **filters
    ) -> Optional[BaseEntityRepository.Entity]:
        if isinstance(e, AnonymousAccount):
            return await cls.save_anonymous_account(e)
        else:
            await cls._cache.delete(key=cls._cache_merchants_key)
            return await super().update(e, **filters)

    @classmethod
    async def update_or_create(
        cls, e: BaseEntityRepository.Entity, **filters
    ) -> BaseEntityRepository.Entity:
        if isinstance(e, AnonymousAccount):
            return await cls.save_anonymous_account(e)
        else:
            await cls._cache.delete(key=cls._cache_merchants_key)
            return await super().update_or_create(e, **filters)

    @classmethod
    async def load_anonymous_account(cls, uid) -> Optional[AnonymousAccount]:
        cache = cls._cache.namespace('anonymous')
        obj = await cache.get(uid)
        if obj:
            return AnonymousAccount.model_validate(obj)
        else:
            return None

    @classmethod
    async def save_anonymous_account(
        cls, account: AnonymousAccount
    ) -> AnonymousAccount:
        cache = cls._cache.namespace('anonymous')
        obj = account.model_dump()
        await cache.set(account.uid, obj, ttl=cls._cache_anonymous_ttl)
        return account

    @classmethod
    async def delete_anonymous_account(cls, uid: str):
        cache = cls._cache.namespace('anonymous')
        await cache.delete(uid)

    @classmethod
    async def delete(cls, **filters) -> int:

        await cls._cache.delete(key=cls._cache_merchants_key)
        _, many = await cls.get_many(**filters)
        if many:
            for a in many:
                await AccountSessionRepository.delete(account_uid=a.uid)
        if 'uid' in filters:
            # попробуем почистить в списке анонимов
            cache = cls._cache.namespace('anonymous')
            await cache.delete(key=filters['uid'])

        def __atomic_delete():
            with transaction.atomic():
                return cls.sync_delete(**filters)

        return await database_sync_to_async(__atomic_delete)()

    @classmethod
    def sync_delete(cls, **filters) -> int:
        accounts = list(DBAccount.objects.filter(
            **cls._prepare_filters(**filters)
        ).all())
        if accounts:
            uids = [a.uid for a in accounts]
            for uid in uids:
                DBSession.objects.filter(account_uid=uid).delete()
                DBCredential.objects.filter(account_uid=uid).delete()
            DBAccount.objects.filter(uid__in=uids).delete()
            return len(uids)
        else:
            return 0

    @classmethod
    def _model_to_dict(cls, model: Model) -> Dict:
        d = super()._model_to_dict(model)
        extra = d.pop('extra') or {}
        d.update(extra)
        d['created_at'] = model.created_at
        d['updated_at'] = model.updated_at
        d['verified'] = model.verified or {}
        return d

    @classmethod
    def _entity_to_dict(cls, e: Union[Account, Dict]) -> Dict:
        d = super()._entity_to_dict(e)
        extra = {}
        kvs = [(k, v) for k, v in d.items()]
        for k, v in kvs:
            if k not in Account.model_fields.keys():
                extra[k] = v
                del d[k]
        d['extra'] = extra
        if d.get('merchant_meta'):
            d['merchant_meta']['url'] = str(d['merchant_meta']['url'])
        return d

    @classmethod
    def _prepare_filters(cls, **filters) -> dict:
        d = super()._prepare_filters(**filters)
        for k, v in filters.items():
            if k not in d:
                if k == 'did':
                    d['merchant_meta__identity__did__root'] = v
                else:
                    d[f'extra__{k}'] = v
        return d


class AccountCredentialRepository(
    EntityCreateMixin, EntityRetrieveMixin, EntityUpdateMixin,
    EntityDeleteMixin, BaseEntityRepository
):
    Model = DBCredential
    Entity = Credential

    @classmethod
    def _prepare_filters(cls, **filters) -> dict:
        d = super()._prepare_filters(**filters)
        for k, v in filters.items():
            if k not in d:
                if k.startswith('payload'):
                    cond = k.replace('.', '__')
                    d[cond] = v
        return d


class AccountSessionRepository(
    EntityCreateMixin, EntityRetrieveMixin, EntityUpdateMixin,
    EntityDeleteMixin, BaseEntityRepository
):
    Model = DBSession
    Entity = Session
    _cache_read_ttl = 60

    @classmethod
    async def get(cls, **filters) -> Optional[BaseEntityRepository.Entity]:
        uid = filters.get('uid')
        access_by_id = uid and len(filters) == 1
        if access_by_id:
            cached = await cls._cache.get(key=uid)
            if cached:
                try:
                    return Session.model_validate(cached)
                except ValueError:
                    await cls._cache.delete(key=uid)
        e: Session = await super().get(**filters)
        if e:
            await cls._update_timestamps(e, store_db=True)
            if access_by_id:
                await cls._cache.set(
                    key=uid,
                    value=e.model_dump(mode='json'),
                    ttl=cls._cache_read_ttl
                )
        return e

    @classmethod
    async def delete(cls, **filters) -> int:
        _, many = await cls.get_many(**filters)
        if many:
            await cls._cache.delete(key=[e.uid for e in many])
        return await super().delete(**filters)

    @classmethod
    async def update(
        cls, e: BaseEntityRepository.Entity, **filters
    ) -> Optional[BaseEntityRepository.Entity]:
        upd = await cls._update_timestamps(e, store_db=False)
        return await super().update(upd, **filters)

    @classmethod
    async def update_or_create(
        cls, e: BaseEntityRepository.Entity, **filters
    ) -> BaseEntityRepository.Entity:
        upd = await cls._update_timestamps(e, store_db=False)
        return await super().update_or_create(upd, **filters)

    @classmethod
    def _entity_to_dict(cls, e: Union[Session, Dict]) -> Dict:
        d = super()._entity_to_dict(e)
        last_access_utc = d.get('last_access_utc')
        if last_access_utc is None:
            d['last_access_utc'] = float_to_datetime(utc_now_float())
        return d

    @classmethod
    async def _update_timestamps(
        cls, e: Session, store_db: bool = False
    ) -> Session:
        upd = Session.model_validate(e.model_dump())
        upd.last_access_utc = float_to_datetime(utc_now_float())
        if store_db:
            await cls.update(e=upd, uid=e.uid)
        return upd


class CorrectionRepository(
    EntityCreateMixin, EntityRetrieveMixin,
    EntityUpdateMixin, BaseEntityRepository
):
    Model = DBCorrection
    Entity = Correction

    @classmethod
    async def delete(cls, **filters) -> int:

        def __atomic_delete():
            with transaction.atomic():
                return cls.sync_delete(**filters)

        return await database_sync_to_async(__atomic_delete)(**filters)

    @classmethod
    def sync_delete(cls, **filters) -> int:
        queryset = DBCorrection.objects.filter(**filters)
        if queryset.exists():
            ids = [getattr(corr, 'uid') for corr in queryset.all()]
            ids = [i for i in set(ids) if i]
            count, *extra = queryset.delete()
            if ids:
                PaymentRepository.sync_delete(costs_outcome__contains=ids)
                PaymentRepository.sync_delete(costs_income__contains=ids)
            return count
        else:
            return 0


class PaymentRepository(
    EntityCreateMixin, EntityRetrieveMixin,
    EntityUpdateMixin, BaseEntityRepository
):
    Model = DBPayment
    Entity = Payment

    @classmethod
    async def delete(cls, **filters) -> int:

        def __atomic_delete(**kwargs):
            with transaction.atomic():
                return cls.sync_delete(**kwargs)

        return await database_sync_to_async(__atomic_delete)(**filters)

    @classmethod
    def sync_delete(cls, **filters) -> int:
        queryset = DBPayment.objects.filter(**filters)
        if queryset.exists():
            codes = [p.code for p in queryset.all()]
            codes = list(set(codes))
            count, *extra = queryset.delete()
            if codes:
                DBDirection.objects.filter(src__in=codes).delete()
                DBDirection.objects.filter(dest__in=codes).delete()
            return count
        else:
            return 0

    @classmethod
    def _model_to_dict(cls, model: DBPayment) -> Dict:
        d = super()._model_to_dict(model)
        costs = Costs(
            income=d.pop('costs_income') or [],
            outcome=d.pop('costs_outcome') or []
        )
        d['costs'] = costs.model_dump()
        return d

    @classmethod
    def _entity_to_dict(cls, e: Union[Payment, Dict]) -> Dict:
        d = super()._entity_to_dict(e)
        costs = d.pop('costs', None) or {}
        d['costs_income'] = cls.__to_array(costs.get('income'))
        d['costs_outcome'] = cls.__to_array(costs.get('outcome'))
        return d

    @classmethod
    def __to_array(cls, value: Union[str, List]) -> Optional[List]:
        if value is None:
            return None
        elif isinstance(value, str):
            return [value]
        else:
            return value


class DirectionRepository(
    EntityCreateMixin, EntityRetrieveMixin, EntityUpdateMixin,
    EntityDeleteMixin, BaseEntityRepository
):
    Model = DBDirection
    Entity = Direction


class LedgerRepository(BaseEntityRepository):
    Model = DBStorageItem
    Entity = Ledger

    _category = 'identity-ledgers'

    @classmethod
    async def ensure_exists(
        cls, identity: Identity,
        ledgers: List[Ledger], remove_others: bool = False
    ):
        storage_id = identity.did.root

        def _sync():
            with transaction.atomic():
                for ledger in ledgers:
                    rec = DBStorageItem.objects.update_or_create(
                        defaults={
                            'payload': ledger.model_dump(mode='json')
                        },
                        storage_id=storage_id, category=cls._category,
                        uid=ledger.id
                    )
                if remove_others:
                    DBStorageItem.objects.filter(
                        storage_id=storage_id, category=cls._category,
                    ).exclude(
                        uid__in=[i.id for i in ledgers]
                    ).delete()

        await database_sync_to_async(_sync)()

    @classmethod
    async def load(
        cls, identity: Identity, tag: str = None,
        id_: Union[str, List[str]] = None
    ) -> List[Ledger]:
        filters = {}
        if tag:
            filters['payload__tags__contains'] = [tag]
        if id_:
            if isinstance(id_, str):
                filters['payload__id'] = id_
            elif isinstance(id_, list):
                filters['payload__id__in'] = id_
        q = DBStorageItem.objects.filter(
            category=cls._category, **filters
        )
        result = []
        did = identity.did.root
        exists_ids = set()
        async for m in q.all():
            m: DBStorageItem
            ledger = Ledger.model_validate(m.payload)
            if m.id == did or ledger.has_participant(did):
                if ledger.id not in exists_ids:
                    result.append(ledger)
                    exists_ids.add(ledger.id)
        return result
