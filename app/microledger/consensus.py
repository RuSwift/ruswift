import uuid
from typing import Tuple, List, Optional, Literal, Union

from exchange.models import StorageItem as DBStorageItem
from entities import StorageItem
from reposiroty import StorageRepository, AtomicDelegator
from .base import BaseConsensus, Transaction, ERR_MSG, DID, KeyValueState


class DatabasePaymentConsensus(BaseConsensus):

    class AtomicStatesOperations(AtomicDelegator):

        def __init__(
            self, me: DID, participants: List[DID],
            states: List[KeyValueState],
            chain: List[AtomicDelegator] = None
        ):
            self.members = [me] + participants
            self.states = states
            self.chain = chain or []

        def atomic(self,  *args, **kwargs):
            for state in self.states:
                state.ledger_id = f'{state.ledger_id}:states'
                for did in set(self.members):
                    DBStorageItem.objects.update_or_create(
                        defaults={
                            'uid': uuid.uuid4().hex,
                            'storage_id': did,
                            'category': state.ledger_id,
                            'storage_ids': self.members,
                            'signature': '<empty>',
                            'payload': state.model_dump(
                                mode='json', exclude={'ledger_id'}
                            )
                        },
                        category=state.ledger_id,
                        storage_id=did,
                        payload__key=state.key
                    )
                for atomic in self.chain:
                    atomic(*args, **kwargs)

    def __init__(self, me: DID, participants: List[DID]):
        super().__init__(me, participants)

    async def propagate(
        self, txns: List[Union[Transaction, KeyValueState]],
        atomic: AtomicDelegator = None
    ) -> Tuple[bool, Optional[ERR_MSG]]:
        items = []
        for txn in [i for i in txns if isinstance(i, Transaction)]:
            items.extend(self._build_storage_items(txn))
        try:
            atomic = self.AtomicStatesOperations(
                me=self.me,
                participants=self.participants,
                states=[i for i in txns if isinstance(i, KeyValueState)],
                chain=[atomic] if atomic else None
            )
            await StorageRepository.create_many(
                entities=items, atomic=atomic
            )
        except Exception as e:
            return False, str(e)
        else:
            return True, None

    async def read(
        self, ledger_id: str, limit: int = None, offset: int = None,
        sort: Literal['asc', 'desc'] = 'asc', **filters
    ) -> Tuple[int, List[Transaction]]:
        filters['storage_id'] = self.me
        if sort == 'asc':
            order_by = 'pk'
        else:
            order_by = '-pk'
        count, items = await StorageRepository.get_many(
            order_by=order_by, limit=limit, offset=offset,
            category=ledger_id, **filters
        )
        txns = []
        for item in items:
            item: StorageItem
            txn = Transaction(
                issuer=item.storage_id,
                ledger_id=item.category,
                tags=item.tags,
                payload=item.payload,
                signature=item.signature
            )
            txns.append(txn)
        return count, txns

    async def states(
        self, ledger_id: str,
        keys: List[str] = None, values: List[str] = None,
    ) -> List[KeyValueState]:
        filters = {}
        if values:
            filters['payload__value__in'] = values
        if keys:
            filters['payload__key__in'] = keys
        filters['storage_id'] = self.me
        filters['category'] = f'{ledger_id}:states'
        queryset = DBStorageItem.objects.filter(**filters)
        result = []
        async for m in queryset.all():
            d = dict(
                ledger_id=m.category.split(':')[0],
                **m.payload
            )
            result.append(KeyValueState.model_validate(d))
        return result

    def _build_storage_items(self, txn: Transaction) -> List[StorageItem]:
        items: List[StorageItem] = []
        members = [self.me] + self.participants
        for did in set(members):
            item = StorageItem(
                storage_id=did,
                category=txn.ledger_id,
                payload=txn.payload,
                tags=txn.tags,
                signature=txn.signature,
                storage_ids=members
            )
            items.append(item)
        return items
