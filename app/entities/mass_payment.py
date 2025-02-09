from typing import Optional, Literal

from pydantic import BaseModel, IPvAnyAddress


class PaymentCustomer(BaseModel):
    identifier: str
    display_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    locale: Optional[str] = None
    ip: Optional[IPvAnyAddress] = None


class PaymentTransaction(BaseModel):
    order_id: str
    description: Optional[str] = None
    amount: Optional[float] = None
    currency: Optional[str] = None
    address: Optional[str] = None
    pay_method_code: Optional[str] = None


class PaymentCard(BaseModel):
    number: str
    expiration_date: str


class PaymentStatus(BaseModel):
    type: str = 'payout'
    status: Literal['pending', 'success', 'processing', 'error', 'attachment', 'correction'] = 'pending'  # noqa
    error: Optional[bool] = False
    sandbox: Optional[bool] = False
    earned: Optional[float] = None
    response_code: Optional[int] = None
    payload: Optional[dict] = None
    message: Optional[str] = None


class Proof(BaseModel):
    url: Optional[str] = None
    base64: Optional[str] = None
    mime_type: Optional[str] = None
