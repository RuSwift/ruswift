import json
import os.path
import uuid

import pytest

from entities import DocumentPhoto, SelfiePhoto
from kyc import BeOrgKYCProvider, MTSKYCProvider


@pytest.mark.asyncio
class TestMTSKYCProvider:

    @pytest.fixture
    def provider(self) -> MTSKYCProvider:
        provider = MTSKYCProvider()
        provider._settings.consumer_key = 'GabmQfjGD8fls4HQhYp1DuiWAeka'
        provider._settings.consumer_secret = 'swqkzpNH_l4RKL1D5YslKubwHc4a'
        return provider

    async def test_allocate_token(self, provider: MTSKYCProvider):
        token = await provider.allocate_token()
        assert token
        token2 = await provider.get_access_token()
        assert token2 == token

    async def test_applicants_lifecycle(self, provider: MTSKYCProvider):
        external_id = uuid.uuid4().hex
        applicant1 = await provider.ensure_applicant_exists(
            external_id=external_id
        )
        assert applicant1

        applicant2 = await provider.ensure_applicant_exists(
            external_id=external_id,
            data=MTSKYCProvider.Applicant(
                externalId=external_id, email='x@gmail.com'
            )
        )
        assert applicant2.email == 'x@gmail.com'

        link = await provider.create_identification_request(
            external_id=external_id
        )
        print('')


@pytest.mark.asyncio
class TestBeorgProvider:

    @pytest.fixture
    def base_path(self) -> str:
        return '/app/exchange/tests/files/kyc/beorg'

    @pytest.fixture
    def provider(self) -> BeOrgKYCProvider:
        BeOrgKYCProvider.settings = BeOrgKYCProvider.KYCSettings(
            project_id='WEB_PASSPORT_BIO',
            machine_uid='BGVTZIWCDDU3VT0BKLLAW24RGYY2GW2367VFFOVP',
            token='254b87a00147fab4e2aff8b0a344b7db'
        )
        return BeOrgKYCProvider()

    async def test_verify_only_success_passport(
        self, base_path: str, provider: BeOrgKYCProvider
    ):
        ok_passport_path = os.path.join(base_path, 'success_passport.pdf')
        ok_selfie_path = os.path.join(base_path, 'selfie.jpeg')
        passport_photo = DocumentPhoto()
        passport_photo.from_file(ok_passport_path)
        selfie_photo = SelfiePhoto()
        selfie_photo.from_file(ok_selfie_path)
        data = await provider.verify(photos=[passport_photo, selfie_photo])
        print(json.dumps(data, indent=2))
