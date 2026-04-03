"""Application service for AI task draft preview generation."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

from pydantic import ValidationError

from app.api.schemas import AiTaskDraftConfirmRequest, AiTaskDraftResponse
from app.models.job import Job, JobStatus
from app.models.tenant import Tenant
from app.models.task import Task
import app.services.task_repo as task_repo
from app.services.integrations.llm_text_adapter import (
    TextDraftRefusalError,
    TextDraftUpstreamError,
)
from app.template.instagram_post import InstagramPost


class AiTaskDraftValidationError(RuntimeError):
    """Raised when the provider returns a draft that fails local validation."""


class SupportsTextDraftPreview(Protocol):
    """Protocol for text draft preview adapters."""

    def generate_single_task_draft(
        self,
        *,
        brief: str,
        tenant_context: dict[str, Any],
    ) -> dict[str, Any]:
        """Return one raw draft bundle."""


class AiTaskDraftService:
    """Generate tenant-aware draft previews for one task and its jobs."""

    def __init__(
        self,
        adapter: SupportsTextDraftPreview,
        *,
        task_writer: Callable[[Task, list[Job]], Task] | None = None,
    ) -> None:
        self.adapter = adapter
        self.task_writer = task_writer or task_repo.create_task_with_jobs

    def generate_preview(self, *, brief: str, tenant: Tenant) -> AiTaskDraftResponse:
        """Return one validated preview bundle without persisting any records."""
        raw_draft = self.adapter.generate_single_task_draft(
            brief=brief,
            tenant_context=self._tenant_context(tenant),
        )
        return self._normalize_preview(raw_draft)

    def confirm_preview(
        self,
        *,
        draft: AiTaskDraftConfirmRequest,
        tenant: Tenant,
    ) -> Task:
        """Persist one reviewed draft task and its jobs atomically."""
        preview = self._normalize_preview(draft.model_dump())

        task = Task(
            tenant_id=tenant.id,
            name=preview.task.name,
            template="instagram_post",
            meta=preview.task.meta,
            post=preview.task.post,
        )
        jobs = [
            Job(
                task_id=task.id,
                generator=job.generator,
                purpose=job.purpose,
                prompt=job.prompt,
                order=job.order,
                status=JobStatus.NEW,
            )
            for job in preview.jobs
        ]
        return self.task_writer(task, jobs)

    def _normalize_preview(self, raw_draft: dict[str, Any]) -> AiTaskDraftResponse:
        """Validate and normalize a preview bundle."""
        try:
            preview = AiTaskDraftResponse.model_validate(raw_draft)
        except ValidationError as exc:
            raise AiTaskDraftValidationError(
                "AI draft preview returned invalid structured data"
            ) from exc

        if preview.task.template != "instagram_post":
            raise AiTaskDraftValidationError(
                "AI draft preview must use the instagram_post template"
            )
        if not preview.jobs:
            raise AiTaskDraftValidationError(
                "AI draft preview must include at least one job"
            )

        template = InstagramPost()
        merged_meta = template.getEmptyMeta()
        merged_meta.update(preview.task.meta)
        merged_post = template.getEmptyPost()
        merged_post.update(preview.task.post)

        return preview.model_copy(
            update={
                "task": preview.task.model_copy(
                    update={
                        "template": "instagram_post",
                        "meta": merged_meta,
                        "post": merged_post,
                    }
                ),
                "jobs": sorted(preview.jobs, key=lambda job: job.order),
            }
        )

    @staticmethod
    def _tenant_context(tenant: Tenant) -> dict[str, Any]:
        """Build the allowlisted tenant context sent to the model."""
        return {
            "name": tenant.name,
            "description": tenant.description,
            "instagram_account": tenant.instagram_account,
            "facebook_page": tenant.facebook_page,
        }


__all__ = [
    "AiTaskDraftService",
    "AiTaskDraftValidationError",
    "TextDraftRefusalError",
    "TextDraftUpstreamError",
]
