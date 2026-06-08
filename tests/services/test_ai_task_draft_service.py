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
                "reference_id": 1,
            }
        ],
    }


class StubAdapter:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def generate_campaign_draft(
        self,
        *,
        master_prompt_text: str,
        creation_prompt_text: str,
        tenant_context: dict,
        model_token: str | None = None,
        reasoning_token: str | None = None,
    ):
        self.calls.append(
            {
                "master_prompt_text": master_prompt_text,
                "creation_prompt_text": creation_prompt_text,
                "tenant_context": tenant_context,
            }
        )
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


def test_generate_preview_returns_validated_preview_without_db_writes(
    tenant, db_session
):
    adapter = StubAdapter(_single_payload())
    service = AiTaskDraftService(adapter)

    preview = service.generate_preview(
        master_prompt_text="Master",
        creation_prompt_text="Create a spring post",
        tenant=tenant,
    )

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
                            "reference_id": 1,
                        }
                    ],
                },
            ]
        }
    )
    service = AiTaskDraftService(adapter)

    preview = service.generate_preview(
        master_prompt_text="Master",
        creation_prompt_text="Campaign",
        tenant=tenant,
    )

    assert len(preview.items) == 2
    assert preview.items[0].task.name == "Launch spring campaign"
    assert preview.items[1].task.name == "Second post"
    assert db_session.exec(select(Task)).all() == []


def test_generate_preview_rejects_empty_items(tenant):
    adapter = StubAdapter({"items": []})

    with pytest.raises(AiTaskDraftValidationError, match="at least one"):
        AiTaskDraftService(adapter).generate_preview(
            master_prompt_text="M",
            creation_prompt_text="Create something",
            tenant=tenant,
        )


def test_generate_preview_rejects_too_many_jobs_per_task(tenant):
    payload = _single_payload()
    payload["jobs"] = [
        {
            "generator": "dalle",
            "purpose": "imagecontent",
            "prompt": {"prompt": f"Prompt {i}"},
            "order": i,
            "reference_id": i + 1,
        }
        for i in range(5)
    ]
    adapter = StubAdapter({"items": [payload]})
    service = AiTaskDraftService(adapter, max_bundle_items=5, max_jobs_per_item=4)

    with pytest.raises(AiTaskDraftItemValidationError, match="jobs"):
        service.validate_raw_llm_dict({"items": [payload]})


def test_generate_preview_rejects_too_many_items(tenant):
    items = []
    for i in range(20):
        p = _single_payload()
        p["task"]["name"] = f"Post {i}"
        items.append(p)
    adapter = StubAdapter({"items": items})
    service = AiTaskDraftService(adapter, max_bundle_items=5)

    with pytest.raises(AiTaskDraftValidationError, match="exceeds maximum"):
        service.generate_preview(
            master_prompt_text="M",
            creation_prompt_text="Huge batch",
            tenant=tenant,
        )


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
                    "reference_id": 1,
                }
            ],
        }
    )

    preview = AiTaskDraftService(adapter).generate_preview(
        master_prompt_text="M",
        creation_prompt_text="Need one simple post",
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
                    "reference_id": 1,
                }
            ],
        }
    )

    with pytest.raises(AiTaskDraftItemValidationError) as excinfo:
        AiTaskDraftService(adapter).generate_preview(
            master_prompt_text="M",
            creation_prompt_text="Create something",
            tenant=tenant,
        )
    assert excinfo.value.item_index == 0


def test_generate_preview_rejects_malformed_payload(tenant):
    adapter = StubAdapter({"task": {"name": "Missing jobs", "template": "instagram_post"}})

    with pytest.raises(AiTaskDraftValidationError):
        AiTaskDraftService(adapter).generate_preview(
            master_prompt_text="M",
            creation_prompt_text="Create something",
            tenant=tenant,
        )


def test_generate_preview_bubbles_up_upstream_errors(tenant):
    adapter = StubAdapter(TextDraftUpstreamError("AI draft preview timed out"))

    with pytest.raises(TextDraftUpstreamError):
        AiTaskDraftService(adapter).generate_preview(
            master_prompt_text="M",
            creation_prompt_text="Create something",
            tenant=tenant,
        )


def test_confirm_bundle_rejects_jobs_without_reference_id(tenant):
    service = AiTaskDraftService(StubAdapter({}))
    draft = AiTaskDraftBundleConfirmRequest.model_validate(
        {
            "items": [
                {
                    "task": {
                        "name": "Missing refs",
                        "template": "instagram_post",
                        "meta": {},
                        "post": {},
                    },
                    "jobs": [
                        {
                            "generator": "dalle",
                            "purpose": "imagecontent",
                            "prompt": {"prompt": "a"},
                            "order": 0,
                        }
                    ],
                }
            ]
        }
    )

    with pytest.raises(AiTaskDraftItemValidationError, match="reference_id"):
        service.confirm_bundle(draft=draft, tenant=tenant)


def test_confirm_bundle_persists_explicit_reference_ids(tenant, db_session):
    service = AiTaskDraftService(StubAdapter({}))
    draft = AiTaskDraftBundleConfirmRequest.model_validate(
        {
            "items": [
                {
                    "task": {
                        "name": "Multi-job task",
                        "template": "instagram_post",
                        "meta": {},
                        "post": {},
                    },
                    "jobs": [
                        {
                            "generator": "dalle",
                            "purpose": "imagecontent",
                            "prompt": {"prompt": "a"},
                            "order": 2,
                            "reference_id": 3,
                        },
                        {
                            "generator": "dalle",
                            "purpose": "imagecontent",
                            "prompt": {"prompt": "b"},
                            "order": 0,
                            "reference_id": 7,
                        },
                    ],
                }
            ]
        }
    )

    service.confirm_bundle(draft=draft, tenant=tenant)

    stored_jobs = db_session.exec(select(Job)).all()
    assert len(stored_jobs) == 2
    refs = sorted(j.reference_id for j in stored_jobs)
    assert refs == [3, 7]


def test_confirm_bundle_rejects_duplicate_explicit_reference_ids(tenant):
    service = AiTaskDraftService(StubAdapter({}))
    draft = AiTaskDraftBundleConfirmRequest.model_validate(
        {
            "items": [
                {
                    "task": {
                        "name": "Dup refs",
                        "template": "instagram_post",
                        "meta": {},
                        "post": {},
                    },
                    "jobs": [
                        {
                            "generator": "dalle",
                            "purpose": "imagecontent",
                            "prompt": {"prompt": "a"},
                            "reference_id": 1,
                        },
                        {
                            "generator": "dalle",
                            "purpose": "imagecontent",
                            "prompt": {"prompt": "b"},
                            "reference_id": 1,
                        },
                    ],
                }
            ]
        }
    )

    with pytest.raises(AiTaskDraftItemValidationError, match="duplicate"):
        service.confirm_bundle(draft=draft, tenant=tenant)


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

    def failing_writer(
        bundles: list[tuple[Task, list[Job]]],
        **kwargs,
    ) -> list[Task]:
        with Session(test_engine) as session:
            for task, jobs in bundles:
                session.add(task)
                session.flush()
                for job in jobs:
                    job.task_id = task.id
                    if not job.reference_id:
                        job.reference_id = 1
                    session.add(job)
                session.flush()
            raise RuntimeError("boom")

    service = AiTaskDraftService(StubAdapter({}), bundle_writer=failing_writer)

    with pytest.raises(RuntimeError):
        service.confirm_bundle(draft=draft, tenant=tenant)

    assert db_session.exec(select(Task)).all() == []
    assert db_session.exec(select(Job)).all() == []


def _runway_draft_item() -> dict:
    return {
        "task": {
            "name": "Video campaign",
            "template": "instagram_post",
            "meta": {"theme": "motion"},
            "post": {"caption": "Watch this"},
        },
        "jobs": [
            {
                "generator": "dalle",
                "purpose": "imagecontent",
                "prompt": {"prompt": "hero still"},
                "order": 0,
                "reference_id": 1,
            },
            {
                "generator": "runway-video",
                "purpose": "videocontent",
                "prompt": {
                    "prompt": "slow zoom",
                    "model": "gen4_turbo",
                    "reference_id": 1,
                },
                "order": 1,
                "reference_id": 2,
            },
        ],
    }


def test_generate_preview_normalizes_runway_bundle(tenant):
    adapter = StubAdapter({"items": [_runway_draft_item()]})
    preview = AiTaskDraftService(adapter).generate_preview(
        master_prompt_text="Master",
        creation_prompt_text="Create mixed media",
        tenant=tenant,
    )
    runway = preview.items[0].jobs[1]
    assert runway.generator == "runway-video"
    assert runway.prompt["model"] == "gen4_turbo"
    assert runway.prompt["reference_id"] == 1


def test_generate_preview_rejects_runway_without_matching_image_slot(tenant):
    payload = _runway_draft_item()
    payload["jobs"][1]["prompt"]["reference_id"] = 2
    adapter = StubAdapter({"items": [payload]})

    with pytest.raises(AiTaskDraftItemValidationError, match="imagecontent"):
        AiTaskDraftService(adapter).generate_preview(
            master_prompt_text="Master",
            creation_prompt_text="Create mixed media",
            tenant=tenant,
        )


def test_confirm_bundle_persists_runway_prompt(tenant, db_session):
    service = AiTaskDraftService(StubAdapter({}))
    draft = AiTaskDraftBundleConfirmRequest.model_validate(
        {"items": [_runway_draft_item()]}
    )

    service.confirm_bundle(draft=draft, tenant=tenant)

    stored_jobs = db_session.exec(select(Job)).all()
    runway = next(j for j in stored_jobs if j.generator == "runway-video")
    image = next(j for j in stored_jobs if j.purpose == "imagecontent")
    assert runway.purpose == "videocontent"
    assert runway.prompt == {
        "prompt": "slow zoom",
        "model": "gen4_turbo",
        "reference_id": 1,
    }
    assert image.reference_id == runway.prompt["reference_id"]


def test_confirm_bundle_runway_slot_uses_explicit_reference_ids_not_array_order(
    tenant, db_session
):
    """Array order may differ from order field; explicit job.reference_id is authoritative."""
    payload = {
        "task": {
            "name": "Video campaign",
            "template": "instagram_post",
            "meta": {},
            "post": {"caption": "Watch this"},
        },
        "jobs": [
            {
                "generator": "dalle",
                "purpose": "imagecontent",
                "prompt": {"prompt": "hero still"},
                "order": 2,
                "reference_id": 1,
            },
            {
                "generator": "runway-video",
                "purpose": "videocontent",
                "prompt": {
                    "prompt": "slow zoom",
                    "model": "gen4_turbo",
                    "reference_id": 1,
                },
                "order": 1,
                "reference_id": 2,
            },
        ],
    }
    service = AiTaskDraftService(StubAdapter({}))
    draft = AiTaskDraftBundleConfirmRequest.model_validate({"items": [payload]})

    service.confirm_bundle(draft=draft, tenant=tenant)

    stored_jobs = db_session.exec(select(Job)).all()
    image = next(j for j in stored_jobs if j.purpose == "imagecontent")
    runway = next(j for j in stored_jobs if j.generator == "runway-video")
    assert image.reference_id == 1
    assert runway.reference_id == 2
    assert runway.prompt["reference_id"] == image.reference_id


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
                            "reference_id": 1,
                        }
                    ],
                }
            ]
        }
    )

    with pytest.raises(AiTaskDraftItemValidationError) as excinfo:
        service.confirm_bundle(draft=draft, tenant=tenant)
    assert excinfo.value.item_index == 0
