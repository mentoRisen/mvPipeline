from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from sqlmodel import Session

from app.models.job import Job, JobStatus
from app.models.task import Task
from app.services.job_reference_service import (
    JobReferenceValidationError,
    assign_reference_ids_for_new_jobs,
    resolve_reference_id,
)


def _task(db_session: Session) -> Task:
    task = Task(name="Ref task", template="instagram_post")
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)
    return task


def _job(
    db_session: Session,
    task: Task,
    *,
    reference_id: int,
    created_at: datetime | None = None,
) -> Job:
    job = Job(
        task_id=task.id,
        reference_id=reference_id,
        generator="dalle",
        purpose="imagecontent",
        order=0,
        status=JobStatus.NEW,
    )
    if created_at is not None:
        job.created_at = created_at
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    return job


def test_resolve_empty_task_omitted_returns_one(db_session: Session):
    task = _task(db_session)
    ref = resolve_reference_id(db_session, task.id, None)
    assert ref == 1


def test_resolve_omitted_after_existing_returns_max_plus_one(db_session: Session):
    task = _task(db_session)
    _job(db_session, task, reference_id=1)
    _job(db_session, task, reference_id=3)
    ref = resolve_reference_id(db_session, task.id, None)
    assert ref == 4


def test_resolve_explicit_unused(db_session: Session):
    task = _task(db_session)
    _job(db_session, task, reference_id=1)
    ref = resolve_reference_id(db_session, task.id, 2)
    assert ref == 2


def test_resolve_explicit_conflict_raises(db_session: Session):
    task = _task(db_session)
    _job(db_session, task, reference_id=2)
    with pytest.raises(JobReferenceValidationError, match="already in use"):
        resolve_reference_id(db_session, task.id, 2)


def test_resolve_explicit_invalid_raises(db_session: Session):
    task = _task(db_session)
    with pytest.raises(JobReferenceValidationError, match=">= 1"):
        resolve_reference_id(db_session, task.id, 0)


def test_batch_three_omitted_sequential(db_session: Session):
    task = _task(db_session)
    assigned = assign_reference_ids_for_new_jobs(
        db_session, task.id, [None, None, None]
    )
    assert assigned == [1, 2, 3]


def test_batch_two_explicit_same_raises(db_session: Session):
    task = _task(db_session)
    with pytest.raises(JobReferenceValidationError, match="duplicate"):
        assign_reference_ids_for_new_jobs(db_session, task.id, [1, 1])


def test_batch_explicit_conflict_with_db_raises(db_session: Session):
    task = _task(db_session)
    _job(db_session, task, reference_id=2)
    with pytest.raises(JobReferenceValidationError, match="already in use"):
        assign_reference_ids_for_new_jobs(db_session, task.id, [2])


def test_batch_continues_after_existing_max(db_session: Session):
    task = _task(db_session)
    _job(db_session, task, reference_id=5)
    assigned = assign_reference_ids_for_new_jobs(
        db_session, task.id, [None, None]
    )
    assert assigned == [6, 7]


def test_batch_explicit_then_auto_continues_after_explicit(db_session: Session):
    task = _task(db_session)
    assigned = assign_reference_ids_for_new_jobs(
        db_session, task.id, [3, None, None]
    )
    assert assigned == [3, 4, 5]


def test_batch_explicit_negative_raises(db_session: Session):
    task = _task(db_session)
    with pytest.raises(JobReferenceValidationError, match=">= 1"):
        assign_reference_ids_for_new_jobs(db_session, task.id, [-1])
