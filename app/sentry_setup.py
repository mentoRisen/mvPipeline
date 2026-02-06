"""Minimal Sentry initialization helper for the project.

This module centralizes Sentry configuration so it can be reused by both
the FastAPI app and standalone scripts.

Phase 1 goal:
    - Only initialize Sentry if SENTRY_DSN is configured.
    - Read basic settings from environment variables.
    - Keep behavior safe and no-op when Sentry is not configured.
"""

import logging
import os
from typing import Optional

import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration

_sentry_initialized: bool = False


def _get_env(name: str, default: Optional[str] = None) -> Optional[str]:
    """Small helper to read environment variables."""
    value = os.getenv(name)
    if value is None:
        return default
    return value


def init_sentry() -> None:
    """Initialize Sentry once for the current process.

    Behavior:
        - If SENTRY_DSN is not set, this function is a no-op.
        - Uses SENTRY_ENVIRONMENT (default: "dev") and SENTRY_RELEASE
          if provided.
        - Configures logging integration so Python logs are sent to Sentry.
        - Safe to call multiple times; initialization happens only once.
    """
    global _sentry_initialized

    if _sentry_initialized:
        return

    dsn = _get_env("SENTRY_DSN")
    if not dsn:
        # Sentry is optional; skip initialization if DSN is missing.
        logging.getLogger(__name__).info(
            "Sentry DSN not configured (SENTRY_DSN missing); Sentry is disabled."
        )
        return

    environment = _get_env("SENTRY_ENVIRONMENT", "dev")
    release = _get_env("SENTRY_RELEASE")

    logging_integration = LoggingIntegration(
        level=logging.INFO,  # capture INFO+ as breadcrumbs
        event_level=logging.ERROR,  # send ERROR+ logs as Sentry events
    )

    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        release=release,
        integrations=[logging_integration],
    )

    _sentry_initialized = True

