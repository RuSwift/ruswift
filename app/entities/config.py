from typing import List, Dict, Union, Optional

import pydantic
from django.conf import settings

from entities import (
    Direction, Correction, Network, PaymentMethod, Currency, Payment,
    UrlPaths, Identity, ReportsConfig, SMSGatewayConfig
)


class ExchangeConfig(pydantic.BaseModel, extra=pydantic.Extra.ignore):
    costs: Dict[str, Correction]
    # timeouts
    refresh_timeout_sec: Optional[int] = 60  # sec
    cache_timeout_sec: Optional[int] = 60 * 15  # 15 min
    kyc_photos_expiration_sec: Optional[int] = 60*60  # 1hr
    #
    methods: Dict[str, Union[Network, PaymentMethod]]
    currencies: List[Currency]
    payments: List[Payment]
    directions: List[Direction]
    paths: UrlPaths = pydantic.Field(default_factory=UrlPaths)
    merchants: Optional[Dict] = None
    identity: Optional[Identity] = None
    reports: Optional[ReportsConfig] = None
    sms: Optional[SMSGatewayConfig] = pydantic.Field(
        default_factory=SMSGatewayConfig
    )


class BestChangeCodeRule(pydantic.BaseModel):
    or_: List[str] = pydantic.Field(default_factory=list, alias='or')
    and_: List[str] = pydantic.Field(default_factory=list, alias='and')

    def match(self, s: str) -> bool:
        if self.and_:
            cnt = self._matches_count(s, self.and_)
            return cnt == len(self.and_)
        if self.or_:
            cnt = self._matches_count(s, self.or_)
            return cnt > 0
        return False

    @classmethod
    def _matches_count(cls, s: str, collection: List[str]) -> int:
        s_lower = s.lower()
        indexes = [s_lower.find(i.lower()) for i in collection]
        return len([ind for ind in indexes if ind >= 0])


class BestChangeMethodMapping(pydantic.BaseModel):
    codes: Dict[str, BestChangeCodeRule] = pydantic.Field(
        default_factory=dict
    )
    ignores: List[BestChangeCodeRule] = pydantic.Field(
        default_factory=list
    )

    @classmethod
    def default_factory(cls) -> Optional['BestChangeMethodMapping']:
        if not hasattr(settings, 'BESTCHANGE_MAPPING'):
            return None
        if settings.BESTCHANGE_MAPPING is None:
            return None
        else:
            return BestChangeMethodMapping.model_validate(settings.BESTCHANGE_MAPPING)  # noqa

    def match_codes(self, s: str) -> List[str]:
        codes = []
        for code, rule in self.codes.items():
            for ignore in self.ignores:
                if ignore.match(s):
                    return []
            if rule.match(s):
                codes.append(code)
        return codes
