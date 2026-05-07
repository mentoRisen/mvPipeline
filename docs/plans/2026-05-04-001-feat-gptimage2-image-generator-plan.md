---
title: "feat: Add gptimage2 image generator"
type: feat
status: active
date: 2026-05-04
---

# feat: Add gptimage2 image generator

## Summary

Add a third supported `Job.generator` value, `gptimage2`, that calls the OpenAI Images API with the appropriate model and saves output under the existing `output/{task_id}/{job_id}.jpeg` convention, with UI and docs updated so operators can select it without changing task or job domain models.

---

## Problem Frame

The product already supports `dalle` and `gptimage15` via dedicated processor modules and a single dispatch point in `app/services/jobs/processor.py`. Operators who want a newer or more “creative” OpenAI image model have no in-app way to name that generator; jobs with an unknown `generator` string fail at processing time. This plan extends the same pattern to `gptimage2` without replacing existing defaults or introducing parallel workflow concepts.

---

## Requirements

- R1. When a job’s `generator` (case-insensitive) is the new token `gptimage2`, `process_job` must generate an image from `job.prompt["prompt"]`, persist it like other generators, best-effort FTP upload, and set `Job` to `PROCESSED` with a `result` payload consistent with the chosen result-shape decision (see Key Technical Decisions).
- R2. Unknown `generator` values must continue to fail with a clear error; `gptimage2` must not be treated as unknown.
- R3. The AI draft modal and task detail job UI must list `gptimage2` as a selectable generator (alongside existing options), without breaking existing tasks that use `dalle` or `gptimage15`.
- R4. `README.md` must document the new generator and point to the new processor module, consistent with the current “Image Generators” section.
- R5. Add targeted automated tests at the narrowest practical seam for the new dispatch path (per project testing rules), without turning this into a full integration test of OpenAI or FTP.

**Origin document:** None for this feature; requirements derived from the confirmed planning synthesis.

---

## Scope Boundaries

- **In scope:** New processor module, `process_job` branch, Vue generator `<option>` updates, schema description text if it lists examples, `README` update, new service-level tests with mocked HTTP or mocked `generate_image`.
- **Out of scope:** Replacing `dalle` or `gptimage15` as the default generator in templates or empty job helpers unless explicitly decided during implementation (default remains `dalle` per synthesis).
- **Out of scope:** Refactoring `app/services/jobs/processor.py` into a large plugin registry; only minimal consistent edits.
- **Out of scope:** Tenant-specific API keys for image generation in this change (continues to use existing `OPENAI_API_KEY` / config pattern used by other processors).
- **Out of scope:** Changing the AI text draft LLM system prompt to prefer `gptimage2` in generated JSON (can be a follow-up if product wants drafts to default to the new model).

### Deferred to Follow-Up Work

- Unify OpenAI image API call + decode logic shared by `gptimage15` and `gptimage2` if duplication becomes costly.
- Reconcile `app/config.py` `DEFAULT_IMAGE_GENERATOR` (e.g. `pillow`) with `process_job` if product wants a single source of truth for “default generator” strings.

---

## Context & Research

### Relevant Code and Patterns

- **Dispatch and orchestration:** `app/services/jobs/processor.py` — routes on `job.generator` lowercased; updates job `result`, best-effort `uploadToPublic`, advances parent task when all jobs processed.
- **Existing OpenAI image adapters:** `app/services/jobs/processor_dalle.py` (URL download + JPEG), `app/services/jobs/processor_gptimage15.py` (base64 from `b64_json` + JPEG).
- **Entrypoints:** `app/worker.py`, `app/api/routes.py` (process job), `scripts/process_job.py` — all call the same `process_job`; no change required if dispatch is extended.
- **Frontend generator lists:** `frontend/src/components/AiTaskDraftModal.vue`, `frontend/src/components/TaskDetail.vue` — hard-coded `<option>` values and `dalle` defaults in several helpers.
- **Template JSON for new tasks:** `app/api/routes.py` — `instagram_post` template still defaults first job to `dalle`; product choice is to keep that default in v1.
- **API shape:** `app/api/schemas.py` — `JobCreate` / `JobUpdate` use free-form `generator: str` with description examples; extend examples for discoverability.
- **Gaps:** No existing tests target `process_job` or the image processors; this plan adds the first narrow seam tests for the new branch.

### Institutional Learnings

- `docs/solutions/` has no image-generator or OpenAI-specific learnings yet; only an adjacent AI draft session cap note. No extra constraints from institutional docs.

### External References

- OpenAI Images API model name and response fields for the target “GPT Image 2” class model must be verified at implementation time against current provider documentation (exact `model` string, supported `size` / `quality`, and whether responses use `b64_json` vs `url`).

---

## Key Technical Decisions

- **Internal generator token:** Use `gptimage2` as the Job.generator string (lowercased in dispatch), matching the user’s naming and the pattern `gptimage15`.
- **New module vs. inlining:** Add `app/services/jobs/processor_gptimage2.py` with a `generate_image` function mirroring the style of `processor_gptimage15.py` (adapter only; no DB in module), to keep parity with existing layout and `README` expectations.
- **Result payload shape:** Match `gptimage15` unless the new API returns a stable `url` like DALL·E; if both are possible, implement parsing that supports the provider’s actual response for the chosen model and fill `result` with `image_path`, optional `image_url` when available, `public_url` after FTP, and `generator` — without logging raw tokens or full provider payloads.
- **Default template / empty jobs:** Keep default generator `dalle` so existing UX and tests remain stable; operators explicitly pick `gptimage2` where desired.

---

## Open Questions

### Resolved During Planning

- **Default generator for new jobs/templates:** Remains `dalle` (select `gptimage2` explicitly for creative experiments).

### Deferred to Implementation

- **Exact OpenAI `model` parameter value** for GPT Image 2 / “gptimage2” (provider string may differ from the internal `generator` token).
- **Response handling:** Confirm whether the new model returns `b64_json`, `url`, or either depending on parameters — implementation follows provider behavior.

---

## Implementation Units

- U1. **OpenAI adapter module for gptimage2**

**Goal:** Encapsulate Images API call + decode + write JPEG under `OUTPUT_DIR`, returning the same relative `/output/...` path pattern as siblings.

**Requirements:** R1

**Dependencies:** None

**Files:**
- Create: `app/services/jobs/processor_gptimage2.py`
- Modify: (none yet)

**Approach:**
- Follow structural patterns from `app/services/jobs/processor_gptimage15.py`: validate `OPENAI_API_KEY`, POST to Images generations endpoint, handle errors with safe logging (strip Authorization), attach structured API error when available for upstream persistence.
- Use provider-documented `model`, `size`, and `quality` defaults appropriate for square Instagram-oriented output, aligned with existing `1024x1024` usage unless the new model requires different allowed values.

**Patterns to follow:**
- `app/services/jobs/processor_gptimage15.py`, `app/services/jobs/processor_dalle.py`

**Test scenarios:**
- Test expectation: none for this unit in isolation if **U2** covers behavior via `process_job` with mocked `generate_image` — **or** add direct unit tests here if the team prefers testing the adapter without DB.

**Verification:**
- Module importable; `generate_image` returns a string path under `/output/...` on success in manual or integrated test.

---

- U2. **Dispatch branch in `process_job`**

**Goal:** Route `generator_type == "gptimage2"` to the new module, with prompt validation and `result` building consistent with Key Technical Decisions.

**Requirements:** R1, R2, R5

**Dependencies:** U1

**Files:**
- Modify: `app/services/jobs/processor.py`
- Test: `tests/services/test_image_job_processor.py` (new)

**Approach:**
- Add an `elif` branch parallel to `dalle` and `gptimage15`.
- Reuse the same prompt validation as other branches (`job.prompt` contains non-empty `prompt` string).
- After generation, best-effort `uploadToPublic` and set `result` fields to match the agreed shape (mirror `gptimage15` or `dalle` as decided).

**Patterns to follow:**
- Existing branches in `app/services/jobs/processor.py`

**Test scenarios:**
- **Happy path:** `process_job` with a job whose `generator` is `gptimage2` / `GptImage2` and `prompt` set — mock `generate_image` on the new module to return a fixed path; assert job status `PROCESSED` and `result` contains expected keys (`image_path`, `generator`, `public_url` if mocked FTP returns a value).
- **Error path:** Mock `generate_image` to raise — assert job status `ERROR` and `result` contains error detail (consistent with existing exception handling).
- **Edge case:** `generator` typo `gptimage3` still raises unknown generator (existing behavior).

**Verification:**
- New tests pass without network calls.

---

- U3. **Frontend generator selection**

**Goal:** Operators can choose `gptimage2` when editing draft jobs and when adding jobs on task detail.

**Requirements:** R3

**Dependencies:** U2 (runtime must recognize token before UX is valuable in production)

**Files:**
- Modify: `frontend/src/components/AiTaskDraftModal.vue`
- Modify: `frontend/src/components/TaskDetail.vue`

**Approach:**
- Add `<option value="gptimage2">gptimage2</option>` next to existing options.
- Do not change default `generator: 'dalle'` unless product explicitly requests it later.

**Patterns to follow:**
- Existing `<select>` blocks for `dalle` / `gptimage15`

**Test scenarios:**
- Test expectation: none — no stable frontend unit test harness referenced for these components; manual verification: open modal and task detail, confirm third option appears and saves.

**Verification:**
- In UI, selecting `gptimage2` persists through draft confirm / job create API payloads.

---

- U4. **API schema hints and documentation**

**Goal:** Discoverability for API consumers and operators reading repo docs.

**Requirements:** R4

**Dependencies:** U1, U2

**Files:**
- Modify: `app/api/schemas.py` (Field descriptions listing example generators)
- Modify: `README.md` (Image Generators subsection)

**Approach:**
- Extend generator example strings in `JobCreate` / `JobUpdate` descriptions to include `gptimage2`.
- Add README bullet for GPT Image 2 processor file name and requirement for `OPENAI_API_KEY`, mirroring existing bullets.

**Test scenarios:**
- Test expectation: none — documentation and description-only change.

**Verification:**
- README renders correctly; OpenAPI `/docs` shows updated examples.

---

## System-Wide Impact

- **Interaction graph:** Only job processing and manual/API-created jobs that set `generator` to `gptimage2`; worker and routes that call `process_job` need no signature changes.
- **Error propagation:** Failures continue to land in `job.result["error"]` and job status `ERROR`, same as other generators.
- **State lifecycle risks:** None beyond existing “unknown generator” class of errors; new token reduces false unknowns for intended use.
- **API surface parity:** `generator` remains a string; no new endpoints.
- **Integration coverage:** Full OpenAI + FTP path is not required in CI; tests use mocks. Optional manual smoke: run one job in dev with real key.
- **Unchanged invariants:** Task status machine, job statuses other than success path, publish flow, and `dalle` / `gptimage15` behavior remain unchanged.

---

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| Provider model name or response shape differs from assumptions | Resolve in implementation using current docs; adapter parses the supported response shape; document deferred unknowns in Open Questions |
| Duplication between `gptimage15` and `gptimage2` modules | Accept short duplication for v1; list refactor under Deferred |
| No existing processor tests | Add `tests/services/test_image_job_processor.py` as regression harness for future generators |

---

## Documentation / Operational Notes

- Update `README.md` Image Generators list.
- If deployment docs mention supported generators, add one line in the same pass (only if such a doc exists and is canonical for operators).

---

## Sources & References

- Related code: `app/services/jobs/processor.py`, `app/services/jobs/processor_gptimage15.py`, `frontend/src/components/AiTaskDraftModal.vue`, `frontend/src/components/TaskDetail.vue`
- External docs: OpenAI Images API — verify at implementation time
