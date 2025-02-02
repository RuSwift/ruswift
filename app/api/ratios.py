from typing import Any, List, Optional
from xml.etree.ElementTree import (
    Element as XmlElement, SubElement as XmlSubElement,
    tostring as xml_tostring
)

from pydantic import BaseModel
from django.http import HttpResponse

from lib import BaseResource
from core.utils import float_to_datetime
from context import context
from api import BaseExchangeController
from merchants import (
    MerchantRatios, load_directions
)


class Side(BaseModel):
    symbol: str
    value: float
    method: str

    def as_xml(self, name: str) -> XmlElement:
        root = XmlElement(name)
        XmlSubElement(root, "symbol").text = self.symbol
        XmlSubElement(root, "value").text = str(round(self.value, 5))
        XmlSubElement(root, "method").text = self.method
        return root


class EngineRateResource(BaseResource):

    pk = 'id'

    class Retrieve(BaseResource.Retrieve):
        id: str
        rate: float
        scope: str
        engine: str
        give: Side
        get: Side
        utc: Optional[List] = None

        def as_xml(self):
            root = XmlElement('item')
            root.set('id', self.id)
            root.set('scope', self.scope)
            root.set('engine', self.engine)
            root.set('get', self.get.symbol)
            root.set('give', self.give.symbol)
            XmlSubElement(root, "rate").text = str(round(self.rate, 5)).replace('.', ',')

            if self.utc:
                utc_child = XmlElement('utc')
                XmlSubElement(utc_child, "unix").text = str(self.utc[0])
                XmlSubElement(utc_child, "iso").text = str(self.utc[1])
                root.append(utc_child)

            root.append(self.give.as_xml('give'))
            root.append(self.get.as_xml('get'))

            return root


class EngineRateController(BaseExchangeController):

    Resource = EngineRateResource

    async def get_one(self, pk: Any, **filters) -> Optional[Resource.Retrieve]:
        values = await self.get_many()
        for val in values:
            if val.id == pk:
                return val
        return None

    async def get_many(
        self, order_by: Any = 'id', limit: int = None, offset: int = None,
        **filters
    ) -> List[Resource.Retrieve]:
        engine = MerchantRatios()
        directions = load_directions(context.config)
        ratios = await engine.engine_ratios(directions)
        self.metadata.total_count = len(ratios)
        result = []
        for ratio in ratios:
            engine = ratio.engine.split('.')[-1]
            item = self.Resource.Retrieve(
                id=ratio.id,
                rate=ratio.rate,
                scope=ratio.scope,
                engine=engine,
                give=Side(
                    symbol=ratio.direction.src.cur.symbol,
                    value=ratio.give,
                    method=ratio.src_method
                ),
                get=Side(
                    symbol=ratio.direction.dest.cur.symbol,
                    value=ratio.get,
                    method=ratio.dest_method
                ),
                utc=[float(ratio.utc), str(float_to_datetime(ratio.utc))] if ratio.utc else None  # noqa
            )
            result.append(item)
        return result


class XMLEngineRateController(EngineRateController):

    Resource = EngineRateController.Resource

    async def get_one(self, pk: Any, **filters):
        value = await super().get_one(pk)
        if value:
            return HttpResponse(
                content_type='application/xml',
                content=xml_tostring(value.as_xml())
            )
        else:
            return None

    async def get_many(
        self, order_by: Any = 'id', limit: int = None, offset: int = None,
        **filters
    ):
        values = await super().get_many(order_by, limit, offset, **filters)
        root = XmlElement('ratios')
        for value in values:
            root.append(value.as_xml())
        return HttpResponse(
            content_type='application/xml',
            content=xml_tostring(root)
        )
