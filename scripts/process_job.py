"""Script to process a job.

Usage:
    python scripts/process_job.py <job_id>
"""

import sys
import argparse
from pathlib import Path
from uuid import UUID

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlmodel import Session, select
from app.models.job import Job
from app.db.engine import engine
from app.services.jobs.processor import process_job


def main():
    """Process a job.
    
    Exits with code 0 on success, non-zero on failure.
    """
    parser = argparse.ArgumentParser(
        description="Process a job",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/process_job.py 123e4567-e89b-12d3-a456-426614174000
        """
    )
    parser.add_argument(
        "job_id",
        type=str,
        help="UUID of the job to process"
    )
    
    args = parser.parse_args()
    
    try:
        # Parse job ID
        try:
            job_uuid = UUID(args.job_id)
        except ValueError:
            print(f"Error: Invalid job ID format: {args.job_id}", file=sys.stderr)
            print("Job ID must be a valid UUID", file=sys.stderr)
            sys.exit(1)
        
        # Get job from database
        with Session(engine) as session:
            statement = select(Job).where(Job.id == job_uuid)
            job = session.exec(statement).first()
            
            if not job:
                print(f"Error: Job {job_uuid} not found", file=sys.stderr)
                sys.exit(1)
            
            # Process the job
            try:
                process_job(job)
                print(f"Job {job_uuid} processed successfully")
                sys.exit(0)
            except ValueError as e:
                print(f"Error: {e}", file=sys.stderr)
                sys.exit(1)
            except Exception as e:
                print(f"Unexpected error processing job: {e}", file=sys.stderr)
                import traceback
                traceback.print_exc()
                sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\nProcessing cancelled by user", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
