"""Database helpers for user management."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlmodel import Session, select

from app.db.engine import engine
from app.models.user import User


def _persist(session: Session, user: User) -> User:
    """Persist helper to DRY up commits."""
    user.updated_at = datetime.utcnow()
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def create_user(
    *,
    username: str,
    hashed_password: str,
    email: Optional[str] = None,
    is_active: bool = True,
) -> User:
    """Create a user with a pre-hashed password."""
    user = User(
        username=username,
        hashed_password=hashed_password,
        email=email,
        is_active=is_active,
    )
    with Session(engine) as session:
        return _persist(session, user)


def get_user_by_username(username: str) -> Optional[User]:
    """Lookup a user by username."""
    with Session(engine) as session:
        statement = select(User).where(User.username == username)
        return session.exec(statement).first()


def get_user_by_id(user_id: UUID) -> Optional[User]:
    """Lookup a user by ID."""
    with Session(engine) as session:
        return session.get(User, user_id)


def list_users(*, include_inactive: bool = True) -> list[User]:
    """Return all users, optionally filtering out inactive ones."""
    with Session(engine) as session:
        statement = select(User).order_by(User.created_at.asc())
        if not include_inactive:
            statement = statement.where(User.is_active.is_(True))
        return list(session.exec(statement))


def deactivate_user(user: User) -> User:
    """Mark a user as inactive."""
    user.is_active = False
    with Session(engine) as session:
        return _persist(session, user)


def update_password(user: User, hashed_password: str) -> User:
    """Update a user's password hash."""
    user.hashed_password = hashed_password
    with Session(engine) as session:
        return _persist(session, user)


def save_user(user: User) -> User:
    """Generic save helper."""
    with Session(engine) as session:
        return _persist(session, user)
