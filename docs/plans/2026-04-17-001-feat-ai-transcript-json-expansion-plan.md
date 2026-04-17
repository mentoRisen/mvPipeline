---
title: "feat: Expand nested JSON strings in AI transcript view"
type: feat
status: active
date: 2026-04-17
origin: docs/brainstorms/2026-04-16-ai-draft-iterative-instructions-requirements.md
---

# feat: Expand nested JSON strings in AI transcript view

## Overvieww

Improve readability of AI transcript payloads in the draft modal by parsing selected JSON-encoded string attributes and rendering them as formatted nested JSON instead of escaped/compressed text.

## Problem Frame

The transcript panel in `frontend/src/components/AiTaskDraftModal.vue` currently renders `ev.payload` with direct pretty stringify. This is readable for normal objects, but hard to inspect when nested fields are JSON-encoded strings (for example `content` and `messages[].content`). The escaped payload output increases debugging friction and obscures model prompt/response structure.

This change is rendering-only: it must preserve transcript history semantics and avoid mutating source payloads (see origin: `docs/brainstorms/2026-04-16-ai-draft-iterative-instructions-requirements.md`).

## Requirements Trace

- R1. Transcript payload rendering parses configured JSON-string fields and displays expanded formatted JSON when parsing succeeds.
- R2. Expansion targets are defined in one local constant to avoid scattered hardcoded checks.
- R3. Invalid or non-JSON strings at target fields fail safely and remain visible as raw values.
- R4. Existing transcript behavior for non-target and non-string fields remains unchanged.
- R5. Rendering flow remains non-mutating and stable across live polling and resumed sessions. 

## Scope Boundaries

- No backend payload schema changes.
- No changes to transcript event ordering, persistence, or API contracts.
- No rich tree UI/collapse controls in this iteration; output remains text-based `pre` rendering.

### Deferred to Separate Tasks

- Optional future expansion rule UI/editor for operators.
- Performance tuning for very large transcript payloads if this becomes a measured bottleneck.

## Context & Research

### Relevant Code and Patterns

- `frontend/src/components/AiTaskDraftModal.vue` currently uses `formatTranscriptPayload(ev)` with `JSON.stringify(ev.payload, null, 2)`.
- `frontend/src/components/TaskDetail.vue` and `frontend/src/components/TenantDetail.vue` show local helper patterns for JSON formatting/parsing rather than global utilities.
- Existing AI draft tests are backend-heavy (`tests/services/` and `tests/api/`), so frontend formatting logic should be isolated in a small helper seam for targeted verification.

### Institutional Learnings

- `docs/solutions/logic-errors/ai-draft-session-cap-trim-deletes-history-2026-04-07.md` reinforces observability-first behavior: preserve debug context and prefer deterministic fail-safe handling over silent mutation.

### External References

- None. Local codebase patterns are sufficient for this frontend-scoped formatting enhancement.

## Key Technical Decisions

- **Extract formatter from modal into a feature-local helper module**: keeps `AiTaskDraftModal` maintainable and allows focused tests for path expansion behavior.
- **Use explicit, minimal expansion rules**: maintain one configuration list for the initial targets (`content`, `messages[].content`, `brief`) and apply only the traversal needed for these paths.
- **Single-pass parse only for target string fields**: avoid recursive over-decoding and preserve predictable output.
- **Fail-safe formatting contract**: parse errors never throw; raw value remains visible when expansion fails.
- **Non-mutating transformation**: formatting pipeline works on cloned data before stringification to avoid state drift across polling/resume flows.
- **Deterministic clone/fallback contract**: object/array payloads are cloned with guarded logic; clone or stringify failures fall back to safe string output rather than throwing.

## Open Questions

### Resolved During Planning

- Should expansion be generic or hardcoded by event kind?
  - Resolution: generic payload-path expansion, independent of event kind, with explicit target rule list.

### Deferred to Implementation

- Should expanded output include inline parse-status markers (for example `raw-fallback`)?
  - Deferred because the final text representation choice depends on UX preference after seeing real output samples.

## High-Level Technical Design

> *This illustrates the intended approach and is directional guidance for review, not implementation specification. The implementing agent should treat it as context, not code to reproduce.*

```text
input event payload
  -> clone payload (no mutation)
  -> for each expansion rule:
       locate matching path(s)
       if value is string:
         try parse JSON once
         if parse succeeds: replace value with parsed object/array/scalar
         else: keep original string
       if path segment is missing/wrong type: no-op (never create missing structures)
  -> stringify transformed payload with indentation
  -> return safe fallback string when stringify fails
```

## Implementation Units

- [ ] **Unit 1: Add formatter helper and formatter-seam tests**

**Goal:** Add a reusable formatter utility that expands configured JSON-string payload attributes before pretty rendering.

**Requirements:** R1, R2, R3, R5

**Dependencies:** None

**Files:**
- Create: `frontend/src/components/aiDraftTranscriptFormatting.js`
- Modify: `frontend/package.json` (only if frontend test runner is missing)
- Create/Modify: `frontend/vitest.config.js` (only if missing)
- Create/Modify: `frontend/src/components/__tests__/testSetup.js` (only if missing)
- Test: `frontend/src/components/__tests__/aiDraftTranscriptFormatting.spec.js`

**Approach:**
- Define an exported expansion-rule constant for initial targets:
  - top-level `content`
  - each `messages[*].content`
  - top-level `brief`
- Implement helper functions to:
  - safely clone input payload with guarded fallback behavior
  - traverse only the required path shapes (top-level field and `messages` array item field)
  - parse JSON only when candidate value is a string
  - preserve raw values on parse failure
- Return final formatted string for UI rendering.
- Add focused formatter tests for the three expansion targets and fallback behavior.
- If no frontend test harness exists, add minimal Vitest + Vue test dependencies/config first, then execute formatter tests.

**Patterns to follow:**
- Local utility pattern from `frontend/src/components/TenantDetail.vue` for safe parse/format behavior.
- Existing modal-level formatting contract from `frontend/src/components/AiTaskDraftModal.vue`.

**Test scenarios:**
- Happy path: `payload.content` contains JSON string -> rendered output shows expanded nested object.
- Happy path: `payload.messages` contains objects with JSON-string `content` -> each applicable entry expands.
- Edge case: `messages` includes mixed non-object elements -> no throw; non-matching elements remain unchanged.
- Edge case: missing `messages`, wrong `messages` type, or empty `messages` array -> no-op traversal and stable output.
- Edge case: target field contains JSON scalar/array string -> parsed and rendered consistently.
- Error path: invalid JSON string at target field -> raw string retained; formatter does not throw.
- Integration: formatter does not mutate original payload object passed by caller.

**Verification:**
- Helper returns stable pretty JSON text with expanded target fields and safe fallback behavior for malformed inputs.

- [ ] **Unit 2: Integrate helper into AI draft modal transcript rendering**

**Goal:** Replace inline payload stringify in modal with helper-based formatting.

**Requirements:** R1, R3, R4, R5

**Dependencies:** Unit 1 (and its conditional test-harness setup if missing)

**Files:**
- Modify: `frontend/src/components/AiTaskDraftModal.vue`
- Test: `frontend/src/components/__tests__/AiTaskDraftModal.transcript.spec.js`

**Approach:**
- Import helper and update `formatTranscriptPayload(ev)` to delegate to it.
- Keep existing method signature and `pre` rendering shape to avoid template churn.
- Confirm behavior remains safe when `ev.payload` is null, primitive, array, or object.
- Add a narrow modal transcript test only if lightweight component mounting is already practical after Unit 1 setup; otherwise rely on formatter-seam tests plus manual transcript verification in this iteration.

**Patterns to follow:**
- Existing `formatTranscriptPayload(ev)` call site and transcript block rendering in `frontend/src/components/AiTaskDraftModal.vue`.

**Test scenarios:**
- Happy path: modal renders transcript events where target fields are expanded and easier to read.
- Edge case: event with non-object payload still renders without UI error.
- Error path: malformed nested JSON-string remains visible raw and component stays functional.
- Integration: resumed/polled communication events render consistently via same formatting path.

**Verification:**
- Transcript panel output remains stable while readability improves for configured encoded fields.

## System-Wide Impact

- **Interaction graph:** Change is frontend-only at transcript rendering seam; no backend/service contract changes.
- **Error propagation:** Parse/stringify failures are contained in formatter helper and surfaced as safe fallback text, not thrown errors.
- **State lifecycle risks:** Main risk is accidental mutation of payload references during polling/resume updates; mitigated with clone-before-transform.
- **API surface parity:** Existing API responses and route payload shapes remain unchanged.
- **Integration coverage:** Resume and live polling event flows should both pass through identical formatter path.
- **Unchanged invariants:** Event sequence ordering, transcript persistence, and stored raw payload values are unchanged by this plan.

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| Over-eager parsing alters fields that should remain plain text | Restrict parsing to explicit expansion rule list only |
| Malformed nested JSON causes rendering failures | Wrap parse/stringify in guarded helpers with raw fallback |
| Large transcripts cause repeated parse overhead during polling | Keep transformation linear and scoped to rule paths; defer optimization unless profiling shows impact |
| Frontend test setup introduces scope churn | Make harness setup conditional and minimal; prioritize formatter-seam coverage |

## Documentation / Operational Notes

- No operational changes expected (no service restart implications).
- Optional follow-up: short developer note documenting how to add new expansion paths safely.

## Sources & References

- **Origin document:** [docs/brainstorms/2026-04-16-ai-draft-iterative-instructions-requirements.md](docs/brainstorms/2026-04-16-ai-draft-iterative-instructions-requirements.md)
- **Institutional learning:** [docs/solutions/logic-errors/ai-draft-session-cap-trim-deletes-history-2026-04-07.md](docs/solutions/logic-errors/ai-draft-session-cap-trim-deletes-history-2026-04-07.md)
- Related code: `frontend/src/components/AiTaskDraftModal.vue`
