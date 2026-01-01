"""Database operations for tasks."""

from typing import Optional
from sqlmodel import Session, select

from app.models.task import Task, TaskStatus
from app.db.engine import engine


def create_task() -> Task:
    """Create a new task with default PENDING status.
    
    Returns:
        Task: The newly created task
    """
    task = Task()
    with Session(engine) as session:
        session.add(task)
        session.commit()
        session.refresh(task)
    return task


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

