"""Build multi-turn OpenAI message arrays for AI draft follow-ups."""

from __future__ import annotations

import json
from typing import Any

from app.models.ai_draft_communication_event import (
    AiDraftCommunicationEvent,
    AiDraftCommunicationKind,
)


def format_follow_up_user_content(
    *,
    instruction_text: str,
    iteration_mode: str | None = None,
    target_scope: str | None = None,
) -> str:
    """User message body for a follow-up iteration."""
    mode = iteration_mode or "regenerate"
    scope = target_scope or "campaign"
    return (
        f"[Follow-up iteration mode: {mode}]\n"
        f"[Target scope: {scope}]\n"
        f"Apply this instruction while preserving campaign context:\n"
        f"{instruction_text.strip()}"
    )


def build_initial_preview_messages(
    *,
    master_prompt_text: str,
    creation_prompt_text: str,
    tenant_context: dict[str, Any],
) -> list[dict[str, Any]]:
    """System = master prompt; user = creation prompt + allowlisted tenant context."""
    return [
        {"role": "system", "content": master_prompt_text.strip()},
        {
            "role": "user",
            "content": json.dumps(
                {
                    "creation_prompt": creation_prompt_text.strip(),
                    "tenant_context": tenant_context,
                }
            ),
        },
    ]


def build_follow_up_messages_from_events(
    events: list[AiDraftCommunicationEvent],
    *,
    instruction_text: str,
    iteration_mode: str | None = None,
    target_scope: str | None = None,
) -> list[dict[str, Any]]:
    """Reconstruct prior turns from transcript rows and append the follow-up user message."""
    last_prompt: dict[str, Any] | None = None
    last_assistant_content: str | None = None

    for event in events:
        if event.kind == AiDraftCommunicationKind.PROMPT_TO_AI.value:
            payload = event.payload if isinstance(event.payload, dict) else {}
            messages = payload.get("messages")
            if isinstance(messages, list) and messages:
                last_prompt = payload
        elif event.kind == AiDraftCommunicationKind.RESPONSE_FROM_AI.value:
            payload = event.payload if isinstance(event.payload, dict) else {}
            content = payload.get("content")
            if isinstance(content, str) and content.strip():
                last_assistant_content = content

    if not last_prompt:
        raise ValueError("No prior prompt_to_ai transcript found for follow-up")

    messages = last_prompt.get("messages")
    if not isinstance(messages, list) or not messages:
        raise ValueError("Prior prompt_to_ai transcript has no messages")

    out: list[dict[str, Any]] = [dict(m) for m in messages if isinstance(m, dict)]

    if last_assistant_content:
        if not out or out[-1].get("role") != "assistant":
            out.append({"role": "assistant", "content": last_assistant_content})

    out.append(
        {
            "role": "user",
            "content": format_follow_up_user_content(
                instruction_text=instruction_text,
                iteration_mode=iteration_mode,
                target_scope=target_scope,
            ),
        }
    )
    return out
