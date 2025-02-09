from typing import Optional, Any, Literal

import pydantic
from pydantic import model_validator, BaseModel

from .base import BaseEntity


class CardDetails(BaseModel):
    number: str
    holder: Optional[str] = None
    expiration_date: Optional[str] = None
    bank: Optional[str] = None


class FPSDetails(BaseModel):
    # СБП
    phone: str
    holder: str
    bank: str


class PaymentDetails(BaseModel):
    card: Optional[CardDetails] = None
    fps: Optional[FPSDetails] = None
    payment_ttl: Optional[float] = None
    active_until: Optional[float] = None

    @model_validator(mode='after')
    @classmethod
    def check_card_number_omitted(cls, data: Any) -> Any:
        card = getattr(data, 'card')
        fps = getattr(data, 'fps')
        payment_ttl = getattr(data, 'payment_ttl')
        values = [card, fps, payment_ttl]
        if all(value is None for value in values):
            raise ValueError(f'All attributes are empty!')
        active_until = getattr(data, 'active_until')
        if active_until:
            if all(value is None for value in [card, fps]):
                raise ValueError(f'Card or FPS must be filled')
        return data


class Order(BaseEntity):
    id: Optional[str] = None
    uid: Optional[str] = None
    description: Optional[str] = None
    customer: str
    amount: float
    currency: str
    details: PaymentDetails
    until: Optional[float] = None


class PaymentRequest(Order):

    class PrivatePart(BaseModel):
        token: Optional[str] = 'USDT'
        source: Optional[str] = 'Garantex'
        amount: Optional[float] = None

    class Destination(BaseModel):
        currency: Optional[str] = None
        amount: Optional[str] = None

    created: Optional[float] = None
    private: Optional[PrivatePart] = pydantic.Field(
        default_factory=PrivatePart
    )
    destination: Optional[Destination] = None
    linked_client: Optional[str] = None
    status: Literal[
        'created', 'linked', 'ready', 'wait', 'payed', 'checking',
        'dispute', 'done', 'declined'
    ] = 'created'
