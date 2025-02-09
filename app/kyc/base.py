from abc import abstractmethod, ABC
from typing import List

from pydantic import BaseModel, Extra

from entities import KYCPhoto, VerifiedDocument


class BaseKYCProvider(ABC):

    class KYCSettings(BaseModel, extra=Extra.ignore):
        ...

    settings: KYCSettings = None
    provider_id: str

    @abstractmethod
    async def verify(self, photos: List[KYCPhoto]) -> VerifiedDocument:
        ...
