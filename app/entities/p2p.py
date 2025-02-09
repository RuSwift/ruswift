from typing import List, Optional

from pydantic import BaseModel, Extra, Field


class P2POrder(BaseModel, extra=Extra.ignore):
    id: str
    trader_nick: str
    price: float
    min_amount: float
    max_amount: float
    pay_methods: List[str]
    description: Optional[str] = ''
    verified_only: Optional[bool] = None
    is_merchant: Optional[bool] = None
    is_verified: Optional[bool] = None
    bestchange_codes: List[str] = Field(default_factory=list)
    utc: Optional[float] = None


class P2POrders(BaseModel):
    asks: List[P2POrder]
    bids: List[P2POrder]
