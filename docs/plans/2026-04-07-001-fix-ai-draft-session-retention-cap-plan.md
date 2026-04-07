---
title: "fix: AI draft session retention with manual-cap enforcement"
type: fix
status: completed
date: 2026-04-07
origin: docs/plans/2026-04-06-001-feat-ai-draft-communication-log-plan.md
---

# fix: AI draft session retention with manual-cap enforcement

## Overview

Rework AI draft session lifecycle so sessions are never auto-deleted for capacity control. Enforce the per-user open-draft cap by rejecting creation of additional drafts until the user manually discards old ones.

## Problem Frame

Current repository behavior trims oldest active sessions to stay under `AI_DRAFT_SESSION_MAX_PER_USER`. That can delete in-flight or still-useful draft sessions and remove valuable communication history needed for debugging and audit workflows.

## Requirements Trace

- **R-R1.** Remove auto-deletion for draft session capacity management.
- **R-R2.** Keep transcript/session history for debugging; retention policy must not silently delete rows during normal preview flow.
- **R-R3.** When open draft count reaches `AI_DRAFT_SESSION_MAX_PER_USER`, `POST /tasks/ai-draft-preview` must reject new session creation with a clear, actionable response.
- **R-R4.** Re-using an existing `draft_session_id` for preview rerun remains allowed (no extra slot consumed).
- **R-R5.** Frontend surfaces cap-reached failures clearly and directs users to discard old drafts.

## Scope Boundaries

- In scope: per-user cap behavior for AI draft sessions and user-visible error handling.
- Out of scope: full archival/history endpoint redesign and pagination expansion.
- Out of scope: deleting historical sessions via background cleanup jobs.

## Context & Research

### Relevant Code and Patterns

- `app/services/ai_draft_session_repo.py` currently trims via `_trim_oldest_active_sessions(...)` from `start_preview_run(...)`.
- `app/api/routes.py` delegates preview start to repo and surfaces `HTTPException` semantics.
- `frontend/src/components/AiTaskDraftModal.vue` already handles API errors and saved-session resume UX.
- `tests/services/test_ai_draft_session_repo.py` and `tests/api/test_ai_task_draft_routes.py` contain session lifecycle test patterns.

### Institutional Learnings

- `docs/solutions/` is not present in this repository.

## Key Technical Decisions

- **No implicit deletion for cap control:** replace trim-on-create with count-and-reject policy.
- **Cap applies to open drafts:** count active draft sessions for `(tenant_id, user_id)` as cap candidates; confirm/discard continues to remove drafts from open pool.
- **Explicit failure contract:** return `409` with machine-readable error payload and human-readable remediation.

## Open Questions

### Resolved During Planning

- Include `running` sessions in cap accounting: **yes** (prevents preview spam and keeps rule simple).

### Deferred to Implementation

- Whether to include structured cap metadata in response body (for example `open_count`, `max_per_user`) now or in follow-up.

## Implementation Units

- [x] **Unit 1: repository cap policy rework**

**Goal:** Stop deleting sessions for capacity and enforce cap by rejection.

**Requirements:** R-R1, R-R2, R-R3, R-R4

**Dependencies:** None

**Files:**
- Modify: `app/services/ai_draft_session_repo.py`
- Test: `tests/services/test_ai_draft_session_repo.py`

**Approach:**
- Remove `_trim_oldest_active_sessions(...)` from new-session path.
- Add open-session count guard in `start_preview_run(...)` before creating a new session row.
- Keep existing behavior for rerun using `draft_session_id` (no new row, no new slot).
- Raise `HTTPException(status_code=409, ...)` with stable error identifier.

**Patterns to follow:**
- Existing scoped checks and `HTTPException` usage in `app/services/ai_draft_session_repo.py`.

**Test scenarios:**
- Happy path: under cap, create new preview session succeeds.
- Edge case: at cap, new preview without `draft_session_id` returns 409 and does not create row.
- Edge case: at cap, rerun with existing `draft_session_id` is allowed.
- Integration: discard one active session then create new preview succeeds immediately.

**Verification:**
- Repository tests confirm no delete-on-cap behavior and deterministic 409 rejection.

---

- [x] **Unit 2: API contract and frontend error UX**

**Goal:** Surface cap-reached response to users with clear remediation.

**Requirements:** R-R3, R-R5

**Dependencies:** Unit 1

**Files:**
- Modify: `app/api/routes.py` (only if response shape mapping is needed)
- Modify: `frontend/src/components/AiTaskDraftModal.vue`
- Test: `tests/api/test_ai_task_draft_routes.py`

**Approach:**
- Preserve 409 from repo through preview route.
- Ensure modal displays actionable message ("discard old drafts to continue") and keeps resume/discard flow accessible.

**Patterns to follow:**
- Existing preview error mapping in route tests and modal error rendering pattern.

**Test scenarios:**
- Happy path: normal preview still starts when under cap.
- Error path: cap reached yields 409 with expected detail payload.
- Error path: frontend shows cap-specific message and does not enter generating/polling state.

**Verification:**
- API tests assert 409 contract; manual UI check confirms clear user guidance.

---

- [x] **Unit 3: documentation alignment**

**Goal:** Update runtime/architecture docs to reflect no-auto-delete retention and manual cap enforcement.

**Requirements:** R-R2, R-R3

**Dependencies:** Unit 1

**Files:**
- Modify: `docs/runtime-flows.md`
- Modify: `docs/architecture.md`

**Approach:**
- Replace wording that implies auto-trim/auto-expire removal.
- Document operator/user expectation: history retained; users must discard to free open-draft slots.

**Test scenarios:**
- Test expectation: none -- documentation-only unit.

**Verification:**
- Docs describe current behavior accurately without reading implementation.

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| Users hit cap more often and perceive friction | Clear 409 message plus obvious resume/discard actions in modal |
| Historical data growth increases table size | Keep existing payload caps; plan separate pagination/archival enhancement if needed |

## Documentation / Operational Notes

- This rework intentionally prioritizes observability/debug retention over automatic cleanup.
- No migration required for this behavior change; schema remains unchanged.

## Sources & References

- Origin plan: [docs/plans/2026-04-06-001-feat-ai-draft-communication-log-plan.md](docs/plans/2026-04-06-001-feat-ai-draft-communication-log-plan.md)
- Related code: `app/services/ai_draft_session_repo.py`, `app/api/routes.py`, `frontend/src/components/AiTaskDraftModal.vue`
