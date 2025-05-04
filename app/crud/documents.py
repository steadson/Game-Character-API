import os
from typing import Any, Dict, Optional, Union, List
import uuid

from sqlalchemy.orm import Session

from app.models.document import Document, DocumentType, ContentType
from app.schemas.document import DocumentCreate, DocumentUpdate
from app.core.config import settings


def get(db: Session, id: int) -> Optional[Document]:
    return db.query(Document).filter(Document.id == id).first()


def get_multi(
    db: Session, *, skip: int = 0, limit: int = 100
) -> List[Document]:
    return db.query(Document).offset(skip).limit(limit).all()


def create(
    db: Session, 
    *, 
    obj_in: DocumentCreate, 
    uploaded_by: int, 
    file_content: Optional[bytes] = None,
    original_filename: Optional[str] = None,
    text_content: Optional[str] = None,
    link_url: Optional[str] = None
) -> Document:
    # Determine content type and handle accordingly
    content_type = ContentType.FILE
    file_path = None
    
    if file_content and original_filename:
        # Handle file upload
        content_type = ContentType.FILE
        
        # Create document storage directory if it doesn't exist
        os.makedirs(settings.DOCUMENT_STORAGE_PATH, exist_ok=True)
        
        # Generate a unique filename to avoid collisions
        file_uuid = str(uuid.uuid4())
        file_extension = os.path.splitext(original_filename)[1].lower()
        unique_filename = f"{file_uuid}{file_extension}"
        file_path = os.path.join(settings.DOCUMENT_STORAGE_PATH, unique_filename)
        
        # Write the file to disk
        with open(file_path, "wb") as f:
            f.write(file_content)
    
    elif text_content:
        # Handle text content
        content_type = ContentType.TEXT
        
        # Create document storage directory if it doesn't exist
        os.makedirs(settings.DOCUMENT_STORAGE_PATH, exist_ok=True)
        
        # Generate a unique filename for the text content
        file_uuid = str(uuid.uuid4())
        unique_filename = f"{file_uuid}.txt"
        file_path = os.path.join(settings.DOCUMENT_STORAGE_PATH, unique_filename)
        
        # Write the text content to disk
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(text_content)
        
        # If no original filename provided, use a default
        if not original_filename:
            original_filename = f"{obj_in.title[:30]}.txt"
    
    elif link_url:
        # Handle link URL
        content_type = ContentType.LINK
        file_path = link_url  # Store the URL in the file_path field
        
        # If no original filename provided, use a default
        if not original_filename:
            original_filename = f"link_{obj_in.title[:30]}"
    
    # Create document record in database
    db_obj = Document(
        title=obj_in.title,
        description=obj_in.description,
        document_type=obj_in.document_type,
        content_type=content_type,
        file_path=file_path,
        original_filename=original_filename or "untitled",
        is_embedded=False,
        embedding_status="pending",
        uploaded_by=uploaded_by,
    )
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def update(
    db: Session, *, db_obj: Document, obj_in: Union[DocumentUpdate, Dict[str, Any]]
) -> Document:
    if isinstance(obj_in, dict):
        update_data = obj_in
    else:
        update_data = obj_in.dict(exclude_unset=True)
    for field in update_data:
        if field in update_data:
            setattr(db_obj, field, update_data[field])
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def delete(db: Session, *, id: int) -> Document:
    obj = db.query(Document).get(id)
    
    # Delete the file from disk if it exists and is a file (not a link)
    if obj and obj.content_type == ContentType.FILE and os.path.exists(obj.file_path):
        os.remove(obj.file_path)
    
    db.delete(obj)
    db.commit()
    return obj


def update_document_status(db: Session, *, document=None, id=None, is_embedded: bool, status: str):
    if document is None and id is not None:
        document = get(db, id=id)
    
    if document:
        document.is_embedded = is_embedded
        document.status = status
        db.add(document)
        db.commit()
        db.refresh(document)  # Refresh the document, not the db
        return document
    return None

def get_by_user(db: Session, *, user_id: int) -> List[Document]:
    """Get all documents uploaded by a specific user."""
    return db.query(Document).filter(Document.uploaded_by == user_id).all()