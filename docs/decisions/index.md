# Architectural Decision Records

This index proposes the most important architectural decisions to capture as ADRs based on `docs/project-audit.md`, `docs/runtime-flows.md`, `docs/glossary.md`, and `docs/architecture.md`.

1. ADR-001: Use shared application services for workflow orchestration
   Why it matters: the same task, job, publish, and scheduler workflows are currently spread across routes, worker code, repositories, and publisher/processor modules. Capturing this decision gives the team a stable direction for incremental refactoring without changing the product shape.
   Current evidence in the codebase: `app/api/routes.py` mixes transport and workflow logic; `app/services/jobs/processor.py` is called from both HTTP and the worker; publish is shared across API, scheduler, and `scripts/publish_task.py`; `docs/architecture.md` recommends delivery -> application -> domain/infrastructure boundaries.
   Recommended priority: high

2. ADR-002: Keep the per-tenant database-polling worker model for now
   Why it matters: the current system depends on one worker per tenant, database polling, and scheduler execution in the same loop. Capturing this prevents an accidental drift toward a queue-based rewrite that the current system does not need yet.
   Current evidence in the codebase: `app/worker.py` polls MySQL for `READY` jobs, initializes tenant context, and runs scheduler checks; `docs/runtime-flows.md` explicitly notes there is no queue and that scheduler and job processing share one loop; `docs/architecture.md` says the target architecture must remain compatible with the polling worker model.
   Recommended priority: high

3. ADR-003: Resolve tenant-scoped integration config explicitly instead of mutating global environment state
   Why it matters: tenant-specific Instagram and public URL config is currently partly stored in `Tenant.env` and may be copied into `os.environ`, creating implicit cross-flow coupling. Capturing this decision establishes a safer migration path for tenant-aware operations.
   Current evidence in the codebase: `app/context.py` mutates `os.environ`; `publisher_instagram.py` reads tenant env and process env; `docs/project-audit.md` flags global mutable tenant config as suspicious; `docs/architecture.md` recommends explicit config resolution for new or touched flows.
   Recommended priority: high

4. ADR-004: Define application-owned transaction boundaries and reduce direct session usage from edge layers
   Why it matters: persistence is currently opened from routes, worker code, scheduler code, processors, publishers, and repositories. An ADR would clarify where multi-step workflows should own transactions and where repositories should stay narrow.
   Current evidence in the codebase: `docs/project-audit.md` calls out direct DB access from many places; `docs/runtime-flows.md` shows mixed repository and direct `Session(engine)` usage; `docs/architecture.md` places transaction boundaries in the application layer.
   Recommended priority: high

5. ADR-005: Introduce database schema migrations instead of relying on runtime `create_all()`
   Why it matters: runtime schema creation is acceptable for early development, but it is a weak long-term production contract. Capturing this decision helps separate architecture cleanup from schema evolution discipline.
   Current evidence in the codebase: `app/main.py` and `app/worker.py` call `create_tables()`; `docs/project-audit.md` and `docs/runtime-flows.md` both note the absence of a migration layer; `docs/architecture.md` names migration tooling as a separate infrastructure improvement.
   Recommended priority: medium

6. ADR-006: Keep external integrations behind adapter-style module boundaries
   Why it matters: OpenAI, FTP, Instagram, Discord, filesystem storage, and MySQL are all currently mixed into workflow code. An ADR would make it clear that integration modules should handle external I/O, while workflow meaning stays higher up.
   Current evidence in the codebase: processors and publishers currently combine HTTP calls, filesystem work, status changes, and DB writes; `docs/architecture.md` defines separate external integration boundaries; `docs/project-audit.md` flags mixed concerns in processing and publishing.
   Recommended priority: medium

7. ADR-007: Preserve the frontend HTTP contract while refactoring backend internals
   Why it matters: the Vue app already has a useful boundary in `frontend/src/services/api.js`. Capturing this decision protects the current UI while backend modules are incrementally reorganized.
   Current evidence in the codebase: `frontend/src/services/api.js` is the central client boundary; `docs/runtime-flows.md` shows the frontend consistently using that service layer; `docs/architecture.md` recommends preserving HTTP contracts unless intentionally changed.
   Recommended priority: medium

8. ADR-008: Treat generated files and public URLs as a formal artifact contract
   Why it matters: publishing depends on `Job.result`, local output files, optional FTP upload, and public URL fallback behavior. This is an implicit contract today and a common source of downstream coupling.
   Current evidence in the codebase: job processors write `output/{task_id}/{job_id}.jpeg`, may upload via FTP, and store `public_url` in `Job.result`; `publisher_instagram.py` reconstructs publishable URLs from result data; `docs/runtime-flows.md` and `docs/architecture.md` both call out this implicit artifact boundary.
   Recommended priority: medium
