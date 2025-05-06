from typing import Optional, List
from sqlalchemy.orm import Session

from app.models.api_key import ApiKey
from app.schemas.api_key import ApiKeyCreate
import secrets


def get_by_key(db: Session, key: str) -> Optional[ApiKey]:
    return db.query(ApiKey).filter(ApiKey.key == key, ApiKey.is_active == True).first()


def create(db: Session, *, obj_in: ApiKeyCreate) -> ApiKey:
    # Generate a random 34-character API key
    api_key = secrets.token_urlsafe(25)  # This generates ~34 characters
    
    db_obj = ApiKey(
        key=api_key,
        name=obj_in.name,
        is_active=True
    )
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def get_all(db: Session, skip: int = 0, limit: int = 100) -> List[ApiKey]:
    return db.query(ApiKey).offset(skip).limit(limit).all()


def deactivate(db: Session, *, id: int) -> Optional[ApiKey]:
    api_key = db.query(ApiKey).filter(ApiKey.id == id).first()
    if api_key:
        api_key.is_active = False
        db.add(api_key)
        db.commit()
        db.refresh(api_key)
    return api_key