"""Persisted AI task draft session (Slice 3).

Holds in-progress bundle state per tenant and user until confirm, discard, or expiry.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, String, Text, TypeDecorator
from sqlmodel import SQLModel, Field, Column, JSON


class UUIDString36(TypeDecorator):
    """Store ``uuid.UUID`` as 36-char string for MySQL FK compatibility and SQLite tests."""

    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, UUID):
            return str(value)
        return str(value)

    def process_result_value(self, value: Any, dialect: Any) -> UUID | None:
        if value is None:
            return None
        if isinstance(value, UUID):
            return value
        return UUID(str(value))


class AiDraftSessionStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    DISCARDED = "discarded"


class AiDraftSession(SQLModel, table=True):
    """Server-side draft container for AI task bundle review."""

    __tablename__ = "ai_draft_sessions"

    # Use String(36) in MySQL so FK columns match `tenants.id` / `users.id` (UUID text with hyphens).
    # The default SQLAlchemy UUID render for MySQL can be CHAR(32), which triggers error 3780
    # ("incompatible" FK) against existing tables.
    id: UUID = Field(
        default_factory=uuid4,
        sa_column=Column(UUIDString36, primary_key=True),
    )

    tenant_id: UUID = Field(
        sa_column=Column(
            UUIDString36,
            ForeignKey("tenants.id"),
            nullable=False,
            index=True,
        ),
    )
    user_id: UUID = Field(
        sa_column=Column(
            UUIDString36,
            ForeignKey("users.id"),
            nullable=False,
            index=True,
        ),
    )

    brief: str = Field(sa_column=Column(Text))

    bundle: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON),
        description="Serialized bundle payload: items list matching confirm shape",
    )

    last_error: Optional[dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
        description="Structured error from last failed confirm or validation",
    )

    status: AiDraftSessionStatus = Field(
        default=AiDraftSessionStatus.ACTIVE,
        sa_column=Column(String(32)),
    )

    expires_at: datetime = Field(description="Session is not resumable after this time")

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
