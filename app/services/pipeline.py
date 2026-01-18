"""Pipeline orchestrator logic."""

import sys
from typing import Optional

from app.models.task import Task, TaskStatus
from app.services.task_repo import create_task, save, mark_failed
from app.services.task_generator import TaskGenerator
from app.services.image_generator import ImageGenerator
from app.db.engine import create_tables
from app.config import DEFAULT_IMAGE_GENERATOR


def run_pipeline() -> Optional[Task]:
    """Run the complete cosplay kitten image pipeline.
    
    Steps:
    1. Create task in database
    2. Generate cosplay kitten prompt
    3. Generate image with cosplay kitten
    4. Mark task as completed
    
    Returns:
        Task object if successful, None if failed
        
    Raises:
        Exception: Re-raises any exception after marking task as failed
    """
    # Initialize database tables
    create_tables()
    
    # Initialize services
    task_generator = TaskGenerator()
    image_generator = ImageGenerator()
    
    task: Optional[Task] = None
    
    try:
        # Step 1: Create task
        task = create_task()
        # Set image generator from config (if not already set)
        if not task.image_generator:
            task.image_generator = DEFAULT_IMAGE_GENERATOR
        print(f"Created task: {task.id} (image_generator: {task.image_generator})")
        task.start_processing()
        task = save(task)
        
        # Step 2: Generate cosplay kitten prompt and image prompt
        cosplay_prompt = task_generator.generate(task)
        image_prompt = task_generator.generate_image_prompt(cosplay_prompt)
        task.mark_quote_ready(cosplay_prompt)
        task.image_generator_prompt = image_prompt
        task = save(task)
        print(f"Generated cosplay kitten prompt for task {task.id}")
        print(f"Generated image prompt for task {task.id}")
        
        # Step 3: Generate image
        image_path = image_generator.render(task)
        task.mark_image_ready(image_path)
        task = save(task)
        print(f"Generated image for task {task.id}: {image_path}")
        
        # Pipeline ends at READY (no publisher/scheduling in MVP)
        print(f"Task {task.id} ready at status {task.status.value}")
        
        return task
        
    except Exception as e:
        error_msg = str(e)
        print(f"Pipeline failed: {error_msg}", file=sys.stderr)
        
        if task:
            mark_failed(task, error_msg)
            print(f"Task {task.id} marked as FAILED")
        
        raise

