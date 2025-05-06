from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, HttpUrl
from app.models.document import DocumentType, ContentType

class EmbedRequest(BaseModel):
    reembed: bool = False
# Shared properties
class DocumentBase(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    document_type: Optional[DocumentType] = None


# Properties to receive via API on creation
class DocumentCreate(DocumentBase):
    title: str
    document_type: DocumentType


# Properties for text content
class TextDocumentCreate(DocumentCreate):
    text_content: str


# Properties for link content
class LinkDocumentCreate(DocumentCreate):
    link_url: HttpUrl


# Properties to receive via API on update
class DocumentUpdate(DocumentBase):
    pass


class DocumentInDBBase(DocumentBase):
    id: Optional[int] = None
    file_path: str
    original_filename: str
    content_type: ContentType
    is_embedded: bool
    embedding_status: str
    uploaded_by: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# Additional properties to return via API
class Document(DocumentInDBBase):
    pass

class DocumentResponse(DocumentInDBBase):
    """Response model for document API endpoints"""
    pass


# Schema for document metadata without the file path
class DocumentInfo(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    document_type: DocumentType
    content_type: ContentType
    original_filename: str
    is_embedded: bool
    embedding_status: str
    created_at: datetime
    
    class Config:
        from_attributes = True