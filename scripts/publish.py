"""Script to publish a task to Instagram.

Usage:
    python scripts/publish.py <task_id>
"""

import sys
import argparse
from pathlib import Path
from uuid import UUID
import requests

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.services.task_repo import get_task_by_id, save
from app.services.instagram_publisher import InstagramPublisher
from app.models.task import TaskStatus
from app.config import PROJECT_ROOT


def main():
    """Publish a task to Instagram.
    
    Exits with code 0 on success, non-zero on failure.
    """
    parser = argparse.ArgumentParser(
        description="Publish a task to Instagram",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/publish.py 123e4567-e89b-12d3-a456-426614174000
        """
    )
    parser.add_argument(
        "task_id",
        type=str,
        help="UUID of the task to publish"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate task and show what would be published without actually posting"
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
        task = get_task_by_id(task_uuid)
        if not task:
            print(f"Error: Task {task_uuid} not found", file=sys.stderr)
            sys.exit(1)
        
        # Validate task status
        if task.status != TaskStatus.READY:
            print(f"Error: Task is in status '{task.status.value}', expected 'ready'", file=sys.stderr)
            print("Only tasks with status 'ready' can be published", file=sys.stderr)
            sys.exit(1)
        
        # Validate task has image
        if not task.image_path:
            print("Error: Task has no image path", file=sys.stderr)
            sys.exit(1)
        
        # Handle image path - can be URL or local file
        image_path_str = task.image_path
        image_path = None
        
        # Check if it's a URL
        if image_path_str.startswith(("http://", "https://")):
            # It's a URL, use it directly
            image_path = image_path_str
            print(f"Using image URL: {image_path}")
        else:
            # It's a local file path
            image_path = Path(image_path_str)
            if not image_path.is_absolute():
                # Assume relative to project root or output directory
                image_path = PROJECT_ROOT / image_path
                if not image_path.exists():
                    # Try output/images directory
                    image_path = PROJECT_ROOT / "output" / "images" / Path(image_path_str).name
            
            if not image_path.exists():
                print(f"Error: Image file not found: {image_path}", file=sys.stderr)
                sys.exit(1)
            print(f"Using local image file: {image_path}")
        
        # Prepare caption
        caption_parts = []
        if task.quote_text:
            caption_parts.append(task.quote_text)
        if task.caption_text:
            caption_parts.append(task.caption_text)
        caption = "\n\n".join(caption_parts) if caption_parts else ""
        
        # Dry run mode
        if args.dry_run:
            print("DRY RUN MODE - No actual posting will occur")
            print(f"\nTask ID: {task.id}")
            print(f"Status: {task.status.value}")
            print(f"Image: {image_path}")
            print(f"Caption: {caption[:100]}{'...' if len(caption) > 100 else ''}")
            print("\nTask is ready for publishing!")
            sys.exit(0)
        
        # Publish to Instagram
        print(f"Publishing task {task.id} to Instagram...")
        print(f"Image: {image_path}")
        print(f"Caption: {caption[:100]}{'...' if len(caption) > 100 else ''}")
        
        try:
            publisher = InstagramPublisher()
            result = publisher.publish_image(image_path, caption)
            
            # Update task metadata with Instagram post info
            if task.meta is None:
                task.meta = {}
            task.meta["instagram_media_id"] = result["id"]
            task.meta["instagram_permalink"] = result.get("permalink", "")
            task.meta["instagram_published_at"] = str(Path(__file__).stat().st_mtime)  # Current timestamp
            
            # Mark task as published
            task.mark_published()
            task = save(task)
            
            print(f"\n✓ Successfully published to Instagram!")
            print(f"Media ID: {result['id']}")
            if result.get("permalink"):
                print(f"Post URL: {result['permalink']}")
            print(f"Task status updated to: {task.status.value}")
            sys.exit(0)
            
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        except requests.RequestException as e:
            print(f"Instagram API error: {e}", file=sys.stderr)
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_data = e.response.json()
                    print(f"API Error Details: {error_data}", file=sys.stderr)
                except:
                    print(f"Response: {e.response.text}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"Unexpected error: {e}", file=sys.stderr)
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
