"""Tenant-scoped prompt templates (e.g. task creation instructions)."""

from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import Column, String, Text
from sqlmodel import Field, SQLModel


class PromptType(str, Enum):
    """Prompt category; extend when adding new admin prompt kinds."""

    TASK_CREATION = "task-creation"
    MASTER_PROMPT = "master-prompt"


class Prompt(SQLModel, table=True):
    """Stored prompt text for a tenant and category."""

    __tablename__ = "prompts"
    __table_args__ = {
        "mysql_charset": "utf8mb3",
        "mysql_collate": "utf8mb3_bin",
    }

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: UUID = Field(foreign_key="tenants.id", index=True)
    name: str = Field(sa_column=Column(String(200), nullable=False))
    prompt_type: PromptType = Field(
        sa_column=Column("type", String(50), nullable=False),
        description="Logical prompt category",
    )
    body: str = Field(sa_column=Column(Text, nullable=False))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
