import asyncio
from typing import Optional, Coroutine, Tuple, List

from django.views.generic.base import (
    TemplateResponseMixin, ContextMixin, View
)
from django.urls import reverse
from urllib.parse import urljoin, urlsplit
from django.http import (
    HttpRequest, HttpResponseRedirect, HttpResponse, HttpResponseForbidden,
    Http404
)
from django.utils.translation import gettext as _
from django.conf import settings

from entities import (
    MerchantMeta, Account, ExchangeConfig, Session, AnonymousAccount,
    MerchantAccount, Identity
)
from api.auth import BaseAuth, AnonymousAuth
from reposiroty import (
    AccountSessionRepository, ExchangeConfigRepository, AccountRepository,
    StorageRepository
)
from kyc import MTSKYCProvider
from context import context as app_context, Context as AppContext


class BaseExchangeView(View):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._request: Optional[HttpRequest] = None

    def dispatch(self, request: HttpRequest, *args, **kwargs):
        handler = super().dispatch(request, *args, **kwargs)
        if asyncio.iscoroutine(handler):
            self._request = request
            return self._dispatcher(request, handler)
        else:
            raise RuntimeError('Only async methods')

    async def _dispatcher(self, request: HttpRequest, handler: Coroutine):
        cfg, user, session = await self._build_context(request)
        with AppContext.create_context(config=cfg, user=user, session=session):
            await self._before(request)
            try:
                resp = await handler
                await self._after(resp=resp)
            except Exception as e:
                await self._after(fail=e)
            else:
                return resp

    @classmethod
    async def _build_context(
        cls, request: HttpRequest
    ) -> Tuple[Optional[ExchangeConfig], Optional[Account], Optional[Session]]:
        cfg = await ExchangeConfigRepository.get()
        user, session = None, None
        return cfg, user, session

    async def _before(self, request: HttpRequest):
        ...

    async def _after(self, resp: HttpResponse = None, fail: Exception = None):
        ...

    def redirect_to(self, path: str, base: str = None) -> HttpResponseRedirect:
        if base:
            redirect_to = urljoin(str(base), path)
        else:
            redirect_to = urljoin(
                self._request.scheme + '://' + self._request.get_host(),
                path
            )
        return HttpResponseRedirect(redirect_to=redirect_to)


class AuthExchangeView(ContextMixin, BaseExchangeView):

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs) or {}
        if app_context.user:
            data['user'] = app_context.user.model_dump(mode='json')
        else:
            data['user'] = None
        return data

    @classmethod
    def extract_identity(cls, user: Account = None) -> Optional[Identity]:
        user_ = user or app_context.user
        if isinstance(user_, MerchantAccount):
            identity = user_.meta.identity
        else:
            identity = app_context.config.identity
        return identity

    @classmethod
    async def _build_context(
        cls, request: HttpRequest
    ) -> Tuple[Optional[ExchangeConfig], Optional[Account], Optional[Session]]:
        cfg, user, session = await super()._build_context(request)
        if user is None:
            for auth in BaseAuth.Descendants:
                auth: BaseAuth
                user, session = await auth.auth(request)
                if user or session:  # в анонимной сессии user м.б. пуст
                    break
        return cfg, user, session

    async def _after(self, resp: HttpResponse = None, fail: Exception = None):
        if resp is None:
            return
        if app_context.user is None:
            await AnonymousAuth.login(
                resp=resp, account=AnonymousAccount()
            )
        elif app_context.session:
            BaseAuth.prepare_response(resp, app_context.session)


class TestView(TemplateResponseMixin, ContextMixin, View):
    template_name = "test.html"

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs) or {}
        return data

    async def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        return self.render_to_response(context)


class ScenarioView(TemplateResponseMixin, AuthExchangeView):

    template_name = 'index.html'
    public_scenarios = [
        'kyc',
        'register',
        'cabinet'
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.merchant: Optional[MerchantMeta] = None
        self.logged_with_account = False

    async def _before(self, request: HttpRequest):
        if app_context.user and app_context.user.merchant_meta and Account.Permission.MERCHANT.value in app_context.user.permissions:
            self.merchant = MerchantMeta.model_validate(
                app_context.user.merchant_meta
            )
        self.logged_with_account = not (app_context.user is None or isinstance(app_context.user, AnonymousAccount))  # noqa

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs) or {}
        data['merchant'] = self.merchant
        data['user'] = app_context.user.model_dump(mode='json') if app_context.user else None  # noqa
        data['mass_payments'] = 'yes'
        login_url: str = settings.LOGIN_URL
        logout_url: str = settings.LOGOUT_URL
        register_url: str = settings.REGISTER_URL
        if not login_url.startswith('/'):
            login_url = '/' + login_url
        if not logout_url.startswith('/'):
            logout_url = '/' + logout_url
        if not register_url.startswith('/'):
            register_url = '/' + register_url

        data['urls'] = {
            'home': '/',
            'login': login_url,
            'logout': logout_url,
            'register': register_url,
            'cabinet': '/cabinet',
            'admin': app_context.config.paths.admin
        }

        if self.merchant:
            data['logo'] = self.merchant.title
            data['urls']['admin'] = self.merchant.paths.admin
            if not self.merchant.mass_payments.enabled:
                data['mass_payments'] = 'no'
        else:
            data['logo'] = 'Control Panel'
            data['urls']['admin'] = app_context.config.paths.admin
        return data

    async def get(self, request: HttpRequest, scenario: str = None, *args, **kwargs):  # noqa
        context = self.get_context_data(**kwargs)
        if scenario:
            if scenario in self.public_scenarios:
                return await self.render_public_scenario(
                    request, scenario, context, *args, **kwargs
                )
            if not self.logged_with_account:
                return HttpResponseForbidden()
        if self.merchant:
            paths = self.merchant.paths
            template_dir = 'merchants/'
        else:
            if self.logged_with_account:
                paths = app_context.config.paths
                template_dir = 'control_panel/'
                merchants = await self.load_merchants()
                merchants_with_mass_payments = [
                    a for a in merchants if a.meta.mass_payments.enabled
                ]
                context['merchants_with_mass_payments'] = merchants_with_mass_payments  # noqa
        if scenario:
            if scenario == paths.admin.replace('/', ''):
                self.template_name = template_dir + 'admin.html'
            else:
                self.template_name = '404.html'
                return self.render_to_response(context, status=404)
        return self.render_to_response(context)

    async def render_public_scenario(self, request: HttpRequest, scenario: str, context: dict, *args, **kwargs) -> HttpResponse:  # noqa
        # 1. load actual templates url
        merchants = await self.load_merchants()
        merchant = None
        for m in merchants:
            parts = urlsplit(str(m.meta.url))
            if str(request.get_host()) == parts.netloc:
                merchant = m
                break
        # 2. fill contexts
        context['public'] = {
            'title': 'RuSwift'
        }
        # 3. load actual templates
        if merchant:
            # потом будем брать из актуальных настроек
            template_dir = 'public/'
            context['public']['title'] = merchant.merchant_meta['title']

        else:
            template_dir = 'public/'

        try:
            resp = None
            if scenario == 'kyc':
                resp = await self._process_kyc(request, context, merchant, *args, **kwargs)
            elif scenario == 'register':
                resp = await self._process_register(request, context, merchant, *args, **kwargs)
            elif scenario == 'cabinet':
                resp = await self._process_cabinet(request, context, merchant, *args, **kwargs)
            if resp:
                return resp
            self.template_name = template_dir + f'{scenario}.html'
            return self.render_to_response(context)
        except Http404:
            self.template_name = '404.html'
            return self.render_to_response(context, status=404)

    @classmethod
    async def load_merchants(cls) -> List[MerchantAccount]:
        merchants = await AccountRepository.get_merchants()
        return merchants

    async def _process_kyc(
        self, request: HttpRequest,
        context: dict, merchant: MerchantAccount = None, *args, **kwargs
    ) -> HttpResponse:  # noqa
        pk = kwargs.get('id')
        if not pk:
            raise Http404

        # identity = self.extract_identity(merchant)

        entity = await StorageRepository.get(
            **{
                'payload__id': pk,
                # 'storage_id': identity.did.root, может потеряться запись
                'category': MTSKYCProvider.provider_id
            }
        )
        if not entity:
            raise Http404

        if entity.payload['account_uid']:
            account = await AccountRepository.get(uid=entity.payload['account_uid'])
        else:
            account = None

        context['registration'] = entity.payload.get('registration', False)
        context['account'] = account
        context['identity_url'] = entity.payload['identification_url']
        context['identity_id'] = pk

    async def _process_register(
        self, request: HttpRequest,
        context: dict, merchant: MerchantAccount = None, *args, **kwargs
    ) -> HttpResponse:

        pk = kwargs.get('id')
        if pk:
            entity = await StorageRepository.get(
                **{
                    'payload__id': pk,
                    # 'storage_id': identity.did.root, может потеряться запись
                    'category': MTSKYCProvider.provider_id
                }
            )
        else:
            entity = None

        if entity:
            if app_context.user and not isinstance(app_context.user, AnonymousAccount):
                return HttpResponseRedirect(
                    redirect_to=context['urls']['logout'] + f'?redirect_to={request.path}'
                )
            if not entity.payload['account_uid'] and isinstance(app_context.user, AnonymousAccount):
                # кладем KYC в хранилище анонима
                entity.payload['account_uid'] = app_context.user.uid
                await StorageRepository.update(
                    entity,
                    payload__id=pk,
                    category=MTSKYCProvider.provider_id
                )

        else:
            if pk:
                raise Http404

        if entity and entity.payload['account_uid']:
            account = await AccountRepository.get(uid=entity.payload['account_uid'])
        else:
            account = None

        if entity:
            context['registration'] = entity.payload.get('registration', False)
            context['account'] = account
            context['identity_url'] = entity.payload['identification_url']
            context['identity_id'] = pk

    async def _process_cabinet(
        self, request: HttpRequest,
        context: dict, merchant: MerchantAccount = None, *args, **kwargs
    ) -> HttpResponse:  # noqa
        if not app_context.user:
            # дадим отработать _after с работой через анонима
            return HttpResponseRedirect(redirect_to='/cabinet')


class KYCView(TemplateResponseMixin, ContextMixin, BaseExchangeView):

    template_name = 'kyc.html'

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs) or {}
        return data

    async def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        return self.render_to_response(context)


class LoginView(TemplateResponseMixin, ContextMixin, BaseExchangeView):

    template_name = 'login.html'
    _redirect_param = 'redirect'

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs) or {}
        data['auths'] = [
            {
                'name': cls.Name,
                'schema': cls.Schema.schema(),
                'ui_schema': cls.UiSchema,
            } for cls in BaseAuth.Descendants if cls.UiSchema
        ]
        data['user'] = app_context.user.model_dump(mode='json') if app_context.user else None  # noqa
        data['urls'] = {
            'home': '/',
            'logout': settings.LOGOUT_URL,
            'register': settings.REGISTER_URL,
            'cabinet': '/cabinet'
        }
        print(data['urls'])
        return data

    async def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        return self.render_to_response(context)

    async def post(self, request: HttpRequest, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        active_auths = [a['name'] for a in context['auths']]
        current_account, current_session = await BaseAuth.auth(request)
        for auth in BaseAuth.Descendants:
            auth: BaseAuth
            if auth.Name not in active_auths or isinstance(auth, AnonymousAuth):
                continue
            if auth.validate(request.POST):
                data = auth.Schema.model_validate(request.POST).model_dump()
                account, session = await auth.auth(data)
                if account:
                    if current_session:
                        await AccountSessionRepository.delete(
                            uid=current_account.uid
                        )
                    if Account.Permission.MERCHANT.value in account.permissions and account.merchant_meta:  # noqa
                        meta = MerchantMeta.model_validate(
                            account.merchant_meta
                        )
                        base, path = str(meta.url), meta.paths.admin
                        domain = None  # str(meta.url)
                    else:
                        base, path = None, app_context.config.paths.admin
                        domain = None
                    resp = self.redirect_to(path, base)
                    await auth.login(resp, account, domain=domain)
                    return resp
            else:
                pass
        context['error'] = _('Ошибка авторизации')
        return self.render_to_response(context)

    @classmethod
    def extract_redirect_url(cls, request: HttpRequest) -> Optional[str]:
        url = request.GET.dict().get(cls._redirect_param)
        return url


class LogoutView(AuthExchangeView):

    async def get(self, request: HttpRequest, *args, **kwargs):
        redirect_to = request.GET.get(
            key='redirect_to', default=reverse('login')
        )
        resp = self.redirect_to(path=redirect_to)
        await BaseAuth.logout(resp)
        return resp
