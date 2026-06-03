"""Per-task job reference_id assignment and canonical job ordering."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.models.job import Job


class JobReferenceValidationError(ValueError):
    """Raised when reference_id assignment or validation fails."""

    def __init__(self, message: str, *, field: str = "reference_id") -> None:
        super().__init__(message)
        self.field = field


def _max_reference_id(session: Session, task_id: UUID) -> int:
    row = session.exec(
        select(Job.reference_id)
        .where(Job.task_id == task_id)
        .order_by(Job.reference_id.desc())
        .limit(1)
    ).first()
    return int(row) if row is not None else 0


def _reference_id_in_use(session: Session, task_id: UUID, reference_id: int) -> bool:
    existing = session.exec(
        select(Job.id)
        .where(Job.task_id == task_id, Job.reference_id == reference_id)
        .limit(1)
    ).first()
    return existing is not None


def resolve_reference_id(
    session: Session,
    task_id: UUID,
    explicit: int | None,
) -> int:
    """Resolve reference_id for a single new job on a task."""
    if explicit is not None:
        if explicit < 1:
            raise JobReferenceValidationError(
                "reference_id must be an integer >= 1"
            )
        if _reference_id_in_use(session, task_id, explicit):
            raise JobReferenceValidationError(
                f"reference_id {explicit} is already in use for this task"
            )
        return explicit
    return _max_reference_id(session, task_id) + 1


def assign_reference_ids_for_new_jobs(
    session: Session,
    task_id: UUID,
    explicit_reference_ids: list[int | None],
) -> list[int]:
    """Assign sequential reference_ids for a batch of new jobs in iteration order.

    explicit_reference_ids aligns with the jobs list order (e.g. preview sort).
    """
    if not explicit_reference_ids:
        return []

    seen_explicit: set[int] = set()
    for idx, explicit in enumerate(explicit_reference_ids):
        if explicit is None:
            continue
        if explicit < 1:
            raise JobReferenceValidationError(
                "reference_id must be an integer >= 1",
                field=f"jobs[{idx}].reference_id",
            )
        if explicit in seen_explicit:
            raise JobReferenceValidationError(
                f"duplicate reference_id {explicit} in the same batch",
                field=f"jobs[{idx}].reference_id",
            )
        seen_explicit.add(explicit)
        if _reference_id_in_use(session, task_id, explicit):
            raise JobReferenceValidationError(
                f"reference_id {explicit} is already in use for this task",
                field=f"jobs[{idx}].reference_id",
            )

    next_auto = _max_reference_id(session, task_id) + 1
    assigned: list[int] = []
    for explicit in explicit_reference_ids:
        if explicit is not None:
            assigned.append(explicit)
            next_auto = max(next_auto, explicit + 1)
        else:
            assigned.append(next_auto)
            next_auto += 1
    return assigned


def jobs_for_task_ordered_statement(task_id: UUID, *, purpose: str | None = None):
    """SQLModel select for jobs on a task in canonical list order."""
    statement = select(Job).where(Job.task_id == task_id)
    if purpose is not None:
        statement = statement.where(Job.purpose == purpose)
    return statement.order_by(
        Job.order.desc(),
        Job.reference_id.asc(),
        Job.created_at.asc(),
    )


def list_jobs_for_task_ordered(
    session: Session,
    task_id: UUID,
    *,
    purpose: str | None = None,
) -> list[Job]:
    """Load jobs for a task in canonical list order."""
    statement = jobs_for_task_ordered_statement(task_id, purpose=purpose)
    return list(session.exec(statement).all())


def integrity_error_to_validation(exc: IntegrityError) -> JobReferenceValidationError | None:
    """Map unique (task_id, reference_id) violations to a validation error."""
    orig = getattr(exc, "orig", None)
    message = str(orig or exc).lower()
    if "uq_jobs_task_reference" in message or (
        "duplicate" in message and "reference" in message
    ):
        return JobReferenceValidationError(
            "reference_id is already in use for this task"
        )
    if "unique" in message and "reference_id" in message:
        return JobReferenceValidationError(
            "reference_id is already in use for this task"
        )
    return None
