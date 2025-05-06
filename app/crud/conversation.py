from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.conversation import Conversation
from app.schemas.conversation import ConversationCreate


def get_user_character_history(
    db: Session, *, user_id: str, character_id: int, limit: int = 5
) -> List[Conversation]:
    """Get the conversation history for a specific user and character."""
    return (
        db.query(Conversation)
        .filter(
            Conversation.user_id == user_id,
            Conversation.character_id == character_id
        )
        .order_by(desc(Conversation.created_at))
        .limit(limit)
        .all()
    )


def create_conversation(
    db: Session, *, user_id: str, character_id: int, message: str, response: str
) -> Conversation:
    """Create a new conversation entry."""
    db_obj = Conversation(
        user_id=user_id,
        character_id=character_id,
        message=message,
        response=response
    )
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    
    # Check if we need to remove old conversations to maintain only 5
    prune_old_conversations(db, user_id=user_id, character_id=character_id, max_count=5)
    
    return db_obj


def prune_old_conversations(
    db: Session, *, user_id: str, character_id: int, max_count: int = 5
) -> None:
    """Remove old conversations to maintain only max_count recent ones."""
    # Get all conversations for this user-character pair
    conversations = (
        db.query(Conversation)
        .filter(
            Conversation.user_id == user_id,
            Conversation.character_id == character_id
        )
        .order_by(desc(Conversation.created_at))
        .all()
    )
    
    # If we have more than max_count, delete the oldest ones
    if len(conversations) > max_count:
        for conv in conversations[max_count:]:
            db.delete(conv)
        db.commit()