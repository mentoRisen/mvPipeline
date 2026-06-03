---
title: Per-task job reference_id slots and assignment service
date: 2026-06-03
category: architecture-patterns
module: jobs
problem_type: architecture_pattern
component: service_object
severity: medium
applies_when:
  - Adding stable per-task identifiers on Job separate from display order
  - Introducing a new Job column with existing production rows
  - Multiple job creation paths must share assignment and uniqueness rules
resolution_type: migration
related_components:
  - database
  - api
  - frontend
tags:
  - reference-id
  - job
  - sync-schema
  - backfill
  - assignment-service
  - task-jobs
  - instagram-publish
---

# Per-task job reference_id slots and assignment service

## Context

Jobs already had UUID primary keys and an `order` field for UI reordering. UUIDs are awkward in JSON/AI drafts, and many jobs share `order=0`, so list ordering fell back to `created_at` — not a stable slot identity. The product needed a small integer handle per task (`1`, `2`, `3`…) for tie-breaking after `order` and for future job-to-job references (processor resolution deferred).

Plan reference: `docs/plans/2026-06-02-001-feat-job-reference-id-plan.md`.

## Guidance

### Two fields, two roles

- **`reference_id`**: create-only, per-task slot; unique within `(task_id, reference_id)`.
- **`order`**: display/rendering sequence; independent of `reference_id`.

### Single assignment boundary

All creation paths call `app/services/job_reference_service.py`:

- `resolve_reference_id(session, task_id, explicit)` — single REST create.
- `assign_reference_ids_for_new_jobs(session, task_id, explicit_list)` — AI bundle / batch (sequential auto slots in iteration order, not repeated `max+1` reads per row).
- Reject duplicate explicit IDs (DB and within-batch) with `JobReferenceValidationError`; no silent auto-bump.

Wire through `task_repo.create_task_bundle_with_jobs(..., explicit_reference_ids_per_bundle=...)` and `create_job` in `app/api/routes.py`. Custom `bundle_writer` callables must accept `**kwargs` for the explicit-ID kwarg.

### Canonical job list sort

Use `list_jobs_for_task_ordered()` / `jobs_for_task_ordered_statement()` everywhere task-scoped job sequence matters:

`order DESC → reference_id ASC → created_at ASC`

Applied at minimum on `GET /tasks/{id}` and Instagram publish (`publisher_instagram.py`). Worker pick order unchanged (`created_at` only).

### Schema rollout (MySQL, no Alembic)

Ordered deploy on production:

```bash
python scripts/sync_schema.py          # ADD COLUMN reference_id NULL via ADD_COLUMN_DDL
python scripts/backfill_job_reference_ids.py   # per-task 1..N by created_at, id; NOT NULL + unique index
sudo systemctl restart mvpipeline-api.service
```

Documented in `docs/deployment-hetzner-flow-mentoverse.md`. Backfill is idempotent; script uses MySQL-specific `MODIFY COLUMN` — not for SQLite test DBs (tests use SQLModel `create_all` with non-null column from the model).

### API contract

- `JobResponse.reference_id` on read.
- Optional `reference_id` (≥1) on create schemas (`JobCreate`, `AiDraftJob`).
- Reject `reference_id` on `JobUpdate` (422).
- Map `(task_id, reference_id)` unique violations to 422 via pre-validation and `integrity_error_to_validation()` on `create_job`.

### UI

TaskDetail jobs table shows **Ref** column (read-only). Client `instagramImageJobs` sort matches the three-key API order.

## Why This Matters

Duplicating `max+1` logic in routes, AI confirm, and JSON import drifts quickly (plan requirement R9/R16). A shared service plus DB unique index gives friendly 422s under normal use and a hard guarantee under concurrency. Skipping backfill before NOT NULL breaks deploy; skipping the shared sort helper breaks publish vs task-detail ordering.

## When to Apply

- Any new job creation entry point must use the assignment service before flush/commit.
- Any new task-scoped job query that affects user-visible sequence or publish order must use `list_jobs_for_task_ordered()`.
- Do not renumber slots after deletes (gaps OK).
- Do not change worker ordering to use `reference_id` unless explicitly specified.

## Examples

**Auto-assign on create (REST):**

```python
reference_id = resolve_reference_id(session, task_id, job_data.reference_id)
job = Job(task_id=task_id, reference_id=reference_id, ...)
```

**Batch assign in bundle writer:**

```python
assigned = assign_reference_ids_for_new_jobs(session, task.id, [None, None, 3])
# → e.g. [1, 2, 3] on empty task, or continues after max existing
```

**Ordered load:**

```python
jobs = list_jobs_for_task_ordered(session, task_id, purpose="imagecontent")
```

## Related

- `docs/decisions/001-shared-application-workflows.md` — shared service boundary
- `docs/brainstorms/2026-06-01-job-reference-id-requirements.md` — origin requirements
- `docs/solutions/architecture-patterns/ai-draft-backend-prompt-wiring-2026-05-22.md` — similar `sync_schema.py` additive column pattern
- Code review follow-up: map `IntegrityError` to 422 on `ai-draft-confirm` the same way as `create_job` for concurrent duplicate slots
