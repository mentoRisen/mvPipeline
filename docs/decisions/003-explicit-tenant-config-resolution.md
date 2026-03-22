# ADR-003: Resolve Tenant-Scoped Integration Config Explicitly

## Status

Proposed

## Context

Tenant-specific integration behavior is central to the current product:

- tenants store integration-related values in `Tenant.env`
- publish flows depend on values such as `INSTAGRAM_ACCESS_TOKEN`, `INSTAGRAM_ACCOUNT_ID`, and `PUBLIC_URL`
- worker and scheduler flows rely on tenant context being initialized before execution

Today, `app/context.py` may copy tenant `env` values into `os.environ`. At the same time, some runtime paths also read directly from process environment variables. This creates an implicit configuration model with several problems:

- it is difficult to know which config source is authoritative for a given flow
- tenant configuration may leak conceptually across flows because resolution is global rather than explicit
- integration code becomes harder to test because required config is not always passed in

`docs/project-audit.md` flags global mutable tenant config as suspicious, and `docs/architecture.md` recommends introducing explicit config resolution for new or touched flows.

## Decision

Move toward explicit tenant-scoped config resolution for workflow and integration code, and stop expanding the pattern of mutating global `os.environ` from tenant data.

This means:

- application workflows should resolve the config they need for a given tenant and pass it down explicitly
- integration adapters should prefer passed-in configuration over hidden global lookup
- existing process-level environment variables may still be used as fallback during migration, but the fallback order should be deliberate and documented
- `app/context.py` may continue to hold the current tenant identity for worker and scheduler scoping, but it should not remain the long-term mechanism for implicit integration configuration

## Alternatives Considered

### Keep using `os.environ` mutation as the main tenant config mechanism

This is convenient in the short term, but it preserves hidden coupling and makes tenant-aware behavior harder to reason about and test.

### Move all tenant config out of the database immediately

This could simplify authority boundaries, but it would be a larger product and operations change than the current architecture step requires.

### Remove tenant-specific config support and rely only on process env

This would not match the current multi-tenant behavior and would reduce flexibility for tenant-specific Instagram and hosting configuration.

## Consequences

Positive:

- tenant-aware flows become easier to reason about
- integration adapters get clearer inputs and better testability
- configuration precedence becomes explicit instead of emergent
- the risk of hidden cross-flow coupling is reduced

Negative:

- some existing call paths will need extra plumbing to pass config objects or resolved values
- there may be a transition period where explicit config and environment fallback both coexist
- older helper functions may need small signature changes when touched

## Migration Notes

- Start with the publish flow, since it already resolves a mix of tenant env and process env values.
- Document the temporary precedence rules wherever fallback is still needed.
- Do not expand `os.environ` mutation to new integrations or new workflow code.
- When editing worker, scheduler, or publish code, prefer passing resolved config objects or explicit values instead of reading globals deep in the call stack.
