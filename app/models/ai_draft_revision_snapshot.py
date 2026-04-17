"""Undo snapshots for AI draft session revisions."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import ForeignKey
from sqlmodel import SQLModel, Field, Column, JSON

from app.models.ai_draft_session import UuidChar32


class AiDraftRevisionSnapshot(SQLModel, table=True):
    """Restorable bundle snapshot captured before successful iteration replace."""

    __tablename__ = "ai_draft_revision_snapshots"
    id: Optional[int] = Field(default=None, primary_key=True)

    draft_session_id: UUID = Field(
        sa_column=Column(
            UuidChar32,
            ForeignKey("ai_draft_sessions.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
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
    bundle: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow)
