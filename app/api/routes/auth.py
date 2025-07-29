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
from app.core.security import verify_password
from app.core.config import settings
from app.schemas.admin_secret import AdminSecretRequest, AdminSecretCreate
from app.dependencies import get_current_user, get_current_super_admin_user
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
    # Strip trailing spaces and convert to lowercase for email and username
    email = user_in.email.strip().lower() if user_in.email else None
    username = user_in.username.strip().lower() if user_in.username else None
    full_name = user_in.full_name.strip() if user_in.full_name else None
    
    # Check for existing users with cleaned data
    user = crud.users.get_by_email(db, email=email)
    if user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email already exists",
        )
    user = crud.users.get_by_username(db, username=username)
    if user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this username already exists",
        )

    is_super_admin = False
    is_approved = False
    is_admin = False # Default admin status to False
    if user_in.secret_token:
        # Get current active secret or use default from .env
        current_secret = crud.admin_secret.get_current_secret_token(db, settings.SUPER_ADMIN_SECRET_TOKEN)
        if user_in.secret_token == current_secret:
            # Check if we already have 2 super admins
            super_admin_count = crud.users.get_super_admin_count(db)
            if super_admin_count >= 2:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Maximum number of super administrators (2) already exists. Cannot create more super admin accounts.",
                )
            is_super_admin = True
            is_approved = True
            is_admin = True # Super admins are also admins
        else:
            # Optional: Raise error for incorrect token, or just ignore it
             raise HTTPException(
                 status_code=status.HTTP_400_BAD_REQUEST,
                 detail="Incorrect secret token provided.",
             )
    
    # Clean and prepare security questions and answers
    security_question_1 = user_in.security_question_1.strip() if user_in.security_question_1 else None
    security_answer_1 = user_in.security_answer_1.strip().lower() if user_in.security_answer_1 else None
    security_question_2 = user_in.security_question_2.strip() if user_in.security_question_2 else None
    security_answer_2 = user_in.security_answer_2.strip().lower() if user_in.security_answer_2 else None

    # Use the cleaned data to create the UserCreate schema for the CRUD function
    user_to_create = schemas.UserCreate(
        email=email,
        username=username,
        password=user_in.password, # Keep password as-is for security
        full_name=full_name,
        is_active=True, # Default new users to active (approval is separate)
        is_admin=is_admin,
        is_super_admin=is_super_admin,
        is_approved=is_approved,
        # Security questions with cleaned data
        security_question_1=security_question_1,
        security_answer_1=security_answer_1,
        security_question_2=security_question_2,
        security_answer_2=security_answer_2
        # Note: secret_token is intentionally omitted
    )

    user = crud.users.create(db, obj_in=user_to_create)
    return user
# New password reset endpoints
@router.post("/auth/forgot-password")
def forgot_password(
    *,
    db: Session = Depends(get_db),
    request: schemas.PasswordResetRequest,
) -> Any:
    """
    Get security questions for password reset
    """
    if request.email:
        user = crud.users.get_by_email(db, email=request.email)
    elif request.username:
        user = crud.users.get_by_username(db, username=request.username)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either email or username must be provided",
        )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    if not user.security_question_1 or not user.security_question_2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Security questions not set for this user",
        )
    
    return {
        "security_question_1": user.security_question_1,
        "security_question_2": user.security_question_2
    }


@router.post("/auth/reset-password")
def reset_password(
    *,
    db: Session = Depends(get_db),
    request: schemas.PasswordResetVerify,
) -> Any:
    """
    Reset password using security question answers
    """
    user = crud.users.verify_security_answers(
        db, 
        username=request.username, 
        email=request.email,
        answer_1=request.answer_1, 
        answer_2=request.answer_2
    )
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid username/email or security answers",
        )
    
    # Reset the password
    crud.users.reset_password(db, user=user, new_password=request.new_password)
    
    return {"message": "Password reset successfully"}

@router.get("/users/me", response_model=schemas.User)
def read_users_me(
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Get current user
    """
    return current_user

@router.put("/users/me", response_model=schemas.User)
def update_user_me(
    *,
    db: Session = Depends(get_db),
    user_in: schemas.UserProfileUpdate,
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Update own user profile.
    """
    # Check if email/username already exists for other users
    if user_in.email and user_in.email != current_user.email:
        existing_user = crud.users.get_by_email(db, email=user_in.email)
        if existing_user and existing_user.id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A user with this email already exists",
            )
    
    if user_in.username and user_in.username != current_user.username:
        existing_user = crud.users.get_by_username(db, username=user_in.username)
        if existing_user and existing_user.id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A user with this username already exists",
            )
    
    user = crud.users.update(db, db_obj=current_user, obj_in=user_in)
    return user

@router.put("/admin/secret")
def update_admin_secret(
    *,
    db: Session = Depends(get_db),
    request: AdminSecretRequest,
    current_user: User = Depends(get_current_super_admin_user),
) -> Any:
    """
    Update the admin secret token (super admin only)
    """
    # Verify the current user's password
    if not verify_password(request.password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect password",
        )
    
    if request.use_default:
        # Use default secret from .env
        secret_token = settings.SUPER_ADMIN_SECRET_TOKEN
    else:
        if not request.custom_secret:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Custom secret token is required",
            )
        secret_token = request.custom_secret
    
    # Create new admin secret
    secret_create = schemas.AdminSecretCreate(
        secret_token=secret_token,
        created_by=current_user.id
    )
    
    crud.admin_secret.create(db, obj_in=secret_create)
    
    return {"message": "Admin secret updated successfully"}