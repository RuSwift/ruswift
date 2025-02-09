from uuid import uuid4
from enum import Enum
from datetime import datetime
from typing import Dict, Union, Literal, List, Optional, Any

from pydantic import BaseModel, Field, Extra, HttpUrl
from pydantic.functional_validators import field_validator


LANG = str
TEXT = str


def generate_random_uid() -> str:
    return uuid4().hex


class BaseEntity(BaseModel, extra=Extra.allow):
    ...


class Labels(BaseEntity):
    translations: Dict[LANG, TEXT]


class Currency(BaseEntity):
    symbol: str
    icon: Optional[str] = None
    is_fiat: bool
    is_enabled: Optional[bool] = True
    owner_did: Optional[str] = None


class BasePaymentMethod(BaseEntity):
    category: str
    name: str
    icon: Optional[str] = None
    is_enabled: Optional[bool] = True
    code: Optional[str] = None
    owner_did: Optional[str] = None


class Network(BasePaymentMethod):
    category: Literal['blockchain'] = 'blockchain'
    explorer: Optional[str] = None


class PaymentMethod(BasePaymentMethod):
    category: Literal['payment-system'] = 'payment-system'
    sub: Literal['fiat', 'digital', 'wire']


class CashMethod(BasePaymentMethod):
    category: Literal['cash'] = 'cash'
    sub: Literal['cash', 'fiat']


class AccountFields(BaseEntity):
    icon: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    telegram: Optional[str] = None

    @property
    def full_name(self) -> str:
        if self.first_name or self.last_name:
            parts = [self.first_name, self.last_name]
            parts = [p for p in parts if p]
            return ' '.join(parts)
        else:
            return ''


class AccountVerifiedFields(BaseModel):
    phone: bool = False
    email: bool = False
    telegram: bool = False


class Account(AccountFields):

    class Permission(Enum):
        ROOT = 'root'  # superuser
        KYC = 'kyc'  # право иметь доступ к KYC
        ACCOUNTS = 'accounts'  # доступ к методам работы с аккаунтами
        GRANT = 'grant'  # доступ к повышению роли
        MERCHANT = 'merchant'  # является мерчантом
        OPERATOR = 'operator'  # оператор обменника
        ANY = 'any'  # любой авторизованный

    uid: str
    is_active: Optional[bool] = True
    permissions: List[str] = Field(default_factory=list)
    is_verified: bool = False
    is_organization: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    merchant_meta: Optional[Dict] = None
    verified: Optional[AccountVerifiedFields] = Field(
        default_factory=AccountVerifiedFields
    )

    @property
    def has_root_permission(self) -> bool:
        return self.Permission.ROOT.value in self.permissions

    @property
    def has_accounts_permission(self) -> bool:
        return self.Permission.ACCOUNTS.value in self.permissions

    @property
    def has_operator_permission(self) -> bool:
        return self.Permission.OPERATOR.value in self.permissions


class AnonymousAccount(Account):
    uid: str = Field(default_factory=generate_random_uid)
    is_anonymous: bool = True
    kyc: Optional[Dict] = None


class Limits(BaseEntity):
    minimum: Optional[float] = None
    maximum: Optional[float] = None
    cur: str


class Correction(BaseEntity):
    cost: float
    is_percents: bool
    cur: str
    limits: Optional[Limits] = None


class Costs(BaseEntity):
    income: Union[str, List[str]] = None
    outcome: Union[str, List[str]] = None

    @field_validator('income', 'outcome')
    @classmethod
    def value(cls, v: Any) -> List[str]:
        if v is None:
            return []
        elif isinstance(v, str):
            return [v]
        else:
            return v


class Payment(BaseEntity):
    code: str
    cur: str
    method: str
    costs: Costs = Field(default_factory=Costs)
    owner_did: Optional[str] = None


class Direction(BaseEntity):
    order_id: Optional[int] = 0
    src: str
    dest: str
    ratio_calculator_class: str
    owner_did: Optional[str] = None


class ExchangePair(BaseEntity):
    # base currency, ex: EUR/USD  EUR - is base currency
    base: str
    # counter currency, ex: EUR/USD  USD - is quota currency
    quote: str
    # ratio price, ex: EUR/USD=1.3045 here 1.3045 U.S. dollars is ratio price
    ratio: float
    # last update utc timestamp
    utc: Union[None, float] = None


class UrlPaths(BaseEntity):
    admin: str = '/admin'


class DIDSettings(BaseModel):
    root: str


class Identity(BaseEntity):
    did: DIDSettings

    def __str__(self):
        return self.did.root


class Ledger(BaseEntity):
    id: str
    tags: List[Literal['payments', 'payment-request']] = Field(
        default_factory=list
    )
    participants: Dict[
        Literal['owner', 'processing', 'guarantor'], List[str]
    ] = Field(default_factory=dict)

    def participants_by_role(self, role: str) -> List[str]:
        for role_, members_ in self.participants.items():
            if role_ == role:
                return members_
        return []

    def role_by_did(self, did: str) -> Optional[str]:
        for role, members in self.participants.items():
            if did in members:
                return role
        return None

    def has_participant(self, addr: str) -> bool:
        if self.id.startswith(addr):
            return True
        for role, members in self.participants.items():
            if addr in members:
                return True
        return False


class ReportsConfig(BaseModel):
    """Настройки отчетов (прежде всего *.pdf)
    """
    logo: Optional[str] = None
    font: str = 'Arial'
    title: Optional[str] = None
    description: Optional[str] = None


class SMSGatewayConfig(BaseModel):
    url: HttpUrl = 'https://api3.greensms.ru/sms/send'
    user: Optional[str] = 'test'
    password: Optional[str] = 'test'
    from_: str = Field(serialization_alias='from', default='RuSwift')
    debug_code: str = '0000'
