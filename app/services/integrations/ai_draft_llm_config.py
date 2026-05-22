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
