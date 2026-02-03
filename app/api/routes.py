"""FastAPI routes for task management API."""

import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

logger = logging.getLogger(__name__)

from app.models.task import Task, TaskStatus
from app.models.job import Job, JobStatus
from app.models.tenant import Tenant
from app.api.schemas import (
    TaskCreate,
    TaskUpdate,
    TaskResponse,
    TaskListResponse,
    TenantCreate,
    TenantUpdate,
    TenantResponse,
    JobCreate,
    JobUpdate,
    JobResponse,
)
from app.db.engine import engine
import app.services.task_repo as task_repo
import app.services.tenant_repo as tenant_repo
from app.template.base import Template
from app.template.instagram_post import InstagramPost
from app.services.jobs.processor import process_job as process_job_service
from app.services import auth as auth_service

router = APIRouter(
    prefix="/api/v1",
    tags=["tasks"],
    dependencies=[Depends(auth_service.get_current_active_user)],
)


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


# --- Tenant routes ---


@router.get("/tenants", response_model=list[TenantResponse])
def list_tenants(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
):
    """List all tenants."""
    tenants = tenant_repo.list_all_tenants(limit=limit, offset=offset)
    return [TenantResponse.model_validate(t) for t in tenants]


@router.get("/tenants/default", response_model=TenantResponse)
def get_default_tenant():
    """Get the default tenant (DEFAULT_TENANT_ID or first tenant)."""
    tenant = tenant_repo.get_default_tenant()
    if not tenant:
        raise HTTPException(status_code=404, detail="No tenants found")
    return TenantResponse.model_validate(tenant)


@router.get("/tenants/{tenant_uuid}", response_model=TenantResponse)
def get_tenant(tenant_uuid: UUID):
    """Get a tenant by UUID."""
    tenant = tenant_repo.get_tenant_by_id(tenant_uuid)
    if not tenant:
        raise HTTPException(status_code=404, detail=f"Tenant {tenant_uuid} not found")
    return TenantResponse.model_validate(tenant)


@router.post("/tenants", response_model=TenantResponse, status_code=201)
def create_tenant_route(data: TenantCreate):
    """Create a new tenant."""
    if tenant_repo.get_tenant_by_tenant_id(data.tenant_id):
        raise HTTPException(status_code=400, detail=f"Tenant with tenant_id '{data.tenant_id}' already exists")
    try:
        tenant = tenant_repo.create_tenant(
            tenant_id=data.tenant_id,
            name=data.name,
            description=data.description,
            instagram_account=data.instagram_account,
            facebook_page=data.facebook_page,
            is_active=data.is_active if data.is_active is not None else True,
            env=data.env,
        )
        return TenantResponse.model_validate(tenant)
    except IntegrityError as e:
        raise HTTPException(status_code=400, detail=f"Database integrity error: {str(e)}")


@router.put("/tenants/{tenant_uuid}", response_model=TenantResponse)
def update_tenant(tenant_uuid: UUID, data: TenantUpdate):
    """Update a tenant."""
    tenant = tenant_repo.get_tenant_by_id(tenant_uuid)
    if not tenant:
        raise HTTPException(status_code=404, detail=f"Tenant {tenant_uuid} not found")
    if data.name is not None:
        tenant.name = data.name
    if data.description is not None:
        tenant.description = data.description
    if data.instagram_account is not None:
        tenant.instagram_account = data.instagram_account
    if data.facebook_page is not None:
        tenant.facebook_page = data.facebook_page
    if data.is_active is not None:
        tenant.is_active = data.is_active
    if data.env is not None:
        tenant.env = data.env
    tenant = tenant_repo.save_tenant(tenant)
    return TenantResponse.model_validate(tenant)


@router.delete("/tenants/{tenant_uuid}", status_code=204)
def delete_tenant_route(tenant_uuid: UUID):
    """Delete a tenant. Tasks with this tenant_id will have tenant_id set to NULL (if FK allows)."""
    tenant = tenant_repo.get_tenant_by_id(tenant_uuid)
    if not tenant:
        raise HTTPException(status_code=404, detail=f"Tenant {tenant_uuid} not found")
    tenant_repo.delete_tenant(tenant)
    return None


# --- Task routes ---


@router.get("/tasks", response_model=TaskListResponse)
def list_tasks(
    limit: int = Query(default=100, ge=1, le=1000, description="Maximum number of tasks to return"),
    offset: int = Query(default=0, ge=0, description="Number of tasks to skip"),
    status: Optional[TaskStatus] = Query(default=None, description="Filter by task status"),
    tenant_id: Optional[UUID] = Query(default=None, description="Filter by tenant ID"),
):
    """List all tasks with optional status/tenant filtering and pagination.
    
    Args:
        limit: Maximum number of tasks to return (1-1000)
        offset: Number of tasks to skip
        status: Optional status filter
        tenant_id: Optional tenant filter
        
    Returns:
        Paginated list of tasks
    """
    with Session(engine) as session:
        if status:
            tasks = task_repo.list_tasks_by_status(status, limit=limit, tenant_id=tenant_id)
            statement = select(Task).where(Task.status == status)
            if tenant_id is not None:
                statement = statement.where(Task.tenant_id == tenant_id)
            total = len(list(session.exec(statement).all()))
        else:
            tasks = task_repo.list_all_tasks(limit=limit, offset=offset, tenant_id=tenant_id)
            statement = select(Task)
            if tenant_id is not None:
                statement = statement.where(Task.tenant_id == tenant_id)
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
    
    # Load jobs for this task ordered by custom order (descending), then by creation time (oldest first)
    with Session(engine) as session:
        statement = (
            select(Job)
            .where(Job.task_id == task_id)
            .order_by(Job.order.desc(), Job.created_at.asc())
        )
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
        if task_data.tenant_id is not None:
            task.tenant_id = task_data.tenant_id
        
        # Get template instance and populate meta and post from template
        template_instance = get_template_instance(task_data.template)
        task.meta = template_instance.getEmptyMeta()
        task.post = template_instance.getEmptyPost()
        
        # Merge provided meta if specified
        if task_data.meta is not None:
            task.meta.update(task_data.meta)
        
        # Merge provided post if specified (e.g., caption from JSON)
        if task_data.post is not None:
            if task.post is None:
                task.post = {}
            if isinstance(task.post, dict):
                task.post.update(task_data.post)
        
        # Set optional fields if provided (legacy support)
        if task_data.quote_text is not None and task.meta is not None:
            task.meta["quote_text"] = task_data.quote_text
        if task_data.caption_text is not None and task.meta is not None:
            task.meta["caption_text"] = task_data.caption_text
        if task_data.image_generator is not None and task.meta is not None:
            task.meta["image_generator"] = task_data.image_generator

        # Ensure caption from caption_text and/or meta is also reflected in task.post.caption
        # so the frontend can display it consistently.
        caption_value = None
        if task_data.caption_text:
            caption_value = task_data.caption_text
        elif task.meta and isinstance(task.meta, dict):
            # Fallback: if caption_text is embedded in meta
            meta_caption = task.meta.get("caption_text")
            if isinstance(meta_caption, str) and meta_caption.strip():
                caption_value = meta_caption

        if caption_value:
            if task.post is None:
                task.post = {}
            if isinstance(task.post, dict):
                # Only set if not already populated by the template/JSON
                if not task.post.get("caption"):
                    task.post["caption"] = caption_value
        
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
    
    Deletes all associated jobs first, then deletes the task.
    
    Args:
        task_id: UUID of the task to delete
        
    Raises:
        HTTPException: 404 if task not found
    """
    task = task_repo.get_task_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    
    with Session(engine) as session:
        # First, delete all jobs associated with this task
        statement = select(Job).where(Job.task_id == task_id)
        jobs = list(session.exec(statement).all())
        for job in jobs:
            session.delete(job)
        
        # Then delete the task
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
    
    Publishes task using the publisher service. Can be called from READY, PUBLISHING, or FAILED status.
    The publisher service handles status transitions (READY/PUBLISHING/FAILED -> PUBLISHING -> PUBLISHED/FAILED).
    
    Args:
        task_id: UUID of the task to publish
        
    Returns:
        Updated task
        
    Raises:
        HTTPException: 404 if task not found, 400 if invalid status or publishing fails
    """
    # Get task
    task = task_repo.get_task_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    
    # Check if task is in a valid state for publishing
    if task.status not in (TaskStatus.READY, TaskStatus.PUBLISHING, TaskStatus.FAILED):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot publish task in status '{task.status}'. Task must be in 'ready', 'publishing', or 'failed' status."
        )
    
    try:
        # Use the publisher service to publish the task
        from app.services.tasks.publisher import publish_task as publish_task_service
        publish_task_service(task)
        
        # Reload task to get updated status
        task = task_repo.get_task_by_id(task_id)
        return TaskResponse.model_validate(task)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to publish task: {str(e)}")


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


@router.post("/tasks/{task_id}/override-processing", response_model=TaskResponse)
def override_task_processing(task_id: UUID):
    """Override processing and move task to PENDING_CONFIRMATION.
    
    Moves task from PROCESSING to PENDING_CONFIRMATION regardless of generator state.
    
    Args:
        task_id: UUID of the task to override
        
    Returns:
        Updated task
        
    Raises:
        HTTPException: 404 if task not found, 400 if invalid status transition
    """
    try:
        task = task_repo.override_task_processing(task_id)
        return TaskResponse.model_validate(task)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/tasks/status/{status}", response_model=TaskListResponse)
def list_tasks_by_status_route(
    status: TaskStatus,
    limit: int = Query(default=100, ge=1, le=1000, description="Maximum number of tasks to return"),
    tenant_id: Optional[UUID] = Query(default=None, description="Filter by tenant ID"),
):
    """List tasks filtered by status.
    
    Args:
        status: Task status to filter by
        limit: Maximum number of tasks to return
        tenant_id: Optional tenant filter
        
    Returns:
        List of tasks with the specified status
    """
    tasks = task_repo.list_tasks_by_status(status, limit=limit, tenant_id=tenant_id)
    
    with Session(engine) as session:
        statement = select(Task).where(Task.status == status)
        if tenant_id is not None:
            statement = statement.where(Task.tenant_id == tenant_id)
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
    logger.info(f"[create_job] Creating job for task {task_id}")
    logger.debug(f"[create_job] Job data: generator={job_data.generator}, purpose={job_data.purpose}, prompt={job_data.prompt}")
    
    # Verify task exists
    task = task_repo.get_task_by_id(task_id)
    if not task:
        logger.warning(f"[create_job] Task {task_id} not found")
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    
    logger.info(f"[create_job] Task {task_id} found, creating job")
    
    try:
        # Create job
        job = Job()
        job.task_id = task_id
        job.generator = job_data.generator
        job.purpose = job_data.purpose
        job.prompt = job_data.prompt
        # Use explicit order if provided, otherwise default to 0
        if job_data.order is not None:
            job.order = job_data.order
        job.status = JobStatus.NEW
        
        logger.debug(f"[create_job] Job object created: generator={job.generator}, purpose={job.purpose}, status={job.status}")
        if job.prompt:
            logger.debug(f"[create_job] Job prompt structure: {type(job.prompt)}, keys={job.prompt.keys() if isinstance(job.prompt, dict) else 'N/A'}")
            if isinstance(job.prompt, dict) and 'prompt' in job.prompt:
                logger.debug(f"[create_job] Job prompt.prompt value: {job.prompt.get('prompt', 'N/A')[:100]}...")
        
        # Save job
        with Session(engine) as session:
            session.add(job)
            session.commit()
            session.refresh(job)
        
        logger.info(f"[create_job] Job created successfully: job_id={job.id}, task_id={task_id}, generator={job.generator}")
        return JobResponse.model_validate(job)
    except IntegrityError as e:
        logger.error(f"[create_job] Database integrity error for task {task_id}: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Database integrity error: {str(e)}")
    except SQLAlchemyError as e:
        logger.error(f"[create_job] Database error for task {task_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    except Exception as e:
        logger.error(f"[create_job] Unexpected error creating job for task {task_id}: {str(e)}", exc_info=True)
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
            if job_data.order is not None:
                job.order = job_data.order
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


@router.get("/templates/{template_name}")
def get_template(template_name: str):
    """Get template JSON structure for creating a task.
    
    Returns a JSON template that includes:
    - Task fields (name, template, meta, post)
    - One example job for image generation
    
    Args:
        template_name: Name of the template (e.g., 'instagram_post')
        
    Returns:
        JSON template structure with task and one job
        
    Raises:
        HTTPException: 400 if template name is not recognized
    """
    try:
        template_instance = get_template_instance(template_name)
        
        # Build template JSON with task and one image job
        # Include default values with explanations for meta and post fields
        meta = template_instance.getEmptyMeta()
        post = template_instance.getEmptyPost()
        
        # Add default values with explanations for Instagram post template
        if template_name == "instagram_post":
            meta["theme"] = "Enter theme here - This field defines the overall theme or topic for the Instagram post (e.g., 'motivation', 'inspiration', 'business')"
            post["caption"] = "Enter caption here - This field contains the text caption that will accompany the Instagram post image"
        
        template_json = {
            "name": "",
            "template": template_name,
            "meta": meta,
            "post": post,
            "jobs": [
                {
                    "generator": "dalle",
                    "purpose": "imagecontent",
                    "prompt": {
                        "prompt": "Enter image generation prompt here - This field contains the text prompt that will be sent to the image generator (e.g., DALL-E) to create the image for the Instagram post"
                    }
                }
            ]
        }
        
        return template_json
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
