"""One-time backfill for jobs.reference_id and enforcement of constraints.

Run after sync_schema adds the nullable column:
    python scripts/sync_schema.py
    python scripts/backfill_job_reference_ids.py

Idempotent: rows that already have reference_id are left unchanged; remaining
rows per task receive 1..N ordered by created_at ASC, id ASC.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy import inspect, text

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.engine import engine  # noqa: E402


def _column_nullable(inspector, table: str, column: str) -> bool | None:
    for col in inspector.get_columns(table):
        if col["name"] == column:
            return col.get("nullable", True)
    return None


def _has_unique_task_reference_index(inspector) -> bool:
    for idx in inspector.get_indexes("jobs"):
        cols = idx.get("column_names") or []
        if cols == ["task_id", "reference_id"] and idx.get("unique"):
            return True
    return False


def backfill(*, dry_run: bool = False, verbose: bool = False) -> int:
    inspector = inspect(engine)
    if not inspector.has_table("jobs"):
        print("jobs table does not exist", file=sys.stderr)
        return 1
    columns = {col["name"] for col in inspector.get_columns("jobs")}
    if "reference_id" not in columns:
        print(
            "jobs.reference_id column missing; run scripts/sync_schema.py first",
            file=sys.stderr,
        )
        return 1

    updated = 0
    with engine.begin() as conn:
        task_ids = conn.execute(
            text("SELECT DISTINCT task_id FROM jobs ORDER BY task_id")
        ).scalars().all()
        for task_id in task_ids:
            rows = conn.execute(
                text(
                    """
                    SELECT id, reference_id
                    FROM jobs
                    WHERE task_id = :task_id
                    ORDER BY created_at ASC, id ASC
                    """
                ),
                {"task_id": task_id},
            ).fetchall()
            next_slot = 1
            for row in rows:
                if row.reference_id is not None:
                    next_slot = max(next_slot, int(row.reference_id) + 1)
                    continue
                if dry_run:
                    if verbose:
                        print(f"[dry-run] task {task_id} job {row.id} -> {next_slot}")
                else:
                    conn.execute(
                        text(
                            "UPDATE jobs SET reference_id = :ref WHERE id = :id"
                        ),
                        {"ref": next_slot, "id": row.id},
                    )
                updated += 1
                next_slot += 1

        if dry_run:
            print(f"[dry-run] would assign reference_id on {updated} job(s)")
            return 0

        nullable = _column_nullable(inspector, "jobs", "reference_id")
        if nullable:
            conn.execute(
                text("ALTER TABLE jobs MODIFY COLUMN reference_id INT NOT NULL")
            )
            if verbose:
                print("[apply] jobs.reference_id NOT NULL")

        if not _has_unique_task_reference_index(inspector):
            conn.execute(
                text(
                    "CREATE UNIQUE INDEX uq_jobs_task_reference "
                    "ON jobs (task_id, reference_id)"
                )
            )
            if verbose:
                print("[apply] UNIQUE INDEX uq_jobs_task_reference")

    print(f"Backfill complete; assigned reference_id on {updated} job(s)")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report rows that would be updated without writing",
    )
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    raise SystemExit(backfill(dry_run=args.dry_run, verbose=args.verbose))


if __name__ == "__main__":
    main()
