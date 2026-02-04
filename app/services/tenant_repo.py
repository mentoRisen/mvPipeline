"""Database operations for tenants."""

from typing import Optional
from uuid import UUID

from sqlmodel import Session, select

from app.models.tenant import Tenant
from app.db.engine import engine
from app.config import DEFAULT_TENANT_ID


def create_tenant(
    name: str,
    description: Optional[str] = None,
    instagram_account: Optional[str] = None,
    facebook_page: Optional[str] = None,
    is_active: bool = True,
    env: Optional[dict] = None,
) -> Tenant:
    """Create a new tenant.
    
    Args:
        name: Display name
        description: Optional description
        instagram_account: Optional Instagram account/handle
        facebook_page: Optional Facebook page URL
        is_active: Whether tenant is active (default True)
        env: Optional JSON config (e.g. Instagram creds)
        
    Returns:
        The created tenant
    """
    tenant = Tenant(
        name=name,
        description=description,
        instagram_account=instagram_account,
        facebook_page=facebook_page,
        is_active=is_active,
        env=env,
    )
    with Session(engine) as session:
        session.add(tenant)
        session.commit()
        session.refresh(tenant)
    return tenant


def get_tenant_by_id(tenant_uuid: UUID) -> Optional[Tenant]:
    """Get a tenant by its UUID."""
    with Session(engine) as session:
        return session.exec(select(Tenant).where(Tenant.id == tenant_uuid)).first()


def list_all_tenants(limit: int = 100, offset: int = 0) -> list[Tenant]:
    """List all tenants with pagination."""
    with Session(engine) as session:
        statement = (
            select(Tenant)
            .order_by(Tenant.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(session.exec(statement).all())


def save_tenant(tenant: Tenant) -> Tenant:
    """Save a tenant to the database."""
    with Session(engine) as session:
        session.add(tenant)
        session.commit()
        session.refresh(tenant)
    return tenant


def delete_tenant(tenant: Tenant) -> None:
    """Delete a tenant. Sets task.tenant_id to NULL for all tasks belonging to this tenant."""
    from app.models.task import Task
    with Session(engine) as session:
        tenant_in_session = session.get(Tenant, tenant.id)
        if not tenant_in_session:
            return
        # Detach tasks from this tenant
        tasks = list(session.exec(select(Task).where(Task.tenant_id == tenant.id)).all())
        for task in tasks:
            task.tenant_id = None
            session.add(task)
        session.delete(tenant_in_session)
        session.commit()


def get_default_tenant() -> Optional[Tenant]:
    """Get the default tenant.

    Preference order:
    1. Tenant whose id matches DEFAULT_TENANT_ID (if set, UUID string)
    2. The first tenant in the database (oldest by created_at)
    """
    with Session(engine) as session:
        tenant: Optional[Tenant] = None

        # Prefer explicit default tenant if configured (UUID)
        if DEFAULT_TENANT_ID:
            try:
                tenant = session.get(Tenant, UUID(DEFAULT_TENANT_ID))
            except (ValueError, TypeError):
                tenant = None

        # Fallback: first tenant by creation time
        if not tenant:
            tenant = session.exec(
                select(Tenant).order_by(Tenant.created_at.asc()).limit(1)
            ).first()

        return tenant
