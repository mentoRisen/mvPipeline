"""Background worker: processes READY jobs and scheduler for all active tenants.

One process polls MySQL and, each cycle, sets tenant context per tenant via
``init_context_by_tenant`` / ``reset_tenant_context`` so ``get_tenant()`` and
tenant ``env`` overrides are correct for that slice of work.

Optional: set ``WORKER_TENANT_ID`` or ``--tenant-id=<UUID>`` to process only
that tenant (must exist and be active).

Configuration:
    WORKER_TENANT_ID                Optional. If set, only this tenant is polled.
    WORKER_CHECK_INTERVAL_SECONDS   Interval between outer poll cycles (default: 30).
    SCHEDULER_CHECK_INTERVAL_SECONDS  Interval between scheduler runs (default: 60).
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
from app.context import get_tenant, init_context_by_tenant, reset_tenant_context
from app.db.engine import create_tables, engine
from app.models.job import Job, JobStatus
from app.models.task import Task, TaskStatus
from app.models.tenant import Tenant
from app.services.jobs.processor import process_job
from app.services.scheduler import run_worker as run_scheduler
from app.services import tenant_repo
from app.utils.logging_config import setup_logging

logger = logging.getLogger(__name__)

_shutdown_requested = False


def _on_signal(_signum, _frame):
    global _shutdown_requested
    _shutdown_requested = True


def _optional_tenant_filter() -> Optional[UUID]:
    """If WORKER_TENANT_ID or --tenant-id= is set, return that UUID; else None."""
    tenant_id_str = os.getenv("WORKER_TENANT_ID")
    if not tenant_id_str and len(sys.argv) > 1:
        for arg in sys.argv[1:]:
            if arg.startswith("--tenant-id="):
                tenant_id_str = arg.split("=", 1)[1].strip()
                break
    if not tenant_id_str:
        return None
    try:
        return UUID(tenant_id_str)
    except ValueError as e:
        raise SystemExit(f"Invalid tenant UUID: {tenant_id_str}") from e


def _tenants_for_this_worker(only_tenant_id: Optional[UUID]) -> list[Tenant]:
    """Tenants to visit this cycle: one active tenant if filtered, else all active."""
    if only_tenant_id is not None:
        t = tenant_repo.get_tenant_by_id(only_tenant_id)
        if t is None:
            return []
        if not t.is_active:
            logger.warning(
                "Worker filter tenant %s is inactive; no work for this tenant",
                only_tenant_id,
            )
            return []
        return [t]
    return tenant_repo.list_active_tenants()


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


def run_worker(only_tenant_id: Optional[UUID] = None):
    """Poll DB and run scheduler, cycling through tenants with fresh context each time."""
    setup_logging()
    create_tables()

    if only_tenant_id is not None:
        logger.info(
            "Worker starting (single-tenant filter %s); job interval=%s s, scheduler interval=%s s",
            only_tenant_id,
            WORKER_CHECK_INTERVAL_SECONDS,
            SCHEDULER_CHECK_INTERVAL_SECONDS,
        )
    else:
        logger.info(
            "Worker starting for all active tenants; job interval=%s s, scheduler interval=%s s",
            WORKER_CHECK_INTERVAL_SECONDS,
            SCHEDULER_CHECK_INTERVAL_SECONDS,
        )

    last_scheduler_run = 0.0

    while not _shutdown_requested:
        tenants = _tenants_for_this_worker(only_tenant_id)
        if not tenants:
            logger.warning(
                "No active tenants to process; sleeping %s s",
                WORKER_CHECK_INTERVAL_SECONDS,
            )
        else:
            now = time.time()
            scheduler_due = now - last_scheduler_run >= SCHEDULER_CHECK_INTERVAL_SECONDS

            for tenant in tenants:
                if _shutdown_requested:
                    break
                try:
                    init_context_by_tenant(tenant.id)
                except ValueError as e:
                    logger.error("Skipping tenant %s: %s", tenant.id, e)
                    continue

                tctx = get_tenant()
                job = _fetch_next_ready_job_in_processing_task()
                if job:
                    try:
                        process_job(job)
                        logger.info(
                            "Worker processed job %s for tenant %s (%s)",
                            job.id,
                            tctx.id,
                            tctx.name,
                        )
                    except Exception as e:
                        logger.exception(
                            "Worker failed to process job %s for tenant %s: %s",
                            job.id,
                            tctx.id,
                            e,
                        )
                else:
                    logger.debug(
                        "No READY jobs in PROCESSING tasks for tenant %s (%s)",
                        tctx.id,
                        tctx.name,
                    )

                if scheduler_due and not _shutdown_requested:
                    try:
                        run_scheduler()
                    except Exception as e:
                        logger.exception(
                            "Scheduler run failed for tenant %s: %s",
                            tctx.id,
                            e,
                        )

            if scheduler_due and not _shutdown_requested:
                last_scheduler_run = time.time()

        reset_tenant_context()

        slept = 0
        while slept < WORKER_CHECK_INTERVAL_SECONDS and not _shutdown_requested:
            time.sleep(min(1, WORKER_CHECK_INTERVAL_SECONDS - slept))
            slept += 1

    reset_tenant_context()
    logger.info("Worker shutting down")


def main():
    """Entry point for python -m app.worker."""
    signal.signal(signal.SIGINT, _on_signal)
    signal.signal(signal.SIGTERM, _on_signal)

    only_tenant_id = _optional_tenant_filter()
    if only_tenant_id is not None:
        t = tenant_repo.get_tenant_by_id(only_tenant_id)
        if t is None:
            raise SystemExit(f"Tenant {only_tenant_id} not found")
        if not t.is_active:
            raise SystemExit(f"Tenant {only_tenant_id} is inactive")

    try:
        run_worker(only_tenant_id=only_tenant_id)
        sys.exit(0)
    except KeyboardInterrupt:
        logger.info("Worker interrupted")
        sys.exit(0)
    except Exception as e:
        logger.exception("Worker exited with error: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
