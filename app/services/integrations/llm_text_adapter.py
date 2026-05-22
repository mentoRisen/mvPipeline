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
from app.services.integrations.ai_draft_llm_config import (
    resolve_openai_model,
    resolve_reasoning_effort,
)
from app.services.integrations.ai_draft_response_schema import draft_bundle_json_schema


class TextDraftAdapterError(RuntimeError):
    """Base exception for text draft adapter failures."""


class TextDraftRefusalError(TextDraftAdapterError):
    """Raised when the model refuses to generate a draft."""


class TextDraftUpstreamError(TextDraftAdapterError):
    """Raised when the upstream provider fails or returns unusable content."""


def _openai_error_detail(response: requests.Response | None) -> str:
    """Best-effort OpenAI error message for operators (no secrets)."""
    if response is None:
        return ""
    try:
        body = response.json()
        err = body.get("error") if isinstance(body, dict) else None
        if isinstance(err, dict):
            message = err.get("message")
            if isinstance(message, str) and message.strip():
                return message.strip()[:500]
    except ValueError:
        pass
    text = (response.text or "").strip()
    return text[:500] if text else ""


class OpenAITextDraftAdapter:
    """Generate structured task draft bundles via OpenAI Chat Completions."""

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

    def build_preview_messages(
        self,
        *,
        master_prompt_text: str,
        creation_prompt_text: str,
        tenant_context: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """OpenAI ``messages`` array for logging and ``complete_preview_chat``."""
        from app.services.ai_draft_conversation import build_initial_preview_messages

        return build_initial_preview_messages(
            master_prompt_text=master_prompt_text,
            creation_prompt_text=creation_prompt_text,
            tenant_context=tenant_context,
        )

    def complete_preview_chat(
        self,
        messages: list[dict[str, Any]],
        *,
        model_token: str | None = None,
        reasoning_token: str | None = None,
        max_tasks: int,
        max_jobs: int,
    ) -> str:
        """POST chat completion; return assistant message content (raw string)."""
        if not self.api_key:
            raise TextDraftUpstreamError("AI draft preview is not configured")

        resolved_model = resolve_openai_model(model_token) if model_token else self.model
        reasoning_effort = resolve_reasoning_effort(reasoning_token)
        task_cap = min(max(1, max_tasks), min(10, self.max_bundle_items))
        job_cap = max(1, min(10, max_jobs))

        payload: dict[str, Any] = {
            "model": resolved_model,
            "response_format": draft_bundle_json_schema(
                max_items=task_cap,
                max_jobs=job_cap,
            ),
            "messages": messages,
        }
        if reasoning_effort:
            payload["reasoning_effort"] = reasoning_effort

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
        except requests.HTTPError as exc:
            detail = _openai_error_detail(exc.response)
            message = "AI draft preview request failed"
            if detail:
                message = f"{message}: {detail}"
            raise TextDraftUpstreamError(message) from exc
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
        master_prompt_text: str,
        creation_prompt_text: str,
        tenant_context: dict[str, Any],
        model_token: str | None = None,
        reasoning_token: str | None = None,
        max_tasks: int = 2,
        max_jobs: int = 4,
    ) -> dict[str, Any]:
        """Return raw draft JSON: ``{\"items\":[...]}`` with instagram_post tasks."""
        messages = self.build_preview_messages(
            master_prompt_text=master_prompt_text,
            creation_prompt_text=creation_prompt_text,
            tenant_context=tenant_context,
        )
        content = self.complete_preview_chat(
            messages,
            model_token=model_token,
            reasoning_token=reasoning_token,
            max_tasks=max_tasks,
            max_jobs=max_jobs,
        )
        return self.parse_campaign_json_from_assistant(content)

    def resolved_model_for_logging(self, model_token: str | None = None) -> str:
        """Model id used on the wire (for transcript logging)."""
        return resolve_openai_model(model_token) if model_token else self.model
