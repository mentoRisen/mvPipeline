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


def _image_job_prompt_schema() -> dict[str, Any]:
    """Image/text generators read ``prompt.prompt`` at job processing time."""
    return {
        "type": "object",
        "properties": {
            "prompt": {"type": "string"},
        },
        "required": ["prompt"],
        "additionalProperties": False,
    }


def _runway_video_prompt_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "prompt": {"type": "string"},
            "model": {
                "type": "string",
                "enum": ["gen4_turbo", "veo3.1_fast"],
            },
            "reference_id": {"type": "integer", "minimum": 1},
        },
        "required": ["prompt", "model", "reference_id"],
        "additionalProperties": False,
    }


_AI_DRAFT_IMAGE_GENERATORS = ("dalle", "gptimage15", "gptimage2")
_AI_DRAFT_JOB_GENERATORS = _AI_DRAFT_IMAGE_GENERATORS + ("runway-video",)

_AI_DRAFT_JOB_PURPOSE = ("imagecontent", "videocontent")


def _image_draft_job_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "generator": {
                "type": "string",
                "enum": list(_AI_DRAFT_IMAGE_GENERATORS),
            },
            "purpose": {
                "type": "string",
                "enum": ["imagecontent"],
            },
            "prompt": _image_job_prompt_schema(),
            "order": {"type": "integer"},
            "reference_id": {"type": "integer", "minimum": 1},
        },
        "required": ["generator", "purpose", "prompt", "order", "reference_id"],
        "additionalProperties": False,
    }


def _runway_draft_job_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "generator": {
                "type": "string",
                "enum": ["runway-video"],
            },
            "purpose": {
                "type": "string",
                "enum": ["videocontent"],
            },
            "prompt": _runway_video_prompt_schema(),
            "order": {"type": "integer"},
            "reference_id": {"type": "integer", "minimum": 1},
        },
        "required": ["generator", "purpose", "prompt", "order", "reference_id"],
        "additionalProperties": False,
    }


def _draft_job_schema() -> dict[str, Any]:
    return {
        "oneOf": [_image_draft_job_schema(), _runway_draft_job_schema()],
    }


# Slice 1–3: only ``instagram_post`` is registered; multi-image carousels use that
# template plus multiple jobs with purpose ``imagecontent`` (see publisher_instagram).
_AI_DRAFT_TEMPLATE_ENUM = ("instagram_post",)


def _draft_task_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "template": {
                "type": "string",
                "enum": list(_AI_DRAFT_TEMPLATE_ENUM),
            },
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


__all__ = [
    "_AI_DRAFT_JOB_GENERATORS",
    "_AI_DRAFT_JOB_PURPOSE",
    "draft_bundle_json_schema",
]
