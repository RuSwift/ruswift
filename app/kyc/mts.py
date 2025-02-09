import os
from typing import Dict, Optional
from urllib.parse import urljoin

import pydantic
from pydantic import BaseModel
from aiohttp import ClientSession, BasicAuth
from django.conf import settings as django_settings

from cache import Cache
from entities import VerifiedDocument
from .base import BaseKYCProvider


class MTSKYCProvider(BaseKYCProvider):

    provider_id = 'mts.ru'  # https://developers.mts.ru/id-kyc-api

    class MTSKYCSettings(BaseKYCProvider.KYCSettings):
        consumer_key: str = os.getenv('MTS_KYC_CONSUMER_KEY')
        consumer_secret: str = os.getenv('MTS_KYC_SECRET_KEY')
        base_url: str = 'https://api.mts.ru'
        test_environ: bool = os.getenv('MTS_KYC_PROD') != 'yes' or True

    settings = MTSKYCSettings
    _cache = Cache(pool=django_settings.REDIS_CONN_POOL, namespace='kyc-mts')

    class Applicant(BaseModel):

        class Passport(BaseModel):
            series: Optional[str] = None
            number: Optional[str] = None
            issuedDate: Optional[str] = None
            issuedBy: Optional[str] = None
            divisionCode: Optional[str] = None

            def empty(self) -> bool:
                return self.series is None and self.number is None \
                       and self.issuedDate is None and self.issuedBy is None \
                       and self.divisionCode is None

        externalId: str = pydantic.Field(serialization_alias='externalId')
        email: Optional[str] = None
        phone: Optional[str] = None
        firstName: Optional[str] = None
        surname: Optional[str] = None
        middleName: Optional[str] = None
        birthdate: Optional[str] = None
        driverId: Optional[str] = None
        passport: Optional[Passport] = pydantic.Field(default_factory=Passport)

        @pydantic.field_validator('phone')
        @classmethod
        def validate_phone(cls, v: str) -> str:
            if v:
                phone = v.replace('+', '').replace(' ', '').replace('-', '')\
                    .replace('(', '').replace(')', '')
                if len(phone) != 11:
                    phone = None
                return phone
            else:
                return None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._settings = self.settings()

    async def get_access_token(self) -> str:
        data = await self._cache.get(key=f'access_token')
        if data:
            return data['value']
        else:
            return await self.allocate_token()

    async def allocate_token(self) -> str:
        async with ClientSession() as cli:
            resp = await cli.post(
                url=urljoin(self._settings.base_url, 'token'),
                auth=BasicAuth(
                    self._settings.consumer_key, self._settings.consumer_secret
                ),
                data={
                    'grant_type': 'client_credentials',
                    'scope': 'openid'
                }
            )
            if resp.ok:
                js = await resp.json()
                token = js['access_token']
                await self._cache.set(
                    key=f'access_token',
                    value={'value': token},
                    ttl=js['expires_in']
                )
                return token
            else:
                msg = await resp.text()
                raise RuntimeError(msg)

    async def create_identification_request(
        self,
        external_id: str,
        link_ttl_minutes=195,  # Время жизни ссылки,
        redirect_url: str = None,
        manual_input: bool = False,
        esia: bool = True,
        mobile_phone: str = None,
        verification: bool = True,
        inn: bool = True,
        bio: bool = True
    ) -> dict:
        preferences = {}
        if manual_input:
            preferences['manualInput'] = {'isActive': True}
        if esia:
            preferences['esia'] = {'isActive': True}
        if mobile_phone:
            preferences['mobileId'] = {'isActive': True, 'msisdn': mobile_phone}
        if verification:
            preferences['verification'] = {'isActive': True}
        if inn:
            preferences['inn'] = {'isActive': True}
        if bio:
            preferences['bio'] = {
                'isActive': True,
                "steps": [
                    "selfie",
                    "passport",
                    "passportForm",
                    "successPage"
                ],
                "lastSelfieMatching": True
            }

        access_token = await self.get_access_token()
        async with ClientSession() as cli:
            resp = await cli.post(
                url=self._build_url(path=f'applicants/{external_id}/identifications'),
                headers={
                    'Authorization': f'Bearer {access_token}'
                },
                json={
                    'linkLifetimeInMinutes': link_ttl_minutes,
                    'redirectUrl': redirect_url,
                    'workflowPreferences': preferences
                }
            )
            if resp.ok:
                js = await resp.json()
                return js
            else:
                msg = await resp.text()
                raise RuntimeError(msg)

    async def ensure_applicant_exists(
        self, external_id: str, data: Applicant = None
    ) -> Applicant:
        access_token = await self.get_access_token()
        async with ClientSession() as cli:
            applicant = await self._retrieve_applicant(
                cli, access_token, external_id
            )
            if applicant:
                if data is not None:
                    data.externalId = external_id
                    if applicant != data:
                        applicant = await self._update_applicant(
                            cli, access_token, external_id, data
                        )
                return applicant
            else:
                await self._create_applicant(
                    cli, access_token, external_id, data
                )
                applicant = await self._retrieve_applicant(
                    cli, access_token, external_id
                )
                return applicant

    async def verify(self, photos) -> VerifiedDocument:
        raise NotImplemented

    async def request_status(self, external_id: str, request_id: str) -> Dict:
        access_token = await self.get_access_token()
        async with ClientSession() as cli:
            resp = await cli.get(
                url=self._build_url(path=f'applicants/{external_id}/identifications/{request_id}'),
                headers={
                    'Authorization': f'Bearer {access_token}'
                }
            )
            if resp.ok:
                js = await resp.json()
                return js
            else:
                msg = await resp.text()
                raise RuntimeError(msg)

    async def _retrieve_applicant(
        self, cli: ClientSession, access_token: str, external_id: str
    ) -> Optional[Applicant]:
        resp = await cli.get(
            url=self._build_url(path=f'applicants/{external_id}'),
            headers={
                'Authorization': f'Bearer {access_token}'
            }
        )
        if resp.ok:
            js = await resp.json()
            applicant = self.Applicant.model_validate(
                obj=js['applicant']
            )
            return applicant
        elif resp.status == 404:
            return None
        else:
            msg = await resp.text()
            raise RuntimeError(msg)

    async def _create_applicant(
        self, cli: ClientSession, access_token: str,
        external_id: str, data: Applicant = None
    ):
        if data is None:
            data = self.Applicant(externalId=external_id)
        else:
            data.externalId = external_id
        data = data.model_dump(mode='json')
        resp = await cli.post(
            url=self._build_url(path=f'applicants'),
            headers={
                'Authorization': f'Bearer {access_token}'
            },
            json=data
        )
        if resp.status == 202:
            return
        else:
            msg = await resp.text()
            raise RuntimeError(msg)

    async def _update_applicant(
        self, cli: ClientSession, access_token: str,
        external_id: str, data: Applicant
    ) -> Applicant:
        data = data.model_dump(mode='json')
        resp = await cli.put(
            url=self._build_url(path=f'applicants/{external_id}'),
            headers={
                'Authorization': f'Bearer {access_token}'
            },
            json=data
        )
        if resp.ok:
            applicant = await self._retrieve_applicant(
                cli, access_token, external_id
            )
            return applicant
        else:
            msg = await resp.text()
            raise RuntimeError(msg)

    def _build_url(self, path: str) -> str:
        if self._settings.test_environ:
            environ = 'rim-api-prodlike'
        else:
            environ = 'rim'
        return f'{self._settings.base_url}/{environ}/2.0/api/v2/{path}'
