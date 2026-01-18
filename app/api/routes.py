"""FastAPI routes for task management API."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from sqlmodel import Session, select

from app.models.task import Task, TaskStatus
from app.api.schemas import (
    TaskCreate,
    TaskUpdate,
    TaskResponse,
    TaskListResponse,
)
from app.db.engine import engine
import app.services.task_repo as task_repo

router = APIRouter(prefix="/api/v1", tags=["tasks"])


def get_db_session():
    """Dependency to get database session."""
    with Session(engine) as session:
        yield session


@router.get("/tasks", response_model=TaskListResponse)
def list_tasks(
    limit: int = Query(default=100, ge=1, le=1000, description="Maximum number of tasks to return"),
    offset: int = Query(default=0, ge=0, description="Number of tasks to skip"),
    status: Optional[TaskStatus] = Query(default=None, description="Filter by task status"),
):
    """List all tasks with optional status filtering and pagination.
    
    Args:
        limit: Maximum number of tasks to return (1-1000)
        offset: Number of tasks to skip
        status: Optional status filter
        
    Returns:
        Paginated list of tasks
    """
    with Session(engine) as session:
        if status:
            tasks = task_repo.list_tasks_by_status(status, limit=limit)
            # Get total count for this status
            statement = select(Task).where(Task.status == status)
            total = len(list(session.exec(statement).all()))
        else:
            tasks = task_repo.list_all_tasks(limit=limit, offset=offset)
            # Get total count
            statement = select(Task)
            total = len(list(session.exec(statement).all()))
        
        return TaskListResponse(
            tasks=[TaskResponse.model_validate(task) for task in tasks],
            total=total,
            limit=limit,
            offset=offset,
        )


@router.get("/tasks/{task_id}", response_model=TaskResponse)
def get_task(task_id: UUID):
    """Get a specific task by ID.
    
    Args:
        task_id: UUID of the task
        
    Returns:
        Task details
        
    Raises:
        HTTPException: 404 if task not found
    """
    task = task_repo.get_task_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return TaskResponse.model_validate(task)


@router.post("/tasks", response_model=TaskResponse, status_code=201)
def create_task(task_data: TaskCreate):
    """Create a new task.
    
    Args:
        task_data: Task creation data
        
    Returns:
        Created task
    """
    task = Task()
    
    # Set optional fields if provided
    if task_data.quote_text is not None:
        task.quote_text = task_data.quote_text
    if task_data.caption_text is not None:
        task.caption_text = task_data.caption_text
    if task_data.image_generator is not None:
        task.image_generator = task_data.image_generator
    if task_data.meta is not None:
        task.meta = task_data.meta
    
    task = task_repo.save(task)
    return TaskResponse.model_validate(task)


@router.put("/tasks/{task_id}", response_model=TaskResponse)
def update_task(task_id: UUID, task_data: TaskUpdate):
    """Update an existing task.
    
    Args:
        task_id: UUID of the task to update
        task_data: Task update data
        
    Returns:
        Updated task
        
    Raises:
        HTTPException: 404 if task not found
    """
    task = task_repo.get_task_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    
    # Update fields if provided
    if task_data.quote_text is not None:
        task.quote_text = task_data.quote_text
    if task_data.caption_text is not None:
        task.caption_text = task_data.caption_text
    if task_data.image_generator is not None:
        task.image_generator = task_data.image_generator
    if task_data.image_generator_prompt is not None:
        task.image_generator_prompt = task_data.image_generator_prompt
    if task_data.scheduled_for is not None:
        task.scheduled_for = task_data.scheduled_for
    if task_data.meta is not None:
        task.meta = task_data.meta
    
    task = task_repo.save(task)
    return TaskResponse.model_validate(task)


@router.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: UUID):
    """Delete a task.
    
    Args:
        task_id: UUID of the task to delete
        
    Raises:
        HTTPException: 404 if task not found
    """
    task = task_repo.get_task_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    
    with Session(engine) as session:
        session.delete(task)
        session.commit()
    
    return None


@router.post("/tasks/{task_id}/submit", response_model=TaskResponse)
def submit_task_for_approval(task_id: UUID):
    """Submit a draft task for approval.
    
    Moves task from DRAFT to PENDING_APPROVAL.
    
    Args:
        task_id: UUID of the task to submit
        
    Returns:
        Updated task
        
    Raises:
        HTTPException: 404 if task not found, 400 if invalid status transition
    """
    try:
        task = task_repo.submit_task_for_approval(task_id)
        return TaskResponse.model_validate(task)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/tasks/{task_id}/approve-processing", response_model=TaskResponse)
def approve_task_for_processing(task_id: UUID):
    """Approve a task for processing.
    
    Moves task from PENDING_APPROVAL to PROCESSING.
    
    Args:
        task_id: UUID of the task to approve
        
    Returns:
        Updated task
        
    Raises:
        HTTPException: 404 if task not found, 400 if invalid status transition
    """
    try:
        task = task_repo.approve_task_for_processing(task_id)
        return TaskResponse.model_validate(task)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/tasks/{task_id}/disapprove", response_model=TaskResponse)
def disapprove_task(task_id: UUID):
    """Disapprove a task from processing.
    
    Moves task from PENDING_APPROVAL to DISAPPROVED.
    
    Args:
        task_id: UUID of the task to disapprove
        
    Returns:
        Updated task
        
    Raises:
        HTTPException: 404 if task not found, 400 if invalid status transition
    """
    try:
        task = task_repo.disapprove_task(task_id)
        return TaskResponse.model_validate(task)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/tasks/{task_id}/approve-publication", response_model=TaskResponse)
def approve_task_for_publication(task_id: UUID):
    """Approve a task for publication.
    
    Moves task from PENDING_CONFIRMATION to READY.
    
    Args:
        task_id: UUID of the task to approve
        
    Returns:
        Updated task
        
    Raises:
        HTTPException: 404 if task not found, 400 if invalid status transition
    """
    try:
        task = task_repo.approve_task_for_publication(task_id)
        return TaskResponse.model_validate(task)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/tasks/{task_id}/publish", response_model=TaskResponse)
def publish_task(task_id: UUID):
    """Publish a task.
    
    Moves task from READY to PUBLISHED.
    
    Args:
        task_id: UUID of the task to publish
        
    Returns:
        Updated task
        
    Raises:
        HTTPException: 404 if task not found, 400 if invalid status transition
    """
    try:
        task = task_repo.publish_task(task_id)
        return TaskResponse.model_validate(task)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/tasks/{task_id}/reject", response_model=TaskResponse)
def reject_task(task_id: UUID):
    """Reject a task from publication.
    
    Moves task from PENDING_CONFIRMATION to REJECTED.
    
    Args:
        task_id: UUID of the task to reject
        
    Returns:
        Updated task
        
    Raises:
        HTTPException: 404 if task not found, 400 if invalid status transition
    """
    try:
        task = task_repo.reject_task(task_id)
        return TaskResponse.model_validate(task)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/tasks/status/{status}", response_model=TaskListResponse)
def list_tasks_by_status(
    status: TaskStatus,
    limit: int = Query(default=100, ge=1, le=1000, description="Maximum number of tasks to return"),
):
    """List tasks filtered by status.
    
    Args:
        status: Task status to filter by
        limit: Maximum number of tasks to return
        
    Returns:
        List of tasks with the specified status
    """
    tasks = task_repo.list_tasks_by_status(status, limit=limit)
    
    with Session(engine) as session:
        statement = select(Task).where(Task.status == status)
        total = len(list(session.exec(statement).all()))
    
    return TaskListResponse(
        tasks=[TaskResponse.model_validate(task) for task in tasks],
        total=total,
        limit=limit,
        offset=0,
    )
