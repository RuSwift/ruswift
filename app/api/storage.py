from datetime import datetime
from typing import Any, List, Optional, Dict

from pydantic import Field

from api.lib import BaseResource

from exchange.entities import Account
from exchange.api import BaseExchangeController, AuthControllerMixin
from exchange.reposiroty import StorageRepository


class StorageItemResource(BaseResource):

    pk = 'uid'

    class Create(BaseResource.Create):
        category: str
        tags: List[str] = Field(default_factory=list)
        payload: Dict

    class Update(Create):
        ...

    class Retrieve(Account):
        uid: str
        updated_at: Optional[datetime]
        created_at: Optional[datetime]


class StorageController(AuthControllerMixin, BaseExchangeController):

    Resource = StorageItemResource

    async def get_one(self, pk: Any, **filters) -> Optional[Resource.Retrieve]:
        e = await StorageRepository.get(uid=pk)
        if e:
            return StorageItemResource.Retrieve.model_validate(e)
        else:
            return None

    async def get_many(
        self, order_by: Any = 'id', limit: int = None,
        offset: int = None, **filters
    ) -> List[Resource.Retrieve]:
        total, many = await StorageRepository.get_many(
            order_by, limit, offset, **filters
        )
        self.metadata.total_count = total
        result: List[StorageItemResource.Retrieve] = []
        for e in many:
            result.append(
                StorageItemResource.Retrieve.model_validate(e)
            )
        return result
