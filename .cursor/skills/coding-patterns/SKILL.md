---
name: coding-patterns
description: Applies mvPipeline implementation patterns for adding features safely. Use when changing validation, error handling, config resolution, backend workflows, or deciding where business logic belongs.
---

# Coding Patterns

## Use This Skill When

- adding backend features or refactoring existing flows
- deciding where validation or business rules should live
- changing config or integration handling
- touching errors, logging, tests, or docs for workflow code

## Where Logic Belongs

- Route handlers: auth, request validation, response shaping, calling shared services
- Shared backend services: multi-step workflows, status transitions, orchestration across repos and integrations
- Repositories: persistence operations and narrow record lifecycle helpers
- Integration adapters: OpenAI, FTP, Instagram, Discord, filesystem I/O

When modifying existing code, move toward this split. Do not introduce additional multi-step business logic in route handlers if a shared service can own it.

## Validation Pattern

- Validate request shape and auth at the delivery layer.
- Validate workflow rules in shared backend services so API, worker, scheduler, and scripts can reuse them.
- Validate tenant-sensitive operations on the server side; do not trust frontend-selected tenant state alone.

## Error And Logging Pattern

- Fail with explicit, actionable errors at the seam that owns the decision.
- Do not swallow integration or persistence errors silently.
- Do not log tokens, passwords, or raw credential payloads.
- When changing a risky path, prefer small changes plus explicit verification notes over broad speculative cleanup.

## Config Pattern

- Prefer explicit config inputs or resolved config objects for tenant-aware workflows.
- Do not add new deep reads from global environment state when config can be passed in.
- Do not introduce additional code that copies tenant config into global `os.environ`.
- During transition, document fallback order when code must support both tenant env and process env.

## Feature Addition Checklist

1. Reuse existing domain terms and statuses.
2. Put the workflow in a shared backend service if more than one entrypoint can trigger it.
3. Keep integration calls behind service or adapter modules.
4. Add the narrowest practical verification.
5. Update docs when runtime or architecture behavior changes.

## Use The Docs As Backing Context

- `docs/architecture.md`
- `docs/decisions/001-shared-application-workflows.md`
- `docs/decisions/003-explicit-tenant-config-resolution.md`
- `.cursor/rules/02-architecture-constraints.mdc`
