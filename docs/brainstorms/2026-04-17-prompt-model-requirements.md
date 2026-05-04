---
date: 2026-04-17
topic: prompt-model
---

# Tenant Prompts (Storage And CRUD)

## Problem Frame

Task-creation and related AI flows need tenant-specific instruction text that operators can edit in-product instead of scattering prompts across env files or external docs. Today there is no first-class place to store those instructions per tenant. This work introduces a **prompt** entity with full CRUD and navigation from the main header so each tenant can maintain one or more long-form prompts, starting with the **Tasks Creation** type.

## Requirements

**Data and tenancy**

- R1. The product must persist prompt records that belong to exactly one tenant (same tenant-scoping expectations as tasks and other tenant-bound data).
- R2. Each prompt record must carry: a **name** (short string for list identification), a **type** (categorical), the **tenant** it belongs to, and **long-form text** (the prompt body). **Names are not required to be unique** within a tenant; users may disambiguate using type, timestamps, or body preview when duplicates occur.
- R3. The **type** field must be presented in the UI as a select. For this release the select includes: stored value `task-creation`, label **Tasks Creation**; and stored value `master-prompt`, label **Master Prompt**. The interaction model must allow adding more type options later without changing the core meaning of R2.

**Administration**

- R4. Authenticated users must be able to **create, read, update, and delete** prompt records from the product, with access constrained to the **current tenant context** (consistent with how other tenant-scoped resources behave).
- R5. A tenant may have **multiple** prompt rows for the same type (e.g. library, drafts, or variants). No requirement for a single canonical row per type in this version.

**Navigation**

- R6. The app header must include a **link next to the Tasks entry** that routes to the prompt management experience (list/create/edit/delete).

## Success Criteria

- Operators can maintain long **Tasks Creation** instructions per tenant entirely inside the app.
- Each prompt is easy to recognize in lists using its **name** without opening the full body.
- CRUD respects tenant isolation: one tenant cannot read or change another tenant’s prompts.
- New users can discover prompt management from the header without relying on a hidden URL.

## Scope Boundaries

- **Out of scope for this slice:** Automatically using stored prompt text inside the AI task-creation LLM call path (may follow as a separate change once content exists).
- **Out of scope:** Additional prompt types beyond **Tasks Creation** and **Master Prompt** until product adds the next select option (model and UI should not hard-block that).

## Key Decisions

- **Multiple rows per tenant per type:** Chosen so tenants can keep several prompts (variants or history) rather than forcing a single global string per type.
- **Name field:** Each prompt has a **name** so list and pick flows can disambiguate rows without reading the full body. Duplicate names within a tenant are **allowed**.

## Dependencies / Assumptions

- Assumes the same **authentication and tenant context** model as the rest of the authenticated app (no new public, unauthenticated prompt surfaces).
- Complements the direction in `docs/brainstorms/2026-04-02-ai-task-job-creation-requirements.md` (tenant-aware authoring) without requiring the AI flow to consume this storage in the first slice.

## Outstanding Questions

### Resolve Before Planning

- (none)

### Deferred to Planning

- **[Affects R6][Product]** Exact nav label (e.g. **Prompts** vs **Task prompts**) and route path slug.
- **[Affects R4/R5][UX]** List UX when many prompts exist: sort order default (e.g. by last updated), and whether to also show a truncated preview of the body under the name.
- **[Affects R2][Product]** Validation rules for **name** (max length, trimming, empty vs required) — planning should propose sensible defaults. Uniqueness per tenant is **not** required.

## Next Steps

Implementation plan: `docs/plans/2026-04-17-002-feat-tenant-prompts-crud-plan.md` — run `/ce:work` or implement from that document.
