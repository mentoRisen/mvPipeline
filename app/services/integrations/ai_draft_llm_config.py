"""Map GUI model/reasoning tokens to OpenAI request parameters."""

from __future__ import annotations

import os

from app.config import AI_TASK_DRAFT_MODEL

_DEFAULT_MODEL_BY_UI: dict[str, str] = {
    "5.1": os.getenv("AI_TASK_DRAFT_MODEL_5_1", AI_TASK_DRAFT_MODEL),
    "5.4": os.getenv("AI_TASK_DRAFT_MODEL_5_4", AI_TASK_DRAFT_MODEL),
    "5.5": os.getenv("AI_TASK_DRAFT_MODEL_5_5", AI_TASK_DRAFT_MODEL),
}

_VALID_REASONING = frozenset({"none", "low", "medium", "high"})

# Upstream HTTP read timeout scales with reasoning effort (base from env, default 120s).
_REASONING_TIMEOUT_MULTIPLIER: dict[str, float] = {
    "none": 1.0,
    "low": 1.25,
    "medium": 1.75,
    "high": 2.5,
}
_PREVIEW_TIMEOUT_MAX_SECONDS = 600


def resolve_openai_model(model_token: str | None) -> str:
    """Map product-facing model token to OpenAI model id."""
    token = (model_token or "").strip()
    if not token:
        return AI_TASK_DRAFT_MODEL
    return _DEFAULT_MODEL_BY_UI.get(token, AI_TASK_DRAFT_MODEL)


def resolve_reasoning_effort(reasoning_token: str | None) -> str | None:
    """Map GUI reasoning to OpenAI ``reasoning_effort``; ``none`` omits the parameter."""
    token = (reasoning_token or "none").strip().lower()
    if token not in _VALID_REASONING or token == "none":
        return None
    return token


def resolve_preview_timeout_seconds(
    reasoning_token: str | None,
    *,
    base_seconds: int | None = None,
) -> int:
    """HTTP timeout for draft preview; longer when reasoning effort is higher."""
    from app.config import AI_TASK_DRAFT_TIMEOUT_SECONDS

    base = base_seconds if base_seconds is not None else AI_TASK_DRAFT_TIMEOUT_SECONDS
    token = (reasoning_token or "none").strip().lower()
    if token not in _VALID_REASONING:
        token = "none"
    multiplier = _REASONING_TIMEOUT_MULTIPLIER.get(token, 1.0)
    return min(_PREVIEW_TIMEOUT_MAX_SECONDS, max(30, int(base * multiplier)))
