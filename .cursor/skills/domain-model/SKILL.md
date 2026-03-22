---
name: domain-model
description: Applies mvPipeline domain terminology, entities, and workflow invariants. Use when working on tasks, jobs, tenants, scheduler features, API schemas, docs, or UI labels.
---

# Domain Model

## Use This Skill When

- adding fields, statuses, or transitions
- editing task, job, tenant, scheduler, or publish behavior
- naming backend APIs, schema fields, or UI labels
- deciding whether a concept already exists in the model

## Canonical Terms

- `Task`: the parent workflow for one Instagram-post flow
- `Job`: a child generation unit under a task, not a generic queue job
- `Tenant`: the account/project boundary that owns tasks and schedule rules
- `ScheduleRule`: a per-tenant scheduler definition
- `ScheduleLog`: one execution record for a rule and timeslot
- `publish`: delivery of a task's generated assets to Instagram

Prefer these canonical names over introducing synonyms. In user-facing copy, `project` may appear, but code should stay tenant-centric.

## State Models To Respect

Task status progression usually moves through:

- `draft`
- `pending_approval`
- `processing`
- `pending_confirmation`
- `ready`
- `publishing`
- `published` or `failed`

Job status progression usually moves through:

- `new`
- `ready`
- `processing`
- `processed` or `error`

Schedule log statuses are:

- `scheduled`
- `processing`
- `no_task`
- `error`
- `done`

## Important Invariants

- A task is the publishable unit; a job is a child generation step.
- Runtime image generation is driven by `job.generator`, not task-level `image_generator` fields.
- The canonical publish caption is `task.post.caption`.
- Publish depends on image jobs that produce usable image paths or `public_url` values.
- Tenant-specific integration config currently lives in `Tenant.env` and must be treated as tenant-scoped data.
- The scheduler operates from `ScheduleRule.times`, not from `Task.scheduled_for`.

## Ambiguities To Avoid Deepening

- Do not introduce new uses of legacy compatibility fields such as `caption_text`, `quote_text`, or `image_generator` unless the task explicitly requires backward compatibility.
- Be careful with overloaded words such as `ready`, `processing`, `publish`, `result`, and `logs`; always anchor them to the entity being discussed.
- Do not create new code paths that blur the distinction between `Task` workflow state and `Job` processing state.

## Practical Guidance

- If a new concept fits inside existing `Task`, `Job`, or `Tenant` meaning, extend that model instead of inventing a parallel abstraction.
- When editing schemas or UI labels, keep terminology consistent with the glossary and existing model names.
- When adding transitions, check both entity status models and downstream effects on worker, publish, and scheduler flows.

## Use The Docs As Backing Context

- `docs/glossary.md`
- `docs/runtime-flows.md`
- `docs/architecture.md`
