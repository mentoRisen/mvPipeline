---
title: "feat: Tenant-scoped prompts (CRUD + header nav)"
type: feat
status: active
date: 2026-04-17
origin: docs/brainstorms/2026-04-17-prompt-model-requirements.md
---

# feat: Tenant-scoped prompts (CRUD + header nav)

## Overview

Add a persisted **prompt** entity per tenant (name, type, long body), full CRUD behind the same auth and tenant header model as tasks, a **Prompts** header link next to **Tasks**, and a Vue screen to manage rows. This slice stops at storage and admin UI; **consuming** prompt text in the AI task-creation path stays out of scope (see origin scope boundaries).

## Problem Frame

Operators need in-product, tenant-scoped storage for long instruction text (starting with **Tasks Creation**) without relying on env or external docs. The product already scopes data with `X-Tenant-Id` and `tenant_context_dependency`; prompts must follow that pattern (see origin: `docs/brainstorms/2026-04-17-prompt-model-requirements.md`).

## Requirements Trace

| ID | Requirement |
|----|-------------|
| R1 | Prompt rows belong to exactly one tenant |
| R2 | Fields: name, type, tenant, long-form body; duplicate names per tenant allowed |
| R3 | Type is categorical; v1 single option `task-creation` / label **Tasks Creation**; extensible for more types |
| R4 | Authenticated CRUD in current tenant context |
| R5 | Multiple rows per tenant per type |
| R6 | Header link next to **Tasks** to prompt management |

## Scope Boundaries

- **In scope:** SQLModel table, repo helpers, scoped API routes, Pydantic schemas, schema sync, frontend list/create/edit/delete, nav link.
- **Out of scope:** Wiring stored prompts into `OpenAITextDraftAdapter` / `AiTaskDraftService` or any LLM call.
- **Out of scope:** New prompt types beyond `task-creation` until product adds them (code should not block adding enum + select options later).

## Planning Resolutions (from brainstorm deferrals)

- **Nav label:** **Prompts**; route path **`/prompts`** (adjacent to `/` Tasks in `frontend/src/main.js` and `frontend/src/App.vue`).
- **List UX:** Sort by **`updated_at` descending**; each row shows **name**, type label (**Tasks Creation**), **truncated body preview** (~120 chars), and **updated** time.
- **Name validation:** Required after trim; reject empty; **max length 200** characters (adjust in implementation if product wants longer). No uniqueness constraint.

## Context & Research

### Relevant Code and Patterns

- **Tenant-scoped routes:** `app/api/routes.py` — `scoped_router` uses `Depends(auth_service.get_current_active_user)` and `Depends(tenant_context_dependency)`; new prompt routes belong here with the same dependencies (already on the router).
- **Repo style:** `app/services/schedule_rule_repo.py` — session-per-operation, `list_*_by_tenant` with `order_by`, `get_by_id`, `save`, `delete`.
- **Models:** `app/models/schedule_rule.py`, `app/models/task.py` — UUID PK, `tenant_id` FK, timestamps.
- **Schema lifecycle:** `app/db/engine.py` and `scripts/sync_schema.py` — `SQLModel.metadata.create_all` after models are imported; new model must be imported in `app/models/__init__.py`.
- **Frontend API:** `frontend/src/services/api.js` — axios instance with `Authorization` and `X-Tenant-Id` from `tenantStore`; add a `promptService` object alongside `taskService`.
- **Router and header:** `frontend/src/main.js`, `frontend/src/App.vue`.
- **Tests:** `tests/conftest.py` patches `engine` on `db_engine`, repos, and `routes`; any new `prompt_repo` must be patched the same way. API tests: `tests/api/test_ai_draft_session_routes.py` pattern (`client`, `tenant`, `Authorization` header, `X-Tenant-Id`).

### Institutional Learnings

- None required for this CRUD slice; follow existing tenant and auth boundaries in `.cursor/rules/04-security.mdc`.

### External References

- None; local CRUD patterns are sufficient.

## Key Technical Decisions

- **Table name:** `prompts` (plural, consistent with `tasks`, `tenants`).
- **Type representation:** Python `Enum` (e.g. `PromptType`) with string values; first member `task_creation` → stored value `task-creation` (match UI label mapping in frontend). API accepts only known enum values; extend enum when adding types.
- **Long text column:** SQLAlchemy `Text` for the body so MySQL/SQLite tests behave predictably for long content.
- **404 vs 403 for cross-tenant access:** Mirror `_task_for_current_tenant_or_404` — if a prompt exists but `prompt.tenant_id != tenant.id`, return **404** to avoid leaking existence.
- **REST shape:** `GET /prompts`, `POST /prompts`, `GET /prompts/{id}`, `PUT /prompts/{id}`, `DELETE /prompts/{id}` under `/api/v1` (scoped).

## Open Questions

### Resolved During Planning

- Nav label, route, sort order, preview, name validation — see **Planning Resolutions** above.

### Deferred to Implementation

- Exact empty-state copy when no tenant is selected in the UI (mirror patterns from task list if present).
- Whether edit uses a dedicated detail route or inline modal (either is fine if UX is consistent with existing admin screens).

## Implementation Units

### Unit 1 — Domain model registration

- **Goal:** Define `Prompt` (and prompt type enum) and register it for metadata creation.
- **Requirements:** R1–R3.
- **Dependencies:** None.
- **Files:**
  - `app/models/prompt.py` (new)
  - `app/models/__init__.py` (modify)
- **Approach:** UUID PK; `tenant_id` FK to `tenants.id`; `name` str; `type` stored as string via enum column pattern (same idea as `Task.status`); `body` as `Text`; `created_at` / `updated_at` like other models.
- **Patterns to follow:** `app/models/task.py`, `app/models/schedule_rule.py`.
- **Test scenarios:** Test expectation: none — no behavior until repo/routes exist; optional smoke: model imports without error.
- **Verification:** `import app.models` succeeds; `scripts/sync_schema.py` (or documented dev sync) can create the new table in target environments.

### Unit 2 — Repository layer

- **Goal:** CRUD and list-by-tenant in a dedicated repo module.
- **Requirements:** R1, R4, R5.
- **Dependencies:** Unit 1.
- **Files:**
  - `app/services/prompt_repo.py` (new)
  - `tests/services/test_prompt_repo.py` (new)
  - `tests/conftest.py` (modify — monkeypatch `prompt_repo.engine` like other repos)
- **Approach:** `create_prompt(tenant_id, name, type, body)`, `get_prompt_by_id`, `list_prompts_for_tenant(tenant_id, limit, offset)` ordered by `updated_at.desc()`, `update_prompt` / `save`, `delete_prompt`. Keep sessions inside repo functions like `schedule_rule_repo`.
- **Patterns to follow:** `app/services/schedule_rule_repo.py`.
- **Test scenarios:**
  - **Happy path:** Create and list returns row; get by id returns same data; update changes body and bumps `updated_at`; delete removes row.
  - **Edge case:** List empty tenant returns `[]`.
  - **Edge case:** `get_prompt_by_id` returns `None` for missing id.
- **Verification:** `pytest tests/services/test_prompt_repo.py` passes.

### Unit 3 — API schemas and routes

- **Goal:** Expose CRUD over HTTP with tenant scoping and validation.
- **Requirements:** R2–R5.
- **Dependencies:** Unit 2.
- **Files:**
  - `app/api/schemas.py` (modify — `PromptCreate`, `PromptUpdate`, `PromptResponse` or equivalent)
  - `app/api/routes.py` (modify — register handlers on `scoped_router`)
  - `tests/api/test_prompt_routes.py` (new)
- **Approach:** POST validates name (non-empty, max length) and type enum; list returns summaries suitable for UI (include truncated preview in response **or** let frontend truncate — pick one and document in code comments). Enforce tenant match on get/put/delete. Use repo functions; avoid ad-hoc `Session(engine)` in route bodies except where existing routes already do for composition (prefer repo).
- **Patterns to follow:** Task and schedule rule handlers; `_task_for_current_tenant_or_404`-style helper for prompts.
- **Test scenarios:**
  - **Happy path:** POST creates prompt; GET list returns it; GET by id; PUT updates; DELETE removes.
  - **Error path:** GET/PUT/DELETE wrong-tenant id → 404.
  - **Error path:** POST with empty name → 422.
  - **Error path:** POST with unknown type → 422.
- **Verification:** `pytest tests/api/test_prompt_routes.py` passes.

### Unit 4 — Frontend: service, view, router, header

- **Goal:** Operators can CRUD prompts from the app with discoverable navigation.
- **Requirements:** R4, R6; success criteria for list clarity (name + preview).
- **Dependencies:** Unit 3.
- **Files:**
  - `frontend/src/services/api.js` (modify — `promptService`)
  - `frontend/src/views/PromptsView.vue` (new)
  - `frontend/src/main.js` (modify — route `/prompts`)
  - `frontend/src/App.vue` (modify — `<router-link>` after Tasks)
- **Approach:** List with add button; create/edit form with fields name (text), type (select: one option), body (textarea); delete with confirm; handle missing tenant (show message, disable mutations — align with how task flows behave when `tenantStore` has no id). Use existing styles (`btn-pink`, cards) from `frontend/src/style.css` / sibling views.
- **Patterns to follow:** `frontend/src/views/TasksView.vue` / `TaskList.vue` for loading patterns; `api.js` for HTTP.
- **Test scenarios:**
  - **Preferred:** Small frontend unit test if the repo has a pattern for exercising a formatter or store (e.g. preview truncation helper). If no suitable seam exists without heavy mount setup, document **manual verification**: load `/prompts`, CRUD roundtrip with tenant selected.
- **Verification:** With API running and tenant selected, full CRUD works; header **Prompts** navigates to the view.

## Risks & Mitigation

| Risk | Mitigation |
|------|------------|
| Forgotten `engine` monkeypatch breaks tests | Update `tests/conftest.py` when adding `prompt_repo`. |
| Large body payloads | Use `Text` column; consider client max length later if needed. |

## System-Wide Impact

- **Database:** New table via `create_all` / sync script; operators must run schema sync in each environment where the app is deployed.
- **Docs:** If `docs/deployment-hetzner-flow-mentoverse.md` or similar mentions schema sync, add a one-line note that new deploys need sync after this change (only if that doc is the canonical checklist — implementer to verify).

## Success Criteria (execution)

- All listed tests pass; manual UI CRUD succeeds with tenant header.
- No new unauthenticated routes; tenant boundary enforced on every mutating operation.
