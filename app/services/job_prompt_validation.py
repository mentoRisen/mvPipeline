"""Shared validation for job prompt JSON by generator."""

from __future__ import annotations

from typing import Any, Sequence
from uuid import UUID

from sqlmodel import Session, select

from app.models.job import Job

RUNWAY_VIDEO_GENERATOR = "runway-video"
VIDEOCONTENT_PURPOSE = "videocontent"
IMAGECONTENT_PURPOSE = "imagecontent"
RUNWAY_VIDEO_MODELS = ("gen4_turbo", "veo3.1_fast")


class JobPromptValidationError(ValueError):
    """Raised when job prompt JSON fails validation."""

    def __init__(self, message: str, *, field: str = "prompt") -> None:
        super().__init__(message)
        self.field = field


def _is_runway_generator(generator: str | None) -> bool:
    return (generator or "").lower() == RUNWAY_VIDEO_GENERATOR


def validate_runway_video_prompt(prompt: dict | None) -> dict:
    """Validate and normalize runway-video prompt shape."""
    if not isinstance(prompt, dict):
        raise JobPromptValidationError(
            "prompt must be a JSON object for runway-video jobs",
            field="prompt",
        )

    text = prompt.get("prompt")
    if not isinstance(text, str) or not text.strip():
        raise JobPromptValidationError(
            "prompt.prompt must be a non-empty string",
            field="prompt",
        )

    model = prompt.get("model")
    if not isinstance(model, str) or model not in RUNWAY_VIDEO_MODELS:
        raise JobPromptValidationError(
            f"prompt.model must be one of: {', '.join(RUNWAY_VIDEO_MODELS)}",
            field="prompt.model",
        )

    reference_id = prompt.get("reference_id")
    if type(reference_id) is not int or reference_id < 1:
        raise JobPromptValidationError(
            "prompt.reference_id must be an integer >= 1",
            field="prompt.reference_id",
        )

    return {
        "prompt": text.strip(),
        "model": model,
        "reference_id": reference_id,
    }


def validate_image_slot_reference(
    session: Session,
    task_id: UUID,
    slot: int,
) -> None:
    """Ensure an imagecontent job exists on the task at the given reference_id slot."""
    row = session.exec(
        select(Job.id)
        .where(
            Job.task_id == task_id,
            Job.reference_id == slot,
            Job.purpose == IMAGECONTENT_PURPOSE,
        )
        .limit(1)
    ).first()
    if row is None:
        raise JobPromptValidationError(
            f"prompt.reference_id {slot} does not match an imagecontent job on this task",
            field="prompt.reference_id",
        )


def planned_reference_ids(
    explicit_reference_ids: Sequence[int | None],
) -> list[int]:
    """Mirror assign_reference_ids_for_new_jobs auto-fill without DB checks."""
    if not explicit_reference_ids:
        return []

    next_auto = 1
    assigned: list[int] = []
    for explicit in explicit_reference_ids:
        if explicit is not None:
            assigned.append(explicit)
            next_auto = max(next_auto, explicit + 1)
        else:
            assigned.append(next_auto)
            next_auto += 1
    return assigned


def validate_draft_job_reference_ids(draft_jobs: Sequence[Any]) -> None:
    """Require explicit, unique reference_id on every job in a draft item."""
    seen: set[int] = set()
    for job_index, job in enumerate(draft_jobs):
        ref = getattr(job, "reference_id", None)
        if type(ref) is not int or ref < 1:
            raise JobPromptValidationError(
                "reference_id must be an integer >= 1 on every draft job",
                field=f"jobs[{job_index}].reference_id",
            )
        if ref in seen:
            raise JobPromptValidationError(
                f"duplicate reference_id {ref} in the same draft item",
                field=f"jobs[{job_index}].reference_id",
            )
        seen.add(ref)


def validate_runway_reference_in_draft_jobs(
    *,
    draft_jobs: Sequence[Any],
    image_slot: int,
) -> None:
    """Validate prompt.reference_id against explicit imagecontent job slots."""
    for job in draft_jobs:
        purpose = (getattr(job, "purpose", None) or "").lower()
        if purpose != IMAGECONTENT_PURPOSE:
            continue
        ref = getattr(job, "reference_id", None)
        if type(ref) is int and ref == image_slot:
            return

    raise JobPromptValidationError(
        f"prompt.reference_id {image_slot} does not match an imagecontent job in this draft item",
        field="prompt.reference_id",
    )


def normalize_non_runway_prompt(prompt: dict | None) -> dict | None:
    """Strip runway-only keys when the effective generator is not runway-video."""
    if not isinstance(prompt, dict):
        return prompt
    if "model" not in prompt and "reference_id" not in prompt:
        return prompt

    text = prompt.get("prompt")
    if isinstance(text, str) and text.strip():
        return {"prompt": text.strip()}
    return {"prompt": ""}


def validate_job_prompt_for_write(
    session: Session | None,
    task_id: UUID | None,
    *,
    generator: str,
    purpose: str | None,
    prompt: dict | None,
    draft_jobs: Sequence[Any] | None = None,
) -> dict | None:
    """Validate prompt for create/update (REST) or draft item normalization."""
    gen_lower = (generator or "").lower()
    purpose_lower = (purpose or "").lower()

    if purpose_lower == VIDEOCONTENT_PURPOSE and gen_lower != RUNWAY_VIDEO_GENERATOR:
        raise JobPromptValidationError(
            f"purpose {VIDEOCONTENT_PURPOSE} requires generator {RUNWAY_VIDEO_GENERATOR}",
            field="purpose",
        )

    if not _is_runway_generator(generator):
        return normalize_non_runway_prompt(prompt)

    if purpose_lower != VIDEOCONTENT_PURPOSE:
        raise JobPromptValidationError(
            f"generator {RUNWAY_VIDEO_GENERATOR} requires purpose {VIDEOCONTENT_PURPOSE}",
            field="purpose",
        )

    normalized = validate_runway_video_prompt(prompt)
    slot = normalized["reference_id"]

    if draft_jobs is not None:
        validate_runway_reference_in_draft_jobs(
            draft_jobs=draft_jobs,
            image_slot=slot,
        )
    elif session is not None and task_id is not None:
        validate_image_slot_reference(session, task_id, slot)
    else:
        raise JobPromptValidationError(
            "runway-video prompt validation requires task context or draft jobs",
            field="prompt",
        )

    return normalized


__all__ = [
    "IMAGECONTENT_PURPOSE",
    "JobPromptValidationError",
    "RUNWAY_VIDEO_GENERATOR",
    "RUNWAY_VIDEO_MODELS",
    "VIDEOCONTENT_PURPOSE",
    "normalize_non_runway_prompt",
    "planned_reference_ids",
    "validate_draft_job_reference_ids",
    "validate_image_slot_reference",
    "validate_job_prompt_for_write",
    "validate_runway_reference_in_draft_jobs",
    "validate_runway_video_prompt",
]
