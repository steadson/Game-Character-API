from pathlib import Path
from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
import os
import shutil
from app.models.user import User
import asyncio
from app import crud, models, schemas
from app.dependencies import get_current_admin_user, get_current_active_user,get_current_super_admin_user
from app.db.session import get_db
from app.models.document import DocumentType
from app.services.scheduler import update_refresh_interval, document_scheduler
from pydantic import BaseModel

router = APIRouter()

class RefreshIntervalUpdate(BaseModel):
    hours: int
    enabled: bool = True


@router.get("/characters", response_model=List[schemas.CharacterWithDocuments])
def get_characters(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Retrieve characters with document count
    """
    characters = crud.characters.get_multi_with_document_count(db, skip=skip, limit=limit)
    return characters


@router.post("/characters", response_model=schemas.Character)
def create_character(
    *,
    db: Session = Depends(get_db),
    character_in: schemas.CharacterCreate,
    current_user: User = Depends(get_current_admin_user),
) -> Any:
    """
    Create new character
    """
    character = crud.characters.get_by_character_id(db, character_id=character_in.character_id)
    if character:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A character with this ID already exists",
        )
    character = crud.characters.create(db, obj_in=character_in, created_by=current_user.id)
    return character


@router.get("/characters/{id}", response_model=schemas.Character)
def get_character(
    *,
    db: Session = Depends(get_db),
    id: int,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Get character by ID
    """
    character = crud.characters.get_character(db, id=id)
    if not character:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Character not found",
        )
    return character


@router.put("/characters/{id}", response_model=schemas.Character)
def update_character(
    *,
    db: Session = Depends(get_db),
    id: int,
    character_in: schemas.CharacterUpdate,
    current_user: User = Depends(get_current_admin_user),
) -> Any:
    """
    Update a character
    """
    character = crud.characters.get_character(db, id=id)
    if not character:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Character not found",
        )
    character = crud.characters.update(db, db_obj=character, obj_in=character_in)
    return character

@router.post("/characters/{id}/image")
def upload_character_image(
    *,
    db: Session = Depends(get_db),
    id: int,
    image: UploadFile = File(...),
    current_user: User = Depends(get_current_admin_user),
) -> Any:
    """
    Upload an image for a character
    """
    character = crud.characters.get_character(db, id=id)
    if not character:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Character not found",
        )
    
    # Create directory if it doesn't exist
    upload_dir = Path("app/static/uploads/characters")
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate a unique filename
    file_extension = os.path.splitext(image.filename)[1]
    filename = f"character_{id}{file_extension}"
    file_path = upload_dir / filename
    
    # Save the file
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(image.file, buffer)
    
    # Update character with image URL
    image_url = f"/static/uploads/characters/{filename}"
    character_update = schemas.CharacterUpdate(image_url=image_url)
    character = crud.characters.update(db=db, db_obj=character, obj_in=character_update)
    
    return {"filename": filename, "image_url": image_url}

@router.delete("/characters/{id}", response_model=schemas.Character)
def delete_character(
    *,
    db: Session = Depends(get_db),
    id: int,
    current_user: User = Depends(get_current_admin_user),
) -> Any:
    """
    Delete a character
    """
    character = crud.characters.get_character(db, id=id)
    if not character:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Character not found",
        )
    character = crud.characters.delete(db, id=id)
    return character


@router.get("/documents", response_model=List[schemas.DocumentInfo])
def get_documents(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Retrieve documents
    """
    documents = crud.documents.get_multi(db, skip=skip, limit=limit)
    return documents

# Add this near the top with other routes
@router.get("/admin/stats")
def get_admin_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
) -> Any:
    """
    Get admin dashboard statistics
    """
    # Add your stats logic here
    return {
        "total_characters": len(crud.characters.get_multi(db)),
        "total_documents": len(crud.documents.get_multi(db)),
        "total_users": len(crud.users.get_multi(db))
    }

@router.post("/documents", response_model=schemas.Document)
async def create_document(
    *,
    db: Session = Depends(get_db),
    title: str = Form(...),
    description: str = Form(None),
    document_type: DocumentType = Form(...),
    content_type: str = Form(...),
    character_id: int = Form(None),
    file: UploadFile = File(None),  # Make file optional
    text_content: str = Form(None),  # Add text_content parameter
    link_url: str = Form(None),     # Add link_url parameter
    current_user: User = Depends(get_current_admin_user),
) -> Any:
    """
    Create new document
    """
    # Validate character exists if character_id is provided
    if character_id:
        character = crud.characters.get(db, id=character_id)
        if not character:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Character not found",
            )
    
    
    
    # Create document
    document_in = schemas.DocumentCreate(
        title=title,
        description=description,
        document_type=document_type,
        character_id=character_id,
    )
    # Handle different content types
    if content_type == "file":
        if not file:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File is required for file content type",
            )
        file_content = await file.read()
        document = crud.documents.create(
            db=db, 
            obj_in=document_in, 
            uploaded_by=current_user.id, 
            file_content=file_content,
            original_filename=file.filename
        )
    elif content_type == "text":
        if not text_content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Text content is required for text content type",
            )
        document = crud.documents.create(
            db=db, 
            obj_in=document_in, 
            uploaded_by=current_user.id,
            text_content=text_content,
            original_filename=f"{title}.txt"
        )
    elif content_type == "link":
        if not link_url:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="URL is required for link content type",
            )
        document = crud.documents.create(
            db=db, 
            obj_in=document_in, 
            uploaded_by=current_user.id,
            link_url=link_url,
            original_filename=f"link_{title}"
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid content type",
        )
    
    
    # TODO: Trigger embedding process asynchronously
    
    return document


@router.get("/documents/{id}", response_model=schemas.DocumentInfo)
def get_document(
    *,
    db: Session = Depends(get_db),
    id: int,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Get document by ID
    """
    document = crud.documents.get(db, id=id)
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    return document

# Add this new route to your existing documents.py file

@router.get("/documents/{document_id}/content", response_model=str)
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
    if not current_user.is_admin and document.uploaded_by != current_user.id:
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

@router.get("/admin/users", response_model=List[schemas.User])
def get_users(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_admin_user),
) -> Any:
    """
    Retrieve all users (super admin only)
    """
    users = crud.users.get_multi(db, skip=skip, limit=limit)
    return users

@router.get("/admin/users/{user_id}", response_model=schemas.User)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
) -> Any:
    """
    Get a specific user by ID (super admin only)
    """
    user = crud.users.get(db, id=user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return user

@router.put("/admin/users/{user_id}/approve", response_model=schemas.User)
def approve_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_super_admin_user),
) -> Any:
    """
    Approve a user (super admin only)
    """
    user = crud.users.get(db, id=user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    # Update user to approved status
    user_in = {"is_approved": True, "is_admin":True, "is_active": True}
    user = crud.users.update(db, db_obj=user, obj_in=user_in)
    return user

@router.put("/admin/users/{user_id}/deactivate", response_model=schemas.User)
def deactivate_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_super_admin_user),
) -> Any:
    """
    Deactivate a user (super admin only)
    """
    user = crud.users.get(db, id=user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    # Prevent deactivating yourself
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot deactivate your own account",
        )
    
    # Update user to inactive status
    user_in = {"is_approved": False, "is_admin":True, "is_active": False}
    user = crud.users.update(db, db_obj=user, obj_in=user_in)
    return user

@router.put("/admin/users/{user_id}/activate", response_model=schemas.User)
def activate_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_super_admin_user),
) -> Any:
    """
    Activate a user (super admin only)
    """
    user = crud.users.get(db, id=user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    # Update user to active status
    user_in = {"is_active": True}
    user = crud.users.update(db, db_obj=user, obj_in=user_in)
    return user

@router.get("/admin/users/{user_id}/characters", response_model=List[schemas.Character])
def get_user_characters(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
) -> Any:
    """
    Get all characters created by a specific user (super admin only)
    """
    user = crud.users.get(db, id=user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    characters = crud.characters.get_by_user(db, user_id=user_id)
    return characters

@router.get("/admin/users/{user_id}/documents", response_model=List[schemas.Document])
def get_user_documents(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
) -> Any:
    """
    Get all documents uploaded by a specific user (super admin only)
    """
    user = crud.users.get(db, id=user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    documents = crud.documents.get_by_user(db, user_id=user_id)
    return documents

@router.post("/admin/users/{user_id}/approve", response_model=schemas.User)
def approve_user_endpoint(
    *,
    db: Session = Depends(get_db),
    user_id: int,
    # Use admin dependency and check is_super_admin, or use specific super_admin dependency
    current_user: User = Depends(get_current_admin_user),
) -> Any:
    """
    Approve a user registration (Requires super admin privileges).
    """
    if not current_user.is_super_admin:
         raise HTTPException(
             status_code=status.HTTP_403_FORBIDDEN,
             detail="Requires super administrator privileges",
         )

    user_to_approve = crud.users.get(db, id=user_id)
    if not user_to_approve:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    if user_to_approve.is_approved:
         raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already approved",
        )

    approved_user = crud.users.approve_user(db=db, user_to_approve=user_to_approve)
    return approved_user

# --- End User Management Endpoints ---


# ... rest of your admin routes (characters, documents, stats, etc.) ...
# Make sure the stats endpoint also checks for super admin if needed
@router.get("/stats")
def get_admin_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user), # Check is_super_admin inside if needed
) -> Any:
    """
    Get admin dashboard statistics
    """
    # Example: Restrict stats view to super admins if desired
    # if not current_user.is_super_admin:
    #     raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requires super admin")

    return {
        "total_characters": len(crud.characters.get_multi(db)),
        "total_documents": len(crud.documents.get_multi(db)),
        "total_users": len(crud.users.get_multi(db)) # Assumes get_multi exists in crud.users
    }
@router.get("/document-refresh/settings")
async def get_document_refresh_settings(
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Get current document refresh settings
    """
    return {
        "hours": document_scheduler.refresh_interval,
        "enabled": document_scheduler.is_enabled,
        "last_refresh": document_scheduler.last_refresh_time.isoformat() if document_scheduler.last_refresh_time else None,
        "status": "completed" if not document_scheduler.is_running else "in_progress"
    }
@router.post("/document-refresh/settings", response_model=dict)
async def set_document_refresh_interval(
    *,
    settings: RefreshIntervalUpdate,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Set the interval for automatic document refreshing
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    if settings.hours < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Refresh interval must be at least 1 hour"
        )
    
    result = await update_refresh_interval(settings.hours, settings.enabled)
    return result

@router.post("/document-refresh/now", response_model=dict)
async def trigger_document_refresh(
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Manually trigger a document refresh
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    # Trigger the refresh process
    asyncio.create_task(document_scheduler._refresh_documents())
    return {"status": "success", "message": "Document refresh process started"}

# Add this after your other document refresh endpoints

@router.get("/document-refresh/status", response_model=dict)
async def get_document_refresh_status(
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Get the current status of document refresh process
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    # Check if refresh is in progress
    is_running = document_scheduler.is_running
    
    # Get progress information
    processed = document_scheduler.processed_count if hasattr(document_scheduler, 'processed_count') else 0
    total = document_scheduler.total_count if hasattr(document_scheduler, 'total_count') else 0
    current_status = "in_progress" if is_running else "completed"
    
    return {
        "status": current_status,
        "processed": processed,
        "total": total,
        "last_refresh": document_scheduler.last_refresh_time.isoformat() if document_scheduler.last_refresh_time else None
    }
@router.delete("/documents/{id}", response_model=schemas.DocumentInfo)
def delete_document(
    *,
    db: Session = Depends(get_db),
    id: int,
    current_user: User = Depends(get_current_admin_user),
) -> Any:
    """
    Delete a document
    """
    document = crud.documents.get(db, id=id)
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    document = crud.documents.delete(db, id=id)
    return document

