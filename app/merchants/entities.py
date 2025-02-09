from typing import List, Optional

from pydantic import BaseModel, Field, computed_field

from entities import (
    ExchangeConfig,
    BasePaymentMethod as _BasePaymentMethod, Currency as _Currency,
    Correction as _Correction, Payment as _Payment
)


class Payment(BaseModel):
    code: str
    cur: _Currency
    method: _BasePaymentMethod
    costs: List[_Correction] = Field(default_factory=list)


class Direction(BaseModel):
    order_id: Optional[int] = 0
    src: Payment
    dest: Payment

    @computed_field
    @property
    def is_enabled(self) -> bool:
        for p in [self.src, self.dest]:
            if not p.cur.is_enabled:
                return False
            if not p.method.is_enabled:
                return False
        return True


def load_directions(cfg: ExchangeConfig) -> List[Direction]:

    result = []

    def _load_cur(symbol: str) -> _Currency:
        for cur in cfg.currencies:
            if symbol == cur.symbol:
                return cur
        raise ValueError(f'Unknown currency "{symbol}"')

    def _load_payment_meth(code: str) -> _BasePaymentMethod:
        for i, details in cfg.methods.items():
            if code == i:
                return details
        raise ValueError(f'Unknown method "{code}"')

    def _load_payment(code: str) -> _Payment:
        for detail in cfg.payments:
            if code == detail.code:
                return detail
        raise ValueError(f'Unknown payment "{code}"')

    def _build_payment(code: str, cost_attr: str) -> Payment:
        p = _load_payment(code)
        return Payment(
            code=code,
            cur=_load_cur(p.cur),
            method=_load_payment_meth(p.method),
            costs=_load_costs(p, cost_attr)
        )

    def _load_cost(code: str) -> _Correction:
        for i, detail in cfg.costs.items():
            if i == code:
                return detail
        raise ValueError(f'Unknown cost "{code}"')

    def _load_costs(p: _Payment, cost_attr: str) -> List[_Correction]:
        _cors = getattr(p.costs, cost_attr) or []
        if isinstance(_cors, str):
            _cors = [_cors]
        return [_load_cost(i) for i in _cors]

    for _dir in cfg.directions:
        direction = Direction(
            order_id=_dir.order_id,
            src=_build_payment(_dir.src, cost_attr='income'),
            dest=_build_payment(_dir.dest, cost_attr='outcome')
        )
        result.append(direction)

    return result
