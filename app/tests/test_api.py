import os
import base64
import asyncio
import uuid
from typing import List
from uuid import uuid4

import magic
import requests
from pydantic import BaseModel, Extra
from pydantic_yaml import parse_yaml_file_as

from django.conf import settings
from django.test import LiveServerTestCase, override_settings

from entities import (
    KYCPhoto, VerifiedDocument, VerifyMetadata, Biometrics,
    MatchFaces, Liveness, Account, ExchangeConfig, MerchantMeta,
    PaymentRequest
)
from reposiroty import (
    ExchangeConfigRepository, AccountRepository
)
from exchange.models import (
    KYCPhoto as DBKYCPhoto, Account as DBAccount,
    StorageItem as DBStorageItem
)
from kyc.base import BaseKYCProvider
from merchants import update_merchants_config
from reposiroty.utils import create_superuser, TokenAuth
from .binaries import DATA_URL_JPG, DATA_URL_PDF, DATA_URI_XLS, DATA_URI_DOCX


class FakeKYCProvider(BaseKYCProvider):

    provider_id = 'fake'

    async def verify(self, photos: List[KYCPhoto]) -> VerifiedDocument:
        selfie = any(p.type == 'selfie' for p in photos)
        data = VerifiedDocument(
            id='number-of-document',
            kyc_provider='beorg.ru',
            issued_by='дата выдачи паспорта',
            issued_date='дата выдачи паспорта',
            issued_id='код подразделения',
            series='серия',
            number='номер',
            gender='M',
            last_name='Dmitry',
            first_name='Ivanov',
            birth_date='01.01.1990',
            birth_place='Moscow',
            has_photo=True,
            has_owner_signature=True,
            metadata=VerifyMetadata(
                confidences={
                    'issued_by': 0.99,
                    'series': 0.95
                },
                broken_reason='Подделка / помарки, причины брака документа',
                biometrics=None
            )
        )
        if selfie:
            data.metadata.biometrics = Biometrics(
                matches=MatchFaces(
                    match_faces=0.99,
                    similarity=0.99
                ),
                liveness=Liveness(
                    liveness=True,
                    probability=0.98
                )
            )
        return data


class ExchangeLiveMixin:

    token_cred: dict

    def setUp(self):
        super().setUp()
        path, section = '/workspaces/ruswift/tests/files/init.example.yml', 'exchange'
        if not os.path.isfile(path):
            raise RuntimeError(f'path "{path}" not exists')
        settings_ = parse_yaml_file_as(AnyCfg, path)
        if section:
            values = getattr(settings_, section)
        else:
            values = settings_
        self.cfg = ExchangeConfig.model_validate(values)
        d = [m for u, m in self.cfg.merchants.items() if u == 'koan'][0]
        merchant = MerchantMeta.model_validate(d)
        assert len(merchant.auth) > 0
        self.merchant: MerchantMeta = merchant
        self.token_cred = [a.settings for a in merchant.auth if a.class_ == 'TokenAuth'][0]
        asyncio.run(
            ExchangeConfigRepository.set(self.cfg)
        )
        asyncio.run(
            update_merchants_config(self.cfg)
        )

    @property
    def headers(self) -> dict:
        return {
            'Content-type': 'application/json',
            'Token': self.token_cred['token']
        }

    @classmethod
    def create_root(cls, token: str) -> Account:
        account = Account(
            uid='root:' + uuid.uuid4().hex,
            phone='+7-911-120-92-22',
            permissions=['root']
        )
        asyncio.run(AccountRepository.create_many([account]))
        asyncio.run(TokenAuth.register(
            account, {'token': token}
        ))
        return account


@override_settings(KYC={'PROV_CLASS': 'exchange.kyc.FakeKYCProvider'})
class TestKYC(LiveServerTestCase):

    @property
    def access_token(self) -> str:
        for user_id, desc in settings.API['AUTH'].items():
            if 'kyc' in desc.permissions:
                return desc.token
        raise AssertionError('Empty KYC token')

    @property
    def headers(self) -> dict:
        return {
            'Content-type': 'application/json',
            'Authorization': f'Token {self.access_token}'
        }

    def test_fail_for_unknown_kyc(self):
        verification_id = uuid4().hex
        url = self.live_server_url + f'/api/kyc/{verification_id}'
        resp = requests.get(
            url,
            headers=self.headers
        )
        assert resp.status_code == 404

    def test_success(self):
        verification_id = uuid4().hex
        url = self.live_server_url + '/api/kyc'
        resp = requests.post(
            url,
            json={
                'id': verification_id,
                'document': base64.b64encode(b'1').decode(),
                'selfie': base64.b64encode(b'2').decode()
            },
            headers=self.headers
        )
        assert resp.status_code == 200
        retrieve = resp.json()
        assert retrieve

        photos = list(DBKYCPhoto.objects.filter(uid=verification_id).all())
        assert len(photos) == 2
        assert any(bytes(p.image) == base64.b64encode(b'1') for p in photos)
        assert any(bytes(p.image) == base64.b64encode(b'2') for p in photos)

    def test_scenario(self):
        verification_id = uuid4().hex
        url = self.live_server_url + '/api/kyc'

        resp = requests.post(
            url,
            json={
                'id': verification_id,
                'document': base64.b64encode(b'1111').decode(),
            },
            headers=self.headers
        )
        assert resp.status_code == 200
        retrieve1 = resp.json()
        assert retrieve1['document_is_set'] is True
        assert retrieve1['selfie_is_set'] is False
        assert retrieve1['account_fields']

        resp = requests.post(
            url,
            json={
                'id': verification_id,
                'selfie': base64.b64encode(b'0000').decode(),
                'account_fields': {
                    'phone': '+7-999-111-22-33'
                }
            },
            headers=self.headers
        )
        assert resp.status_code == 200
        retrieve2 = resp.json()
        assert retrieve2['document_is_set'] is True
        assert retrieve2['selfie_is_set'] is True
        assert retrieve2['account_fields']

        resp = requests.get(
            url=self.live_server_url + f'/api/kyc/{verification_id}',
            headers=self.headers
        )
        assert resp.status_code == 200
        retrieve3 = resp.json()
        assert retrieve3 == retrieve2
        assert retrieve2 != retrieve1

        # Get
        account_url = f'/api/kyc/{verification_id}/account'
        resp = requests.get(
            url=self.live_server_url + account_url,
            headers=self.headers
        )
        assert resp.status_code == 200
        account = Account.model_validate(resp.json())
        assert account.phone == '+7-999-111-22-33'
        # Edit
        resp = requests.put(
            url=self.live_server_url + account_url,
            json={
                'phone': '+7-222-111-22-33'
            },
            headers=self.headers
        )
        assert resp.status_code == 200
        account = Account.model_validate(resp.json())
        assert account.phone == '+7-222-111-22-33'

        # Clean existing fields
        resp = requests.put(
            url=self.live_server_url + account_url,
            json={
                'inn': '123456',
                'uid': 'xxx'
            },
            headers=self.headers
        )
        assert resp.status_code == 200
        account = Account.model_validate(resp.json())
        assert account.inn == '123456'
        assert account.phone is None
        assert account.uid != 'xxx'

        # Re-retrieve
        resp = requests.get(
            url=self.live_server_url + account_url,
            headers=self.headers
        )
        assert resp.status_code == 200
        account = Account.model_validate(resp.json())
        assert account.phone is None
        assert account.inn == '123456'
        assert account.is_verified is False

        # Register account
        resp = requests.post(
            url=self.live_server_url + account_url,
            json={},
            headers=self.headers
        )
        assert resp.status_code == 200
        account = Account.model_validate(resp.json())
        assert account
        assert account.inn == '123456'
        assert account.is_verified is True

        rec = DBAccount.objects.filter(uid=account.uid).first()
        assert rec and rec.phone == account.phone
        assert rec.kyc
        assert bytes(rec.kyc.image_b64_document) == base64.b64encode(b'1111')
        assert bytes(rec.kyc.image_b64_selfie) == base64.b64encode(b'0000')

        resp = requests.delete(
            url=self.live_server_url + f'/api/kyc/{verification_id}',
            headers=self.headers
        )
        assert resp.status_code == 204

        resp = requests.get(
            url=self.live_server_url + f'/api/kyc/{verification_id}',
            headers=self.headers
        )
        assert resp.status_code == 404


class TestMTSKYC(LiveServerTestCase):

    def setUp(self):
        super().setUp()
        path, section = '/workspaces/ruswift/tests/files/init.example.yml', 'exchange'
        if not os.path.isfile(path):
            raise RuntimeError(f'path "{path}" not exists')
        settings_ = parse_yaml_file_as(AnyCfg, path)
        if section:
            values = getattr(settings_, section)
        else:
            values = settings_
        self.cfg = ExchangeConfig.model_validate(values)
        asyncio.run(
            ExchangeConfigRepository.set(self.cfg)
        )

    @property
    def access_token(self) -> str:
        for user_id, desc in settings.API['AUTH'].items():
            if 'kyc' in desc.permissions:
                return desc.token
        raise AssertionError('Empty KYC token')

    @property
    def headers(self) -> dict:
        return {
            'Content-type': 'application/json',
            'Authorization': f'Token {self.access_token}'
        }

    def create_account(self) -> Account:
        account = Account(
            uid='some:account:' + uuid.uuid4().hex,
            phone='+7-911-120-92-22'
        )
        asyncio.run(AccountRepository.create_many([account]))
        return account

    def test_lifecycle(self):
        account = self.create_account()

        resp1 = requests.post(
            url=self.live_server_url + f'/api/kyc/mts',
            headers=self.headers,
            json={
                'account_uid': account.uid,
                'link_ttl_minutes': 300,
                #'redirect_url': 'https://redirect.com'
            }
        )
        assert resp1.status_code == 200

        resp2 = requests.get(
            url=self.live_server_url + f'/api/kyc/mts',
            headers=self.headers,
            params={
                'account_uid': account.uid
            }
        )
        assert resp2.status_code == 200
        assert len(resp2.json()) > 0

        id_ = resp1.json()['id']
        resp3 = requests.get(
            url=self.live_server_url + f'/api/kyc/mts/{id_}',
            headers=self.headers,
        )
        assert resp3.status_code == 200

        resp4 = requests.get(
            url=self.live_server_url + f'/api/kyc/mts/{id_}/status',
            headers=self.headers,
        )
        assert resp4.status_code == 200

        resp5 = requests.delete(
            url=self.live_server_url + f'/api/kyc/mts/clear_all?account_uid={account.uid}',
            headers=self.headers,
        )
        assert resp5.status_code == 204


class TestContactsVerify(LiveServerTestCase):

    def setUp(self):
        super().setUp()
        path, section = '/workspaces/ruswift/tests/files/init.example.yml', 'exchange'
        if not os.path.isfile(path):
            raise RuntimeError(f'path "{path}" not exists')
        settings_ = parse_yaml_file_as(AnyCfg, path)
        if section:
            values = getattr(settings_, section)
        else:
            values = settings_
        self.cfg = ExchangeConfig.model_validate(values)
        asyncio.run(
            ExchangeConfigRepository.set(self.cfg)
        )

    @property
    def headers(self) -> dict:
        return {
            'Content-type': 'application/json',
        }

    def test_sane(self):
        anonym = requests.get(
            url=self.live_server_url
        )
        assert anonym.status_code == 200
        session_uid = anonym.cookies.get('session_uid')
        assert session_uid

        url = self.live_server_url + f'/api/contact-verify'

        resp1 = requests.get(
            url=url,
            cookies={'session_uid': session_uid}
        )
        assert resp1.status_code == 200

        resp2 = requests.post(
            url=url,
            cookies={'session_uid': session_uid},
            headers=self.headers,
            json={
                'id': 'phone',
                'value': '79112223344',
                'ttl': 60
            }
        )
        assert resp2.status_code == 200

        resp3 = requests.post(
            url=url,
            cookies={'session_uid': session_uid},
            headers=self.headers,
            json={
                'id': 'phone',
                'code': '0000'
            }
        )
        assert resp3.status_code == 200
        obj = resp3.json()
        assert obj['id'] == 'phone'
        assert obj['value'] == '79112223344'
        assert obj['verified'] is True

        resp4 = requests.post(
            url=url,
            cookies={'session_uid': session_uid},
            headers=self.headers,
            json={
                'id': 'email',
                'value': 'x@gmail.com',
                'ttl': 360
            }
        )
        assert resp4.status_code == 200

        resp5 = requests.post(
            url=url + '/accept',
            cookies={'session_uid': session_uid},
            headers=self.headers,
            json={}
        )
        assert resp5.status_code == 200

        resp6 = requests.get(
            url=self.live_server_url + f'/api/accounts/iam',
            cookies={'session_uid': session_uid},
            headers=self.headers
        )
        assert resp6.status_code == 200
        acc = Account.model_validate(resp6.json())
        assert acc.phone == '79112223344'
        assert acc.verified.phone is True
        assert acc.email == 'x@gmail.com'
        assert acc.verified.email is False


class TestRegistration(LiveServerTestCase):

    def setUp(self):
        super().setUp()
        path, section = '/workspaces/ruswift/tests/files/init.example.yml', 'exchange'
        if not os.path.isfile(path):
            raise RuntimeError(f'path "{path}" not exists')
        settings_ = parse_yaml_file_as(AnyCfg, path)
        if section:
            values = getattr(settings_, section)
        else:
            values = settings_
        self.cfg = ExchangeConfig.model_validate(values)
        asyncio.run(
            ExchangeConfigRepository.set(self.cfg)
        )

    def create_root(self, token: str) -> Account:
        account = Account(
            uid='root:' + uuid.uuid4().hex,
            phone='+7-911-120-92-22',
            permissions=['root']
        )
        asyncio.run(AccountRepository.create_many([account]))
        asyncio.run(TokenAuth.register(
            account, {'token': token}
        ))
        return account

    @classmethod
    def headers(cls, extra = None) -> dict:
        hdr = {
            'Content-type': 'application/json',
        }
        if extra:
            for k,v in extra.items():
                hdr[k] = v
        return hdr

    def test_sane(self):
        root_token = uuid4().hex
        root = self.create_root(root_token)

        resp_reg = requests.post(
            url=self.live_server_url + f'/api/kyc/mts/create_registration_link',
            headers=self.headers(extra={'Token': root_token}),
            json={
                'registration': True,
            }
        )
        assert resp_reg.status_code == 200
        reg_link_id = resp_reg.json()['id']

        # Заходим на страницу регистрации аккаунта
        anonym = requests.get(
            url=self.live_server_url + '/register/' + reg_link_id
        )
        assert anonym.status_code == 200
        session_uid = anonym.cookies.get('session_uid')
        assert session_uid

        # Апдейтим поля
        resp_retrieve = requests.get(
            url=self.live_server_url + '/api/register/' + reg_link_id,
            cookies={'session_uid': session_uid},
            headers=self.headers()
        )
        assert resp_retrieve.status_code == 200

        resp_update = requests.put(
            url=self.live_server_url + '/api/register/' + reg_link_id,
            cookies={'session_uid': session_uid},
            headers=self.headers(),
            json={
                'fields': {
                    'first_name': 'First Name',
                    'last_name': 'Last Name'
                }
            }
        )
        assert resp_update.status_code == 200

        # Подтвердим номер тлф
        resp_ver1 = requests.post(
            url=self.live_server_url + f'/api/contact-verify',
            cookies={'session_uid': session_uid},
            headers=self.headers(),
            json={
                'id': 'phone',
                'value': '79112223344',
                'ttl': 60
            }
        )
        assert resp_ver1.status_code == 200

        resp_ver2 = requests.post(
            url=self.live_server_url + f'/api/contact-verify',
            cookies={'session_uid': session_uid},
            headers=self.headers(),
            json={
                'id': 'phone',
                'code': '0000'
            }
        )
        assert resp_ver2.status_code == 200

        # Регистрируем аккаунт
        resp_accept = requests.post(
            url=self.live_server_url + '/api/register/' + reg_link_id + '/accept',
            cookies={'session_uid': session_uid},
            headers=self.headers(),
            json={}
        )
        assert resp_accept.status_code == 200
        new_session_uid = resp_accept.cookies.get('session_uid')
        assert new_session_uid != session_uid

        # проверяем что данные применились
        resp_iam = requests.get(
            url=self.live_server_url + '/api/accounts/iam',
            cookies={'session_uid': new_session_uid},
            headers=self.headers(),
        )
        assert resp_iam.status_code == 200
        acc = Account.model_validate(resp_iam.json())
        assert acc.first_name == 'First Name'
        assert acc.last_name == 'Last Name'
        assert acc.phone == '79112223344'
        assert acc.verified.phone is True

    def test_regenerate_link_for_specific_reg_link(self):
        root_token = uuid4().hex
        root = self.create_root(root_token)

        resp_reg = requests.post(
            url=self.live_server_url + f'/api/kyc/mts/create_registration_link',
            headers=self.headers(extra={'Token': root_token}),
            json={
                'registration': True,
            }
        )
        assert resp_reg.status_code == 200
        reg_link_id = resp_reg.json()['id']

        # Заходим на страницу регистрации аккаунта
        anonym = requests.get(
            url=self.live_server_url + '/register/' + reg_link_id
        )
        assert anonym.status_code == 200
        session_uid = anonym.cookies.get('session_uid')
        assert session_uid

        # regenerate for specific id
        resp1 = requests.post(
            url=self.live_server_url + f'/api/register/' + reg_link_id + '/regenerate',
            headers=self.headers(),
            cookies={'session_uid': session_uid},
            json={}
        )
        assert resp1.status_code == 200
        reg_link_id2 = resp1.json()['id']
        assert reg_link_id2 != reg_link_id

    def test_regenerate_custom(self):
        # Заходим на страницу регистрации аккаунта
        anonym = requests.get(
            url=self.live_server_url + '/register'
        )
        assert anonym.status_code == 200
        session_uid = anonym.cookies.get('session_uid')
        assert session_uid

        # regenerate for specific id
        resp1 = requests.post(
            url=self.live_server_url + f'/api/register/regenerate',
            headers=self.headers(),
            cookies={'session_uid': session_uid},
            json={}
        )
        assert resp1.status_code == 200


class TestAccounts(LiveServerTestCase):

    def setUp(self):
        super().setUp()
        path, section = '/workspaces/ruswift/tests/files/init.example.yml', 'exchange'
        if not os.path.isfile(path):
            raise RuntimeError(f'path "{path}" not exists')
        settings_ = parse_yaml_file_as(AnyCfg, path)
        if section:
            values = getattr(settings_, section)
        else:
            values = settings_
        self.cfg = ExchangeConfig.model_validate(values)
        asyncio.run(
            ExchangeConfigRepository.set(self.cfg)
        )

    @property
    def access_token(self) -> str:
        for user_id, desc in settings.API['AUTH'].items():
            if 'kyc' in desc.permissions and 'accounts' in desc.permissions:
                return desc.token
        raise AssertionError('Empty KYC token')

    @property
    def headers(self) -> dict:
        return {
            'Content-type': 'application/json',
            'Authorization': f'Token {self.access_token}'
        }

    @property
    def base_path(self) -> str:
        return '/app/exchange/tests/files/kyc/beorg'

    @property
    def doc_path(self) -> str:
        return os.path.join(self.base_path, 'success_passport.pdf')

    @property
    def selfie_path(self) -> str:
        return os.path.join(self.base_path, 'selfie.jpeg')

    def test_sane(self):
        for n in range(10):
            DBAccount.objects.create(uid=f'uid-{n}')

        url = f'/api/accounts'
        resp = requests.get(
            url=self.live_server_url + url,
            headers=self.headers
        )
        assert resp.status_code == 200
        values1 = resp.json()
        assert len(values1) == 10
        assert resp.headers.get('X-Total-Count') == '10'

        resp = requests.get(
            url=self.live_server_url + url,
            params={'limit': 5, 'offset': 2},
            headers=self.headers
        )
        assert resp.status_code == 200
        values2 = resp.json()
        assert len(values2) == 3
        assert resp.headers.get('X-Total-Count') == '10'

        resp = requests.get(
            url=self.live_server_url + url,
            params={'order_by': '-id'},
            headers=self.headers
        )
        assert resp.status_code == 200

    def test_iam(self):
        url = f'/api/accounts/iam'
        resp = requests.get(
            url=self.live_server_url + url,
            headers=self.headers
        )
        assert resp.status_code == 200
        account = resp.json()
        assert account

        other_account_uid = 'some-account'
        DBAccount.objects.create(uid=other_account_uid)
        grant_headers = self.headers
        grant_headers['X-Grant'] = other_account_uid
        resp = requests.get(
            url=self.live_server_url + url,
            headers=grant_headers
        )
        assert resp.status_code == 200
        account = resp.json()
        assert account
        assert account['uid'] == other_account_uid

        # some-account don't have perms to other account methods
        resp = requests.get(
            url=self.live_server_url + f'/api/accounts',
            headers=grant_headers
        )
        assert resp.status_code == 403

    def test_iam_for_anonymous_session(self):
        url = f'/api/accounts/iam'
        resp = requests.get(
            url=self.live_server_url + url
        )
        assert resp.status_code == 404

    def test_filter_by_attrs(self):
        dbs = {}
        for n in range(10):
            rec = DBAccount.objects.create(
                uid=f'uid-{n}', telegram=f'@tg{n}'
            )
            dbs[rec.uid] = rec

        first = dbs[list(dbs.keys())[0]]
        url = f'/api/accounts'
        resp = requests.get(
            url=self.live_server_url + url,
            headers=self.headers,
            params={'uid': first.uid}
        )
        assert resp.status_code == 200
        values1 = resp.json()
        assert len(values1) == 1

        url = f'/api/accounts/{first.uid}'
        resp = requests.get(
            url=self.live_server_url + url,
            headers=self.headers,
            params={'uid': first.uid}
        )
        assert resp.status_code == 200
        values2 = resp.json()
        assert values2 == values1[0]

    def test_account_kyc_2_schema(self):
        account = DBAccount.objects.create(uid=uuid.uuid4().hex)
        url = self.live_server_url + f'/api/accounts/{account.uid}/verify'
        resp1 = requests.post(
            url,
            json={
                'provider_class': 'kyc.FakeKYCProvider',
                'document': base64.b64encode(b'1').decode(),
                'selfie': base64.b64encode(b'2').decode()
            },
            headers=self.headers
        )
        assert resp1.status_code == 200

        account.refresh_from_db()
        assert account.is_verified is True

        url = self.live_server_url + f'/api/accounts/{account.uid}/kyc'
        resp2 = requests.get(url, headers=self.headers)
        assert resp2.status_code == 200
        assert resp2.json()['verify'] == resp1.json()

    def test_account_create_or_update(self):
        url = self.live_server_url + f'/api/accounts/update_or_create'
        resp1 = requests.post(
            url,
            json=dict(first_name='Name', email='x@server.com'),
            headers=self.headers
        )
        assert resp1.status_code == 200
        assert resp1.json()['first_name'] == 'Name'
        assert resp1.json()['email'] == 'x@server.com'
        assert resp1.json()['is_verified'] is False

        resp_alone = requests.post(
            url,
            json=dict(first_name='Name'),
            headers=self.headers
        )
        assert resp_alone.status_code == 200

        resp2 = requests.post(
            url,
            json=dict(first_name='Name-Updated'),
            headers=self.headers,
            params={'email': 'x@server.com'}
        )
        assert resp2.status_code == 200
        assert resp2.json()['first_name'] == 'Name-Updated'
        assert resp2.json()['email'] == 'x@server.com'
        assert resp2.json()['uid'] == resp1.json()['uid']

        resp3 = requests.post(
            url,
            json=dict(is_verified=True),
            headers=self.headers,
            params={'uid': resp1.json()['uid']}
        )
        assert resp3.status_code == 200
        assert resp3.json()['is_verified'] is True

    def test_account_update(self):
        auth_token = uuid.uuid4().hex
        account: Account = asyncio.run(
            AccountRepository.create(
                uid=uuid.uuid4().hex, is_active=True
            )
        )
        cred = asyncio.run(
            TokenAuth.register(
                account=account,
                payload={'token': auth_token}
            )
        )
        url = self.live_server_url + f'/api/accounts/{account.uid}?token={auth_token}'
        resp = requests.put(
            url,
            json=dict(first_name='Name-Updated', email='updated@server.com')
        )
        assert resp.status_code == 200
        assert resp.json()['first_name'] == 'Name-Updated'
        assert resp.json()['email'] == 'updated@server.com'

    def test_merchant_update(self):
        root_token = uuid.uuid4().hex
        root: Account = asyncio.run(
            AccountRepository.create(
                uid=uuid.uuid4().hex, permissions=['root'], is_active=True
            )
        )
        merchant: Account = asyncio.run(
            AccountRepository.create(
                uid='babapay', permissions=['merchant'], is_active=True
            )
        )

        cred = asyncio.run(
            TokenAuth.register(
                account=root,
                payload={'token': root_token}
            )
        )

        # в первый раз не инициализируем ledger
        merchant_meta = dict(
            title='Test merchant',
            base_currency='RUB',
            url='https://test.ruswift.ru',
            mass_payments=dict(
                enabled=True,
                asset=dict(
                    code='USDTTRC20',
                    address='TVFysSZPcid6KiDUEs1byFcjwPqsQqaXfX'
                ),
                ratios=dict(
                    engine='GarantexEngine',
                    base='RUB',
                    quote='USDT'
                ),
            ),
        )

        url = self.live_server_url + f'/api/accounts/{merchant.uid}/update_merchant?token={root_token}'
        resp1 = requests.post(
            url,
            json=merchant_meta
        )
        assert resp1.status_code == 200

        # 2. Отключаем Ledger
        merchant_meta['mass_payments']['enabled'] = False
        resp2 = requests.post(
            url,
            json=merchant_meta
        )
        assert resp2.status_code == 200

        # 3. Включае Ledger и меняем
        merchant_meta = resp2.json()
        merchant_meta['mass_payments']['enabled'] = True
        merchant_meta['mass_payments']['ledger']['participants']['guarantor'] = ['did:web:ruswift.ru:guarant']
        resp3 = requests.post(
            url,
            json=merchant_meta
        )
        assert resp3.status_code == 200

        # 4. check ledgers
        resp4 = requests.get(
            url=self.live_server_url + f'/api/ledgers?token={root_token}',
            json=merchant_meta
        )
        assert resp4.status_code == 200
        assert len(resp4.json()) > 0

    def test_admin(self):
        root_token = uuid.uuid4().hex
        root: Account = asyncio.run(
            AccountRepository.create(
                uid=uuid.uuid4().hex, permissions=['root'], is_active=True
            )
        )
        cred = asyncio.run(
            TokenAuth.register(
                account=root,
                payload={'token': root_token}
            )
        )
        account: Account = asyncio.run(
            AccountRepository.create(
                uid=uuid4().hex, permissions=[], is_active=True,
                first_name='BlaBlaBla'
            )
        )
        cred = asyncio.run(
            TokenAuth.register(
                account=account,
                payload={'token': uuid4().hex}
            )
        )
        # 1. check initial model
        resp1 = requests.get(
            url=self.live_server_url + f'/api/accounts/{account.uid}',
            headers={
                'Content-type': 'application/json',
                'Token': root_token
            }
        )
        assert resp1.status_code == 200
        # 2. admin call
        resp2 = requests.post(
            url=self.live_server_url + f'/api/accounts/{account.uid}/admin',
            headers={
                'Content-type': 'application/json',
                'Token': root_token
            },
            json={
                'permissions': ['operator'],
                'is_verified': False,
                'is_organization': True,
                'verified': {
                    'phone': True
                 }
            }
        )
        assert resp2.status_code == 200
        assert resp2.json()['is_organization'] is True
        assert resp2.json()['verified']['phone'] is True
        assert resp2.json()['first_name'] == 'BlaBlaBla'

        # 3. проверим что методы update не затирают админские поля
        resp3 = requests.put(
            url=self.live_server_url + f'/api/accounts/{account.uid}',
            headers={
                'Content-type': 'application/json',
                'Token': root_token
            },
            json={
                'first_name': 'NewName',
            }
        )
        assert resp3.status_code == 200
        assert resp3.json()['is_organization'] is True
        assert resp3.json()['verified']['phone'] is True
        assert resp3.json()['first_name'] == 'NewName'

    def test_auth(self):
        root_token = uuid.uuid4().hex
        root: Account = asyncio.run(
            AccountRepository.create(
                uid=uuid.uuid4().hex, permissions=['root'], is_active=True
            )
        )
        cred = asyncio.run(
            TokenAuth.register(
                account=root,
                payload={'token': root_token}
            )
        )
        account: Account = asyncio.run(
            AccountRepository.create(
                uid=uuid4().hex, permissions=[], is_active=True,
                first_name='BlaBlaBla'
            )
        )
        resp1 = requests.get(
            url=self.live_server_url + f'/api/accounts/{account.uid}/auth',
            headers={
                'Content-type': 'application/json',
                'Token': root_token
            },
        )
        assert resp1.status_code == 200
        assert len(resp1.json()['auths']) == 0

        resp2 = requests.post(
            url=self.live_server_url + f'/api/accounts/{account.uid}/auth',
            headers={
                'Content-type': 'application/json',
                'Token': root_token
            },
            json={
                'auths': [
                    {
                        'operation': 'create',
                        'class': 'Login',
                        'settings': {
                            'login': 'test',
                            'password': 'password'
                        }
                    }
                ],
            }
        )
        assert resp2.status_code == 200
        assert len(resp2.json()['auths']) == 1

        resp3 = requests.post(
            url=self.live_server_url + f'/api/accounts/{account.uid}/auth',
            headers={
                'Content-type': 'application/json',
                'Token': root_token,
            },
            json={
                'auths': [
                    {
                        'operation': 'remove',
                        'class': 'Login'
                    }
                ],
            }
        )
        assert resp3.status_code == 200
        assert len(resp3.json()['auths']) == 0

    def test_organization_onboard(self):
        account = DBAccount.objects.create(
            uid=uuid.uuid4().hex, is_organization=True
        )
        url1 = self.live_server_url + f'/api/accounts/{account.uid}/document'

        resp1 = requests.post(
            url1,
            json=dict(
                photo=base64.b64encode(b'111').decode(),
                attrs=dict(attr1='val1', attr2=123),
                type='some-type'
            ),
            headers=self.headers,
        )
        assert resp1.status_code == 200
        doc1 = resp1.json()
        assert doc1['attrs'] == dict(attr1='val1', attr2=123)
        assert doc1['type'] == 'some-type'
        assert doc1['document']['type'] == 'document'
        assert doc1['document']['image'] == base64.b64encode(b'111').decode()

        resp2 = requests.get(
            url1,
            headers=self.headers,
        )
        assert resp2.status_code == 200
        docs = resp2.json()
        assert docs[0] == doc1

        url2 = self.live_server_url + f'/api/accounts/{account.uid}/document/{doc1["id"]}'
        resp3 = requests.get(
            url2,
            headers=self.headers,
        )
        assert resp3.status_code == 200
        assert resp3.json() == doc1

        # TODO: добить тесты на Update/Remove
        resp4 = requests.put(
            url2,
            json={
                'photo': base64.b64encode(b'222').decode(),
                'attrs': dict(attr3='val3', attr4=444),
                'type': 'some-type2'
            },
            headers=self.headers,
        )
        assert resp4.status_code == 200
        doc2 = resp4.json()
        assert doc2['attrs'] == dict(attr3='val3', attr4=444)
        assert doc2['type'] == 'some-type2'
        assert doc2['document']['type'] == 'document'
        assert doc2['document']['image'] == base64.b64encode(b'222').decode()

        resp5 = requests.delete(
            url2,
            headers=self.headers
        )
        assert resp5.status_code == 204

        resp6 = requests.get(
            url1,
            headers=self.headers,
        )
        assert resp6.status_code == 200
        docs = resp6.json()
        assert docs == []


class AnyCfg(BaseModel, extra=Extra.allow):
    ...


class TestMassPayments(LiveServerTestCase):

    token_cred: dict

    def setUp(self):
        super().setUp()
        path, section = '/workspaces/ruswift/tests/files/init.example.yml', 'exchange'
        if not os.path.isfile(path):
            raise RuntimeError(f'path "{path}" not exists')
        settings_ = parse_yaml_file_as(AnyCfg, path)
        if section:
            values = getattr(settings_, section)
        else:
            values = settings_
        self.cfg = ExchangeConfig.model_validate(values)
        d = [m for u, m in self.cfg.merchants.items() if u == 'koan'][0]
        merchant = MerchantMeta.model_validate(d)
        assert len(merchant.auth) > 0
        self.merchant: MerchantMeta = merchant
        self.token_cred = [a.settings for a in merchant.auth if a.class_ == 'TokenAuth'][0]
        asyncio.run(
            ExchangeConfigRepository.set(self.cfg)
        )
        asyncio.run(
            update_merchants_config(self.cfg)
        )

    @property
    def headers(self) -> dict:
        return {
            'Content-type': 'application/json',
            'Token': self.token_cred['token']
        }

    def test_make_order(self):
        url = self.live_server_url + f'/api/mass-payments'
        order_id = uuid.uuid4().hex
        create = requests.post(
            url,
            json={
                'transaction': {
                    'order_id': order_id,
                    'description': 'Test description',
                    'amount': 10000.0,
                    'currency': 'RUB'
                },
                'customer': {
                    'identifier': 'ivan@sidorov.ru',
                    'display_name': 'Ivan Sidorov',
                    'email': 'ivan@sidorov.ru',
                },
                'card': {
                    'number': '22001112200005555',
                    'expiration_date': '10/30'
                },
                'proof': {
                    'url': 'https://domain.com/doc.pdf',
                    'mime_type': 'application/pdf'
                }
            },
            headers=self.headers
        )
        assert create.status_code == 200
        assert create.json()['id'] == order_id
        assert create.json()['proof']['url'] == 'https://domain.com/doc.pdf'
        assert create.json()['utc']

        read = requests.get(
            url + f'/{order_id}', headers=self.headers
        )
        assert read.status_code == 200
        assert read.json()

        status = requests.get(
            url + f'/{order_id}/status', headers=self.headers
        )
        assert status.status_code == 200
        assert status.json()

    def test_deny_order_with_duplicates(self):
        """По просьбе KOAN сделать проверку на дубли order_id
        """
        url = self.live_server_url + f'/api/mass-payments'
        order_id = '12345'
        # 1. Mass operation
        create = requests.post(
            url,
            json=[
                {
                    'transaction': {'order_id': order_id, 'description': 'Test description', 'amount': 10000.0,'currency': 'RUB'},
                    'customer': {'identifier': 'ivan@sidorov.ru','display_name': 'Ivan Sidorov','email': 'ivan@sidorov.ru',},
                    'card': {'number': '22001112200005555','expiration_date': '10/30'},
                    'proof': {'url': 'https://domain.com/doc.pdf','mime_type': 'application/pdf'}
                },
                {
                    'transaction': {'order_id': order_id,'description': 'Test description','amount': 10000.0,'currency': 'RUB'},
                    'customer': {'identifier': 'ivan@sidorov.ru','display_name': 'Ivan Sidorov','email': 'ivan@sidorov.ru',},
                    'card': {'number': '22001112200005555','expiration_date': '10/30'},
                    'proof': {'url': 'https://domain.com/doc.pdf','mime_type': 'application/pdf'}
                }
            ],
            headers=self.headers
        )
        assert create.status_code == 400

        # 2. Creat order and then try to create with same order_id
        create = requests.post(
            url,
            json={
                'transaction': {'order_id': order_id, 'description': 'Test description','amount': 10000.0, 'currency': 'RUB'},
                'customer': {'identifier': 'ivan@sidorov.ru','display_name': 'Ivan Sidorov','email': 'ivan@sidorov.ru', },
                'card': {'number': '22001112200005555','expiration_date': '10/30'},
                'proof': {'url': 'https://domain.com/doc.pdf','mime_type': 'application/pdf'}
            },
            headers=self.headers
        )
        assert create.status_code == 200

        create2 = requests.post(
            url,
            json={
                'transaction': {'order_id': order_id,'description': 'Test description','amount': 10000.0, 'currency': 'RUB'},
                'customer': {'identifier': 'ivan@sidorov.ru','display_name': 'Ivan Sidorov','email': 'ivan@sidorov.ru', },
                'card': {'number': '22001112200005555','expiration_date': '10/30'},
                'proof': {'url': 'https://domain.com/doc.pdf','mime_type': 'application/pdf'}
            },
            headers=self.headers
        )
        assert create2.status_code == 400

        create3 = requests.post(
            url,
            json=[
                {
                    'transaction': {'order_id': order_id,'description': 'Test description','amount': 10000.0, 'currency': 'RUB'},
                    'customer': {'identifier': 'ivan@sidorov.ru','display_name': 'Ivan Sidorov','email': 'ivan@sidorov.ru', },
                    'card': {'number': '22001112200005555','expiration_date': '10/30'},
                    'proof': {'url': 'https://domain.com/doc.pdf','mime_type': 'application/pdf'}
                },
                {
                    'transaction': {'order_id': '11111111','description': 'Test description','amount': 10000.0, 'currency': 'RUB'},
                    'customer': {'identifier': 'ivan@sidorov.ru','display_name': 'Ivan Sidorov','email': 'ivan@sidorov.ru', },
                    'card': {'number': '22001112200005555','expiration_date': '10/30'},
                    'proof': {'url': 'https://domain.com/doc.pdf','mime_type': 'application/pdf'}
                }
            ],
            headers=self.headers
        )
        assert create3.status_code == 400

    def test_make_order_multiple(self):
        url = self.live_server_url + f'/api/mass-payments'
        order_id1, order_id2 = uuid.uuid4().hex, uuid.uuid4().hex
        create = requests.post(
            url,
            json=[
                {
                    'transaction': {
                        'order_id': order_id1,
                        'description': 'Test description',
                        'amount': 10000.0,
                        'currency': 'RUB'
                    },
                    'customer': {
                        'identifier': 'ivan@sidorov.ru',
                        'display_name': 'Ivan Sidorov',
                        'email': 'ivan@sidorov.ru',
                    },
                    'card': {
                        'number': '22001112200005555',
                        'expiration_date': '10/30'
                    }
                },
                {
                    'transaction': {
                        'order_id': order_id2,
                        'description': 'Test description',
                        'amount': 30000.0,
                        'currency': 'RUB'
                    },
                    'customer': {
                        'identifier': 'petr@ivanov.ru',
                        'display_name': 'Petr Ivanov',
                        'email': 'petr@ivanov.ru',
                    },
                    'card': {
                        'number': '22001112200005555',
                        'expiration_date': '10/30'
                    }
                }
            ],
            headers=self.headers
        )
        assert create.status_code == 200
        assert len(create.json()) == 2

        si = list(DBStorageItem.objects.filter(
            payload__transaction__order_id__in=[order_id1, order_id2]
        ).all())
        assert len(si) == 4  # по 1 записи для мерчанта и для оператора платежей

        read = requests.get(
            url, headers=self.headers
        )
        assert read.status_code == 200
        assert len(read.json()) == 2
        read_order_ids = [o['id'] for o in read.json()]
        assert order_id1 in read_order_ids
        assert order_id2 in read_order_ids

        read = requests.get(
            url + '/status', headers=self.headers
        )
        assert read.status_code == 200
        assert len(read.json()) == 2

    def test_filters_with_retrieve(self):
        url = self.live_server_url + f'/api/mass-payments'
        order_id_pending, order_id_error, order_id_success = uuid.uuid4().hex, uuid.uuid4().hex, uuid.uuid4().hex
        create = requests.post(
            url,
            json=[
                {
                    'transaction': {'order_id': order_id_pending, 'description': 'Test description', 'amount': 10000.0, 'currency': 'RUB'},
                    'customer': {'identifier': 'ivan@sidorov.ru', 'display_name': 'Ivan Sidorov', 'email': 'ivan@sidorov.ru',},
                    'card': {'number': '22001112200005555', 'expiration_date': '10/30'}
                },
                {
                    'transaction': {'order_id': order_id_error, 'description': 'Test description','amount': 30000.0, 'currency': 'RUB'},
                    'customer': {'identifier': 'petr@ivanov.ru', 'display_name': 'Petr Ivanov', 'email': 'petr@ivanov.ru',},
                    'card': {'number': '22001112200005555', 'expiration_date': '10/30'}
                },
                {
                    'transaction': {'order_id': order_id_success,'description': 'Test description','amount': 30000.0, 'currency': 'RUB'},
                    'customer': {'identifier': 'petr@ivanov.ru', 'display_name': 'Petr Ivanov','email': 'petr@ivanov.ru', },
                    'card': {'number': '22001112200005555', 'expiration_date': '10/30'}
                }
            ],
            headers=self.headers
        )
        assert create.status_code == 200
        items = create.json()
        assert len(items) == 3
        uid_pending = [i['uid'] for i in items if i['transaction']['order_id'] == order_id_pending][0]
        uid_error = [i['uid'] for i in items if i['transaction']['order_id'] == order_id_error][0]
        uid_success = [i['uid'] for i in items if i['transaction']['order_id'] == order_id_success][0]

        root_token = uuid.uuid4().hex
        asyncio.run(
            create_superuser(
                uid='test:root-234',
                credentials=[
                    TokenAuth.TokenCredential(
                        token=root_token
                    )
                ]
            )
        )
        root_access_header = {
            'Token': root_token
        }

        for uid, status in [(uid_error, 'error'), (uid_success, 'success')]:
            resp = requests.post(
                self.live_server_url + f'/api/control-panel/{self.merchant.identity.did.root}/mass-payments/status',
                json={
                    'uid': uid,
                    'status': status,
                    'message': f'Set status to {status}'
                },
                headers=root_access_header
            )
            assert resp.status_code == 200

        # Get records
        resp = requests.get(
            self.live_server_url + f'/api/control-panel/{self.merchant.identity.did.root}/mass-payments',
            headers=root_access_header
        )
        assert resp.status_code == 200
        records = {}
        for i in resp.json():
            records[i['uid']] = i

        assert records[uid_pending]['status']['status'] == 'pending'
        assert records[uid_error]['status']['status'] == 'error'
        assert records[uid_success]['status']['status'] == 'success'

        # Filter with status pending
        resp = requests.get(
            self.live_server_url + f'/api/control-panel/{self.merchant.identity.did.root}/mass-payments?status=pending',
            headers=root_access_header
        )
        assert resp.status_code == 200
        records = {}
        for i in resp.json():
            records[i['uid']] = i
        assert uid_pending in records
        assert len(records) == 1

        # Filter with status error & pending
        resp = requests.get(
            self.live_server_url + f'/api/control-panel/{self.merchant.identity.did.root}/mass-payments?status=error&status=pending',
            headers=root_access_header
        )
        assert resp.status_code == 200
        records = {}
        for i in resp.json():
            records[i['uid']] = i
        assert uid_pending in records
        assert uid_error in records
        assert len(records) == 2

        # Filter with status success
        resp = requests.get(
            self.live_server_url + f'/api/control-panel/{self.merchant.identity.did.root}/mass-payments?status=success',
            headers=root_access_header
        )
        assert resp.status_code == 200
        records = {}
        for i in resp.json():
            records[i['uid']] = i
        assert uid_success in records
        assert len(records) == 1
        
        # Filter for attachment can be broken
        attach_uid = 'pdf_uid-' + uuid.uuid4().hex
        resp = requests.post(
            self.live_server_url + f'/api/control-panel/{self.merchant.identity.did.root}/mass-payments/attachments',
            json=[
                {
                    'uid': attach_uid,
                    'name': 'Document.pdf',
                    'data': DATA_URL_PDF
                }
            ],
            headers=root_access_header
        )
        assert resp.status_code == 200
        upd = requests.post(
            self.live_server_url + f'/api/control-panel/{self.merchant.identity.did.root}/mass-payments/status',
            json=[
                {
                    'uid': uid_pending,
                    'status': 'attachment',
                    'payload': {
                        'attachments': [
                            {'uid': attach_uid}
                        ]
                    }
                }
            ],
            headers=root_access_header
        )
        assert upd.status_code == 200
        resp = requests.get(
            self.live_server_url + f'/api/control-panel/{self.merchant.identity.did.root}/mass-payments?status=pending',
            headers=root_access_header
        )
        assert resp.status_code == 200
        records = {}
        for i in resp.json():
            records[i['uid']] = i
        assert uid_pending in records
        assert len(records) == 1

    def test_assets(self):
        url = self.live_server_url + f'/api/mass-payments/assets'
        assets = requests.get(
            url, headers=self.headers
        )
        assert assets.status_code == 200
        assert assets.json()

        # update webhook
        assets = requests.post(
            url,
            json={
                'webhook': 'https://server.com/xxx'
            },
            headers=self.headers
        )
        assert assets.status_code == 200
        assert assets.json().get('webhook') == 'https://server.com/xxx'

    def test_status_history(self):
        root_token = uuid.uuid4().hex
        asyncio.run(
            create_superuser(
                uid='test:root',
                credentials=[
                    TokenAuth.TokenCredential(
                        token=root_token
                    )
                ]
            )
        )
        root_access_header = {
            'Token': root_token
        }

        create = requests.post(
            self.live_server_url + f'/api/mass-payments',
            json={
                'transaction': {
                    'order_id': uuid.uuid4().hex,
                    'description': 'Test description',
                    'amount': 10000.0,
                    'currency': 'RUB'
                },
                'customer': {
                    'identifier': 'ivan@sidorov.ru',
                    'display_name': 'Ivan Sidorov',
                    'email': 'ivan@sidorov.ru',
                },
                'card': {
                    'number': '22001112200005555',
                    'expiration_date': '10/30'
                },
                'proof': {
                    'url': 'https://domain.com/doc.pdf',
                    'mime_type': 'application/pdf'
                }
            },
            headers=self.headers
        )
        assert create.status_code == 200
        uid = create.json()['uid']
        creation_utc = create.json()['utc']

        # Запросим историю
        history = requests.get(
            self.live_server_url + f'/api/control-panel/{self.merchant.identity.did.root}/mass-payments/{uid}/history',
            headers=root_access_header
        )
        assert history.status_code == 200
        assert len(history.json()) == 1
        assert history.json()[0]['utc'] == creation_utc

        # Обновим статус
        attach_payload = {
            'attachments': ['xxx', 'zzz']
        }
        upd = requests.post(
            self.live_server_url + f'/api/control-panel/{self.merchant.identity.did.root}/mass-payments/status',
            json=[
                {
                    'uid': uid,
                    'status': 'attachment',
                    'payload': attach_payload
                }
            ],
            headers=root_access_header
        )
        assert upd.status_code == 200
        obj = upd.json()[0]
        assert obj['status'] == 'pending'
        assert obj['payload'] == None

        # снова запросим историю
        for url, auth_hdr in [
            (
                self.live_server_url + f'/api/control-panel/{self.merchant.identity.did.root}/mass-payments/{uid}/history',
                root_access_header
            ),
            (
                self.live_server_url + f'/api/mass-payments/{uid}/history',
                self.headers
            )
        ]:
            retrieved = requests.get(
                url,
                headers=auth_hdr
            )
            assert retrieved.status_code == 200
            assert len(retrieved.json()) == 2
            first, second = retrieved.json()
            assert first['status'] == 'created'
            assert second['status'] == 'attachment'
            assert second['payload'] == attach_payload

    def test_status_lifecycle(self):
        root_token = uuid.uuid4().hex
        asyncio.run(
            create_superuser(
                uid='test:root2',
                credentials=[
                    TokenAuth.TokenCredential(
                        token=root_token
                    )
                ]
            )
        )
        root_access_header = {
            'Token': root_token
        }

        create = requests.post(
            self.live_server_url + f'/api/mass-payments',
            json={
                'transaction': {
                    'order_id': uuid.uuid4().hex,
                    'description': 'Test description',
                    'amount': 10000.0,
                    'currency': 'RUB'
                },
                'customer': {
                    'identifier': 'ivan@sidorov.ru',
                    'display_name': 'Ivan Sidorov',
                    'email': 'ivan@sidorov.ru',
                },
                'card': {
                    'number': '22001112200005555',
                    'expiration_date': '10/30'
                },
                'proof': {
                    'url': 'https://domain.com/doc.pdf',
                    'mime_type': 'application/pdf'
                }
            },
            headers=self.headers
        )
        assert create.status_code == 200
        uid = create.json()['uid']

        resp = requests.get(
            self.live_server_url + f'/api/control-panel/{self.merchant.identity.did.root}/mass-payments/{uid}/status',
            headers=root_access_header
        )
        assert resp.status_code == 200
        status1 = resp.json()

        process = requests.post(
            self.live_server_url + f'/api/control-panel/{self.merchant.identity.did.root}/mass-payments/status',
            json={
                'uid': uid,
                'status': 'processing',
                'message': 'Start processing'
            },
            headers=root_access_header
        )
        assert process.status_code == 200

        upd = requests.post(
            self.live_server_url + f'/api/control-panel/{self.merchant.identity.did.root}/mass-payments/status',
            json={
                'uid': uid,
                'status': 'error',
                'error': True,
                'message': 'Some error message'
            },
            headers=root_access_header
        )
        assert upd.status_code == 200
        resp = requests.get(
            self.live_server_url + f'/api/control-panel/{self.merchant.identity.did.root}/mass-payments/{uid}/status',
            headers=root_access_header
        )
        assert resp.status_code == 200
        status2 = resp.json()

        upd = requests.post(
            self.live_server_url + f'/api/control-panel/{self.merchant.identity.did.root}/mass-payments/status',
            json={
                'uid': uid,
                'status': 'attachment',
                'payload': {
                    'attachments': ['xxx', 'yyy']
                }
            },
            headers=root_access_header
        )
        assert upd.status_code == 200
        resp = requests.get(
            self.live_server_url + f'/api/control-panel/{self.merchant.identity.did.root}/mass-payments/{uid}/status',
            headers=root_access_header
        )
        assert resp.status_code == 200
        status3 = resp.json()

        history = requests.get(
            self.live_server_url + f'/api/control-panel/{self.merchant.identity.did.root}/mass-payments/{uid}/history',
            headers=root_access_header
        )
        assert history.status_code == 200
        assert history.json()[-1]['status'] == 'attachment'

        upd = requests.post(
            self.live_server_url + f'/api/control-panel/{self.merchant.identity.did.root}/mass-payments/status',
            json={
                'uid': uid,
                'status': 'success'
            },
            headers=root_access_header
        )
        assert upd.status_code == 200
        resp = requests.get(
            self.live_server_url + f'/api/control-panel/{self.merchant.identity.did.root}/mass-payments/{uid}/status',
            headers=root_access_header
        )
        assert resp.status_code == 200
        status4 = resp.json()

        assert (status1['status'], status2['status'], status3['status'], status4['status']) == ('pending', 'error', 'error', 'success')

        resp = requests.get(
            self.live_server_url + f'/api/control-panel/{self.merchant.identity.did.root}/mass-payments/{uid}/history',
            headers=root_access_header
        )
        assert resp.status_code == 200
        statuses = resp.json()
        assert len(statuses) == 5

    def test_attachments(self):
        root_token = uuid.uuid4().hex
        asyncio.run(
            create_superuser(
                uid='test:root3',
                credentials=[
                    TokenAuth.TokenCredential(
                        token=root_token
                    )
                ]
            )
        )
        root_access_header = {
            'Token': root_token
        }

        pdf_uid = uuid4().hex
        jpg_uid = uuid4().hex
        xls_uid = uuid4().hex
        docx_uid = uuid4().hex
        resp = requests.post(
            self.live_server_url + f'/api/control-panel/{self.merchant.identity.did.root}/mass-payments/attachments',
            json=[
                {
                    'uid': pdf_uid,
                    'name': 'Document.pdf',
                    'data': DATA_URL_PDF
                },
                {
                    'uid': jpg_uid,
                    'name': 'Image.jpeg',
                    'data': DATA_URL_JPG
                },
                {
                    'uid': xls_uid,
                    'name': 'Document.xls',
                    'data': DATA_URI_XLS
                },
                {
                    'uid': docx_uid,
                    'name': 'Document.docx',
                    'data': DATA_URI_DOCX
                }
            ],
            headers=root_access_header
        )
        assert resp.status_code == 200
        attachments = resp.json()
        assert len(attachments) == 4
        for a in attachments:
            assert a['data'] in [DATA_URL_PDF, DATA_URL_JPG, DATA_URI_XLS, DATA_URI_DOCX]
            assert a['utc']

        resp = requests.get(
            self.live_server_url + f'/api/control-panel/{self.merchant.identity.did.root}/mass-payments/attachments?full',
            headers=root_access_header
        )
        assert resp.status_code == 200
        attachments = resp.json()
        assert len(attachments) > 0
        assert any(a['data'] in [DATA_URL_PDF, DATA_URL_JPG] for a in attachments)
        assert any(a['uid'] in [jpg_uid, pdf_uid] for a in attachments)

        # check JPG file download
        resp = requests.get(
            self.live_server_url + f'/api/control-panel/{self.merchant.identity.did.root}/mass-payments/{jpg_uid}/file',
            headers=root_access_header
        )
        assert resp.status_code == 200
        mime_type = magic.from_buffer(resp.content, mime=True)
        assert mime_type == 'image/jpeg'

        # check XLS file download
        resp = requests.get(
            self.live_server_url + f'/api/control-panel/{self.merchant.identity.did.root}/mass-payments/{xls_uid}/file',
            headers=root_access_header
        )
        assert resp.status_code == 200
        assert resp.headers.get('Content-Type') == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

        # check DOCS file download
        resp = requests.get(
            self.live_server_url + f'/api/control-panel/{self.merchant.identity.did.root}/mass-payments/{docx_uid}/file',
            headers=root_access_header
        )
        assert resp.status_code == 200
        assert resp.headers.get('Content-Type') == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'

    def test_attachments_last_attachment(self):
        root_token = uuid.uuid4().hex
        asyncio.run(
            create_superuser(
                uid='test:rootx',
                credentials=[
                    TokenAuth.TokenCredential(
                        token=root_token
                    )
                ]
            )
        )
        root_access_header = {
            'Token': root_token
        }

        xls_uid = uuid4().hex
        docx_uid = uuid4().hex
        resp = requests.post(
            self.live_server_url + f'/api/control-panel/{self.merchant.identity.did.root}/mass-payments/attachments',
            json=[
                {
                    'uid': xls_uid,
                    'name': 'Document.xls',
                    'data': DATA_URI_XLS
                },
                {
                    'uid': docx_uid,
                    'name': 'Document.docx',
                    'data': DATA_URI_DOCX
                }
            ],
            headers=root_access_header
        )
        assert resp.status_code == 200

        create = requests.post(
            self.live_server_url + f'/api/mass-payments',
            json={
                'transaction': {
                    'order_id': uuid.uuid4().hex,
                    'description': 'Test description',
                    'amount': 10000.0,
                    'currency': 'RUB'
                },
                'customer': {
                    'identifier': 'ivan@sidorov.ru',
                    'display_name': 'Ivan Sidorov',
                    'email': 'ivan@sidorov.ru',
                },
                'card': {
                    'number': '22001112200005555',
                    'expiration_date': '10/30'
                }
            },
            headers=self.headers
        )
        assert create.status_code == 200
        order_id = create.json()['uid']

        resp = requests.post(
            self.live_server_url + f'/api/control-panel/{self.merchant.identity.did.root}/mass-payments/status',
            json=[
                {
                    'uid': order_id,
                    'status': 'attachment',
                    'payload': {
                        'attachments': [
                            {'uid': xls_uid}, {'uid': docx_uid}
                        ]
                    }
                }
            ],
            headers=root_access_header
        )
        assert resp.status_code == 200

        resp = requests.get(
            self.live_server_url + f'/api/control-panel/{self.merchant.identity.did.root}/mass-payments/{order_id}/history',
            headers=root_access_header
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 2
        assert resp.json()[-1]['status'] == 'attachment'

    def test_attachment_files_to_many_statuses(self):
        order_id1, order_id2 = uuid.uuid4().hex, uuid.uuid4().hex
        create = requests.post(
            self.live_server_url + f'/api/mass-payments',
            json=[
                {
                    'transaction': {
                        'order_id': order_id1,
                        'description': 'Test description',
                        'amount': 10000.0,
                        'currency': 'RUB'
                    },
                    'customer': {
                        'identifier': 'ivan@sidorov.ru',
                        'display_name': 'Ivan Sidorov',
                        'email': 'ivan@sidorov.ru',
                    },
                    'card': {
                        'number': '22001112200005555',
                        'expiration_date': '10/30'
                    }
                },
                {
                    'transaction': {
                        'order_id': order_id2,
                        'description': 'Test description',
                        'amount': 30000.0,
                        'currency': 'RUB'
                    },
                    'customer': {
                        'identifier': 'petr@ivanov.ru',
                        'display_name': 'Petr Ivanov',
                        'email': 'petr@ivanov.ru',
                    },
                    'card': {
                        'number': '22001112200005555',
                        'expiration_date': '10/30'
                    }
                }
            ],
            headers=self.headers
        )
        assert create.status_code == 200
        assert len(create.json()) == 2
        ids = [i['uid'] for i in create.json()]

        root_token = uuid.uuid4().hex
        asyncio.run(
            create_superuser(
                uid='test:root4',
                credentials=[
                    TokenAuth.TokenCredential(
                        token=root_token
                    )
                ]
            )
        )
        root_access_header = {
            'Token': root_token
        }

        pdf_uid = uuid4().hex
        jpg_uid = uuid4().hex
        resp = requests.post(
            self.live_server_url + f'/api/control-panel/{self.merchant.identity.did.root}/mass-payments/attachments',
            json=[
                {
                    'uid': pdf_uid,
                    'name': 'Document.pdf',
                    'data': DATA_URL_PDF
                },
                {
                    'uid': jpg_uid,
                    'name': 'Image.jpeg',
                    'data': DATA_URL_JPG
                }
            ],
            headers=root_access_header
        )
        assert resp.status_code == 200
        resp = requests.post(
            self.live_server_url + f'/api/control-panel/{self.merchant.identity.did.root}/mass-payments/status',
            json=[
                {
                    'uid': pdf_uid,
                    'name': 'Document.pdf',
                    'data': DATA_URL_PDF
                },
                # Тестим что логика неявной под-грузки старых записей работает
                # {
                #     'uid': jpg_uid,
                #     'name': 'Image.jpeg',
                #     'data': DATA_URL_JPG
                # },
                {
                    'uid': ids[0],
                    'status': 'success',
                    'payload': {
                        'attachments': [
                            {'uid': pdf_uid}
                        ]
                    }
                },
                {
                    'uid': ids[1],
                    'status': 'success',
                    'payload': {
                        'attachments': [
                            {'uid': jpg_uid}
                        ]
                    }
                }
            ],
            headers=root_access_header
        )
        assert resp.status_code == 200
        statuses1 = resp.json()
        assert len(statuses1) == 2
        assert all(s['status'] == 'success' for s in statuses1)

        # GET-1
        resp = requests.get(
            self.live_server_url + f'/api/control-panel/{self.merchant.identity.did.root}/mass-payments/status?uid={ids[0]}&uid={ids[1]}',
            headers=root_access_header
        )
        assert resp.status_code == 200
        statuses2 = resp.json()
        assert statuses1 == statuses2
        # GET-2
        resp = requests.get(
            self.live_server_url + f'/api/control-panel/{self.merchant.identity.did.root}/mass-payments?uid={ids[0]}&uid={ids[1]}',
            headers=root_access_header
        )
        assert resp.status_code == 200
        payments = resp.json()
        assert len(payments) == 2
        assert all(p['status']['status'] == 'success' for p in payments)
        # GET-3
        resp = requests.get(
            self.live_server_url + f'/api/control-panel/{self.merchant.identity.did.root}/mass-payments/attachments',
            headers=root_access_header
        )
        assert resp.status_code == 200

    def test_statuses(self):
        order_id1, order_id2, order_id3 = uuid.uuid4().hex, uuid.uuid4().hex, uuid.uuid4().hex
        create = requests.post(
            self.live_server_url + f'/api/mass-payments',
            json=[
                {
                    'transaction': {
                        'order_id': order_id1,
                        'description': 'Test description',
                        'amount': 10000.0,
                        'currency': 'RUB'
                    },
                    'customer': {
                        'identifier': 'ivan@sidorov.ru',
                        'display_name': 'Ivan Sidorov',
                        'email': 'ivan@sidorov.ru',
                    },
                    'card': {
                        'number': '22001112200005555',
                        'expiration_date': '10/30'
                    }
                },
                {
                    'transaction': {
                        'order_id': order_id2,
                        'description': 'Test description',
                        'amount': 30000.0,
                        'currency': 'RUB'
                    },
                    'customer': {
                        'identifier': 'petr@ivanov.ru',
                        'display_name': 'Petr Ivanov',
                        'email': 'petr@ivanov.ru',
                    },
                    'card': {
                        'number': '22001112200005555',
                        'expiration_date': '10/30'
                    }
                },
                {
                    'transaction': {
                        'order_id': order_id3,
                        'description': 'Test description',
                        'amount': 50000.0,
                        'currency': 'RUB'
                    },
                    'customer': {
                        'identifier': 'fedor@ivanov.ru',
                        'display_name': 'Fedor Ivanov',
                        'email': 'petr@ivanov.ru',
                    },
                    'card': {
                        'number': '22001112200005556',
                        'expiration_date': '10/30'
                    }
                }
            ],
            headers=self.headers
        )
        assert create.status_code == 200
        assert len(create.json()) == 3

        first, second, third = create.json()

        # Test filter by uid
        many = requests.get(
            self.live_server_url + f'/api/mass-payments?uid={first["uid"]}&uid={second["uid"]}',
            headers=self.headers
        )
        assert many.status_code == 200
        assert len(many.json()) == 2
        assert all(i['uid'] in [first['uid'], second['uid']] for i in many.json())

        # Set status
        root_token = uuid.uuid4().hex
        asyncio.run(
            create_superuser(
                uid='test:root4',
                credentials=[
                    TokenAuth.TokenCredential(
                        token=root_token
                    )
                ]
            )
        )
        root_access_header = {
            'Token': root_token
        }
        resp = requests.post(
            self.live_server_url + f'/api/control-panel/{self.merchant.identity.did.root}/mass-payments/status',
            json=[
                {
                    'uid': first['uid'],
                    'status': 'success',
                },
                {
                    'uid': second['uid'],
                    'status': 'error',
                }
            ],
            headers=root_access_header
        )
        assert resp.status_code == 200

        # Filter by status = success
        filtered = requests.get(
            self.live_server_url + f'/api/control-panel/{self.merchant.identity.did.root}/mass-payments?status=success',
            headers=root_access_header
        )
        assert filtered.status_code == 200
        assert len(filtered.json()) == 1
        assert filtered.json()[0]['uid'] == first['uid']

        # Filter by status = [success, error]
        filtered = requests.get(
            self.live_server_url + f'/api/control-panel/{self.merchant.identity.did.root}/mass-payments?status=success&status=error',
            headers=root_access_header
        )
        assert filtered.status_code == 200
        assert len(filtered.json()) == 2
        for i in filtered.json():
            if i['uid'] == first['uid']:
                assert i['status']['status'] == 'success'
            if i['uid'] == second['uid']:
                assert i['status']['status'] == 'error'

        # Filter by status = pending
        filtered = requests.get(
            self.live_server_url + f'/api/control-panel/{self.merchant.identity.did.root}/mass-payments?status=pending',
            headers=root_access_header
        )
        assert filtered.status_code == 200
        assert len(filtered.json()) == 1
        assert filtered.json()[0]['uid'] == third['uid']

    def test_combination_of_processing_and_orders(self):
        # Allocate root tokens
        root_token = uuid.uuid4().hex
        asyncio.run(
            create_superuser(
                uid='test:root:orders',
                credentials=[
                    TokenAuth.TokenCredential(
                        token=root_token
                    )
                ]
            )
        )
        root_access_header = {
            'Token': root_token
        }
        
        # Create payment-orders
        uid1, uid2, uid3 = 'uid1-'+uuid.uuid4().hex, 'uid2-'+uuid.uuid4().hex, 'uid3-'+uuid.uuid4().hex
        create = requests.post(
            self.live_server_url + f'/api/mass-payments',
            json=[
                {
                    'uid': uid1,
                    'transaction': {'order_id': uid1, 'description': 'Test description', 'amount': 10000.0, 'currency': 'RUB'},
                    'customer': {'identifier': 'ivan@sidorov.ru', 'display_name': 'Ivan Sidorov', 'email': 'ivan@sidorov.ru',},
                    'card': {'number': '22001112200005555', 'expiration_date': '10/30'}
                },
                {
                    'uid': uid2,
                    'transaction': {'order_id': uid2, 'description': 'Test description', 'amount': 30000.0, 'currency': 'RUB'},
                    'customer': {'identifier': 'petr@ivanov.ru', 'display_name': 'Petr Ivanov', 'email': 'petr@ivanov.ru',},
                    'card': {'number': '22001112200005555', 'expiration_date': '10/30'}
                },
                {
                    'uid': uid3,
                    'transaction': {'order_id': uid3, 'description': 'Test description', 'amount': 50000.0, 'currency': 'RUB'},
                    'customer': {'identifier': 'fedor@ivanov.ru', 'display_name': 'Fedor Ivanov', 'email': 'petr@ivanov.ru'},
                    'card': {'number': '22001112200005556', 'expiration_date': '10/30'}
                }
            ],
            headers=self.headers
        )
        assert create.status_code == 200
        assert len(create.json()) == 3

        first, second, third = create.json()

        # 1. Check response for all members
        for auth_headers in [self.headers, root_access_header]:
            resp = requests.get(
                self.live_server_url + f'/api/orders',
                headers=auth_headers
            )
            assert resp.status_code == 200
            assert len(resp.json()) == 0
        # 2. Change status to processing for 2 orders
        resp = requests.post(
            self.live_server_url + f'/api/control-panel/{self.merchant.identity.did.root}/mass-payments/status',
            json=[
                {
                    'uid': uid1,
                    'status': 'processing',
                },
                {
                    'uid': uid2,
                    'status': 'processing',
                }
            ],
            headers=root_access_header
        )
        assert resp.status_code == 200
        # 3. Check response for all members
        for auth_headers in [self.headers, root_access_header]:
            resp = requests.get(
                self.live_server_url + f'/api/orders',
                headers=auth_headers
            )
            assert resp.status_code == 200
            assert len(resp.json()) == 1
            order = resp.json()[0]
            assert order['type'] == 'mass-payment'
            batch = order['batch']
            assert len(batch['orders']) == 2
            assert all(i['id'] in [uid1, uid2] for i in batch['orders'])
        # 4. Change status to processing for one
        resp = requests.post(
            self.live_server_url + f'/api/control-panel/{self.merchant.identity.did.root}/mass-payments/status',
            json=[
                {
                    'uid': uid1,
                    'status': 'success',
                }
            ],
            headers=root_access_header
        )
        assert resp.status_code == 200
        # 5. Check response for all members
        for auth_headers in [self.headers, root_access_header]:
            resp = requests.get(
                self.live_server_url + f'/api/orders',
                headers=auth_headers
            )
            assert resp.status_code == 200
            assert len(resp.json()) == 1
            order = resp.json()[0]
            batch = order['batch']
            assert len(batch['orders']) == 1
            assert all(i['id'] in [uid2] for i in batch['orders'])
        # 6. Для attachments
        attachment_uid = uuid4().hex
        resp = requests.post(
            self.live_server_url + f'/api/control-panel/{self.merchant.identity.did.root}/mass-payments/status',
            json=[
                {
                    'uid': attachment_uid,
                    'name': 'Document.pdf',
                    'data': DATA_URL_PDF
                },
                {
                    'uid': uid2,
                    'status': 'attachment',
                    'payload': {
                        'attachments': [
                            {'uid': attachment_uid}
                        ]
                    }
                }
            ],
            headers=root_access_header
        )
        assert resp.status_code == 200
        resp = requests.get(
            self.live_server_url + f'/api/orders',
            headers=auth_headers
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        order = resp.json()[0]
        batch = order['batch']
        attachments = batch.get('attachments')
        assert attachments
        assert attachment_uid in str(attachments)

    def test_combination_of_deposits_and_orders(self):
        # Allocate root tokens
        root_token = uuid.uuid4().hex
        asyncio.run(
            create_superuser(
                uid='test:root:deposits_and_orders',
                credentials=[
                    TokenAuth.TokenCredential(
                        token=root_token
                    )
                ]
            )
        )
        root_access_header = {
            'Token': root_token
        }

        # 1. Make deposit
        created = requests.post(
            self.live_server_url + f'/api/mass-payments/deposit',
            json={
                'amount': 10500.50
            },
            headers=self.headers
        )
        assert created.status_code == 200
        # 2. Processor see order
        resp = requests.get(
            self.live_server_url + f'/api/orders',
            headers=root_access_header
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert len(resp.json()[0]['batch']['deposits']) == 1

    def test_deposits(self):
        # Allocate root tokens
        root_token = uuid.uuid4().hex
        asyncio.run(
            create_superuser(
                uid='test:root:deposits',
                credentials=[
                    TokenAuth.TokenCredential(
                        token=root_token
                    )
                ]
            )
        )
        root_access_header = {
            'Token': root_token
        }

        resp = requests.get(
            self.live_server_url + f'/api/mass-payments/deposit',
            headers=self.headers
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 0

        # 1. Make deposit
        created = requests.post(
            self.live_server_url + f'/api/mass-payments/deposit',
            json={
                'amount': 10500.50
            },
            headers=self.headers
        )
        assert created.status_code == 200
        assert created.json().get('amount') == 10500.50
        deposit_order_uid = created.json()['uid']
        assert deposit_order_uid

        # 2. Re-retrieve
        resp = requests.get(
            self.live_server_url + f'/api/mass-payments/deposit',
            headers=self.headers
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        order = resp.json()[0]
        assert order['uid'] == deposit_order_uid
        assert order['status'] == 'pending'

        # 3. Approve deposit by processing side
        updated = requests.post(
            self.live_server_url + f'/api/control-panel/{self.merchant.identity.did.root}/mass-payments/{deposit_order_uid}/deposit',
            json={
                'amount': 10500.00,
                'status': 'success'
            },
            headers=root_access_header
        )
        assert updated.status_code == 200
        status = updated.json()
        assert status['uid'] == deposit_order_uid
        assert status['amount'] == 10500.0
        assert status['status'] == 'success'

    def test_deposits_balances(self):
        # Allocate root tokens
        root_token = uuid.uuid4().hex
        asyncio.run(
            create_superuser(
                uid='test:root:deposits_balances',
                credentials=[
                    TokenAuth.TokenCredential(
                        token=root_token
                    )
                ]
            )
        )
        root_access_header = {
            'Token': root_token
        }

        # 1. Make deposit
        created = requests.post(
            self.live_server_url + f'/api/mass-payments/deposit',
            json={
                'amount': 10000.0
            },
            headers=self.headers
        )
        assert created.status_code == 200
        deposit_uid = created.json()['uid']

        # 1.1 Balance not changed
        assets = requests.get(
            self.live_server_url + f'/api/mass-payments/assets',
            headers=self.headers
        )
        assert assets.status_code == 200
        balances1 = assets.json()
        assert all(balances1[attr] == 0.0 for attr in ['balance', 'reserved', 'deposit'])

        # 2. Approve deposit
        approved = requests.post(
            self.live_server_url + f'/api/control-panel/{self.merchant.identity.did.root}/mass-payments/{deposit_uid}/deposit',
            json={
                'status': 'success'
            },
            headers=root_access_header
        )
        assert approved.status_code == 200
        # 2.1 Balance should change
        assets = requests.get(
            self.live_server_url + f'/api/mass-payments/assets',
            headers=self.headers
        )
        assert assets.status_code == 200
        balances2 = assets.json()
        assert balances2['balance'] == 10000.0
        assert balances2['deposit'] == 10000.0
        assert balances2['reserved'] == 0.0

        # 2.2 Balance correction
        corrected = requests.post(
            self.live_server_url + f'/api/control-panel/{self.merchant.identity.did.root}/mass-payments/{deposit_uid}/deposit',
            json={
                'status': 'correction',
                'amount': -1000
            },
            headers=root_access_header
        )
        assert corrected.status_code == 200
        # 2.3 Balance should corrected
        assets = requests.get(
            self.live_server_url + f'/api/mass-payments/assets',
            headers=self.headers
        )
        assert assets.status_code == 200
        balances3 = assets.json()
        assert balances3['balance'] == 10000.0 - 1000.0
        assert balances3['deposit'] == 10000.0 - 1000.0
        assert balances3['reserved'] == 0.0

    def test_deposits_filtering(self):
        # Allocate root tokens
        root_token = uuid.uuid4().hex
        asyncio.run(
            create_superuser(
                uid='test:root:deposits_filtering',
                credentials=[
                    TokenAuth.TokenCredential(
                        token=root_token
                    )
                ]
            )
        )
        root_access_header = {
            'Token': root_token
        }
        # 1. Make 3 deposits
        uids = []
        for no, amount in enumerate([1000.0, 20000.0, 30000.0]):
            created = requests.post(
                self.live_server_url + f'/api/mass-payments/deposit',
                json={
                    'uid': f'id-{no}',
                    'amount': amount
                },
                headers=self.headers
            )
            assert created.status_code == 200
            uids.append(created.json()['uid'])
        # 2. Retrieve list
        many = requests.get(
            self.live_server_url + f'/api/mass-payments/deposit',
            headers=self.headers
        )
        assert many.status_code == 200
        assert len(many.json()) == 3
        assert many.json()[0]['uid'] == uids[2]
        assert many.json()[2]['uid'] == uids[0]
        # 3. Approve first
        first_uid = uids[0]
        approved = requests.post(
            self.live_server_url + f'/api/control-panel/{self.merchant.identity.did.root}/mass-payments/{first_uid}/deposit',
            json={
                'status': 'success'
            },
            headers=root_access_header
        )
        assert approved.status_code == 200
        # 4. Check retrieve
        many = requests.get(
            self.live_server_url + f'/api/mass-payments/deposit',
            headers=self.headers
        )
        assert many.status_code == 200
        assert len(many.json()) == 3
        assert many.json()[2]['status'] == 'success'
        assert many.json()[2]['uid'] == uids[0]
        assert many.json()[0]['status'] == 'pending'
        assert many.json()[0]['uid'] == uids[2]
        # 5. Check filters
        filtered = requests.get(
            self.live_server_url + f'/api/mass-payments/deposit?status=pending',
            headers=self.headers
        )
        assert filtered.status_code == 200
        assert len(filtered.json()) == 2
        assert many.json()[0]['uid'] == uids[2]
        assert many.json()[1]['uid'] == uids[1]

    def test_deposits_attachments(self):
        # 1. Make deposit
        created = requests.post(
            self.live_server_url + f'/api/mass-payments/deposit',
            json={
                'amount': 10000.0,
                'attachments': [
                    {
                        'name': 'TestDoc.pdf',
                        'data': DATA_URL_PDF,
                    }
                ]
            },
            headers=self.headers
        )
        assert created.status_code == 200
        deposit_uid = created.json()['uid']

        # 2. Attach files
        attachments = requests.post(
            self.live_server_url + f'/api/mass-payments/{deposit_uid}/deposit',
            json={
                'status': 'attachment',
                'attachments': [
                    {
                        'name': 'TestImage.jpg',
                        'data': DATA_URL_JPG,
                    }
                ]
            },
            headers=self.headers
        )
        assert attachments.status_code == 200
        assert len(attachments.json()['attachments']) == 2
        jpg_attach_uid = attachments.json()['attachments'][-1]['uid']

        # 2. Get attachment file
        resp = requests.get(
            self.live_server_url + f'/api/mass-payments/{jpg_attach_uid}/file',
            headers=self.headers
        )
        assert resp.status_code == 200
        mime_type = magic.from_buffer(resp.content, mime=True)
        assert mime_type == 'image/jpeg'

    def test_export_register(self):
        """Экспорт реестров"""

        root_token = uuid.uuid4().hex
        asyncio.run(
            create_superuser(
                uid='test:export_register',
                credentials=[
                    TokenAuth.TokenCredential(
                        token=root_token
                    )
                ]
            )
        )
        root_access_header = {
            'Token': root_token
        }

        create = requests.post(
            self.live_server_url + f'/api/mass-payments',
            json=[
                {
                    'transaction': {'order_id': uuid.uuid4().hex,'description': 'Test description','amount': 10000.0,'currency': 'RUB'},
                    'customer': {'identifier': 'ivan@sidorov.ru','display_name': 'Ivan Sidorov','email': 'ivan@sidorov.ru',},
                    'card': {'number': '22001112200005555','expiration_date': '10/30'},
                },
                {
                    'transaction': {'order_id': uuid.uuid4().hex,'description': 'Test description','amount': 10000.0, 'currency': 'RUB'},
                    'customer': {'identifier': 'ivan@sidorov.ru','display_name': 'Ivan Sidorov','email': 'ivan@sidorov.ru', },
                    'card': {'number': '22001112200005555','expiration_date': '10/30'},
                }
            ],
            headers=self.headers
        )
        assert create.status_code == 200
        uid1, uid2 = create.json()[0]['uid'], create.json()[1]['uid']

        process = requests.post(
            self.live_server_url + f'/api/control-panel/{self.merchant.identity.did.root}/mass-payments/status',
            json=[
                {
                    'uid': uid1,
                    'status': 'processing',
                },
                {
                    'uid': uid2,
                    'status': 'processing',
                }
            ],
            headers=root_access_header
        )
        assert process.status_code == 200

        # Get export file via link
        export = requests.get(
            self.live_server_url + f'/api/control-panel/{self.merchant.identity.did.root}/mass-payments/export?engine=qugo',
            headers=root_access_header
        )
        assert export.status_code == 200


class TestPaymentRequest(ExchangeLiveMixin, LiveServerTestCase):

    @property
    def headers(self) -> dict:
        return {
            'Content-type': 'application/json',
            'Token': self.token_cred['token']
        }

    def test_create_order(self):
        url = self.live_server_url + f'/api/orders'

        # 1. Create
        create = requests.post(
            url,
            json={
                'type': 'payment-request',
                'payment_request': {
                    'description': 'Оплата экскурсии',
                    'customer': 'Иван Коровин',
                    'amount': 150000,
                    'currency': 'RUB',
                    'details': {
                        'payment_ttl': 15 * 60  # 15 мин
                    }
                }
            },
            headers=self.headers
        )
        assert create.status_code == 200
        order = create.json()
        pr = PaymentRequest.model_validate(order['payment_request'])
        assert pr.uid
        assert pr.id
        assert pr.created

        # 2. Ensure new ledger exists
        ledgers = requests.get(
            url=self.live_server_url + f'/api/ledgers',
            headers=self.headers
        )
        assert ledgers.status_code == 200
        assert len(ledgers.json()) == 2

        # 3. load payment requests
        many = requests.get(
            url=url,
            headers=self.headers
        )
        assert many.status_code == 200
        assert len(many.json()) == 1

    def test_lyfecycle(self):
        url = self.live_server_url + f'/api/orders'
        # 1. Create
        create = requests.post(
            url,
            json={
                'type': 'payment-request',
                'payment_request': {
                    'description': 'Аренда байка',
                    'customer': 'Иван Коровин',
                    'amount': 150000,
                    'currency': 'RUB',
                    'details': {
                        'payment_ttl': 15 * 60  # 15 мин
                    }
                }
            },
            headers=self.headers
        )
        assert create.status_code == 200
        request = PaymentRequest.model_validate(create.json()['payment_request'])

        # 2. Клиент заходит на сайт
        anonym = requests.get(
            url=self.live_server_url
        )
        assert anonym.status_code == 200
        session_uid = anonym.cookies.get('session_uid')
        assert session_uid

        # 3. Клиент линкуется к ордеру
        link = requests.post(
            url + '/link',
            json={
                'id': create.json()['id'],
                'type': 'payment-request'
            },
            cookies={'session_uid': session_uid}
        )
        assert link.status_code == 200
        request = PaymentRequest.model_validate(link.json()['payment_request'])
        assert request.status == 'linked'
        assert request.linked_client == session_uid

        # 3. Клиент запрашивает реквизиты
        ready = requests.post(
            url + '/status',
            json={
                'id': create.json()['id'],
                'type': 'payment-request',
                'status': 'ready'
            },
            cookies={'session_uid': session_uid}
        )
        assert ready.status_code == 200
        request = PaymentRequest.model_validate(ready.json()['payment_request'])
        assert request.status == 'ready'

        # 4. Оператор запрашивает платежные реквизиты
        wait = requests.post(
            url + '/status',
            json={
                'id': create.json()['id'],
                'type': 'payment-request',
                'status': 'wait',
                'details': {
                    'payment_ttl': 900,
                    'fps': {
                        'phone': '+79991112233',
                        'holder': 'Иван Петрович М',
                        'bank': 'Т-Банк'
                    }
                }
            },
            headers=self.headers
        )
        assert wait.status_code == 200
        request = PaymentRequest.model_validate(wait.json()['payment_request'])
        assert request.status == 'wait'
        assert request.details.active_until
        assert request.details.fps.phone == '+79991112233'

        # 5. Клиент произвел оплату
        payed = requests.post(
            url + '/status',
            json={
                'id': create.json()['id'],
                'type': 'payment-request',
                'status': 'payed'
            },
            cookies={'session_uid': session_uid}
        )
        assert payed.status_code == 200
        request = PaymentRequest.model_validate(payed.json()['payment_request'])
        assert request.status == 'payed'

        # 6. Оператор начал проверку
        checking = requests.post(
            url + '/status',
            json={
                'id': create.json()['id'],
                'type': 'payment-request',
                'status': 'checking',
            },
            headers=self.headers
        )
        assert checking.status_code == 200
        request = PaymentRequest.model_validate(checking.json()['payment_request'])
        assert request.status == 'checking'

        # 7. Оператор закрыл заявку
        done = requests.post(
            url + '/status',
            json={
                'id': create.json()['id'],
                'type': 'payment-request',
                'status': 'done',
            },
            headers=self.headers
        )
        assert done.status_code == 200
        request = PaymentRequest.model_validate(done.json()['payment_request'])
        assert request.status == 'done'

    def test_retrieve_multiple_requests_with_filters(self):
        url = self.live_server_url + f'/api/orders'
        # 1. Create
        create1 = requests.post(
            url,
            json={
                'type': 'payment-request',
                'payment_request': {
                    'description': 'Аренда байка [1]',
                    'customer': 'Иван Коровин',
                    'amount': 150000,
                    'currency': 'RUB',
                    'details': {
                        'payment_ttl': 15 * 60  # 15 мин
                    }
                }
            },
            headers=self.headers
        )
        assert create1.status_code == 200
        request1 = PaymentRequest.model_validate(create1.json()['payment_request'])

        create2 = requests.post(
            url,
            json={
                'type': 'payment-request',
                'payment_request': {
                    'description': 'Аренда байка [2]',
                    'customer': 'Иван Коровин',
                    'amount': 150000,
                    'currency': 'RUB',
                    'details': {
                        'payment_ttl': 15 * 60  # 15 мин
                    }
                }
            },
            headers=self.headers
        )
        assert create2.status_code == 200
        request2 = PaymentRequest.model_validate(create2.json()['payment_request'])

        many1 = requests.get(
            url + f'?uid={request1.uid}&type=payment-request',
            headers=self.headers,
        )
        assert many1.status_code == 200
        assert len(many1.json()) == 1
        assert many1.json()[0]['payment_request']['uid'] == request1.uid

        # 2. Change status
        link = requests.post(
            url + '/link',
            json={
                'id': create2.json()['id'],
                'type': 'payment-request'
            },
            headers=self.headers,
        )
        assert link.status_code == 200

        many2 = requests.get(
            url + f'?status=linked&type=payment-request',
            headers=self.headers,
        )
        assert many2.status_code == 200
        assert len(many2.json()) == 1
        assert many2.json()[0]['payment_request']['uid'] == request2.uid


class TestDirections(ExchangeLiveMixin, LiveServerTestCase):

    def test_retrieve(self):
        root_token = uuid.uuid4().hex
        root = self.create_root(root_token)

        url = self.live_server_url + f'/api/exchange/directions'
        resp = requests.get(
            url,
            # headers={'Token': root_token}
        )
        assert resp.status_code == 200
        assert len(resp.json()) > 0

        pk1 = resp.json()[0]['id']
        resp = requests.get(
            url + '/' + pk1,
            # headers={'Token': root_token}
        )
        assert resp.status_code == 200

    def test_currencies_lifecycle(self):
        root_token = uuid.uuid4().hex
        root = self.create_root(root_token)

        url = self.live_server_url + f'/api/exchange/currencies'

        resp = requests.get(
            url,
            headers={'Token': root_token}
        )
        assert resp.status_code == 200
        assert len(resp.json()) > 0

        create = requests.post(
            url,
            headers={'Token': root_token},
            json={
                'symbol': 'AED',
                'is_fiat': True,
                'payments_count': 10050
            }
        )
        assert create.status_code == 200
        cur = create.json()

        update = requests.put(
            url + f'/{cur["id"]}',
            headers={'Token': root_token},
            json={
                'symbol': 'AED',
                'is_fiat': True,
                'icon': 'some-url',
                'payments_count': 10050
            }
        )
        assert update.status_code == 200
        assert update.json()['icon'] == 'some-url'

        update = requests.put(
            url + f'/{cur["id"]}',
            headers={'Token': root_token},
            json={
                'symbol': 'RUB',
                'is_fiat': True,
                'icon': 'some-url',
                'payments_count': 10050
            }
        )
        assert update.status_code == 400

        delete = requests.delete(
            url + f'/{cur["id"]}',
            headers={'Token': root_token}
        )
        assert delete.status_code == 204

        resp = requests.get(
            url + f'/{cur["id"]}',
            headers={'Token': root_token}
        )
        assert resp.status_code == 404
