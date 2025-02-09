from uuid import uuid4
from datetime import datetime
from typing import List, Dict, Optional

from .base import BaseEntity, Field


def generate_uid() -> str:
    return uuid4().hex


class StorageItem(BaseEntity):
    uid: str = Field(default_factory=generate_uid)
    storage_id: Optional[str] = None
    category: str
    signature: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    updated_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    payload: Dict
    storage_ids: Optional[List[str]] = Field(default_factory=list)
