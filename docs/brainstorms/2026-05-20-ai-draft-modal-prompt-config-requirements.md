---
date: 2026-05-20
topic: ai-draft-modal-prompt-config
---

# AI Draft Modal — Prompt & Model Configuration

## Summary

Refactor the AI Create Campaign modal so the **campaign brief is removed**. Operators configure the run via **Master Prompt** and **Creation Prompt** text (each with a type-filtered saved-prompt picker that prefills the textarea), plus **model** (5.1 / 5.4 / 5.5) and **reasoning** (none / low / medium / high). **Phase 1 is GUI-only**; backend may use a temporary shim until the preview API drops `brief` in favor of explicit prompt fields.

## Problem Frame

AI draft quality depends on which instructions and model settings reach the LLM. Prompts are already stored per tenant (`master-prompt`, `task-creation`), but the draft modal still uses a single free-text **brief** and hardcoded adapter prompts. The product direction is to replace the brief with **two explicit prompt fields** filled manually or from saved rows in the prompts table.

## Requirements

**Prompt selection**
- R1. The modal exposes **Master Prompt** and **Creation Prompt** sections.
- R2. Each section has a **saved-prompt select** and a **textarea**.
- R3. Saved options are loaded from tenant prompts and **filtered by type**: Master slot → `master-prompt`; Creation slot → `task-creation`.
- R4. Choosing a saved prompt **prefills** that slot’s textarea with the saved **body**; the user may edit afterward.

**Model and reasoning**
- R5. **Model** select: `5.1`, `5.4`, `5.5`; default **5.1**.
- R6. **Reasoning** select: `none`, `low`, `medium`, `high`; default **none**.

**Phase boundary**
- R7. This delivery is **frontend-only**; breaking or ignoring new fields on the preview API is acceptable.
- R8. A follow-on slice must document and implement backend wiring (request schema, adapter messages, persistence).

**Layout / removed field**
- R9. The modal **does not** include a separate campaign brief field; **Master** and **Creation** prompt textareas are the primary inputs.
- R10. Draft session resume, bundle review, confirm, and transcript column remain; resume labeling may use a prompt excerpt until sessions store split prompts (follow-up).

**Generate gate (GUI phase)**
- R11. **Generate Draft** requires non-empty **Creation** prompt text (minimum); Master may be optional or required — default **both** textareas non-empty before generate.

## Acceptance Examples

- AE1. **Covers R3, R4.** Given saved master prompts A and B, when the user selects B in the Master dropdown, the Master textarea shows B’s body.
- AE2. **Covers R3, R4.** Given saved creation prompts, when the user selects one in the Creation dropdown, the Creation textarea prefills; editing the textarea does not clear the dropdown selection.
- AE3. **Covers R5, R6.** Given a fresh modal open, model is 5.1 and reasoning is none until changed.
- AE4. **Covers R9, R7.** Given the modal is open, there is no brief textarea; only Master and Creation sections appear above model/reasoning.
- AE5. **Covers R7, R11.** Given preview API still expects `brief`, when the user generates, the client may send a **temporary shim** (e.g. creation text or a structured concat) in the `brief` field until the backend slice removes it.

## Success Criteria

- Operators can configure both prompts, model, and reasoning in the modal without using the separate Prompts admin page for every run.
- UI state is clear (loading prompts, empty catalogs, tenant not selected).
- Follow-on backend work is enumerated with no ambiguity about what the GUI fields mean.

## Scope Boundaries

- Backend changes to `AiTaskDraftRequest`, `OpenAITextDraftAdapter`, or session autosave for AI config.
- New `PromptType` values beyond `master-prompt` and `task-creation`.
- Removing follow-up iteration UI in this slice (may remain; iteration still uses instruction text, not brief).
- Full migration of `ai_draft_sessions.brief` column and resume UX to split prompt fields (follow-up).
- Persisting AI config on draft session resume (optional later).

## Key Decisions

- **Filtered catalogs:** Separate dropdowns per slot using existing `PromptType` values (not one shared list).
- **GUI-first:** Ship modal UX before API/adapter integration.
- **Defaults:** Model 5.1, reasoning none (product choice for cost/latency baseline until 5.5 integration is proven).

## Outstanding Questions

### Deferred to Planning

- [Technical] Exact API model id strings sent to OpenAI (e.g. `gpt-5.1` vs product labels).
- [Technical] Whether Generate should require non-empty Master/Creation text in GUI-only phase or only brief (rehearsal vs strict validation).
