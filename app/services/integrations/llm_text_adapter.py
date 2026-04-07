"""Adapter for text-LLM draft preview generation."""

from __future__ import annotations

import json
from typing import Any

import requests

from app.config import (
    AI_TASK_DRAFT_API_URL,
    AI_TASK_DRAFT_MODEL,
    AI_TASK_DRAFT_MAX_BUNDLE_ITEMS,
    AI_TASK_DRAFT_TIMEOUT_SECONDS,
    OPENAI_API_KEY,
)


class TextDraftAdapterError(RuntimeError):
    """Base exception for text draft adapter failures."""


class TextDraftRefusalError(TextDraftAdapterError):
    """Raised when the model refuses to generate a draft."""


class TextDraftUpstreamError(TextDraftAdapterError):
    """Raised when the upstream provider fails or returns unusable content."""


class OpenAITextDraftAdapter:
    """Generate structured task draft bundles from a natural-language brief."""

    def __init__(
        self,
        *,
        api_key: str | None = OPENAI_API_KEY,
        api_url: str = AI_TASK_DRAFT_API_URL,
        model: str = AI_TASK_DRAFT_MODEL,
        timeout_seconds: int = AI_TASK_DRAFT_TIMEOUT_SECONDS,
        max_bundle_items: int = AI_TASK_DRAFT_MAX_BUNDLE_ITEMS,
        session: requests.sessions.Session | None = None,
    ) -> None:
        self.api_key = api_key
        self.api_url = api_url
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.max_bundle_items = max_bundle_items
        self.session = session or requests.Session()

    def _system_prompt(self) -> str:
        return (
            "You generate one or more draft tasks for template `instagram_post` from the "
            "user's campaign brief. Each draft task must include one or more draft jobs. "
            "Respond with JSON only using this shape: "
            '{"items":['
            '{"task":{"name":"...","template":"instagram_post","meta":{},"post":{}},'
            '"jobs":[{"generator":"...","purpose":"...","prompt":{},"order":0}],'
            '"warnings":[]}]} '
            f"Use at most {self.max_bundle_items} items. "
            "Prefer multiple items when the brief clearly describes distinct posts or angles. "
            "Do not include tenant ids, credentials, or commentary."
        )

    def build_preview_messages(
        self,
        *,
        brief: str,
        tenant_context: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """OpenAI ``messages`` array for logging and ``complete_preview_chat``."""
        return [
            {"role": "system", "content": self._system_prompt()},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "brief": brief,
                        "tenant_context": tenant_context,
                    }
                ),
            },
        ]

    def complete_preview_chat(self, messages: list[dict[str, Any]]) -> str:
        """POST chat completion; return assistant message content (raw string)."""
        if not self.api_key:
            raise TextDraftUpstreamError("AI draft preview is not configured")

        payload = {
            "model": self.model,
            "response_format": {"type": "json_object"},
            "messages": messages,
        }

        try:
            response = self.session.post(
                self.api_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
        except requests.Timeout as exc:
            raise TextDraftUpstreamError("AI draft preview timed out") from exc
        except requests.RequestException as exc:
            raise TextDraftUpstreamError("AI draft preview request failed") from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise TextDraftUpstreamError("AI draft preview returned invalid JSON") from exc

        choice = ((data.get("choices") or [{}])[0]).get("message") or {}
        if choice.get("refusal"):
            raise TextDraftRefusalError("AI draft preview was refused")

        content = choice.get("content")
        if not content:
            raise TextDraftUpstreamError("AI draft preview returned empty content")

        if isinstance(content, list):
            text_chunks = [
                block.get("text")
                for block in content
                if isinstance(block, dict) and block.get("text")
            ]
            content = "".join(text_chunks)

        if not isinstance(content, str):
            raise TextDraftUpstreamError("AI draft preview returned unsupported content")

        return content

    def parse_campaign_json_from_assistant(self, content: str) -> dict[str, Any]:
        try:
            parsed: dict[str, Any] = json.loads(content)
            return parsed
        except ValueError as exc:
            raise TextDraftUpstreamError(
                "AI draft preview returned non-JSON content"
            ) from exc

    def generate_campaign_draft(
        self,
        *,
        brief: str,
        tenant_context: dict[str, Any],
    ) -> dict[str, Any]:
        """Return raw draft JSON: ``{\"items\":[...]}`` with instagram_post tasks."""
        messages = self.build_preview_messages(
            brief=brief, tenant_context=tenant_context
        )
        content = self.complete_preview_chat(messages)
        return self.parse_campaign_json_from_assistant(content)
