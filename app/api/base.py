import logging
from abc import ABC, abstractmethod
from typing import Type, Callable, Optional, Dict, List, Tuple, Union

from django.conf import settings
from django.http import HttpResponse, HttpRequest

from api.lib import (
    BaseResource, SingleResourceAsyncHttpTransport,
    ManyResourceAsyncHttpTransport, HttpRouter, BaseController,
    MethodMapping
)

from exchange.entities import (
    Account, ExchangeConfig, AnonymousAccount, MerchantAccount,
    MerchantMeta, Identity
)
from exchange.context import Context, context as app_context
from exchange.cache import Cache
from exchange.reposiroty.config import ExchangeConfigRepository
from .auth import BaseAuth


METHOD_NAME = str
PERMISSION_NAME = str
ERR_MSG = str


class BaseExchangeThrottler:

    @classmethod
    @abstractmethod
    async def validate(
        cls, user: Account, request: HttpRequest
    ) -> Tuple[bool, Optional[ERR_MSG]]:
        ...


class BaseExchangeController(ABC, BaseController):

    PERMISSIONS: Dict[METHOD_NAME, Optional[List[PERMISSION_NAME]]] = {'*': None}  # noqa
    THROTTLERS: List[Type[BaseExchangeThrottler]] = []

    class Context(BaseController.Context):
        user: Optional[Account] = None
        config: Optional[ExchangeConfig] = None

    context: Context

    def __init__(self, context: BaseController.Context, *args, **kwargs):
        super().__init__(context, *args, **kwargs)
        self.cache = Cache(
            pool=settings.REDIS_CONN_POOL,
            namespace=self.__class__.__name__
        )

    async def before(self, *args, **kwargs):
        ...

    async def check_permission(
        self, request: HttpRequest, handler: Union[Callable, MethodMapping]
    ) -> bool:
        if self.context.user and Account.Permission.ROOT.value in self.context.user.permissions:
            return True
        if isinstance(handler, MethodMapping):
            method_name = handler.func_name
        else:
            method_name = handler.__func__.__name__
        for name, perms in self.PERMISSIONS.items():
            for matched in [method_name == name, name == '*']:
                if matched:
                    if perms:
                        if isinstance(perms, str):
                            perms = [perms]
                        if self.context.user:
                            superset = set(perms)
                            subset = set(self.context.user.permissions)
                            subset.add(Account.Permission.ANY.value)
                            if superset.intersection(subset) != superset:
                                return False
                        else:
                            return False
        return True

    @property
    def identity(self) -> Optional[Identity]:
        if isinstance(self.context.user, MerchantAccount):
            identity = self.context.user.meta.identity
        else:
            identity = app_context.config.identity
        return identity


class AuthControllerMixin:

    async def check_permission(
        self, request: HttpRequest, handler: Union[Callable, MethodMapping]
    ) -> bool:
        if self.context.user and self.context.user.is_active:
            if isinstance(self.context.user, AnonymousAccount):
                return False
            else:
                return await super().check_permission(request, handler)
        else:
            return False


class ExchangeContextMixin:

    async def post(
        self, request: HttpRequest, controller_handler: Callable,
        context: 'Controller.Context', resource: Type[BaseResource],
        *args, **kwargs
    ) -> HttpResponse:
        resp = await super().post(
            request, controller_handler, context, resource, *args, **kwargs
        )
        if resp.status_code == 201:
            resp.status_code = 200
        return resp

    async def transport(
        self, handler,
        resource: Type[BaseResource],
        request: HttpRequest,
        context: BaseExchangeController.Context,
        *args, **kwargs
    ) -> HttpResponse:
        try:
            cfg = await ExchangeConfigRepository.get()
            context.config = cfg
            user = await self._extract_user(request)
            context.user = user
            with Context.create_context(config=cfg, user=user):
                if isinstance(self.controller, BaseExchangeController):
                    await self.controller.before(*args, **kwargs)
                return await super().transport(
                    handler, resource, request, context, *args, **kwargs
                )
        except Exception as e:
            logging.exception('ERROR')
            if isinstance(e, ValueError):
                err = e.args[0] if e.args else ''
                return HttpResponse(status=400, content=err.encode())
            raise e

    @classmethod
    async def _extract_user(cls, request: HttpRequest) -> Optional[Account]:
        for auth in BaseAuth.Descendants:
            auth: BaseAuth
            account, session = await auth.auth(request)
            if account:
                if account.merchant_meta and Account.Permission.MERCHANT.value in account.permissions:
                    account = MerchantAccount(
                        meta=MerchantMeta.model_validate(account.merchant_meta),
                        **dict(account)
                    )
                return account
        return None


class ExchangeSingleResourceTransport(
    ExchangeContextMixin, SingleResourceAsyncHttpTransport
):
    ...


class ExchangeManyResourceTransport(
    ExchangeContextMixin, ManyResourceAsyncHttpTransport
):
    ...


class ExchangeHttpRouter(HttpRouter):

    def __init__(
        self, base_url: str,
        single_transport: Type[ExchangeSingleResourceTransport] = None,
        many_transport: Type[ExchangeManyResourceTransport] = None
    ):
        super().__init__(
            base_url,
            single_transport or ExchangeSingleResourceTransport,
            many_transport or ExchangeManyResourceTransport
        )
