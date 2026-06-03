from __future__ import annotations

from datetime import datetime, timedelta

from sqlmodel import Session

from app.models.job import Job, JobStatus
from app.models.task import Task


def _headers(tenant) -> dict[str, str]:
    return {"X-Tenant-Id": str(tenant.id), "Authorization": "Bearer test"}


def _create_task(client, tenant) -> str:
    response = client.post(
        "/api/v1/tasks",
        headers=_headers(tenant),
        json={"name": "Ref route task", "template": "instagram_post"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_create_job_auto_assigns_reference_id(client, tenant):
    task_id = _create_task(client, tenant)
    response = client.post(
        f"/api/v1/tasks/{task_id}/jobs",
        headers=_headers(tenant),
        json={"generator": "dalle", "purpose": "imagecontent"},
    )
    assert response.status_code == 201
    assert response.json()["reference_id"] == 1


def test_create_job_explicit_unused(client, tenant):
    task_id = _create_task(client, tenant)
    first = client.post(
        f"/api/v1/tasks/{task_id}/jobs",
        headers=_headers(tenant),
        json={"generator": "dalle", "purpose": "imagecontent"},
    )
    assert first.status_code == 201

    second = client.post(
        f"/api/v1/tasks/{task_id}/jobs",
        headers=_headers(tenant),
        json={
            "generator": "dalle",
            "purpose": "imagecontent",
            "reference_id": 3,
        },
    )
    assert second.status_code == 201
    body = second.json()
    assert body["reference_id"] == 3
    assert body["order"] == 0


def test_create_job_duplicate_explicit_returns_422(client, tenant):
    task_id = _create_task(client, tenant)
    client.post(
        f"/api/v1/tasks/{task_id}/jobs",
        headers=_headers(tenant),
        json={"generator": "dalle", "reference_id": 2},
    )
    response = client.post(
        f"/api/v1/tasks/{task_id}/jobs",
        headers=_headers(tenant),
        json={"generator": "dalle", "reference_id": 2},
    )
    assert response.status_code == 422


def test_update_job_rejects_reference_id(client, tenant):
    task_id = _create_task(client, tenant)
    created = client.post(
        f"/api/v1/tasks/{task_id}/jobs",
        headers=_headers(tenant),
        json={"generator": "dalle"},
    ).json()
    response = client.put(
        f"/api/v1/tasks/{task_id}/jobs/{created['id']}",
        headers=_headers(tenant),
        json={"reference_id": 99},
    )
    assert response.status_code == 422


def test_get_task_orders_by_reference_id_when_order_ties(
    client, tenant, db_session: Session
):
    task = Task(
        name="Sort task",
        template="instagram_post",
        tenant_id=tenant.id,
    )
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)

    base = datetime.utcnow()
    j1 = Job(
        task_id=task.id,
        reference_id=2,
        order=5,
        generator="dalle",
        status=JobStatus.NEW,
        created_at=base + timedelta(seconds=10),
    )
    j2 = Job(
        task_id=task.id,
        reference_id=1,
        order=5,
        generator="dalle",
        status=JobStatus.NEW,
        created_at=base,
    )
    db_session.add(j1)
    db_session.add(j2)
    db_session.commit()

    response = client.get(
        f"/api/v1/tasks/{task.id}",
        headers=_headers(tenant),
    )
    assert response.status_code == 200
    job_ids = [j["id"] for j in response.json()["jobs"]]
    assert job_ids == [str(j2.id), str(j1.id)]
