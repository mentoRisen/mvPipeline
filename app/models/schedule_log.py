"""ScheduleLog model.

Stores what has already been done for a given schedule rule and timeslot.
The triple (tenant_id, schedule_rule_id, timeslot) is unique.
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import UniqueConstraint
from sqlmodel import SQLModel, Field, Column, JSON


class ScheduleLogStatus(str, Enum):
    """Status of a schedule log entry."""
    SCHEDULED = "scheduled"  # Scheduled, not yet run
    PROCESSING = "processing"
    NO_TASK = "no_task"  # No task available to run (e.g. no READY task for tenant)
    ERROR = "error"
    DONE = "done"


class ScheduleLog(SQLModel, table=True):
    """Log of a scheduled action execution for a specific timeslot."""

    __tablename__ = "schedule_logs"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "schedule_rule_id",
            "timeslot",
            name="uq_schedule_log_tenant_rule_timeslot",
        ),
    )

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
        description="Unique identifier for the log entry",
    )

    status: ScheduleLogStatus = Field(
        description="Current status: SCHEDULED, PROCESSING, NO_TASK, ERROR, DONE",
    )

    timeslot: str = Field(
        description="String identifying the timeslot (e.g. date or slot key)",
    )

    processed: Optional[datetime] = Field(
        default=None,
        description="When the action was processed (set when done or error)",
    )

    tenant_id: UUID = Field(
        foreign_key="tenants.id",
        description="Tenant this log belongs to",
    )

    schedule_rule_id: UUID = Field(
        foreign_key="schedule_rules.id",
        description="Schedule rule that was executed",
    )

    task_id: Optional[UUID] = Field(
        default=None,
        foreign_key="tasks.id",
        description="Optional task linked to this log (e.g. published task)",
    )

    action: str = Field(
        description="Action that was run (e.g. testlog, publish_instagram)",
    )

    result: Optional[dict] = Field(
        default=None,
        sa_column=Column(JSON),
        description="JSON result or error details",
    )
