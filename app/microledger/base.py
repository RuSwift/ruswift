from abc import abstractmethod, ABC
from typing import List, Optional, Dict, Type, Tuple, Literal, Union

from pydantic import BaseModel, Field

from entities import Identity, AnonymousAccount, Ledger
from entities import MerchantMeta
from reposiroty import AtomicDelegator
from context import context


DID = str
ERR_MSG = str


class Transaction(BaseModel):
    issuer: DID
    signature: str
    ledger_id: str
    tags: List[str] = Field(default_factory=list)
    payload: Dict


class KeyValueState(BaseModel):
    ledger_id: str
    key: str
    value: str


class BaseConsensus(ABC):

    def __init__(self, me: DID, participants: List[DID]):
        self.me = me
        self.participants = [did for did in participants if did != me]

    @abstractmethod
    async def propagate(
        self, txns: List[Union[Transaction, KeyValueState]],
        atomic: AtomicDelegator = None
    ) -> Tuple[bool, Optional[ERR_MSG]]:
        ...

    @abstractmethod
    async def read(
        self, ledger_id: str, limit: int = None, offset: int = None,
        sort: Literal['asc', 'desc'] = 'asc', **filters
    ) -> Tuple[int, List[Transaction]]:
        ...

    @abstractmethod
    async def states(
        self, ledger_id: str,
        keys: List[str] = None, values: List[str] = None,
    ) -> List[KeyValueState]:
        ...


class BaseMicroLedger(ABC):

    ID: str
    Message: Type[BaseModel] = BaseModel

    def __init__(
        self, participants: List[DID],
        consensus_cls: Type[BaseConsensus],
        me: Optional[Identity] = None
    ):
        if me:
            self.identity = me
        else:
            if not context.user:
                raise RuntimeError(
                    'You must operate with microledgers in '
                    'auth context or Declare Me explicitly'
                )
            self.identity = self.get_identity()
        if self.identity is None:
            raise RuntimeError(
                'Identity is empty'
            )
        if self.identity.did.root not in participants:
            participants.append(self.identity.did.root)
        self.participants = list(set(participants))
        self.consensus = consensus_cls(
            me=self.identity.did.root,
            participants=self.participants
        )

    @classmethod
    def create_type_for(cls, id_: str) -> Type['BaseMicroLedger']:
        kwargs = {'ID': id_}
        return type(cls.__name__, (cls,), {**kwargs})

    @classmethod
    def create_from_ledger(
        cls, src: Ledger, me: Identity, consensus_cls: Type[BaseConsensus]
    ) -> Type['BaseMicroLedger']:
        factory_cls = cls.create_type_for(id_=src.id)
        participants = set()
        for role, members in src.participants.items():
            participants |= set(members)
        inst = factory_cls(
            participants=list(participants),
            consensus_cls=consensus_cls,
            me=me
        )
        return inst

    @abstractmethod
    async def send(self, msg: Message, atomic: AtomicDelegator = None):
        ...

    @abstractmethod
    async def send_batch(self, msgs: List[Message], atomic: AtomicDelegator = None):  # noqa
        ...

    @abstractmethod
    async def load(
        self, limit: int = None, offset: int = None,
        sort: Literal['asc', 'desc'] = 'asc', **filters
    ) -> Tuple[int, List[Message]]:
        ...

    @classmethod
    def get_identity(cls) -> Optional[Identity]:
        if not context.user:
            return None
        if isinstance(context.user, AnonymousAccount):
            return None
        if context.user.merchant_meta:
            m = MerchantMeta.model_validate(context.user.merchant_meta)
            return m.identity
        else:
            return context.config.identity
