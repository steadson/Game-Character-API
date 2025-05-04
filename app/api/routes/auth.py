from datetime import timedelta
from typing import Any
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.models.user import User
from app import crud, models, schemas
from app.core import security
from app.core.config import settings
from app.dependencies import get_current_user
from app.db.session import get_db

templates = Jinja2Templates(directory="app/static/templates")
router = APIRouter()


@router.post("/auth/login", response_model=schemas.Token)
def login_access_token(
    db: Session = Depends(get_db), form_data: OAuth2PasswordRequestForm = Depends()
) -> Any:
    """
    OAuth2 compatible token login, get an access token for future requests
    """
    user = crud.users.authenticate(
        db, username=form_data.username, password=form_data.password
    )
    print(user)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    elif not crud.users.is_active(user):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user",
        )
    # --- New Approval Check ---
    elif not user.is_approved:
         raise HTTPException(
             status_code=status.HTTP_403_FORBIDDEN, # Use 403 Forbidden
             detail="Account not approved by administrator.",
         )
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return {
        "access_token": security.create_access_token(
            user.id, expires_delta=access_token_expires
        ),
        "token_type": "bearer",
    }

@router.post("/register", response_model=schemas.User)
def register_user(
    *,
    db: Session = Depends(get_db),
    user_in: schemas.UserCreate,
) -> Any:
    """
    Register a new user.
    Super admins are created if the correct secret token is provided.
    Regular users require approval.
    """
    user = crud.users.get_by_email(db, email=user_in.email)
    if user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email already exists",
        )
    user = crud.users.get_by_username(db, username=user_in.username)
    if user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this username already exists",
        )

    is_super_admin = False
    is_approved = False
    is_admin = False # Default admin status to False
    if user_in.secret_token:
        if user_in.secret_token == settings.SUPER_ADMIN_SECRET_TOKEN:
            is_super_admin = True
            is_approved = True
            is_admin = True # Super admins are also admins
        else:
            # Optional: Raise error for incorrect token, or just ignore it
             raise HTTPException(
                 status_code=status.HTTP_400_BAD_REQUEST,
                 detail="Incorrect secret token provided.",
             )
    # Create user object for CRUD operation
    # We create a dictionary to avoid modifying the input Pydantic model directly
    

    # Use the dictionary to create the UserCreate schema for the CRUD function
    user_to_create = schemas.UserCreate(
        email=user_in.email,
        username=user_in.username,
        password=user_in.password, # Pass the raw password for hashing in CRUD
        full_name=user_in.full_name,
        is_active=True, # Default new users to active (approval is separate)
        is_admin=is_admin,
        is_super_admin=is_super_admin,
        is_approved=is_approved
        # Note: secret_token is intentionally omitted
    )

    user = crud.users.create(db, obj_in=user_to_create)
    return user
    # By default, new users are not admins
    # user_in.is_admin = False
    # user = crud.users.create(db, obj_in=user_in)
    # return user


@router.get("/users/me", response_model=schemas.User)
def read_users_me(
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Get current user
    """
    return current_user