"""Test script for the Discord notifier service.

Usage examples:
    python -m scripts.test_notifier --tenant-id=<TENANT_ID> --type=info --message="Hello"

This script calls app.services.notifier.notify(type, message) with the
tenant information included in the message text.
"""

import argparse
import sys
from pathlib import Path

# Add project root to path for imports (same pattern as other scripts).
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import app.config early so that its side-effect of loading the .env file
# (via python-dotenv) is applied before we read environment variables.
from app import config  # noqa: E402, F401

from app.context import init_context_by_tenant  # noqa: E402
from app.services.notifier import notify  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Send a test notification to Discord via the notifier service.",
    )
    parser.add_argument(
        "--tenant-id",
        required=True,
        help="Tenant identifier to include in the notification message.",
    )
    parser.add_argument(
        "--type",
        required=True,
        help='Logical type/category of the event (e.g. "info", "warning", "error").',
    )
    parser.add_argument(
        "--message",
        required=True,
        help="Message text to send.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    # Initialize context for the chosen tenant.
    init_context_by_tenant(args.tenant_id)

    # Now notifier will pick up the tenant from context.
    notify(args.type, args.message)

    print("Notifier test message sent (check your Discord channel).")
    print(f"  tenant_id: {args.tenant_id}")
    print(f"  type      : {args.type}")
    print(f"  message   : {args.message}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

