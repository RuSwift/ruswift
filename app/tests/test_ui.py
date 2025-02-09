import os.path
import asyncio
from typing import Dict

import requests
from pydantic import BaseModel, Extra
from pydantic_yaml import parse_yaml_file_as
from django.test import LiveServerTestCase, override_settings
from django.urls import reverse

from api.auth import BaseAuth, TokenAuth
from ui.landing import LandingPayolinView
from entities import ExchangeConfig, MerchantMeta, Credential
from merchants import update_merchants_config


class AnyCfg(BaseModel, extra=Extra.allow):
    ...


class TestStatic(LiveServerTestCase):

    def test_success(self):
        url = self.live_server_url + f'/static/assets/favicon.ico'
        resp = requests.get(url)
        assert resp.status_code == 200


class TestAuth(LiveServerTestCase):

    cfg: ExchangeConfig
    token_cred: Dict
    login_cred: Dict

    def setUp(self):
        super().setUp()
        path, section = '/app/exchange/tests/files/init.example.yml', 'exchange'
        if not os.path.isfile(path):
            raise RuntimeError(f'path "{path}" not exists')
        settings = parse_yaml_file_as(AnyCfg, path)
        if section:
            values = getattr(settings, section)
        else:
            values = settings
        self.cfg = ExchangeConfig.model_validate(values)
        d = [m for u, m in self.cfg.merchants.items() if u == 'babapay'][0]
        merchant = MerchantMeta.model_validate(d)
        assert len(merchant.auth) == 2
        self.token_cred = [a.settings for a in merchant.auth if a.class_ == 'TokenAuth'][0]
        self.login_cred = [a.settings for a in merchant.auth if a.class_ == 'LoginAuth'][0]
        asyncio.run(
            update_merchants_config(self.cfg)
        )

    def test_auth_by_login(self):
        url = self.live_server_url + reverse('login')
        get = requests.get(url)
        assert get.status_code == 200
        csrf_token = get.cookies.get('csrftoken')
        login = requests.post(
            url, data=dict(
                csrfmiddlewaretoken=csrf_token, **self.login_cred
            ),
            cookies=get.cookies,
            allow_redirects=False
        )
        assert login.status_code == 302
        assert 'session_uid' in login.cookies
        assert 'babapay' in login.next.url

        url = f'/api/accounts/iam'
        iam = requests.get(
            url=self.live_server_url + url,
            cookies=login.cookies
        )
        assert iam.status_code == 200
        account = iam.json()
        assert account and account['uid'] == 'babapay'

    def test_auth_by_token(self):
        url = self.live_server_url + reverse('login')
        get = requests.get(url)
        assert get.status_code == 200
        csrf_token = get.cookies.get('csrftoken')
        login = requests.post(
            url, data=dict(
                csrfmiddlewaretoken=csrf_token, **self.token_cred
            ),
            cookies=get.cookies,
            allow_redirects=False
        )
        assert login.status_code == 302
        assert 'session_uid' in login.cookies
        assert 'babapay' in login.next.url

        url = f'/api/accounts/iam'
        iam = requests.get(
            url=self.live_server_url + url,
            cookies=login.cookies
        )
        assert iam.status_code == 200
        account = iam.json()
        assert account and account['uid'] == 'babapay'

        # Auth with GET param
        url = f'/api/accounts/iam?token=' + self.token_cred['token']
        iam = requests.get(
            url=self.live_server_url + url
        )
        assert iam.status_code == 200
        account = iam.json()
        assert account and account['uid'] == 'babapay'

    def test_logout(self):
        url = self.live_server_url + reverse('login')
        get = requests.get(url)
        assert get.status_code == 200

        csrf_token = get.cookies.get('csrftoken')
        login = requests.post(
            url, data=dict(
                csrfmiddlewaretoken=csrf_token, **self.token_cred
            ),
            cookies=get.cookies,
            allow_redirects=False
        )
        assert 'session_uid' in login.cookies

        logout = requests.get(
            self.live_server_url + reverse('logout'),
            cookies=login.cookies,
            allow_redirects=False
        )
        assert logout.status_code == 302
        assert 'session_uid' not in logout.cookies
        assert 'login' in logout.next.url


class TestViews(LiveServerTestCase):

    cfg: ExchangeConfig

    def setUp(self):
        super().setUp()
        path, section = '/app/exchange/tests/files/init.example.yml', 'exchange'
        if not os.path.isfile(path):
            raise RuntimeError(f'path "{path}" not exists')
        settings = parse_yaml_file_as(AnyCfg, path)
        if section:
            values = getattr(settings, section)
        else:
            values = settings
        self.cfg = ExchangeConfig.model_validate(values)
        d = [m for u, m in self.cfg.merchants.items() if u == 'babapay'][0]
        merchant = MerchantMeta.model_validate(d)
        assert len(merchant.auth) == 2
        asyncio.run(
            update_merchants_config(self.cfg)
        )

    def test_index_page_anonymous_session_allocation(self):
        get = requests.get(self.live_server_url)
        assert get.status_code == 200
        assert 'session_uid' in get.cookies

        path = f'/api/accounts/iam'
        iam = requests.get(
            url=self.live_server_url + path,
            cookies=get.cookies
        )
        assert iam.status_code == 200
        account = iam.json()
        assert account
        assert account['is_anonymous'] is True

        session_id = get.cookies['session_uid']
        get2 = requests.get(self.live_server_url, cookies=get.cookies)
        assert get2.status_code == 200
        assert get2.cookies['session_uid'] == session_id

    def test_merchant_admin_page(self):
        merchant = MerchantMeta.model_validate(self.cfg.merchants['babapay'])
        token_cred = [
            a.settings for a in merchant.auth if a.class_ == 'TokenAuth'
        ][0]

        # 0. Init
        admin_path = merchant.paths.admin.replace('/', '')

        admin = requests.get(
            self.live_server_url + '/' + admin_path,
        )
        assert admin.status_code == 403

        get = requests.get(self.live_server_url + reverse('login'))
        # 1. Login
        csrf_token = get.cookies.get('csrftoken')
        login = requests.post(
            self.live_server_url + reverse('login'),
            data=dict(
                csrfmiddlewaretoken=csrf_token, **token_cred
            ),
            cookies=get.cookies,
            allow_redirects=False
        )
        assert login.status_code == 302
        assert login.next.url.endswith(admin_path)
        # 2. Go to admin page
        admin = requests.get(
            self.live_server_url + '/' + admin_path,
            cookies=login.cookies
        )
        assert admin.status_code == 200


@override_settings(ROOT_URLCONF='settings.landing.payolin.urls')
class TestPayolinLanding(LiveServerTestCase):

    def test_index_page(self):
        get = requests.get(self.live_server_url)
        assert get.status_code == 200

    def test_parsing_bank_resource(self):
        coro = LandingPayolinView.load_bank_cur('cny', use_cache=False)
        res = asyncio.run(coro)
        assert res
        assert type(res[0]) is str
        assert type(res[1]) is float
