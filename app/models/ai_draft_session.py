"""Persisted AI task draft session (Slice 3).

Holds in-progress bundle state per tenant and user until confirm, discard, or expiry.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

from sqlalchemy import String, Text
from sqlmodel import SQLModel, Field, Column, JSON


class AiDraftSessionStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    DISCARDED = "discarded"


class AiDraftSession(SQLModel, table=True):
    """Server-side draft container for AI task bundle review."""

    __tablename__ = "ai_draft_sessions"

    id: UUID = Field(default_factory=uuid4, primary_key=True)

    tenant_id: UUID = Field(foreign_key="tenants.id", index=True)
    user_id: UUID = Field(foreign_key="users.id", index=True)

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
