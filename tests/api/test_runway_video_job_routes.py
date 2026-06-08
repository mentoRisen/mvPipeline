from __future__ import annotations

from tests.api.test_job_reference_id_routes import _create_task, _headers


def _runway_prompt(*, reference_id: int = 1, model: str = "gen4_turbo") -> dict:
    return {
        "prompt": "camera pans slowly",
        "model": model,
        "reference_id": reference_id,
    }


def test_create_runway_video_job_after_imagecontent(client, tenant):
    task_id = _create_task(client, tenant)
    image = client.post(
        f"/api/v1/tasks/{task_id}/jobs",
        headers=_headers(tenant),
        json={"generator": "dalle", "purpose": "imagecontent"},
    )
    assert image.status_code == 201
    assert image.json()["reference_id"] == 1

    response = client.post(
        f"/api/v1/tasks/{task_id}/jobs",
        headers=_headers(tenant),
        json={
            "generator": "runway-video",
            "purpose": "videocontent",
            "prompt": _runway_prompt(reference_id=1),
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["generator"] == "runway-video"
    assert body["purpose"] == "videocontent"
    assert body["prompt"]["model"] == "gen4_turbo"
    assert body["prompt"]["reference_id"] == 1


def test_create_runway_video_without_image_slot_returns_422(client, tenant):
    task_id = _create_task(client, tenant)
    response = client.post(
        f"/api/v1/tasks/{task_id}/jobs",
        headers=_headers(tenant),
        json={
            "generator": "runway-video",
            "purpose": "videocontent",
            "prompt": _runway_prompt(reference_id=1),
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "prompt.reference_id"]


def test_create_runway_video_invalid_model_returns_422(client, tenant):
    task_id = _create_task(client, tenant)
    client.post(
        f"/api/v1/tasks/{task_id}/jobs",
        headers=_headers(tenant),
        json={"generator": "dalle", "purpose": "imagecontent"},
    )
    response = client.post(
        f"/api/v1/tasks/{task_id}/jobs",
        headers=_headers(tenant),
        json={
            "generator": "runway-video",
            "purpose": "videocontent",
            "prompt": _runway_prompt(model="unknown_model"),
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "prompt.model"]


def test_create_runway_video_without_purpose_returns_422(client, tenant):
    task_id = _create_task(client, tenant)
    client.post(
        f"/api/v1/tasks/{task_id}/jobs",
        headers=_headers(tenant),
        json={"generator": "dalle", "purpose": "imagecontent"},
    )
    response = client.post(
        f"/api/v1/tasks/{task_id}/jobs",
        headers=_headers(tenant),
        json={
            "generator": "runway-video",
            "prompt": _runway_prompt(reference_id=1),
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "purpose"]


def test_create_runway_video_boolean_reference_id_returns_422(client, tenant):
    task_id = _create_task(client, tenant)
    client.post(
        f"/api/v1/tasks/{task_id}/jobs",
        headers=_headers(tenant),
        json={"generator": "dalle", "purpose": "imagecontent"},
    )
    response = client.post(
        f"/api/v1/tasks/{task_id}/jobs",
        headers=_headers(tenant),
        json={
            "generator": "runway-video",
            "purpose": "videocontent",
            "prompt": {
                "prompt": "camera pans slowly",
                "model": "gen4_turbo",
                "reference_id": True,
            },
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "prompt.reference_id"]


def test_update_runway_video_model_and_reference(client, tenant):
    task_id = _create_task(client, tenant)
    client.post(
        f"/api/v1/tasks/{task_id}/jobs",
        headers=_headers(tenant),
        json={"generator": "dalle", "purpose": "imagecontent"},
    )
    second_image = client.post(
        f"/api/v1/tasks/{task_id}/jobs",
        headers=_headers(tenant),
        json={"generator": "dalle", "purpose": "imagecontent"},
    )
    assert second_image.json()["reference_id"] == 2

    created = client.post(
        f"/api/v1/tasks/{task_id}/jobs",
        headers=_headers(tenant),
        json={
            "generator": "runway-video",
            "purpose": "videocontent",
            "prompt": _runway_prompt(reference_id=1),
        },
    ).json()

    response = client.put(
        f"/api/v1/tasks/{task_id}/jobs/{created['id']}",
        headers=_headers(tenant),
        json={
            "prompt": _runway_prompt(reference_id=2, model="veo3.1_fast"),
        },
    )
    assert response.status_code == 200
    assert response.json()["prompt"]["model"] == "veo3.1_fast"
    assert response.json()["prompt"]["reference_id"] == 2


def test_update_runway_video_invalid_reference_slot_returns_422(client, tenant):
    task_id = _create_task(client, tenant)
    client.post(
        f"/api/v1/tasks/{task_id}/jobs",
        headers=_headers(tenant),
        json={"generator": "dalle", "purpose": "imagecontent"},
    )
    video_only = client.post(
        f"/api/v1/tasks/{task_id}/jobs",
        headers=_headers(tenant),
        json={
            "generator": "runway-video",
            "purpose": "videocontent",
            "prompt": _runway_prompt(reference_id=1),
        },
    ).json()

    response = client.put(
        f"/api/v1/tasks/{task_id}/jobs/{video_only['id']}",
        headers=_headers(tenant),
        json={"prompt": _runway_prompt(reference_id=2)},
    )
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "prompt.reference_id"]


def test_update_generator_only_runway_to_dalle_strips_runway_prompt_keys(client, tenant):
    task_id = _create_task(client, tenant)
    client.post(
        f"/api/v1/tasks/{task_id}/jobs",
        headers=_headers(tenant),
        json={"generator": "dalle", "purpose": "imagecontent"},
    )
    created = client.post(
        f"/api/v1/tasks/{task_id}/jobs",
        headers=_headers(tenant),
        json={
            "generator": "runway-video",
            "purpose": "videocontent",
            "prompt": _runway_prompt(reference_id=1),
        },
    ).json()

    response = client.put(
        f"/api/v1/tasks/{task_id}/jobs/{created['id']}",
        headers=_headers(tenant),
        json={"generator": "dalle", "purpose": "imagecontent"},
    )
    assert response.status_code == 200
    assert response.json()["prompt"] == {"prompt": "camera pans slowly"}
    assert "model" not in response.json()["prompt"]
    assert "reference_id" not in response.json()["prompt"]


def test_dalle_job_still_accepts_prompt_only(client, tenant):
    task_id = _create_task(client, tenant)
    response = client.post(
        f"/api/v1/tasks/{task_id}/jobs",
        headers=_headers(tenant),
        json={
            "generator": "dalle",
            "purpose": "imagecontent",
            "prompt": {"prompt": "still life"},
        },
    )
    assert response.status_code == 201
    assert response.json()["prompt"] == {"prompt": "still life"}
