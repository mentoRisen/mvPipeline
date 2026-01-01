"""Pipeline orchestrator logic."""

import sys
from typing import Optional

from app.models.task import Task, TaskStatus
from app.services.task_repo import create_task, save, mark_failed
from app.services.quote_generator import QuoteGenerator
from app.services.image_generator import ImageGenerator
from app.db.engine import create_tables


def run_pipeline() -> Optional[Task]:
    """Run the complete quote-image pipeline.
    
    Steps:
    1. Create task in database
    2. Generate quote text
    3. Generate image with quote
    4. Mark task as completed
    
    Returns:
        Task object if successful, None if failed
        
    Raises:
        Exception: Re-raises any exception after marking task as failed
    """
    # Initialize database tables
    create_tables()
    
    # Initialize services
    quote_generator = QuoteGenerator()
    image_generator = ImageGenerator()
    
    task: Optional[Task] = None
    
    try:
        # Step 1: Create task
        task = create_task()
        print(f"Created task: {task.id}")
        task.start_processing()
        task = save(task)
        
        # Step 2: Generate quote
        quote_text = quote_generator.generate(task)
        task.mark_quote_ready(quote_text)
        task = save(task)
        print(f"Generated quote for task {task.id}")
        
        # Step 3: Generate image
        image_path = image_generator.render(task)
        task.mark_image_ready(image_path)
        task = save(task)
        print(f"Generated image for task {task.id}: {image_path}")
        
        # Pipeline ends at IMAGE_READY (no publisher/scheduling in MVP)
        print(f"Task {task.id} ready at status {task.status.value}")
        
        return task
        
    except Exception as e:
        error_msg = str(e)
        print(f"Pipeline failed: {error_msg}", file=sys.stderr)
        
        if task:
            mark_failed(task, error_msg)
            print(f"Task {task.id} marked as FAILED")
        
        raise

