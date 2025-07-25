from sqlalchemy import Boolean, Column, Integer, String, DateTime
from sqlalchemy.sql import func

from app.db.base import Base


class AdminSecret(Base):
    __tablename__ = "admin_secrets"

    id = Column(Integer, primary_key=True, index=True)
    secret_token = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_by = Column(Integer, nullable=False)  # User ID who created this secret
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())