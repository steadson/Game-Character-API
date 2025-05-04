from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field


# Shared properties
class CharacterBase(BaseModel):
    character_id: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    backstory: Optional[str] = None
    personality: Optional[str] = None
    system_prompt: Optional[str] = None
    is_active: Optional[bool] = True
    image_url: Optional[str] = None 


# Properties to receive via API on creation
class CharacterCreate(CharacterBase):
    character_id: str
    name: str
    description: str
    personality: str
    system_prompt: str


# Properties to receive via API on update
class CharacterUpdate(CharacterBase):
    pass


class CharacterInDBBase(CharacterBase):
    id: Optional[int] = None
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# Additional properties to return via API
class Character(CharacterInDBBase):
    pass


# Additional properties to return via API with document count
class CharacterWithDocuments(Character):
    document_count: int = 0