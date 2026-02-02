"""Database operations for tasks."""

from typing import Optional
from uuid import UUID
from sqlmodel import Session, select

from app.models.task import Task, TaskStatus
from app.models.job import Job, JobStatus
from app.db.engine import engine


def create_task() -> Task:
    """Create a new task with default DRAFT status.
    
    Returns:
        Task: The newly created task
    """
    task = Task()
    with Session(engine) as session:
        session.add(task)
        session.commit()
        session.refresh(task)
    return task


def get_task_by_id(task_id: UUID) -> Optional[Task]:
    """Get a task by its ID.
    
    Args:
        task_id: The UUID of the task
        
    Returns:
        Task if found, None otherwise
    """
    with Session(engine) as session:
        statement = select(Task).where(Task.id == task_id)
        result = session.exec(statement).first()
        return result


def list_all_tasks(limit: int = 100, offset: int = 0) -> list[Task]:
    """List all tasks with pagination.
    
    Args:
        limit: Maximum number of tasks to return (default: 100)
        offset: Number of tasks to skip (default: 0)
        
    Returns:
        List of tasks, ordered by creation time (newest first)
    """
    with Session(engine) as session:
        statement = (
            select(Task)
            .order_by(Task.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        results = session.exec(statement).all()
        return list(results)


def get_next_task_by_status(status: TaskStatus) -> Optional[Task]:
    """Get the next available task with the given status.
    
    For MVP: Returns the oldest task with the specified status.
    For multi-worker: This should use row-level locking (SELECT FOR UPDATE)
    to prevent multiple workers from claiming the same task.
    
    Args:
        status: The status to filter by
        
    Returns:
        Task if found, None otherwise
    """
    with Session(engine) as session:
        # TODO: For multi-worker, add FOR UPDATE lock:
        # statement = select(Task).where(Task.status == status).order_by(Task.created_at).limit(1).with_for_update()
        statement = (
            select(Task)
            .where(Task.status == status)
            .order_by(Task.created_at)
            .limit(1)
        )
        result = session.exec(statement).first()
        return result


def list_tasks_by_status(status: TaskStatus, limit: int = 100) -> list[Task]:
    """List tasks filtered by status.
    
    Args:
        status: The status to filter by
        limit: Maximum number of tasks to return (default: 100)
        
    Returns:
        List of tasks with the specified status, ordered by creation time
    """
    with Session(engine) as session:
        statement = (
            select(Task)
            .where(Task.status == status)
            .order_by(Task.created_at)
            .limit(limit)
        )
        results = session.exec(statement).all()
        return list(results)


def save(task: Task) -> Task:
    """Save a task to the database.
    
    Creates a new task if it doesn't exist, or updates an existing one.
    
    Args:
        task: The task to save
        
    Returns:
        The saved task (with refreshed data from database)
    """
    with Session(engine) as session:
        session.add(task)
        session.commit()
        session.refresh(task)
    return task


def mark_failed(task: Task, error: str) -> Task:
    """Mark a task as failed with an error message.
    
    Uses the task's built-in mark_failed() method and saves to database.
    
    Args:
        task: The task to mark as failed
        error: Error message describing the failure
        
    Returns:
        The updated task
    """
    task.mark_failed(error)
    return save(task)


def approve_task_for_processing(task_id: UUID) -> Task:
    """Approve a task for processing (user action).
    
    Moves task from PENDING_APPROVAL to PROCESSING.
    Also sets all jobs with status NEW to READY (same as clicking "Ready" on each).
    
    Args:
        task_id: The UUID of the task to approve
        
    Returns:
        The updated task
        
    Raises:
        ValueError: If task not found or not in PENDING_APPROVAL status
    """
    task = get_task_by_id(task_id)
    if not task:
        raise ValueError(f"Task {task_id} not found")
    task.approve_for_processing()
    with Session(engine) as session:
        session.add(task)
        # Set all NEW jobs to READY (same as "Ready" action on each job)
        jobs = list(
            session.exec(
                select(Job).where(
                    Job.task_id == task_id,
                    Job.status == JobStatus.NEW,
                )
            ).all()
        )
        for job in jobs:
            job.status = JobStatus.READY
            session.add(job)
        session.commit()
        session.refresh(task)
    return task


def disapprove_task(task_id: UUID) -> Task:
    """Disapprove a task from processing (user action).
    
    Moves task from PENDING_APPROVAL to DISAPPROVED.
    
    Args:
        task_id: The UUID of the task to disapprove
        
    Returns:
        The updated task
        
    Raises:
        ValueError: If task not found or not in PENDING_APPROVAL status
    """
    task = get_task_by_id(task_id)
    if not task:
        raise ValueError(f"Task {task_id} not found")
    task.disapprove_task()
    return save(task)


def approve_task_for_publication(task_id: UUID) -> Task:
    """Approve a task for publication (user action).
    
    Moves task from PENDING_CONFIRMATION to READY.
    
    Args:
        task_id: The UUID of the task to approve
        
    Returns:
        The updated task
        
    Raises:
        ValueError: If task not found or not in PENDING_CONFIRMATION status
    """
    task = get_task_by_id(task_id)
    if not task:
        raise ValueError(f"Task {task_id} not found")
    task.approve_for_publication()
    return save(task)


def publish_task(task_id: UUID) -> Task:
    """Publish a task (user action).
    
    Moves task from READY to PUBLISHED.
    
    Args:
        task_id: The UUID of the task to publish
        
    Returns:
        The updated task
        
    Raises:
        ValueError: If task not found or not in READY status
    """
    task = get_task_by_id(task_id)
    if not task:
        raise ValueError(f"Task {task_id} not found")
    task.mark_published()
    return save(task)


def reject_task(task_id: UUID) -> Task:
    """Reject a task from publication (user action).
    
    Moves task from PENDING_CONFIRMATION to REJECTED.
    
    Args:
        task_id: The UUID of the task to reject
        
    Returns:
        The updated task
        
    Raises:
        ValueError: If task not found or not in PENDING_CONFIRMATION status
    """
    task = get_task_by_id(task_id)
    if not task:
        raise ValueError(f"Task {task_id} not found")
    task.reject_task()
    return save(task)


def submit_task_for_approval(task_id: UUID) -> Task:
    """Submit a draft task for approval (user action).
    
    Moves task from DRAFT to PENDING_APPROVAL.
    
    Args:
        task_id: The UUID of the task to submit
        
    Returns:
        The updated task
        
    Raises:
        ValueError: If task not found or not in DRAFT status
    """
    task = get_task_by_id(task_id)
    if not task:
        raise ValueError(f"Task {task_id} not found")
    task.submit_for_approval()
    return save(task)


def override_task_processing(task_id: UUID) -> Task:
    """Override processing and move task to PENDING_CONFIRMATION (user action).
    
    Moves task from PROCESSING to PENDING_CONFIRMATION regardless of generator state.
    
    Args:
        task_id: The UUID of the task to override
        
    Returns:
        The updated task
        
    Raises:
        ValueError: If task not found or not in PROCESSING status
    """
    task = get_task_by_id(task_id)
    if not task:
        raise ValueError(f"Task {task_id} not found")
    task.override_processing()
    return save(task)

