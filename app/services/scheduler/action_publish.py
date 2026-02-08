"""Publish action: calls the task publisher to publish the task."""

from app.models.schedule_log import ScheduleLog
from app.models.task import Task
from app.services.tasks.publisher import publish_task


def do_action(task: Task, log: ScheduleLog) -> None:
    """Publish the task via the task publisher. Caller must persist log."""
    result = publish_task(task)
    log.task_id = task.id
    if result is not None:
        log.result = {"action": "publish_instagram", **result}
    else:
        log.result = {
            "action": "publish_instagram",
            "task_id": str(task.id),
            "published": False,
            "reason": "invalid status (task not ready/publishing/failed)",
        }
