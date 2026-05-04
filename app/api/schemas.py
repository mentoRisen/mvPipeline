"""Pydantic schemas for API requests and responses."""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict, field_validator

from app.models.task import TaskStatus
from app.models.job import JobStatus
from app.models.prompt import PromptType


# --- Tenant schemas ---


class TenantCreate(BaseModel):
    """Schema for creating a tenant."""
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


class AiTaskDraftRequest(BaseModel):
    """Schema for requesting an AI-generated draft preview."""

    model_config = ConfigDict(extra="forbid")

    brief: str = Field(
        ...,
        min_length=1,
        max_length=4000,
        description="Natural-language brief for generating one or more draft tasks",
    )
    draft_session_id: Optional[UUID] = Field(
        default=None,
        description="When set, replace this active draft session after a successful preview",
    )
    iteration_mode: Optional[str] = Field(
        default=None,
        description="Follow-up instruction mode: regenerate or targeted_intent",
    )
    instruction_text: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=4000,
        description="Additional instruction used for follow-up preview iterations",
    )
    target_scope: Optional[str] = Field(
        default=None,
        description="Target granularity for follow-up instructions; v1 supports campaign",
    )


class AiDraftIterationMode(str, Enum):
    REGENERATE = "regenerate"
    TARGETED_INTENT = "targeted_intent"


class AiDraftTask(BaseModel):
    """Structured draft task returned by the AI preview flow."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=255)
    template: str = Field(..., description="Template identifier for the draft task")
    meta: dict = Field(default_factory=dict)
    post: dict = Field(default_factory=dict)


class AiDraftJob(BaseModel):
    """Structured draft job returned by the AI preview flow."""

    model_config = ConfigDict(extra="forbid")

    generator: str = Field(..., min_length=1, max_length=255)
    purpose: Optional[str] = Field(default=None, max_length=255)
    prompt: dict = Field(default_factory=dict)
    order: int = Field(default=0, ge=0)


class AiTaskDraftItem(BaseModel):
    """One draft task plus jobs inside an AI draft bundle (preview or confirm)."""

    model_config = ConfigDict(extra="forbid")

    task: AiDraftTask
    jobs: list[AiDraftJob] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class AiDraftCommunicationEventResponse(BaseModel):
    """One persisted AI transcript row for prompt-engineering visibility."""

    model_config = ConfigDict(extra="forbid")

    sequence: int
    kind: str
    payload: dict
    created_at: datetime


class AiTaskDraftBundleResponse(BaseModel):
    """Preview payload: ordered list of draft tasks, each with jobs."""

    model_config = ConfigDict(extra="forbid")

    items: list[AiTaskDraftItem] = Field(
        default_factory=list,
        description="Draft tasks in creation order; empty while async preview is running",
    )
    draft_session_id: Optional[UUID] = Field(
        default=None,
        description="Set by the API after persisting the preview; omitted in internal service-only previews",
    )
    preview_status: str = Field(
        default="succeeded",
        description="Async preview: running until complete, then succeeded or failed",
    )
    last_error: Optional[dict] = Field(
        default=None,
        description="When preview_status is failed (blocking mode), structured error if available",
    )
    communication_events: list[AiDraftCommunicationEventResponse] = Field(
        default_factory=list,
        description="Transcript rows when returned from blocking preview completion",
    )


class AiTaskDraftBundleConfirmRequest(BaseModel):
    """Reviewed bundle for atomic multi-task creation."""

    model_config = ConfigDict(extra="forbid")

    items: list[AiTaskDraftItem] = Field(..., min_length=1)
    draft_session_id: Optional[UUID] = Field(
        default=None,
        description="When set, complete this session on success or record errors on failure",
    )


class AiTaskDraftConfirmBundleResponse(BaseModel):
    """Result of confirming an AI draft bundle (all tasks created or none)."""

    tasks: list[TaskResponse]


class AiTaskDraftValidationErrorBody(BaseModel):
    """Machine-readable validation error for AI draft preview/confirm."""

    error: str = "ai_draft_validation"
    message: str
    item_index: Optional[int] = None
    field: Optional[str] = None


class AiDraftSessionSummaryResponse(BaseModel):
    """List entry for resumable AI draft sessions."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    brief: str
    item_count: int
    updated_at: datetime
    preview_status: str = Field(
        default="succeeded",
        description="Async AI preview lifecycle for this session",
    )


class AiDraftSessionDetailResponse(BaseModel):
    """Full draft session for resume in the AI create flow."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    brief: str
    items: list[AiTaskDraftItem] = Field(
        default_factory=list,
        description="Empty while preview is running or failed without bundle",
    )
    last_error: Optional[dict] = None
    updated_at: datetime
    preview_status: str = "succeeded"
    communication_events: list[AiDraftCommunicationEventResponse] = Field(
        default_factory=list,
    )
    undo_snapshots: list["AiDraftRevisionSnapshotResponse"] = Field(
        default_factory=list,
    )


class AiDraftSessionPatchRequest(BaseModel):
    """Autosave edits for a draft session bundle."""

    model_config = ConfigDict(extra="forbid")

    brief: Optional[str] = Field(default=None, max_length=4000)
    items: Optional[list[AiTaskDraftItem]] = None


class AiDraftRevisionSnapshotResponse(BaseModel):
    """One restorable prior bundle snapshot for undo support."""

    model_config = ConfigDict(extra="forbid")

    id: int
    created_at: datetime


class AiDraftSessionRestoreRequest(BaseModel):
    """Restore bundle from a recent undo snapshot."""

    model_config = ConfigDict(extra="forbid")

    snapshot_id: int


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


# --- ScheduleRule schemas ---


class ScheduleRuleCreate(BaseModel):
    """Schema for creating a schedule rule."""

    action: str = Field(..., description="Action to perform (e.g. publish, remind)")
    note: Optional[str] = Field(default=None, description="Optional note / description")
    times: Optional[dict] = Field(
        default=None,
        description="JSON config, e.g. {'hour': 9, 'days': [1, 2, 3]} (cron-style DOW)",
    )


class ScheduleRuleUpdate(BaseModel):
    """Schema for updating a schedule rule."""
    action: Optional[str] = None
    note: Optional[str] = None
    times: Optional[dict] = None


class ScheduleRuleResponse(BaseModel):
    """Schema for schedule rule response."""
    id: UUID
    tenant_id: UUID
    action: str
    note: Optional[str] = None
    times: Optional[dict] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# --- Prompt schemas ---


class PromptCreate(BaseModel):
    """Create a tenant prompt row."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., max_length=200)
    type: PromptType = Field(..., description="Prompt category (e.g. task-creation)")
    body: str = Field(..., min_length=1, description="Full prompt text")

    @field_validator("name")
    @classmethod
    def name_non_empty(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("name must not be empty")
        return s


class PromptUpdate(BaseModel):
    """Partial update for a prompt."""

    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(default=None, max_length=200)
    type: Optional[PromptType] = None
    body: Optional[str] = Field(default=None, min_length=1)

    @field_validator("name")
    @classmethod
    def name_if_set(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        s = v.strip()
        if not s:
            raise ValueError("name must not be empty")
        return s


class PromptSummaryResponse(BaseModel):
    """List row: metadata plus truncated body for scanning."""

    id: UUID
    name: str
    type: PromptType
    body_preview: str = Field(description="Truncated body (~120 chars) for list UIs")
    created_at: datetime
    updated_at: datetime


class PromptResponse(BaseModel):
    """Full prompt for detail/edit responses."""

    id: UUID
    tenant_id: UUID
    name: str
    type: PromptType
    body: str
    created_at: datetime
    updated_at: datetime
