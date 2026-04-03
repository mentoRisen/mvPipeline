"""Application-wide execution context (currently focused on tenant).

This module provides a simple context mechanism that can hold the
*current tenant* for the lifetime of a request, background job, or script.

It is designed to feel like a "singleton", but is implemented using
`contextvars` so it is safe for concurrent execution.

Public API:
    - init_context_by_tenant(tenant_id, *, apply_env): load tenant and set it as current.
    - get_tenant(): return the current tenant or raise if not set.
    - reset_tenant_context(): clear tenant context and undo env overrides from the last init.
"""

from __future__ import annotations

from contextvars import ContextVar
import os
from typing import Optional, Union
from uuid import UUID

from app.models.tenant import Tenant
from app.services.tenant_repo import get_tenant_by_id

_tenant_var: ContextVar[Optional[Tenant]] = ContextVar("current_tenant", default=None)
# Stack of (env_key, had_key, previous_value_or_dummy) for restoring os.environ after request scope.
_env_undo_var: ContextVar[Optional[list[tuple[str, bool, str]]]] = ContextVar(
    "tenant_env_undo", default=None
)


def _normalize_tenant_id(tenant_id: Union[str, UUID]) -> UUID:
    if isinstance(tenant_id, UUID):
        return tenant_id
    return UUID(str(tenant_id))


def reset_tenant_context() -> None:
    """Clear current tenant and restore ``os.environ`` from before ``init_context_by_tenant``."""
    undo = _env_undo_var.get()
    if undo:
        for key, had_key, prev in reversed(undo):
            if had_key:
                os.environ[key] = prev
            else:
                os.environ.pop(key, None)
        _env_undo_var.set(None)
    _tenant_var.set(None)


def init_context_by_tenant(
    tenant_id: Union[str, UUID],
    *,
    apply_env: bool = True,
) -> Tenant:
    """Initialize the context for the given tenant id.

    Loads the tenant from the database and stores the full Tenant entity
    in a context-local variable.

    Each call resets any previous context in this execution scope first so API
    dependencies can re-enter cleanly. Worker startup uses a single init per
    process.

    Raises:
        ValueError: if no tenant with the given id exists.
    """
    reset_tenant_context()
    tenant_uuid = _normalize_tenant_id(tenant_id)
    tenant = get_tenant_by_id(tenant_uuid)
    if not tenant:
        raise ValueError(f"Tenant with id {tenant_uuid} not found")

    _tenant_var.set(tenant)

    undo: list[tuple[str, bool, str]] = []
    if apply_env and tenant.env:
        for key, value in tenant.env.items():
            k = str(key)
            had_key = k in os.environ
            prev = os.environ[k] if had_key else ""
            undo.append((k, had_key, prev))
            os.environ[k] = "" if value is None else str(value)
    if undo:
        _env_undo_var.set(undo)

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
