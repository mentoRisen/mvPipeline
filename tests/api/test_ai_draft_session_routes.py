from __future__ import annotations

import json
from uuid import uuid4

from app.api.schemas import AiTaskDraftBundleResponse
from app.services.integrations.llm_text_adapter import OpenAITextDraftAdapter


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


def _mock_llm(monkeypatch, body: dict):
    monkeypatch.setattr(
        OpenAITextDraftAdapter,
        "complete_preview_chat",
        lambda self, m: json.dumps(body),
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
    _mock_llm(monkeypatch, _one_item_bundle().model_dump(mode="json"))
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
    assert body[0]["preview_status"] == "succeeded"


def test_get_draft_session_roundtrip(client, tenant, monkeypatch):
    _mock_llm(monkeypatch, _one_item_bundle().model_dump(mode="json"))
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
    data = r.json()
    assert data["brief"] == "Roundtrip"
    assert len(data["items"]) == 1
    assert data["preview_status"] == "succeeded"
    assert len(data["communication_events"]) >= 3


def test_delete_draft_session(client, tenant, monkeypatch):
    _mock_llm(monkeypatch, _one_item_bundle().model_dump(mode="json"))
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
    _mock_llm(monkeypatch, _one_item_bundle().model_dump(mode="json"))
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
