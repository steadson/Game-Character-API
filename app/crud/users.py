from typing import Any, Dict, Optional, Union

from sqlalchemy.orm import Session

from app.core.security import get_password_hash, verify_password
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate


def get_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email).first()


def get_by_username(db: Session, username: str) -> Optional[User]:
    return db.query(User).filter(User.username == username).first()


def get(db: Session, id: int) -> Optional[User]:
    return db.query(User).filter(User.id == id).first()

def approve_user(db: Session, *, user_to_approve: User) -> User:
    """Sets the is_approved flag for a user to True."""
    if not user_to_approve:
        return None
    user_to_approve.is_approved = True
    db.add(user_to_approve)
    db.commit()
    db.refresh(user_to_approve)
    return user_to_approve

def get_multi(
    db: Session, *, skip: int = 0, limit: int = 100
) -> list[User]:
    return db.query(User).offset(skip).limit(limit).all()


def create(db: Session, *, obj_in: UserCreate) -> User:

    # --- Modification Start ---
    # Explicitly create the dictionary for the DB model constructor
    # This ensures only fields defined in the models.User class are included.
    db_model_data = {
        "email": obj_in.email,
        "username": obj_in.username,
        #"full_name": obj_in.full_name,
        "hashed_password": get_password_hash(obj_in.password),
        # Use values from obj_in, falling back to defaults if necessary
        "is_active": obj_in.is_active if obj_in.is_active is not None else True,
        "is_admin": obj_in.is_admin,
        "is_super_admin": obj_in.is_super_admin,
        "is_approved": obj_in.is_approved,
    }
    # --- Modification End ---

    # Create the SQLAlchemy User model instance using the explicitly built dictionary
    db_obj = User(**db_model_data) # Now uses db_model_data

    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj

def update(
    db: Session, *, db_obj: User, obj_in: Union[UserUpdate, Dict[str, Any]]
) -> User:
    if isinstance(obj_in, dict):
        update_data = obj_in
    else:
        update_data = obj_in.dict(exclude_unset=True)
    if update_data.get("password"):
        hashed_password = get_password_hash(update_data["password"])
        del update_data["password"]
        update_data["hashed_password"] = hashed_password
    for field in update_data:
        if field in update_data:
            setattr(db_obj, field, update_data[field])
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def authenticate(
    db: Session, *, username: str, password: str
) -> Optional[User]:
    user = get_by_username(db, username=username)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def is_active(user: User) -> bool:
    return user.is_active


def is_admin(user: User) -> bool:
    return user.is_admin