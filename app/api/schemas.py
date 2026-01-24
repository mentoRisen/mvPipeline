"""Pydantic schemas for API requests and responses."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.task import TaskStatus
from app.models.job import JobStatus


class TaskCreate(BaseModel):
    """Schema for creating a new task."""
    name: str = Field(..., description="Task name/identifier")
    template: str = Field(..., description="Template identifier or name")
    quote_text: Optional[str] = None
    caption_text: Optional[str] = None
    image_generator: Optional[str] = None
    meta: Optional[dict] = None


class TaskUpdate(BaseModel):
    """Schema for updating a task."""
    name: Optional[str] = None
    scheduled_for: Optional[datetime] = None
    meta: Optional[dict] = None
    post: Optional[dict] = None


class JobResponse(BaseModel):
    """Schema for job response."""
    id: UUID
    task_id: UUID
    status: JobStatus
    generator: str
    purpose: Optional[str] = None
    prompt: Optional[dict] = None
    result: Optional[dict] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class JobCreate(BaseModel):
    """Schema for creating a new job."""
    generator: str = Field(..., description="Generator to use (e.g., 'dalle', 'gptimage15')")
    purpose: Optional[str] = Field(None, description="Purpose/reason for how the job result should be used")
    prompt: Optional[dict] = Field(None, description="JSON with all data needed to run the prompt")


class JobUpdate(BaseModel):
    """Schema for updating a job."""
    generator: Optional[str] = Field(None, description="Generator to use (e.g., 'dalle', 'gptimage15')")
    purpose: Optional[str] = Field(None, description="Purpose/reason for how the job result should be used")
    prompt: Optional[dict] = Field(None, description="JSON with all data needed to run the prompt")
    status: Optional[JobStatus] = Field(None, description="Job status")
    result: Optional[dict] = Field(None, description="JSON with the job result (e.g., image paths, errors)")


class TaskResponse(BaseModel):
    """Schema for task response."""
    id: UUID
    status: TaskStatus
    name: Optional[str] = None
    template: Optional[str] = None
    quote_text: Optional[str] = None
    caption_text: Optional[str] = None
    image_path: Optional[str] = None
    image_generator: Optional[str] = None
    image_generator_prompt: Optional[str] = None
    scheduled_for: Optional[datetime] = None
    last_error: Optional[str] = None
    meta: Optional[dict] = None
    post: Optional[dict] = None
    jobs: Optional[list[JobResponse]] = None
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
