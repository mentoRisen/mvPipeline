---
date: 2026-06-14
topic: runway-video-processor
---

# Runway video job processor

## Summary

Implement processing for existing **`videocontent` / `runway-video`** jobs: resolve the motion prompt, model, and referenced image slot from the job prompt, call Runway image-to-video, save the output locally, persist result metadata on the job, and show a playable preview in TaskDetail. Operators process image jobs manually first; Process on a runway job stays disabled until the referenced image slot is ready. Runway credentials resolve tenant-first with global fallback. Publish and worker auto-ordering are out of scope.

---

## Problem Frame

The videocontent CRUD slice landed first so operators could author runway-video jobs through REST, TaskDetail, and AI draft confirm with a shared prompt contract (`prompt`, `model`, `prompt.reference_id`). Tasks with runway jobs have been created in production-like use, but nothing has been processed yet.

Today, clicking **Process** on a runway-video job fails with an unknown-generator error because `app/services/jobs/processor.py` only dispatches image generators. Without a processor, mixed image+video tasks cannot complete: the task stays blocked in `PROCESSING` until every job reaches `PROCESSED`. The next slice closes the gap from authored job to generated local video the operator can preview.

---

## Key Decisions

- **Manual image-then-video ordering** — no worker dependency graph in v1. The operator runs image jobs first, then Process on the runway job.
- **Shared upstream readiness rule** — one definition of “image slot ready” drives TaskDetail’s disabled Process state and backend validation at process time.
- **Image-processor-shaped adapter** — Runway integration lives behind a dedicated processor module with no DB writes inside the adapter, matching existing image generator modules.
- **Local file + preview** — generated video is stored under the project output tree; `job.result` carries path metadata and optional public URL; TaskDetail renders a playable preview for processed runway jobs.
- **Tenant-first credentials with global fallback** — Runway API key is read from tenant env when present, otherwise from server-level config, consistent with other integrations migrating toward explicit resolution.
- **Fail-closed at process time** — referenced image must be `PROCESSED` with a usable local image result before Runway is called; CRUD-time slot validation stays unchanged (slot existence only).

---

## Requirements

**Processing and dispatch**
- R1. When `job.generator` is `runway-video` (case-insensitive), `process_job` dispatches to a Runway video processor instead of raising an unknown-generator error.
- R2. The processor reads the normalized prompt shape already enforced at write time: non-empty motion `prompt`, allowed `model` (`gen4_turbo` or `veo3.1_fast`), and integer `prompt.reference_id` for the image slot.
- R3. Before calling Runway, the processor resolves the sibling `imagecontent` job on the same task whose row `reference_id` equals `prompt.reference_id`.
- R4. Processing fails with a clear error if the referenced image job is missing, not `PROCESSED`, or lacks a usable local image in `result` (for example no `image_path`).
- R5. On success, the runway job is marked `PROCESSED` and `job.result` includes at minimum a local `video_path`, the generator token, and `public_url` when `PUBLIC_URL` is configured.
- R6. On failure, the runway job is marked `ERROR` with error details in `result`, matching existing image processor behavior.
- R7. After a successful runway job, parent task status advancement follows today’s rule: when the task is `PROCESSING` and all jobs on the task are `PROCESSED`, move the task to `PENDING_CONFIRMATION`.

**Runway integration**
- R8. Runway API credentials resolve tenant-first from tenant env, with fallback to server-level config when the tenant key is absent.
- R9. If no Runway credential is available for the active tenant context, processing fails with a clear configuration error rather than attempting an unauthenticated call.
- R10. The adapter accepts the referenced image’s local file, the motion prompt text, and the selected model, and completes when Runway returns a finished video suitable for download (including any poll/wait logic required by the Runway API within the single process invocation).

**Operator UI**
- R11. In TaskDetail, **Process** is disabled for runway-video jobs until the referenced image slot’s `imagecontent` job is `PROCESSED` with a usable image result.
- R12. When Process is disabled for this reason, the UI shows a short explanation (for example which image slot must be processed first).
- R13. For processed runway-video jobs, TaskDetail shows a playable video preview sourced from the job result (local path or public URL as appropriate).
- R14. Retry behavior for runway jobs in `ERROR` state matches existing job retry UX.

**Out of scope for this slice (unchanged behavior)**
- R15. Instagram publish and any videocontent publish path remain unchanged and image-only.
- R16. Worker job selection order is unchanged; the worker does not auto-skip runway jobs waiting on image jobs.
- R17. CRUD validation does not require the referenced image job to be processed at create/update time.

---

## Key Flows

- F1. **Happy path — mixed task**
  - **Trigger:** Operator has a task with at least one `imagecontent` job and one `runway-video` job referencing that slot.
  - **Steps:** Operator processes the image job to `PROCESSED`; Process on the runway job becomes enabled; operator clicks Process; system generates video, saves locally, sets result; TaskDetail shows video preview; when all jobs are `PROCESSED`, task moves to `PENDING_CONFIRMATION`.
  - **Covered by:** R1, R4, R5, R7, R11, R13

- F2. **Runway Process before image is ready**
  - **Trigger:** Operator attempts to process the runway job while the referenced image slot is not ready.
  - **Steps:** Process control is disabled in TaskDetail with explanation; if process is invoked anyway (API/worker), backend rejects with a clear error and does not call Runway.
  - **Covered by:** R4, R11, R12

- F3. **Missing Runway credentials**
  - **Trigger:** Tenant and global config both lack a Runway API key.
  - **Steps:** Process fails; job moves to `ERROR` with a configuration message; no external Runway call is made.
  - **Covered by:** R8, R9, R6

---

## Acceptance Examples

- AE1. **Covers R4, R11. Image not processed**
  - **Given:** A task with `imagecontent` job at ref 1 in `READY` and `runway-video` job with `prompt.reference_id: 1`
  - **When:** Operator views TaskDetail
  - **Then:** Process on the runway job is disabled with a reason referencing the image slot; direct process API call returns an error without calling Runway

- AE2. **Covers R1, R5, R13. End-to-end success**
  - **Given:** Image job at ref 1 is `PROCESSED` with usable `result.image_path`; runway job references ref 1 and is `READY`
  - **When:** Operator clicks Process on the runway job
  - **Then:** Job becomes `PROCESSED`; local video file exists; `job.result` includes `video_path`; TaskDetail shows playable preview

- AE3. **Covers R7. Task completion with mixed jobs**
  - **Given:** A task in `PROCESSING` with one processed image job and one unprocessed runway job
  - **When:** Operator processes the runway job successfully
  - **Then:** Task status becomes `PENDING_CONFIRMATION`

- AE4. **Covers R9. No API key**
  - **Given:** No Runway key in tenant env or global config
  - **When:** Operator processes a ready runway job
  - **Then:** Job is `ERROR` with a configuration error; no Runway request is sent

---

## Success Criteria

- An operator can take an already-authored mixed image+video task from created jobs through to a processed runway job with local video file and in-app preview without publish work.
- Process on runway jobs cannot be triggered from the UI until the referenced image is processed; backend enforces the same rule.
- Runway credential resolution is tenant-first with global fallback and fails closed when neither is set.
- Existing image-only tasks and processors behave unchanged.

---

## Scope Boundaries

**Deferred for later**
- Instagram or other publish paths for videocontent / carousel including video
- Worker auto-ordering or dependency-aware job picking
- Requiring referenced image jobs to be processed at CRUD create/update time
- Additional Runway models beyond the v1 enum (`gen4_turbo`, `veo3.1_fast`)

**Outside this change**
- Changes to the runway-video prompt JSON contract (already owned by `app/services/job_prompt_validation.py`)
- FTP or off-host video storage layout beyond local `output/` files
- Replacing manual Process with fully automated pipeline runs without operator action

---

## Dependencies / Assumptions

- Videocontent CRUD, shared prompt validation, TaskDetail runway authoring fields, and AI draft support are already shipped (see `docs/solutions/architecture-patterns/videocontent-runway-video-job-crud.md`).
- A valid Runway API account and key will be available for at least one tenant or globally before end-to-end verification.
- Referenced image jobs continue to store local paths in `result.image_path` (or equivalent) when `PROCESSED`, consistent with existing image processors.
- `PUBLIC_URL` may remain unset; preview should still work from local/served output paths where the app already serves generated files.
- Runway image-to-video API details (exact endpoints, polling intervals, model mapping) are deferred to planning and adapter implementation.

---

## Outstanding Questions

### Deferred to planning

- Exact Runway API request/response mapping for `gen4_turbo` and `veo3.1_fast`.
- Preferred local video file extension and naming convention under `output/{task_id}/`.
- Whether `job.result` should also retain a Runway-hosted URL for debugging or re-download.
- Exact tenant env key name (for example `RUNWAY_API_KEY`) and whether global config mirrors `OPENAI_API_KEY` pattern.
- Service-level test strategy for the adapter (mock HTTP vs recorded fixtures).

---

## Sources / Research

- `docs/solutions/architecture-patterns/videocontent-runway-video-job-crud.md` — prompt contract and deferred processor note
- `docs/plans/2026-06-04-001-feat-videocontent-runway-video-crud-plan.md` — original CRUD plan with explicit processor deferral
- `docs/runtime-flows.md` — current image job processing flow and runway CRUD behavior
- `app/services/jobs/processor.py` — dispatch point for new generator branch
- `app/services/job_prompt_validation.py` — existing runway prompt and slot validation
- `tests/services/test_image_job_processor.py` — processor test patterns to mirror
