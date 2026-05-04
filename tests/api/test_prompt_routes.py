from __future__ import annotations

from uuid import uuid4

from app.models.tenant import Tenant


def _headers(tenant_id):
    return {
        "X-Tenant-Id": str(tenant_id),
        "Authorization": "Bearer test",
    }


def test_prompt_crud_happy_path(client, tenant):
    h = _headers(tenant.id)
    create = client.post(
        "/api/v1/prompts",
        headers=h,
        json={
            "name": "  Brief one  ",
            "type": "task-creation",
            "body": "Do the thing",
        },
    )
    assert create.status_code == 201
    body = create.json()
    pid = body["id"]
    assert body["name"] == "Brief one"
    assert body["type"] == "task-creation"
    assert body["body"] == "Do the thing"

    lst = client.get("/api/v1/prompts", headers=h)
    assert lst.status_code == 200
    rows = lst.json()
    assert len(rows) == 1
    assert rows[0]["id"] == pid
    assert rows[0]["body_preview"] == "Do the thing"

    one = client.get(f"/api/v1/prompts/{pid}", headers=h)
    assert one.status_code == 200
    assert one.json()["body"] == "Do the thing"

    upd = client.put(
        f"/api/v1/prompts/{pid}",
        headers=h,
        json={"body": "Updated body"},
    )
    assert upd.status_code == 200
    assert upd.json()["body"] == "Updated body"

    delete = client.delete(f"/api/v1/prompts/{pid}", headers=h)
    assert delete.status_code == 204

    missing = client.get(f"/api/v1/prompts/{pid}", headers=h)
    assert missing.status_code == 404


def test_prompt_wrong_tenant_404(client, tenant, db_session):
    other = Tenant(name="Other org")
    db_session.add(other)
    db_session.commit()
    db_session.refresh(other)

    h_a = _headers(tenant.id)
    create = client.post(
        "/api/v1/prompts",
        headers=h_a,
        json={"name": "Secret", "type": "task-creation", "body": "x"},
    )
    assert create.status_code == 201
    pid = create.json()["id"]

    h_b = _headers(other.id)
    assert client.get(f"/api/v1/prompts/{pid}", headers=h_b).status_code == 404
    assert (
        client.put(
            f"/api/v1/prompts/{pid}",
            headers=h_b,
            json={"name": "y"},
        ).status_code
        == 404
    )
    assert client.delete(f"/api/v1/prompts/{pid}", headers=h_b).status_code == 404


def test_prompt_create_empty_name_422(client, tenant):
    r = client.post(
        "/api/v1/prompts",
        headers=_headers(tenant.id),
        json={"name": "   ", "type": "task-creation", "body": "x"},
    )
    assert r.status_code == 422


def test_prompt_create_unknown_type_422(client, tenant):
    r = client.post(
        "/api/v1/prompts",
        headers=_headers(tenant.id),
        json={"name": "a", "type": "not-a-real-type", "body": "x"},
    )
    assert r.status_code == 422


def test_prompt_create_master_prompt_type_201(client, tenant):
    r = client.post(
        "/api/v1/prompts",
        headers=_headers(tenant.id),
        json={"name": "Master baseline", "type": "master-prompt", "body": "x"},
    )
    assert r.status_code == 201
    assert r.json()["type"] == "master-prompt"


def test_prompt_update_empty_payload_422(client, tenant):
    create = client.post(
        "/api/v1/prompts",
        headers=_headers(tenant.id),
        json={"name": "a", "type": "task-creation", "body": "x"},
    )
    pid = create.json()["id"]
    r = client.put(
        f"/api/v1/prompts/{pid}",
        headers=_headers(tenant.id),
        json={},
    )
    assert r.status_code == 422


def test_prompt_get_unknown_404(client, tenant):
    r = client.get(
        f"/api/v1/prompts/{uuid4()}",
        headers=_headers(tenant.id),
    )
    assert r.status_code == 404
