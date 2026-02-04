"""ScheduleRule model.

Each row defines what action should be done at which times during the week.
Used for scheduling of publishing (e.g. post at Mon 09:00, Wed 14:00).
"""

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlmodel import SQLModel, Field, Column, JSON


class ScheduleRule(SQLModel, table=True):
    """Rule for when to perform an action during the week.

    action: e.g. 'publish', 'remind'
    times: JSON structure, currently:
        {"hour": 9, "days": [1, 2, 3]}
        where hour is 0-23 and days are cron-style day-of-week integers.
    """

    __tablename__ = "schedule_rules"

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
        description="Unique identifier for the rule",
    )

    tenant_id: UUID = Field(
        foreign_key="tenants.id",
        description="Tenant this rule belongs to",
    )

    action: str = Field(
        description="Action to perform (e.g. publish, remind)",
    )

    note: Optional[str] = Field(
        default=None,
        description="Optional note / description of this rule",
    )

    times: Optional[dict] = Field(
        default=None,
        sa_column=Column(JSON),
        description="JSON config, e.g. {'hour': 9, 'days': [1, 2, 3]}",
    )

    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Creation timestamp",
    )

    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Last update timestamp",
    )
