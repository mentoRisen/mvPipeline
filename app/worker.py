"""Background worker that processes READY jobs in PROCESSING tasks.

Runs as a separate process. Polls the database on a configurable interval,
picks READY jobs whose parent task is PROCESSING, and calls process_job for each.
Process one job per tick; then sleep until the next check.

Usage:
    python -m app.worker

Configuration:
    WORKER_CHECK_INTERVAL_SECONDS  Interval between checks (default: 30).
"""

import logging
import signal
import sys
import time
from typing import Optional

from sqlmodel import Session, select

from app.config import WORKER_CHECK_INTERVAL_SECONDS
from app.db.engine import create_tables, engine
from app.models.job import Job, JobStatus
from app.models.task import Task, TaskStatus
from app.services.jobs.processor import process_job
from app.utils.logging_config import setup_logging

logger = logging.getLogger(__name__)

_shutdown_requested = False


def _on_signal(_signum, _frame):
    global _shutdown_requested
    _shutdown_requested = True


def _fetch_next_ready_job_in_processing_task() -> Optional[Job]:
    """Return one READY job whose parent task is PROCESSING, or None."""
    with Session(engine) as session:
        stmt = (
            select(Job)
            .join(Task, Job.task_id == Task.id)
            .where(
                Job.status == JobStatus.READY,
                Task.status == TaskStatus.PROCESSING,
            )
            .order_by(Job.created_at)
            .limit(1)
        )
        job = session.exec(stmt).first()
        return job


def run_worker():
    """Run the worker loop until shutdown requested."""
    setup_logging()
    logger.info(
        "Worker starting; interval=%s s, processing READY jobs in PROCESSING tasks",
        WORKER_CHECK_INTERVAL_SECONDS,
    )
    create_tables()

    while not _shutdown_requested:
        job = _fetch_next_ready_job_in_processing_task()
        if job:
            try:
                process_job(job)
                logger.info("Worker processed job %s", job.id)
            except Exception as e:
                logger.exception("Worker failed to process job %s: %s", job.id, e)
        else:
            logger.debug("No READY jobs in PROCESSING tasks; sleeping")

        # Sleep in small steps so we can react to shutdown promptly
        slept = 0
        while slept < WORKER_CHECK_INTERVAL_SECONDS and not _shutdown_requested:
            time.sleep(min(1, WORKER_CHECK_INTERVAL_SECONDS - slept))
            slept += 1

    logger.info("Worker shutting down")


def main():
    """Entry point for python -m app.worker."""
    signal.signal(signal.SIGINT, _on_signal)
    signal.signal(signal.SIGTERM, _on_signal)

    try:
        run_worker()
        sys.exit(0)
    except KeyboardInterrupt:
        logger.info("Worker interrupted")
        sys.exit(0)
    except Exception as e:
        logger.exception("Worker exited with error: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
