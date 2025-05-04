from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.models.user import User
from app import crud, schemas
from app.dependencies import get_current_active_user
from app.db.session import get_db

router = APIRouter()  # This is the missing router object


@router.get("/characters", response_model=List[schemas.Character])
def get_characters(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Retrieve characters.
    """
    characters = crud.characters.get_multi(db, skip=skip, limit=limit)
    return characters


@router.get("/characters/{character_id}", response_model=schemas.Character)
def get_character(
    *,
    db: Session = Depends(get_db),
    character_id: str,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Get character by ID.
    """
    character = crud.characters.get_by_character_id(db, character_id=character_id)
    if not character:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Character not found",
        )
    return character