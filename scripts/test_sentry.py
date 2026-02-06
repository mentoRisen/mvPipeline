"""Test script to send a tenant-tagged event to Sentry.

Usage examples:
    python -m scripts.test_sentry --tenant-id=<TENANT_ID>
    python -m scripts.test_sentry -t <TENANT_ID> --level=warning
    python -m scripts.test_sentry -t <TENANT_ID> --environment=staging

This script is meant for validating that:
    - Sentry is correctly configured for this project.
    - Events are tagged with `tenant_id` so Sentry can route them
      (e.g. to Discord via alert rules configured per tenant).
"""

import argparse
import logging
import os
import sys
from pathlib import Path

# Ensure project root is on sys.path for imports, similar to other scripts.
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import app.config early so that its side-effect of loading the .env file
# (via python-dotenv) is applied before we read environment variables.
from app import config  # noqa: E402, F401

import sentry_sdk  # noqa: E402

from app.sentry_setup import init_sentry  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Send a tenant-tagged test event to Sentry."
    )

    parser.add_argument(
        "-t",
        "--tenant-id",
        required=True,
        help="Tenant identifier to attach as a Sentry tag (tenant_id).",
    )
    parser.add_argument(
        "-m",
        "--message",
        help=(
            "Optional custom message for the Sentry event. "
            "Defaults to a standard test message including tenant_id."
        ),
    )
    parser.add_argument(
        "-l",
        "--level",
        choices=["info", "warning", "error"],
        default="error",
        help="Log level for the event (default: error).",
    )
    parser.add_argument(
        "-e",
        "--environment",
        help=(
            "Optional environment override for this run "
            "(e.g. dev, staging, prod). If not provided, "
            "SENTRY_ENVIRONMENT will be used or default to 'dev'."
        ),
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    # Optionally override environment just for this invocation.
    if args.environment:
        os.environ["SENTRY_ENVIRONMENT"] = args.environment

    dsn = os.getenv("SENTRY_DSN")
    if not dsn:
        print(
            "SENTRY_DSN environment variable is not set. "
            "Configure it and try again.",
            file=sys.stderr,
        )
        return 1

    # Initialize Sentry using the shared helper.
    init_sentry()

    environment = os.getenv("SENTRY_ENVIRONMENT", "dev")

    message = args.message or (
        f"Test Sentry log event for tenant '{args.tenant_id}' "
        f"(level={args.level}, environment={environment})"
    )

    # Map CLI level to Python logging level.
    level_map = {
        "info": logging.INFO,
        "warning": logging.WARNING,
        "error": logging.ERROR,
    }
    log_level = level_map.get(args.level, logging.ERROR)

    # Attach tenant-specific tags on the Sentry scope, then emit a log record.
    with sentry_sdk.configure_scope() as scope:
        scope.set_tag("tenant_id", args.tenant_id)
        scope.set_tag("component", "scripts_test_sentry")

    logger = logging.getLogger("scripts.test_sentry")
    logger.log(log_level, message)

    print("\nSentry test event sent.")
    print(f"  tenant_id   : {args.tenant_id}")
    print(f"  level       : {args.level}")
    print(f"  environment : {environment}")
    print(f"  message     : {message}")
    print(f"  SENTRY_DSN  : {'configured' if dsn else 'missing'}")
    print(
        "\nIn Sentry, filter events by tag tenant_id="
        f"'{args.tenant_id}' to find this test event."
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

