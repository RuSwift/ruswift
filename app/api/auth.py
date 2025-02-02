import logging
import secrets
from hashlib import md5
from typing import Type, Dict, Tuple, Union, Optional, List, Any

from pydantic import BaseModel, model_validator
from django.http import HttpResponse, HttpRequest, QueryDict
from django.utils.translation import gettext as _
from django.conf import settings

from entities import (
    Session as AccountSession, Credential as AccountCredential,
    Account, GrantedAccount, AnonymousAccount
)
from reposiroty import (
    AccountCredentialRepository, AccountSessionRepository, AccountRepository
)


class BaseAuth:

    class Credential(BaseModel):
        ...

        @model_validator(mode='before')
        @classmethod
        def multipart_friendly(cls, data: Any) -> Dict:
            ret = {}
            if isinstance(data, Dict):
                for k, v in data.items():
                    if isinstance(v, list) and len(v) == 0:
                        v = v[0]
                    ret[k] = v
            else:
                ret = dict(data)
            return ret

    Schema: Type[Credential]
    UiSchema: Optional[List] = None
    Descendants = []
    Name: str = 'Base'
    COOKIE_NAME = 'session_uid'

    def __init_subclass__(cls, **kwargs):
        if issubclass(cls, BaseAuth):
            cls.Descendants.append(cls)
        super().__init_subclass__(**kwargs)

    @classmethod
    def load_descendant(cls, class_name: str) -> Optional[Type['BaseAuth']]:
        map_ = {class_.Name: class_ for class_ in cls.Descendants}
        map_.update({class_.__name__: class_ for class_ in cls.Descendants})
        found = map_.get(class_name)
        return found

    @classmethod
    def validate(cls, payload: Union[Dict, QueryDict]) -> bool:
        try:
            cls.Schema.model_validate(payload)
        except ValueError as e:
            return False
        else:
            return True

    @classmethod
    async def auth(
        cls, request: Union[HttpRequest, Dict],
    ) -> Tuple[Optional[Account], Optional[AccountSession]]:
        account, session = None, None
        if isinstance(request, HttpRequest):
            session_uid = request.COOKIES.get(cls.COOKIE_NAME)
            if session_uid:
                session: Optional[AccountSession] = await AccountSessionRepository.get(
                    uid=session_uid
                )
                if session:
                    account: Optional[Account] = await AccountRepository.get(
                        uid=session.account_uid
                    )
                    if account is None:
                        if session.account_uid:
                            await cls.clean(
                                session.account_uid, only_sessions=False
                            )
                        return None, None
                    if not account.is_active:
                        await cls.clean(
                            session.account_uid, only_sessions=True
                        )
                        logging.critical(f'Account {account.uid} is deactivated')
                        return None, None
        return account, session

    @classmethod
    async def login(
        cls, resp: HttpResponse, account: Account, domain: str = None
    ) -> AccountSession:
        session: AccountSession = await AccountSessionRepository.create(
            uid=secrets.token_hex(16),
            class_name=cls.__name__,
            account_uid=account.uid
        )
        cls.prepare_response(resp, session, domain)
        return session

    @classmethod
    def prepare_response(
        cls, resp: HttpResponse, session: AccountSession, domain: str = None
    ):
        if session:
            resp.set_cookie(cls.COOKIE_NAME, session.uid, domain=domain)

    @classmethod
    async def logout(cls, resp: HttpResponse):
        resp.delete_cookie(cls.COOKIE_NAME)

    @classmethod
    async def register(
        cls, account: Union[Account, str], payload: Dict
    ) -> AccountCredential:
        account_uid = account if isinstance(account, str) else account.uid
        cls.Schema.model_validate(payload)
        cred = await AccountCredentialRepository.update_or_create(
            e=AccountCredential(
                class_name=cls.__name__,
                account_uid=account_uid,
                schema=cls.Schema.schema(),
                payload=payload
            ),
            account_uid=account_uid, class_name=cls.__name__
        )
        return cred

    @classmethod
    async def clean(
        cls, account: Union[Account, str], only_sessions: bool = True
    ):
        account_uid = account if isinstance(account, str) else account.uid
        filters = dict(account_uid=account_uid)
        await AccountSessionRepository.delete(**filters)
        if not only_sessions:
            await AccountCredentialRepository.delete(**filters)


class TokenAuth(BaseAuth):

    Name = 'Token'

    class TokenCredential(BaseAuth.Credential):
        token: str

    Schema = TokenCredential
    UiSchema = [
        {
            'component': 'div',
            'fieldOptions': {
                'class': ['form-group'],
            },
            'children': [
                {
                    'component': 'input',
                    'model': 'token',
                    'errorOptions': {
                        'class': ['is-invalid'],
                    },
                    'fieldOptions': {
                        'attrs': {
                            'id': 'token',
                            'name': 'token',
                            'placeholder': _('Персональный Token')
                        },
                        'class': ['form-control'],
                        'on': ['input'],
                    },
                }
            ]
        }
    ]

    @classmethod
    async def auth(
        cls, request: Union[HttpRequest, Dict],
    ) -> Tuple[Optional[Account], Optional[AccountSession]]:
        account, session = None, None
        if isinstance(request, HttpRequest):
            data = None
            lowered_headers = {
                k.lower(): v for k, v in request.headers.items()
            }
            if cls.validate(request.GET):
                data = cls.Schema.model_validate(request.GET).model_dump()
            elif cls.validate(lowered_headers):
                data = cls.Schema.model_validate(lowered_headers).model_dump()
            if data:
                return await cls.auth(data)
            else:
                account, session = await super().auth(request)
        else:
            passed = cls.TokenCredential.model_validate(request)
            h = 'md5:' + md5(passed.token.encode()).hexdigest()
            cred = await AccountCredentialRepository.get(
                payload__token=h
            )
            if cred:
                account = await AccountRepository.get(uid=cred.account_uid)
        return account, session

    @classmethod
    async def register(
        cls, account: Union[Account, str], payload: Dict
    ) -> AccountCredential:
        data = cls.TokenCredential.model_validate(payload)
        data.token = 'md5:' + md5(data.token.encode()).hexdigest()
        # Проверяем что нет другого пользователя с таким же token
        account_uid = account if isinstance(account, str) else account.uid
        cred = await AccountCredentialRepository.get(
            payload__token=data.token, class_name=cls.__name__
        )
        if cred and cred.account_uid != account_uid:
            raise ValueError(f'Token занят')
        return await super().register(account, data.model_dump())


class LoginAuth(BaseAuth):

    Name = 'Login'

    class LoginCredential(BaseAuth.Credential):
        login: str
        password: str

    Schema = LoginCredential
    UiSchema = [
        {
            'component': 'div',
            'fieldOptions': {
                'class': ['form-group'],
            },
            'children': [
                {
                    'component': 'input',
                    'model': 'login',
                    'errorOptions': {
                        'class': ['is-invalid'],
                    },
                    'fieldOptions': {
                        'attrs': {
                            'id': 'login',
                            'name': 'login',
                            'placeholder': _('Логин')
                        },
                        'class': ['form-control'],
                        'on': ['input'],
                    },
                },
                {
                    'component': 'input',
                    'model': 'password',
                    'errorOptions': {
                        'class': ['is-invalid'],
                    },
                    'fieldOptions': {
                        'attrs': {
                            'id': 'password',
                            'name': 'password',
                            'placeholder': _('Пароль')
                        },
                        'class': ['form-control', 'mt-1'],
                        'on': ['input'],
                    },
                }
            ]
        }
    ]

    @classmethod
    async def auth(
        cls, request: Union[HttpRequest, Dict],
    ) -> Tuple[Optional[Account], Optional[AccountSession]]:
        account, session = None, None
        if isinstance(request, HttpRequest):
            account, session = await super().auth(request)
        else:
            passed = cls.LoginCredential.model_validate(request)
            cred: Optional[AccountCredential] = await AccountCredentialRepository.get(
                payload__login=passed.login, class_name=cls.__name__
            )
            if cred:
                account = await AccountRepository.get(uid=cred.account_uid)
            if cred and account:
                stored = cls.LoginCredential.model_validate(cred.payload)
                h = 'md5:' + md5(passed.password.encode()).hexdigest()
                if stored.password != h:
                    account = None
            else:
                account, session = None, None
        return account, session

    @classmethod
    async def register(
        cls, account: Union[Account, str], payload: Dict
    ) -> AccountCredential:
        data = cls.LoginCredential.model_validate(payload)
        # Проверяем что нет другого пользователя с таким же login
        account_uid = account if isinstance(account, str) else account.uid
        cred = await AccountCredentialRepository.get(
            payload__login=data.login, class_name=cls.__name__
        )
        if cred and cred.account_uid != account_uid:
            raise ValueError(f'Login занят')
        # заполняем
        data.password = 'md5:' + md5(data.password.encode()).hexdigest()
        return await super().register(account, data.model_dump())


class ApiTokenAuth(BaseAuth):

    Name = 'ApiToken'
    GRANT_ACCOUNT_HDR = 'X-Grant'
    GRANT_PERMISSION = Account.Permission.GRANT.value

    class ApiCredential(BaseAuth.Credential):
        access_token: str

    Schema = ApiCredential

    @classmethod
    async def auth(
        cls, request: Union[HttpRequest, Dict],
    ) -> Tuple[Optional[Account], Optional[AccountSession]]:
        cur_account: Optional[Account] = None
        if settings.API['AUTH']:
            auth_scheme = request.headers.get('Authorization')
            if auth_scheme:
                if auth_scheme.startswith('Token'):
                    access_token = auth_scheme.split(' ')[-1]
                    for uid, desc in settings.API['AUTH'].items():
                        if desc.token == access_token:
                            cur_account = Account(
                                uid=uid, permissions=desc.permissions
                            )
        if cls.GRANT_ACCOUNT_HDR in request.headers:
            if not cur_account:
                raise ValueError(f'You try to Grant but not authorized')
            if cls.GRANT_PERMISSION not in cur_account.permissions:
                raise ValueError(
                    f'You try to Grant but not have "{cls.GRANT_PERMISSION}" '
                    f'permissions'
                )
            granted_account: Account = await AccountRepository.get(
                uid=request.headers[cls.GRANT_ACCOUNT_HDR]
            )
            if not granted_account:
                raise ValueError(f'You try to Grant to unknown account')
            cur_account = GrantedAccount(
                owner=cur_account.uid,
                **granted_account.model_dump()
            )
        return cur_account, None

    @classmethod
    async def login(
        cls, resp: HttpResponse, account: Account
    ) -> AccountSession:
        raise NotImplemented('Invalid operation')

    @classmethod
    async def logout(cls, resp: HttpResponse):
        raise NotImplemented('Invalid operation')

    @classmethod
    async def register(
        cls, account: Union[Account, str], payload: Dict
    ) -> AccountCredential:
        raise NotImplemented('Invalid operation')

    @classmethod
    async def clean(
        cls, account: Union[Account, str], only_sessions: bool = True
    ):
        raise NotImplemented('Invalid operation')


class AnonymousAuth(BaseAuth):

    Name = 'Anonymous'

    class AnonymousCredential(BaseAuth.Credential):
        ...

    Schema = AnonymousCredential

    @classmethod
    def validate(cls, payload: Union[Dict, QueryDict]) -> bool:
        return True

    @classmethod
    async def auth(
        cls, request: Union[HttpRequest, Dict],
    ) -> Tuple[Optional[Account], Optional[AccountSession]]:
        account, session = None, None
        if isinstance(request, HttpRequest):
            session_uid = request.COOKIES.get(cls.COOKIE_NAME)
            if session_uid:
                session: Optional[AccountSession] = await AccountSessionRepository.get(  # noqa
                    uid=session_uid
                )
                if session and session.account_uid is None:
                    uid = session.uid
                    account = await AccountRepository.load_anonymous_account(uid)  # noqa
                    if account:
                        return account, session
                    else:
                        return AnonymousAccount(uid=session.uid), session
                else:
                    return None, None
        return account, session

    @classmethod
    async def login(
        cls, resp: HttpResponse, account: Account
    ) -> AccountSession:
        if not isinstance(account, AnonymousAccount):
            raise RuntimeError('Supported only anonymous accounts')
        session: AccountSession = await AccountSessionRepository.create(
            uid=account.uid,
            class_name=cls.__name__,
            account_uid=None
        )
        resp.set_cookie(cls.COOKIE_NAME, session.uid)
        return session
