"""Scheduler worker: finds schedule rules due for the current timeslot and (for now) logs them.

Timeslot format: "YYYY-MM-DD-HH" for the hour 00–23 (e.g. "2026-02-06-20" = 20:00–20:59).
Timezone is read from .env: SCHEDULER_TIMEZONE (e.g. Europe/Prague). Defaults to UTC.
"""

import json
import logging
from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlmodel import Session, select

from app.config import SCHEDULER_TIMEZONE
from app.context import get_tenant
from app.db.engine import engine
from app.models.schedule_log import ScheduleLog, ScheduleLogStatus
from app.models.schedule_rule import ScheduleRule
from app.models.task import Task
from app.services import task_repo
from app.services.notifier import notify as notify_send
from app.services.scheduler import action_testlog

logger = logging.getLogger(__name__)


def get_current_timeslot() -> str:
    """Current timeslot string: YYYY-MM-DD-HH in SCHEDULER_TIMEZONE (from .env)."""
    tz = ZoneInfo(SCHEDULER_TIMEZONE)
    now = datetime.now(tz)
    return now.strftime("%Y-%m-%d-%H")


def timeslot_to_hour_and_weekday(timeslot: str) -> tuple[int, int] | None:
    """Parse timeslot 'YYYY-MM-DD-HH' into (hour_0_23, cron_weekday).
    Cron weekday: 0=Sunday, 1=Monday, ..., 6=Saturday.
    Returns None if timeslot format is invalid.
    """
    parts = timeslot.split("-")
    if len(parts) != 4:
        return None
    try:
        y, m, d, h = int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3])
        if not (0 <= h <= 23):
            return None
        from datetime import date
        dt = date(year=y, month=m, day=d)
        # Python: Mon=0 .. Sun=6  ->  cron: Sun=0, Mon=1 .. Sat=6
        py_weekday = dt.weekday()
        cron_weekday = (py_weekday + 1) % 7
        return (h, cron_weekday)
    except (ValueError, IndexError):
        return None


def rule_matches_timeslot(rule: ScheduleRule, timeslot: str) -> bool:
    """True if rule.times says this rule should run in the given timeslot."""
    parsed = timeslot_to_hour_and_weekday(timeslot)
    if not parsed:
        return False
    slot_hour, slot_cron_dow = parsed
    times = rule.times
    if not times or not isinstance(times, dict):
        return False
    rule_hour = times.get("hour")
    rule_days = times.get("days")
    if not isinstance(rule_days, list):
        rule_days = []
    if rule_hour is None or not isinstance(rule_hour, int):
        return False
    if slot_hour != rule_hour:
        return False
    return slot_cron_dow in rule_days


def _get_task_for_log(
    session: Session,
    log: ScheduleLog,
    tenant_id: UUID,
) -> Task | None:
    """Get task for this log: from log.task_id if set, else oldest READY task for tenant."""
    if log.task_id is not None:
        return session.get(Task, log.task_id)
    return task_repo.fetch_ready_task(tenant_id)


def _log_schedule_rule_result(
    rule: ScheduleRule,
    timeslot: str,
    log: ScheduleLog,
    task: Task | None = None,
) -> None:
    """Log the outcome of schedule rule processing (call after log is updated). Also notifies via notifier."""
    status = log.status.value if hasattr(log.status, "value") else log.status
    task_id = task.id if task else None
    err = (log.result or {}).get("error", "") if isinstance(log.result, dict) else ""
    if log.status == ScheduleLogStatus.ERROR:
        logger.error(
            "Schedule rule result: status=%s rule_id=%s tenant_id=%s action=%s timeslot=%s log_id=%s task_id=%s error=%s",
            status, rule.id, rule.tenant_id, rule.action, timeslot, log.id, task_id, err,
        )
    else:
        logger.info(
            "Schedule rule result: status=%s rule_id=%s tenant_id=%s action=%s timeslot=%s log_id=%s task_id=%s",
            status, rule.id, rule.tenant_id, rule.action, timeslot, log.id, task_id,
        )

    event_type = "scheduler_error" if log.status == ScheduleLogStatus.ERROR else "scheduler"
    msg = f"status={status} action={rule.action} timeslot={timeslot} log_id={log.id} task_id={task_id}"
    if err:
        msg += f" error={err}"
    if log.result and isinstance(log.result, dict):
        msg += "\n```json\n" + json.dumps(log.result, indent=2) + "\n```"
    try:
        notify_send(event_type, msg)
    except Exception as e:
        logger.debug("Notifier skipped: %s", e)


def run_schedule_rule(
    session: Session,
    rule: ScheduleRule,
    timeslot: str,
    log: ScheduleLog | None = None,
) -> tuple[ScheduleLog, Task | None]:
    """Ensure a log exists in PROCESSING state, resolve task (from log or fetch_ready_task), then run the rule (action TBD).
    If log is None, creates a new ScheduleLog with status PROCESSING.
    If log exists, sets its status to PROCESSING.
    Task: from log.task_id if set, else oldest READY task for current tenant. Returns (log, task or None).
    """
    if log is None:
        log = ScheduleLog(
            tenant_id=rule.tenant_id,
            schedule_rule_id=rule.id,
            timeslot=timeslot,
            action=rule.action,
            status=ScheduleLogStatus.PROCESSING,
        )
        session.add(log)
    else:
        log.status = ScheduleLogStatus.PROCESSING
        session.add(log)
    session.commit()
    session.refresh(log)

    task = _get_task_for_log(session, log, rule.tenant_id)
    if task is None:
        log.status = ScheduleLogStatus.NO_TASK
        session.add(log)
        session.commit()
        session.refresh(log)
        _log_schedule_rule_result(rule, timeslot, log)
        return log, None

    _log_schedule_rule_result(rule, timeslot, log, task=task)

    try:
        match rule.action:
            case "testlog":
                action_testlog.do_action(task, log)
            case _:
                raise ValueError(f"Unknown schedule rule action: {rule.action}")
        log.status = ScheduleLogStatus.DONE
        log.processed = datetime.utcnow()
        session.add(log)
        session.commit()
        session.refresh(log)
        _log_schedule_rule_result(rule, timeslot, log, task=task)
    except Exception as e:
        log.status = ScheduleLogStatus.ERROR
        log.processed = datetime.utcnow()
        log.result = {"error": str(e)}
        session.add(log)
        session.commit()
        session.refresh(log)
        _log_schedule_rule_result(rule, timeslot, log, task=task)
    return log, task


def _run_scheduled_logs(session: Session, tenant_id: UUID, timeslot: str) -> None:
    """Find schedule_logs with status SCHEDULED for this tenant and timeslot, and run them."""
    scheduled_logs = list(
        session.exec(
            select(ScheduleLog).where(
                ScheduleLog.tenant_id == tenant_id,
                ScheduleLog.timeslot == timeslot,
                ScheduleLog.status == ScheduleLogStatus.SCHEDULED,
            )
        ).all()
    )
    for log in scheduled_logs:
        rule = session.get(ScheduleRule, log.schedule_rule_id)
        if rule is not None:
            run_schedule_rule(session, rule, timeslot, log=log)
        # TODO: actually run the action and update log status


def run_worker() -> None:
    """Run SCHEDULED logs for current timeslot, then find rules without a log that should run and log them.
    Requires tenant to be initialized via init_context_by_tenant() before calling.
    """
    tenant = get_tenant()
    tenant_id = tenant.id
    timeslot = get_current_timeslot()
    logger.info("Scheduler worker running for timeslot %s tenant_id=%s", timeslot, tenant_id)

    with Session(engine) as session:
        _run_scheduled_logs(session, tenant_id, timeslot)

        all_rules = list(
            session.exec(select(ScheduleRule).where(ScheduleRule.tenant_id == tenant_id)).all()
        )

        for rule in all_rules:
            existing = session.exec(
                select(ScheduleLog).where(
                    ScheduleLog.tenant_id == rule.tenant_id,
                    ScheduleLog.schedule_rule_id == rule.id,
                    ScheduleLog.timeslot == timeslot,
                )
            ).first()
            if existing is not None:
                continue

            if not rule_matches_timeslot(rule, timeslot):
                continue

            run_schedule_rule(session, rule, timeslot)
