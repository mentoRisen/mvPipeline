from __future__ import annotations

from uuid import uuid4

from app.api.schemas import AiTaskDraftBundleResponse


class StubDraftService:
    def __init__(self, result):
        self.result = result

    def generate_preview(self, *, brief, tenant):
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def _one_item_bundle() -> AiTaskDraftBundleResponse:
    return AiTaskDraftBundleResponse.model_validate(
        {
            "items": [
                {
                    "task": {
                        "name": "One",
                        "template": "instagram_post",
                        "meta": {},
                        "post": {"caption": "Hi"},
                    },
                    "jobs": [
                        {
                            "generator": "dalle",
                            "purpose": "imagecontent",
                            "prompt": {"prompt": "x"},
                            "order": 0,
                        }
                    ],
                }
            ]
        }
    )


def test_list_draft_sessions_empty(client, tenant, monkeypatch):
    monkeypatch.setattr("app.api.routes.current_tenant", lambda: tenant)
    r = client.get(
        "/api/v1/tasks/ai-draft-sessions",
        headers={"X-Tenant-Id": str(tenant.id), "Authorization": "Bearer test"},
    )
    assert r.status_code == 200
    assert r.json() == []


def test_list_draft_sessions_after_preview(client, tenant, monkeypatch):
    monkeypatch.setattr(
        "app.api.routes.get_ai_task_draft_service",
        lambda: StubDraftService(_one_item_bundle()),
    )
    monkeypatch.setattr("app.api.routes.current_tenant", lambda: tenant)
    client.post(
        "/api/v1/tasks/ai-draft-preview",
        headers={"X-Tenant-Id": str(tenant.id), "Authorization": "Bearer test"},
        json={"brief": "Brief text"},
    )
    r = client.get(
        "/api/v1/tasks/ai-draft-sessions",
        headers={"X-Tenant-Id": str(tenant.id), "Authorization": "Bearer test"},
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["brief"] == "Brief text"
    assert body[0]["item_count"] == 1


def test_get_draft_session_roundtrip(client, tenant, monkeypatch):
    monkeypatch.setattr(
        "app.api.routes.get_ai_task_draft_service",
        lambda: StubDraftService(_one_item_bundle()),
    )
    monkeypatch.setattr("app.api.routes.current_tenant", lambda: tenant)
    prev = client.post(
        "/api/v1/tasks/ai-draft-preview",
        headers={"X-Tenant-Id": str(tenant.id), "Authorization": "Bearer test"},
        json={"brief": "Roundtrip"},
    )
    sid = prev.json()["draft_session_id"]
    r = client.get(
        f"/api/v1/tasks/ai-draft-sessions/{sid}",
        headers={"X-Tenant-Id": str(tenant.id), "Authorization": "Bearer test"},
    )
    assert r.status_code == 200
    assert r.json()["brief"] == "Roundtrip"
    assert len(r.json()["items"]) == 1


def test_delete_draft_session(client, tenant, monkeypatch):
    monkeypatch.setattr(
        "app.api.routes.get_ai_task_draft_service",
        lambda: StubDraftService(_one_item_bundle()),
    )
    monkeypatch.setattr("app.api.routes.current_tenant", lambda: tenant)
    prev = client.post(
        "/api/v1/tasks/ai-draft-preview",
        headers={"X-Tenant-Id": str(tenant.id), "Authorization": "Bearer test"},
        json={"brief": "To discard"},
    )
    sid = prev.json()["draft_session_id"]
    d = client.delete(
        f"/api/v1/tasks/ai-draft-sessions/{sid}",
        headers={"X-Tenant-Id": str(tenant.id), "Authorization": "Bearer test"},
    )
    assert d.status_code == 204
    g = client.get(
        f"/api/v1/tasks/ai-draft-sessions/{sid}",
        headers={"X-Tenant-Id": str(tenant.id), "Authorization": "Bearer test"},
    )
    assert g.status_code == 404


def test_patch_draft_session_updates_brief(client, tenant, monkeypatch):
    monkeypatch.setattr(
        "app.api.routes.get_ai_task_draft_service",
        lambda: StubDraftService(_one_item_bundle()),
    )
    monkeypatch.setattr("app.api.routes.current_tenant", lambda: tenant)
    prev = client.post(
        "/api/v1/tasks/ai-draft-preview",
        headers={"X-Tenant-Id": str(tenant.id), "Authorization": "Bearer test"},
        json={"brief": "Original"},
    )
    sid = prev.json()["draft_session_id"]
    r = client.patch(
        f"/api/v1/tasks/ai-draft-sessions/{sid}",
        headers={"X-Tenant-Id": str(tenant.id), "Authorization": "Bearer test"},
        json={"brief": "Patched brief"},
    )
    assert r.status_code == 200
    assert r.json()["brief"] == "Patched brief"


def test_get_unknown_session_returns_404(client, tenant, monkeypatch):
    monkeypatch.setattr("app.api.routes.current_tenant", lambda: tenant)
    r = client.get(
        f"/api/v1/tasks/ai-draft-sessions/{uuid4()}",
        headers={"X-Tenant-Id": str(tenant.id), "Authorization": "Bearer test"},
    )
    assert r.status_code == 404
