"""Application service for AI task draft preview generation."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

from pydantic import ValidationError

from app.api.schemas import (
    AiTaskDraftBundleConfirmRequest,
    AiTaskDraftBundleResponse,
    AiTaskDraftItem,
)
from app.config import AI_TASK_DRAFT_MAX_BUNDLE_ITEMS
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


class AiTaskDraftItemValidationError(AiTaskDraftValidationError):
    """Validation failure tied to a specific bundle item (optional index for clients)."""

    def __init__(
        self,
        message: str,
        *,
        item_index: int | None = None,
        field: str | None = None,
    ) -> None:
        super().__init__(message)
        self.item_index = item_index
        self.field = field


class SupportsTextDraftPreview(Protocol):
    """Protocol for text draft preview adapters."""

    def generate_campaign_draft(
        self,
        *,
        brief: str,
        tenant_context: dict[str, Any],
    ) -> dict[str, Any]:
        """Return raw JSON with either ``items`` (list) or a single-task shape (task + jobs)."""


class AiTaskDraftService:
    """Generate tenant-aware draft previews and confirm bundles atomically."""

    def __init__(
        self,
        adapter: SupportsTextDraftPreview,
        *,
        bundle_writer: Callable[
            [list[tuple[Task, list[Job]]]], list[Task]
        ] | None = None,
        max_bundle_items: int | None = None,
    ) -> None:
        self.adapter = adapter
        self.bundle_writer = bundle_writer or task_repo.create_task_bundle_with_jobs
        self.max_bundle_items = max_bundle_items or AI_TASK_DRAFT_MAX_BUNDLE_ITEMS

    def generate_preview(
        self, *, brief: str, tenant: Tenant
    ) -> AiTaskDraftBundleResponse:
        """Return a validated preview bundle without persisting any records."""
        raw = self.adapter.generate_campaign_draft(
            brief=brief,
            tenant_context=self.build_tenant_context(tenant),
        )
        return self.validate_raw_llm_dict(raw)

    def validate_raw_llm_dict(self, raw: dict[str, Any]) -> AiTaskDraftBundleResponse:
        """Validate and normalize raw LLM JSON (``items`` or legacy single-task)."""
        coerced = self._coerce_raw_bundle(raw)
        items_raw = coerced.get("items")
        if not isinstance(items_raw, list):
            raise AiTaskDraftValidationError(
                "AI draft preview returned invalid structured data"
            )
        if len(items_raw) == 0:
            raise AiTaskDraftValidationError(
                "AI draft preview must include at least one task"
            )
        if len(items_raw) > self.max_bundle_items:
            raise AiTaskDraftItemValidationError(
                f"AI draft preview exceeds maximum of {self.max_bundle_items} tasks",
                field="items",
            )
        items: list[AiTaskDraftItem] = []
        for idx, item_dict in enumerate(items_raw):
            if not isinstance(item_dict, dict):
                raise AiTaskDraftItemValidationError(
                    "AI draft preview item must be an object",
                    item_index=idx,
                    field="items",
                ) from None
            try:
                items.append(self._normalize_item(item_dict))
            except AiTaskDraftValidationError as exc:
                raise AiTaskDraftItemValidationError(
                    str(exc), item_index=idx
                ) from exc
        return AiTaskDraftBundleResponse(items=items)

    def confirm_bundle(
        self,
        *,
        draft: AiTaskDraftBundleConfirmRequest,
        tenant: Tenant,
    ) -> list[Task]:
        """Persist all reviewed tasks and jobs atomically."""
        if len(draft.items) > self.max_bundle_items:
            raise AiTaskDraftItemValidationError(
                f"Reviewed bundle exceeds maximum of {self.max_bundle_items} tasks",
                field="items",
            )
        normalized: list[AiTaskDraftItem] = []
        for idx, item in enumerate(draft.items):
            try:
                normalized.append(self._normalize_item(item.model_dump()))
            except AiTaskDraftValidationError as exc:
                raise AiTaskDraftItemValidationError(
                    str(exc), item_index=idx
                ) from exc

        bundles: list[tuple[Task, list[Job]]] = []
        for preview in normalized:
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
            bundles.append((task, jobs))

        return self.bundle_writer(bundles)

    def _coerce_raw_bundle(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Accept either ``{\"items\": [...]}`` or legacy single-task JSON."""
        if "items" in raw and isinstance(raw["items"], list):
            return raw
        if "task" in raw:
            return {"items": [raw]}
        raise AiTaskDraftValidationError(
            "AI draft preview returned invalid structured data "
            "(expected `items` array or a single `task` object)"
        )

    def _normalize_item(self, raw_draft: dict[str, Any]) -> AiTaskDraftItem:
        """Validate and normalize one draft item (task + jobs)."""
        try:
            preview = AiTaskDraftItem.model_validate(raw_draft)
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
                "AI draft preview must include at least one job per task"
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
    def build_tenant_context(tenant: Tenant) -> dict[str, Any]:
        """Build the allowlisted tenant context sent to the model."""
        return {
            "name": tenant.name,
            "description": tenant.description,
            "instagram_account": tenant.instagram_account,
            "facebook_page": tenant.facebook_page,
        }


__all__ = [
    "AiTaskDraftService",
    "AiTaskDraftItemValidationError",
    "AiTaskDraftValidationError",
    "TextDraftRefusalError",
    "TextDraftUpstreamError",
]
