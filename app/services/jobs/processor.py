"""Job processor module.

Contains functions to process jobs in the pipeline.
"""

import logging
from datetime import datetime
import traceback

from sqlmodel import Session, select
from app.models.job import Job, JobStatus
from app.models.task import Task, TaskStatus
from app.models.tenant import Tenant
from app.db.engine import engine
from app.services.public_url import public_url_for_image_path

logger = logging.getLogger(__name__)


def process_job(job: Job) -> None:
    """Process a job entity.
    
    Routes to appropriate processor based on job.generator type.
    Handles status updates and result saving.
    
    Args:
        job: The job entity to process
        
    Raises:
        ValueError: If job status is not READY or if generator type is unknown
    """
    # Allow processing when job is in READY or ERROR state (for retries/testing)
    # job.status may be a raw string or an enum; handle both
    current_status = job.status.value if isinstance(job.status, JobStatus) else str(job.status)
    allowed_statuses = {JobStatus.READY.value, JobStatus.ERROR.value}
    if current_status not in allowed_statuses:
        raise ValueError(
            f"Job {job.id} is not in a processable state. "
            f"Current status: {current_status}. "
            f"Allowed statuses: {', '.join(sorted(allowed_statuses))}"
        )
    
    # Create session for database operations
    with Session(engine) as session:
        # Fetch fresh job instance to ensure it's attached to session
        statement = select(Job).where(Job.id == job.id)
        db_job = session.exec(statement).first()
        
        if not db_job:
            raise ValueError(f"Job {job.id} not found in database")
        
        try:
            # Update job status to PROCESSING
            db_job.status = JobStatus.PROCESSING
            db_job.updated_at = datetime.utcnow()
            session.add(db_job)
            session.commit()
            session.refresh(db_job)
            
            logger.info(f"Processing job {job.id} with generator: {job.generator}")
            
            # Route to appropriate processor based on generator type
            generator_type = (job.generator or "").lower()
            if generator_type == "dalle":
                from app.services.jobs.processor_dalle import generate_image as generate_image_dalle
                # Validate prompt exists
                if not job.prompt or "prompt" not in job.prompt:
                    raise ValueError(f"Job {job.id} is missing prompt data")
                prompt_text = job.prompt.get("prompt")
                if not prompt_text:
                    raise ValueError(f"Job {job.id} prompt is empty")
                # Generate image using DALL-E
                image_path, image_url = generate_image_dalle(
                    prompt_text=prompt_text,
                    task_id=str(job.task_id),
                    job_id=str(job.id)
                )
                public_url = public_url_for_image_path(image_path)

                # Update job with success result
                db_job.status = JobStatus.PROCESSED
                db_job.result = {
                    "image_path": image_path,
                    "image_url": image_url,
                    "public_url": public_url,
                    "generator": generator_type,
                }
                db_job.updated_at = datetime.utcnow()
                session.add(db_job)
                session.commit()
                logger.info(f"Successfully processed job {job.id}. Image saved to {image_path}")
            elif generator_type == "gptimage15":
                from app.services.jobs.processor_gptimage15 import generate_image as generate_image_gpt
                # Validate prompt exists
                if not job.prompt or "prompt" not in job.prompt:
                    raise ValueError(f"Job {job.id} is missing prompt data")
                prompt_text = job.prompt.get("prompt")
                if not prompt_text:
                    raise ValueError(f"Job {job.id} prompt is empty")
                # Generate image using GPT-Image-1.5
                image_path = generate_image_gpt(
                    prompt_text=prompt_text,
                    task_id=str(job.task_id),
                    job_id=str(job.id)
                )
                public_url = public_url_for_image_path(image_path)

                # Update job with success result
                db_job.status = JobStatus.PROCESSED
                db_job.result = {
                    "image_path": image_path,
                    "public_url": public_url,
                    "generator": generator_type,
                }
                db_job.updated_at = datetime.utcnow()
                session.add(db_job)
                session.commit()
                logger.info(f"Successfully processed job {job.id} with GPT-Image-1.5. Image saved to {image_path}")
            elif generator_type == "gptimage2":
                from app.services.jobs.processor_gptimage2 import generate_image as generate_image_gpt2
                # Validate prompt exists
                if not job.prompt or "prompt" not in job.prompt:
                    raise ValueError(f"Job {job.id} is missing prompt data")
                prompt_text = job.prompt.get("prompt")
                if not prompt_text:
                    raise ValueError(f"Job {job.id} prompt is empty")
                # Generate image using GPT-Image-2
                image_path = generate_image_gpt2(
                    prompt_text=prompt_text,
                    task_id=str(job.task_id),
                    job_id=str(job.id)
                )
                public_url = public_url_for_image_path(image_path)

                # Update job with success result
                db_job.status = JobStatus.PROCESSED
                db_job.result = {
                    "image_path": image_path,
                    "public_url": public_url,
                    "generator": generator_type,
                }
                db_job.updated_at = datetime.utcnow()
                session.add(db_job)
                session.commit()
                logger.info(f"Successfully processed job {job.id} with GPT-Image-2. Image saved to {image_path}")
            elif generator_type == "runway-video":
                from app.config import RUNWAY_VIDEO_TIMEOUT_SECONDS
                from app.services.integrations.runway_config import resolve_runway_api_key
                from app.services.job_prompt_validation import (
                    resolve_processed_image_slot,
                    validate_runway_video_prompt,
                )
                from app.services.jobs.processor_runway_video import generate_video

                if not job.prompt:
                    raise ValueError(f"Job {job.id} is missing prompt data")
                normalized_prompt = validate_runway_video_prompt(job.prompt)
                image_slot = normalized_prompt["reference_id"]
                _image_job, image_path = resolve_processed_image_slot(
                    session,
                    job.task_id,
                    image_slot,
                )

                task_row = session.get(Task, job.task_id)
                tenant_env: dict = {}
                if task_row and task_row.tenant_id:
                    tenant_row = session.get(Tenant, task_row.tenant_id)
                    tenant_env = (tenant_row.env or {}) if tenant_row else {}
                api_key = resolve_runway_api_key(tenant_env=tenant_env)
                video_result = generate_video(
                    image_path=image_path,
                    prompt_text=normalized_prompt["prompt"],
                    model=normalized_prompt["model"],
                    task_id=str(job.task_id),
                    job_id=str(job.id),
                    api_key=api_key,
                    timeout_seconds=RUNWAY_VIDEO_TIMEOUT_SECONDS,
                )
                public_url = public_url_for_image_path(video_result["video_path"])

                db_job.status = JobStatus.PROCESSED
                db_job.result = {
                    "video_path": video_result["video_path"],
                    "public_url": public_url,
                    "generator": generator_type,
                }
                if video_result.get("runway_task_id"):
                    db_job.result["runway_task_id"] = video_result["runway_task_id"]
                if video_result.get("runway_url"):
                    db_job.result["runway_url"] = video_result["runway_url"]
                db_job.updated_at = datetime.utcnow()
                session.add(db_job)
                session.commit()
                logger.info(
                    "Successfully processed job %s with Runway video. Video saved to %s",
                    job.id,
                    video_result["video_path"],
                )
            else:
                raise ValueError(f"Unknown generator type: {job.generator}")
            
            # After successful job processing, if the parent task is in PROCESSING
            # and all its jobs are PROCESSED, move the task to PENDING_CONFIRMATION.
            task = session.get(Task, db_job.task_id)
            if task and task.status == TaskStatus.PROCESSING:
                jobs_stmt = select(Job).where(Job.task_id == db_job.task_id)
                all_jobs = list(session.exec(jobs_stmt).all())
                if all_jobs and all(j.status == JobStatus.PROCESSED for j in all_jobs):
                    task.status = TaskStatus.PENDING_CONFIRMATION
                    task.updated_at = datetime.utcnow()
                    session.add(task)
                    session.commit()
                    logger.info(
                        "All jobs for task %s processed; task moved to PENDING_CONFIRMATION",
                        task.id,
                    )

        except Exception as e:
            # Handle any errors with detailed traceback
            tb = traceback.format_exc()
            error_msg = f"{e.__class__.__name__}: {e}\n{tb}"
            
            # Update job with error status and full error details
            db_job.status = JobStatus.ERROR
            db_job.result = {
                "error": error_msg
            }
            db_job.updated_at = datetime.utcnow()
            session.add(db_job)
            session.commit()

            
            
            logger.error(f"Error processing job {job.id}: {error_msg}")
            raise
