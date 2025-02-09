import base64
import os.path
from datetime import datetime
from typing import Literal, Optional, Dict, Union

import magic
from pydantic import BaseModel, Extra, Field


class KYCPhoto(BaseModel, extra=Extra.allow):
    type: Literal['document', 'selfie', 'document+selfie']
    image: bytes = b''
    remove_after: Optional[float] = None
    mime_type: str = None

    def from_file(self, path: str):
        if not os.path.exists(path):
            raise RuntimeError(f'File {path} not exists')
        with open(path, 'rb') as f:
            self.from_image(f.read())

    def from_image(self, raw: Union[bytes, str]):
        if isinstance(raw, str):
            raw = raw.encode()
        self.image = base64.b64encode(raw)
        self.mime_type = magic.from_buffer(raw, mime=True)


class DocumentPhoto(KYCPhoto):
    type: str = 'document'


class SelfiePhoto(KYCPhoto):
    type: str = 'selfie'


class DocAndSelfiePhoto(KYCPhoto):
    type: str = 'document+selfie'


class Liveness(BaseModel):
    """результаты проверки живости человека на селфи,
    проверяет живой ли человек на изображении"""

    liveness: bool  # живой/не живой, значения 0 или 1
    probability: float  # вероятность живости, значения от 0 до 1


class MatchFaces(BaseModel):
    """результаты проверки схожести человека на изображении
    в паспорте и селфи"""

    match_faces: bool  # совпадает/не совпадает, значения 0 или 1
    similarity: float  # на сколько изображения лиц схожи, значения от 0 до 1


class Biometrics(BaseModel):
    liveness: Optional[Liveness] = None
    matches: Optional[MatchFaces] = None


class VerifyMetadata(BaseModel):

    # качество распознавания каждого поля документа
    confidences: Optional[Dict[str, float]] = None

    # Подделка / помарки, причины брака документа,
    # возможные варианты: Не типовой документ (Паспорт РФ),
    # Некачественное изображение, Подделка/помарки, Брак (иная причина)
    broken_reason: Optional[str] = None

    # результаты проверок биометрии
    biometrics: Optional[Biometrics] = None


class VerifiedDocument(BaseModel, extra=Extra.allow):
    id: str  # номер документа, полученный при загрузке
    kyc_provider: str
    issued_by: Optional[str] = None  # дата выдачи паспорта
    issued_date: Optional[str] = None  # дата выдачи паспорта
    issued_id: Optional[str] = None  # код подразделения
    series: Optional[str] = None  # серия
    number: Optional[str] = None  # номер
    gender: Optional[Literal['F', 'M']] = None  # пол F - женский, М - мужской
    last_name: Optional[str] = None
    first_name: Optional[str] = None
    middle_name: Optional[str] = None
    birth_date: Optional[str] = None
    birth_place: Optional[str] = None
    has_photo: Optional[bool] = None  # признак наличия фото
    has_owner_signature: Optional[bool] = None
    metadata: Optional[VerifyMetadata] = None


class AccountKYCPhotos(BaseModel):
    document: Optional[DocumentPhoto] = None
    selfie: Optional[SelfiePhoto] = None

    @property
    def is_empty(self) -> bool:
        return self.document is None and self.selfie is None


class OrganizationDocument(BaseModel):
    id: Optional[int] = None
    type: Optional[str] = None
    document: Optional[DocumentPhoto] = None
    attrs: Dict = Field(default_factory=dict)


class AccountKYC(BaseModel):
    document_id: str
    provider: str
    photos: AccountKYCPhotos = Field(default_factory=AccountKYCPhotos)
    verify: VerifiedDocument
    inn: Optional[str] = None
    source: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    external_id: Optional[str] = None  # внешний ID в стороннем сервисе
