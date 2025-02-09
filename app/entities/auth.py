from datetime import datetime
from typing import Dict, Optional, List

import pydantic
from pydantic import HttpUrl, Field

from .base import Account, BaseEntity, UrlPaths, Identity, Ledger


class GrantedAccount(Account):
    owner: str


class Credential(BaseEntity):
    class_name: str
    account_uid: str
    schema: Dict
    payload: Dict
    ttl: Optional[int] = 60*60*24  # 1hr


class Session(BaseEntity):
    uid: str
    class_name: str
    account_uid: Optional[str] = None
    last_access_utc: Optional[datetime] = None
    kill_after_utc: Optional[datetime] = None


class MerchantAuth(BaseEntity):
    class_: str = Field(default_factory=str, alias='class')
    settings: Dict


class MassPaymentAsset(BaseEntity):
    code: Optional[str] = None  # ex: USDTTRC20
    address: Optional[str]  # ex: blockchain addr


class MassPaymentRatios(BaseEntity):
    engine: Optional[str]
    base: Optional[str]
    quote: Optional[str]


class MassPaymentsCfg(BaseEntity):
    enabled: bool = False
    asset: Optional[MassPaymentAsset] = None
    ratios: Optional[MassPaymentRatios] = None
    ledger: Optional[Ledger] = None


class MerchantMeta(BaseEntity):
    title: Optional[str] = None
    base_currency: str
    url: HttpUrl
    paths: Optional[UrlPaths] = Field(default_factory=UrlPaths)
    auth: List[MerchantAuth] = Field(default_factory=list)
    ratios: Optional[Dict] = None
    mass_payments: Optional[MassPaymentsCfg] = Field(default_factory=MassPaymentsCfg)
    identity: Optional[Identity] = None


class MerchantAccount(Account):
    meta: MerchantMeta
