"""Task model and related enums.

Represents one Instagram post job in the quote-image pipeline.
"""

from enum import Enum
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlmodel import SQLModel, Field, Column, JSON
from sqlalchemy import String


class TaskStatus(str, Enum):
    """Task status enumeration for Instagram post pipeline.
    
    Status transitions (with manual approvals):
        DRAFT -> PENDING_APPROVAL (when AI creates task and user submits)
        PENDING_APPROVAL -> PROCESSING (when user approves for processing)
        PENDING_APPROVAL -> DISAPPROVED (when user disapproves processing)
        PROCESSING -> PENDING_CONFIRMATION (when quote and image generation complete)
        PENDING_CONFIRMATION -> READY (when user confirms/approves the content)
        PENDING_CONFIRMATION -> REJECTED (when user rejects publication)
        READY -> PUBLISHING (when publishing starts)
        PUBLISHING -> PUBLISHED (when publishing completes successfully)
        PUBLISHING -> READY (when publishing fails, can retry)
        Any -> FAILED (on error)
        FAILED -> PENDING_APPROVAL (retry)
    """
    DRAFT = "draft"  # AI created, not yet submitted for approval
    PENDING_APPROVAL = "pending_approval"  # Waiting for user to approve processing
    DISAPPROVED = "disapproved"  # User disapproved processing
    PROCESSING = "processing"  # User approved, processing started
    PENDING_CONFIRMATION = "pending_confirmation"  # Waiting for user to confirm content after generation
    REJECTED = "rejected"  # User rejected publication
    READY = "ready"  # User confirmed content, ready for publication
    PUBLISHING = "publishing"  # Currently being published
    PUBLISHED = "published"  # User confirmed, post published (completed)
    FAILED = "failed"  # Error state


class Task(SQLModel, table=True):
    """Task model representing one Instagram post job.
    
    Tracks the lifecycle of generating a quote image post from creation
    through quote generation, image generation, to completion.
    """
    
    __tablename__ = "tasks"
    
    # Primary key
    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
        description="Unique identifier for the task"
    )
    
    # Tenant association (optional for backwards compatibility)
    tenant_id: Optional[UUID] = Field(
        default=None,
        foreign_key="tenants.id",
        index=True,
        description="Tenant this task belongs to"
    )
    
    # Status tracking
    status: TaskStatus = Field(
        default=TaskStatus.DRAFT,
        sa_column=Column(String(50)),
        description="Current status of the task (stored as string in database)"
    )
    
    # Name
    name: Optional[str] = Field(
        default=None,
        description="Task name/identifier"
    )
    
    # Scheduling
    scheduled_for: Optional[datetime] = Field(
        default=None,
        description="Optional scheduled publication time"
    )
    
    # Metadata
    meta: Optional[dict] = Field(
        default=None,
        sa_column=Column(JSON),
        description="Additional metadata as JSON"
    )
    
    # Content fields
    template: Optional[str] = Field(
        default=None,
        description="Template identifier or name"
    )
    
    post: Optional[dict] = Field(
        default=None,
        sa_column=Column(JSON),
        description="Post content as JSON"
    )
    
    # Publish result (e.g. Instagram API responses)
    result: Optional[dict] = Field(
        default=None,
        sa_column=Column(JSON),
        description="Publish result with logs array of full API responses"
    )
    
    # Timestamps
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Task creation timestamp"
    )
    
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Last update timestamp"
    )
    
    def mark_failed(self, error: str) -> None:
        """Mark task as failed with error message.
        
        Args:
            error: Error message describing the failure
        """
        self.status = TaskStatus.FAILED
        self.updated_at = datetime.utcnow()
    
    def mark_quote_ready(self, quote_text: str) -> None:
        """Mark task as having quote ready.
        
        Note: Status remains PROCESSING until image is also generated.
        
        Args:
            quote_text: The generated quote text
        """
        self.updated_at = datetime.utcnow()
    
    def mark_image_ready(self, image_path: str) -> None:
        """Mark task as having image ready (quote and image both complete).
        
        Moves task from PROCESSING to PENDING_CONFIRMATION, waiting for user approval.
        
        Args:
            image_path: Path to the generated image file
        """
        self.status = TaskStatus.PENDING_CONFIRMATION
        self.updated_at = datetime.utcnow()
    
    def mark_completed(self) -> None:
        """Mark task as completed (DEPRECATED - use mark_published)."""
        self.status = TaskStatus.PUBLISHED
        self.updated_at = datetime.utcnow()
    
    def mark_published(self) -> None:
        """Mark task as published (user action).
        
        Moves task from READY, PUBLISHING, or FAILED to PUBLISHED.
        """
        if self.status not in (TaskStatus.READY, TaskStatus.PUBLISHING, TaskStatus.FAILED):
            raise ValueError(f"Cannot publish task in status {self.status.value}")
        self.status = TaskStatus.PUBLISHED
        self.updated_at = datetime.utcnow()
    
    def approve_for_processing(self) -> None:
        """Approve task for processing (user action)."""
        if self.status != TaskStatus.PENDING_APPROVAL:
            raise ValueError(f"Cannot approve task in status {self.status.value}")
        self.status = TaskStatus.PROCESSING
        self.updated_at = datetime.utcnow()
    
    def disapprove_task(self) -> None:
        """Disapprove task from processing (user action)."""
        if self.status != TaskStatus.PENDING_APPROVAL:
            raise ValueError(f"Cannot disapprove task in status {self.status.value}")
        self.status = TaskStatus.DISAPPROVED
        self.updated_at = datetime.utcnow()
    
    def approve_for_publication(self) -> None:
        """Approve task content for publication (user action).
        
        Moves task from PENDING_CONFIRMATION to READY.
        """
        if self.status != TaskStatus.PENDING_CONFIRMATION:
            raise ValueError(f"Cannot approve publication in status {self.status.value}")
        self.status = TaskStatus.READY
        self.updated_at = datetime.utcnow()
    
    def reject_task(self) -> None:
        """Reject task from publication (user action)."""
        if self.status != TaskStatus.PENDING_CONFIRMATION:
            raise ValueError(f"Cannot reject task in status {self.status.value}")
        self.status = TaskStatus.REJECTED
        self.updated_at = datetime.utcnow()
    
    def submit_for_approval(self) -> None:
        """Submit draft task for approval (move from DRAFT to PENDING_APPROVAL)."""
        if self.status != TaskStatus.DRAFT:
            raise ValueError(f"Cannot submit task in status {self.status.value}")
        self.status = TaskStatus.PENDING_APPROVAL
        self.updated_at = datetime.utcnow()
    
    def start_processing(self) -> None:
        """Mark task as being processed (internal use - use approve_for_processing for user actions)."""
        self.status = TaskStatus.PROCESSING
        self.updated_at = datetime.utcnow()
    
    def request_confirmation(self) -> None:
        """Request user confirmation before publication (DEPRECATED - not used in current flow).
        
        This method is kept for backwards compatibility but is not part of the current
        status flow. The flow is: PROCESSING -> PENDING_CONFIRMATION -> READY -> PUBLISHED.
        """
        if self.status != TaskStatus.READY:
            raise ValueError(f"Cannot request confirmation in status {self.status.value}")
        self.status = TaskStatus.PENDING_CONFIRMATION
        self.updated_at = datetime.utcnow()

    def override_processing(self) -> None:
        """Override processing and move task to PENDING_CONFIRMATION (user action).
        
        Allows a user to force-finish processing when in PROCESSING state,
        e.g. when generation is stuck but the content is considered ready.
        """
        if self.status != TaskStatus.PROCESSING:
            raise ValueError(f"Cannot override processing in status {self.status.value}")
        self.status = TaskStatus.PENDING_CONFIRMATION
        self.updated_at = datetime.utcnow()

