import asyncio
import base64
import hashlib
import logging
import uuid
import urllib.parse
from typing import Any, List, Optional, Type, Union

from django.conf import settings
from django.http import HttpResponse, HttpResponseBadRequest
from pydantic import Field

from api.lib import BaseResource, action
from api.lib.mixins import MixinCreateOne, MixinDeleteOne

from exchange.core import utc_now_float, load_class
from exchange.entities import (
    VerifiedDocument, AccountFields, Account, StorageItem,
    DocumentPhoto, SelfiePhoto, AccountKYC, AccountKYCPhotos
)
from exchange.api import BaseExchangeController
from exchange.reposiroty import (
    KYCPhotoRepository, AccountRepository, StorageRepository
)
from exchange.context import context as app_context
from exchange.kyc import BaseKYCProvider, MTSKYCProvider


class KYCDocument(BaseResource):

    pk = 'id'

    class Common(BaseResource.Create):
        account_fields: Optional[AccountFields] = Field(
            default_factory=AccountFields
        )

    class Create(Common):
        id: str
        document: Optional[str] = None
        selfie: Optional[str] = None
        success: Optional[bool] = True

    class Update(Create):
        ...

    class Retrieve(Common):
        id: str
        document_is_set: bool
        selfie_is_set: bool
        verification: VerifiedDocument = None


class KYCRegistration(BaseResource):

    pk = 'id'

    class Create(AccountFields):
        ...

    class Update(Create):
        ...

    class Retrieve(Account):
        ...


class KYCController(
    MixinCreateOne, MixinDeleteOne, BaseExchangeController
):

    Resource = KYCDocument
    PERMISSIONS = {'*': [Account.Permission.KYC.value]}

    def __init__(
        self, context: BaseExchangeController.Context, *args, **kwargs
    ):
        super().__init__(context, *args, **kwargs)
        self.provider_class: Type[BaseKYCProvider] = load_class(settings.KYC['PROV_CLASS'])  # noqa

    async def get_one(
        self, pk: str, **filters
    ) -> Optional[Resource.Retrieve]:
        verification_uid = pk
        raw = await self.cache.get(verification_uid)
        if raw:
            return KYCDocument.Retrieve(**raw)
        else:
            return None

    async def create_one(
        self, data: Resource.Create, **extra
    ) -> Optional[Resource.Retrieve]:
        verification_uid = data.id
        remove_after = utc_now_float() + app_context.config.kyc_photos_expiration_sec  # noqa
        if data.document:
            doc = DocumentPhoto(remove_after=remove_after)
            doc.from_image(base64.b64decode(data.document))
            await KYCPhotoRepository.update_or_create(
                doc, uid=verification_uid, type=doc.type
            )
        if data.selfie:
            selfie = SelfiePhoto(remove_after=remove_after)
            selfie.from_image(base64.b64decode(data.selfie))
            await KYCPhotoRepository.update_or_create(
                selfie, uid=verification_uid, type=selfie.type
            )
        # process
        _, photos = await KYCPhotoRepository.get_many(uid=verification_uid)
        photos = {p.type: p for p in photos}
        doc = photos.get('document')
        selfie = photos.get('selfie')
        try:
            for photo in photos.values():
                await KYCPhotoRepository.update(
                    photo,
                    uid=verification_uid,
                    type=photo.type,
                    remove_after=remove_after
                )
            resp = KYCDocument.Retrieve(
                id=verification_uid,
                document_is_set=doc is not None,
                selfie_is_set=selfie is not None,
                account_fields=data.account_fields,
                verification=await self._verify(doc, selfie)
            )
            await self.cache.set(
                key=verification_uid,
                value=resp.model_dump(mode='json'),
                ttl=app_context.config.kyc_photos_expiration_sec
            )
        except Exception as e:
            logging.exception('ERROR')
            raise
        return await self.get_one(pk=verification_uid)

    async def delete_one(
        self, pk: Any, **extra
    ) -> Optional[BaseResource.Retrieve]:
        verification_uid = pk
        resp = await self.get_one(pk=verification_uid)
        await KYCPhotoRepository.delete(uid=verification_uid)
        await self.cache.delete(key=verification_uid)
        return resp

    async def get_many(
        self, order_by: Any = 'id', limit: int = None,
        offset: Any = None, **filters
    ) -> List[Resource.Retrieve]:
        if 'id' in filters:
            one = await self.get_one(**filters)
            return [one]
        else:
            return []

    @action(methods=['GET', 'POST', 'PUT'], detail=True, resource=KYCRegistration)  # noqa
    async def account(
        self, pk: str, data: AccountFields = None, **filters
    ) -> Optional[Account]:
        verification_uid = pk
        document = await self.get_one(pk, **filters)
        if document:
            account = Account(
                uid=f'{self.provider_class.provider_id}::{document.id}',
                **document.account_fields.model_dump()
            )
            if self.method.lower() == 'get':
                return account
            elif self.method.lower() == 'put':
                if data:
                    await self._update_account_fields(
                        verification_uid,
                        document, fields=data
                    )
                return Account(
                    uid=account.uid,
                    **document.account_fields.model_dump()
                )
            elif self.method.lower() == 'post':
                if data:
                    await self._update_account_fields(
                        verification_uid,
                        document, fields=data, refresh_expirations=False
                    )
                    account.is_verified = True
                    actual_acc: Account = await AccountRepository.update_or_create(
                        account, uid=account.uid
                    )
                    #
                    kyc_photos = AccountKYCPhotos()
                    _, photos = await KYCPhotoRepository.get_many(
                        uid=verification_uid
                    )
                    for p in photos:
                        if p.type == 'document':
                            kyc_photos.document = p
                        elif p.type == 'selfie':
                            kyc_photos.selfie = p
                    await AccountRepository.update_kyc(
                        kyc=AccountKYC(
                            document_id=document.id,
                            provider=self.provider_class.provider_id,
                            verify=document.verification,
                            photos=kyc_photos
                        ),
                        account=actual_acc
                    )
                    return actual_acc
                else:
                    return None
            else:
                raise RuntimeError('Unexpected method')
        else:
            return None

    async def _verify(
        self, doc: DocumentPhoto = None, selfie: SelfiePhoto = None
    ) -> VerifiedDocument:
        provider: BaseKYCProvider = self.provider_class()
        photos = [p for p in (doc, selfie) if p]
        data = await provider.verify(photos=photos)
        return data

    async def _update_account_fields(
        self, verification_uid: str, document: KYCDocument.Retrieve,
        fields: AccountFields, refresh_expirations: bool = True
    ):
        remove_after = utc_now_float() + app_context.config.kyc_photos_expiration_sec  # noqa
        try:
            if refresh_expirations:
                _, photos = await KYCPhotoRepository.get_many(
                    uid=verification_uid
                )
                photos = {p.type: p for p in photos}
                for photo in photos.values():
                    await KYCPhotoRepository.update(
                        photo,
                        uid=verification_uid,
                        type=photo.type,
                        remove_after=remove_after
                    )
            new_data = fields.model_dump(
                exclude={'uid', 'is_verified'}
            )
            data = document.account_fields.model_dump()
            data.update(new_data)
            document.account_fields = AccountFields(**data)
            if refresh_expirations:
                await self.cache.set(
                    key=verification_uid,
                    value=document.model_dump(mode='json'),
                    ttl=app_context.config.kyc_photos_expiration_sec
                )
        except Exception as e:
            logging.exception('ERROR')
            raise


class MTSKYCVerification(BaseResource):

    pk = 'id'

    class Create(BaseResource.Create):
        account_uid: Optional[str] = None
        link_ttl_minutes: int = 195  # Время жизни ссылки
        redirect_url: Optional[str] = None
        manual_input: bool = False
        esia: bool = True
        mobile_phone: Optional[str] = None
        verification: bool = True
        inn: bool = True
        bio: bool = True
        identification_url: Optional[str] = None
        request_id: Optional[str] = None
        external_id: Optional[str] = None
        final: Optional[bool] = False
        registration: Optional[bool] = False

    class Update(Create):
        ...

    class Retrieve(Update):
        id: str
        until: float = None
        status: Optional[dict] = None


class MTSKYCController(
    MixinCreateOne, BaseExchangeController
):

    Resource = MTSKYCVerification
    PERMISSIONS = {'*': [Account.Permission.ANY.value]}
    PROVIDER = MTSKYCProvider

    def __init__(
        self, context: BaseExchangeController.Context, *args, **kwargs
    ):
        super().__init__(context, *args, **kwargs)
        self.provider = self.PROVIDER()
        self.storage_category = f'kyc:{self.PROVIDER.provider_id}'

    async def get_one(self, pk: Any, **filters) -> Optional[Resource.Retrieve]:
        await self.clean_old_records()
        entity = await StorageRepository.get(
            **{
                'payload__id': pk,
                'storage_id': self.identity.did.root,
                'category': self.provider.provider_id
            }
        )
        if entity:
            return self.Resource.Retrieve(**entity.payload)
        else:
            return None

    async def get_many(
        self, order_by: Any = 'id', limit: int = None,
        offset: int = None, **filters
    ) -> List[Resource.Retrieve]:
        pld_filters = {}
        for k, v in filters.items():
            if k == 'final':
                pld_filters[f'payload__{k}'] = True if v == 'yes' else False
            else:
                pld_filters[f'payload__{k}'] = v

        await self.clean_old_records()
        count, entities = await StorageRepository.get_many(
            storage_id=self.identity.did.root,
            category=self.provider.provider_id,
            **pld_filters
        )
        self.metadata.total_count = count
        return [
            self.Resource.Retrieve(**e.payload)
            for e in entities
        ]

    async def create_one(
        self, data: Resource.Create,
        allow_empty_account: bool = False,
        **extra
    ) -> Resource.Retrieve:
        if not data.account_uid:
            if not allow_empty_account:
                return HttpResponseBadRequest('account_id is Empty!')
        account: Account = await AccountRepository.get(uid=data.account_uid)
        if not account:
            if not allow_empty_account:
                return HttpResponse(status=400, content=b'Unknown account uid')
            # create virtual account
            account = Account(uid=uuid.uuid4().hex)

        external_id = self.extract_internal_id(account.uid)
        try:
            applicant = self._build_applicant(account)
            actual_applicant = await self.provider.ensure_applicant_exists(
                external_id=external_id,
                data=applicant
            )
            link = await self.provider.create_identification_request(
                external_id=external_id,
                link_ttl_minutes=data.link_ttl_minutes,
                redirect_url=data.redirect_url,
                manual_input=data.manual_input,
                esia=data.esia,
                mobile_phone=data.mobile_phone,
                verification=data.verification,
                inn=data.inn,
                bio=data.bio
            )
            data.identification_url = link['identificationUrl']
            data.request_id = link['id']
            data.external_id = external_id
        except Exception as e:
            raise

        id_ = uuid.uuid4().hex
        si = self._build_storage_item(id_=id_, data=data)
        created = await StorageRepository.create_many(entities=[si])
        e = created[0]
        return self.Resource.Retrieve(**e.payload)

    @action(methods=['POST'], url_path='create_registration_link', detail=False)
    async def create_registration_link(
        self, data: Resource.Create, **extra
    ):
        try:
            resp = await self._create_registration_link(data, **extra)
        except ValueError as e:
            err_msg = e.args[0] if e.args else str(e)
            return HttpResponseBadRequest(
                content=err_msg.encode()
            )
        else:
            return resp

    @classmethod
    def extract_internal_id(cls, value: str) -> str:
        # return hashlib.md5(value.encode()).hexdigest()
        value = urllib.parse.quote(value).replace('&', '__').replace('%', '__')
        return value

    @action(methods=['DELETE'], detail=False)
    async def clear_all(self, **filters) -> Optional[Resource.Retrieve]:
        filters_ = {
            'storage_id': self.identity.did.root,
            'category': self.provider.provider_id
        }
        if 'account_uid' in filters:
            filters_['payload__account_uid'] = filters['account_uid']
        count = await StorageRepository.delete(**filters_)
        if count > 0:
            return HttpResponse(status=204)
        else:
            return None

    @action(methods=['GET'], detail=True)
    async def status(
        self, pk: str, **filters
    ) -> Optional[Resource.Retrieve]:
        entity = await StorageRepository.get(
            **{
                'payload__id': pk,
                'category': self.provider.provider_id
            }
        )
        if entity:
            resource = self.Resource.Retrieve(**entity.payload)
            status = await self.provider.request_status(
                external_id=entity.payload['external_id'],
                request_id=entity.payload['request_id']
            )
            resource.status = status
            return resource
        else:
            return None

    @action(methods=['GET'], detail=True)
    async def personal_data(
        self, pk: str, **filters
    ) -> Optional[AccountKYC]:
        # TODO: подумать над безопасностью
        account = await AccountRepository.get(uid=pk)
        if account:
            kyc = await AccountRepository.load_kyc(account)
            return kyc
        else:
            return None

    @classmethod
    async def update_final_tasks(cls, storage_id: str = None, delay: float = 0.0):
        filters = {
            'category': cls.PROVIDER.provider_id,
            'payload__final': False
        }
        if storage_id:
            filters['storage_id'] = storage_id

        count, entities = await StorageRepository.get_many(**filters)
        if count > 0:
            provider = cls.PROVIDER()
            for entity in entities:
                entity: StorageItem
                try:
                    await asyncio.sleep(delay)
                    data = await provider.request_status(
                        external_id=entity.payload['external_id'],
                        request_id=entity.payload['request_id']
                    )
                    if data:
                        status = data.get('identification').get('status')
                        if status == 'identificationSucceeded':
                            account: Account = await AccountRepository.get(
                                uid=entity.payload['account_uid']
                            )
                            if account:
                                workflow_data = data['workflowData']
                                personal_data = workflow_data['personalData']
                                passport = personal_data['passport']
                                result_workflow = workflow_data.get('resultWorkflow') or []
                                optional_checks = workflow_data.get('optionalChecks', {})
                                passport_id = f'{passport["series"]} {passport["number"]}'

                                kyc = AccountKYC(
                                    document_id=passport_id,
                                    provider=provider.provider_id,
                                    verify=VerifiedDocument(
                                        id=passport_id,
                                        kyc_provider=provider.provider_id,
                                        issued_by=passport['issuedBy'],
                                        issued_date=passport['issuedDate'],
                                        issued_id=passport['divisionCode'],
                                        series=passport["series"],
                                        number=passport["number"],
                                        gender='M' if personal_data['sex'] == 'male' else 'F',
                                        last_name=personal_data['surname'],
                                        first_name=personal_data['firstName'],
                                        middle_name=personal_data['middleName'],
                                        birth_date=personal_data['birthdate'],
                                        birth_place=personal_data['birthplace']
                                    ),
                                    inn=optional_checks.get('inn', {}).get('inn'),
                                    source=result_workflow[0] if result_workflow else None,
                                    external_id=entity.payload['external_id']
                                )
                                await AccountRepository.update_kyc(
                                    kyc=kyc,
                                    account=account
                                )

                        if status in ['identificationFailed', 'identificationSucceeded', 'systemError']:
                            entity.payload['final'] = True
                            upd = await StorageRepository.update(
                                e=entity,
                                **{'payload__id': entity.payload['id']}
                            )
                except Exception as e:
                    pass

    def _build_storage_item(
        self, id_: str, data: Resource.Create
    ) -> StorageItem:
        payload = data.model_dump(
            mode='json'
        )
        payload['until'] = utc_now_float() + data.link_ttl_minutes * 60
        payload['id'] = id_
        return StorageItem(
            storage_id=self.identity.did.root,
            category=self.provider.provider_id,
            payload=payload
        )

    @classmethod
    def _build_applicant(cls, account: Account) -> MTSKYCProvider.Applicant:
        return MTSKYCProvider.Applicant(
            externalId=account.uid,
            email=account.email,
            phone=account.phone,
            firstName=account.first_name,
            surname=account.last_name
        )

    async def clean_old_records(self, until: float = None):
        filters = {
            'storage_id': self.identity.did.root,
            'category': self.provider.provider_id
        }
        if until is None:
            until = utc_now_float()
        filters['payload__until__lt'] = until
        await StorageRepository.delete(**filters)

    async def _create_registration_link(
        self, data: Resource.Create = None,
        remove_same_account_records: bool = False,
        **extra
    ) -> Resource.Retrieve:
        if data is None:
            # with default values
            data = self.Resource.Create()

        if data.account_uid:
            account: Account = await AccountRepository.get(
                uid=data.account_uid
            )
        else:
            account = None

        filter_kwargs = dict(
            storage_id=self.identity.did.root,
            category=self.provider.provider_id,
        )

        if account:
            if remove_same_account_records:
                await StorageRepository.delete(
                    payload__account_uid=data.account_uid,
                    **filter_kwargs
                )
            else:
                raise ValueError(f'Аккаунт {data.account_uid} уже существует')

        if data.account_uid and not account:
            await AccountRepository.create(
                uid=data.account_uid, is_active=False
            )

        if account:
            si = await StorageRepository.get(
                payload__account_uid=data.account_uid,
                **filter_kwargs
            )
            if si:
                raise ValueError(
                    f'Для аккаунта {data.account_uid} уже создана '
                    f'ссылка на регистрацию'
                )
        data.registration = True
        resp = await self.create_one(data, allow_empty_account=True, **extra)
        return resp
