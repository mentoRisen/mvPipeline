from __future__ import annotations

import pytest
from sqlmodel import Session

from app.models.job import Job, JobStatus
from app.models.task import Task, TaskStatus
from app.services.jobs import processor as job_processor


def _create_task_and_job(*, db_session: Session, generator: str) -> Job:
    task = Task(
        name="Image task",
        template="instagram_post",
        status=TaskStatus.PROCESSING,
    )
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)

    job = Job(
        task_id=task.id,
        status=JobStatus.READY,
        generator=generator,
        purpose="imagecontent",
        prompt={"prompt": "A cinematic product photo"},
        order=0,
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    return job


def _load_job(*, test_engine, job_id):
    with Session(test_engine) as session:
        return session.get(Job, job_id)


def test_process_job_gptimage2_happy_path_updates_result(
    db_session: Session,
    test_engine,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(job_processor, "engine", test_engine)
    monkeypatch.setattr(
        "app.services.jobs.processor_gptimage2.generate_image",
        lambda **kwargs: "/output/task-1/job-1.jpeg",
    )
    monkeypatch.setattr(
        job_processor,
        "uploadToPublic",
        lambda path: f"https://public.example{path}",
    )
    job = _create_task_and_job(db_session=db_session, generator="GptImage2")

    job_processor.process_job(job)

    stored_job = _load_job(test_engine=test_engine, job_id=job.id)
    assert stored_job is not None
    assert stored_job.status == JobStatus.PROCESSED
    assert stored_job.result["image_path"] == "/output/task-1/job-1.jpeg"
    assert stored_job.result["generator"] == "gptimage2"
    assert stored_job.result["public_url"] == "https://public.example/output/task-1/job-1.jpeg"


def test_process_job_gptimage2_error_marks_job_error(
    db_session: Session,
    test_engine,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(job_processor, "engine", test_engine)

    def _raise_error(**kwargs):
        raise RuntimeError("upstream image generation failed")

    monkeypatch.setattr("app.services.jobs.processor_gptimage2.generate_image", _raise_error)
    job = _create_task_and_job(db_session=db_session, generator="gptimage2")

    with pytest.raises(RuntimeError, match="upstream image generation failed"):
        job_processor.process_job(job)

    stored_job = _load_job(test_engine=test_engine, job_id=job.id)
    assert stored_job is not None
    assert stored_job.status == JobStatus.ERROR
    assert "upstream image generation failed" in stored_job.result["error"]


def test_process_job_unknown_generator_still_errors(
    db_session: Session,
    test_engine,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(job_processor, "engine", test_engine)
    job = _create_task_and_job(db_session=db_session, generator="gptimage3")

    with pytest.raises(ValueError, match="Unknown generator type: gptimage3"):
        job_processor.process_job(job)

    stored_job = _load_job(test_engine=test_engine, job_id=job.id)
    assert stored_job is not None
    assert stored_job.status == JobStatus.ERROR
