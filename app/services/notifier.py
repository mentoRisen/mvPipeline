"""Simple Discord notifier service.

This service is intentionally minimal for now:
    - Uses a single Discord webhook URL from the environment.
    - Exposes a single function: notify(type, message).
    - Caller is responsible for including tenant information in the message
      if needed (e.g. "[tenant:xyz] ...").

Later, this can be extended to:
    - Use per-tenant webhook URLs.
    - Support different "type"→channel mappings.
"""

import logging
import os
from typing import Optional

import requests

from app.context import get_tenant

logger = logging.getLogger(__name__)


def _get_webhook_url() -> Optional[str]:
    """Return the Discord webhook URL from environment, if configured."""
    return os.getenv("DISCORD_WEBHOOK_URL")


def notify(event_type: str, message: str) -> None:
    """Send a notification message to Discord.

    Assumes that the current tenant has already been set in the context
    via `init_context_by_tenant`. The tenant's name is included in the
    message as:

        [<tenant.name>] [<type>] <message>

    Args:
        event_type: Logical type/category of the event (e.g. "info",
            "warning", "error", "scheduler", etc.).
        message: The main message body to send.
    """
    tenant = get_tenant()  # Will raise if context was not initialized.

    webhook_url = _get_webhook_url()
    if not webhook_url:
        logger.warning(
            "DISCORD_WEBHOOK_URL is not set; skipping Discord notification. "
            "tenant=%s event_type=%s message=%s",
            tenant.name,
            event_type,
            message,
        )
        return

    # Build a readable message that includes tenant and type.
    content = f"[{tenant.name}] [{event_type}] {message}"
    payload = {"content": content}

    try:
        response = requests.post(webhook_url, json=payload, timeout=5)
        if response.status_code >= 400:
            logger.error(
                "%s (status=%s body=%s)",
                content,
                response.status_code,
                response.text,
            )
        else:
            logger.info("%s", content)
    except Exception as exc:
        logger.exception("Error while sending Discord notification: %s err=%s", content, exc)

