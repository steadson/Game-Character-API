from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime


class ConversationBase(BaseModel):
    user_id: str
    character_id: int
    message: str
    response: str


class ConversationCreate(ConversationBase):
    pass


class ConversationInDB(ConversationBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class Conversation(ConversationInDB):
    pass


class ConversationHistory(BaseModel):
    conversations: List[Conversation]