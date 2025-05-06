from typing import Optional
from pydantic import BaseModel
from datetime import datetime


class ApiKeyBase(BaseModel):
    name: str


class ApiKeyCreate(ApiKeyBase):
    pass


class ApiKeyInDB(ApiKeyBase):
    id: int
    key: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ApiKey(ApiKeyInDB):
    pass