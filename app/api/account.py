import base64
import uuid
from typing import Any, List, Optional, Dict, Union, Literal, Type

from pydantic import Field, BaseModel, field_validator
from pydantic_core.core_schema import FieldValidationInfo
from django.conf import settings
from django.http import (
    HttpResponseForbidden, HttpResponse, HttpResponseBadRequest
)

from lib import BaseResource, action
from lib.mixins import MixinUpdateOne, MixinCreateOne, MixinDeleteOne

from core import (
    load_class, utc_now_float, generate_digit_str, trim_account_uid
)
from kyc import (
    BaseKYCProvider, MTSKYCProvider, BeOrgKYCProvider, FakeKYCProvider
)
from entities import (
    Account, VerifiedDocument, AccountKYC, DocumentPhoto, SelfiePhoto,
    OrganizationDocument, AccountFields, MerchantMeta, UrlPaths, Identity,
    DIDSettings, AccountVerifiedFields, AnonymousAccount
)
from cache import Cache
from entities.auth import MassPaymentsCfg
from api import BaseExchangeController
from reposiroty import (
    AccountRepository, LedgerRepository, AccountCredentialRepository,
    StorageRepository
)
from api.utils import configure_mass_payments_ledger
from api.auth import BaseAuth, AccountCredential
from api.kyc import MTSKYCController


class AccountResource(BaseResource):

    pk = 'uid'

    class Create(AccountFields):
        ...

    class Update(Create):
        ...

    class Retrieve(Account):
        ...


class KYCResource(BaseResource):

    pk = 'uid'

    class Create(BaseResource.Create):
        document: Optional[str] = None
        selfie: Optional[str] = None
        provider_class: Optional[str] = None

    class Update(Create):
        pass

    class Retrieve(OrganizationDocument):
        pass


class OrgDocResource(BaseResource):

    pk = 'uid'

    class Create(BaseResource.Create):
        photo: Optional[str] = None
        attrs: Dict
        type: Optional[str] = None

    class Update(Create):
        attrs: Optional[Dict] = None

    class Retrieve(AccountKYC):
        pass


class MerchantResource(BaseResource):
    pk = 'uid'

    class Create(BaseResource.Create):
        title: Optional[str] = None
        base_currency: Optional[str] = None
        url: Optional[str] = None
        paths: Optional[UrlPaths] = Field(default_factory=UrlPaths)
        mass_payments: Optional[MassPaymentsCfg] = None

    class Update(Create):
        ...

    class Retrieve(MerchantMeta, BaseResource.Retrieve):
        uid: str


class AdminAccountResource(BaseResource):
    pk = 'uid'

    class Create(BaseResource.Create):
        is_active: Optional[bool] = True
        permissions: Optional[List[str]] = None
        is_verified: Optional[bool] = False
        is_organization: Optional[bool] = False
        verified: Optional[AccountVerifiedFields] = None

    class Update(Create):
        ...

    class Retrieve(Update):
        uid: str


class AuthAccountResource(BaseResource):
    pk = 'uid'

    class AdminAuth(BaseModel):
        operation: Literal['remove', 'create', 'read']
        class_: str = Field(default_factory=str, alias='class')
        settings: Optional[Dict] = None

        @field_validator('settings')
        @classmethod
        def check_settings(cls, v: Any, info: FieldValidationInfo) -> Optional[Dict]:
            operation = info.data.get('operation')
            if operation == 'create':
                if v is None:
                    raise ValueError('settings must be set')
            return v

    class Create(BaseResource.Create):
        auths: Optional[List['AdminAuth']] = None

    class Update(Create):
        ...

    class Retrieve(Update):
        uid: str


class AccountController(
    MixinUpdateOne, BaseExchangeController
):

    Resource = AccountResource
    PERMISSIONS = {
        'get_one': [Account.Permission.ACCOUNTS.value],
        'get_many': [Account.Permission.ACCOUNTS.value],
        'iam': None,
        'update_or_create': [Account.Permission.ACCOUNTS.value],
        'verify': [Account.Permission.KYC.value],
        'kyc': [Account.Permission.KYC.value],
        'test': None,
        'update_one': [Account.Permission.ANY.value],
        'update_merchant': [Account.Permission.ROOT.value],
        'admin': [Account.Permission.ACCOUNTS.value]
    }

    @action(detail=False, methods=['POST'])
    async def update_or_create(
        self, data: Resource.Create, **filters
    ) -> Union[Account, HttpResponse]:
        d = data.model_dump()
        if filters:
            account = await AccountRepository.get(**filters)
        else:
            account = None
        if account:
            d['uid'] = account.uid
        else:
            d['uid'] = filters.get('uid') or 'auto:' + uuid.uuid4().hex
        filters['uid'] = d['uid']
        e = Account.model_validate(d)
        account = await AccountRepository.update_or_create(e, **filters)
        return account

    async def update_one(
        self, pk: Any, data: Resource.Update, **extra
    ) -> Union[Optional[BaseResource.Retrieve], HttpResponse]:
        # индивидуальный подход к проверке
        if Account.Permission.ROOT.value not in self.context.user.permissions:
            if Account.Permission.ACCOUNTS.value not in self.context.user.permissions:
                if self.context.user.uid != pk:
                    return HttpResponseForbidden()

        account: Account = await AccountRepository.update(data, uid=pk)
        return account

    async def get_one(self, pk: Any, **filters) -> Optional[Resource.Retrieve]:
        try:
            account = await AccountRepository.get(uid=pk, **filters)
        except Exception as e:
            raise
        return account

    async def get_many(
        self, order_by: Any = 'id', limit: int = None,
        offset: int = None, **filters
    ) -> List[Resource.Retrieve]:
        total, accounts = await AccountRepository.get_many(
            order_by=order_by, limit=limit, offset=offset, **filters
        )
        self.metadata.total_count = total
        return accounts

    @action(detail=False)
    async def iam(self, **filters) -> Optional[Account]:
        return self.context.user

    @action(detail=True, methods=['POST'], resource=MerchantResource)
    async def update_merchant(
        self, pk, data: MerchantResource.Update, **filters
    ) -> Union[MerchantResource.Retrieve, HttpResponse, None]:
        account: Account = await AccountRepository.get(uid=pk)
        if not account:
            return None
        if Account.Permission.MERCHANT.value not in account.permissions:
            return HttpResponseBadRequest(content=b'Account is not merchant')
        if not data:
            return HttpResponseBadRequest(content=b'Data is empty')

        data_as_meta = MerchantMeta.model_validate(
            data.model_dump(mode='json')
        )
        exists_meta = MerchantMeta.model_validate(account.merchant_meta) if account.merchant_meta else None  # noqa
        creator = self.identity
        if not data_as_meta.identity:
            did_paths = creator.did.root.split(':')
            did_paths.append(account.uid)
            data_as_meta.identity = Identity(
                did=DIDSettings(
                    root=':'.join(did_paths)
                )
            )
        owner = data_as_meta.identity
        if exists_meta and exists_meta.mass_payments.ledger:
            dlts = await LedgerRepository.load(owner)
            dlts = [i for i in dlts if 'payments' in i.tags]
            dlt = dlts[0] if dlts else None
        else:
            dlt = None

        if not data_as_meta.mass_payments.ledger and dlt:
            data_as_meta.mass_payments.ledger = dlt  # noqa
        if data_as_meta.mass_payments.ledger and dlt:
            if data_as_meta.mass_payments.ledger.id != dlt.id:
                return HttpResponseBadRequest(
                    content=b'You can not change ledger id'
                )
        if data_as_meta.mass_payments and data_as_meta.mass_payments.enabled:
            if not data_as_meta.mass_payments.ledger:
                dlt = configure_mass_payments_ledger(  # noqa
                    self.context.config, owner=owner, ledger=None
                )
                data_as_meta.mass_payments.ledger = dlt
        if data_as_meta.mass_payments.ledger:
            await LedgerRepository.ensure_exists(
                identity=owner, ledgers=[data_as_meta.mass_payments.ledger]
            )

        account.merchant_meta = data_as_meta
        account = await AccountRepository.update(account, uid=pk)
        return MerchantResource.Retrieve(
            uid=account.uid,
            title=data_as_meta.title,
            base_currency=data_as_meta.base_currency,
            url=data_as_meta.url,
            paths=data_as_meta.paths,
            ratios=data_as_meta.ratios,
            mass_payments=data_as_meta.mass_payments,
            identity=data_as_meta.identity
        )

    @action(detail=True, methods=['POST'], resource=AdminAccountResource)
    async def admin(
        self, pk, data: AdminAccountResource.Create, **filters
    ) -> Union[AdminAccountResource.Retrieve, HttpResponse, None]:
        account: Account = await AccountRepository.get(uid=pk)
        if not account:
            return None
        if any([perm in data.permissions for perm in (Account.Permission.ROOT.value, Account.Permission.ACCOUNTS.value, Account.Permission.MERCHANT.value)]):  # noqa
            if not self.context.user.has_root_permission:
                return HttpResponseBadRequest(f'Необходимо обладать правами root')
        if any([perm in data.permissions for perm in (Account.Permission.OPERATOR.value)]):  # noqa
            if not (self.context.user.has_root_permission or self.context.user.has_accounts_permission):  # noqa
                return HttpResponseBadRequest(f'Необходимо обладать правами')
        if all([perm in data.permissions for perm in (Account.Permission.ROOT.value, Account.Permission.MERCHANT.value)]):  # noqa
            return HttpResponseBadRequest(f'Нельзя совмещать статус мерчанта и суперпользователя')  # noqa
        if Account.Permission.MERCHANT.value in data.permissions:
            if any([perm in data.permissions for perm in (Account.Permission.OPERATOR.value, Account.Permission.ACCOUNTS.value)]):  # noqa
                return HttpResponseBadRequest(f'Нельзя совмещать статус мерчанта и оператора сервиса')  # noqa
        # Other fields
        upd_payload = data.model_dump()
        payload = account.model_dump()
        payload |= upd_payload
        upd_account = Account.model_validate(payload)
        account = await AccountRepository.update(upd_account, uid=pk)
        result = AdminAccountResource.Retrieve(**account.model_dump())
        return result

    @action(detail=True, methods=['GET', 'POST'], resource=AuthAccountResource)
    async def auth(
        self, pk, data: AuthAccountResource.Create = None, **filters
    ) -> Union[AdminAccountResource.Retrieve, HttpResponse, None]:
        account: Account = await AccountRepository.get(uid=pk)
        if not account:
            return None
        if self.method.lower() == 'post' and data.auths:
            for auth in data.auths:
                auth: AdminAccountResource.AdminAuth
                engine_cls = BaseAuth.load_descendant(auth.class_)
                if not engine_cls:
                    return HttpResponseBadRequest(
                        content=f'Unknown auth engine {auth.class_}'.encode()
                    )
                engine_cls: Type[BaseAuth]
                if auth.operation == 'create':
                    if not engine_cls.validate(auth.settings):
                        return HttpResponseBadRequest(
                            content=b'Invalid auth.settings schema'
                        )
                    try:
                        await engine_cls.register(account, auth.settings)
                    except ValueError as e:
                        return HttpResponseBadRequest(e.args[0])
                elif auth.operation == 'remove':
                    await AccountCredentialRepository.delete(
                        account_uid=account.uid, class_name=engine_cls.__name__
                    )

        # load actual auths
        _, creds = await AccountCredentialRepository.get_many(
            account_uid=account.uid
        )
        result = AuthAccountResource.Retrieve(uid=pk)
        result.auths = []
        for cred in creds:
            cred: AccountCredential
            engine_cls = BaseAuth.load_descendant(cred.class_name)
            result.auths.append(
                AuthAccountResource.AdminAuth(
                    **{
                        'operation': 'read',
                        'class': engine_cls.Name,
                        'settings': cred.payload
                    }
                )
            )
        return result

    @action(
        detail=True, url_path='document',
        resource=OrgDocResource,
        methods=['GET', 'POST']
    )
    async def document_cr(
        self, pk: str, data: OrgDocResource.Create = None, **filters
    ):
        account: Account = await AccountRepository.get(uid=pk)
        if not account:
            return None
        if self.method.lower() == 'get':
            total, docs = await AccountRepository.get_documents(
                account, **filters
            )
            self.metadata.total_count = total
            return docs
        elif self.method.lower() == 'post':
            if data:
                photo = DocumentPhoto()
                photo.from_image(raw=base64.b64decode(data.photo))
                doc = OrganizationDocument(
                    type=data.type, document=photo, attrs=data.attrs
                )
                doc = await AccountRepository.create_document(account, doc)
                return doc
            else:
                raise ValueError(f'Document data is empty')
        return Account.model_validate(dict(test='success', uid='test'))

    @action(
        detail=True, url_path='document/<int:document_id>',
        resource=OrgDocResource,
        methods=['GET', 'PUT', 'DELETE']
    )
    async def document_urd(
        self, pk: str, data: OrgDocResource.Update = None, **filters
    ):
        account: Account = await AccountRepository.get(uid=pk)
        if not account:
            return None
        document_id = filters['document_id']
        if self.method.lower() == 'get':
            _, docs = await AccountRepository.get_documents(
                account, id=document_id
            )
            return docs[0] if docs else None
        elif self.method.lower() == 'put':
            doc = OrganizationDocument(
                type=data.type,
                attrs=data.attrs,
                document=DocumentPhoto(image=data.photo)
            )
            doc = await AccountRepository.update_document(
                account, doc, id_=document_id
            )
            return doc
        elif self.method.lower() == 'delete':
            doc = await AccountRepository.remove_document(
                account, id_=document_id
            )
            return doc

    @action(detail=True, resource=KYCResource, methods=['GET'])
    async def kyc(self, pk: str) -> Optional[KYCResource.Retrieve]:
        account: Account = await AccountRepository.get(uid=pk)
        if not account:
            return None
        kyc = await AccountRepository.load_kyc(account)
        if kyc:
            return kyc
        else:
            raise ValueError('Account doesnt have KYC')

    @action(detail=True, resource=KYCResource, methods=['POST'])
    async def verify(
        self, pk: str, data: KYCResource.Create = None
    ) -> Optional[VerifiedDocument]:
        account: Account = await AccountRepository.get(uid=pk)
        if not account:
            return None
        try:
            provider_class = load_class(
                data.provider_class or settings.KYC['PROV_CLASS']
            )
        except Exception as e:
            raise ValueError from e
        provider: BaseKYCProvider = provider_class()
        photos = []
        raw_doc = None
        raw_selfie = None
        if data.document:
            raw_doc = base64.b64decode(data.document)
            doc = DocumentPhoto()
            doc.from_image(raw_doc)
            photos.append(doc)
        if data.selfie:
            raw_selfie = base64.b64decode(data.selfie)
            selfie = SelfiePhoto()
            selfie.from_image(raw_selfie)
            photos.append(selfie)
        verified_doc = await provider.verify(photos=photos)
        kyc = AccountKYC(
            document_id=verified_doc.id,
            provider=provider.provider_id,
            verify=verified_doc,
        )
        if raw_doc:
            kyc.photos.document = DocumentPhoto()
            kyc.photos.document.from_image(raw_doc)
        if raw_selfie:
            kyc.photos.selfie = SelfiePhoto()
            kyc.photos.selfie.from_image(raw_selfie)

        await AccountRepository.update_kyc(kyc, account)
        account.is_verified = True
        await AccountRepository.update(account, uid=pk)
        return verified_doc


class RegisterResource(BaseResource):

    pk = 'id'

    class Create(BaseResource.Create):
        account_uid: Optional[str] = None
        link_ttl_minutes: Optional[int] = None
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
        fields: AccountFields

    class Retrieve(Update):
        id: str
        until: float = None
        status: Optional[dict] = None
        kyc_provider: str


class RegistrationController(
    MixinUpdateOne, BaseExchangeController
):
    # пользователь хотя бы должен быть Anonymous, т.е.
    # он должен делать запрос с страницы сайта
    PERMISSIONS = {'*': Account.Permission.ANY.value}

    Resource = RegisterResource
    _avail_providers = [
        MTSKYCProvider.provider_id,
        BeOrgKYCProvider.provider_id,
        FakeKYCProvider.provider_id
    ]
    _kyc_class = MTSKYCController

    async def get_one(
        self, pk: Any, **filters
    ) -> Optional[Resource.Retrieve]:
        values = await self.get_many(id=pk)
        return values[0] if values else None

    async def get_many(
        self, order_by: Any = 'id', limit: int = None,
        offset: int = None, **filters
    ) -> List[RegisterResource.Retrieve]:
        provider = filters.pop('provider', None)
        complex_filters = {}
        if provider:
            complex_filters['category'] = provider
        else:
            complex_filters['category__in'] = self._avail_providers
        for k, v in filters.items():
            complex_filters[f'payload__{k}'] = v
        total, many = await StorageRepository.get_many(
            order_by=order_by, limit=limit, offset=offset,
            **complex_filters
        )
        result = []
        fields = AccountFields.model_validate(self.context.user.model_dump())
        for si in many:
            entity = self.Resource.Retrieve.model_validate(
                dict(
                    kyc_provider=si.category,
                    fields=fields,
                    **si.payload
                )
            )
            result.append(entity)
        return result

    @action(detail=True, methods=['POST'], resource=BaseResource)
    async def accept(
        self, pk: str, data: BaseResource.Create, **filters
    ) -> HttpResponse:
        ctrl = ContactsVerifyController(context=self.context)
        resp = await ctrl._accept()
        if resp.status_code == 200:
            if isinstance(self.context.user, AnonymousAccount):
                reg_link = await self.get_one(pk)
                if not reg_link.account_uid:
                    # пробуем создать аккаунт по уник значению контакта
                    account_uid = 'auto:' + uuid.uuid4().hex
                    for attr in ['phone', 'email', 'telegram']:
                        try_uid = getattr(self.context.user, attr, None)
                        if try_uid:
                            try_uid = trim_account_uid(try_uid)
                            e = await AccountRepository.get(uid=try_uid)
                            if not e:
                                account_uid = try_uid
                                break
                else:
                    account_uid = reg_link.account_uid

                kyc = await AccountRepository.load_kyc(self.context.user)

                create_account = Account.model_validate(
                    self.context.user.model_dump(
                        exclude={'is_anonymous', 'id', 'kyc'}
                    )
                )
                create_account.is_active = True
                create_account.uid = account_uid
                acc = await AccountRepository.update_or_create(
                    create_account, uid=account_uid
                )
                if kyc:
                    await AccountRepository.update_kyc(
                        kyc, create_account
                    )
                if isinstance(self.context.user, AnonymousAccount):
                    await AccountRepository.delete_anonymous_account(
                        uid=self.context.user.uid
                    )
                resp = HttpResponse(b'OK')
                await BaseAuth.login(resp, create_account)
                return resp
        else:
            return resp

    async def update_one(
        self, pk: Any, data: Resource.Update, **extra
    ) -> Optional[BaseResource.Retrieve]:
        obj = self.context.user.model_dump()
        obj |= data.fields.model_dump()
        account = self.context.user.model_validate(obj)
        self.context.user = await AccountRepository.update(
            account, uid=account.uid
        )
        entity = await self.get_one(pk)
        return entity

    @action(
        detail=True, methods=['POST'],
        resource=BaseResource, url_path='regenerate'
    )
    async def regenerate_reg_link_for_pk(
        self, pk: str, data: BaseResource.Create, **filters
    ) -> Optional[Resource.Retrieve]:
        resp = await self.__regenerate_reg_link(pk)
        return resp

    @action(
        detail=False, methods=['POST'],
        resource=BaseResource, url_path='regenerate'
    )
    async def regenerate_reg_link(
            self, data: BaseResource.Create, **filters
    ) -> Optional[Resource.Retrieve]:
        resp = await self.__regenerate_reg_link()
        return resp

    async def __regenerate_reg_link(self, pk=None) -> Resource.Retrieve:
        ctrl = self._kyc_class(context=self.context)
        if pk:
            entity = await ctrl.get_one(pk)
        else:
            entity = None

        if entity:
            data = self._kyc_class.Resource.Create(
                account_uid=entity.account_uid,
                link_ttl_minutes=entity.link_ttl_minutes,
                manual_input=entity.manual_input,
                esia=entity.esia,
                mobile_phone=entity.mobile_phone,
                verification=entity.verification,
                inn=entity.inn,
                bio=entity.bio
            )
        else:
            data = None

        try:
            reg_link = await ctrl._create_registration_link(
                data, remove_same_account_records=True
            )
        except ValueError as e:
            err_msg = e.args[0] if e.args else str(e)
            return HttpResponseBadRequest(
                content=err_msg.encode()
            )
        else:
            d = reg_link.model_dump()
            d['fields'] = AccountFields.model_validate(
                self.context.user.model_dump()
            )
            d['kyc_provider'] = ctrl.PROVIDER.provider_id
            return self.Resource.Retrieve.model_validate(d)


class ContactResource(BaseResource):

    pk = 'id'

    class Create(BaseResource.Create):
        id: str
        code: Optional[str] = None
        ttl: Optional[float] = None
        value: Optional[str] = None

    class Update(Create):
        ...

    class Retrieve(Update):
        verified: bool
        value: Optional[str] = None
        temporary: bool


class ContactsVerifyController(
    MixinCreateOne, MixinDeleteOne, BaseExchangeController
):

    Resource = ContactResource
    # пользователь хотя бы должен быть Anonymous, т.е.
    # потом что данные накапливаются для пользовательской сессии
    PERMISSIONS = {'*': Account.Permission.ANY.value}

    _cache = Cache(pool=settings.REDIS_CONN_POOL, namespace='account-contact')
    # эти поля обязательно должны быть верифицированы для успешного prove
    _must_be_verified = ['phone']

    async def create_one(
        self, data: Resource.Create, **extra
    ) -> Union[Resource.Retrieve, HttpResponse]:
        cache = self._cache.namespace(self.context.user.uid)
        meta = await cache.get(data.id)
        if data.code:
            if not meta:
                return HttpResponseBadRequest(
                    f'Таймаут вышел'.encode()
                )
            stored_code = meta.get('code')
            valid_codes = [stored_code]
            if self.context.config.sms.debug_code:
                valid_codes.append(self.context.config.sms.debug_code)
            if data.code in valid_codes:
                meta['verified'] = True
                await cache.set(
                    key=data.id, value=meta, ttl=60*60
                )
                return await self.get_one(pk=data.id)
            else:
                return HttpResponseBadRequest(
                    f'Неверный код'.encode()
                )
        else:
            if meta and not meta.get('verified', False) and data.id in self._must_be_verified:
                return HttpResponseBadRequest(
                    f'Таймаут не вышел'.encode()
                )
            if not data.ttl:
                return HttpResponseBadRequest(
                    f'ttl should be > 0'.encode()
                )
            if data.value:
                meta = dict(
                    id=data.id,
                    expire_at=utc_now_float() + data.ttl,
                    code=generate_digit_str(4),
                    value=data.value,
                    verified=False
                )
                await cache.set(
                    key=data.id, value=meta,
                    ttl=round(data.ttl) if data.ttl else 360
                )
                return await self.get_one(pk=data.id)
            else:
                return await self.delete_one(pk=data.id)

    async def delete_one(
        self, pk: Any, **extra
    ) -> Optional[BaseResource.Retrieve]:
        ret = await self.get_one(pk)
        if ret:
            cache = self._cache.namespace(self.context.user.uid)
            await cache.delete(pk)
            return ret
        else:
            return None

    async def get_one(
        self, pk: Any, **filters
    ) -> Optional[Resource.Retrieve]:
        res = await self.get_many()
        if res:
            res = [i for i in res if i.id == pk]
        return res[0] if res else None

    async def get_many(
        self, order_by: Any = 'id', limit: int = None,
        offset: int = None, **filters
    ) -> List[Resource.Retrieve]:
        result = []
        cache = self._cache.namespace(self.context.user.uid)
        methods = ['phone', 'email', 'telegram']
        metas = await cache.get(methods)
        for method in methods:
            meta_verif = metas.get(method)
            if meta_verif:
                verified_ = meta_verif.get('verified', False)
                value_ = meta_verif.get('value')
                ttl_ = meta_verif['expire_at'] - utc_now_float()
                temporary_ = True
            else:
                verified_ = getattr(self.context.user.verified, method, False)
                value_ = getattr(self.context.user, method, None)
                ttl_ = None
                temporary_ = False
            result.append(
                self.Resource.Retrieve(
                    id=method,
                    verified=verified_,
                    value=value_,
                    ttl=ttl_,
                    temporary=temporary_
                )
            )
        return result

    @action(detail=False, methods=['POST'], resource=BaseResource)
    async def accept(
        self, data: BaseResource.Create, **filters
    ) -> HttpResponse:
        resp = await self._accept()
        return resp

    async def _accept(self) -> Union[HttpResponse, HttpResponseBadRequest]:
        items = await self.get_many()
        verified = [i for i in items if i.id in self._must_be_verified and i.verified]
        if len(verified) < len(self._must_be_verified):
            return HttpResponseBadRequest(
                'Не пройдена верификация контактов'.encode()
            )
        for i in items:
            setattr(self.context.user, i.id, i.value)
            setattr(self.context.user.verified, i.id, i.verified)
            await AccountRepository.update(
                self.context.user, uid=self.context.user.uid
            )
        return HttpResponse(b'OK')


