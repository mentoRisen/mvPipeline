---
title: Videocontent and runway-video job CRUD with shared prompt validation
date: 2026-06-04
category: architecture-patterns
module: jobs
problem_type: architecture_pattern
component: service_object
severity: medium
applies_when:
  - Adding a new job generator with a structured prompt JSON contract
  - Extending REST job create/update and AI draft confirm with the same rules
  - Wiring Vue job modals (TaskDetail, AiTaskDraftModal) to a backend validation gate
related_components:
  - frontend_stimulus
  - database
  - integrations
tags:
  - videocontent
  - runway-video
  - job-prompt
  - reference-id
  - ai-draft
  - validation
  - task-detail
resolution_type: code_fix
---

# Videocontent and runway-video job CRUD with shared prompt validation

## Context

Operators needed to create, edit, list, and delete **video jobs** (`purpose: videocontent`, `generator: runway-video`) through the existing job API and GUI before Runway processor work lands. Image jobs already used a minimal prompt shape `{ "prompt": "..." }`; video jobs need **model**, **motion prompt**, and an **image slot** pointing at an `imagecontent` job on the same task.

Without a shared validation module, REST would accept free-form prompt dicts and the AI draft path would diverge from TaskDetail authoring. Plan reference: `docs/plans/2026-06-04-001-feat-videocontent-runway-video-crud-plan.md` (processor dispatch intentionally deferred).

## Guidance

### Single validation gate

Add `app/services/job_prompt_validation.py` and call it from:

- `create_job` / `update_job` in `app/api/routes.py` (map `JobPromptValidationError` → HTTP 422, same `loc` shape as `JobReferenceValidationError`)
- `AiTaskDraftService._normalize_item` (map to `AiTaskDraftItemValidationError`)

Constants and contract:

| Field | Rule |
|-------|------|
| `purpose` | `videocontent` when generator is `runway-video` (required; omit → 422) |
| `prompt.prompt` | Non-empty string (stripped on write) |
| `prompt.model` | `gen4_turbo` or `veo3.1_fast` |
| `prompt.reference_id` | Integer ≥ 1; must match an **imagecontent** job slot on the task (REST) or in the draft item (AI) |

Use `type(reference_id) is not int` (not `isinstance(..., int)`) so JSON booleans do not pass as slot ids.

### Two meanings of `reference_id`

- **Job row `reference_id`**: per-task slot assigned at create (`job_reference_service`).
- **`prompt.reference_id`**: which image job slot supplies the still frame for Runway.

UI labels: job table **Ref** vs modal **Image slot**. See `docs/glossary.md`.

### AI draft: explicit job slots, not array order

Draft confirm previously risked validating slots in array order while persisting jobs sorted by `order`. Fix: require **explicit `reference_id` on every draft job** before normalize (`validate_draft_job_reference_ids`), extend strict JSON Schema `oneOf` branches to include `reference_id` in `required`, and match runway `prompt.reference_id` against **explicit** image job `reference_id` values (not planned/auto order).

### Frontend parity

Centralize purpose/generator/model lists in `frontend/src/components/jobGeneratorConfig.js`. `draftJobPromptValid(job, siblingJobs)` must call the same slot rule as the backend (`runwayImageSlotValid`) so `canConfirm` does not enable Create when the API would 422.

## Why This Matters

Duplicated validation in routes, AI service, and Vue guarantees drift (purpose optional on REST, bool slots, confirm enabled with bad image refs). One module plus mirrored frontend helpers keeps REST, AI confirm, and operator UI aligned until `processor_runway_video` is added.

## When to Apply

- Adding another generator with a non-trivial `prompt` JSON shape — extend `validate_job_prompt_for_write`, not route handlers alone.
- AI strict schema changes — update `ai_draft_response_schema.py` and schema regression tests together.
- Cross-job references — validate against persisted task rows (REST) or explicit draft job `reference_id` (bundle), never assumed list index.

## Examples

**Shared validator (runway branch):**

```python
if purpose_lower != VIDEOCONTENT_PURPOSE:
    raise JobPromptValidationError(
        f"generator {RUNWAY_VIDEO_GENERATOR} requires purpose {VIDEOCONTENT_PURPOSE}",
        field="purpose",
    )
normalized = validate_runway_video_prompt(prompt)
validate_image_slot_reference(session, task_id, normalized["reference_id"])
```

**Draft slot check (explicit ids):**

```python
validate_draft_job_reference_ids(preview.jobs)  # every job.reference_id int >= 1, unique
validate_runway_reference_in_draft_jobs(
    draft_jobs=preview.jobs,
    image_slot=normalized["reference_id"],
)
```

**Frontend confirm gate:**

```javascript
return item.jobs.every((job) => draftJobPromptValid(job, item.jobs))
```

## Related

- `docs/solutions/architecture-patterns/job-reference-id-per-task-slots.md` — job row slot assignment
- `docs/solutions/architecture-patterns/ai-draft-backend-prompt-wiring-2026-05-22.md` — strict schema + single backend gate pattern
- `docs/runtime-flows.md` — TaskDetail runway fields; processor not wired yet
- Open follow-ups from review: P2 generator-switch prompt shape (`/tmp/mvpipeline-handoff-p2-2026-06-04.md`), Runway processor slice (deferred in plan)
