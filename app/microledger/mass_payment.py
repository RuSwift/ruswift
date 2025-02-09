from datetime import datetime
from typing import List, Tuple, Optional, Union, Literal, Any, Dict

from pydantic import BaseModel, Field, model_validator

from entities import mass_payment
from reposiroty import AtomicDelegator
from .base import BaseMicroLedger, Transaction, KeyValueState


class MassPaymentMicroLedger(BaseMicroLedger):

    ID = 'mass-payment'

    class PayOutMessage(BaseModel):
        uid: str
        type: Literal['payout', 'status', 'attachment', 'deposit'] = 'payout'
        transaction: Optional[mass_payment.PaymentTransaction] = None
        customer: Optional[mass_payment.PaymentCustomer] = None
        card: Optional[mass_payment.PaymentCard] = None
        proof: Optional[mass_payment.Proof] = None
        status: Optional[mass_payment.PaymentStatus] = Field(
            default_factory=mass_payment.PaymentStatus
        )
        utc: Optional[datetime] = None

        @model_validator(mode='after')
        @classmethod
        def check_card_number_omitted(cls, data: Any) -> Any:
            type_ = getattr(data, 'type')
            expected_attrs = []
            if type_ == 'payout':
                expected_attrs = ['transaction', 'customer', 'card']
            elif type_ == 'status':
                expected_attrs = ['status']
            elif type_ == 'attachment':
                expected_attrs = ['status']
            for attr in expected_attrs:
                val = getattr(data, attr)
                if not val:
                    raise ValueError(f'Attr "{attr}" is empty')
            return data

    Message = PayOutMessage

    async def send(
        self, msg: Message,
        states: Dict[str, str] = None, atomic: AtomicDelegator = None
    ):
        await self.send_batch(msgs=[msg], states=states, atomic=atomic)

    async def send_batch(
        self, msgs: List[Message],
        states: Dict[str, str] = None, atomic: AtomicDelegator = None
    ):
        txns = [self._build_txn(msg) for msg in msgs] + self._build_state_txns(states)
        ok, err = await self.consensus.propagate(
            txns=txns, atomic=atomic
        )
        if not ok:
            raise RuntimeError(err)

    async def load(
        self, limit: int = None, offset: int = None,
        order_id: Union[str, List[str]] = None, identifier: str = None,
        status: Union[str, List[str]] = None, type_: str = None,
        uid: Union[str, List[str]] = None, sort: Literal['asc', 'desc'] = 'asc',
        **filters
    ) -> Tuple[int, List[Message]]:
        if type_:
            filters['payload__type'] = type_
        if order_id is not None:
            if isinstance(order_id, list):
                filters['payload__transaction__order_id__in'] = order_id
            else:
                filters['payload__transaction__order_id'] = order_id
        if identifier is not None:
            filters['payload__customer__identifier'] = identifier
        if uid is not None:
            if isinstance(uid, list):
                filters['payload__uid__in'] = uid
            else:
                filters['payload__uid'] = uid
        if status is not None:
            if isinstance(status, list):
                filters['payload__status__status__in'] = status
            else:
                filters['payload__status__status'] = status
        filters['ledger_id'] = self.ID

        count, txns = await self.consensus.read(
            limit=limit, offset=offset, sort=sort, **filters
        )
        msgs = []
        for txn in txns:
            msgs.append(
                self.Message.model_validate(txn.payload)
            )
        return count, msgs

    async def load_payments(
        self, limit: int = None, offset: int = None,
        order_id: Union[str, List[str]] = None, identifier: str = None,
        uid: Union[str, List[str]] = None,
        sort: Literal['asc', 'desc'] = 'asc', **filters
    ) -> Tuple[int, List[Message]]:
        status = filters.pop('status', None)
        if status:
            if isinstance(status, str):
                status = [status]
            kvs = await self.consensus.states(
                ledger_id=self.ID, values=status
            )
            uid = uid or []
            uid += [i.key for i in kvs]
        count, payments = await self.load(
            limit=limit, offset=offset, order_id=order_id, uid=uid,
            identifier=identifier, type_='payout', sort=sort
        )
        _, statuses = await self.load(
            type_='status',
            status=['pending', 'processing', 'success', 'error'],
            uid=[p.uid for p in payments],
            sort='desc'
        )
        status_map = {}
        for s in statuses:
            if s.uid not in status_map:
                # запишем только самые свежие
                status_map[s.uid] = s.status
        for p in payments:
            if p.uid in status_map:
                p.status = status_map[p.uid]
        return count, payments

    async def load_deposits(
        self, aggregate: bool, **filters
    ) -> List[Message]:
        filters['type_'] = 'deposit'
        filters['sort'] = 'asc'
        status = filters.pop('status', None)
        if status:
            if isinstance(status, str):
                status = [status]
            kvs = await self.consensus.states(
                ledger_id=self.ID, values=status
            )
            uid = filters.get('uid') or []
            if isinstance(uid, str):
                uid = [uid]
            uid += [i.key for i in kvs]
            filters['uid'] = uid
        _, msgs = await self.load(**filters)
        if aggregate:
            map_ = {}
            attachments_ = {}
            result = []
            for msg in msgs:
                if msg.status.payload and 'attachments' in msg.status.payload:
                    atts = msg.status.payload['attachments']
                else:
                    atts = []
                if msg.uid not in map_:
                    map_[msg.uid] = msg
                    attachments_[msg.uid] = atts
                    result.append(msg)
                else:
                    map_[msg.uid].status = msg.status
                    map_[msg.uid].transaction = msg.transaction
                    attachments_[msg.uid].extend(atts)
                    if attachments_[msg.uid]:
                        pld = map_[msg.uid].status.payload or {}
                        pld['attachments'] = attachments_[msg.uid]
                        map_[msg.uid].status.payload = pld

            return result
        else:
            return msgs

    async def load_states(
        self,
        keys: List[str] = None, values: List[str] = None,
    ) -> List[KeyValueState]:
        kvs = await self.consensus.states(
            ledger_id=self.ID, keys=keys, values=values
        )
        return kvs
        
    def _build_txn(self, msg: Message) -> Transaction:
        if msg.utc is None:
            msg = msg.copy()
            msg.utc = datetime.utcnow()
        tags = []
        if msg.type == 'payout':
            for tag in [msg.transaction.order_id,
                        msg.transaction.currency,
                        msg.customer.identifier,
                        msg.customer.email,
                        msg.customer.phone,
                        msg.card.number
                        ]:
                if tag:
                    tags.append(str(tag).lower())
        return Transaction(
            issuer=self.identity.did.root,
            signature='<empty>',
            ledger_id=self.ID,
            tags=tags,
            payload=msg.model_dump(mode='json')
        )

    def _build_state_txns(self, states: Dict[str, str]) -> List[KeyValueState]:
        if not states:
            return []
        txns = []
        for k, v in states.items():
            txn = KeyValueState(
                ledger_id=self.ID,
                key=k,
                value=v
            )
            txns.append(txn)
        return txns
