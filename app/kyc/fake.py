from typing import List

from entities import (
    KYCPhoto, VerifiedDocument, VerifyMetadata, Biometrics,
    MatchFaces, Liveness
)
from kyc.base import BaseKYCProvider


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
