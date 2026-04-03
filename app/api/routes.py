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
from app.models.schedule_rule import ScheduleRule
from app.api.schemas import (
    AiTaskDraftConfirmRequest,
    AiTaskDraftRequest,
    AiTaskDraftResponse,
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
    ScheduleRuleCreate,
    ScheduleRuleUpdate,
    ScheduleRuleResponse,
)
from app.db.engine import engine
import app.services.task_repo as task_repo
import app.services.tenant_repo as tenant_repo
import app.services.schedule_rule_repo as schedule_rule_repo
from app.services.ai_task_draft_service import (
    AiTaskDraftService,
    AiTaskDraftValidationError,
    TextDraftRefusalError,
    TextDraftUpstreamError,
)
from app.services.integrations.llm_text_adapter import OpenAITextDraftAdapter
from app.template.base import Template
from app.template.instagram_post import InstagramPost
from app.services.jobs.processor import process_job as process_job_service
from app.services import auth as auth_service
from app.api.tenant_deps import tenant_context_dependency
from app.context import get_tenant as current_tenant

bootstrap_router = APIRouter(
    prefix="/api/v1",
    tags=["tenants"],
    dependencies=[Depends(auth_service.get_current_active_user)],
)

scoped_router = APIRouter(
    prefix="/api/v1",
    tags=["tasks"],
    dependencies=[
        Depends(auth_service.get_current_active_user),
        Depends(tenant_context_dependency),
    ],
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


def _task_for_current_tenant_or_404(task_id: UUID, tenant: Tenant) -> Task:
    task = task_repo.get_task_by_id(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    if task.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return task


def _ensure_tenant_path_matches(tenant_uuid: UUID, tenant: Tenant) -> None:
    if tenant_uuid != tenant.id:
        raise HTTPException(
            status_code=403,
            detail="Requested tenant does not match X-Tenant-Id",
        )


def _schedule_rule_for_current_tenant_or_404(rule_id: UUID, tenant: Tenant) -> ScheduleRule:
    rule = schedule_rule_repo.get_schedule_rule_by_id(rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail=f"Schedule rule {rule_id} not found")
    if rule.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail=f"Schedule rule {rule_id} not found")
    return rule


def get_db_session():
    """Dependency to get database session."""
    with Session(engine) as session:
        yield session


def get_ai_task_draft_service() -> AiTaskDraftService:
    """Build the shared AI draft preview service."""
    return AiTaskDraftService(OpenAITextDraftAdapter())


# --- Tenant routes ---


@bootstrap_router.get("/tenants", response_model=list[TenantResponse])
def list_tenants(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
):
    """List all tenants."""
    tenants = tenant_repo.list_all_tenants(limit=limit, offset=offset)
    return [TenantResponse.model_validate(t) for t in tenants]


@bootstrap_router.get("/tenants/default", response_model=TenantResponse)
def get_default_tenant():
    """Get the default tenant (DEFAULT_TENANT_ID or first tenant)."""
    tenant = tenant_repo.get_default_tenant()
    if not tenant:
        raise HTTPException(status_code=404, detail="No tenants found")
    return TenantResponse.model_validate(tenant)


@scoped_router.get("/tenants/{tenant_uuid}", response_model=TenantResponse)
def get_tenant_detail(
    tenant_uuid: UUID,
    tenant: Tenant = Depends(tenant_context_dependency),
):
    """Get a tenant by UUID."""
    _ensure_tenant_path_matches(tenant_uuid, tenant)
    tenant = tenant_repo.get_tenant_by_id(tenant_uuid)
    if not tenant:
        raise HTTPException(status_code=404, detail=f"Tenant {tenant_uuid} not found")
    return TenantResponse.model_validate(tenant)


@bootstrap_router.post("/tenants", response_model=TenantResponse, status_code=201)
def create_tenant_route(data: TenantCreate):
    """Create a new tenant."""
    try:
        tenant = tenant_repo.create_tenant(
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


@scoped_router.put("/tenants/{tenant_uuid}", response_model=TenantResponse)
def update_tenant(
    tenant_uuid: UUID,
    data: TenantUpdate,
    tenant: Tenant = Depends(tenant_context_dependency),
):
    """Update a tenant."""
    _ensure_tenant_path_matches(tenant_uuid, tenant)
    tenant_record = tenant_repo.get_tenant_by_id(tenant_uuid)
    if not tenant_record:
        raise HTTPException(status_code=404, detail=f"Tenant {tenant_uuid} not found")
    if data.name is not None:
        tenant_record.name = data.name
    if data.description is not None:
        tenant_record.description = data.description
    if data.instagram_account is not None:
        tenant_record.instagram_account = data.instagram_account
    if data.facebook_page is not None:
        tenant_record.facebook_page = data.facebook_page
    if data.is_active is not None:
        tenant_record.is_active = data.is_active
    if data.env is not None:
        tenant_record.env = data.env
    tenant_record = tenant_repo.save_tenant(tenant_record)
    return TenantResponse.model_validate(tenant_record)


@scoped_router.delete("/tenants/{tenant_uuid}", status_code=204)
def delete_tenant_route(
    tenant_uuid: UUID,
    tenant: Tenant = Depends(tenant_context_dependency),
):
    """Delete a tenant. Tasks with this tenant will have tenant_id set to NULL."""
    _ensure_tenant_path_matches(tenant_uuid, tenant)
    tenant_record = tenant_repo.get_tenant_by_id(tenant_uuid)
    if not tenant_record:
        raise HTTPException(status_code=404, detail=f"Tenant {tenant_uuid} not found")
    tenant_repo.delete_tenant(tenant_record)
    return None


# --- ScheduleRule routes ---


@scoped_router.get("/tenants/{tenant_uuid}/schedule-rules", response_model=list[ScheduleRuleResponse])
def list_schedule_rules(
    tenant_uuid: UUID,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    tenant: Tenant = Depends(tenant_context_dependency),
):
    """List schedule rules for a tenant."""
    _ensure_tenant_path_matches(tenant_uuid, tenant)
    rules = schedule_rule_repo.list_schedule_rules_by_tenant(
        tenant_id=tenant_uuid, limit=limit, offset=offset
    )
    return [ScheduleRuleResponse.model_validate(r) for r in rules]


@scoped_router.get("/schedule-rules/{rule_id}", response_model=ScheduleRuleResponse)
def get_schedule_rule(
    rule_id: UUID,
    tenant: Tenant = Depends(tenant_context_dependency),
):
    """Get a schedule rule by ID."""
    rule = _schedule_rule_for_current_tenant_or_404(rule_id, tenant)
    return ScheduleRuleResponse.model_validate(rule)


@scoped_router.post("/schedule-rules", response_model=ScheduleRuleResponse, status_code=201)
def create_schedule_rule_route(
    data: ScheduleRuleCreate,
    tenant: Tenant = Depends(tenant_context_dependency),
):
    """Create a new schedule rule."""
    rule = schedule_rule_repo.create_schedule_rule(
        tenant_id=tenant.id,
        action=data.action,
        note=data.note,
        times=data.times,
    )
    return ScheduleRuleResponse.model_validate(rule)


@scoped_router.put("/schedule-rules/{rule_id}", response_model=ScheduleRuleResponse)
def update_schedule_rule_route(
    rule_id: UUID,
    data: ScheduleRuleUpdate,
    tenant: Tenant = Depends(tenant_context_dependency),
):
    """Update a schedule rule."""
    rule = _schedule_rule_for_current_tenant_or_404(rule_id, tenant)
    if data.action is not None:
        rule.action = data.action
    if data.note is not None:
        rule.note = data.note
    if data.times is not None:
        rule.times = data.times
    rule = schedule_rule_repo.save_schedule_rule(rule)
    return ScheduleRuleResponse.model_validate(rule)


@scoped_router.delete("/schedule-rules/{rule_id}", status_code=204)
def delete_schedule_rule_route(
    rule_id: UUID,
    tenant: Tenant = Depends(tenant_context_dependency),
):
    """Delete a schedule rule."""
    rule = _schedule_rule_for_current_tenant_or_404(rule_id, tenant)
    schedule_rule_repo.delete_schedule_rule(rule)
    return None


# --- Task routes ---


@scoped_router.post("/tasks/ai-draft-preview", response_model=AiTaskDraftResponse)
def create_ai_task_draft_preview(
    data: AiTaskDraftRequest,
    tenant: Tenant = Depends(tenant_context_dependency),
):
    """Return one tenant-aware AI draft preview without persisting records."""
    service = get_ai_task_draft_service()
    try:
        return service.generate_preview(brief=data.brief, tenant=tenant)
    except TextDraftRefusalError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except AiTaskDraftValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except TextDraftUpstreamError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@scoped_router.post("/tasks/ai-draft-confirm", response_model=TaskResponse, status_code=201)
def confirm_ai_task_draft(
    data: AiTaskDraftConfirmRequest,
    tenant: Tenant = Depends(tenant_context_dependency),
):
    """Persist one reviewed AI draft as a real task plus jobs."""
    service = get_ai_task_draft_service()
    try:
        task = service.confirm_preview(draft=data, tenant=tenant)
        return TaskResponse.model_validate(task)
    except AiTaskDraftValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (IntegrityError, SQLAlchemyError) as exc:
        raise HTTPException(status_code=500, detail="Failed to persist reviewed draft") from exc


@scoped_router.get("/tasks", response_model=TaskListResponse)
def list_tasks(
    limit: int = Query(default=100, ge=1, le=1000, description="Maximum number of tasks to return"),
    offset: int = Query(default=0, ge=0, description="Number of tasks to skip"),
    status: Optional[TaskStatus] = Query(default=None, description="Filter by task status"),
    tenant: Tenant = Depends(tenant_context_dependency),
):
    """List all tasks with optional status filtering and pagination (scoped to X-Tenant-Id)."""
    tenant_id = tenant.id
    with Session(engine) as session:
        if status:
            tasks = task_repo.list_tasks_by_status(status, limit=limit, tenant_id=tenant_id)
            statement = select(Task).where(
                Task.status == status,
                Task.tenant_id == tenant_id,
            )
            total = len(list(session.exec(statement).all()))
        else:
            tasks = task_repo.list_all_tasks(limit=limit, offset=offset, tenant_id=tenant_id)
            statement = select(Task).where(Task.tenant_id == tenant_id)
            total = len(list(session.exec(statement).all()))
        
        return TaskListResponse(
            tasks=[TaskResponse.model_validate(task) for task in tasks],
            total=total,
            limit=limit,
            offset=offset,
        )


@scoped_router.get("/tasks/{task_id}", response_model=TaskResponse)
def get_task(
    task_id: UUID,
    tenant: Tenant = Depends(tenant_context_dependency),
):
    """Get a specific task by ID.
    
    Args:
        task_id: UUID of the task
        
    Returns:
        Task details
        
    Raises:
        HTTPException: 404 if task not found
    """
    task = _task_for_current_tenant_or_404(task_id, tenant)
    
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


@scoped_router.post("/tasks", response_model=TaskResponse, status_code=201)
def create_task(
    task_data: TaskCreate,
    tenant: Tenant = Depends(tenant_context_dependency),
):
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
        task.tenant_id = tenant.id
        
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


@scoped_router.put("/tasks/{task_id}", response_model=TaskResponse)
def update_task(
    task_id: UUID,
    task_data: TaskUpdate,
    tenant: Tenant = Depends(tenant_context_dependency),
):
    """Update an existing task.
    
    Args:
        task_id: UUID of the task to update
        task_data: Task update data
        
    Returns:
        Updated task
        
    Raises:
        HTTPException: 404 if task not found
    """
    task = _task_for_current_tenant_or_404(task_id, tenant)
    
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


@scoped_router.delete("/tasks/{task_id}", status_code=204)
def delete_task(
    task_id: UUID,
    tenant: Tenant = Depends(tenant_context_dependency),
):
    """Delete a task.
    
    Deletes all associated jobs first, then deletes the task.
    
    Args:
        task_id: UUID of the task to delete
        
    Raises:
        HTTPException: 404 if task not found
    """
    _task_for_current_tenant_or_404(task_id, tenant)
    
    with Session(engine) as session:
        task = session.get(Task, task_id)
        if not task:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
        # First, delete all jobs associated with this task
        statement = select(Job).where(Job.task_id == task_id)
        jobs = list(session.exec(statement).all())
        for job in jobs:
            session.delete(job)
        
        # Then delete the task
        session.delete(task)
        session.commit()
    
    return None


@scoped_router.post("/tasks/{task_id}/submit", response_model=TaskResponse)
def submit_task_for_approval(
    task_id: UUID,
    tenant: Tenant = Depends(tenant_context_dependency),
):
    """Submit a draft task for approval.
    
    Moves task from DRAFT to PENDING_APPROVAL.
    
    Args:
        task_id: UUID of the task to submit
        
    Returns:
        Updated task
        
    Raises:
        HTTPException: 404 if task not found, 400 if invalid status transition
    """
    _task_for_current_tenant_or_404(task_id, tenant)
    try:
        task = task_repo.submit_task_for_approval(task_id)
        return TaskResponse.model_validate(task)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@scoped_router.post("/tasks/{task_id}/approve-processing", response_model=TaskResponse)
def approve_task_for_processing(
    task_id: UUID,
    tenant: Tenant = Depends(tenant_context_dependency),
):
    """Approve a task for processing.
    
    Moves task from PENDING_APPROVAL to PROCESSING.
    
    Args:
        task_id: UUID of the task to approve
        
    Returns:
        Updated task
        
    Raises:
        HTTPException: 404 if task not found, 400 if invalid status transition
    """
    _task_for_current_tenant_or_404(task_id, tenant)
    try:
        task = task_repo.approve_task_for_processing(task_id)
        return TaskResponse.model_validate(task)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@scoped_router.post("/tasks/{task_id}/disapprove", response_model=TaskResponse)
def disapprove_task(
    task_id: UUID,
    tenant: Tenant = Depends(tenant_context_dependency),
):
    """Disapprove a task from processing.
    
    Moves task from PENDING_APPROVAL to DISAPPROVED.
    
    Args:
        task_id: UUID of the task to disapprove
        
    Returns:
        Updated task
        
    Raises:
        HTTPException: 404 if task not found, 400 if invalid status transition
    """
    _task_for_current_tenant_or_404(task_id, tenant)
    try:
        task = task_repo.disapprove_task(task_id)
        return TaskResponse.model_validate(task)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@scoped_router.post("/tasks/{task_id}/approve-publication", response_model=TaskResponse)
def approve_task_for_publication(
    task_id: UUID,
    tenant: Tenant = Depends(tenant_context_dependency),
):
    """Approve a task for publication.
    
    Moves task from PENDING_CONFIRMATION to READY.
    
    Args:
        task_id: UUID of the task to approve
        
    Returns:
        Updated task
        
    Raises:
        HTTPException: 404 if task not found, 400 if invalid status transition
    """
    _task_for_current_tenant_or_404(task_id, tenant)
    try:
        task = task_repo.approve_task_for_publication(task_id)
        return TaskResponse.model_validate(task)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@scoped_router.post("/tasks/{task_id}/publish", response_model=TaskResponse)
def publish_task(
    task_id: UUID,
    tenant: Tenant = Depends(tenant_context_dependency),
):
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
    task = _task_for_current_tenant_or_404(task_id, tenant)
    
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
        task = _task_for_current_tenant_or_404(task_id, tenant)
        return TaskResponse.model_validate(task)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to publish task: {str(e)}")


@scoped_router.post("/tasks/{task_id}/reject", response_model=TaskResponse)
def reject_task(
    task_id: UUID,
    tenant: Tenant = Depends(tenant_context_dependency),
):
    """Reject a task from publication.
    
    Moves task from PENDING_CONFIRMATION to REJECTED.
    
    Args:
        task_id: UUID of the task to reject
        
    Returns:
        Updated task
        
    Raises:
        HTTPException: 404 if task not found, 400 if invalid status transition
    """
    _task_for_current_tenant_or_404(task_id, tenant)
    try:
        task = task_repo.reject_task(task_id)
        return TaskResponse.model_validate(task)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@scoped_router.post("/tasks/{task_id}/override-processing", response_model=TaskResponse)
def override_task_processing(
    task_id: UUID,
    tenant: Tenant = Depends(tenant_context_dependency),
):
    """Override processing and move task to PENDING_CONFIRMATION.
    
    Moves task from PROCESSING to PENDING_CONFIRMATION regardless of generator state.
    
    Args:
        task_id: UUID of the task to override
        
    Returns:
        Updated task
        
    Raises:
        HTTPException: 404 if task not found, 400 if invalid status transition
    """
    _task_for_current_tenant_or_404(task_id, tenant)
    try:
        task = task_repo.override_task_processing(task_id)
        return TaskResponse.model_validate(task)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@scoped_router.get("/tasks/status/{status}", response_model=TaskListResponse)
def list_tasks_by_status_route(
    status: TaskStatus,
    limit: int = Query(default=100, ge=1, le=1000, description="Maximum number of tasks to return"),
    tenant: Tenant = Depends(tenant_context_dependency),
):
    """List tasks filtered by status (scoped to X-Tenant-Id)."""
    tenant_id = tenant.id
    tasks = task_repo.list_tasks_by_status(status, limit=limit, tenant_id=tenant_id)
    
    with Session(engine) as session:
        statement = select(Task).where(
            Task.status == status,
            Task.tenant_id == tenant_id,
        )
        total = len(list(session.exec(statement).all()))
    
    return TaskListResponse(
        tasks=[TaskResponse.model_validate(task) for task in tasks],
        total=total,
        limit=limit,
        offset=0,
    )


@scoped_router.post("/tasks/{task_id}/jobs", response_model=JobResponse, status_code=201)
def create_job(
    task_id: UUID,
    job_data: JobCreate,
    tenant: Tenant = Depends(tenant_context_dependency),
):
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
    
    # Verify task exists and belongs to current tenant
    _task_for_current_tenant_or_404(task_id, tenant)
    
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


@scoped_router.put("/tasks/{task_id}/jobs/{job_id}", response_model=JobResponse)
def update_job(
    task_id: UUID,
    job_id: UUID,
    job_data: JobUpdate,
    tenant: Tenant = Depends(tenant_context_dependency),
):
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
    _task_for_current_tenant_or_404(task_id, tenant)
    
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


@scoped_router.delete("/tasks/{task_id}/jobs/{job_id}", status_code=204)
def delete_job(
    task_id: UUID,
    job_id: UUID,
    tenant: Tenant = Depends(tenant_context_dependency),
):
    """Delete a job.
    
    Args:
        task_id: UUID of the parent task
        job_id: UUID of the job to delete
        
    Raises:
        HTTPException: 404 if task or job not found, 400 if database error occurs
    """
    _task_for_current_tenant_or_404(task_id, tenant)
    
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


@scoped_router.post("/tasks/{task_id}/jobs/{job_id}/process", response_model=JobResponse)
def process_job(
    task_id: UUID,
    job_id: UUID,
    tenant: Tenant = Depends(tenant_context_dependency),
):
    """Process a job using the appropriate generator.
    
    Args:
        task_id: UUID of the parent task
        job_id: UUID of the job to process
        
    Returns:
        Updated job after processing
        
    Raises:
        HTTPException: 404 if task or job not found, 400/500 on processing errors
    """
    _task_for_current_tenant_or_404(task_id, tenant)
    
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


@scoped_router.get("/templates/{template_name}")
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
