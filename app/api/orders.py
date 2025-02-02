import uuid
from datetime import datetime
from typing import Literal, Any, List, Optional, Union, Callable

from django.http import (
    HttpResponseForbidden, HttpResponse, HttpResponseBadRequest,
    HttpRequest
)

from api.lib import BaseResource, MethodMapping, action
from api.lib.mixins import MixinCreateOne
from pydantic import BaseModel, Field

from exchange.core import utc_now_float
from exchange.entities import (
    Order, PaymentDetails, CardDetails, Ledger, Account, PaymentRequest,
    MerchantAccount
)
from exchange.reposiroty import (
    LedgerRepository, AccountRepository, StorageRepository
)
from exchange.api import BaseExchangeController, AuthControllerMixin
from exchange.microledger import (
    MassPaymentMicroLedger, DatabasePaymentConsensus,
    PaymentRequestMicroLedger
)


class BatchLedgerMeta(BaseModel):
    id: str
    api: str
    role: str
    title: str


class Attachment(BaseModel):
    uid: str
    name: str
    mime_type: Optional[str] = None


class Deposit(BaseModel):
    uid: str
    utc: Optional[datetime]
    amount: float
    currency: str
    address: Optional[str] = None
    pay_method_code: Optional[str] = None
    attachments: List[dict] = Field(default_factory=list)


class Batch(BaseModel):
    orders: List[Order]
    ledger: Optional[BatchLedgerMeta] = None
    attachments: List[Attachment] = Field(default_factory=list)
    deposits: List[Deposit] = Field(default_factory=list)


class PayloadAttachmentsSchema(BaseModel):
    attachments: List[Attachment]


class OrderResource(BaseResource):

    pk = 'id'

    class Common(BaseResource.Create):
        ...

    class Create(Common):
        type: Literal['mass-payment', 'simple', 'payment-request'] = 'simple'
        order: Optional[Order] = None
        batch: Optional[Batch] = None
        payment_request: Optional[PaymentRequest] = None

    class Update(Common):
        ...

    class Retrieve(Update, Create):
        id: str


class OrderStatus(BaseResource):

    pk = 'id'

    class Create(BaseResource.Create):
        id: str
        type: Literal['payment-request']
        status: Optional[str] = None
        details: Optional[PaymentDetails] = None

    class Update(Create):
        ...

    class Retrieve(Update):
        payment_request: Optional[PaymentRequest] = None


class OrderController(
    AuthControllerMixin,
    MixinCreateOne,
    BaseExchangeController
):

    Resource = OrderResource
    _min_order_value = 4500

    async def get_one(self, pk: Any, **filters) -> Optional[Resource.Retrieve]:
        res = await self.get_many()
        for i in res:
            if i.id == pk:
                return self.Resource.Retrieve.model_validate(dict(i))
        return None

    async def get_many(
        self, order_by: Any = 'id', limit: int = None,
        offset: int = None, **filters
    ) -> List[Resource.Retrieve]:
        result = []
        type_ = filters.get('type')
        if isinstance(type_, str):
            type_ = [type_]
        uid = filters.get('uid')
        if isinstance(uid, str):
            uid = [uid]
        if not type_:
            type_ = ['payments', 'payment-request']
        # Сначала запросим mass-payments
        if self.identity:
            # 1. Mass payments
            if 'payments' in type_:
                mass_payment_ledgers = await LedgerRepository.load(
                    self.identity, tag='payments'
                )
            else:
                mass_payment_ledgers = []
            for ledger in mass_payment_ledgers:
                if 'payments' in ledger.tags:
                    dlt: MassPaymentMicroLedger = MassPaymentMicroLedger.create_from_ledger(  # noqa
                        src=ledger, me=self.identity,
                        consensus_cls=DatabasePaymentConsensus
                    )
                    _, payment_orders = await dlt.load_payments(
                        status='processing'
                    )
                    _, statuses = await dlt.load(
                        uid=[p.uid for p in payment_orders]
                    )
                    if ledger.role_by_did(self.identity.did.root) == 'processing':
                        pending_deposits = await dlt.load_deposits(
                            aggregate=True, status='pending'
                        )
                    else:
                        pending_deposits = []
                    attachments = []
                    attachments_ids = set()
                    for p in payment_orders + statuses:
                        try:
                            container = PayloadAttachmentsSchema.model_validate(p.status.payload)
                            for a in container.attachments:
                                if a.uid not in attachments_ids:
                                    attachments.append(a)
                                    attachments_ids.add(a.uid)
                        except Exception:
                            pass
                    batch_deposits = []
                    for msg in pending_deposits:
                        attachments_container = None
                        if msg.status.payload:
                            try:
                                attachments_container = PayloadAttachmentsSchema.model_validate(
                                    msg.status.payload
                                )
                            except ValueError:
                                ...
                        if attachments_container:
                            deposit_attachments = [
                                a.model_dump(mode='json')
                                for a in attachments_container.attachments
                            ]
                        else:
                            deposit_attachments = []
                        dep = Deposit(
                            uid=msg.uid,
                            utc=msg.utc,
                            amount=msg.transaction.amount,
                            currency=msg.transaction.currency,
                            address=msg.transaction.address,
                            pay_method_code=msg.transaction.pay_method_code,
                            attachments=deposit_attachments
                        )
                        batch_deposits.append(dep)

                    if payment_orders or batch_deposits:
                        result.append(
                            self.Resource.Retrieve(
                                id=ledger.id,
                                type='mass-payment',
                                batch=Batch(
                                    orders=[
                                        self._cast_dlt_msg_to_order(
                                            src=msg
                                        ) for msg in payment_orders
                                    ],
                                    ledger=await self._load_batch_ledger_meta(ledger),  # noqa
                                    attachments=attachments,
                                    deposits=batch_deposits
                                )
                            )
                        )
            # 2. Payment Request
            if 'payment-request' in type_:
                ledger_filters = {}
                if uid:
                    dlt_id = []
                    for s in uid:
                        dlt_cls = PaymentRequestMicroLedger.create_type_for(s)
                        dlt_id.append(dlt_cls.ID)
                    ledger_filters_uid = dlt_id
                else:
                    ledger_filters_uid = []

                status = filters.get('status')
                if not status:
                    status = [
                        'created', 'linked', 'ready', 'wait', 'payed',
                        'checking', 'dispute'
                    ]
                if status:
                    ledger_filters_status = await PaymentRequestMicroLedger.fetch_ledger_ids(
                        me=self.identity, status=status
                    )
                else:
                    ledger_filters_status = []

                ledger_filters['id_'] = None
                if ledger_filters_uid:
                    if ledger_filters_status:
                        ledger_filters['id_'] = list(set(ledger_filters_uid).intersection(set(ledger_filters_status)))  # noqa
                    else:
                        ledger_filters['id_'] = ledger_filters_uid
                elif ledger_filters_status:
                    ledger_filters['id_'] = ledger_filters_status
                payment_requests_ledgers = await LedgerRepository.load(
                    self.identity, tag='payment-request', **ledger_filters
                )
            else:
                payment_requests_ledgers = []
            for ledger in payment_requests_ledgers:
                dlt: PaymentRequestMicroLedger = self._get_payment_request_dlt(ledger)  # noqa
                order = await dlt.contract.fetch()
                result.append(
                    OrderResource.Retrieve(
                        id=dlt.ledger_id(),
                        type='payment-request',
                        payment_request=order
                    )
                )
        return result

    async def create_one(
        self, data: Resource.Create, **extra
    ) -> Union[Resource.Retrieve, HttpResponse]:
        id_counter_category = self.__class__.__name__ + ':' + 'payment-requests-order-id-gen'  # noqa
        if data.type == 'payment-request':
            order_uid = uuid.uuid4().hex
            dlt = await self._create_payment_request_dlt_instance(
                order_uid=order_uid
            )
            order = PaymentRequest(**data.payment_request.model_dump())
            e = await StorageRepository.create(
                uid=uuid.uuid4().hex,
                category=id_counter_category,
                payload={}
            )
            order.uid = order_uid
            order.id = str(e.id + self._min_order_value)
            order.created = utc_now_float()
            await dlt.contract.create(order)
            resp = self.Resource.Retrieve(
                id=dlt.ledger_id(),
                **data.model_dump()
            )
            resp.payment_request = order
            return resp
        else:
            return HttpResponse(
                status=400,
                content='Invalid type'.encode()
            )

    @action(
        detail=False, url_path='link',
        methods=['POST'], resource=OrderStatus
    )
    async def link(
        self, data: OrderStatus.Create, **filters
    ) -> Union[OrderStatus.Retrieve, HttpResponse, None]:
        try:
            if data.type == 'payment-request':
                ledgers = await LedgerRepository.load(
                    identity=self.identity, id_=data.id
                )
                if ledgers:
                    ledger = ledgers[0]
                    dlt = self._get_payment_request_dlt(ledger)
                    request = await dlt.contract.link_client(self.context.user.uid)
                    return OrderStatus.Retrieve(
                        id=data.id,
                        type=data.type,
                        payment_request=request
                    )
                else:
                    return None
            else:
                return HttpResponseBadRequest(
                    content='Unsupported type'.encode()
                )
        except ValueError as e:
            err = e.args[0] if e.args else str(e)
            return HttpResponseBadRequest(content=err.encode())

    @action(
        detail=False, url_path='status',
        methods=['GET', 'POST'], resource=OrderStatus
    )
    async def status(
        self, data: OrderStatus.Create, **filters
    ) -> Union[Resource.Retrieve, HttpResponse, None]:
        try:
            if data.type == 'payment-request':
                ledgers = await LedgerRepository.load(
                    identity=self.identity, id_=data.id
                )
                if ledgers:
                    ledger = ledgers[0]
                    dlt = self._get_payment_request_dlt(ledger)
                    if data.status == 'ready':
                        request = await dlt.contract.mark_ready()
                    elif data.status == 'wait':
                        request = await dlt.contract.wait_payment(data.details)
                    elif data.status == 'payed':
                        request = await dlt.contract.mark_payed()
                    elif data.status == 'checking':
                        request = await dlt.contract.mark_checking()
                    elif data.status == 'dispute':
                        request = await dlt.contract.mark_dispute()
                    elif data.status == 'done':
                        request = await dlt.contract.mark_done()
                    elif data.status == 'declined':
                        request = await dlt.contract.mark_declined()
                    else:
                        return HttpResponseBadRequest(
                            content=f'Unsupported status "{data.status}"'.encode()
                        )

                    return OrderStatus.Retrieve(
                        id=data.id,
                        type=data.type,
                        payment_request=request
                    )
                else:
                    return None
            else:
                return HttpResponseBadRequest(
                    content='Unsupported type'.encode()
                )
        except ValueError as e:
            err = e.args[0] if e.args else str(e)
            return HttpResponseBadRequest(content=err.encode())

    async def check_permission(
        self, request: HttpRequest, handler: Union[Callable, MethodMapping]
    ) -> bool:
        if isinstance(handler, MethodMapping):
            method_name = handler.func_name
        else:
            method_name = handler.__func__.__name__
        if method_name in ['status', 'link']:
            success = True
        else:
            success = await super().check_permission(request, handler)
        if success:
            if Account.Permission.ROOT.value in self.context.user.permissions:
                return True
            if method_name == 'create_one':
                superset = {
                    Account.Permission.MERCHANT.value,
                    Account.Permission.OPERATOR.value
                }
                i = superset.intersection(self.context.user.permissions)
                return i != {}
            elif method_name == 'status':
                return True
            else:
                return True
        else:
            return False

    async def _load_batch_ledger_meta(
        self, ledger: Ledger
    ) -> Optional[BatchLedgerMeta]:
        kwargs = {
            'id': ledger.id,
            'role': ledger.role_by_did(self.identity.did.root)
        }
        owners = ledger.participants_by_role('owner')
        if not owners:
            return None
        owner_did = owners[0]
        account: Account = await AccountRepository.get(did=owner_did)
        if account:
            if account.merchant_meta:
                kwargs['title'] = account.merchant_meta.get('title')
            else:
                kwargs['title'] = account.first_name + account.last_name
            kwargs['title'] = kwargs['title'] or account.uid
        else:
            kwargs['title'] = owner_did
        if kwargs['role'] == 'owner':
            kwargs['api'] = '/api/mass-payments'
        else:
            kwargs['api'] = f'/api/control-panel/{owner_did}/mass-payments'
        return BatchLedgerMeta(**kwargs)

    @classmethod
    def _cast_dlt_msg_to_order(
        cls, src: MassPaymentMicroLedger.Message
    ) -> Order:
        return Order(
            id=src.transaction.order_id,
            uid=src.uid,
            customer=src.customer.identifier,
            description=src.transaction.description,
            amount=src.transaction.amount,
            currency=src.transaction.currency,
            details=PaymentDetails(
                card=CardDetails(
                    number=src.card.number,
                    holder=src.customer.display_name,
                    expiration_date=src.card.expiration_date
                )
            )
        )

    async def _create_payment_request_dlt_instance(
        self, order_uid: str
    ) -> PaymentRequestMicroLedger:
        # update ledgers linked to participants
        participants = {
            'processing': [self.context.config.identity.did.root]
        }
        if isinstance(self.context.user, MerchantAccount):
            owner = self.context.user.meta.identity.did.root
        else:
            owner = self.context.config.identity.did.root
        participants['owner'] = [owner]

        dlt_cls = PaymentRequestMicroLedger.create_type_for(uid=order_uid)
        ledger = Ledger(
            id=dlt_cls.ID,
            tags=['payment-request'],
            participants=participants
        )
        await LedgerRepository.ensure_exists(
            identity=self.identity, ledgers=[ledger]
        )
        # build DLT instance
        dlt = dlt_cls.create_from_ledger(
            src=ledger, me=self.identity,
            consensus_cls=DatabasePaymentConsensus
        )
        return dlt

    def _get_payment_request_dlt(self, ledger: Ledger) -> PaymentRequestMicroLedger:
        dlt_cls = PaymentRequestMicroLedger.create_type_for(
            uid=ledger.id
        )
        dlt: PaymentRequestMicroLedger = dlt_cls.create_from_ledger(
            src=ledger, me=self.identity,
            consensus_cls=DatabasePaymentConsensus
        )
        return dlt
