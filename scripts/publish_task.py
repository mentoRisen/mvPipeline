"""Script to publish a task.

Usage:
    python scripts/publish_task.py <task_id>
"""

import sys
import argparse
from pathlib import Path
from uuid import UUID

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Setup logging before importing other modules
from app.utils.logging_config import setup_logging
setup_logging()

from sqlmodel import Session, select
from app.models.task import Task
from app.db.engine import engine
from app.services.tasks.publisher import publish_task


def main():
    """Publish a task.
    
    Exits with code 0 on success, non-zero on failure.
    """
    parser = argparse.ArgumentParser(
        description="Publish a task",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/publish_task.py 123e4567-e89b-12d3-a456-426614174000
        """
    )
    parser.add_argument(
        "task_id",
        type=str,
        help="UUID of the task to publish"
    )
    
    args = parser.parse_args()
    
    try:
        # Parse task ID
        try:
            task_uuid = UUID(args.task_id)
        except ValueError:
            print(f"Error: Invalid task ID format: {args.task_id}", file=sys.stderr)
            print("Task ID must be a valid UUID", file=sys.stderr)
            sys.exit(1)
        
        # Get task from database
        with Session(engine) as session:
            statement = select(Task).where(Task.id == task_uuid)
            task = session.exec(statement).first()
            
            if not task:
                print(f"Error: Task {task_uuid} not found", file=sys.stderr)
                sys.exit(1)
            
            # Publish the task
            try:
                publish_task(task)
                print(f"Task {task_uuid} published successfully")
                sys.exit(0)
            except ValueError as e:
                print(f"Error: {e}", file=sys.stderr)
                sys.exit(1)
            except Exception as e:
                print(f"Unexpected error publishing task: {e}", file=sys.stderr)
                import traceback
                traceback.print_exc()
                sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\nPublishing cancelled by user", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
