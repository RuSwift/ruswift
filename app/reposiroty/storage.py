from datetime import datetime
from typing import Union, Dict, Optional

from exchange.models import StorageItem as DBStorageItem
from entities import StorageItem
from .base import (
    BaseEntityRepository, EntityRetrieveMixin, EntityUpdateMixin,
    EntityCreateMixin, EntityDeleteMixin
)


class StorageRepository(
    EntityCreateMixin, EntityRetrieveMixin,
    EntityUpdateMixin, EntityDeleteMixin,
    BaseEntityRepository
):
    Model = DBStorageItem
    Entity = StorageItem

    @classmethod
    def _model_to_dict(cls, model: DBStorageItem) -> Dict:
        d = super()._model_to_dict(model)
        d['updated_at'] = model.updated_at
        d['created_at'] = model.created_at
        return d

    @classmethod
    def _entity_to_dict(cls, e: Union[Entity, Dict]) -> Dict:
        d = super()._entity_to_dict(e)
        d.pop('created_at', None)
        return d

    @classmethod
    def _prepare_filters(cls, **filters) -> dict:
        d = super()._prepare_filters(**filters)
        if 'tag' in filters:
            tag = filters['tag']
            if isinstance(tag, str):
                tag = [tag]
            d['tags__contains'] = tag
        for k, v in filters.items():
            if '__' in k:
                d[k] = v
        return d
