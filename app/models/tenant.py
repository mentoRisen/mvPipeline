"""Tenant model.

Represents a project that encapsulates tasks. Each tenant can have its own
configuration (e.g. Instagram credentials in env) for multi-account support.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlmodel import SQLModel, Field, Column, JSON


class Tenant(SQLModel, table=True):
    """Tenant model representing a project with its own tasks and configuration.
    
    Encapsulates all tasks for a specific project (e.g. one Instagram account).
    The env JSON field holds tenant-specific config such as INSTAGRAM_ACCESS_TOKEN,
    INSTAGRAM_ACCOUNT_ID, PUBLIC_URL, etc.
    """
    
    __tablename__ = "tenants"
    
    # Primary key
    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
        description="Unique identifier for the tenant"
    )
    
    # Human-readable identifier (e.g. "acme-instagram", "brand-x")
    tenant_id: str = Field(
        unique=True,
        index=True,
        description="Unique tenant identifier (slug)"
    )
    
    name: str = Field(
        description="Display name for the tenant"
    )
    
    description: Optional[str] = Field(
        default=None,
        description="Optional description of the tenant/project"
    )
    
    # Social / display
    instagram_account: Optional[str] = Field(
        default=None,
        description="Instagram account name or handle"
    )
    facebook_page: Optional[str] = Field(
        default=None,
        description="Facebook page URL or identifier (for clickable link)"
    )
    is_active: bool = Field(
        default=True,
        description="Whether the tenant is active"
    )
    
    # Tenant-specific environment/config (e.g. Instagram creds, PUBLIC_URL)
    env: Optional[dict] = Field(
        default=None,
        sa_column=Column(JSON),
        description="JSON config: INSTAGRAM_ACCESS_TOKEN, INSTAGRAM_ACCOUNT_ID, PUBLIC_URL, etc."
    )
    
    # Timestamps
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Tenant creation timestamp"
    )
    
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Last update timestamp"
    )
