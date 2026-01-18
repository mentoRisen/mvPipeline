"""Pydantic schemas for API requests and responses."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.task import TaskStatus


class TaskCreate(BaseModel):
    """Schema for creating a new task."""
    quote_text: Optional[str] = None
    caption_text: Optional[str] = None
    image_generator: Optional[str] = None
    meta: Optional[dict] = None


class TaskUpdate(BaseModel):
    """Schema for updating a task."""
    quote_text: Optional[str] = None
    caption_text: Optional[str] = None
    image_generator: Optional[str] = None
    image_generator_prompt: Optional[str] = None
    scheduled_for: Optional[datetime] = None
    meta: Optional[dict] = None


class TaskResponse(BaseModel):
    """Schema for task response."""
    id: UUID
    status: TaskStatus
    quote_text: Optional[str] = None
    caption_text: Optional[str] = None
    image_path: Optional[str] = None
    image_generator: Optional[str] = None
    image_generator_prompt: Optional[str] = None
    scheduled_for: Optional[datetime] = None
    attempt_count: int
    last_error: Optional[str] = None
    meta: Optional[dict] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TaskListResponse(BaseModel):
    """Schema for paginated task list response."""
    tasks: list[TaskResponse]
    total: int
    limit: int
    offset: int


class ApprovalAction(BaseModel):
    """Schema for approval actions."""
    task_id: UUID = Field(..., description="ID of the task to approve")
