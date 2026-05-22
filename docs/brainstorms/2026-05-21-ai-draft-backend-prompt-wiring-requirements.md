---
date: 2026-05-21
topic: ai-draft-backend-prompt-wiring
---

# AI Draft Backend — Prompt Wiring, Structured Outputs, and Model Controls

## Summary

Rework the backend AI draft pipeline so the tenant's saved master prompt becomes the OpenAI system message, the creation prompt becomes the user message, and the `brief` field is removed. Switch from freeform `json_object` mode to OpenAI structured outputs with an explicit JSON Schema. Wire model and reasoning controls from the frontend through to the API call. Handle follow-up/modification prompts as multi-turn conversations reconstructed server-side from stored communication events.

---

## Problem Frame

The AI draft preview pipeline currently hardcodes a system prompt in `OpenAITextDraftAdapter._system_prompt()` and sends the operator's input as a single `brief` string wrapped in a JSON blob. The GUI-first plan (2026-05-20) shipped master prompt and creation prompt textareas and model/reasoning selects, but the frontend still shims everything into `brief` because the backend has not been updated. The response format uses OpenAI's unstructured `json_object` mode, which provides no schema enforcement and relies on prompt-level instructions to coerce the correct shape. Follow-up iterations concatenate instruction text onto the brief string rather than preserving conversational context.

---

## Requirements

**Prompt structure**
- R1. The tenant's master prompt text replaces the hardcoded system prompt entirely and is sent as the `system` role message.
- R2. The creation prompt text is sent as the `user` role message, alongside tenant context.
- R3. The `brief` field is removed from the API request schema (`AiTaskDraftRequest`).

**Response format**
- R4. The OpenAI call uses structured outputs (`response_format: {"type": "json_schema", ...}`) with an explicit JSON Schema matching the current `AiTaskDraftItem` shape.
- R5. The JSON Schema definition is extracted into a separate module so it can be extended or replaced per-tenant in the future.

**Follow-up / modification prompts**
- R6. Follow-up iterations use multi-turn conversation: the backend reconstructs prior system/user/assistant messages from stored `communication_events`, then appends the new follow-up instruction as a `user` message.
- R7. The frontend sends only the new follow-up instruction text; the backend is the source of truth for conversation history.

**Model and reasoning controls**
- R8. The frontend-selected model identifier flows through the API request to the OpenAI call.
- R9. The frontend-selected reasoning level flows through the API request and maps to the appropriate OpenAI parameter.
- R10. The env-level `AI_TASK_DRAFT_MODEL` config becomes the fallback default when no per-request model is provided.

---

## Acceptance Examples

- AE1. **Covers R1, R2.** Given a tenant with a saved master prompt and a creation prompt entered in the modal, when the operator generates a draft, the OpenAI request contains the master prompt text as the `system` message and the creation prompt as the `user` message — no hardcoded system prompt.
- AE2. **Covers R3.** Given the updated API, when a client sends a request with a `brief` field, the request is rejected (extra field forbidden).
- AE3. **Covers R4.** Given any draft generation, the OpenAI payload uses `response_format` with `type: json_schema` and a schema matching the items/task/jobs structure.
- AE4. **Covers R6, R7.** Given an existing draft session with prior communication events, when the operator submits a follow-up instruction, the backend sends a multi-turn messages array (system + prior user + prior assistant + new user instruction) without the frontend sending the full history.
- AE5. **Covers R8, R9.** Given the operator selects model "5.5" and reasoning "medium" in the modal, the OpenAI request uses the corresponding model identifier and reasoning parameter.

---

## Success Criteria

- Operators control the full system prompt via tenant master prompts without code changes.
- LLM responses conform to a defined schema, reducing parse failures from freeform JSON.
- Follow-up iterations carry conversation context, improving modification quality.
- Model and reasoning selections from the GUI reach the LLM call.

---

## Scope Boundaries

- Frontend changes to the modal GUI (already shipped in the 2026-05-20 plan).
- New `PromptType` values beyond `master-prompt` and `task-creation`.
- Streaming responses from the LLM.
- Per-tenant customizable JSON response schemas (the extracted module enables this later only).

---

## Key Decisions

- **Tenant owns the system prompt**: The master prompt fully replaces the hardcoded `_system_prompt()`. Structural format instructions move into the JSON Schema definition, not the prompt.
- **Hybrid follow-up**: Backend reconstructs conversation from communication events; frontend sends only the new instruction. Keeps the API payload small and the server as source of truth.
- **Schema extracted, not customizable yet**: The JSON Schema is hardcoded to the current response shape but lives in its own module for future per-tenant flexibility.
- **Reasoning via OpenAI parameter**: Reasoning level maps to OpenAI's `reasoning_effort` parameter (or model-family equivalent), not prompt-level instructions.

---

## Dependencies / Assumptions

- The GUI-first plan (2026-05-20) is complete — the frontend already sends `master_prompt_text`, `creation_prompt_text`, `model`, and `reasoning` (currently shimmed into `brief`).
- OpenAI's Chat Completions API supports `response_format: {"type": "json_schema", ...}` for the target model family.
- The `communication_events` table reliably stores the full message exchange needed for multi-turn reconstruction.

---

## Outstanding Questions

### Deferred to Planning

- [Affects R2][Technical] How tenant context is incorporated into the user message alongside creation prompt text.
- [Affects R4][Needs research] Exact OpenAI structured outputs JSON Schema syntax and any model-specific restrictions.
- [Affects R8][Technical] Mapping from GUI model labels (5.1 / 5.4 / 5.5) to OpenAI model identifiers.
- [Affects R9][Needs research] Whether `reasoning_effort` is supported on all target models or only specific ones.
- [Affects R6][Technical] How `iteration_mode` and `target_scope` are represented in the multi-turn conversation.
