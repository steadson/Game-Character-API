from sqlalchemy import Boolean, Column, Integer, String, Text, DateTime, ForeignKey, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum

from app.db.base import Base


class DocumentType(str, enum.Enum):
    INTERNAL_DOC = "internal_documentation"
    PARTNER_DOC = "partner_documentation"
    KNOWLEDGE_BASE = "knowledge_base"
    REFERENCE = "reference"
    INSTRUCTION = "instruction"
    OTHER = "other"


class ContentType(str, enum.Enum):
    FILE = "file"
    TEXT = "text"
    LINK = "link"


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    file_path = Column(String, nullable=False)  # For files: path, for links: URL
    original_filename = Column(String, nullable=False)
    document_type = Column(Enum(DocumentType), nullable=False)
    content_type = Column(Enum(ContentType), default=ContentType.FILE, nullable=False)
    is_embedded = Column(Boolean, default=False)
    embedding_status = Column(String, default="pending")
    uploaded_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    uploader = relationship("User")