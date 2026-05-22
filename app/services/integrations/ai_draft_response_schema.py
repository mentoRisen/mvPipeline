"""OpenAI structured-output JSON Schema for AI task draft bundles."""

from __future__ import annotations

from typing import Any


def _nullable_string_schema() -> dict[str, Any]:
    return {"type": ["string", "null"]}


def _instagram_meta_schema() -> dict[str, Any]:
    """Matches ``InstagramPost.getEmptyMeta()`` for strict structured outputs."""
    return {
        "type": "object",
        "properties": {
            "theme": _nullable_string_schema(),
        },
        "required": ["theme"],
        "additionalProperties": False,
    }


def _instagram_post_schema() -> dict[str, Any]:
    """Matches ``InstagramPost.getEmptyPost()`` for strict structured outputs."""
    return {
        "type": "object",
        "properties": {
            "caption": _nullable_string_schema(),
        },
        "required": ["caption"],
        "additionalProperties": False,
    }


def _job_prompt_schema() -> dict[str, Any]:
    """Image/text generators read ``prompt.prompt`` at job processing time."""
    return {
        "type": "object",
        "properties": {
            "prompt": {"type": "string"},
        },
        "required": ["prompt"],
        "additionalProperties": False,
    }


def _draft_job_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "generator": {"type": "string"},
            "purpose": _nullable_string_schema(),
            "prompt": _job_prompt_schema(),
            "order": {"type": "integer"},
        },
        # Strict mode: every key in ``properties`` must appear in ``required``.
        # Use nullable types for optional job fields (e.g. purpose may be null).
        "required": ["generator", "purpose", "prompt", "order"],
        "additionalProperties": False,
    }


def _draft_task_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "template": {"type": "string"},
            "meta": _instagram_meta_schema(),
            "post": _instagram_post_schema(),
        },
        "required": ["name", "template", "meta", "post"],
        "additionalProperties": False,
    }


def _draft_item_schema(*, max_jobs: int) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "task": _draft_task_schema(),
            "jobs": {
                "type": "array",
                "maxItems": max_jobs,
                "items": _draft_job_schema(),
            },
            "warnings": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
        "required": ["task", "jobs", "warnings"],
        "additionalProperties": False,
    }


def draft_bundle_json_schema(*, max_items: int, max_jobs: int) -> dict[str, Any]:
    """Return ``response_format.json_schema`` payload for Chat Completions."""
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "ai_task_draft_bundle",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "maxItems": max_items,
                        "items": _draft_item_schema(max_jobs=max_jobs),
                    }
                },
                "required": ["items"],
                "additionalProperties": False,
            },
        },
    }
