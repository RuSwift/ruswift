from typing import Any, List, Optional

from lib import BaseResource

from entities import Ledger, MerchantAccount
from reposiroty import LedgerRepository
from api import BaseExchangeController, AuthControllerMixin
from context import context


class LedgerResource(BaseResource):

    pk = 'id'

    class Create(BaseResource.Create):
        ...

    class Update(Create):
        ...

    class Retrieve(Update, Ledger):
        ...


class LedgerController(AuthControllerMixin, BaseExchangeController):

    Resource = LedgerResource

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
        ledgers = await LedgerRepository.load(self.identity)
        result = []
        for ledger in ledgers:
            result.append(
                self.Resource.Retrieve.model_validate(dict(ledger))
            )
        return result
