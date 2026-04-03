from __future__ import annotations

from app.api.schemas import AiTaskDraftConfirmRequest
from app.api.schemas import AiTaskDraftResponse
from app.models.task import Task
from app.services.ai_task_draft_service import AiTaskDraftValidationError
from app.services.integrations.llm_text_adapter import (
    TextDraftRefusalError,
    TextDraftUpstreamError,
)
from sqlalchemy.exc import IntegrityError


class StubDraftService:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def generate_preview(self, *, brief, tenant):
        self.calls.append({"brief": brief, "tenant_id": tenant.id})
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class StubConfirmService:
    def __init__(self, result):
        self.result = result

    def confirm_preview(self, *, draft, tenant):
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def test_ai_draft_preview_route_returns_preview(client, tenant, monkeypatch):
    service = StubDraftService(
        AiTaskDraftResponse.model_validate(
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
        )
    )
    monkeypatch.setattr(
        "app.api.routes.get_ai_task_draft_service",
        lambda: service,
    )
    monkeypatch.setattr("app.api.routes.current_tenant", lambda: tenant)

    response = client.post(
        "/api/v1/tasks/ai-draft-preview",
        headers={"X-Tenant-Id": str(tenant.id), "Authorization": "Bearer test"},
        json={"brief": "Create a launch post"},
    )

    assert response.status_code == 200
    assert response.json()["task"]["template"] == "instagram_post"
    assert service.calls[0]["tenant_id"] == tenant.id


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
        "app.api.routes.get_ai_task_draft_service",
        lambda: StubDraftService(
            AiTaskDraftValidationError(
                "AI draft preview returned invalid structured data"
            )
        ),
    )
    monkeypatch.setattr("app.api.routes.current_tenant", lambda: tenant)

    response = client.post(
        "/api/v1/tasks/ai-draft-preview",
        headers={"X-Tenant-Id": str(tenant.id), "Authorization": "Bearer test"},
        json={"brief": "Create a launch post"},
    )

    assert response.status_code == 422


def test_ai_draft_preview_route_maps_refusals(client, tenant, monkeypatch):
    monkeypatch.setattr(
        "app.api.routes.get_ai_task_draft_service",
        lambda: StubDraftService(TextDraftRefusalError("AI draft preview was refused")),
    )
    monkeypatch.setattr("app.api.routes.current_tenant", lambda: tenant)

    response = client.post(
        "/api/v1/tasks/ai-draft-preview",
        headers={"X-Tenant-Id": str(tenant.id), "Authorization": "Bearer test"},
        json={"brief": "Create a launch post"},
    )

    assert response.status_code == 422


def test_ai_draft_preview_route_maps_upstream_failures(client, tenant, monkeypatch):
    monkeypatch.setattr(
        "app.api.routes.get_ai_task_draft_service",
        lambda: StubDraftService(
            TextDraftUpstreamError("AI draft preview request failed")
        ),
    )
    monkeypatch.setattr("app.api.routes.current_tenant", lambda: tenant)

    response = client.post(
        "/api/v1/tasks/ai-draft-preview",
        headers={"X-Tenant-Id": str(tenant.id), "Authorization": "Bearer test"},
        json={"brief": "Create a launch post"},
    )

    assert response.status_code == 502


def test_ai_draft_confirm_route_creates_task_and_jobs(client, tenant, monkeypatch):
    task = Task(name="Launch post", template="instagram_post", tenant_id=tenant.id)
    monkeypatch.setattr(
        "app.api.routes.get_ai_task_draft_service",
        lambda: StubConfirmService(task),
    )
    monkeypatch.setattr("app.api.routes.current_tenant", lambda: tenant)

    response = client.post(
        "/api/v1/tasks/ai-draft-confirm",
        headers={"X-Tenant-Id": str(tenant.id), "Authorization": "Bearer test"},
        json=AiTaskDraftConfirmRequest.model_validate(
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
        ).model_dump(),
    )

    assert response.status_code == 201
    assert response.json()["tenant_id"] == str(tenant.id)


def test_ai_draft_confirm_route_rejects_tenant_fields_in_body(client, tenant, monkeypatch):
    monkeypatch.setattr(
        "app.api.routes.get_ai_task_draft_service",
        lambda: StubConfirmService(Task(name="Launch post", template="instagram_post", tenant_id=tenant.id)),
    )
    monkeypatch.setattr("app.api.routes.current_tenant", lambda: tenant)

    response = client.post(
        "/api/v1/tasks/ai-draft-confirm",
        headers={"X-Tenant-Id": str(tenant.id), "Authorization": "Bearer test"},
        json={
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
        json=AiTaskDraftConfirmRequest.model_validate(
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
        json=AiTaskDraftConfirmRequest.model_validate(
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
