"""Utility script to bootstrap the first application user."""

from __future__ import annotations

import argparse
import sys
from getpass import getpass
from pathlib import Path

# Ensure the project root is on sys.path so `app` can be imported.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services import auth as auth_service  # noqa: E402  pylint: disable=wrong-import-position
from app.services import user_repo  # noqa: E402  pylint: disable=wrong-import-position


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a Mentoverse Pipeline user")
    parser.add_argument("--username", required=True, help="Login username")
    parser.add_argument("--email", help="Optional email address")
    parser.add_argument(
        "--password",
        help="Password (omit to be prompted interactively)",
    )
    args = parser.parse_args()

    password = args.password or getpass("Password: ")
    if not password:
        raise SystemExit("Password cannot be empty")

    existing = user_repo.get_user_by_username(args.username)
    if existing:
        raise SystemExit(f"User '{args.username}' already exists.")

    hashed = auth_service.get_password_hash(password)
    user = user_repo.create_user(
        username=args.username,
        hashed_password=hashed,
        email=args.email,
        is_active=True,
    )
    print(f"Created user '{user.username}' with id={user.id}")  # noqa: T201


if __name__ == "__main__":
    main()
