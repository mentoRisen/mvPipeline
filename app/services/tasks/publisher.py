"""Task publisher module.

Contains functions to publish tasks in the pipeline.
"""

import logging
from datetime import datetime

from sqlmodel import Session

from app.models.task import Task, TaskStatus
from app.db.engine import engine

logger = logging.getLogger(__name__)


def publish_task(task: Task) -> None:
    """Publish a task entity.
    
    Determines the appropriate publisher based on task.template and publishes the task.
    Currently supports:
    - instagram_post: Publishes as Instagram carousel post
    
    Sets task status to PUBLISHING before starting, then to PUBLISHED on success,
    or to FAILED on failure.
    
    Args:
        task: The task entity to publish
        
    Raises:
        ValueError: If task is not in READY status or template is not supported
    """
    logger.info(f"Processing task {task.id}")
    
    # Store task ID before any session operations
    task_id = task.id
    
    # Check if task is in a valid state for publishing (READY, PUBLISHING, or FAILED)
    if task.status not in (TaskStatus.READY, TaskStatus.PUBLISHING, TaskStatus.FAILED):
        logger.warning(f"Cannot publish task {task_id}: task is in status '{task.status}', but must be 'ready', 'publishing', or 'failed'")
        return
    
    # Set status to PUBLISHING before starting
    logger.info(f"Setting task {task_id} status to PUBLISHING")
    with Session(engine) as session:
        from sqlmodel import select
        # Get fresh task instance in this session to avoid session conflicts
        task_in_session = session.exec(select(Task).where(Task.id == task_id)).first()
        if not task_in_session:
            raise ValueError(f"Task {task_id} not found")
        task_in_session.status = TaskStatus.PUBLISHING
        task_in_session.updated_at = datetime.utcnow()
        session.commit()
    
    # Store template before session operations
    task_template = task.template or "instagram_post"
    
    try:
        # Reload task for publishing (publisher needs fresh instance)
        with Session(engine) as session:
            from sqlmodel import select
            task_for_publish = session.exec(select(Task).where(Task.id == task_id)).first()
            if not task_for_publish:
                raise ValueError(f"Task {task_id} not found")
        
        # Determine publisher based on template
        if task_template == "instagram_post":
            from app.services.tasks.publisher_instagram import publish_task_instagram
            logger.info(f"Publishing task {task_id} to Instagram")
            result = publish_task_instagram(task_for_publish)
            logger.info(f"Successfully published task {task_id} to Instagram: {result.get('permalink', 'N/A')}")
            
            # Set status to PUBLISHED on success and save full Instagram result to result.logs
            with Session(engine) as session:
                from sqlmodel import select
                task_in_session = session.exec(select(Task).where(Task.id == task_id)).first()
                if task_in_session:
                    task_in_session.status = TaskStatus.PUBLISHED
                    task_in_session.updated_at = datetime.utcnow()
                    # Append full Instagram result to result.logs array
                    existing_result = task_in_session.result or {}
                    logs = list(existing_result.get("logs", []))
                    logs.append(result)
                    task_in_session.result = {**existing_result, "logs": logs}
                    session.commit()
                    logger.info(f"Task {task_id} status set to PUBLISHED")
        else:
            raise ValueError(f"Unsupported template for publishing: {task_template}")
    except Exception as e:
        # On error, set status to FAILED
        logger.error(f"Error publishing task {task_id}: {e}")
        with Session(engine) as session:
            # Get task by ID to avoid session conflicts
            from sqlmodel import select
            task_in_session = session.exec(select(Task).where(Task.id == task_id)).first()
            if task_in_session:
                task_in_session.status = TaskStatus.FAILED
                task_in_session.updated_at = datetime.utcnow()
                session.commit()
                logger.info(f"Task {task_id} status set to FAILED due to error")
        raise
