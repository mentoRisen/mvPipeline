---
title: AI draft backend prompt wiring and structured outputs
date: 2026-05-22
category: architecture-patterns
module: ai-task-draft
problem_type: architecture_pattern
component: service_object
severity: medium
applies_when:
  - Extending AI task draft preview or follow-up iteration on the backend
  - Changing how tenant master and creation prompts reach OpenAI
  - Persisting or resuming draft sessions with split prompt fields
symptoms:
  - GUI exposed master and creation prompts but preview still used a brief shim and hardcoded system text
  - Follow-up iterations could not reconstruct multi-turn context from communication events
  - Model and reasoning tokens from the UI were not mapped to OpenAI request parameters
root_cause: wrong_api
resolution_type: code_fix
related_components:
  - database
  - integrations
tags:
  - ai-draft
  - master-prompt
  - creation-prompt
  - structured-outputs
  - json-schema
  - openai
  - communication-events
  - sync-schema
---

# AI draft backend prompt wiring and structured outputs

## Context

The GUI-first AI Create Campaign modal shipped **Master Prompt**, **Creation Prompt**, **model**, and **reasoning** controls, but the backend preview pipeline still treated operator input as a single `brief` string with a hardcoded system prompt and unstructured `json_object` responses. Follow-up iterations concatenated instructions onto `brief` instead of preserving conversational context.

This slice wires the backend to match the GUI contract: split prompts, OpenAI strict JSON Schema, transcript-based multi-turn follow-ups, and per-request model/reasoning from the API. Plan reference: `docs/plans/2026-05-21-001-feat-ai-draft-backend-prompt-wiring-plan.md`.

## Guidance

### Split prompt contract on the API

`AiTaskDraftRequest` (`app/api/schemas.py`) uses `extra="forbid"` — legacy `brief` returns 422. Initial preview requires `master_prompt_text` and `creation_prompt_text`. Follow-ups require `instruction_text`, `draft_session_id`, and validated `iteration_mode` / `target_scope`.

Routes (`app/api/routes.py`) resolve prompts via `_resolve_preview_prompts()` (session backfill uses `creation_prompt_text or row.brief` for legacy rows) and freeze `max_tasks` / `max_jobs` from the first `user_input` communication event on follow-ups.

### Conversation assembly (shared service, not routes)

`app/services/ai_draft_conversation.py`:

- **Initial:** `build_initial_preview_messages()` — `system` = master prompt; `user` = JSON `{creation_prompt, tenant_context}` with allowlisted tenant fields only.
- **Follow-up:** `build_follow_up_messages_from_events()` — replays the last `prompt_to_ai` message array, appends the last `response_from_ai` assistant content, then a new `user` turn with iteration metadata and `instruction_text`.

### OpenAI adapter and structured outputs

`app/services/integrations/llm_text_adapter.py` posts chat completions with `response_format` from `draft_bundle_json_schema()` in `app/services/integrations/ai_draft_response_schema.py` (strict mode: all properties required; optional fields use nullable types).

`app/services/integrations/ai_draft_llm_config.py` maps GUI tokens `5.1` / `5.4` / `5.5` and reasoning `none` / `low` / `medium` / `high` to OpenAI parameters (`reasoning_effort` omitted when `none`).

### Async preview runner and transcript

`app/services/ai_draft_preview_runner.py` logs `user_input` → `prompt_to_ai` (full `messages`) → `response_from_ai` → validates via `AiTaskDraftService.validate_raw_llm_dict()` → persists bundle or structured failure.

### Session persistence

`scripts/sync_schema.py` adds `master_prompt_text` and `creation_prompt_text` on `ai_draft_sessions`. Legacy `brief` column remains populated from creation text for resume list labels.

## Why This Matters

| Concern | Mechanism |
|--------|-----------|
| Tenant owns system behavior | Master prompt is the OpenAI `system` message — no hardcoded adapter prompt |
| Creation intent separated from brand rules | Creation prompt in user JSON; master stays stable across iterations |
| Safe tenant data | `build_tenant_context()` allowlists name, description, instagram_account, facebook_page only |
| Reliable LLM shape | Strict JSON Schema at provider; service validates again before persisting |
| Follow-up quality | Multi-turn replay from server transcript; client sends only the new instruction |
| GUI controls honored | `model` / `reasoning` flow route → runner → resolver → OpenAI payload |

## When to Apply

- Adding new LLM preview or iteration flows in mvPipeline
- Frontend and backend prompt contracts diverge (avoid long-lived client shims)
- Responses must match domain models (`Task`, `Job`, `AiTaskDraftItem`)
- Iterations need context without trusting the client to replay history

**Deploy checklist:**

1. Run `venv/bin/python scripts/sync_schema.py` (adds prompt columns).
2. Restart `mvpipeline-api.service` after deploy.
3. Stage untracked implementation files before PR (`ai_draft_conversation.py`, `ai_draft_llm_config.py`, `ai_draft_response_schema.py`, and their tests).

## Examples

### Before: brief shim

```json
{
  "brief": "Create a launch post",
  "instruction_text": "Make it more playful"
}
```

OpenAI saw a hardcoded system prompt and `brief` in user JSON; follow-ups re-sent a mutated brief as a single turn.

### After: split prompts (initial)

```json
{
  "master_prompt_text": "You are Acme's brand voice...",
  "creation_prompt_text": "Create a launch post for spring campaign",
  "model": "5.5",
  "reasoning": "medium",
  "max_tasks": 2,
  "max_jobs": 4
}
```

### After: follow-up

```json
{
  "draft_session_id": "...",
  "iteration_mode": "regenerate",
  "instruction_text": "Make it more playful",
  "target_scope": "campaign"
}
```

## Prevention

- Put message-array construction in `app/services/ai_draft_conversation.py`, not route handlers or adapters
- Keep JSON Schema in `app/services/integrations/ai_draft_response_schema.py` for future per-tenant extension
- Log full `messages` in `prompt_to_ai` events — follow-ups depend on it; watch `AI_DRAFT_COMMUNICATION_MAX_PAYLOAD_BYTES` on long sessions
- Use `AiTaskDraftService.validate_raw_llm_dict()` as the single post-LLM validation gate
- Do not reintroduce `brief` on `AiTaskDraftRequest`
- Validate unknown `model` / `reasoning` tokens at the API layer (silent fallback to default model is confusing)

**Anti-patterns:** hardcoded system prompts when tenant master exists; client-sent full conversation history; `json_object` without schema for structured domain output.

## Related

- [AI draft cap trimming deleted active session history](../logic-errors/ai-draft-session-cap-trim-deletes-history-2026-04-07.md) — reject-at-cap policy; transcript retention under cap pressure
- Plan: `docs/plans/2026-05-21-001-feat-ai-draft-backend-prompt-wiring-plan.md`
- Requirements: `docs/brainstorms/2026-05-21-ai-draft-backend-prompt-wiring-requirements.md`
