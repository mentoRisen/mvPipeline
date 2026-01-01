"""Task model and related enums.

Represents one Instagram post job in the quote-image pipeline.
"""

from enum import Enum
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlmodel import SQLModel, Field, Column, JSON


class TaskStatus(str, Enum):
    """Task status enumeration for Instagram post pipeline.
    
    Status transitions:
        PENDING -> PROCESSING (when pipeline starts)
        PROCESSING -> QUOTE_READY (when quote is generated)
        QUOTE_READY -> IMAGE_READY (when image is generated)
        IMAGE_READY -> COMPLETED (when post is ready)
        Any -> FAILED (on error)
        FAILED -> PENDING (retry)
    """
    PENDING = "pending"
    PROCESSING = "processing"
    QUOTE_READY = "quote_ready"
    IMAGE_READY = "image_ready"
    COMPLETED = "completed"
    FAILED = "failed"


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
    
    # Status tracking
    status: TaskStatus = Field(
        default=TaskStatus.PENDING,
        description="Current status of the task"
    )
    
    # Content fields
    quote_text: Optional[str] = Field(
        default=None,
        description="Generated quote text"
    )
    
    caption_text: Optional[str] = Field(
        default=None,
        description="Optional Instagram caption text"
    )
    
    image_path: Optional[str] = Field(
        default=None,
        description="Path to generated image file"
    )
    
    image_generator: Optional[str] = Field(
        default=None,
        description="Image generator to use (e.g., 'pillow', empty defaults to pillow)"
    )
    
    # Scheduling
    scheduled_for: Optional[datetime] = Field(
        default=None,
        description="Optional scheduled publication time"
    )
    
    # Error tracking
    attempt_count: int = Field(
        default=0,
        description="Number of processing attempts"
    )
    
    last_error: Optional[str] = Field(
        default=None,
        description="Last error message if task failed"
    )
    
    # Metadata
    meta: Optional[dict] = Field(
        default=None,
        sa_column=Column(JSON),
        description="Additional metadata as JSON"
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
        self.last_error = error
        self.attempt_count += 1
        self.updated_at = datetime.utcnow()
    
    def mark_quote_ready(self, quote_text: str) -> None:
        """Mark task as having quote ready.
        
        Args:
            quote_text: The generated quote text
        """
        self.status = TaskStatus.QUOTE_READY
        self.quote_text = quote_text
        self.updated_at = datetime.utcnow()
    
    def mark_image_ready(self, image_path: str) -> None:
        """Mark task as having image ready.
        
        Args:
            image_path: Path to the generated image file
        """
        self.status = TaskStatus.IMAGE_READY
        self.image_path = image_path
        self.updated_at = datetime.utcnow()
    
    def mark_completed(self) -> None:
        """Mark task as completed."""
        self.status = TaskStatus.COMPLETED
        self.updated_at = datetime.utcnow()
    
    def start_processing(self) -> None:
        """Mark task as being processed."""
        self.status = TaskStatus.PROCESSING
        self.attempt_count += 1
        self.updated_at = datetime.utcnow()

