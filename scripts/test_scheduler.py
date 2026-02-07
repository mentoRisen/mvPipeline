"""Test script for the scheduler worker.

Usage:
    python -m scripts.test_scheduler --tenant-id=<UUID>
"""

import argparse
import logging
import sys
from pathlib import Path
from uuid import UUID

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.context import init_context_by_tenant  # noqa: E402
from app.services.scheduler import run_worker  # noqa: E402


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s [%(name)s] %(message)s",
    )
    parser = argparse.ArgumentParser(
        description="Run the scheduler worker for a tenant (current timeslot, matching rules).",
    )
    parser.add_argument(
        "--tenant-id",
        required=True,
        type=UUID,
        help="Tenant UUID to run the scheduler for.",
    )
    args = parser.parse_args()
    init_context_by_tenant(args.tenant_id)
    run_worker()


if __name__ == "__main__":
    main()
