"""Job model and related enums.

Represents generic AI jobs that belong to tasks in the pipeline.
"""

from enum import Enum
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlmodel import SQLModel, Field, Column, JSON
from sqlalchemy import String


class JobStatus(str, Enum):
    """Job status enumeration for generic AI jobs."""
    NEW = "new"  # Job created, not yet ready for processing
    READY = "ready"  # Job ready for processing
    PROCESSING = "processing"  # Job currently being processed
    PROCESSED = "processed"  # Job processing completed
    ERROR = "error"  # Job failed with an error


class Job(SQLModel, table=True):
    """Job model representing a generic AI job.
    
    Represents individual AI generation jobs that belong to a parent task.
    Tracks the lifecycle of executing an AI job from creation through processing to completion.
    """
    
    __tablename__ = "jobs"
    
    # Primary key
    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
        description="Unique identifier for the job"
    )
    
    # Foreign key to parent task
    task_id: UUID = Field(
        foreign_key="tasks.id",
        description="Parent task ID"
    )
    
    # Status tracking
    status: JobStatus = Field(
        default=JobStatus.NEW,
        sa_column=Column(String(50)),
        description="Current status of the job (stored as string in database)"
    )
    
    # Generator information
    generator: str = Field(
        description="Generator to use (e.g., 'openai', 'pillow', etc.)"
    )
    
    # Purpose - how the result should be used
    purpose: Optional[str] = Field(
        default=None,
        sa_column=Column(String(255)),
        description="Purpose/reason for how the job result should be used"
    )
    
    # Prompt data (JSON)
    prompt: Optional[dict] = Field(
        default=None,
        sa_column=Column(JSON),
        description="JSON with all data needed to run the prompt"
    )
    
    # Result data (JSON)
    result: Optional[dict] = Field(
        default=None,
        sa_column=Column(JSON),
        description="JSON with the job result"
    )
    
    # Timestamps
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Job creation timestamp"
    )
    
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Last update timestamp"
    )
