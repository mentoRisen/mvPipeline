---
date: 2026-06-01
topic: job-reference-id
---

# Job reference_id

## Summary

Add a per-task integer `reference_id` on each `Job` as a stable slot identity (1, 2, 3…) separate from display `order`. New jobs receive `max(existing reference_id in task) + 1` when omitted; callers may set `reference_id` on create only. Existing jobs are backfilled per task by `created_at`. Task job lists sort by `order` descending, then `reference_id` ascending, then `created_at` ascending. Cross-job references inside prompts and processors are deferred to a later job-types effort.

---

## Problem Frame

Jobs under a task already have a UUID primary key and an `order` field for display/rendering sequence. UUIDs are poor handles for authors defining pipelines in JSON or AI drafts, and `order` is meant for UI reordering—not a stable, task-scoped slot number. Multiple jobs often share the same `order` (for example default `0`), so tie-breaking falls back to `created_at`, which does not reflect intentional pipeline sequence.

A dedicated `reference_id` gives each job a small, task-local identifier suitable for default list ordering (as a tie-breaker after `order`) and for future job-to-job references when job types support dependencies. The field is introduced now; resolution of references in prompts or processors is explicitly out of scope for this change.

---

## Requirements

**Data model and migration**
- R1. Each `Job` row stores a non-null integer `reference_id` scoped to its parent task.
- R2. `reference_id` values are unique within a task (no two jobs on the same task share the same `reference_id`).
- R3. On deploy, all existing jobs are backfilled per task: assign `reference_id` 1..N ordered by `created_at` ascending (oldest job gets 1).

**Assignment on create**
- R4. When a job is created without an explicit `reference_id`, the system sets `reference_id` to `max(reference_id among jobs for that task) + 1`, or `1` when the task has no jobs yet.
- R5. When a job is created with an explicit `reference_id`, that value is stored if it does not conflict with an existing job on the same task.
- R6. If an explicit `reference_id` on create conflicts with an existing job on the same task, creation fails with a clear validation error (no silent auto-bump).
- R7. `reference_id` cannot be changed after the job is created (not accepted on update APIs or edit flows).

**API and authoring surfaces**
- R8. Job read responses expose `reference_id` alongside existing job fields.
- R9. Job create schemas accept an optional `reference_id` (create-only); all job creation entry points apply the same assignment and uniqueness rules (single-job API, task-with-jobs bundle, JSON import, AI draft confirm).
- R10. `order` remains a separate optional field on create/update with its existing display-order meaning; setting `reference_id` does not implicitly set `order`.

**Listing and sort behavior**
- R11. When jobs for a task are listed (API task detail, publish paths, and any other canonical task-scoped job query), the default sort is: `order` descending, then `reference_id` ascending, then `created_at` ascending.
- R12. Sort behavior applies consistently wherever task jobs are loaded for display or downstream selection by sequence, unless a specific flow documents a different requirement.

**Relationship to future job references**
- R13. This change does not define how one job references another in `prompt` JSON or in processors; it only establishes stable per-task slot numbers for that future work.

---

## Success Criteria

- Every job in the database has a `reference_id` after migration and backfill.
- Creating a job without `reference_id` always yields the next sequential slot for that task.
- Bulk authoring (JSON / AI draft) can pin stable slot numbers on create; duplicate slots on the same task are rejected.
- Task job lists break ties among equal `order` values using `reference_id` before `created_at`.
- `order` continues to control primary display ordering without being conflated with slot identity.

---

## Scope Boundaries

**Deferred for later**
- Job-type-specific reference fields in `prompt` JSON and processor logic to resolve “job B uses output of job A” by `reference_id`.
- Database-level unique constraint on `(task_id, reference_id)` if not included in the first implementation (application-level uniqueness is required either way).
- Renumbering or compacting `reference_id` after deletes (gaps are acceptable).
- Task detail UI column for `reference_id` (API exposure is in scope; visible UI label/column is left to planning unless product asks to include it in the same slice).

**Outside this change**
- Removing or repurposing the `order` field.
- Changing job processing order in the worker based on `reference_id` (worker ordering is unchanged unless separately specified).
- Cross-task or global reference identifiers.

---

## Key Decisions

- **Two fields, two roles**: `reference_id` is the stable per-task slot; `order` remains for display and manual reordering.
- **Create-only explicit IDs**: Supports JSON and AI bundle authoring without allowing renumbering that would break future references.
- **Backfill by `created_at`**: Existing jobs get deterministic 1..N slots reflecting historical creation order.
- **Conflict policy on create**: Duplicate explicit `reference_id` within a task fails validation rather than auto-assigning another number.
- **Sort is tie-break, not primary**: `order` desc stays the main UX sort; `reference_id` asc resolves equal `order` values (common when many jobs use default `order`).

---

## Dependencies / Assumptions

- Job creation today flows through `app/models/job.py`, `app/api/routes.py`, `app/services/task_repo.py`, frontend task/job create paths, and AI draft confirm paths—all must adopt shared assignment logic to avoid drift.
- Schema bootstrapping uses `SQLModel.metadata.create_all`; a one-time backfill script or migration step is required for existing deployments with data.
- Integer slots are sufficient; fractional or string reference identifiers are not needed.

---

## Outstanding Questions

### Deferred to planning

- [Affects R12][Technical] Exact list of query sites beyond task detail and Instagram publish that must adopt the new sort order.
- [Scope] Whether task detail UI should show `reference_id` in the jobs table in the same slice as the backend change.
- [Affects R2][Technical] Whether to add a DB unique index on `(task_id, reference_id)` in v1 or rely on application checks only.
