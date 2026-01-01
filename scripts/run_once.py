"""CLI runner script for one-time pipeline execution."""

import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.services.pipeline import run_pipeline


def main():
    """Run the pipeline once.
    
    Exits with code 0 on success, non-zero on failure.
    """
    try:
        task = run_pipeline()
        
        if task:
            print(f"\nPipeline completed successfully")
            print(f"Task ID: {task.id}")
            print(f"Final Status: {task.status.value}")
            sys.exit(0)
        else:
            print("Pipeline failed: No task returned", file=sys.stderr)
            sys.exit(1)
            
    except Exception as e:
        print(f"\nPipeline failed with error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

