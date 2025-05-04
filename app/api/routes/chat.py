from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.models.user import User
from app import crud, models
from app.dependencies import get_current_active_user
from app.db.session import get_db
from app.services.rag import generate_character_response

router = APIRouter()


class ChatRequest(BaseModel):
    character_id: str
    message: str
    user_id: str = None


class ChatResponse(BaseModel):
    response: str


@router.post("", response_model=ChatResponse)
def chat_with_character(
    *,
    db: Session = Depends(get_db),
    chat_request: ChatRequest,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Chat with a game character
    """
    # Validate character exists
    character = crud.characters.get_by_character_id(db, character_id=chat_request.character_id)
    if not character:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Character not found",
        )
    
    # Generate response using RAG
    response = generate_character_response(
        db=db,
        character=character,
        message=chat_request.message,
        user_id=chat_request.user_id or f"user_{current_user.id}"
    )
    
    return {"response": response}