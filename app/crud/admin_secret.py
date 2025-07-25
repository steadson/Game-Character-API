from typing import Optional
from sqlalchemy.orm import Session

from app.models.admin_secret import AdminSecret
from app.schemas.admin_secret import AdminSecretCreate, AdminSecretUpdate


def get_active_secret(db: Session) -> Optional[AdminSecret]:
    """Get the currently active admin secret"""
    return db.query(AdminSecret).filter(AdminSecret.is_active == True).first()


def create(db: Session, *, obj_in: AdminSecretCreate) -> AdminSecret:
    """Create a new admin secret and deactivate all others"""
    # Deactivate all existing secrets
    db.query(AdminSecret).update({AdminSecret.is_active: False})
    
    # Create new secret
    db_obj = AdminSecret(
        secret_token=obj_in.secret_token,
        is_active=True,
        created_by=obj_in.created_by
    )
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def get_current_secret_token(db: Session, default_secret: str) -> str:
    """Get the current active secret token or return default from .env"""
    active_secret = get_active_secret(db)
    if active_secret:
        return active_secret.secret_token
    return default_secret