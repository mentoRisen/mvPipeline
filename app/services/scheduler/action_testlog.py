"""Testlog action: writes task info into log.result (for testing the scheduler)."""

from datetime import datetime

from app.models.schedule_log import ScheduleLog
from app.models.task import Task


def do_action(task: Task, log: ScheduleLog) -> None:
    """Testing action: write task info to log.result. Caller must persist log."""
    log.result = {
        "action": "testlog",
        "task_id": str(task.id),
        "task_status": task.status.value if hasattr(task.status, "value") else str(task.status),
        "task_name": task.name,
        "tenant_id": str(task.tenant_id) if task.tenant_id else None,
        "task_created_at": task.created_at.isoformat() if task.created_at else None,
        "task_updated_at": task.updated_at.isoformat() if task.updated_at else None,
        "ran_at": datetime.utcnow().isoformat(),
    }
