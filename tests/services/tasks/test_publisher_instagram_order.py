from __future__ import annotations

from datetime import datetime, timedelta

from app.models.job import Job, JobStatus
from app.models.task import Task
from app.services.job_reference_service import list_jobs_for_task_ordered


def test_list_jobs_for_task_ordered_tie_breaks_on_reference_id(db_session):
    task = Task(name="Publish sort", template="instagram_post")
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)

    base = datetime.utcnow()
    later = Job(
        task_id=task.id,
        reference_id=2,
        order=1,
        generator="dalle",
        purpose="imagecontent",
        status=JobStatus.PROCESSED,
        created_at=base + timedelta(seconds=5),
    )
    earlier = Job(
        task_id=task.id,
        reference_id=1,
        order=1,
        generator="dalle",
        purpose="imagecontent",
        status=JobStatus.PROCESSED,
        created_at=base,
    )
    db_session.add(later)
    db_session.add(earlier)
    db_session.commit()

    jobs = list_jobs_for_task_ordered(
        db_session, task.id, purpose="imagecontent"
    )
    assert [job.reference_id for job in jobs] == [1, 2]
