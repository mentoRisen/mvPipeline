---
title: "feat: AI draft communication log (Slice 3 extension)"
type: feat
status: active
date: 2026-04-06
origin: docs/brainstorms/2026-04-02-ai-task-job-creation-requirements.md
---

# feat: AI draft communication log (Slice 3 extension)

## Overview

Extend **Slice 3** so each AI campaign draft session retains a **technical, ordered log** of what was sent to the model and what came back, plus the **user’s brief as captured by the server**. The **AI Create Campaign** modal becomes a **two-pane** layout: **left** keeps today’s structured draft review; **right** shows a **read-only transcript** aimed at **prompt engineers** (raw prompts, payloads, and model output—not end-user marketing copy).

**Preview execution model:** The user-visible preview is driven by **async work + client polling** (not SSE/streaming). After the user submits a brief, the API returns **quickly** with a session in a **“preview in progress”** state; the client **polls** session (or transcript) until preview **succeeds or fails**, refreshing the **right pane as new communication rows appear** and the **left pane** when the validated bundle is ready. This matches the desire to see communication **progress in near real time** without coupling to OpenAI streaming APIs.

This satisfies an operational need to understand “what the AI did” without digging through server logs or re-running requests.

## Problem Frame

Slice 3 persists `brief` + `bundle` on `ai_draft_sessions`, but **does not record** the actual LLM request/response artifacts. Prompt iteration and debugging require visibility into **system instructions**, **user message payload**, and **assistant content** (and errors), tied to the **same draft session** the user edits. That visibility must live **in the database** and be **exposed through the existing session APIs** the modal already uses.

(see origin: `docs/brainstorms/2026-04-02-ai-task-job-creation-requirements.md` — extends R3a/R14 observability; does not change R7/R11c deferrals.)

## Requirements Trace

- **R-O1.** For every AI **preview run**, persist ordered steps: **user input** (server-accepted brief), **prompt to AI** (outbound message snapshot), **response from AI** (raw assistant text prior to coercion). During **in-flight** preview, the server **commits intermediate events** so polling clients can show transcript growth before the bundle is final.
- **R-O1b.** **POST preview** **does not block** on the LLM; it **starts** async work and returns identifiers + **preview status**. **GET session detail** (or a dedicated lightweight poll endpoint if needed) returns **`preview_status`**, **bundle/items when ready**, and **communication events accumulated so far**.
- **R-O2.** Log rows are **scoped to `ai_draft_sessions`**, inherit **tenant + user** isolation from the parent session, and are returned when loading session detail for the modal’s technical pane.
- **R-O3.** **No secrets** in stored payloads: no API keys, bearer tokens, or raw tenant credential fields; `tenant_context` in logs must follow the same **allowlisted** subset already used for LLM calls (see `app/services/ai_task_draft_service.py` / adapter inputs).
- **R-O4.** **Frontend:** `AiTaskDraftModal` uses a **two-column** layout—**draft unchanged in behavior** on the left; **communication list** on the right, technical presentation (monospace / collapsible sections / timestamps). While **`preview_status` is in progress**, show **left** as loading/skeleton (or prior bundle if regenerating); **poll periodically** to refresh **right** (and **left** once complete).
- **R-O5.** **Failure paths:** If the LLM call fails after a **user_input** row is written, append a row or structured error entry so engineers see **where** the chain stopped (exact shape deferred; see Implementation).
- **R-O6.** **Performance / size:** Log payloads can be large; enforce **per-row and/or per-session size limits** and reject with the same class of errors as oversized bundles where practical.

## Scope Boundaries

- **In scope:** Preview path only (`POST .../ai-draft-confirm` does **not** call the LLM today—no new log rows on confirm unless a future slice adds LLM there). **Async preview + polling** for progressive transcript and non-blocking HTTP.
- **Out of scope:** **Token streaming** (SSE/chunked LLM response) unless a later iteration proves polling insufficient for latency—polling suffices for **event-level** progress (user → prompt → response).
- **Out of scope:** Changing LLM **semantics**, model choice UI, multi-turn clarification (R7/R7a), repair loop (R11c), or admin-only sharing across users.
- **Out of scope:** Full OpenAI raw HTTP dump (headers, ids) unless later needed—store **message-level** content sufficient for prompt engineering.

## Context & Research

### Relevant Code and Patterns

- `app/services/integrations/llm_text_adapter.py` — builds `system` string, `messages`, POST body to OpenAI-compatible API; parses `choices[0].message.content`.
- `app/services/ai_task_draft_service.py` — `generate_preview` calls `adapter.generate_campaign_draft`.
- `app/api/routes.py` — today `create_ai_task_draft_preview` runs preview **synchronously**; will evolve to **start async preview** + poll-friendly responses.
- `app/worker.py` — tenant worker polls **task/job** processing on a **multi-second** interval; **do not** rely on it as the primary executor for interactive AI preview latency unless a dedicated fast loop is introduced (see Key Technical Decisions).
- `app/services/ai_draft_session_repo.py` — session persistence, caps, TTL; extend or add sibling helpers rather than duplicating workflow in routes.
- `app/models/ai_draft_session.py` — `UuidChar32` / FK patterns for MySQL; new child table should reference `ai_draft_sessions.id` with **matching charset/collation** on MySQL for FK compatibility.
- `app/api/schemas.py` — `AiDraftSessionDetailResponse`; extend or add nested list type.
- `frontend/src/components/AiTaskDraftModal.vue`, `frontend/src/services/api.js` — session fetch already exists for resume; augment UI.
- `tests/services/test_ai_draft_session_repo.py`, `tests/api/test_ai_task_draft_routes.py` — patterns for tenant/user scoping and session lifecycle.

### Institutional Learnings

- `docs/solutions/` is not present in this repository.

### External References

- Skipped: behavior is app-specific; local SQLModel/FastAPI/Vue patterns are established.

## Key Technical Decisions

- **Async preview + polling (user choice):** Replace **synchronous** `POST /tasks/ai-draft-preview` blocking behavior with: **(1)** accept brief, create or update **`ai_draft_sessions`** row with **`preview_status`** (or equivalent) transitions **`pending` → `running` → `succeeded` | `failed`**; **(2)** schedule **async execution** in the **same deployment unit as the API** (recommended default: FastAPI **`BackgroundTasks`** or an asyncio task launched from the route handler) that performs LLM I/O and **commits communication events incrementally**; **(3)** client **polls** `GET .../ai-draft-sessions/{id}` (or a transcript-only URL) on an interval (e.g. 500–1500 ms, backoff when idle) until terminal status. **Rationale:** Per-tenant **`app/worker.py`** uses **coarse poll intervals** suited for batch work—not appropriate as the sole mechanism for interactive preview unless a separate **low-latency** consumer is added. Keeping execution colocated with the API avoids new infrastructure for v1.
- **Child table vs JSON column:** Use a **normalized child table** (e.g. `ai_draft_communication_events`) with `draft_session_id` FK, monotonic **`sequence`** per session, **`kind`** enum (`user_input` | `prompt_to_ai` | `response_from_ai` | optional `error` or `upstream_error`), **`payload` JSON**, **`created_at`**. Rationale: ordered transcript, poll-friendly incremental reads, future multi-turn friendly.
- **Where to capture content:** Background runner calls existing **`AiTaskDraftService` / adapter** path; after each logical step (**persist brief as user_input**, **build and persist prompt payload**, **persist raw response**), **commit** (or flush) so pollers observe new rows. Final step runs existing **validation/coercion** then writes **`bundle`** and sets **`preview_status=succeeded`**. On failure, set **`failed`**, **`last_error`**, append **error** transcript row as needed.
- **Transactional integrity:** **Per-event commits** (or short transactions per stage) are **acceptable** and desired for polling visibility; final bundle update should be **atomic** with terminal status so clients never see an incomplete bundle labeled succeeded. Document race: **double-submit** preview—enforce **idempotency or reject** second `running` for same session (implementation detail).
- **API contract:** **`POST` preview** returns **`draft_session_id`**, **`preview_status`** (e.g. `running`), optional **`communication_events`** snapshot or omit heavy body and rely on **GET**. **`GET` detail** includes **`preview_status`**, **`items`** when `succeeded`, **`last_error` / events** when `failed`, and growing **`communication_events`** while `running`. List endpoint may omit events; consider **`since_sequence`** query later to shrink poll payloads.
- **UI styling:** Right pane is **technical**: chronological list, **kind badge**, **expand/collapse** per event, monospace for `prompt_to_ai` / `response_from_ai`. Mobile: stack panes vertically with transcript below or behind a tab—defer polish to implementation once desktop works.

### Resolved During Planning

- **Row granularity:** One row per **kind per preview round** for the three main types; if `prompt_to_ai` is easier as a single JSON object mirroring `messages[]`, use that rather than splitting system vs user into two rows (still satisfies “prompt engineer visibility”).
- **Execution target:** **API-colocated background task** for v1; **not** the long-interval tenant worker loop alone.

### Deferred to Implementation

- Exact enum names and whether **`error`** is a separate `kind` or `payload.error_code`.
- Whether to store **token usage** from provider JSON when present.
- Max events per session and truncation policy (oldest vs reject new preview).

## Open Questions

### Deferred to Implementation

- **HTTP status for POST:** `200` with `preview_status: running` vs **`202 Accepted`**—either is fine if contract is clear; prefer one and document.
- **Polling interval / backoff** and when to stop (terminal state, max duration client-side).

## High-Level Technical Design

> *This illustrates the intended approach and is directional guidance for review, not implementation specification. The implementing agent should treat it as context, not code to reproduce.*

```mermaid
sequenceDiagram
  participant UI as AiTaskDraftModal
  participant API as POST ai-draft-preview
  participant BG as Preview runner
  participant Svc as AiTaskDraftService
  participant Adp as OpenAITextDraftAdapter
  participant Repo as ai_draft_session_repo
  participant DB as MySQL

  UI->>API: brief (+ optional draft_session_id)
  API->>Repo: create/update session preview_status=running
  API->>BG: schedule run(session_id, brief, ...)
  API-->>UI: draft_session_id + preview_status=running

  loop poll until terminal
    UI->>API: GET ai-draft-sessions/id
    API->>Repo: load session + events
    API-->>UI: preview_status + items? + communication_events
  end

  Note over BG,DB: Background (same process as API): commit stages for polling visibility
  BG->>Repo: append user_input, prompt_to_ai
  BG->>Svc: call adapter / validate bundle
  Svc->>Adp: HTTP to model
  Adp-->>Svc: response
  BG->>Repo: append response_from_ai; set bundle + preview_status=succeeded (or failed + last_error)
```

## Alternative Approaches Considered

- **SSE / streaming:** Lower latency for **token** visibility; user preference is **polling**, which is sufficient for **stage-level** transcript updates.
- **Tenant worker as sole executor:** Simple operationally but **too slow** for default poll cadence unless preview jobs get a **dedicated fast queue**; defer unless API-colocated tasks prove unreliable in production.

## Implementation Units

- [ ] **Unit 1: persistence model**

**Goal:** Add the child table model and register it for `create_all`, with MySQL-safe FK/column types consistent with `ai_draft_sessions`. Extend **`ai_draft_sessions`** with **preview lifecycle** fields suitable for polling (**`preview_status`** or equivalent, timestamps optional).

**Requirements:** R-O2, R-O6, R-O1b

**Dependencies:** None

**Files:**
- Create: `app/models/ai_draft_communication_event.py` (or equivalent single-module name consistent with repo naming)
- Modify: `app/models/__init__.py`
- Modify: `app/models/ai_draft_session.py` — preview status enum + columns

**Approach:**
- Define FK to `ai_draft_sessions.id`, `sequence` ordering, `kind` enum/string per project convention, JSON `payload`, timestamp.
- Mirror charset/collation lessons from `app/models/ai_draft_session.py` for any string FKs or indexed text if applicable.
- Default **`preview_status`** for new sessions: treat **idle vs running** consistently when listing “resumable” sessions (only **succeeded** bundles appear as editable drafts, or define whether **failed** remains resumable with brief).

**Patterns to follow:**
- `app/models/ai_draft_session.py`, existing SQLModel table modules.

**Test scenarios:**
- Test expectation: none at pure model level unless project adds model-level tests — **prefer** covering via repo tests in Unit 2.

**Verification:**
- Model imports cleanly; metadata includes new table; no duplicate table names.

---

- [ ] **Unit 2: repository — append and load transcript**

**Goal:** Encapsulate **scoped** insert and select for communication events (same tenant/user/session guards as existing session repo).

**Requirements:** R-O2, R-O5, R-O6

**Dependencies:** Unit 1

**Files:**
- Modify or extend: `app/services/ai_draft_session_repo.py`
- Test: `tests/services/test_ai_draft_session_repo.py`

**Approach:**
- Append events only when parent session belongs to `(tenant_id, user_id)` and is eligible (ACTIVE / same rules as `get_active_for_user`—decide whether **completed** sessions remain readable for transcript).
- Enforce monotonic `sequence` (MAX+1 or counting in Python within transaction).
- Optional: `assert_transcript_within_size` mirroring bundle size checks.

**Patterns to follow:**
- Existing `_trim_oldest_active_sessions`, `get_active_for_user`, HTTPException patterns in the same module.

**Test scenarios:**
- **Happy path:** After save preview flow with mocked trace, `GET` path loads events in correct order.
- **Edge case:** Wrong `user_id` cannot append or list another user’s transcript (404 / no rows).
- **Error path:** Oversize transcript payload rejected with 422 (or chosen status) without partial writes when wrapped in one transaction.

**Verification:**
- Service-level tests pass; no direct `Session(engine)` in new route code for transcript persistence.

---

- [ ] **Unit 3: adapter + service + background preview runner**

**Goal:** Keep **`generate_preview`** (or a **`run_preview_async`** orchestration in `app/services/`) as the single place that **calls the adapter** and **coerces** the bundle. The **preview runner** invokes it **after** persisting **user_input** and **prompt_to_ai** rows, and **appends response** + sets **terminal status**. All steps **redact secrets**.

**Requirements:** R-O1, R-O1b, R-O3, R-O5

**Dependencies:** Unit 2 in progress for repo hooks.

**Files:**
- Modify: `app/services/integrations/llm_text_adapter.py` (return/trace shape as needed)
- Modify: `app/services/ai_task_draft_service.py`
- Create or modify: `app/services/ai_draft_preview_runner.py` (or equivalent — **shared service**, not route handler logic)
- Test: `tests/services/` — runner + repo integration with mocked LLM

**Approach:**
- Runner loads session by id, verifies **tenant/user**, guards against **duplicate concurrent runs**.
- **Commit** communication events **between** stages so GET polls see progress (same process as API via `BackgroundTasks`).
- Map upstream errors to **`preview_status=failed`**, **`last_error`**, transcript **error** row.

**Patterns to follow:**
- Workspace boundary: multi-step workflow in **service**, not `routes.py`.

**Test scenarios:**
- **Happy path:** Mock adapter; events appear in order; terminal **succeeded** with bundle.
- **Error path:** Mid-flight failure leaves **failed** status and partial transcript per policy.
- **Edge case:** Second POST while **running** returns **409** or ignores with clear contract.

**Verification:**
- No LLM calls from route handlers; tests use mocks at adapter boundary.

---

- [ ] **Unit 4: API — async preview start + poll detail**

**Goal:** **`POST /tasks/ai-draft-preview`** returns quickly with **`preview_status=running`** and schedules the runner; **`GET /tasks/ai-draft-sessions/{id}`** returns **`preview_status`**, **`items` when ready**, and **monotonically growing** `communication_events`.

**Requirements:** R-O1, R-O1b, R-O2, R-O4 (contract for UI)

**Dependencies:** Units 2–3

**Files:**
- Modify: `app/api/routes.py`
- Modify: `app/api/schemas.py`
- Test: `tests/api/test_ai_task_draft_routes.py`

**Approach:**
- Use FastAPI **`BackgroundTasks`** (or equivalent) to start **`run_ai_draft_preview(...)`** after response payload is prepared.
- Response body includes **`draft_session_id`**, **`preview_status`**, and optionally **empty `items`** while running; clients use **GET** for updates.
- Extend **`AiDraftSessionDetailResponse`** (and preview POST response if different schema) with **`preview_status`** and events list.

**Patterns to follow:**
- Existing `scoped_router`, `get_current_active_user`, `tenant_context_dependency`, 404 semantics for cross-user access.

**Test scenarios:**
- **Happy path:** POST returns **running**; poll GET until **succeeded** (use mock + short sleep or dependency-injected runner in tests).
- **Edge case:** List sessions behavior while **running** (show/hide spinner session—product choice; test chosen behavior).
- **Error path:** Runner sets **failed**; GET returns **last_error** + transcript.

**Verification:**
- OpenAPI-shaped responses reviewed; no new unauthenticated routes.

---

- [ ] **Unit 5: frontend — split modal + polling**

**Goal:** Implement **two-pane** modal: left draft UX; right **technical transcript** updated **via polling** while **`preview_status === 'running'`**.

**Requirements:** R-O4

**Dependencies:** Unit 4

**Files:**
- Modify: `frontend/src/components/AiTaskDraftModal.vue`
- Modify: `frontend/src/services/api.js` (only if response typing or fields need client-side parsing helpers)

**Approach:**
- On **POST preview** success, store **`draft_session_id`**, show **loading** on left, start **`setInterval`** (or `requestAnimationFrame` + throttle) to **GET session** until terminal status; **clear interval** on unmount / cancel / completion.
- **Merge or replace** `communication_events` by **`sequence`** to avoid flicker; scroll right pane optional.
- Responsive layout: desktop side-by-side; mobile stack/tab.

**Patterns to follow:**
- Existing modal state: `draftSessionId`, `loadResumableSessions`, error handling, tenant scoping; reuse **AbortController** if adding cancel for in-flight poll only (note: background run may continue server-side).

**Test scenarios:**
- **Manual / browser:** Submit brief → right pane shows **user_input** then **prompt** then **response** over polls; left fills when **succeeded**.
- **Edge case:** Navigate away or close modal — polling stops client-side; document whether server run continues.
- **Error path:** **failed** status surfaces same as today’s error UX plus transcript.

**Verification:**
- Visual check against existing design tokens (spacing, typography) in the file.

---

- [ ] **Unit 6: documentation**

**Goal:** Describe transcript persistence and operational limits for future operators.

**Requirements:** Traceability for rollout (aligns with workspace rule on architecture/runtime doc updates when behavior changes).

**Dependencies:** Unit 4 minimum

**Files:**
- Modify: `docs/runtime-flows.md`
- Modify: `docs/architecture.md` (brief pointer only if already discussing AI draft flow)

**Approach:**
- Document what is stored, retention/TTL interaction (sessions expire; transcript expires with parent), **no secrets** policy, **async preview + polling** contract, and **stuck `running`** operational note (API restart).

**Test scenarios:**
- Test expectation: none — documentation only.

**Verification:**
- Another contributor can find the feature from docs without reading Vue/Python source.

## System-Wide Impact

- **Interaction graph:** AI preview route, **background preview runner**, draft session repo, adapter, session GET for modal.
- **Error propagation:** LLM failures must not leak provider internals on **POST** (return **running** then **failed** on GET); transcript **error** rows are for **authenticated same-user** detail views.
- **State lifecycle risks:** Large JSON columns—watch MySQL `JSON` size and app memory when returning full transcript; consider **`since_sequence`** for poll efficiency. **API restart** may orphan **`running`** sessions—define **stale timeout** or recovery (manual discard / mark failed).
- **API surface parity:** N/A (single app).
- **Integration coverage:** API test for **async** preview + polled GET; repo test for **concurrent run** guard.
- **Unchanged invariants:** Confirm path, task/job creation, and non-AI routes unchanged.

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| **`running` stuck after API crash** | TTL or periodic cleanup; client timeout + user message; optional **heartbeat** column later |
| Duplicate preview spam | Per-session **mutex** or status guard (**409**) |
| Stored prompts contain unexpected PII | Allowlist `tenant_context`; document; optional future scrub pass |
| Transcript size blows up responses | Per-event caps; **`since_sequence`** or transcript-only GET |
| MySQL FK charset mismatch on new FK | Reuse same FK/column typing pattern as `ai_draft_session` |

## Documentation / Operational Notes

- Rollout: new table via `create_all` on deploy; restart API service per hot-swap docs.
- Operators: transcript is **not** a user-facing marketing view—still **authenticated** and **scoped**.

## Sources & References

- **Origin document:** [docs/brainstorms/2026-04-02-ai-task-job-creation-requirements.md](docs/brainstorms/2026-04-02-ai-task-job-creation-requirements.md)
- **Prior slice plan:** [docs/plans/2026-04-03-003-feat-ai-task-draft-slice-3-plan.md](docs/plans/2026-04-03-003-feat-ai-task-draft-slice-3-plan.md)
- Related code: `app/services/integrations/llm_text_adapter.py`, `app/services/ai_task_draft_service.py`, `app/services/ai_draft_session_repo.py`, `frontend/src/components/AiTaskDraftModal.vue`
