from typing import Optional
from pydantic import BaseModel
from datetime import datetime


class AdminSecretBase(BaseModel):
    secret_token: str
    is_active: bool = True


class AdminSecretCreate(AdminSecretBase):
    created_by: int


class AdminSecretUpdate(BaseModel):
    secret_token: Optional[str] = None
    is_active: Optional[bool] = None


class AdminSecretInDB(AdminSecretBase):
    id: int
    created_by: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AdminSecret(AdminSecretInDB):
    pass


class AdminSecretRequest(BaseModel):
    password: str
    use_default: bool = True
    custom_secret: Optional[str] = None