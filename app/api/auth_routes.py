"""Authentication and user management API routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError

from app.api.schemas import (
    LoginRequest,
    TokenResponse,
    UserCreate,
    UserResponse,
    UserUpdate,
)
from app.models.user import User
from app.services import auth as auth_service
from app.services import user_repo

router = APIRouter(prefix="/api/v1", tags=["auth"])


@router.post("/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest):
    """Authenticate a user using username + password."""
    user = auth_service.authenticate_user(payload.username, payload.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    token = auth_service.create_access_token(subject=user.username)
    return TokenResponse(access_token=token, user=user)  # type: ignore[arg-type]


@router.get("/auth/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(auth_service.get_current_active_user)):
    """Return the active user tied to the current access token."""
    return current_user


@router.get("/users", response_model=list[UserResponse], tags=["users"])
async def list_users(_: User = Depends(auth_service.get_current_active_user)):
    """List all users (simple admin helper)."""
    users = user_repo.list_users()
    return [UserResponse.model_validate(u) for u in users]


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED, tags=["users"])
async def create_user(payload: UserCreate, _: User = Depends(auth_service.get_current_active_user)):
    """Create a new user."""
    if user_repo.get_user_by_username(payload.username):
        raise HTTPException(status_code=400, detail="Username already exists")
    hashed = auth_service.get_password_hash(payload.password)
    try:
        user = user_repo.create_user(
            username=payload.username,
            hashed_password=hashed,
            email=payload.email,
            is_active=payload.is_active if payload.is_active is not None else True,
        )
    except IntegrityError as exc:
        raise HTTPException(status_code=400, detail=f"Database error: {exc}") from exc
    return UserResponse.model_validate(user)


@router.patch("/users/{user_id}", response_model=UserResponse, tags=["users"])
async def update_user(
    user_id: UUID,
    payload: UserUpdate,
    _: User = Depends(auth_service.get_current_active_user),
):
    """Update basic user fields."""
    user = user_repo.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if payload.email is not None:
        user.email = payload.email
    if payload.is_active is not None:
        user.is_active = payload.is_active
    if payload.password:
        user.hashed_password = auth_service.get_password_hash(payload.password)
    updated = user_repo.save_user(user)
    return UserResponse.model_validate(updated)
