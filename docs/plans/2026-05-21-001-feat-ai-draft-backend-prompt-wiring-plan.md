---
title: "feat: AI draft backend prompt wiring, structured outputs, and session migration"
type: feat
status: completed
date: 2026-05-21
origin: docs/brainstorms/2026-05-21-ai-draft-backend-prompt-wiring-requirements.md
---

# feat: AI draft backend prompt wiring, structured outputs, and session migration

## Summary

Wire the AI draft preview pipeline to send tenant master and creation prompts to OpenAI (no `brief`), enforce responses via JSON Schema structured outputs, support multi-turn follow-ups from communication events, pass model/reasoning from the GUI, and migrate `ai_draft_sessions` with `master_prompt_text` / `creation_prompt_text` columns.

---

## Problem Frame

The GUI-first plan shipped prompt controls but the backend still consumed a `brief` shim and a hardcoded system prompt. See origin: `docs/brainstorms/2026-05-21-ai-draft-backend-prompt-wiring-requirements.md`.

---

## Requirements

- R1. Master prompt as OpenAI `system` message; creation prompt as `user` message with tenant context.
- R2. Remove `brief` from `AiTaskDraftRequest` (extra fields forbidden).
- R3. Structured outputs via `json_schema` module.
- R4. Follow-ups: reconstruct conversation from `communication_events`; append instruction as new `user` message.
- R5. Model and reasoning flow from request to OpenAI call.
- R6. DB migration: add `master_prompt_text`, `creation_prompt_text` on `ai_draft_sessions`; keep `brief` as legacy resume label.

---

## Key Technical Decisions

- **Schema module:** `app/services/integrations/ai_draft_response_schema.py` — hardcoded bundle shape, ready for per-tenant extension.
- **Conversation builder:** `app/services/ai_draft_conversation.py` — initial and follow-up message assembly.
- **Model mapping:** `app/services/integrations/ai_draft_llm_config.py` — UI tokens `5.1`/`5.4`/`5.5` → env-configurable OpenAI ids; `reasoning_effort` omitted when `none`.
- **Migration:** `scripts/sync_schema.py` additive DDL for new columns (no Alembic in this repo).
- **Session `brief`:** Still populated from creation text for list/resume labels; API responses expose split fields.

---

## Verification

- `PYTHONPATH=/opt/mvPipeline venv/bin/pytest` — 66 tests in AI draft suite (passed).
- `npm test -- --run src/components/__tests__/aiDraftPromptConfig.spec.js` — passed.
- `venv/bin/python scripts/sync_schema.py` — applied `master_prompt_text`, `creation_prompt_text` columns.
- Restart `mvpipeline-api.service` on deploy host after pull (sudo required in this environment).
