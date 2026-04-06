"""Persisted AI task draft session (Slice 3).

Holds in-progress bundle state per tenant and user until confirm, discard, or expiry.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, String, Text, TypeDecorator
from sqlalchemy.dialects import mysql
from sqlmodel import SQLModel, Field, Column, JSON


class UuidChar32(TypeDecorator):
    """Store ``uuid.UUID`` as 32-char lowercase hex (no hyphens).

    Live MySQL uses ``CHAR(32)`` for ``tenants.id``, ``users.id``, and task PKs, with
    ``utf8mb3`` / ``utf8mb3_bin`` (legacy schema). The schema default may be
    ``utf8mb4``; without explicit charset/collation, new columns won't match referenced
    PKs and MySQL 8 reports error 3780.

    On non-MySQL dialects (e.g. SQLite tests), use ``String(32)``.
    """

    impl = String(32)
    cache_ok = True

    def load_dialect_impl(self, dialect: Any) -> Any:
        if dialect.name == "mysql":
            return dialect.type_descriptor(
                mysql.CHAR(32, charset="utf8mb3", collation="utf8mb3_bin")
            )
        return dialect.type_descriptor(String(32))

    def process_bind_param(self, value: Any, dialect: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, UUID):
            return value.hex
        s = str(value).strip()
        if len(s) == 36 and s.count("-") == 4:
            return UUID(s).hex
        if len(s) == 32:
            return s.lower()
        return UUID(s).hex

    def process_result_value(self, value: Any, dialect: Any) -> UUID | None:
        if value is None:
            return None
        if isinstance(value, UUID):
            return value
        s = str(value)
        if len(s) == 32:
            return UUID(hex=s)
        return UUID(s)


class AiDraftSessionStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    DISCARDED = "discarded"


class AiDraftSession(SQLModel, table=True):
    """Server-side draft container for AI task bundle review."""

    __tablename__ = "ai_draft_sessions"

    # UuidChar32 → CHAR(32) on MySQL to match existing tenant/user PK DDL (see class docstring).
    id: UUID = Field(
        default_factory=uuid4,
        sa_column=Column(UuidChar32, primary_key=True),
    )

    tenant_id: UUID = Field(
        sa_column=Column(
            UuidChar32,
            ForeignKey("tenants.id"),
            nullable=False,
            index=True,
        ),
    )
    user_id: UUID = Field(
        sa_column=Column(
            UuidChar32,
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
