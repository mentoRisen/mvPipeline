"""Background worker that processes READY jobs and scheduler for a single tenant.

Run one worker process per tenant. Polls the database on a configurable interval,
picks READY jobs whose parent task is PROCESSING and belongs to this tenant,
and runs the scheduler (schedule rules) about every 1 minute.

Usage:
    python -m app.worker --tenant-id=<UUID>
    # or set WORKER_TENANT_ID in environment

Configuration:
    WORKER_TENANT_ID                Tenant UUID (env). Required if --tenant-id not set.
    WORKER_CHECK_INTERVAL_SECONDS   Interval between job checks (default: 30).
    SCHEDULER_CHECK_INTERVAL_SECONDS  Interval between scheduler runs (default: 60 = 1 min).
"""

import logging
import os
import signal
import sys
import time
from typing import Optional
from uuid import UUID

from sqlmodel import Session, select

from app.config import SCHEDULER_CHECK_INTERVAL_SECONDS, WORKER_CHECK_INTERVAL_SECONDS
from app.context import get_tenant, init_context_by_tenant
from app.db.engine import create_tables, engine
from app.models.job import Job, JobStatus
from app.models.task import Task, TaskStatus
from app.services.jobs.processor import process_job
from app.services.scheduler import run_worker as run_scheduler
from app.services import tenant_repo
from app.utils.logging_config import setup_logging

logger = logging.getLogger(__name__)

_shutdown_requested = False


def _on_signal(_signum, _frame):
    global _shutdown_requested
    _shutdown_requested = True


def _get_tenant_id_from_env_or_args() -> UUID:
    """Resolve tenant ID from WORKER_TENANT_ID env or --tenant-id CLI. Raises if missing/invalid."""
    tenant_id_str = os.getenv("WORKER_TENANT_ID")
    if not tenant_id_str and len(sys.argv) > 1:
        for arg in sys.argv[1:]:
            if arg.startswith("--tenant-id="):
                tenant_id_str = arg.split("=", 1)[1].strip()
                break
    if not tenant_id_str:
        raise SystemExit(
            "Tenant required. Set WORKER_TENANT_ID or pass --tenant-id=<UUID>. "
            "Run one worker per tenant."
        )
    try:
        return UUID(tenant_id_str)
    except ValueError as e:
        raise SystemExit(f"Invalid tenant UUID: {tenant_id_str}") from e


def _fetch_next_ready_job_in_processing_task() -> Optional[Job]:
    """Return one READY job whose parent task is PROCESSING and belongs to current tenant, or None."""
    tenant = get_tenant()
    with Session(engine) as session:
        stmt = (
            select(Job)
            .join(Task, Job.task_id == Task.id)
            .where(
                Job.status == JobStatus.READY,
                Task.status == TaskStatus.PROCESSING,
                Task.tenant_id == tenant.id,
            )
            .order_by(Job.created_at)
            .limit(1)
        )
        job = session.exec(stmt).first()
        return job


def run_worker():
    """Run the worker loop for the current tenant (context must be initialized)."""
    setup_logging()
    tenant = get_tenant()
    logger.info(
        "Worker starting for tenant %s (%s); job interval=%s s, scheduler interval=%s s",
        tenant.id,
        tenant.name,
        WORKER_CHECK_INTERVAL_SECONDS,
        SCHEDULER_CHECK_INTERVAL_SECONDS,
    )
    create_tables()

    last_scheduler_run = 0.0

    while not _shutdown_requested:
        job = _fetch_next_ready_job_in_processing_task()
        if job:
            try:
                process_job(job)
                logger.info("Worker processed job %s", job.id)
            except Exception as e:
                logger.exception("Worker failed to process job %s: %s", job.id, e)
        else:
            logger.debug("No READY jobs in PROCESSING tasks for this tenant; sleeping")

        # Run scheduler about every SCHEDULER_CHECK_INTERVAL_SECONDS (e.g. 1 min)
        now = time.time()
        if now - last_scheduler_run >= SCHEDULER_CHECK_INTERVAL_SECONDS:
            try:
                run_scheduler()
            except Exception as e:
                logger.exception("Scheduler run failed: %s", e)
            last_scheduler_run = now

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

    tenant_id = _get_tenant_id_from_env_or_args()
    if not tenant_repo.get_tenant_by_id(tenant_id):
        raise SystemExit(f"Tenant {tenant_id} not found")

    init_context_by_tenant(tenant_id)

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
