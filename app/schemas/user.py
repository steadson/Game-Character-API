from typing import Optional
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field


# Shared properties
class UserBase(BaseModel):
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    full_name: Optional[str] = None
    is_active: Optional[bool] = True
    is_admin: bool = False
    is_super_admin: bool = False # New field
    is_approved: bool = False # New field


# Properties to receive via API on creation
class UserCreate(UserBase):
    email: EmailStr
    username: str
    password: str
    secret_token: Optional[str] = None #
    # Security questions
    security_question_1: Optional[str] = None
    security_answer_1: Optional[str] = None
    security_question_2: Optional[str] = None
    security_answer_2: Optional[str] = None


# Properties to receive via API on update
class UserUpdate(UserBase):
    password: Optional[str] = None
    # Security questions
    full_name: Optional[str] = None
    security_question_1: Optional[str] = None
    security_answer_1: Optional[str] = None
    security_question_2: Optional[str] = None
    security_answer_2: Optional[str] = None


class UserProfileUpdate(BaseModel):
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    full_name: Optional[str] = None
    password: Optional[str] = None
    security_question_1: Optional[str] = None
    security_answer_1: Optional[str] = None
    security_question_2: Optional[str] = None
    security_answer_2: Optional[str] = None

# Schema for password reset request
class PasswordResetRequest(BaseModel):
    email: Optional[EmailStr] = None
    username: Optional[str] = None


# Schema for password reset verification
class PasswordResetVerify(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    answer_1: str
    answer_2: str
    new_password: str

class UserInDBBase(UserBase):
    id: Optional[int] = None
    security_question_1: Optional[str] = None
    security_question_2: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# Additional properties to return via API
class User(UserInDBBase):
    pass


# Additional properties stored in DB
class UserInDB(UserInDBBase):
    hashed_password: str