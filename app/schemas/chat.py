from typing import Optional, List
from pydantic import BaseModel


class ChatRequest(BaseModel):
    character_id: int
    message: str
    chat_history_id: Optional[int] = None


class ChatResponse(BaseModel):
    response: str
    character: dict
    sources: List[dict]


class ChatHistory(BaseModel):
    id: int
    user_id: int
    character_id: int
    title: Optional[str] = None
    created_at: str
    
    class Config:
        from_attributes = True


class ChatMessage(BaseModel):
    id: int
    chat_history_id: int
    is_user: bool
    message: str
    created_at: str
    
    class Config:
        from_attributes = True