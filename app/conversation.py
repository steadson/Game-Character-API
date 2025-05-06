from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.sql import func

from app.db.base_class import Base


class Conversation(Base):
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)
    character_id = Column(Integer, ForeignKey("character.id"))
    message = Column(Text)
    response = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())