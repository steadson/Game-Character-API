from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.sql import func

#from app.db.base_class import Base
from app.db.base import Base
from sqlalchemy.orm import relationship

class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)
    character_id = Column(Integer, ForeignKey("characters.id"), index=True)
    message = Column(Text, nullable=False)
    response = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    creator = relationship("Character", foreign_keys=[character_id])