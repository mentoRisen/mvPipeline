"""Pydantic schemas for API requests and responses."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.task import TaskStatus
from app.models.job import JobStatus


# --- Tenant schemas ---


class TenantCreate(BaseModel):
    """Schema for creating a tenant."""
    tenant_id: str = Field(..., description="Unique tenant identifier (slug)")
    name: str = Field(..., description="Display name for the tenant")
    description: Optional[str] = None
    instagram_account: Optional[str] = None
    facebook_page: Optional[str] = None
    is_active: Optional[bool] = True
    env: Optional[dict] = None


class TenantUpdate(BaseModel):
    """Schema for updating a tenant."""
    name: Optional[str] = None
    description: Optional[str] = None
    instagram_account: Optional[str] = None
    facebook_page: Optional[str] = None
    is_active: Optional[bool] = None
    env: Optional[dict] = None


class TenantResponse(BaseModel):
    """Schema for tenant response."""
    id: UUID
    tenant_id: str
    name: str
    description: Optional[str] = None
    instagram_account: Optional[str] = None
    facebook_page: Optional[str] = None
    is_active: bool = True
    env: Optional[dict] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# --- Task schemas ---

class TaskCreate(BaseModel):
    """Schema for creating a new task."""
    name: str = Field(..., description="Task name/identifier")
    template: str = Field(..., description="Template identifier or name")
    tenant_id: Optional[UUID] = Field(None, description="Tenant this task belongs to")
    quote_text: Optional[str] = None
    caption_text: Optional[str] = None
    image_generator: Optional[str] = None
    meta: Optional[dict] = None
    # Optional initial post content (e.g., {"caption": "..."}), used when creating tasks from JSON.
    post: Optional[dict] = None


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
    order: int
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
    order: Optional[int] = Field(0, description="Rendering order for this job (ascending)")


class JobUpdate(BaseModel):
    """Schema for updating a job."""
    generator: Optional[str] = Field(None, description="Generator to use (e.g., 'dalle', 'gptimage15')")
    purpose: Optional[str] = Field(None, description="Purpose/reason for how the job result should be used")
    prompt: Optional[dict] = Field(None, description="JSON with all data needed to run the prompt")
    status: Optional[JobStatus] = Field(None, description="Job status")
    result: Optional[dict] = Field(None, description="JSON with the job result (e.g., image paths, errors)")
    order: Optional[int] = Field(None, description="Rendering order for this job (ascending)")


class TaskResponse(BaseModel):
    """Schema for task response."""
    id: UUID
    status: TaskStatus
    tenant_id: Optional[UUID] = None
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
    result: Optional[dict] = None
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


# --- User & Auth schemas ---


class UserBase(BaseModel):
    """Shared user fields."""

    username: str = Field(..., description="Unique username")
    email: Optional[str] = Field(None, description="Optional email for notifications")


class UserCreate(UserBase):
    """Schema for creating a user."""

    password: str = Field(..., min_length=8, description="Plain-text password")
    is_active: Optional[bool] = True


class UserUpdate(BaseModel):
    """Schema for updating a user."""

    email: Optional[str] = None
    password: Optional[str] = Field(None, min_length=8)
    is_active: Optional[bool] = None


class UserResponse(UserBase):
    """Response schema for user details."""

    id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class LoginRequest(BaseModel):
    """Username + password login payload."""

    username: str
    password: str


class TokenResponse(BaseModel):
    """JWT token response."""

    access_token: str
    token_type: str = "bearer"
    user: UserResponse
