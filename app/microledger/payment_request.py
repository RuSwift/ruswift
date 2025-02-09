from typing import Literal, Tuple, List, Type, Optional, Union

from entities import (
    BaseEntity, PaymentRequest, StorageItem, PaymentDetails, Identity
)
from core import utc_now_float
from .base import BaseMicroLedger, Transaction, KeyValueState
from reposiroty import AtomicDelegator, StorageRepository


class PaymentRequestMicroLedger(BaseMicroLedger):

    ID = 'payment-request'
    Message = BaseEntity

    @classmethod
    def create_type_for(
        cls, uid: str = None, **kwargs
    ) -> Type['PaymentRequestMicroLedger']:
        if uid:
            prefix = cls.ID + ':'
            if not uid.startswith(prefix):
                uid = prefix + uid
            kwargs = {'ID': uid}
        return type(cls.__name__, (cls,), {**kwargs})

    @classmethod
    async def fetch_ledger_ids(
        cls, me: Identity, status: Union[str, List[str]] = None
    ) -> List[str]:
        filters = {}
        if status:
            if isinstance(status, str):
                filters['payload__status'] = status
            elif isinstance(status, list):
                filters['payload__status__in'] = status
        count, entities = await StorageRepository.get_many(
            storage_id=me.did.root,
            tag='payment_request',
            **filters
        )
        entities: List[StorageItem]
        return [e.category for e in entities]

    def ledger_id(self) -> str:
        if self.ID == PaymentRequestMicroLedger.ID:
            raise RuntimeError(
                'DLT for mass payments must have unique ID, '
                'call `create_type_for` constructor'
            )
        return self.ID

    @property
    def contract(self) -> 'PaymentRequestContract':
        return PaymentRequestContract(self)

    async def send(self, msg: Message, atomic: AtomicDelegator = None):
        raise NotImplemented(
            'Реализуем позже, когда дойдем до необходимости'
        )

    async def send_batch(
        self, msgs: List[Message], atomic: AtomicDelegator = None
    ):
        raise NotImplemented(
            'Реализуем позже, когда дойдем до необходимости'
        )

    async def load(
        self, limit: int = None, offset: int = None,
        sort: Literal['asc', 'desc'] = 'asc', **filters
    ) -> Tuple[int, List[Message]]:
        raise NotImplemented(
            'Реализуем позже, когда дойдем до необходимости'
        )


class PaymentRequestContract:

    def __init__(self, dlt: PaymentRequestMicroLedger):
        self.__dlt = dlt

    async def create(self, order: PaymentRequest):
        # TODO: это должно уйти в consensus.propagate
        entities = []
        for did in self.__dlt.participants:
            entity = StorageItem(
                storage_id=did,
                category=self.__dlt.ledger_id(),
                tags=['payment_request'],
                signature='<empty>',
                storage_ids=self.__dlt.participants,
                payload=order.model_dump(mode='json'),
            )
            entities.append(entity)

        await StorageRepository.create_many(entities=entities)

    async def fetch(self, raise_error: bool = False) -> Optional[PaymentRequest]:
        # TODO: это должно уйти в consensus.propagate
        entity: StorageItem = await StorageRepository.get(
            **self._build_storage_kwargs()
        )
        if entity:
            resp = PaymentRequest.model_validate(entity.payload)
            return resp
        else:
            if raise_error:
                raise ValueError('Data not exists')
            return None

    async def link_client(self, client_id) -> PaymentRequest:
        # TODO: это должно уйти в consensus.propagate
        order = await self.fetch(raise_error=True)
        if order.linked_client:
            raise ValueError(
                f'К этому ордеру уже прикреплен клиент {order.linked_client}'
            )
        order.linked_client = client_id
        order.status = 'linked'
        await self._update_for_all_participants(order)
        new_order = await self.fetch()
        return new_order

    async def mark_ready(self) -> PaymentRequest:
        # TODO: это должно уйти в consensus.propagate
        order = await self.fetch(raise_error=True)
        avail_statuses = ['linked']
        new_status = 'ready'
        if order.status in avail_statuses:
            order.status = new_status
        else:
            raise ValueError(
                f'Допустимые состояния для "{new_status}" - [{avail_statuses}]'
            )
        await self._update_for_all_participants(order)
        new_order = await self.fetch()
        return new_order

    async def wait_payment(self, details: PaymentDetails):
        # TODO: это должно уйти в consensus.propagate
        order = await self.fetch(raise_error=True)
        avail_statuses = ['ready']
        new_status = 'wait'
        if order.status in avail_statuses:
            if not details:
                raise ValueError(
                    f'Не заданы платежные реквизиты'
                )
            if not details.payment_ttl:
                raise ValueError(
                    f'Не указан таймаут жизни реквизитов'
                )
            order.details = details
            order.details.active_until = utc_now_float() + details.payment_ttl
            order.status = new_status
        else:
            raise ValueError(
                f'Допустимые состояния для "{new_status}" - [{avail_statuses}]'
            )
        await self._update_for_all_participants(order)
        new_order = await self.fetch()
        return new_order

    async def mark_payed(self):
        # TODO: это должно уйти в consensus.propagate
        order = await self.fetch(raise_error=True)
        avail_statuses = ['wait']
        new_status = 'payed'
        if order.status in avail_statuses:
            order.status = new_status
        else:
            raise ValueError(
                f'Допустимые состояния для "{new_status}" - [{avail_statuses}]'
            )
        await self._update_for_all_participants(order)
        new_order = await self.fetch()
        return new_order

    async def mark_checking(self):
        # TODO: это должно уйти в consensus.propagate
        order = await self.fetch(raise_error=True)
        avail_statuses = ['payed']
        new_status = 'checking'
        if order.status in avail_statuses:
            order.status = new_status
        else:
            raise ValueError(
                f'Допустимые состояния для "{new_status}" - [{avail_statuses}]'
            )
        await self._update_for_all_participants(order)
        new_order = await self.fetch()
        return new_order

    async def mark_done(self):
        # TODO: это должно уйти в consensus.propagate
        order = await self.fetch(raise_error=True)
        avail_statuses = ['checking', 'dispute']
        new_status = 'done'
        if order.status in avail_statuses:
            order.status = new_status
        else:
            raise ValueError(
                f'Допустимые состояния для "{new_status}" - [{avail_statuses}]'
            )
        await self._update_for_all_participants(order)
        new_order = await self.fetch()
        return new_order

    async def mark_declined(self):
        # TODO: это должно уйти в consensus.propagate
        order = await self.fetch(raise_error=True)
        avail_statuses = ['dispute']
        new_status = 'declined'
        if order.status in avail_statuses:
            order.status = new_status
        else:
            raise ValueError(
                f'Допустимые состояния для "{new_status}" - [{avail_statuses}]'
            )
        await self._update_for_all_participants(order)
        new_order = await self.fetch()
        return new_order

    async def mark_dispute(self):
        # TODO: это должно уйти в consensus.propagate
        order = await self.fetch(raise_error=True)
        new_status = 'dispute'
        order.status = new_status
        await self._update_for_all_participants(order)
        new_order = await self.fetch()
        return new_order

    def _build_storage_kwargs(self) -> dict:
        return dict(
            storage_id=self.__dlt.identity.did.root,
            category=self.__dlt.ledger_id(),
            tag='payment_request'
        )

    async def _update_for_all_participants(self, order: PaymentRequest):
        # TODO: должно уйти в consensus.propagate
        kwargs = self._build_storage_kwargs()
        kwargs.pop('storage_id')
        kwargs['payload__uid'] = order.uid
        count, entities = await StorageRepository.get_many(
            storage_id__in=self.__dlt.participants,
            **kwargs
        )

        for entity in entities:
            entity: StorageItem
            entity.payload = order.model_dump(mode='json')
            e = await StorageRepository.update(
                e=entity,
                storage_id=entity.storage_id,
                **kwargs,
            )
        return True
