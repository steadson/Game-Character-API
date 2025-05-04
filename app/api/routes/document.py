from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any

from app.db.session import get_db
from app.models.user import User
from app.dependencies import get_current_active_user
from app.schemas.document import DocumentCreate, DocumentResponse
from app.services.embedding import process_document
from app.crud.documents import create, get_multi, get, delete,get_by_user, update_document_status
import app.models.document as models
import app.crud.documents as crud
router = APIRouter(prefix="/documents", tags=["documents"])

@router.post("/", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    character_id: int = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Upload a document and associate it with a character."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    # Read the file content
    content = await file.read()
    
    # Create the document metadata in the database
    doc_in = DocumentCreate(
        title=file.filename,
        character_id=character_id,
        file_type=file.content_type
    )
    
    # Save the document and process for embeddings
    document = create_document(db=db, obj_in=doc_in, file_content=content)
    
    # Process the document for embeddings asynchronously
    await process_document(document.id, content, db)
    
    return document

@router.get("/", response_model=List[DocumentResponse])
async def read_documents(
    character_id: Optional[int] = None,
    skip: int = 0, 
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get all documents, optionally filtered by character ID."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    documents = get_documents(db, skip=skip, limit=limit, character_id=character_id)
    return documents

@router.get("/{document_id}", response_model=DocumentResponse)
async def read_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get a specific document by ID."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    document = get_document(db, document_id=document_id)
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    return document

@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Delete a document by ID."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    document = get_document(db, document_id=document_id)
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    delete_document(db, document_id=document_id)
    return None

# Add this new route to your existing documents.py file

@router.get("/{document_id}/content", response_model=str)
def get_document_content(
    *,
    db: Session = Depends(get_db),
    document_id: int,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Get document content by ID
    """
    document = crud.documents.get(db=db, id=document_id)
    if not document:
        raise HTTPException(
            status_code=404,
            detail="Document not found",
        )
    
    # Check if user has permission to access this document
    if not crud.user.is_admin(current_user) and document.uploaded_by != current_user.id:
        raise HTTPException(
            status_code=403, 
            detail="Not enough permissions to access this document"
        )
    
    # Handle different content types
    if document.content_type == models.document.ContentType.TEXT:
        # For text content, read the file and return the content
        try:
            with open(document.file_path, "r", encoding="utf-8") as f:
                content = f.read()
            return content
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error reading document content: {str(e)}",
            )
    elif document.content_type == models.document.ContentType.LINK:
        # For links, return the URL
        return document.file_path
    else:
        # For files, we don't return the content directly
        # Instead, inform the client that this is a file type
        raise HTTPException(
            status_code=422,
            detail="Content preview not available for file type documents",
        )
@router.post("/{document_id}/embed", response_model=Dict[str, Any])
async def embed_document(
    document_id: int,
    reembed: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Start the embedding process for a document and wait for completion."""
    # Check permissions
    if not current_user.is_admin and not current_user.is_superuser:
        # Get the document to check ownership
        document = get(db, id=document_id)
        if not document or document.uploaded_by != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions to embed this document"
            )
    
    document = get(db, id=document_id)
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    # If document is already embedded and reembed is not requested, return early
    if document.is_embedded and not reembed:
        return {
            "message": "Document is already embedded",
            "status": "embedded",
            "document_id": document.id
        }
    
    # Update status to processing
    update_document_status(db, id=document_id, is_embedded=False, status="processing")
    
    # Process document synchronously - wait for completion
    await process_document(document_id, db)
    
    # Get updated document status
    updated_document = get(db, id=document_id)
    
    # Return final result
    if updated_document.is_embedded:
        return {
            "message": "Document embedding completed successfully",
            "status": "embedded",
            "document_id": document.id
        }
    else:
        return {
            "message": "Document embedding failed",
            "status": "failed",
            "document_id": document.id
        }