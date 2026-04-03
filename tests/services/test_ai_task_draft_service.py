from __future__ import annotations

import pytest
from sqlmodel import Session
from sqlmodel import select

from app.api.schemas import AiTaskDraftBundleConfirmRequest
from app.models.job import Job
from app.models.task import Task
from app.services.ai_task_draft_service import (
    AiTaskDraftService,
    AiTaskDraftItemValidationError,
    AiTaskDraftValidationError,
)
from app.services.integrations.llm_text_adapter import TextDraftUpstreamError


def _single_payload() -> dict:
    return {
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


class StubAdapter:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def generate_campaign_draft(self, *, brief: str, tenant_context: dict):
        self.calls.append({"brief": brief, "tenant_context": tenant_context})
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


def test_generate_preview_returns_validated_preview_without_db_writes(
    tenant, db_session
):
    adapter = StubAdapter(_single_payload())
    service = AiTaskDraftService(adapter)

    preview = service.generate_preview(brief="Create a spring post", tenant=tenant)

    assert len(preview.items) == 1
    item = preview.items[0]
    assert item.task.template == "instagram_post"
    assert item.task.meta["theme"] == "spring"
    assert item.task.post["caption"] == "Bloom with us"
    assert item.jobs[0].generator == "dalle"
    assert adapter.calls[0]["tenant_context"] == {
        "name": "Acme",
        "description": "On-brand marketing copy",
        "instagram_account": "@acme",
        "facebook_page": "acme-page",
    }
    assert db_session.exec(select(Task)).all() == []
    assert db_session.exec(select(Job)).all() == []


def test_generate_preview_accepts_items_array(tenant, db_session):
    adapter = StubAdapter(
        {
            "items": [
                _single_payload(),
                {
                    "task": {
                        "name": "Second post",
                        "template": "instagram_post",
                        "meta": {"theme": "summer"},
                        "post": {"caption": "Heat wave"},
                    },
                    "jobs": [
                        {
                            "generator": "dalle",
                            "purpose": "imagecontent",
                            "prompt": {"prompt": "summer vibe"},
                            "order": 0,
                        }
                    ],
                },
            ]
        }
    )
    service = AiTaskDraftService(adapter)

    preview = service.generate_preview(brief="Campaign", tenant=tenant)

    assert len(preview.items) == 2
    assert preview.items[0].task.name == "Launch spring campaign"
    assert preview.items[1].task.name == "Second post"
    assert db_session.exec(select(Task)).all() == []


def test_generate_preview_rejects_empty_items(tenant):
    adapter = StubAdapter({"items": []})

    with pytest.raises(AiTaskDraftValidationError, match="at least one"):
        AiTaskDraftService(adapter).generate_preview(
            brief="Create something",
            tenant=tenant,
        )


def test_generate_preview_rejects_too_many_items(tenant):
    items = []
    for i in range(20):
        p = _single_payload()
        p["task"]["name"] = f"Post {i}"
        items.append(p)
    adapter = StubAdapter({"items": items})
    service = AiTaskDraftService(adapter, max_bundle_items=5)

    with pytest.raises(AiTaskDraftValidationError, match="exceeds maximum"):
        service.generate_preview(brief="Huge batch", tenant=tenant)


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

    assert preview.items[0].task.meta == {"theme": None}
    assert preview.items[0].task.post == {"caption": None}
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

    with pytest.raises(AiTaskDraftItemValidationError) as excinfo:
        AiTaskDraftService(adapter).generate_preview(
            brief="Create something",
            tenant=tenant,
        )
    assert excinfo.value.item_index == 0


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


def test_confirm_bundle_persists_tasks_and_jobs_atomically(tenant, db_session):
    service = AiTaskDraftService(StubAdapter({}))
    draft = AiTaskDraftBundleConfirmRequest.model_validate(
        {"items": [_single_payload(), _single_payload()]}
    )
    draft.items[1].task.name = "Second task"

    tasks = service.confirm_bundle(draft=draft, tenant=tenant)

    stored_tasks = db_session.exec(select(Task)).all()
    stored_jobs = db_session.exec(select(Job)).all()
    assert len(tasks) == 2
    assert {t.tenant_id for t in tasks} == {tenant.id}
    assert len(stored_tasks) == 2
    assert len(stored_jobs) == 2
    assert {j.task_id for j in stored_jobs} == {t.id for t in stored_tasks}


def test_confirm_bundle_rolls_back_when_writer_fails(tenant, test_engine, db_session):
    draft = AiTaskDraftBundleConfirmRequest.model_validate(
        {"items": [_single_payload(), _single_payload()]}
    )

    def failing_writer(bundles: list[tuple[Task, list[Job]]]) -> list[Task]:
        with Session(test_engine) as session:
            for task, jobs in bundles:
                session.add(task)
                for job in jobs:
                    session.add(job)
                session.flush()
            raise RuntimeError("boom")

    service = AiTaskDraftService(StubAdapter({}), bundle_writer=failing_writer)

    with pytest.raises(RuntimeError):
        service.confirm_bundle(draft=draft, tenant=tenant)

    assert db_session.exec(select(Task)).all() == []
    assert db_session.exec(select(Job)).all() == []


def test_confirm_bundle_rejects_invalid_template(tenant):
    service = AiTaskDraftService(StubAdapter({}))
    draft = AiTaskDraftBundleConfirmRequest.model_validate(
        {
            "items": [
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
            ]
        }
    )

    with pytest.raises(AiTaskDraftItemValidationError) as excinfo:
        service.confirm_bundle(draft=draft, tenant=tenant)
    assert excinfo.value.item_index == 0
