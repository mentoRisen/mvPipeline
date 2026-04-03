from __future__ import annotations

import pytest
from sqlmodel import Session
from sqlmodel import select

from app.api.schemas import AiTaskDraftConfirmRequest
from app.models.job import Job
from app.models.task import Task
from app.services.ai_task_draft_service import (
    AiTaskDraftService,
    AiTaskDraftValidationError,
)
from app.services.integrations.llm_text_adapter import TextDraftUpstreamError


class StubAdapter:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def generate_single_task_draft(self, *, brief: str, tenant_context: dict):
        self.calls.append({"brief": brief, "tenant_context": tenant_context})
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


def test_generate_preview_returns_validated_preview_without_db_writes(
    tenant, db_session
):
    adapter = StubAdapter(
        {
            "task": {
                "name": "Launch spring campaign",
                "template": "instagram_post",
                "meta": {"theme": "spring"},
                "post": {"caption": "Bloom with us"},
            },
            "jobs": [
                {
                    "generator": "dalle",
                    "purpose": "imagecontent",
                    "prompt": {"prompt": "flowers and clean brand layout"},
                    "order": 1,
                }
            ],
        }
    )
    service = AiTaskDraftService(adapter)

    preview = service.generate_preview(brief="Create a spring post", tenant=tenant)

    assert preview.task.template == "instagram_post"
    assert preview.task.meta["theme"] == "spring"
    assert preview.task.post["caption"] == "Bloom with us"
    assert preview.jobs[0].generator == "dalle"
    assert adapter.calls[0]["tenant_context"] == {
        "name": "Acme",
        "description": "On-brand marketing copy",
        "instagram_account": "@acme",
        "facebook_page": "acme-page",
    }
    assert db_session.exec(select(Task)).all() == []
    assert db_session.exec(select(Job)).all() == []


def test_generate_preview_allows_missing_optional_tenant_fields(tenant):
    tenant.description = None
    tenant.instagram_account = None
    tenant.facebook_page = None
    adapter = StubAdapter(
        {
            "task": {
                "name": "Minimal brand post",
                "template": "instagram_post",
                "meta": {},
                "post": {},
            },
            "jobs": [
                {
                    "generator": "dalle",
                    "purpose": "imagecontent",
                    "prompt": {"prompt": "minimal brand card"},
                    "order": 0,
                }
            ],
        }
    )

    preview = AiTaskDraftService(adapter).generate_preview(
        brief="Need one simple post",
        tenant=tenant,
    )

    assert preview.task.meta == {"theme": None}
    assert preview.task.post == {"caption": None}
    assert adapter.calls[0]["tenant_context"]["description"] is None


def test_generate_preview_rejects_non_instagram_template(tenant):
    adapter = StubAdapter(
        {
            "task": {
                "name": "Wrong template",
                "template": "other_template",
                "meta": {},
                "post": {},
            },
            "jobs": [
                {
                    "generator": "dalle",
                    "purpose": "imagecontent",
                    "prompt": {"prompt": "brand image"},
                    "order": 0,
                }
            ],
        }
    )

    with pytest.raises(AiTaskDraftValidationError):
        AiTaskDraftService(adapter).generate_preview(
            brief="Create something",
            tenant=tenant,
        )


def test_generate_preview_rejects_malformed_payload(tenant):
    adapter = StubAdapter({"task": {"name": "Missing jobs", "template": "instagram_post"}})

    with pytest.raises(AiTaskDraftValidationError):
        AiTaskDraftService(adapter).generate_preview(
            brief="Create something",
            tenant=tenant,
        )


def test_generate_preview_bubbles_up_upstream_errors(tenant):
    adapter = StubAdapter(TextDraftUpstreamError("AI draft preview timed out"))

    with pytest.raises(TextDraftUpstreamError):
        AiTaskDraftService(adapter).generate_preview(
            brief="Create something",
            tenant=tenant,
        )


def test_confirm_preview_persists_task_and_jobs_atomically(tenant, db_session):
    service = AiTaskDraftService(StubAdapter({}))
    draft = AiTaskDraftConfirmRequest.model_validate(
        {
            "task": {
                "name": "Launch spring campaign",
                "template": "instagram_post",
                "meta": {"theme": "spring"},
                "post": {"caption": "Bloom with us"},
            },
            "jobs": [
                {
                    "generator": "dalle",
                    "purpose": "imagecontent",
                    "prompt": {"prompt": "flowers and clean brand layout"},
                    "order": 0,
                }
            ],
        }
    )

    task = service.confirm_preview(draft=draft, tenant=tenant)

    stored_tasks = db_session.exec(select(Task)).all()
    stored_jobs = db_session.exec(select(Job)).all()
    assert task.tenant_id == tenant.id
    assert len(stored_tasks) == 1
    assert len(stored_jobs) == 1
    assert stored_jobs[0].task_id == stored_tasks[0].id
    assert stored_jobs[0].status == "new"


def test_confirm_preview_rolls_back_when_writer_fails(tenant, test_engine, db_session):
    draft = AiTaskDraftConfirmRequest.model_validate(
        {
            "task": {
                "name": "Launch spring campaign",
                "template": "instagram_post",
                "meta": {"theme": "spring"},
                "post": {"caption": "Bloom with us"},
            },
            "jobs": [
                {
                    "generator": "dalle",
                    "purpose": "imagecontent",
                    "prompt": {"prompt": "flowers and clean brand layout"},
                    "order": 0,
                }
            ],
        }
    )

    def failing_writer(task: Task, jobs: list[Job]) -> Task:
        with Session(test_engine) as session:
            session.add(task)
            for job in jobs:
                session.add(job)
            session.flush()
            raise RuntimeError("boom")

    service = AiTaskDraftService(StubAdapter({}), task_writer=failing_writer)

    with pytest.raises(RuntimeError):
        service.confirm_preview(draft=draft, tenant=tenant)

    assert db_session.exec(select(Task)).all() == []
    assert db_session.exec(select(Job)).all() == []


def test_confirm_preview_rejects_invalid_template(tenant):
    service = AiTaskDraftService(StubAdapter({}))
    draft = AiTaskDraftConfirmRequest.model_validate(
        {
            "task": {
                "name": "Wrong template",
                "template": "other_template",
                "meta": {},
                "post": {},
            },
            "jobs": [
                {
                    "generator": "dalle",
                    "purpose": "imagecontent",
                    "prompt": {"prompt": "brand image"},
                    "order": 0,
                }
            ],
        }
    )

    with pytest.raises(AiTaskDraftValidationError):
        service.confirm_preview(draft=draft, tenant=tenant)
