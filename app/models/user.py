"""User model for authentication."""

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlmodel import SQLModel, Field


class User(SQLModel, table=True):
    """Application user with basic authentication credentials."""

    __tablename__ = "users"

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
        description="Unique identifier for the user",
    )
    username: str = Field(
        unique=True,
        index=True,
        description="Unique login name",
    )
    email: Optional[str] = Field(
        default=None,
        description="Optional contact email",
    )
    hashed_password: str = Field(
        description="BCrypt hashed password",
    )
    is_active: bool = Field(
        default=True,
        description="Whether the user account is active",
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Creation timestamp",
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Last update timestamp",
    )
