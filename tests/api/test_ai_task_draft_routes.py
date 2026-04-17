from __future__ import annotations

import json
from uuid import UUID

from app.api.schemas import (
    AiTaskDraftBundleConfirmRequest,
    AiTaskDraftBundleResponse,
)
from app.services import ai_draft_session_repo
from app.models.task import Task
from app.services.ai_task_draft_service import AiTaskDraftValidationError
from app.services.integrations.llm_text_adapter import (
    OpenAITextDraftAdapter,
    TextDraftRefusalError,
    TextDraftUpstreamError,
)
from sqlalchemy.exc import IntegrityError


class StubConfirmService:
    def __init__(self, result):
        self.result = result

    def confirm_bundle(self, *, draft, tenant):
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def _sample_bundle() -> AiTaskDraftBundleResponse:
    return AiTaskDraftBundleResponse.model_validate(
        {
            "items": [
                {
                    "task": {
                        "name": "Launch post",
                        "template": "instagram_post",
                        "meta": {"theme": "launch"},
                        "post": {"caption": "Hello world"},
                    },
                    "jobs": [
                        {
                            "generator": "dalle",
                            "purpose": "imagecontent",
                            "prompt": {"prompt": "launch visual"},
                            "order": 0,
                        }
                    ],
                }
            ]
        }
    )


def test_ai_draft_preview_route_returns_bundle(client, tenant, monkeypatch):
    llm_body = _sample_bundle().model_dump(mode="json")
    monkeypatch.setattr(
        OpenAITextDraftAdapter,
        "complete_preview_chat",
        lambda self, m: json.dumps(llm_body),
    )
    monkeypatch.setattr("app.api.routes.current_tenant", lambda: tenant)

    response = client.post(
        "/api/v1/tasks/ai-draft-preview",
        headers={"X-Tenant-Id": str(tenant.id), "Authorization": "Bearer test"},
        json={"brief": "Create a launch post"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["preview_status"] == "succeeded"
    assert len(body["items"]) == 1
    assert body["items"][0]["task"]["template"] == "instagram_post"
    assert body.get("draft_session_id")
    UUID(body["draft_session_id"])  # valid UUID


def test_ai_draft_preview_route_rejects_tenant_fields_in_body(client, tenant):
    response = client.post(
        "/api/v1/tasks/ai-draft-preview",
        headers={"X-Tenant-Id": str(tenant.id), "Authorization": "Bearer test"},
        json={
            "brief": "Create a launch post",
            "tenant_id": "not-allowed",
        },
    )

    assert response.status_code == 422


def test_ai_draft_preview_route_requires_valid_tenant_header(client):
    response = client.post(
        "/api/v1/tasks/ai-draft-preview",
        headers={"X-Tenant-Id": "bad-uuid", "Authorization": "Bearer test"},
        json={"brief": "Create a launch post"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid X-Tenant-Id header value"


def test_ai_draft_preview_route_maps_validation_errors(client, tenant, monkeypatch):
    monkeypatch.setattr(
        OpenAITextDraftAdapter,
        "complete_preview_chat",
        lambda self, m: json.dumps({"items": []}),
    )
    monkeypatch.setattr("app.api.routes.current_tenant", lambda: tenant)

    response = client.post(
        "/api/v1/tasks/ai-draft-preview",
        headers={"X-Tenant-Id": str(tenant.id), "Authorization": "Bearer test"},
        json={"brief": "Create a launch post"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["preview_status"] == "failed"
    assert body["items"] == []
    sid = body["draft_session_id"]
    detail = client.get(
        f"/api/v1/tasks/ai-draft-sessions/{sid}",
        headers={"X-Tenant-Id": str(tenant.id), "Authorization": "Bearer test"},
    ).json()
    assert detail["preview_status"] == "failed"
    assert detail["last_error"]["error"] == "ai_draft_validation"


def test_ai_draft_preview_route_validation_error_includes_field_path(client, tenant, monkeypatch):
    bad = {
        "items": [
            {
                "task": {
                    "name": "Valid",
                    "template": "instagram_post",
                    "meta": {},
                    "post": {"caption": "ok"},
                },
                "jobs": [
                    {
                        "generator": "dalle",
                        "purpose": "imagecontent",
                        "prompt": {"prompt": "x"},
                        "order": 0,
                    }
                ],
            },
            {
                "task": {
                    "name": "Invalid second",
                    "template": "instagram_post",
                    "meta": {},
                    "post": {"caption": "bad"},
                },
                "jobs": [
                    {
                        "generator": "dalle",
                        "purpose": "imagecontent",
                        "prompt": "not-an-object",
                        "order": 0,
                    }
                ],
            },
        ]
    }
    monkeypatch.setattr(
        OpenAITextDraftAdapter,
        "complete_preview_chat",
        lambda self, m: json.dumps(bad),
    )
    monkeypatch.setattr("app.api.routes.current_tenant", lambda: tenant)

    response = client.post(
        "/api/v1/tasks/ai-draft-preview",
        headers={"X-Tenant-Id": str(tenant.id), "Authorization": "Bearer test"},
        json={"brief": "Create a launch post"},
    )
    assert response.status_code == 200
    sid = response.json()["draft_session_id"]
    detail = client.get(
        f"/api/v1/tasks/ai-draft-sessions/{sid}",
        headers={"X-Tenant-Id": str(tenant.id), "Authorization": "Bearer test"},
    ).json()
    assert detail["preview_status"] == "failed"
    assert detail["last_error"]["error"] == "ai_draft_validation"
    assert detail["last_error"]["item_index"] == 1
    assert detail["last_error"]["field"] == "jobs.0.prompt"


def test_ai_draft_preview_route_maps_refusals(client, tenant, monkeypatch):
    def _refuse(self, m):
        raise TextDraftRefusalError("AI draft preview was refused")

    monkeypatch.setattr(OpenAITextDraftAdapter, "complete_preview_chat", _refuse)
    monkeypatch.setattr("app.api.routes.current_tenant", lambda: tenant)

    response = client.post(
        "/api/v1/tasks/ai-draft-preview",
        headers={"X-Tenant-Id": str(tenant.id), "Authorization": "Bearer test"},
        json={"brief": "Create a launch post"},
    )

    assert response.status_code == 200
    assert response.json()["preview_status"] == "failed"


def test_ai_draft_preview_route_maps_upstream_failures(client, tenant, monkeypatch):
    def _upstream(self, m):
        raise TextDraftUpstreamError("AI draft preview request failed")

    monkeypatch.setattr(OpenAITextDraftAdapter, "complete_preview_chat", _upstream)
    monkeypatch.setattr("app.api.routes.current_tenant", lambda: tenant)

    response = client.post(
        "/api/v1/tasks/ai-draft-preview",
        headers={"X-Tenant-Id": str(tenant.id), "Authorization": "Bearer test"},
        json={"brief": "Create a launch post"},
    )

    assert response.status_code == 200
    assert response.json()["preview_status"] == "failed"


def test_ai_draft_confirm_route_creates_tasks(client, tenant, monkeypatch):
    t1 = Task(name="Launch post", template="instagram_post", tenant_id=tenant.id)
    t2 = Task(name="Second", template="instagram_post", tenant_id=tenant.id)
    monkeypatch.setattr(
        "app.api.routes.get_ai_task_draft_service",
        lambda: StubConfirmService([t1, t2]),
    )
    monkeypatch.setattr("app.api.routes.current_tenant", lambda: tenant)

    response = client.post(
        "/api/v1/tasks/ai-draft-confirm",
        headers={"X-Tenant-Id": str(tenant.id), "Authorization": "Bearer test"},
        json=AiTaskDraftBundleConfirmRequest.model_validate(
            {
                "items": [
                    {
                        "task": {
                            "name": "Launch post",
                            "template": "instagram_post",
                            "meta": {"theme": "launch"},
                            "post": {"caption": "Hello world"},
                        },
                        "jobs": [
                            {
                                "generator": "dalle",
                                "purpose": "imagecontent",
                                "prompt": {"prompt": "launch visual"},
                                "order": 0,
                            }
                        ],
                    },
                    {
                        "task": {
                            "name": "Second",
                            "template": "instagram_post",
                            "meta": {},
                            "post": {},
                        },
                        "jobs": [
                            {
                                "generator": "dalle",
                                "purpose": "imagecontent",
                                "prompt": {"prompt": "x"},
                                "order": 0,
                            }
                        ],
                    },
                ]
            }
        ).model_dump(),
    )

    assert response.status_code == 201
    body = response.json()
    assert len(body["tasks"]) == 2
    assert body["tasks"][0]["tenant_id"] == str(tenant.id)


def test_ai_draft_confirm_route_rejects_tenant_fields_in_body(client, tenant, monkeypatch):
    monkeypatch.setattr(
        "app.api.routes.get_ai_task_draft_service",
        lambda: StubConfirmService(
            [
                Task(name="Launch post", template="instagram_post", tenant_id=tenant.id),
            ]
        ),
    )
    monkeypatch.setattr("app.api.routes.current_tenant", lambda: tenant)

    response = client.post(
        "/api/v1/tasks/ai-draft-confirm",
        headers={"X-Tenant-Id": str(tenant.id), "Authorization": "Bearer test"},
        json={
            "items": [
                {
                    "task": {
                        "name": "Launch post",
                        "template": "instagram_post",
                        "meta": {"theme": "launch"},
                        "post": {"caption": "Hello world"},
                        "tenant_id": "bad",
                    },
                    "jobs": [
                        {
                            "generator": "dalle",
                            "purpose": "imagecontent",
                            "prompt": {"prompt": "launch visual"},
                            "order": 0,
                        }
                    ],
                }
            ]
        },
    )

    assert response.status_code == 422


def test_ai_draft_confirm_route_maps_validation_errors(client, tenant, monkeypatch):
    monkeypatch.setattr(
        "app.api.routes.get_ai_task_draft_service",
        lambda: StubConfirmService(AiTaskDraftValidationError("invalid reviewed draft")),
    )
    monkeypatch.setattr("app.api.routes.current_tenant", lambda: tenant)

    response = client.post(
        "/api/v1/tasks/ai-draft-confirm",
        headers={"X-Tenant-Id": str(tenant.id), "Authorization": "Bearer test"},
        json=AiTaskDraftBundleConfirmRequest.model_validate(
            {
                "items": [
                    {
                        "task": {
                            "name": "Launch post",
                            "template": "instagram_post",
                            "meta": {"theme": "launch"},
                            "post": {"caption": "Hello world"},
                        },
                        "jobs": [
                            {
                                "generator": "dalle",
                                "purpose": "imagecontent",
                                "prompt": {"prompt": "launch visual"},
                                "order": 0,
                            }
                        ],
                    }
                ]
            }
        ).model_dump(),
    )

    assert response.status_code == 422


def test_ai_draft_confirm_route_maps_database_failures(client, tenant, monkeypatch):
    monkeypatch.setattr(
        "app.api.routes.get_ai_task_draft_service",
        lambda: StubConfirmService(IntegrityError("stmt", {}, Exception("boom"))),
    )
    monkeypatch.setattr("app.api.routes.current_tenant", lambda: tenant)

    response = client.post(
        "/api/v1/tasks/ai-draft-confirm",
        headers={"X-Tenant-Id": str(tenant.id), "Authorization": "Bearer test"},
        json=AiTaskDraftBundleConfirmRequest.model_validate(
            {
                "items": [
                    {
                        "task": {
                            "name": "Launch post",
                            "template": "instagram_post",
                            "meta": {"theme": "launch"},
                            "post": {"caption": "Hello world"},
                        },
                        "jobs": [
                            {
                                "generator": "dalle",
                                "purpose": "imagecontent",
                                "prompt": {"prompt": "launch visual"},
                                "order": 0,
                            }
                        ],
                    }
                ]
            }
        ).model_dump(),
    )

    assert response.status_code == 500


def test_ai_draft_preview_route_returns_404_for_unknown_tenant(client):
    response = client.post(
        "/api/v1/tasks/ai-draft-preview",
        headers={
            "X-Tenant-Id": "00000000-0000-0000-0000-000000000000",
            "Authorization": "Bearer test",
        },
        json={"brief": "Create a launch post"},
    )

    assert response.status_code == 404


def test_ai_draft_preview_route_requires_instruction_for_iteration(client, tenant, monkeypatch):
    monkeypatch.setattr("app.api.routes.current_tenant", lambda: tenant)
    response = client.post(
        "/api/v1/tasks/ai-draft-preview",
        headers={"X-Tenant-Id": str(tenant.id), "Authorization": "Bearer test"},
        json={
            "brief": "update this draft",
            "draft_session_id": "00000000-0000-0000-0000-000000000000",
            "iteration_mode": "regenerate",
            "target_scope": "campaign",
        },
    )
    assert response.status_code == 422
    assert "instruction_text" in response.json()["detail"]


def test_ai_draft_preview_route_rejects_non_campaign_scope(client, tenant, monkeypatch):
    monkeypatch.setattr("app.api.routes.current_tenant", lambda: tenant)
    response = client.post(
        "/api/v1/tasks/ai-draft-preview",
        headers={"X-Tenant-Id": str(tenant.id), "Authorization": "Bearer test"},
        json={
            "brief": "update this draft",
            "draft_session_id": "00000000-0000-0000-0000-000000000000",
            "iteration_mode": "targeted_intent",
            "instruction_text": "rewrite headline",
            "target_scope": "item",
        },
    )
    assert response.status_code == 422
    assert "target_scope" in response.json()["detail"]


def test_ai_draft_preview_route_rejects_iteration_without_session_id(client, tenant, monkeypatch):
    monkeypatch.setattr("app.api.routes.current_tenant", lambda: tenant)
    response = client.post(
        "/api/v1/tasks/ai-draft-preview",
        headers={"X-Tenant-Id": str(tenant.id), "Authorization": "Bearer test"},
        json={
            "brief": "update this draft",
            "iteration_mode": "regenerate",
            "instruction_text": "tighten tone",
            "target_scope": "campaign",
        },
    )
    assert response.status_code == 422
    assert "draft_session_id" in response.json()["detail"]


def test_ai_draft_preview_route_rejects_invalid_iteration_mode(client, tenant, monkeypatch):
    monkeypatch.setattr("app.api.routes.current_tenant", lambda: tenant)
    response = client.post(
        "/api/v1/tasks/ai-draft-preview",
        headers={"X-Tenant-Id": str(tenant.id), "Authorization": "Bearer test"},
        json={
            "brief": "update this draft",
            "draft_session_id": "00000000-0000-0000-0000-000000000000",
            "iteration_mode": "bad_mode",
            "instruction_text": "tighten tone",
            "target_scope": "campaign",
        },
    )
    assert response.status_code == 422
    assert "iteration_mode" in response.json()["detail"]


def test_ai_draft_preview_route_returns_409_when_draft_cap_reached(
    client, tenant, monkeypatch
):
    monkeypatch.setattr("app.api.routes.current_tenant", lambda: tenant)
    monkeypatch.setattr("app.services.ai_draft_session_repo.AI_DRAFT_SESSION_MAX_PER_USER", 1)
    monkeypatch.setattr(
        OpenAITextDraftAdapter,
        "complete_preview_chat",
        lambda self, m: json.dumps(_sample_bundle().model_dump(mode="json")),
    )

    first = client.post(
        "/api/v1/tasks/ai-draft-preview",
        headers={"X-Tenant-Id": str(tenant.id), "Authorization": "Bearer test"},
        json={"brief": "first"},
    )
    assert first.status_code == 200

    second = client.post(
        "/api/v1/tasks/ai-draft-preview",
        headers={"X-Tenant-Id": str(tenant.id), "Authorization": "Bearer test"},
        json={"brief": "second"},
    )
    assert second.status_code == 409
    detail = second.json()["detail"]
    assert detail["error"] == "ai_draft_session_limit_reached"


def test_ai_draft_restore_endpoint_restores_snapshot(client, tenant, monkeypatch, auth_user):
    llm_body = _sample_bundle().model_dump(mode="json")
    monkeypatch.setattr(
        OpenAITextDraftAdapter,
        "complete_preview_chat",
        lambda self, m: json.dumps(llm_body),
    )
    monkeypatch.setattr("app.api.routes.current_tenant", lambda: tenant)
    first = client.post(
        "/api/v1/tasks/ai-draft-preview",
        headers={"X-Tenant-Id": str(tenant.id), "Authorization": "Bearer test"},
        json={"brief": "first"},
    )
    sid = first.json()["draft_session_id"]
    second = client.post(
        "/api/v1/tasks/ai-draft-preview",
        headers={"X-Tenant-Id": str(tenant.id), "Authorization": "Bearer test"},
        json={"brief": "second", "draft_session_id": sid},
    )
    assert second.status_code == 200
    detail = client.get(
        f"/api/v1/tasks/ai-draft-sessions/{sid}",
        headers={"X-Tenant-Id": str(tenant.id), "Authorization": "Bearer test"},
    ).json()
    assert len(detail["undo_snapshots"]) >= 1
    snapshot_id = detail["undo_snapshots"][0]["id"]
    restore = client.post(
        f"/api/v1/tasks/ai-draft-sessions/{sid}/restore",
        headers={"X-Tenant-Id": str(tenant.id), "Authorization": "Bearer test"},
        json={"snapshot_id": snapshot_id},
    )
    assert restore.status_code == 200
    assert restore.json()["preview_status"] == "succeeded"
    restored_names = [it["task"]["name"] for it in restore.json()["items"]]
    assert "Launch post" in restored_names


def test_ai_draft_confirm_second_submit_with_session_returns_404(
    client, tenant, monkeypatch, auth_user
):
    llm_body = _sample_bundle().model_dump(mode="json")
    monkeypatch.setattr(
        OpenAITextDraftAdapter,
        "complete_preview_chat",
        lambda self, m: json.dumps(llm_body),
    )
    monkeypatch.setattr("app.api.routes.current_tenant", lambda: tenant)

    prev = client.post(
        "/api/v1/tasks/ai-draft-preview",
        headers={"X-Tenant-Id": str(tenant.id), "Authorization": "Bearer test"},
        json={"brief": "Create a launch post"},
    )
    assert prev.status_code == 200
    sid = prev.json()["draft_session_id"]

    t1 = Task(name="Launch post", template="instagram_post", tenant_id=tenant.id)
    monkeypatch.setattr(
        "app.api.routes.get_ai_task_draft_service",
        lambda: StubConfirmService([t1]),
    )

    payload = AiTaskDraftBundleConfirmRequest.model_validate(
        {
            "items": [
                {
                    "task": {
                        "name": "Launch post",
                        "template": "instagram_post",
                        "meta": {"theme": "launch"},
                        "post": {"caption": "Hello world"},
                    },
                    "jobs": [
                        {
                            "generator": "dalle",
                            "purpose": "imagecontent",
                            "prompt": {"prompt": "launch visual"},
                            "order": 0,
                        }
                    ],
                }
            ],
            "draft_session_id": sid,
        }
    ).model_dump(mode="json")

    r1 = client.post(
        "/api/v1/tasks/ai-draft-confirm",
        headers={"X-Tenant-Id": str(tenant.id), "Authorization": "Bearer test"},
        json=payload,
    )
    assert r1.status_code == 201

    r2 = client.post(
        "/api/v1/tasks/ai-draft-confirm",
        headers={"X-Tenant-Id": str(tenant.id), "Authorization": "Bearer test"},
        json=payload,
    )
    assert r2.status_code == 404


def test_ai_draft_confirm_allows_failed_session_with_existing_bundle(
    client, tenant, monkeypatch, auth_user
):
    llm_body = _sample_bundle().model_dump(mode="json")
    monkeypatch.setattr(
        OpenAITextDraftAdapter,
        "complete_preview_chat",
        lambda self, m: json.dumps(llm_body),
    )
    monkeypatch.setattr("app.api.routes.current_tenant", lambda: tenant)

    prev = client.post(
        "/api/v1/tasks/ai-draft-preview",
        headers={"X-Tenant-Id": str(tenant.id), "Authorization": "Bearer test"},
        json={"brief": "Create a launch post"},
    )
    assert prev.status_code == 200
    sid = prev.json()["draft_session_id"]

    ai_draft_session_repo.finalize_preview_failure(
        draft_session_id=UUID(sid),
        tenant_id=tenant.id,
        user_id=auth_user.id,
        last_error={"error": "upstream", "message": "simulated failure"},
    )

    monkeypatch.setattr(
        "app.api.routes.get_ai_task_draft_service",
        lambda: StubConfirmService(
            [Task(name="Launch post", template="instagram_post", tenant_id=tenant.id)]
        ),
    )
    payload = AiTaskDraftBundleConfirmRequest.model_validate(
        {
            "items": [
                {
                    "task": {
                        "name": "Launch post",
                        "template": "instagram_post",
                        "meta": {"theme": "launch"},
                        "post": {"caption": "Hello world"},
                    },
                    "jobs": [
                        {
                            "generator": "dalle",
                            "purpose": "imagecontent",
                            "prompt": {"prompt": "launch visual"},
                            "order": 0,
                        }
                    ],
                }
            ],
            "draft_session_id": sid,
        }
    ).model_dump(mode="json")

    response = client.post(
        "/api/v1/tasks/ai-draft-confirm",
        headers={"X-Tenant-Id": str(tenant.id), "Authorization": "Bearer test"},
        json=payload,
    )
    assert response.status_code == 201


def test_ai_draft_confirm_validation_persists_last_error(
    client, tenant, monkeypatch, auth_user
):
    llm_body = _sample_bundle().model_dump(mode="json")
    monkeypatch.setattr(
        OpenAITextDraftAdapter,
        "complete_preview_chat",
        lambda self, m: json.dumps(llm_body),
    )
    monkeypatch.setattr("app.api.routes.current_tenant", lambda: tenant)

    prev = client.post(
        "/api/v1/tasks/ai-draft-preview",
        headers={"X-Tenant-Id": str(tenant.id), "Authorization": "Bearer test"},
        json={"brief": "Create a launch post"},
    )
    sid = prev.json()["draft_session_id"]

    monkeypatch.setattr(
        "app.api.routes.get_ai_task_draft_service",
        lambda: StubConfirmService(
            AiTaskDraftValidationError("invalid reviewed draft")
        ),
    )

    payload = AiTaskDraftBundleConfirmRequest.model_validate(
        {
            "items": [
                {
                    "task": {
                        "name": "Launch post",
                        "template": "instagram_post",
                        "meta": {"theme": "launch"},
                        "post": {"caption": "Hello world"},
                    },
                    "jobs": [
                        {
                            "generator": "dalle",
                            "purpose": "imagecontent",
                            "prompt": {"prompt": "launch visual"},
                            "order": 0,
                        }
                    ],
                }
            ],
            "draft_session_id": sid,
        }
    ).model_dump(mode="json")

    response = client.post(
        "/api/v1/tasks/ai-draft-confirm",
        headers={"X-Tenant-Id": str(tenant.id), "Authorization": "Bearer test"},
        json=payload,
    )
    assert response.status_code == 422

    row = ai_draft_session_repo.get_active_for_user(
        UUID(sid), tenant_id=tenant.id, user_id=auth_user.id
    )
    assert row is not None
    assert row.last_error is not None
    assert row.last_error.get("error") == "ai_draft_validation"


def test_list_tasks_route_uses_injected_tenant_scope(client, tenant, db_session):
    task = Task(name="Scoped task", template="instagram_post", tenant_id=tenant.id)
    db_session.add(task)
    db_session.commit()

    response = client.get(
        "/api/v1/tasks",
        headers={"X-Tenant-Id": str(tenant.id), "Authorization": "Bearer test"},
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["tasks"][0]["name"] == "Scoped task"
