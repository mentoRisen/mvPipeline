"""Transcript rows for AI draft preview (prompt engineering visibility)."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlmodel import SQLModel, Field, Column, JSON

from app.models.ai_draft_session import UuidChar32


class AiDraftCommunicationKind(str, Enum):
    """Kind of persisted AI draft transcript row."""

    USER_INPUT = "user_input"
    PROMPT_TO_AI = "prompt_to_ai"
    RESPONSE_FROM_AI = "response_from_ai"
    ERROR = "error"


class AiDraftCommunicationEvent(SQLModel, table=True):
    """One ordered step in the AI preview transcript for a draft session."""

    __tablename__ = "ai_draft_communication_events"
    __table_args__ = (
        UniqueConstraint(
            "draft_session_id",
            "sequence",
            name="uq_ai_draft_comm_events_session_seq",
        ),
    )

    id: Optional[int] = Field(default=None, primary_key=True)

    draft_session_id: UUID = Field(
        sa_column=Column(
            UuidChar32,
            ForeignKey("ai_draft_sessions.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
    )

    sequence: int = Field(ge=0, description="Monotonic per draft_session_id")

    kind: str = Field(sa_column=Column(String(32), nullable=False))

    payload: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))

    created_at: datetime = Field(default_factory=datetime.utcnow)
