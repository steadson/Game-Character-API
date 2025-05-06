from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func

from app.db.base_class import Base


class ApiKey(Base):
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, index=True)
    name = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())