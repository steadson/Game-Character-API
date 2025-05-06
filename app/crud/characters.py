from typing import Any, Dict, Optional, Union, List

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.character import Character
from app.models.document import Document
from app.schemas.character import CharacterCreate, CharacterUpdate


def get_by_character_id(db: Session, character_id: str) -> Optional[Character]:
    return db.query(Character).filter(Character.character_id == character_id).first()


def get_character(db: Session, id: int) -> Optional[Character]:
   return db.query(Character).filter(Character.id == id).first()


def get_multi(
    db: Session, *, skip: int = 0, limit: int = 100
) -> List[Character]:
    return db.query(Character).offset(skip).limit(limit).all()


def get_multi_with_document_count(
    db: Session, *, skip: int = 0, limit: int = 100
) -> List[Dict]:
    characters = db.query(Character).offset(skip).limit(limit).all()
    result = []
    
    for character in characters:
        # Since we're dissociating characters and documents, set document_count to 0
        char_dict = {**character.__dict__}
        if '_sa_instance_state' in char_dict:
            del char_dict['_sa_instance_state']
        char_dict['document_count'] = 0  # No relationship, so always 0
        result.append(char_dict)
    
    return result


def create(db: Session, *, obj_in: CharacterCreate, created_by: int) -> Character:
    db_obj = Character(
        character_id=obj_in.character_id,
        name=obj_in.name,
        description=obj_in.description,
        backstory=obj_in.backstory,
        personality=obj_in.personality,
        system_prompt=obj_in.system_prompt,
        created_by=created_by,
    )
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def update(
    db: Session, *, db_obj: Character, obj_in: Union[CharacterUpdate, Dict[str, Any]]
) -> Character:
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


def delete(db: Session, *, id: int) -> Character:
    obj = db.query(Character).get(id)
    db.delete(obj)
    db.commit()
    return obj

def get_by_user(db: Session, *, user_id: int) -> List[Character]:
    """Get all characters created by a specific user."""
    return db.query(Character).filter(Character.created_by == user_id).all()