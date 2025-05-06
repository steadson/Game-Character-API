from typing import Generator, Optional, Any
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.orm import Session
from pydantic import ValidationError
from app.models.user import User  
from app import crud, models, schemas
from app.core import security
from app.core.config import settings
from app.db.session import get_db
from fastapi.security.api_key import APIKeyHeader 

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login"
)
# API Key authentication for public endpoints
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)
async def get_api_key(
    api_key: str = Depends(api_key_header),
    db: Session = Depends(get_db)
) -> Any:
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key header missing"
        )
    
    # Check if the API key matches the environment variable
    if api_key == settings.PUBLIC_API_KEY:
        return True
    
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid API Key"
    )

def get_current_user(
    db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)
) -> User:
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        token_data = schemas.TokenPayload(**payload)
    except (JWTError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = crud.users.get(db, id=token_data.sub)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    if not crud.users.is_active(current_user):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user",
        )
    # --- New Approval Check ---
    if not current_user.is_approved:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account not approved",
        )
    # --- End New Check ---
   
    return current_user

def get_current_super_admin_user(
    current_user: User = Depends(get_current_active_user),
) -> User:
    if not crud.users.is_admin(current_user): # Check admin first
         raise HTTPException(
             status_code=status.HTTP_403_FORBIDDEN,
             detail="The user doesn't have enough privileges",
         )
    if not current_user.is_super_admin: # Then check super admin
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Requires super administrator privileges",
        )
    return current_user


def get_current_admin_user(
    current_user: User = Depends(get_current_active_user),
) -> User:
    if not crud.users.is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user doesn't have enough privileges",
        )
    return current_user