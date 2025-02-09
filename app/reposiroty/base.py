from abc import ABC, abstractmethod
from typing import Type, List, Tuple, Optional, Dict, Union, Any

import pydantic
from channels.db import database_sync_to_async
from django.db import models, transaction
from django.forms.models import model_to_dict

from entities import BaseEntity
from cache import ImplicitCacheMixin


class AtomicDelegator(ABC):

    @abstractmethod
    def atomic(self, *args, **kwargs):
        ...

    def __call__(self, *args, **kwargs):
        self.atomic(*args, **kwargs)


class BaseEntityRepository(ImplicitCacheMixin, ABC):

    Model: Type[models.Model] = None
    Entity: Type[BaseEntity] = None

    def __init_subclass__(cls, **kwargs):
        if not cls.Entity:
            raise RuntimeError('Entity is empty')
        super().__init_subclass__(**kwargs)

    @classmethod
    async def _get_one(cls, **filters) -> Optional[Entity]:
        m = await cls.Model.objects.filter(**cls._prepare_filters(**filters)).afirst()
        if m:
            return cls.Entity(**cls._model_to_dict(m))
        else:
            return None

    @classmethod
    async def _get_many(
        cls, order_by: Any = None, limit: int = None,
        offset: int = None, **filters
    ) -> Tuple[int, List[Entity]]:
        q = cls.Model.objects.filter(**cls._prepare_filters(**filters))
        total: int = await q.acount()
        if order_by:
            if isinstance(order_by, list):
                q = q.order_by(*order_by)
            else:
                q = q.order_by(order_by)
        ms = []
        async for m in q.all()[offset:limit]:
            ms.append(cls.Entity(**cls._model_to_dict(m)))
        return total, ms

    @classmethod
    async def _create_one(
        cls, atomic: AtomicDelegator = None, **kwargs
    ) -> Entity:

        def _synced() -> cls.Entity:
            with transaction.atomic():
                m = cls.Model.objects.create(**cls._entity_to_dict(kwargs))
                if atomic:
                    atomic()
                return cls.Entity(**cls._model_to_dict(m))

        return await database_sync_to_async(_synced)()

    @classmethod
    async def _create_many(
        cls, entities: List[Entity], atomic: AtomicDelegator = None
    ) -> List[Entity]:
        if not entities:
            return []

        def _sync():
            create_kwargs = [cls._entity_to_dict(e) for e in entities]
            with transaction.atomic():
                ms = []
                for kwargs in create_kwargs:
                    m = cls.Model.objects.create(**cls._entity_to_dict(kwargs))
                    ms.append(m)
                if atomic:
                    atomic()
                return [cls.Entity(**cls._model_to_dict(m)) for m in ms]

        entities = await database_sync_to_async(_sync)()
        return entities

    @classmethod
    async def _update_one(
        cls, e: Entity, atomic: AtomicDelegator = None, **filters
    ) -> Optional[Entity]:
        d = cls._entity_to_dict(e)
        for k in filters.keys():
            if k in d:
                del d[k]

        def _synced():
            with transaction.atomic():
                cls.Model.objects.filter(
                    **cls._prepare_filters(**filters)
                ).update(**d)
                if atomic:
                    atomic.atomic()

        await database_sync_to_async(_synced)()
        return await cls._get_one(**filters)

    @classmethod
    async def _delete_one(
        cls, atomic: AtomicDelegator = None, **filters
    ) -> int:

        def _synced():
            count, *extra = cls.Model.objects.filter(
                **cls._prepare_filters(**filters)
            ).delete()
            if atomic:
                atomic.atomic()
            return count

        return await database_sync_to_async(_synced)()

    @classmethod
    def _model_to_dict(cls, model: models.Model) -> Dict:
        return model_to_dict(model)

    @classmethod
    def _entity_to_dict(cls, e: Union[Entity, Dict]) -> Dict:
        if isinstance(e, pydantic.BaseModel):
            return e.model_dump()
        else:
            return e

    @classmethod
    def _prepare_filters(cls, **filters) -> dict:
        if cls.Model:
            opts = cls.Model._meta
            d = {}
            for f in opts.concrete_fields:
                if not getattr(f, "editable", False):
                    continue
                if f.name in filters:
                    d[f.name] = filters[f.name]
            return d
        else:
            return filters


class EntityRetrieveMixin:

    @classmethod
    async def get(cls, **filters) -> Optional[BaseEntityRepository.Entity]:
        return await cls._get_one(**filters)

    @classmethod
    async def get_many(
        cls, order_by: Any = None, limit: int = None,
        offset: int = None, **filters
    ) -> Tuple[int, List[BaseEntityRepository.Entity]]:  # noqa
        return await cls._get_many(
            order_by=order_by, limit=limit, offset=offset,
            **filters
        )


class EntityCreateMixin:

    @classmethod
    async def create(
        cls, atomic: AtomicDelegator = None, **kwargs
    ) -> BaseEntityRepository.Entity:
        return await cls._create_one(atomic, **kwargs)

    @classmethod
    async def create_many(
        cls,
        entities: List[BaseEntityRepository.Entity],
        atomic: AtomicDelegator = None
    ) -> BaseEntityRepository.Entity:
        return await cls._create_many(entities, atomic)


class EntityUpdateMixin:

    @classmethod
    async def update(
        cls, e: BaseEntityRepository.Entity, atomic: AtomicDelegator = None,
        **filters
    ) -> Optional[BaseEntityRepository.Entity]:
        return await cls._update_one(e, atomic, **filters)

    @classmethod
    async def update_or_create(
        cls, e: BaseEntityRepository.Entity,
        atomic: AtomicDelegator = None,
        **filters
    ) -> BaseEntityRepository.Entity:
        exists = await cls._get_one(**filters)
        if exists:
            ee = e.model_copy()
            for k, v in exists.model_extra.items():
                setattr(ee, k, v)
            return await cls._update_one(ee, atomic, **filters)
        else:
            # data = dict(**filters)
            # data.update(e.model_dump())
            data = e.model_dump() | filters
            return await cls._create_one(atomic, **data)


class EntityDeleteMixin:

    @classmethod
    async def delete(cls, atomic: AtomicDelegator = None, **filters) -> int:
        return await cls._delete_one(atomic, **filters)


class CacheMixin:

    @classmethod
    async def invalidate_cache(cls):
        ks = await cls._cache.keys()
        await cls._cache.delete(ks)
