# Architecture

This document proposes a target architecture for the current codebase as it exists today. It is grounded in `docs/project-audit.md`, `docs/runtime-flows.md`, and `docs/glossary.md`, and it intentionally favors incremental migration over a rewrite.

## Current Reality

- The system is a multi-tenant application with three real runtime entrypoints: the FastAPI API in `app/main.py`, the Vue admin SPA in `frontend/src/main.js`, and the tenant-scoped worker in `app/worker.py`.
- The main business workflow is database-backed: a `Task` owns one or more `Job` records, jobs generate image assets, outputs are optionally uploaded to a public host, and the task is then published to Instagram.
- MySQL is the system of record, but persistence responsibilities are spread across route handlers, repository helpers, processors, publishers, scheduler code, and worker code rather than one application-service boundary.
- The worker is a polling loop, not a queue consumer. It discovers `READY` jobs in MySQL and also runs scheduler checks in the same process.
- `app/api/routes.py` is the largest mixed-concern module. It handles HTTP concerns, data loading, workflow transitions, and some response shaping directly.
- The job processor and publish paths are also mixed-concern modules. They combine integration calls, filesystem work, status transitions, and database writes in a single flow.
- Tenant scoping is explicit: the Vue app sends `X-Tenant-Id` on tenant-scoped API calls; FastAPI dependencies load that tenant into `app/context.py`. The worker calls `init_context_by_tenant()` / `reset_tenant_context()` around each tenant as it cycles all active tenants (optional `WORKER_TENANT_ID` / `--tenant-id` limits to one). Listing/creating tenants and auth bootstrap omit the header via dedicated routes in `app/api/routes.py`.
- Tenant configuration is currently stored in database `Tenant.env` JSON and may also be copied into `os.environ`, which makes configuration resolution powerful but hard to reason about.
- The frontend already has one useful boundary: `frontend/src/services/api.js` is the single client integration layer for backend HTTP calls.

## Intended Direction

The target architecture is not a new platform. It is the current application shape with clearer boundaries:

- Keep the existing entrypoints: API, worker, frontend, and supporting scripts.
- Keep MySQL, SQLModel, the polling worker, local output files, and the current external integrations.
- Move workflow orchestration toward explicit application services so API routes, worker loops, scheduler actions, and scripts call the same use-case entrypoints.
- Narrow repository responsibility to persistence and simple record lifecycle operations.
- Narrow integration modules to external I/O only: OpenAI, FTP, Instagram, Discord, filesystem.
- Make tenant configuration resolution more explicit over time so new code depends on passed-in config/context rather than global environment mutation.
- Split large mixed modules incrementally when they are touched, starting with the most reused flows rather than by folder purity alone.

In short:

- Current state: routes, processors, publishers, and scheduler code all own pieces of workflow logic.
- Target state: workflow logic lives in one application layer, while HTTP, worker, scheduler, and scripts become delivery adapters into that layer.

## Major Layers

### 1. Delivery Layer

Current state:

- `app/api/`
- `app/main.py`
- `app/worker.py`
- `scripts/`

Target state:

- HTTP routes, worker entrypoints, scheduler triggers, and CLI scripts are delivery adapters.
- They accept input, load auth/context, call application services, and return results.
- They should not become the primary place where task/job workflow rules are decided.

### 2. Application Layer

Current state:

- Partly present but scattered across `app/services/task_repo.py`, `app/services/jobs/processor.py`, `app/services/tasks/publisher.py`, `app/services/scheduler/worker.py`, and pieces of `app/api/routes.py`.

Target state:

- A clearer orchestration layer owns use-cases such as:
  - task transitions
  - job processing
  - publish execution
  - scheduler tick execution
  - tenant-scoped config resolution for a workflow
- This layer is called by API routes, worker code, scheduler actions, and scripts.

### 3. Domain Layer

Current state:

- Mainly represented by SQLModel entities, enums/status values, task templates, and the workflow meanings documented in `docs/glossary.md`.

Target state:

- Core concepts remain the same: `Task`, `Job`, `Tenant`, `ScheduleRule`, `ScheduleLog`, and their statuses.
- Workflow invariants become more explicit and less duplicated across routes and service modules.
- Domain code stays free of direct HTTP calls and should avoid hidden config lookup where possible.

### 4. Infrastructure Layer

Current state:

- Database engine/session usage in many places.
- Integration code under `app/services/jobs/`, `app/services/tasks/`, `app/services/ftpupload.py`, `app/services/notifier.py`, and local filesystem usage under `output/`.

Target state:

- Infrastructure modules handle external systems and persistence mechanics:
  - MySQL sessions and repositories
  - OpenAI image generation
  - FTP upload/public URL hosting
  - Instagram Graph API delivery
  - Discord webhook notifications
  - local file storage
- These modules do not decide broader workflow transitions unless that behavior is intentionally wrapped by an application service.

### 5. Frontend Layer

Current state:

- Vue views/components plus `frontend/src/services/api.js`, `frontend/src/authStore.js`, and localStorage-based session and tenant selection.

Target state:

- The frontend continues to speak only to the backend HTTP API.
- `frontend/src/services/api.js` remains the single integration boundary for backend calls.
- Backend refactors should preserve existing API behavior unless a deliberate API change is being made. Tenant-scoped routes now require the `X-Tenant-Id` header and no longer accept redundant `tenant_id` query or body fields for task list/create or schedule-rule create.

## Responsibility of Each Layer

| Layer | Primary responsibility | Should not own long-term |
|---|---|---|
| Delivery | Parse requests/commands, authenticate, initialize context, call use-cases, shape responses | Core workflow rules, direct cross-system orchestration |
| Application | Coordinate workflows and transaction boundaries across domain, persistence, and integrations | Low-level HTTP client details or framework-specific response code |
| Domain | Define entities, statuses, invariants, and shared business meaning | External API calls, filesystem access, environment mutation |
| Infrastructure | Persist data, call external services, store files, implement adapter logic | Deciding overall business flow across multiple steps |
| Frontend | Present UI state, invoke backend APIs, store client session and selected tenant | Re-implementing backend workflow rules |

## Allowed Dependency Direction

Target dependency direction:

- `frontend` -> backend HTTP API
- delivery -> application
- application -> domain
- application -> infrastructure
- infrastructure -> domain data structures only when needed

Guidance:

- Delivery code may depend on schemas, auth helpers, and application services.
- Application services may depend on repositories, integration adapters, and domain concepts.
- Infrastructure may depend on shared models/types needed to persist or serialize data.
- Domain logic should not depend on FastAPI, Axios, Requests, FTP, Instagram, or environment mutation.

Avoid for new code:

- route handlers directly coordinating multi-step workflows when a reusable application service exists
- low-level integration clients opening their own extra workflow boundaries unless they are strictly adapter-local
- new features depending on implicit tenant config injected into global `os.environ`
- frontend code depending on backend implementation details beyond HTTP contracts

## Module Boundaries

The target boundaries below are intended to fit the current repository shape with minimal churn.

### API Surface

Current state:

- `app/api/routes.py` is monolithic and mixes transport, persistence, and workflow decisions.

Target state:

- Keep the current URLs and request/response contracts where possible.
- Move route logic toward thin handlers that call application services.
- Split large route groups gradually by feature or resource when touched, not as a standalone rewrite.
- Recent example of the intended direction: the AI draft preview/confirm flow keeps new HTTP routes in `app/api/routes.py`, but puts tenant-aware draft generation and atomic draft confirmation behind `app/services/ai_task_draft_service.py` instead of embedding that workflow directly in the route layer. Preview LLM work is scheduled from the route via FastAPI `BackgroundTasks` and implemented in `app/services/ai_draft_preview_runner.py` (commit-sized transcript rows for polling). Persisted AI draft sessions (resume after refresh, structured errors on failed confirm) use `app/services/ai_draft_session_repo.py`, scoped by authenticated user and tenant; transcript rows live in `ai_draft_communication_events`. Open draft cap enforcement is reject-on-create (manual discard required), not auto-delete trimming.

### Repositories

Current state:

- `task_repo.py`, `tenant_repo.py`, `user_repo.py`, `schedule_rule_repo.py`, and `ai_draft_session_repo.py` already provide useful seams, but some workflow logic is mixed in and many flows bypass them.

Target state:

- Repositories own persistence operations and simple lifecycle helpers.
- Application services own multi-step orchestration and cross-entity coordination.

### Job Processing

Current state:

- `app/services/jobs/processor.py` orchestrates status updates, generator dispatch, file writes, upload behavior, and task advancement.

Target state:

- Generator-specific modules remain infrastructure adapters for image generation.
- The reusable workflow entrypoint for "process this job" becomes application-owned, even if it still delegates into `processor.py` during transition.
- API and worker both call the same workflow entrypoint.

### Publishing

Current state:

- `app/services/tasks/publisher.py` and `publisher_instagram.py` together own DB reloads, status changes, media assembly, tenant config lookup, and Instagram HTTP behavior.

Target state:

- Instagram-specific HTTP behavior remains isolated behind an integration adapter.
- The decision to move task status to `PUBLISHING`, `PUBLISHED`, or `FAILED` belongs to a reusable publish workflow service.
- Manual publish, scheduled publish, and CLI publish all share the same workflow entrypoint.

### Scheduler

Current state:

- Scheduler logic is readable but still combines due-rule selection, task picking, action dispatch, persistence, and notification.

Target state:

- Scheduler remains in-process inside the worker for now.
- It becomes an application orchestration boundary that calls shared task/job/publish workflows rather than embedding separate action behavior.
- Notification emission stays adapter-like and does not define scheduler business meaning.

### Tenant Context And Config

Current state:

- `app/context.py` both stores current tenant context and mutates `os.environ` from tenant config.

Target state:

- Keep tenant context for worker/scheduler scoping in the short term.
- Stop expanding the global environment mutation pattern.
- Introduce explicit config resolution objects or helper functions for new or touched flows.

## External Integration Boundaries

Each external system should have one clear adapter boundary and one clear caller boundary.

### MySQL

- Current state: sessions are opened from many locations.
- Target state: application services define transaction boundaries; repositories and persistence helpers perform DB work underneath them.
- Recent example: AI draft confirmation uses an application-owned workflow plus `task_repo.create_task_bundle_with_jobs()` so an entire reviewed bundle (many tasks and their jobs) is created in a single transaction.

### OpenAI Images API

- Current state: generator modules both call OpenAI and participate in processing flow expectations.
- Target state: generator modules return generation results; broader job/task transitions are handled by the processing workflow.

### FTP / Public Hosting

- Current state: upload is best-effort and its contract is implicit through `Job.result.public_url`.
- Target state: upload remains optional, but the contract becomes explicit: processing produces either a usable public URL or a clearly understood local-only result.

### Instagram Graph API

- Current state: Instagram integration is mixed with task/job loading and publish orchestration.
- Target state: the Instagram client layer only knows how to publish media and return integration results; application code decides what that means for task state.

### Discord Webhook

- Current state: used only from scheduler result notification flow.
- Target state: remains an outbound notification adapter, not a domain coordinator.

### Local Filesystem And `/output`

- Current state: generated files are stored under `output/` and served via `/output`.
- Target state: keep this storage model unless there is a separate infrastructure change. Treat it as an internal artifact boundary with a stable result contract.

## Known Deviations / Legacy Areas

- `app/api/routes.py` is still a monolithic route module and will remain so until incrementally split.
- Direct `Session(engine)` usage exists across routes, worker, scheduler, processors, and publishers.
- `create_tables()` at runtime is bootstrap behavior, not a migration system.
- Tenant-scoped HTTP handlers derive the active tenant from `X-Tenant-Id` and enforce task/schedule access against `get_tenant().id`; worker/scheduler paths continue to use `app/context.py` without HTTP.
- `Tenant.env` is both persisted config and runtime config source, and `app/context.py` may copy it into `os.environ`.
- The worker and scheduler share one polling loop, so slow work can delay scheduled actions.
- The same job processor can be triggered through HTTP and background execution.
- Some documented or modeled concepts appear partially orphaned or legacy, such as scheduler action vocabulary beyond the currently implemented actions and compatibility task fields like `caption_text` or `image_generator`.

These deviations are not reasons to stop. They define where migration should be careful and where new code should avoid deepening old patterns.

## Migration Principles

- Prefer extraction over replacement. Move reusable workflow logic behind stable entrypoints before reorganizing files aggressively.
- Keep existing runtime entrypoints: FastAPI API, Vue frontend, worker, scheduler-in-worker, and support scripts.
- Migrate one workflow at a time. The best early candidates are publish and job processing because they are reused by API, worker, scheduler, and scripts.
- Do not introduce a queue, event bus, or service split unless there is a concrete operational need. The target architecture must remain compatible with the current polling worker model.
- For new or edited code, avoid adding more business logic directly into route handlers.
- For new or edited code, avoid adding more hidden dependencies on tenant config through `os.environ`.
- Preserve HTTP contracts unless the user-facing API is intentionally being changed.
- Make implicit contracts explicit when touching them, especially:
  - `Job.result` shape
  - `Task.result.logs` shape
  - `public_url` versus local image path behavior
  - tenant credential resolution order
- Introduce clearer module boundaries in the direction of current code, not against it. Favor small refactors that reduce duplication or mixed concerns in active paths.
- Treat database migration tooling as a separate infrastructure improvement, not a prerequisite for the architectural cleanup above.
