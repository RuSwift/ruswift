import base64
import uuid
from datetime import datetime
from typing import Any, List, Optional, Tuple, Literal, Union

from pydantic import AnyHttpUrl, BaseModel, Extra, Field
from django.http import (
    HttpRequest, Http404, HttpResponseNotAllowed,
    HttpResponse, HttpResponseForbidden, HttpResponseBadRequest
)

from api.lib import BaseResource, action

from exchange.models import MassPaymentBalance
from exchange.microledger import (
    MassPaymentMicroLedger, DatabasePaymentConsensus
)
from exchange.entities import (
    mass_payment, Account, MerchantAccount, StorageItem, Identity
)
from exchange.ratios import GarantexEngine
from exchange.reposiroty import StorageRepository, AccountRepository, AtomicDelegator  # noqa
from exchange.api import BaseExchangeController, AuthControllerMixin
from exchange.reports import QugoRegistry


class MassPaymentResource(BaseResource):

    pk = 'id'

    class Create(BaseResource.Create):
        uid: Optional[str] = None
        transaction: mass_payment.PaymentTransaction
        customer: mass_payment.PaymentCustomer
        card: mass_payment.PaymentCard
        proof: Optional[mass_payment.Proof] = None

    class Update(Create):
        ...

    class Retrieve(Update):
        id: str
        # status: mass_payment.PaymentStatus
        utc: datetime
        uid: str


class StatusResource(BaseResource):

    class Create(BaseResource.Create):
        type: str = 'payout'
        status: Literal['pending', 'processing', 'success', 'error', 'attachment']  # noqa
        error: Optional[bool] = False
        sandbox: Optional[bool] = False
        earned: Optional[float] = None
        response_code: Optional[int] = None
        payload: Optional[dict] = None
        message: Optional[str] = None

    class Update(Create):
        uid: str

    class Retrieve(Create):
        id: str
        order_id: str
        description: Optional[str] = None
        user: str
        amount: float
        currency: str
        utc: datetime


class AttachmentsResource(BaseResource):

    class Create(BaseResource.Create):
        uid: Optional[str] = None
        name: str
        data: str
        mime_type: Optional[str] = None

    class Update(Create):
        data: Optional[str] = None

    class Retrieve(Update):
        uid: str
        utc: datetime


class PayloadAttachment(BaseModel):
    uid: str
    name: Optional[str] = None
    mime_type: Optional[str] = None


class PayloadAttachments(BaseModel):
    attachments: List[PayloadAttachment]


class AssetsRatios(BaseModel):
    engine: str
    base: str
    quote: str
    ratio: Optional[float] = None


class MassPaymentAssetsResource(BaseResource):
    STORAGE_CATEGORY = 'mass-payment-settings'
    TYPE_DEPOSIT = 'mass-payment-deposit'
    TYPE_RESERVED = 'mass-payment-reserved'

    class PersistentSettings(BaseModel, extra=Extra.ignore):
        webhook: Optional[AnyHttpUrl] = None

    class Create(BaseResource.Create):
        webhook: Optional[AnyHttpUrl] = None

    class Update(Create):
        ...

    class Retrieve(Update):
        id: str = '1'
        balance: Optional[float]
        deposit: Optional[float]
        reserved: Optional[float]
        code: Optional[str]
        address: str
        ratios: Optional[AssetsRatios] = None

    class DepositResource(BaseResource):
        """Вынес в отдельный подкласс чтобы изоировать денежные операции"""

        class Create(BaseResource.Create):
            uid: Optional[str] = None
            amount: Optional[float] = None
            attachments: List[AttachmentsResource.Create] = Field(
                default_factory=list
            )

        class Update(Create):
            status: Literal['pending', 'success', 'error', 'attachment', 'correction']  # noqa

        class Retrieve(Update):
            uid: str
            utc: Optional[datetime]
            address: Optional[str] = None
            pay_method_code: Optional[str] = None
            attachments: List[PayloadAttachment] = Field(
                default_factory=list
            )

    @classmethod
    async def read_settings(cls, account: MerchantAccount) -> PersistentSettings:
        filters = dict(
            category=cls.STORAGE_CATEGORY,
            storage_id=account.meta.identity.did.root,
        )
        item: Optional[StorageItem] = await StorageRepository.get(**filters)
        if item:
            settings = cls.PersistentSettings.model_validate(
                item.payload
            )
            return settings
        else:
            return cls.PersistentSettings()

    @classmethod
    async def write_settings(
        cls, account: MerchantAccount, value: PersistentSettings
    ) -> PersistentSettings:
        filters = dict(
            category=cls.STORAGE_CATEGORY,
            storage_id=account.meta.identity.did.root,
        )
        item = StorageItem(
            payload=value.model_dump(mode='json'),
            **filters
        )
        actual = await StorageRepository.update_or_create(item, **filters)
        settings = cls.PersistentSettings.model_validate(actual.payload)
        return settings

    @classmethod
    async def read_balances(
        cls, account: MerchantAccount
    ) -> Tuple[float, float]:
        deposit, reserved = 0.0, 0.0
        # 1
        deposit_rec = await MassPaymentBalance.objects.filter(
            account_uid=account.uid, type=cls.TYPE_DEPOSIT
        ).afirst()
        if deposit_rec:
            deposit = deposit_rec.value
        # 2
        reserved_rec = await MassPaymentBalance.objects.filter(
            account_uid=account.uid, type=cls.TYPE_RESERVED
        ).afirst()
        if reserved_rec:
            reserved = reserved_rec.value
        return deposit, reserved

    @classmethod
    def update_balances(
        cls, account: MerchantAccount,
        balance_increment: float, reserved_increment: float
    ) -> Tuple[float, float]:
        # 1
        deposit_rec, _ = MassPaymentBalance.objects.update_or_create(
            account_uid=account.uid, type=cls.TYPE_DEPOSIT
        )
        deposit_rec.value += balance_increment
        deposit_rec.save(update_fields=['value'])
        # 2
        reserved_rec, _ = MassPaymentBalance.objects.update_or_create(
            account_uid=account.uid, type=cls.TYPE_RESERVED
        )
        reserved_rec.value += reserved_increment
        reserved_rec.save(update_fields=['value'])
        # 3
        return deposit_rec.value, reserved_rec.value

    @classmethod
    def set_balances(
        cls, account: MerchantAccount,
        balance: float, reserved: float
    ) -> Tuple[float, float]:
        # 1
        deposit_rec, _ = MassPaymentBalance.objects.update_or_create(
            account_uid=account.uid, type=cls.TYPE_DEPOSIT
        )
        deposit_rec.value = balance
        deposit_rec.save(update_fields=['value'])
        # 2
        reserved_rec, _ = MassPaymentBalance.objects.update_or_create(
            account_uid=account.uid, type=cls.TYPE_RESERVED
        )
        reserved_rec.value = reserved
        reserved_rec.save(update_fields=['value'])
        # 3
        return deposit_rec.value, reserved_rec.value


class AtomicChangeBalances(AtomicDelegator):

    def __init__(
        self, merchant: MerchantAccount,
        balance_increment: float, reserved_increment: float
    ):
        self._merchant = merchant
        self._balance_increment = balance_increment
        self._reserved_increment = reserved_increment
        self._deposit: Optional[float] = None
        self._reserved: Optional[float] = None

    @property
    def deposit(self) -> Optional[float]:
        return self._deposit

    @property
    def reserved(self) -> Optional[float]:
        return self._reserved

    def atomic(self, *args, **kwargs):
        self._deposit, self._reserved = MassPaymentAssetsResource.update_balances(
            account=self._merchant,
            balance_increment=self._balance_increment,
            reserved_increment=self._reserved_increment
        )


class MassPaymentController(AuthControllerMixin, BaseExchangeController):
    PERMISSIONS = {'*': Account.Permission.MERCHANT.value}
    Resource = MassPaymentResource

    EDITABLE_STATUSES = ['attachment']

    class ParticipantContext(BaseExchangeController.Context):
        identity: Optional[Identity] = None
        merchant: Optional[MerchantAccount] = None

    context: ParticipantContext

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._ledger: Optional[MassPaymentMicroLedger] = None

    async def check_permission(
        self, request: HttpRequest, handler
    ) -> bool:
        success = await super().check_permission(request, handler)
        if success:
            return await self._detailed_check_permission()
        else:
            return False

    @property
    def ledger(self) -> MassPaymentMicroLedger:
        if self._ledger is None:
            self._ledger = MassPaymentMicroLedger.create_from_ledger(
                src=self.context.merchant.meta.mass_payments.ledger,
                me=self.context.identity,
                consensus_cls=DatabasePaymentConsensus
            )
        return self._ledger

    async def get_one(self, pk: Any, **filters) -> Optional[Resource.Retrieve]:
        msg = await self._load_payment_msg(pk)
        if msg:
            return self.Resource.Retrieve(
                id=msg.transaction.order_id,
                **dict(msg)
            )
        else:
            return None

    async def get_many(
        self, order_by: Any = 'id', limit: int = None,
        offset: int = None, **filters
    ) -> List[Resource.Retrieve]:
        total, many = await self.ledger.load_payments(
            limit=limit, offset=offset, sort='desc', **filters
        )
        self.metadata.total_count = total
        result: List[MassPaymentResource.Retrieve] = []
        for msg in many:
            result.append(
                MassPaymentResource.Retrieve(
                    id=msg.transaction.order_id,
                    **dict(msg)
                )
            )
        return result

    async def create_one(
        self, data: Resource.Create, **extra
    ) -> Optional[Resource.Retrieve]:
        data.uid = data.uid or uuid.uuid4().hex

        duplicates = await self.ledger.load_states(
            keys=[data.transaction.order_id]
        )
        if duplicates:
            return HttpResponseBadRequest(
                content=f'Order with order_id "{data.transaction.order_id}" already exists'.encode()
            )
        await self.ledger.send(
            msg=MassPaymentMicroLedger.Message(
                **dict(data)
            ),
            states={
                data.uid: 'pending',
                data.transaction.order_id: 'exists'
            }
        )
        order = await self.get_one(data.transaction.order_id)
        return order

    async def create_many(
        self, data: List[Resource.Create], **extra
    ) -> List[Resource.Retrieve]:
        creation = {}
        states = {}
        for d in data:
            d.uid = d.uid or uuid.uuid4().hex
            creation[d.uid] = dict(d)
            states[d.uid] = 'pending'
        # check duplicates
        order_id_set = set()
        for item in data:
            item: MassPaymentResource.Create
            if item.transaction.order_id in order_id_set:
                return HttpResponseBadRequest(
                    content=f'Order "{item.transaction.order_id}" already exists'.encode()
                )
            else:
                order_id_set.add(item.transaction.order_id)
        duplicates = await self.ledger.load_states(
            keys=list(order_id_set)
        )
        if duplicates:
            kv = duplicates[0]
            return HttpResponseBadRequest(
                content=f'Order with order_id "{kv.key}" already exists'.encode()
            )

        await self.ledger.send_batch(
            msgs=[
                MassPaymentMicroLedger.Message(**d)
                for uid, d in creation.items()
            ],
            states=states
        )
        res = await self.get_many(
            uid=list(creation.keys())
        )
        return res

    @action(detail=True, url_path='status', resource=StatusResource)
    async def order_status(
        self, pk, **filters
    ) -> Optional[StatusResource.Retrieve]:
        msg = await self._load_payment_msg(pk)
        if msg:
            return self._cast_storage_item_to_status(msg)
        else:
            return None

    @action(
        methods=['GET', 'POST'],
        detail=False, url_path='status', resource=BaseResource
    )
    async def order_status_many(
        self, order_by: Any = 'id', limit: int = None,
        offset: Any = None,
        data: List[BaseResource.Create] = None,  # noqa
        **filters
    ) -> List[Union[StatusResource.Retrieve, AttachmentsResource.Retrieve]]:
        if self.method == 'GET':
            return await self._read_order_status_many(
                order_by=order_by, limit=limit, offset=offset, **filters
            )
        else:
            attach_items = []
            status_items = []
            state_statuses = ['pending', 'success', 'processing', 'error']
            status_msg_with_attachments: List[
                MassPaymentMicroLedger.Message] = []
            states = {}
            if not isinstance(data, list):
                data = [data]
            for item in data:
                # statuses
                try:
                    s = StatusResource.Update.model_validate(dict(item))
                    if self.EDITABLE_STATUSES is not None:
                        if s.status not in self.EDITABLE_STATUSES:
                            return HttpResponseForbidden()
                    if s.status in state_statuses:
                        states[s.uid] = s.status
                    status_msg = MassPaymentMicroLedger.Message(
                        uid=s.uid,
                        type='status',
                        status=mass_payment.PaymentStatus(
                            **dict(s)
                        )
                    )
                    status_items.append(status_msg)
                    try:
                        if s.payload:
                            container = PayloadAttachments.model_validate(
                                s.payload)
                            status_msg_with_attachments.append(status_msg)
                    except ValueError:
                        ...
                    continue
                except ValueError:
                    pass
                # attachments
                try:
                    a = AttachmentsResource.Create.model_validate(dict(item))
                except ValueError:
                    pass
                else:
                    attach_items.append(a)

            if attach_items:
                stored_attachments = await self._attachments(
                    data=attach_items, mute_data=True
                )
                stored_attachments_map = {
                    a.uid: a for a in stored_attachments
                }
            else:
                stored_attachments_map = {}
            if status_msg_with_attachments:
                attach_uid = []
                for msg in status_msg_with_attachments:
                    container = PayloadAttachments.model_validate(
                        msg.status.payload)  # noqa
                    attach_uid.extend([a.uid for a in container.attachments])
                attach_uid = list(set(attach_uid))
                uid_to_load = [
                    uid for uid in attach_uid if
                    uid not in stored_attachments_map  # noqa
                ]
                if uid_to_load:
                    extra_stored_attachments = await self._attachments(
                        uid=uid_to_load, mute_data=True
                    )
                    for a in extra_stored_attachments:
                        stored_attachments_map[a.uid] = a
                for msg in status_msg_with_attachments:
                    container = PayloadAttachments.model_validate(
                        msg.status.payload)
                    full_attachments = []
                    for a in container.attachments:
                        info: Optional[
                            AttachmentsResource.Retrieve] = stored_attachments_map.get(
                            a.uid)  # noqa
                        if info is None:
                            raise ValueError(
                                f'Attachment with UID: {a.uid} not found'
                            )
                        full_attachments.append(info.model_dump(mode='json'))
                    msg.status.payload['attachments'] = full_attachments

            # Fire !!!
            await self.ledger.send_batch(status_items, states=states)
            _, payments = await self.ledger.load_payments(
                uid=[i.uid for i in status_items]
            )
            return [self._cast_storage_item_to_status(p) for p in payments]

    @action(
        methods=['GET', 'POST'],
        detail=False, url_path='assets', resource=MassPaymentAssetsResource
    )
    async def assets(
        self, data: MassPaymentAssetsResource.Create = None,  **filters
    ) -> Optional[MassPaymentAssetsResource.Retrieve]:
        if self.method == 'POST':
            settings = MassPaymentAssetsResource.PersistentSettings(
                **dict(data)
            )
            await MassPaymentAssetsResource.write_settings(
                self.context.merchant, settings
            )
            return await self._read_assets(self.context.merchant)
        else:
            return await self._read_assets(self.context.merchant)

    @action(
        methods=['GET', 'POST'],
        detail=True, url_path='deposit',
        resource=MassPaymentAssetsResource.DepositResource
    )
    async def deposit_one(
        self, pk,
        data: Union[
            MassPaymentAssetsResource.DepositResource.Create,
            MassPaymentAssetsResource.DepositResource.Update
        ] = None,
        **filters
    ) -> Optional[
        Union[
            MassPaymentAssetsResource.DepositResource.Retrieve,
            HttpResponse
        ]
    ]:
        my_role = self.context.merchant.meta.mass_payments.ledger.role_by_did(
            did=self.identity.did.root
        )
        if not my_role:
            return HttpResponseForbidden()

        msgs = await self.ledger.load_deposits(
            aggregate=True, uid=pk
        )
        if msgs:
            msg = msgs[0]
        else:
            return None

        if self.method == 'GET':
            return self._msg2deposit_entity(msg)
        elif self.method == 'POST':
            if my_role != 'processing':
                if data.status != 'attachment':
                    return HttpResponseForbidden()
            if data.amount:
                msg.transaction.amount = data.amount
            msg.status.status = data.status
            atomic = None

            if data.status in ['success', 'correction']:
                atomic = AtomicChangeBalances(
                    merchant=self.context.merchant,
                    balance_increment=msg.transaction.amount,
                    reserved_increment=0
                )

            if data.attachments:
                stored_attachments = await self._attachments(
                    data=data.attachments, mute_data=True
                )
                msg.status.payload = PayloadAttachments(
                    attachments=[
                        PayloadAttachment(**dict(a)) for a in stored_attachments
                    ]
                ).model_dump(mode='json')
            await self.ledger.send(
                msg=msg,
                states={msg.uid: msg.status.status},
                atomic=atomic
            )
            msgs = await self.ledger.load_deposits(
                aggregate=True, uid=msg.uid
            )
            if msgs:
                msg = msgs[0]
                return self._msg2deposit_entity(msg)
            else:
                return None

    @action(
        methods=['GET', 'POST'],
        detail=False, url_path='deposit',
        resource=MassPaymentAssetsResource.DepositResource
    )
    async def deposit_many(
        self, data: MassPaymentAssetsResource.DepositResource.Create = None,
        **filters
    ) -> Optional[
        Union[
            List[MassPaymentAssetsResource.DepositResource.Retrieve],
            MassPaymentAssetsResource.DepositResource.Retrieve,
            HttpResponse
        ]
    ]:
        my_role = self.context.merchant.meta.mass_payments.ledger.role_by_did(
            did=self.identity.did.root
        )
        if not my_role:
            return HttpResponseForbidden()

        msg_kwargs = {
            'utc': datetime.utcnow(),
            'type': 'deposit'
        }
        if data:
            msg_kwargs['uid'] = data.uid or uuid.uuid4().hex
        if self.method in ['POST', 'PUT']:
            assets = await self._read_assets(self.context.merchant)
        else:
            assets = None

        if self.method == 'GET':
            msgs = await self.ledger.load_deposits(aggregate=True, **filters)
            self.metadata.total_count = len(msgs)
            return [self._msg2deposit_entity(msg) for msg in reversed(msgs)]
        elif self.method == 'POST':
            if my_role != 'owner':
                return HttpResponseForbidden()
            if data.amount is None or data.amount < 0:
                return HttpResponseBadRequest(content='amount invalid'.encode())

            pay_settings = await self._read_assets(self.context.merchant)

            msg = MassPaymentMicroLedger.Message(
                transaction=mass_payment.PaymentTransaction(
                    order_id=msg_kwargs['uid'],
                    amount=data.amount,
                    currency=assets.ratios.quote,
                    address=pay_settings.address,
                    pay_method_code=pay_settings.code
                ),
                **msg_kwargs
            )
            if data.attachments:
                stored_attachments = await self._attachments(
                    data=data.attachments, mute_data=True
                )
                msg.status.payload = PayloadAttachments(
                    attachments=[
                        PayloadAttachment(**dict(a)) for a in stored_attachments
                    ]
                ).model_dump(mode='json')

            await self.ledger.send(
                msg=msg,
                states={msg_kwargs['uid']: msg.status.status}
            )
            msgs = await self.ledger.load_deposits(
                aggregate=True, uid=msg_kwargs['uid']
            )
            if msgs:
                msg = msgs[0]
                return self._msg2deposit_entity(msg)
            else:
                return None

    @action(
        methods=['GET'],
        detail=True, url_path='history', resource=StatusResource
    )
    async def status_history(
        self, pk, **filters
    ) -> Optional[List[StatusResource.Retrieve]]:
        msg = await self._load_payment_msg(pk)
        if msg:
            history = await self._read_status_history(msg.uid)
            return history
        else:
            return None

    @action(
        methods=['GET'], detail=True, url_path='file'
    )
    async def file(self, pk: Any, **filters):
        _, loaded = await self.ledger.load(
            status='attachment', sort='desc',
            payload__status__payload__uid=pk
        )
        if loaded:
            msg = loaded[0]
            e = AttachmentsResource.Create.model_validate(msg.status.payload)
            if e.data.startswith('data:') and 'base64' in e.data[:512]:
                header, encoded = e.data.split("base64,", 1)
                binaries = base64.b64decode(encoded)
            else:
                try:
                    binaries = base64.b64decode(e.data)
                except Exception:
                    binaries = e.data.encode()
            if e.mime_type:
                self.metadata.content_type = e.mime_type
            if e.name:
                self.metadata.content_name = 'attachment; filename=' + e.name
            return HttpResponse(content=binaries, content_type=e.mime_type)
        else:
            return None

    @action(
        methods=['GET', 'POST'], detail=False,
        url_path='attachments', resource=AttachmentsResource
    )
    async def attachments(
        self,
        data: Union[AttachmentsResource.Create, List[AttachmentsResource.Create]] = None,  # noqa
        limit: int = None,
        offset: int = None, **filters
    ) -> Optional[
        Union[
            AttachmentsResource.Retrieve, List[AttachmentsResource.Retrieve]
        ]
    ]:
        return await self._attachments(
            data=data, limit=limit, offset=offset, **filters
        )

    async def _read_order_status_many(
        self, order_by: Any = 'id', limit: int = None,
        offset: Any = None, **filters
    ) -> List[StatusResource.Retrieve]:
        total, orders = await self.ledger.load_payments(
            limit=limit, offset=offset, **filters
        )
        self.metadata.total_count = total
        if orders:
            return [
                self._cast_storage_item_to_status(o) for o in orders
            ]
        else:
            return []

    async def _load_payment_msg(
        self, pk
    ) -> Optional[MassPaymentMicroLedger.Message]:
        _, orders = await self.ledger.load_payments(uid=pk)
        if not orders:
            _, orders = await self.ledger.load_payments(order_id=pk)
        return orders[0] if orders else None

    @classmethod
    async def _read_assets(
        cls, merchant: MerchantAccount
    ) -> MassPaymentAssetsResource.Retrieve:
        settings = await MassPaymentAssetsResource.read_settings(
            account=merchant
        )
        engine = GarantexEngine()
        ratio = await engine.ratio(
            base=merchant.meta.mass_payments.ratios.base,
            quote=merchant.meta.mass_payments.ratios.quote
        )
        deposit, reserved = await MassPaymentAssetsResource.read_balances(
            merchant
        )
        return MassPaymentAssetsResource.Retrieve(
            webhook=settings.webhook,
            balance=deposit - reserved,
            deposit=deposit,
            reserved=reserved,
            code=merchant.meta.mass_payments.asset.code,
            address=merchant.meta.mass_payments.asset.address,
            ratios=AssetsRatios(
                engine=merchant.meta.mass_payments.ratios.engine.replace('Engine', ''),  # noqa
                base=merchant.meta.mass_payments.ratios.base,
                quote=merchant.meta.mass_payments.ratios.quote,
                ratio=round(ratio.ratio, 2) if ratio else None
            )
        )

    @classmethod
    def _cast_storage_item_to_status(
        cls, src: MassPaymentMicroLedger.Message, **extra
    ) -> StatusResource.Retrieve:
        ret = StatusResource.Retrieve(
            id=src.transaction.order_id,
            order_id=src.transaction.order_id,
            description=src.transaction.description,
            user=src.customer.identifier,
            amount=src.transaction.amount,
            currency=src.transaction.currency,
            type=src.status.type,
            status=src.status.status,
            error=src.status.error,
            sandbox=src.status.sandbox,
            earned=src.status.earned,
            response_code=src.status.response_code,
            utc=src.utc,
            payload=src.status.payload,
            message=src.status.message
        )
        for k, v in extra.items():
            setattr(ret, k, v)
        return ret

    async def _read_status_history(
        self, uid: str
    ) -> Optional[List[StatusResource.Retrieve]]:
        _, history = await self.ledger.load(uid=uid)
        if history:
            # первой записью всегда будет запись о создании
            first = history[0]
            created_rec = self._cast_storage_item_to_status(
                first, status='created'
            )
            history = history[1:]
            for i in history:
                if i.type == 'status':
                    i.transaction = first.transaction
                    i.customer = first.customer
            return [created_rec] + [
                self._cast_storage_item_to_status(i) for i in history
            ]
        else:
            return None

    async def _attachments(
        self,
        data: Union[AttachmentsResource.Create, List[AttachmentsResource.Create]] = None, # noqa
        limit: int = None,
        offset: int = None, mute_data: bool = False, **filters
    ) -> Optional[Union[AttachmentsResource.Retrieve, List[AttachmentsResource.Retrieve]]]:
        return_as_list = True
        loaded = []
        if not data:
            filters.pop('status', None)
            pk = filters.pop('pk', None)
            if pk:
                filters['payload__status__payload__uid__in'] = pk
            else:
                filters['payload__status__payload__attachments__isnull'] = True
            _, loaded = await self.ledger.load(
                limit=limit, offset=offset,
                status='attachment', **filters
            )
            if not loaded:
                return []
            result = []
            for msg in loaded:
                try:
                    a = AttachmentsResource.Retrieve.model_validate(
                        dict(**msg.status.payload, utc=msg.utc)
                    )
                except ValueError:
                    ...
                else:
                    if 'full' not in filters:
                        a.data = None
                    result.append(a)
            return result
        elif data:
            if isinstance(data, list):
                items = data
            else:
                items = [data]
                return_as_list = False

            msgs = self._attachments_to_messages(items)
            await self.ledger.send_batch(msgs)
            _, loaded = await self.ledger.load(
                status='attachment',
                payload__status__payload__uid__in=[i.uid for i in items],
                sort='desc'  # load last attachment
            )
            if not loaded:
                return None
        # Build response
        attachments = []
        uid_set = set()
        for msg in loaded:
            msg: MassPaymentMicroLedger.Message
            e = AttachmentsResource.Create.model_validate(msg.status.payload)
            if e.uid in uid_set:
                continue
            uid_set.add(e.uid)
            attachments.append(
                AttachmentsResource.Retrieve(
                    name=e.name,
                    data=None if mute_data else e.data,
                    mime_type=e.mime_type,
                    uid=e.uid,
                    utc=msg.utc
                )
            )
        if return_as_list:
            return attachments
        else:
            return attachments[0]

    async def _detailed_check_permission(self) -> bool:
        if isinstance(self.context.user, MerchantAccount):
            self.context.identity = self.context.user.meta.identity
            self.context.merchant = self.context.user
            settings = self.context.user.meta.mass_payments
            if settings.ledger is None:
                return False
            return settings.enabled and settings.ratios and settings.asset
        else:
            return False

    @classmethod
    def _attachments_to_messages(
        cls, items: List[AttachmentsResource.Create]
    ) -> List[MassPaymentMicroLedger.Message]:
        msgs = []
        for item in items:
            item: AttachmentsResource.Create
            if not item.uid:
                item.uid = uuid.uuid4().hex

            if not item.mime_type and item.data.startswith('data:') and 'base64' in item.data[:512]:  # noqa
                try:
                    header, encoded = item.data.split("base64,", 1)
                    item.mime_type = header.replace(';', '').split('data:')[-1]
                except Exception:
                    ...
            msgs.append(
                MassPaymentMicroLedger.Message(
                    uid=item.uid,
                    type='attachment',
                    status=mass_payment.PaymentStatus(
                        status='attachment',
                        payload=item.model_dump(mode='json')
                    )
                )
            )
        return msgs

    @classmethod
    def _msg2deposit_entity(
        cls, m: MassPaymentMicroLedger.Message,
    ) -> MassPaymentAssetsResource.DepositResource.Retrieve:
        attachments_container = None
        if m.status.payload:
            try:
                attachments_container = PayloadAttachments.model_validate(
                    m.status.payload
                )
            except ValueError:
                ...
        return MassPaymentAssetsResource.DepositResource.Retrieve(
            uid=m.uid,
            utc=m.utc,
            amount=m.transaction.amount,
            status=m.status.status,
            address=m.transaction.address,
            pay_method_code=m.transaction.pay_method_code,
            attachments=attachments_container.attachments if attachments_container else []
        )


class ControlPanelMassPaymentController(MassPaymentController):

    PERMISSIONS = {'*': Account.Permission.OPERATOR.value}
    EDITABLE_STATUSES = None

    async def before(self, *args, **kwargs):
        self.context.identity = self.context.config.identity
        self.context.merchant = await self._load_merchant(
            kwargs.pop('merchant')
        )

    async def create_one(
        self, data: MassPaymentResource.Create, **extra
    ):
        return HttpResponseForbidden()

    async def create_many(
        self, data: List[MassPaymentResource.Create], **extra
    ):
        return HttpResponseForbidden()

    @action(
        methods=['GET'], detail=True,
        url_path='history', resource=StatusResource
    )
    async def history(
        self, pk, data: StatusResource.Create = None, **filters
    ) -> Optional[Union[List[StatusResource.Retrieve], StatusResource.Retrieve, HttpResponse]]:  # noqa
        msg = await self._load_payment_msg(pk)
        if msg:
            if self.method == 'GET':
                return await self._read_status_history(msg.uid)
            else:
                return HttpResponseNotAllowed(permitted_methods=['GET'])
        else:
            return None

    @action(detail=True, url_path='status', resource=StatusResource)
    async def order_status(
        self, pk, **filters
    ) -> Optional[StatusResource.Retrieve]:
        msg = await self._load_payment_msg(pk)
        if msg:
            return self._cast_storage_item_to_status(msg)
        else:
            return None

    @action(
        methods=['GET'],
        detail=False, url_path='assets', resource=MassPaymentAssetsResource
    )
    async def assets(
        self, data: MassPaymentAssetsResource.Create = None, **filters
    ) -> Optional[MassPaymentAssetsResource.Retrieve]:
        return await self._read_assets(self.context.merchant)

    @action(
        methods=['GET'], detail=False, url_path='export'
    )
    async def export_to_external_system(self, **filters):
        _, payment_orders = await self.ledger.load_payments(
            status='processing'
        )
        engine = filters.get('engine')
        if engine == 'qugo':
            exporter = QugoRegistry(payments=payment_orders)
            binary = await exporter.export_to_buffer()
            self.metadata.content_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'  # noqa
            self.metadata.content_name = 'attachment; filename=' + 'Qugo Payment-registry.xlsx'  # noqa
            print('======== XXX =======')
            print(self.metadata.content_name)
            print('======================')
            return HttpResponse(
                content=binary, content_type=self.metadata.content_type
            )

    async def _detailed_check_permission(self) -> bool:
        if self.context.merchant is None:
            return False
        if self.context.merchant.meta.mass_payments is None:
            return False
        if self.context.merchant.meta.mass_payments.ledger is None:
            return False
        return True

    @classmethod
    async def _load_merchant(cls, merchant_id: str) -> MerchantAccount:
        accounts = await AccountRepository.get_merchants()
        for acc in accounts:
            if acc.uid == merchant_id or acc.meta.title == merchant_id or acc.meta.identity.did.root == merchant_id:  # noqa
                return acc
        raise Http404



