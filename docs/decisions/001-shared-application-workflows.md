# ADR-001: Use Shared Application Services For Workflow Orchestration

## Status

Proposed

## Context

The current system has multiple delivery paths into the same business workflows:

- HTTP routes in `app/api/routes.py`
- the tenant worker in `app/worker.py`
- scheduler actions under `app/services/scheduler/`
- operational scripts such as `scripts/publish_task.py`

The same workflow rules are currently split across route handlers, repositories, processors, publishers, and scheduler code. Examples include:

- job processing is triggered both by HTTP and the worker through `app/services/jobs/processor.py`
- publish execution is triggered by manual API publish, scheduler publish, and CLI publish
- task state changes are partly enforced in routes, partly in `task_repo.py`, and partly in publish/processor paths

This makes workflow behavior harder to reason about and increases the chance that one entrypoint will drift from the others.

`docs/architecture.md` defines the intended direction as delivery -> application -> domain/infrastructure, with workflow logic moved toward a shared application layer instead of remaining in edge modules.

## Decision

Introduce and prefer shared application services as the canonical orchestration boundary for core workflows.

This means:

- delivery code such as HTTP routes, worker entrypoints, scheduler actions, and scripts should call the same workflow entrypoints
- multi-step flows such as task transitions, job processing, publish execution, and scheduler tick execution should be coordinated in one application-owned place
- low-level modules such as repositories and integration adapters should support those workflows rather than define the overall business flow themselves

This is an incremental decision, not a folder rewrite. Existing modules may continue to host the implementation during migration, but new or touched workflow code should move toward shared application entrypoints.

## Alternatives Considered

### Keep the current split responsibilities

This avoids short-term refactoring, but it preserves the current duplication and makes behavior drift more likely between API, worker, scheduler, and script entrypoints.

### Rewrite the backend into a new service layout immediately

This would create a cleaner conceptual structure faster, but it does not fit the project's current size, operating model, or incremental migration goals.

### Push more workflow logic into repositories

Repositories are useful persistence seams, but using them as the main orchestration layer would keep transport, transaction, and external integration concerns mixed into persistence code.

## Consequences

Positive:

- API, worker, scheduler, and scripts can share the same workflow behavior
- business rules become easier to test and reason about
- route handlers can get thinner over time without changing external behavior
- integration modules can become narrower and easier to replace or harden

Negative:

- there will be a transition period where old and new orchestration paths coexist
- some existing service modules may need to be split conceptually before they are split physically
- transaction ownership will need to be clarified as shared workflow entrypoints emerge

## Migration Notes

- Start with the highest-reuse workflows: publish execution and job processing.
- Introduce stable workflow entrypoints first, even if they initially delegate to existing modules.
- Update API routes, scheduler actions, worker code, and scripts to call those entrypoints before doing larger file reorganizations.
- Avoid adding new business rules directly to `app/api/routes.py` when a shared workflow entrypoint can own them.
