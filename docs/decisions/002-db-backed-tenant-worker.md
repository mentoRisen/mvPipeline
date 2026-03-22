# ADR-002: Keep The Per-Tenant Database-Polling Worker Model For Now

## Status

Proposed

## Context

The current background execution model is simple and already wired into the product:

- `app/worker.py` runs one worker per tenant
- the worker initializes tenant context and polls MySQL for one `READY` job whose parent task is in `PROCESSING`
- the same worker loop also performs scheduler checks and dispatches scheduled actions
- there is no queue broker, no external message bus, and no separate scheduler service

This model is explicitly reflected in `docs/runtime-flows.md` and preserved in `docs/architecture.md`, which states that the target architecture must remain compatible with the current polling worker model.

The system has architectural issues, but they are mostly boundary issues inside the current shape rather than proof that the execution model itself must be replaced now.

## Decision

Retain the per-tenant, database-polling worker model as the supported execution model for the near-term architecture.

This means:

- continue using MySQL-backed job discovery instead of introducing a queue as part of the current architecture cleanup
- keep scheduler execution inside the worker for now
- refactor workflow boundaries, config handling, and persistence access within the current execution model
- treat a future queue or broker as a separate scaling decision that requires explicit evidence and a new ADR

## Alternatives Considered

### Introduce a queue system now

This could improve isolation and throughput at larger scale, but it would materially change operations, deployment, and failure handling. It would also turn an incremental architecture cleanup into a platform rewrite.

### Split scheduler into a separate service now

This would decouple scheduled work from job polling, but it adds another runtime component without first addressing the more immediate boundary problems inside the existing code.

### Keep the worker model but leave it undocumented

This risks accidental architecture drift, especially if later work assumes background execution must move to a queue before other cleanup can happen.

## Consequences

Positive:

- architecture work stays grounded in the current operating model
- refactors can focus on workflow sharing and module boundaries first
- deployment and local development remain aligned with current scripts and docs

Negative:

- scheduler latency can still be affected by slow job processing in the same loop
- database polling remains less efficient than a dedicated queue at higher scale
- tenant isolation continues to rely on process layout and worker startup discipline

## Migration Notes

- Do not introduce Celery, Redis, RabbitMQ, or a new scheduler process as part of the current cleanup.
- Improve the worker inside the current model first: shared workflow entrypoints, clearer logging, and clearer tenant config resolution.
- If scale or reliability later requires a queue, capture that as a separate decision with operational evidence rather than as an implicit next step.
