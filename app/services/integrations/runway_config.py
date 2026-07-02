"""Runway API credential resolution."""

from __future__ import annotations

import os
from typing import Mapping

import app.config as app_config


def resolve_runway_api_key(*, tenant_env: Mapping[str, object] | None = None) -> str:
    """Resolve Runway API key with tenant env first, then global config."""
    if tenant_env is not None:
        tenant_key = tenant_env.get("RUNWAY_API_KEY")
        if tenant_key:
            return str(tenant_key)

    global_key = os.getenv("RUNWAY_API_KEY") or app_config.RUNWAY_API_KEY
    if global_key:
        return str(global_key)

    raise ValueError(
        "RUNWAY_API_KEY not set. "
        "Add RUNWAY_API_KEY to tenant env or set it in .env / environment variable."
    )


__all__ = ["resolve_runway_api_key"]
