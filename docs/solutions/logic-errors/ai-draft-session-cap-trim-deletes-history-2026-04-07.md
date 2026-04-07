---
title: AI draft cap trimming deleted active session history
date: 2026-04-07
category: logic-errors
module: ai-draft-sessions
problem_type: logic_error
component: service_object
symptoms:
  - AI preview requests intermittently failed to finish when users had many draft sessions.
  - Session/transcript history disappeared unexpectedly during new draft creation.
  - `journalctl` showed preview flow errors tied to session lifecycle assumptions.
root_cause: logic_error
resolution_type: code_fix
severity: high
tags: [ai-draft, session-retention, cap-enforcement, transcript-history]
---

# AI draft cap trimming deleted active session history

## Problem
The AI draft session repository used capacity trimming that deleted oldest active sessions when creating a new draft. This conflicted with the requirement to retain draft/transcript history for debugging and made preview flow behavior non-deterministic under cap pressure.

## Symptoms
- New preview creation at or near cap could remove prior active sessions without user intent.
- In-flight or recently active debugging context could disappear from resume/transcript views.
- Users could not trust saved AI draft history as an audit/debug trail.

## What Didn't Work
- Relying on implicit trim-on-create to keep cap under control.  
  This solved storage pressure but violated observability/debug retention and introduced lifecycle races.

## Solution
Reworked repository policy from "delete oldest when full" to "reject new session creation at cap."

Key changes:
- Removed trim behavior from `start_preview_run(...)` and `save_after_preview(...)`.
- Added `_count_open_active_sessions(...)` and explicit `409` rejection when `AI_DRAFT_SESSION_MAX_PER_USER` is reached.
- Kept rerun behavior for existing `draft_session_id` intact (no new slot consumed).
- Returned structured error details:
  - `error: "ai_draft_session_limit_reached"`
  - `message: "Maximum open AI drafts reached. Discard old drafts to continue."`
  - `max_per_user`
- Updated modal error formatter to show a cap-specific remediation message.
- Added repository/API tests for cap-reached and rerun-at-cap paths.

## Why This Works
The prior logic optimized for capacity by mutating user state implicitly. The new logic preserves state and moves control to explicit user actions (discard/confirm), which aligns with retention/debug requirements and avoids silent data loss.

## Prevention
- For retention-sensitive entities, prefer explicit rejection over implicit deletion when limits are hit.
- Test cap behavior at service seam and API seam:
  - create-under-cap succeeds
  - create-at-cap returns deterministic `409`
  - rerun existing session at cap remains allowed
- Keep user-facing remediation messages aligned with backend error codes.

## Related Issues
- Plan: `docs/plans/2026-04-07-001-fix-ai-draft-session-retention-cap-plan.md`
- Plan: `docs/plans/2026-04-06-001-feat-ai-draft-communication-log-plan.md`
- Updated files: `app/services/ai_draft_session_repo.py`, `tests/services/test_ai_draft_session_repo.py`, `tests/api/test_ai_task_draft_routes.py`, `frontend/src/components/AiTaskDraftModal.vue`
