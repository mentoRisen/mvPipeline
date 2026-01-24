"""FastAPI routes for task management API."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from sqlmodel import Session, select
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from app.models.task import Task, TaskStatus
from app.models.job import Job, JobStatus
from app.api.schemas import (
    TaskCreate,
    TaskUpdate,
    TaskResponse,
    TaskListResponse,
    JobCreate,
    JobUpdate,
    JobResponse,
)
from app.db.engine import engine
import app.services.task_repo as task_repo
from app.template.base import Template
from app.template.instagram_post import InstagramPost
from app.services.jobs.processor import process_job as process_job_service

router = APIRouter(prefix="/api/v1", tags=["tasks"])


def get_template_instance(template_name: str) -> Template:
    """Get a template instance by name.
    
    Args:
        template_name: Name of the template (e.g., 'instagram_post')
        
    Returns:
        Template instance
        
    Raises:
        ValueError: If template name is not recognized
    """
    template_map = {
        "instagram_post": InstagramPost,
    }
    
    template_class = template_map.get(template_name)
    if not template_class:
        raise ValueError(f"Unknown template: {template_name}")
    
    return template_class()


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
    
    # Load jobs for this task (oldest first)
    with Session(engine) as session:
        statement = select(Job).where(Job.task_id == task_id).order_by(Job.created_at.asc())
        jobs = list(session.exec(statement).all())
    
    # Create task response with jobs
    task_dict = TaskResponse.model_validate(task).model_dump()
    task_dict['jobs'] = [JobResponse.model_validate(job) for job in jobs]
    return TaskResponse(**task_dict)


@router.post("/tasks", response_model=TaskResponse, status_code=201)
def create_task(task_data: TaskCreate):
    """Create a new task.
    
    Args:
        task_data: Task creation data
        
    Returns:
        Created task
        
    Raises:
        HTTPException: 400 if validation or database error occurs, 500 for unexpected errors
    """
    try:
        task = Task()
        
        # Set required fields
        task.name = task_data.name
        task.template = task_data.template
        
        # Get template instance and populate meta and post from template
        template_instance = get_template_instance(task_data.template)
        task.meta = template_instance.getEmptyMeta()
        task.post = template_instance.getEmptyPost()
        
        # Merge provided meta if specified
        if task_data.meta is not None:
            task.meta.update(task_data.meta)
        
        # Set optional fields if provided (legacy support)
        if task_data.quote_text is not None:
            if task.meta:
                task.meta["quote_text"] = task_data.quote_text
        if task_data.caption_text is not None:
            if task.meta:
                task.meta["caption_text"] = task_data.caption_text
        if task_data.image_generator is not None:
            if task.meta:
                task.meta["image_generator"] = task_data.image_generator
        
        task = task_repo.save(task)
        return TaskResponse.model_validate(task)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except IntegrityError as e:
        raise HTTPException(status_code=400, detail=f"Database integrity error: {str(e)}")
    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error creating task: {str(e)}")


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
    if task_data.name is not None:
        task.name = task_data.name
    if task_data.scheduled_for is not None:
        task.scheduled_for = task_data.scheduled_for
    if task_data.meta is not None:
        task.meta = task_data.meta
    if task_data.post is not None:
        task.post = task_data.post
    
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


@router.post("/tasks/{task_id}/jobs", response_model=JobResponse, status_code=201)
def create_job(task_id: UUID, job_data: JobCreate):
    """Create a new job for a task.
    
    Args:
        task_id: UUID of the parent task
        job_data: Job creation data
        
    Returns:
        Created job
        
    Raises:
        HTTPException: 404 if task not found, 400 if validation or database error occurs
    """
    # Verify task exists
    task = task_repo.get_task_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    
    try:
        # Create job
        job = Job()
        job.task_id = task_id
        job.generator = job_data.generator
        job.purpose = job_data.purpose
        job.prompt = job_data.prompt
        job.status = JobStatus.NEW
        
        # Save job
        with Session(engine) as session:
            session.add(job)
            session.commit()
            session.refresh(job)
        
        return JobResponse.model_validate(job)
    except IntegrityError as e:
        raise HTTPException(status_code=400, detail=f"Database integrity error: {str(e)}")
    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error creating job: {str(e)}")


@router.put("/tasks/{task_id}/jobs/{job_id}", response_model=JobResponse)
def update_job(task_id: UUID, job_id: UUID, job_data: JobUpdate):
    """Update an existing job.
    
    Args:
        task_id: UUID of the parent task
        job_id: UUID of the job to update
        job_data: Job update data
        
    Returns:
        Updated job
        
    Raises:
        HTTPException: 404 if task or job not found, 400 if validation or database error occurs
    """
    # Verify task exists
    task = task_repo.get_task_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    
    try:
        # Get job
        with Session(engine) as session:
            statement = select(Job).where(Job.id == job_id, Job.task_id == task_id)
            job = session.exec(statement).first()
            
            if not job:
                raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
            
            # Update job fields if provided
            if job_data.generator is not None:
                job.generator = job_data.generator
            if job_data.purpose is not None:
                job.purpose = job_data.purpose
            if job_data.prompt is not None:
                job.prompt = job_data.prompt
            if job_data.status is not None:
                job.status = job_data.status
            # Allow updating result JSON (e.g., edited in the UI)
            if job_data.result is not None:
                job.result = job_data.result
            
            # Update timestamp
            job.updated_at = datetime.utcnow()
            
            session.add(job)
            session.commit()
            session.refresh(job)
        
        return JobResponse.model_validate(job)
    except HTTPException:
        raise
    except IntegrityError as e:
        raise HTTPException(status_code=400, detail=f"Database integrity error: {str(e)}")
    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error updating job: {str(e)}")


@router.delete("/tasks/{task_id}/jobs/{job_id}", status_code=204)
def delete_job(task_id: UUID, job_id: UUID):
    """Delete a job.
    
    Args:
        task_id: UUID of the parent task
        job_id: UUID of the job to delete
        
    Raises:
        HTTPException: 404 if task or job not found, 400 if database error occurs
    """
    # Verify task exists
    task = task_repo.get_task_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    
    try:
        # Get and delete job
        with Session(engine) as session:
            statement = select(Job).where(Job.id == job_id, Job.task_id == task_id)
            job = session.exec(statement).first()
            
            if not job:
                raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
            
            session.delete(job)
            session.commit()
        
        return None
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error deleting job: {str(e)}")


@router.post("/tasks/{task_id}/jobs/{job_id}/process", response_model=JobResponse)
def process_job(task_id: UUID, job_id: UUID):
    """Process a job using the appropriate generator.
    
    Args:
        task_id: UUID of the parent task
        job_id: UUID of the job to process
        
    Returns:
        Updated job after processing
        
    Raises:
        HTTPException: 404 if task or job not found, 400/500 on processing errors
    """
    # Verify task exists
    task = task_repo.get_task_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    
    # Get job
    with Session(engine) as session:
        statement = select(Job).where(Job.id == job_id, Job.task_id == task_id)
        job = session.exec(statement).first()
        
        if not job:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    
    try:
        # Process job via service (handles status and result updates)
        process_job_service(job)
        
        # Reload job from database to return fresh state
        with Session(engine) as session:
            statement = select(Job).where(Job.id == job_id, Job.task_id == task_id)
            job = session.exec(statement).first()
        
        if not job:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found after processing")
        
        return JobResponse.model_validate(job)
    except ValueError as e:
        # Validation / bad state errors
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        # Unexpected processing errors - surface the underlying message (which already
        # contains detailed API error info when coming from the generators)
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )
