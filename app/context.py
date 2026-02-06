"""Application-wide execution context (currently focused on tenant).

This module provides a simple context mechanism that can hold the
*current tenant* for the lifetime of a request, background job, or script.

It is designed to feel like a "singleton", but is implemented using
`contextvars` so it is safe for concurrent execution.

Public API:
    - init_context_by_tenant(tenant_id): load tenant and set it as current.
    - get_tenant(): return the current tenant or raise if not set.
"""

from __future__ import annotations

from contextvars import ContextVar
import os
from typing import Optional, Union
from uuid import UUID

from app.models.tenant import Tenant
from app.services.tenant_repo import get_tenant_by_id

_tenant_var: ContextVar[Optional[Tenant]] = ContextVar("current_tenant", default=None)


def _normalize_tenant_id(tenant_id: Union[str, UUID]) -> UUID:
    if isinstance(tenant_id, UUID):
        return tenant_id
    return UUID(str(tenant_id))


def init_context_by_tenant(tenant_id: Union[str, UUID]) -> Tenant:
    """Initialize the context for the given tenant id.

    Loads the tenant from the database and stores the full Tenant entity
    in a context-local variable.

    Raises:
        ValueError: if no tenant with the given id exists.
    """
    tenant_uuid = _normalize_tenant_id(tenant_id)
    tenant = get_tenant_by_id(tenant_uuid)
    if not tenant:
        raise ValueError(f"Tenant with id {tenant_uuid} not found")

    # Set tenant into context.
    _tenant_var.set(tenant)

    # Apply tenant-specific environment overrides, if any.
    # Example tenant.env:
    # {
    #   "DISCORD_WEBHOOK_URL": "https://discord.com/api/webhooks/...",
    #   "OTHER_KEY": "value"
    # }
    if tenant.env:
        for key, value in tenant.env.items():
            # Convert all values to strings for environment variables.
            os.environ[str(key)] = "" if value is None else str(value)

    return tenant


def get_tenant() -> Tenant:
    """Return the current tenant from context.

    Raises:
        RuntimeError: if the tenant has not been initialized in this context.
    """
    tenant = _tenant_var.get()
    if tenant is None:
        raise RuntimeError(
            "Tenant context is not initialized. "
            "Call init_context_by_tenant(...) before using get_tenant()."
        )
    return tenant

