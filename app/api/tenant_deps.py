"""FastAPI dependency that loads tenant into ``app.context`` from a header."""

from collections.abc import Generator
from typing import Annotated
from uuid import UUID

from fastapi import Header, HTTPException

from app.models.tenant import Tenant
from app.context import init_context_by_tenant, reset_tenant_context


# Sent on every tenant-scoped API request (see frontend api.js).
TENANT_ID_HEADER = "X-Tenant-Id"


def tenant_context_dependency(
    x_tenant_id: Annotated[str, Header(alias=TENANT_ID_HEADER)],
) -> Generator[Tenant, None, None]:
    try:
        tenant_uuid = UUID(x_tenant_id.strip())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {TENANT_ID_HEADER} header value",
        ) from None
    try:
        tenant = init_context_by_tenant(tenant_uuid)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    try:
        yield tenant
    finally:
        reset_tenant_context()
