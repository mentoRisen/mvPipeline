# Project Audit

This is a reverse-engineering snapshot of the current repository shape. It focuses on structure, entry points, subsystem boundaries, external dependencies, and obvious architectural risks.

## Entry Points

- `app/main.py`
  Purpose: primary FastAPI HTTP API entrypoint. Builds the app, mounts `/output`, registers routers, and creates tables on startup.
- `app/worker.py`
  Purpose: background worker entrypoint. Runs one worker per tenant, processes READY jobs, and periodically runs scheduler logic.
- `frontend/src/main.js`
  Purpose: Vue SPA bootstrap. Creates the router, enforces auth redirects, and mounts the frontend.
- `startup.sh`
  Purpose: local orchestration entrypoint. Starts API, frontend, and optional tenant worker; also handles pid files and logs.
- `scripts/*.py`
  Purpose: operational and ad hoc CLI entrypoints such as `create_user.py`, `publish_task.py`, `process_job.py`, and test helpers.

## Major Modules

| Module | Purpose | Main files / folders | Key dependencies | Assessment |
|---|---|---|---|---|
| API layer | HTTP endpoints for auth, tenants, tasks, jobs, templates, and scheduler rules | `app/api/routes.py`, `app/api/auth_routes.py`, `app/api/schemas.py` | FastAPI, SQLModel, SQLAlchemy exceptions, auth helpers | Mixed |
| Data models and persistence | SQLModel entities and engine/bootstrap logic | `app/models/`, `app/db/engine.py` | SQLModel, SQLAlchemy, MySQL via `pymysql` | Mixed |
| Repositories and auth services | CRUD/state-transition helpers for tasks, tenants, users, schedule rules, plus JWT/password logic | `app/services/task_repo.py`, `tenant_repo.py`, `user_repo.py`, `schedule_rule_repo.py`, `auth.py` | SQLModel sessions, `python-jose`, `passlib[bcrypt]` | Mostly clean |
| Job processing and image generation | Processes image jobs, calls OpenAI image APIs, uploads outputs, advances task state | `app/services/jobs/`, `app/services/ftpupload.py` | Requests, OpenAI HTTP API, FTP, SQLModel | Mixed |
| Publishing and social delivery | Publishes processed assets to Instagram and records publish results | `app/services/tasks/publisher.py`, `app/services/tasks/publisher_instagram.py` | Instagram Graph API, Requests, SQLModel | Mixed |
| Scheduler and notifications | Resolves due rules for a tenant, picks tasks, runs actions, emits Discord notifications | `app/services/scheduler/`, `app/services/notifier.py`, `app/models/schedule_log.py` | SQLModel, `zoneinfo`, Requests, tenant context | Mixed |
| Tenant context and config | Global/runtime configuration and tenant-specific environment overrides | `app/config.py`, `app/context.py` | `os`, `dotenv`, contextvars | Suspicious |
| Frontend admin SPA | Authenticated UI for tasks, tenants, scheduler, and task detail flows | `frontend/src/`, especially `main.js`, `App.vue`, `views/`, `components/`, `services/api.js` | Vue 3, Vue Router, Axios, localStorage | Mixed |
| Scripts and local ops | Bootstrap, publishing, worker/process helpers, and lightweight tests | `scripts/`, `startup.sh` | Python CLI, Bash, app service modules | Mixed |

### Module Notes

#### API layer

- `app/api/routes.py` is the main backend surface and appears to contain most non-auth endpoints in one file.
- It mixes HTTP concerns with some business logic, direct session work, template shaping, and status orchestration.
- `app/api/auth_routes.py` is comparatively small and focused.

#### Data models and persistence

- `app/models/` is cleanly separated by entity.
- `app/db/engine.py` is simple, but schema management is just `SQLModel.metadata.create_all(engine)`, with no visible migration system.

#### Repositories and auth services

- Repo files generally encapsulate simple CRUD and status transitions well.
- `task_repo.py` also includes workflow/state-transition logic, so it is not a pure data-access layer.
- Auth is small and understandable, but security posture depends heavily on environment configuration.

#### Job processing and image generation

- This appears to be the canonical image-generation path now.
- OpenAI API calling, file writing, FTP upload, DB updates, and task-state advancement are still tightly coupled.

#### Publishing and social delivery

- Instagram publishing logic is reasonably isolated, but it still opens DB sessions and reconstructs data inside the publisher path.
- `publisher_instagram.py` contains both application-level orchestration and low-level HTTP request logic for carousel publishing.

#### Scheduler and notifications

- The scheduler is conceptually separated and readable.
- It still performs direct DB lookups, task picking, action dispatch, logging, and notification emission in one flow.
- Tenant context is assumed to be initialized globally before use.

#### Tenant context and config

- `app/context.py` stores tenant in a context variable, which is fine.
- It also mutates `os.environ` from tenant JSON config, which is powerful but risky and hard to reason about.
- `app/config.py` contains committed defaults for DB and auth secrets.

#### Frontend admin SPA

- The frontend structure is straightforward: router bootstrap, simple stores, views, and a single API client.
- `frontend/src/services/api.js` is a central integration layer and is a good boundary.
- The app appears functional but small; state management is lightweight and tightly coupled to localStorage and route guards.

#### Scripts and local ops

- `scripts/` mixes real operational commands with ad hoc validation scripts like `test_scheduler.py`, `test_notifier.py`, and `test_sentry.py`.
- `startup.sh` does more than process startup: dependency install, pid/log management, and cleanup.

## External Integrations

- MySQL
  Main persistence layer via `sqlmodel` and `pymysql`.
- OpenAI Images API
  Used from `app/services/jobs/processor_dalle.py`, `processor_gptimage15.py`, and mirrored generator classes.
- Instagram Graph API
  Used by `app/services/tasks/publisher_instagram.py`.
- FTP hosting
  Used by `app/services/ftpupload.py` to push generated images to a public location before Instagram publish.
- Discord webhook
  Used by `app/services/notifier.py` for scheduler and error notifications.
- Sentry
  Optional observability via `app/sentry_setup.py`.
- Uvicorn / Vite
  App runtime and frontend dev-server infrastructure.
- Local filesystem
  Heavy dependency on `output/`, `logs/`, `templates/`, and `fonts/`.

## Architectural Smells

- Giant file: `app/api/routes.py` is a monolithic endpoint module and the clearest large-file hotspot.
- Mixed concerns in the API layer: route handlers perform DB access, pagination counting, template shaping, job CRUD, and workflow/state transitions instead of delegating consistently.
- Mixed concerns in processing/publishing: job processors and publishers combine external HTTP calls, DB writes, state transitions, file I/O, and integration fallback behavior.
- Business logic in edge layers: route handlers decide workflow validity and transition semantics; publishers also update task statuses directly.
- Direct DB access from many places: sessions are opened in routes, repos, worker, scheduler, publishers, and processors rather than through one clear application-service boundary.
- Global mutable tenant config: `app/context.py` copies tenant `env` values into `os.environ`, which can leak configuration across flows and makes dependency boundaries implicit.
- Infra config in code: `app/config.py` hardcodes a MySQL URL and a default auth secret fallback.
- No visible migration layer: schema creation uses `create_all()` at runtime, which is convenient early on but fragile for long-lived production schema evolution.
- Local/dev orchestration doing too much: `startup.sh` owns process lifecycle, dependency install, and cleanup, which is convenient but not a clean deployment boundary.

## Questions / Unknowns

- Are tenant `env` JSON blobs intended as the long-term config model, or only an MVP shortcut?
- Is there any deployment setup outside this repo for process supervision, secrets, public file hosting, and MySQL provisioning?
- Are the ad hoc scripts under `scripts/` supported operational tools, or mostly manual developer utilities?
- Is there an intended application-service layer that should sit between routes/workers and repos/integrations, but has not been extracted yet?
