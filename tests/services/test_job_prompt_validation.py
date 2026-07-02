from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlmodel import Session

from app.models.job import Job, JobStatus
from app.models.task import Task
import app.config as app_config
from app.services.job_prompt_validation import (
    JobPromptValidationError,
    planned_reference_ids,
    resolve_processed_image_slot,
    validate_draft_job_reference_ids,
    validate_image_slot_reference,
    validate_job_prompt_for_write,
    validate_runway_reference_in_draft_jobs,
    validate_runway_video_prompt,
)


def test_validate_runway_video_prompt_happy_path_strips_text():
    result = validate_runway_video_prompt(
        {
            "prompt": "  motion prompt  ",
            "model": "gen4_turbo",
            "reference_id": 1,
        }
    )
    assert result == {
        "prompt": "motion prompt",
        "model": "gen4_turbo",
        "reference_id": 1,
    }


@pytest.mark.parametrize(
    "prompt,field",
    [
        (None, "prompt"),
        ({}, "prompt"),
        ({"prompt": "", "model": "gen4_turbo", "reference_id": 1}, "prompt"),
        (
            {"prompt": "ok", "model": "bad", "reference_id": 1},
            "prompt.model",
        ),
        (
            {"prompt": "ok", "model": "gen4_turbo", "reference_id": 0},
            "prompt.reference_id",
        ),
        (
            {"prompt": "ok", "model": "gen4_turbo", "reference_id": True},
            "prompt.reference_id",
        ),
        (
            {"prompt": "ok", "model": "gen4_turbo"},
            "prompt.reference_id",
        ),
    ],
)
def test_validate_runway_video_prompt_errors(prompt, field):
    with pytest.raises(JobPromptValidationError) as excinfo:
        validate_runway_video_prompt(prompt)
    assert excinfo.value.field == field


def test_validate_image_slot_reference_happy_and_error(db_session: Session):
    task = Task(name="slot task", template="instagram_post")
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)

    image_job = Job(
        task_id=task.id,
        reference_id=1,
        generator="dalle",
        purpose="imagecontent",
        status=JobStatus.NEW,
    )
    video_job = Job(
        task_id=task.id,
        reference_id=2,
        generator="runway-video",
        purpose="videocontent",
        status=JobStatus.NEW,
    )
    db_session.add(image_job)
    db_session.add(video_job)
    db_session.commit()

    validate_image_slot_reference(db_session, task.id, 1)

    with pytest.raises(JobPromptValidationError, match="imagecontent"):
        validate_image_slot_reference(db_session, task.id, 2)

    with pytest.raises(JobPromptValidationError, match="imagecontent"):
        validate_image_slot_reference(db_session, task.id, 3)


def test_validate_job_prompt_for_write_non_runway_passthrough(db_session: Session):
    task = Task(name="passthrough", template="instagram_post")
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)

    prompt = {"prompt": "hello", "extra": True}
    result = validate_job_prompt_for_write(
        db_session,
        task.id,
        generator="dalle",
        purpose="imagecontent",
        prompt=prompt,
    )
    assert result == prompt


def test_validate_job_prompt_for_write_strips_runway_keys_for_image_generator():
    runway_shaped = {
        "prompt": "camera pans slowly",
        "model": "gen4_turbo",
        "reference_id": 1,
    }
    result = validate_job_prompt_for_write(
        None,
        None,
        generator="dalle",
        purpose="imagecontent",
        prompt=runway_shaped,
    )
    assert result == {"prompt": "camera pans slowly"}


def test_validate_job_prompt_for_write_runway_against_db(db_session: Session):
    task = Task(name="runway task", template="instagram_post")
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)

    db_session.add(
        Job(
            task_id=task.id,
            reference_id=1,
            generator="dalle",
            purpose="imagecontent",
            status=JobStatus.NEW,
        )
    )
    db_session.commit()

    normalized = validate_job_prompt_for_write(
        db_session,
        task.id,
        generator="runway-video",
        purpose="videocontent",
        prompt={
            "prompt": "move",
            "model": "veo3.1_fast",
            "reference_id": 1,
        },
    )
    assert normalized["model"] == "veo3.1_fast"

    with pytest.raises(JobPromptValidationError, match="imagecontent"):
        validate_job_prompt_for_write(
            db_session,
            task.id,
            generator="runway-video",
            purpose="videocontent",
            prompt={
                "prompt": "move",
                "model": "veo3.1_fast",
                "reference_id": 2,
            },
        )


def test_validate_runway_reference_in_draft_jobs():
    jobs = [
        SimpleNamespace(
            purpose="imagecontent",
            reference_id=1,
            generator="dalle",
        ),
        SimpleNamespace(
            purpose="videocontent",
            reference_id=2,
            generator="runway-video",
        ),
    ]
    validate_runway_reference_in_draft_jobs(draft_jobs=jobs, image_slot=1)

    with pytest.raises(JobPromptValidationError):
        validate_runway_reference_in_draft_jobs(draft_jobs=jobs, image_slot=2)


def test_validate_runway_reference_in_draft_jobs_uses_explicit_ids_not_array_order():
    jobs = [
        SimpleNamespace(purpose="videocontent", reference_id=2, generator="runway-video"),
        SimpleNamespace(purpose="imagecontent", reference_id=1, generator="dalle"),
    ]
    validate_runway_reference_in_draft_jobs(draft_jobs=jobs, image_slot=1)


def test_validate_draft_job_reference_ids_requires_explicit_unique_slots():
    jobs = [
        SimpleNamespace(reference_id=1),
        SimpleNamespace(reference_id=2),
    ]
    validate_draft_job_reference_ids(jobs)

    with pytest.raises(JobPromptValidationError, match="reference_id"):
        validate_draft_job_reference_ids([SimpleNamespace(reference_id=None)])

    with pytest.raises(JobPromptValidationError, match="duplicate"):
        validate_draft_job_reference_ids(
            [
                SimpleNamespace(reference_id=1),
                SimpleNamespace(reference_id=1),
            ]
        )


def test_planned_reference_ids_auto_fill():
    assert planned_reference_ids([None, None]) == [1, 2]
    assert planned_reference_ids([3, None]) == [3, 4]


def test_validate_job_prompt_for_write_purpose_mismatch():
    with pytest.raises(JobPromptValidationError, match="videocontent"):
        validate_job_prompt_for_write(
            None,
            None,
            generator="dalle",
            purpose="videocontent",
            prompt={"prompt": "x"},
        )

    with pytest.raises(JobPromptValidationError, match="runway-video"):
        validate_job_prompt_for_write(
            None,
            None,
            generator="runway-video",
            purpose="imagecontent",
            prompt={
                "prompt": "x",
                "model": "gen4_turbo",
                "reference_id": 1,
            },
            draft_jobs=[
                SimpleNamespace(purpose="imagecontent", reference_id=1),
            ],
        )


def test_validate_job_prompt_for_write_runway_requires_videocontent_purpose():
    with pytest.raises(JobPromptValidationError) as excinfo:
        validate_job_prompt_for_write(
            None,
            None,
            generator="runway-video",
            purpose=None,
            prompt={
                "prompt": "x",
                "model": "gen4_turbo",
                "reference_id": 1,
            },
            draft_jobs=[
                SimpleNamespace(purpose="imagecontent", reference_id=1),
            ],
        )
    assert excinfo.value.field == "purpose"


def _create_task_with_image_job(
    db_session: Session,
    *,
    status: JobStatus = JobStatus.PROCESSED,
    result: dict | None = None,
    slot: int = 1,
) -> tuple[Task, Job]:
    task = Task(name="slot resolve task", template="instagram_post")
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)

    image_job = Job(
        task_id=task.id,
        reference_id=slot,
        generator="dalle",
        purpose="imagecontent",
        status=status,
        result=result,
    )
    db_session.add(image_job)
    db_session.commit()
    db_session.refresh(image_job)
    return task, image_job


def test_resolve_processed_image_slot_happy_path(
    db_session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(app_config, "OUTPUT_DIR", tmp_path)
    image_file = tmp_path / "task-1" / "job-1.jpeg"
    image_file.parent.mkdir(parents=True)
    image_file.write_bytes(b"fake-jpeg")

    task, _image_job = _create_task_with_image_job(
        db_session,
        result={"image_path": "/output/task-1/job-1.jpeg"},
    )

    matched_job, local_path = resolve_processed_image_slot(db_session, task.id, 1)
    assert matched_job.reference_id == 1
    assert local_path == image_file


def test_resolve_processed_image_slot_not_processed(db_session: Session):
    task, _image_job = _create_task_with_image_job(
        db_session,
        status=JobStatus.READY,
        result={"image_path": "/output/task-1/job-1.jpeg"},
    )

    with pytest.raises(ValueError, match="not processed"):
        resolve_processed_image_slot(db_session, task.id, 1)


def test_resolve_processed_image_slot_no_image_path(db_session: Session):
    task, _image_job = _create_task_with_image_job(
        db_session,
        result={},
    )

    with pytest.raises(ValueError, match="no image path"):
        resolve_processed_image_slot(db_session, task.id, 1)


def test_resolve_processed_image_slot_missing_slot(db_session: Session):
    task = Task(name="empty task", template="instagram_post")
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)

    with pytest.raises(ValueError, match="no imagecontent job"):
        resolve_processed_image_slot(db_session, task.id, 1)
