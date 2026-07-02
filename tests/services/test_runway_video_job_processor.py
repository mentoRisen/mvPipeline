from __future__ import annotations

from pathlib import Path

import pytest
from sqlmodel import Session

import app.config as app_config
import app.services.tenant_repo as tenant_repo
from app.context import init_context_by_tenant, reset_tenant_context
from app.models.job import Job, JobStatus
from app.models.task import Task, TaskStatus
from app.services.jobs import processor as job_processor


def _create_runway_task(
    *,
    db_session: Session,
    tenant_id,
    image_status: JobStatus = JobStatus.PROCESSED,
    image_result: dict | None = None,
    runway_status: JobStatus = JobStatus.READY,
) -> tuple[Task, Job, Job]:
    task = Task(
        name="Runway task",
        template="instagram_post",
        status=TaskStatus.PROCESSING,
        tenant_id=tenant_id,
    )
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)

    image_job = Job(
        task_id=task.id,
        reference_id=1,
        status=image_status,
        generator="dalle",
        purpose="imagecontent",
        prompt={"prompt": "still image"},
        result=image_result,
        order=0,
    )
    runway_job = Job(
        task_id=task.id,
        reference_id=2,
        status=runway_status,
        generator="runway-video",
        purpose="videocontent",
        prompt={
            "prompt": "camera pans slowly",
            "model": "gen4_turbo",
            "reference_id": 1,
        },
        order=1,
    )
    db_session.add(image_job)
    db_session.add(runway_job)
    db_session.commit()
    db_session.refresh(image_job)
    db_session.refresh(runway_job)
    return task, image_job, runway_job


def _load_job(*, test_engine, job_id):
    with Session(test_engine) as session:
        return session.get(Job, job_id)


def _load_task(*, test_engine, task_id):
    with Session(test_engine) as session:
        return session.get(Task, task_id)


@pytest.fixture(autouse=True)
def _reset_tenant_context():
    yield
    reset_tenant_context()


def test_process_runway_video_happy_path(
    db_session: Session,
    test_engine,
    tenant,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(job_processor, "engine", test_engine)
    monkeypatch.setattr(tenant_repo, "engine", test_engine)
    monkeypatch.setattr(app_config, "OUTPUT_DIR", tmp_path)
    monkeypatch.setenv("RUNWAY_API_KEY", "global-runway-key")
    monkeypatch.setenv("PUBLIC_URL", "https://public.example")

    task, image_job, runway_job = _create_runway_task(
        db_session=db_session,
        tenant_id=tenant.id,
        image_result=None,
    )
    image_result_path = f"/output/{task.id}/image.jpeg"
    image_file = tmp_path / str(task.id) / "image.jpeg"
    image_file.parent.mkdir(parents=True, exist_ok=True)
    image_file.write_bytes(b"fake-jpeg")
    image_job.result = {"image_path": image_result_path}
    db_session.add(image_job)
    db_session.commit()

    init_context_by_tenant(tenant.id, apply_env=False)

    monkeypatch.setattr(
        "app.services.jobs.processor_runway_video.generate_video",
        lambda **kwargs: {
            "video_path": f"/output/{task.id}/{runway_job.id}.mp4",
            "runway_task_id": "rw-1",
        },
    )

    job_processor.process_job(runway_job)

    stored_job = _load_job(test_engine=test_engine, job_id=runway_job.id)
    assert stored_job is not None
    assert stored_job.status == JobStatus.PROCESSED
    assert stored_job.result["video_path"] == f"/output/{task.id}/{runway_job.id}.mp4"
    assert stored_job.result["generator"] == "runway-video"
    assert (
        stored_job.result["public_url"]
        == f"https://public.example/output/{task.id}/{runway_job.id}.mp4"
    )


def test_process_runway_video_image_not_processed_marks_error(
    db_session: Session,
    test_engine,
    tenant,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(job_processor, "engine", test_engine)
    monkeypatch.setattr(tenant_repo, "engine", test_engine)
    monkeypatch.setenv("RUNWAY_API_KEY", "global-runway-key")

    task, _image_job, runway_job = _create_runway_task(
        db_session=db_session,
        tenant_id=tenant.id,
        image_status=JobStatus.READY,
        image_result={"image_path": "/output/task/image.jpeg"},
    )
    init_context_by_tenant(tenant.id, apply_env=False)

    adapter_called = {"value": False}

    def _should_not_call(**kwargs):
        adapter_called["value"] = True
        return {}

    monkeypatch.setattr(
        "app.services.jobs.processor_runway_video.generate_video",
        _should_not_call,
    )

    with pytest.raises(ValueError, match="not processed"):
        job_processor.process_job(runway_job)

    assert adapter_called["value"] is False
    stored_job = _load_job(test_engine=test_engine, job_id=runway_job.id)
    assert stored_job.status == JobStatus.ERROR


def test_process_runway_video_missing_api_key_marks_error(
    db_session: Session,
    test_engine,
    tenant,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(job_processor, "engine", test_engine)
    monkeypatch.setattr(tenant_repo, "engine", test_engine)
    monkeypatch.setattr(app_config, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(app_config, "RUNWAY_API_KEY", None)
    monkeypatch.delenv("RUNWAY_API_KEY", raising=False)

    task, image_job, runway_job = _create_runway_task(
        db_session=db_session,
        tenant_id=tenant.id,
        image_result=None,
    )
    image_result_path = f"/output/{task.id}/image.jpeg"
    image_file = tmp_path / str(task.id) / "image.jpeg"
    image_file.parent.mkdir(parents=True, exist_ok=True)
    image_file.write_bytes(b"fake-jpeg")
    image_job.result = {"image_path": image_result_path}
    db_session.add(image_job)
    db_session.commit()

    init_context_by_tenant(tenant.id, apply_env=False)

    adapter_called = {"value": False}

    def _should_not_call(**kwargs):
        adapter_called["value"] = True
        return {}

    monkeypatch.setattr(
        "app.services.jobs.processor_runway_video.generate_video",
        _should_not_call,
    )

    with pytest.raises(ValueError, match="RUNWAY_API_KEY not set"):
        job_processor.process_job(runway_job)

    assert adapter_called["value"] is False
    stored_job = _load_job(test_engine=test_engine, job_id=runway_job.id)
    assert stored_job.status == JobStatus.ERROR


def test_process_runway_video_mixed_task_moves_to_pending_confirmation(
    db_session: Session,
    test_engine,
    tenant,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(job_processor, "engine", test_engine)
    monkeypatch.setattr(tenant_repo, "engine", test_engine)
    monkeypatch.setattr(app_config, "OUTPUT_DIR", tmp_path)
    monkeypatch.setenv("RUNWAY_API_KEY", "global-runway-key")

    task, image_job, runway_job = _create_runway_task(
        db_session=db_session,
        tenant_id=tenant.id,
        image_result=None,
    )
    image_result_path = f"/output/{task.id}/image.jpeg"
    image_file = tmp_path / str(task.id) / "image.jpeg"
    image_file.parent.mkdir(parents=True, exist_ok=True)
    image_file.write_bytes(b"fake-jpeg")
    image_job.result = {"image_path": image_result_path}
    db_session.add(image_job)
    db_session.commit()

    init_context_by_tenant(tenant.id, apply_env=False)
    monkeypatch.setattr(
        "app.services.jobs.processor_runway_video.generate_video",
        lambda **kwargs: {
            "video_path": f"/output/{task.id}/{runway_job.id}.mp4",
        },
    )

    job_processor.process_job(runway_job)

    stored_task = _load_task(test_engine=test_engine, task_id=task.id)
    assert stored_task.status == TaskStatus.PENDING_CONFIRMATION


def test_process_runway_video_adapter_error_marks_job_error(
    db_session: Session,
    test_engine,
    tenant,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(job_processor, "engine", test_engine)
    monkeypatch.setattr(tenant_repo, "engine", test_engine)
    monkeypatch.setattr(app_config, "OUTPUT_DIR", tmp_path)
    monkeypatch.setenv("RUNWAY_API_KEY", "global-runway-key")

    task, image_job, runway_job = _create_runway_task(
        db_session=db_session,
        tenant_id=tenant.id,
        image_result=None,
    )
    image_result_path = f"/output/{task.id}/image.jpeg"
    image_file = tmp_path / str(task.id) / "image.jpeg"
    image_file.parent.mkdir(parents=True, exist_ok=True)
    image_file.write_bytes(b"fake-jpeg")
    image_job.result = {"image_path": image_result_path}
    db_session.add(image_job)
    db_session.commit()

    init_context_by_tenant(tenant.id, apply_env=False)

    def _raise_error(**kwargs):
        raise RuntimeError("upstream runway failed")

    monkeypatch.setattr(
        "app.services.jobs.processor_runway_video.generate_video",
        _raise_error,
    )

    with pytest.raises(RuntimeError, match="upstream runway failed"):
        job_processor.process_job(runway_job)

    stored_job = _load_job(test_engine=test_engine, job_id=runway_job.id)
    assert stored_job.status == JobStatus.ERROR
    assert "upstream runway failed" in stored_job.result["error"]
