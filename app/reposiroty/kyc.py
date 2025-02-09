from typing import Union, Dict
from uuid import uuid4

from channels.db import database_sync_to_async

from exchange.models import KYCPhoto as DBKYCPhoto
from entities import KYCPhoto
from core import utc_now_float

from .base import (
    BaseEntityRepository, EntityRetrieveMixin, EntityUpdateMixin,
    EntityCreateMixin, EntityDeleteMixin
)


class KYCPhotoRepository(
    EntityCreateMixin, EntityRetrieveMixin,
    EntityUpdateMixin, EntityDeleteMixin, BaseEntityRepository
):
    Model = DBKYCPhoto
    Entity = KYCPhoto

    @classmethod
    async def remove_expired_files(cls):

        def _synced():
            now = utc_now_float()
            DBKYCPhoto.objects.filter(remove_after__lte=now).delete()

        await database_sync_to_async(_synced)()

    @classmethod
    def _model_to_dict(cls, model: Model) -> Dict:
        d = super()._model_to_dict(model)
        d['image'] = bytes(model.image)
        return d

    @classmethod
    def _entity_to_dict(cls, e: Union[Entity, Dict]) -> Dict:
        d = super()._entity_to_dict(e)
        if isinstance(e, cls.Entity):
            uid = getattr(e, 'uid', None)
        else:
            uid = d.get('uid', None)
        if not uid:
            d['uid'] = uuid4().hex
        return d
