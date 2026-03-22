---
name: architecture
description: Applies the mvPipeline target architecture when adding or refactoring backend or frontend code. Use when working on routes, worker flows, scheduler actions, publishing, job processing, or module boundaries.
---

# Architecture

## Use This Skill When

- adding or refactoring backend flows
- splitting responsibilities between routes, services, repos, and integrations
- touching worker, scheduler, publish, or processing paths
- deciding where new logic belongs

## Default Mental Model

- Delivery: `app/api/`, `app/main.py`, `app/worker.py`, scheduler actions, `scripts/`
- Application: shared workflow orchestration for task transitions, job processing, publish, scheduler tick
- Domain: `Task`, `Job`, `Tenant`, `ScheduleRule`, `ScheduleLog`, statuses, template meaning
- Infrastructure: DB sessions/repos, OpenAI, FTP, Instagram, Discord, filesystem
- Frontend: Vue views/stores calling backend only through HTTP

Dependency direction:

- frontend -> HTTP API
- delivery -> application
- application -> domain
- application -> infrastructure

## Request And Workflow Flow

Use this default path for new or changed behavior:

1. frontend or script triggers a backend action
2. delivery layer authenticates, validates, and loads context
3. shared application service runs the workflow
4. repositories and integration adapters do persistence or external I/O
5. delivery layer returns the result without re-owning the workflow

## Operational Rules

- Treat routes, worker entrypoints, scheduler actions, and scripts as delivery adapters.
- New multi-step workflow logic should not start in `app/api/routes.py`.
- If the same behavior is needed from API, worker, and scheduler, make or reuse one shared backend workflow entrypoint.
- Do not add new direct integration orchestration in route handlers.
- When touching mixed modules, improve boundaries locally instead of rewriting whole subsystems.
- Preserve the current runtime shape unless the task explicitly changes it: FastAPI API, Vue frontend, MySQL, per-tenant worker, scheduler-in-worker, local output artifacts.

## Watch For Existing Hotspots

- `app/api/routes.py` is the main mixed-concern backend module.
- `app/services/jobs/processor.py` mixes workflow, persistence, file I/O, and integrations.
- `app/services/tasks/publisher.py` and `publisher_instagram.py` mix orchestration and adapter logic.
- `app/context.py` holds tenant context and currently leaks config concerns into global environment state.

## Use The Docs As Backing Context

- `docs/architecture.md`
- `docs/project-audit.md`
- `docs/runtime-flows.md`
