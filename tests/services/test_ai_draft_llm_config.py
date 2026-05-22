from __future__ import annotations

from app.services.integrations.ai_draft_llm_config import (
    resolve_openai_model,
    resolve_reasoning_effort,
)


def test_resolve_openai_model_defaults():
    assert resolve_openai_model(None)
    assert resolve_openai_model("5.1")


def test_resolve_reasoning_effort_none_omits():
    assert resolve_reasoning_effort(None) is None
    assert resolve_reasoning_effort("none") is None


def test_resolve_reasoning_effort_maps_levels():
    assert resolve_reasoning_effort("medium") == "medium"
