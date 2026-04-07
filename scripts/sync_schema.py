"""Sync SQLModel schema and verify critical AI draft columns/tables.

Usage:
    python scripts/sync_schema.py
    python scripts/sync_schema.py --check-only
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy import inspect

# Ensure the project root is on sys.path so `app` can be imported.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.engine import create_tables, engine  # noqa: E402  pylint: disable=wrong-import-position


REQUIRED_TABLE_COLUMNS = {
    "ai_draft_sessions": {
        "id",
        "tenant_id",
        "user_id",
        "brief",
        "bundle",
        "last_error",
        "status",
        "preview_status",
        "expires_at",
        "created_at",
        "updated_at",
    },
    "ai_draft_communication_events": {
        "id",
        "draft_session_id",
        "sequence",
        "kind",
        "payload",
        "created_at",
    },
}

ADD_COLUMN_DDL = {
    "ai_draft_sessions": {
        # Existing deployments created this table before async preview lifecycle existed.
        "preview_status": "ALTER TABLE ai_draft_sessions ADD COLUMN preview_status VARCHAR(32) NOT NULL DEFAULT 'succeeded'",
    },
}


def _run_checks(verbose: bool = False) -> tuple[bool, list[str]]:
    inspector = inspect(engine)
    failures: list[str] = []
    details: list[str] = []

    for table, required_columns in REQUIRED_TABLE_COLUMNS.items():
        if not inspector.has_table(table):
            failures.append(f"missing table: {table}")
            continue
        existing_columns = {col["name"] for col in inspector.get_columns(table)}
        missing_columns = sorted(required_columns - existing_columns)
        if missing_columns:
            failures.append(
                f"table {table} missing columns: {', '.join(missing_columns)}"
            )
        elif verbose:
            details.append(f"table {table}: OK ({len(existing_columns)} columns)")

    return len(failures) == 0, details + failures


def _apply_missing_additive_changes(verbose: bool = False) -> list[str]:
    """Apply safe additive schema changes for known rollout gaps."""

    inspector = inspect(engine)
    applied: list[str] = []

    with engine.begin() as conn:
        for table, column_ddls in ADD_COLUMN_DDL.items():
            if not inspector.has_table(table):
                continue
            existing_columns = {col["name"] for col in inspector.get_columns(table)}
            for column, ddl in column_ddls.items():
                if column in existing_columns:
                    continue
                conn.execute(text(ddl))
                applied.append(f"applied: {table}.{column}")
                if verbose:
                    print(f"[apply] {table}.{column}")  # noqa: T201

    return applied


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run SQLModel create_all sync, then verify AI draft schema shape.",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Do not apply create_all; only verify current schema.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print extra success details.",
    )
    args = parser.parse_args()

    if not args.check_only:
        print("Applying SQLModel.metadata.create_all ...")  # noqa: T201
        create_tables()
        print("Schema sync apply step complete.")  # noqa: T201
        applied = _apply_missing_additive_changes(verbose=args.verbose)
        if applied:
            print(f"Applied additive schema updates: {len(applied)}")  # noqa: T201

    ok, messages = _run_checks(verbose=args.verbose)
    for msg in messages:
        prefix = "[ok]" if not msg.startswith("missing") and "missing columns" not in msg else "[fail]"
        print(f"{prefix} {msg}")  # noqa: T201

    if ok:
        print("Schema checks passed.")  # noqa: T201
        return

    raise SystemExit("Schema checks failed.")


if __name__ == "__main__":
    main()
