---
name: hotswap-service-check
description: Checks and validates the mvPipeline hot-swap systemd services for the API and frontend. Use when testing backend or frontend changes, verifying the live dev runtime, restarting `mvpipeline-api.service` or `mvpipeline-frontend-dev.service`, or when the user mentions hot-swap services, systemd, Vite service health, or deployment verification.
---

# Hotswap Service Check

## Use This Skill When

- testing backend changes against the live dev environment
- testing frontend changes against the live dev environment
- verifying or restarting `mvpipeline-api.service`
- verifying or restarting `mvpipeline-frontend-dev.service`
- checking whether a runtime issue is caused by stale services rather than code

## Runtime Shape

- Backend service: `mvpipeline-api.service`
- Frontend service: `mvpipeline-frontend-dev.service`
- Frontend dev runtime is persistent Vite behind Nginx/TLS, as documented in `docs/deployment-hetzner-flow-mentoverse.md`
- Avoid starting duplicate `uvicorn` or Vite dev servers when this hot-swap setup is the intended test environment

## Default Workflow

1. Decide scope first:
   - backend-only change -> inspect/restart `mvpipeline-api.service`
   - frontend-only change -> inspect/restart `mvpipeline-frontend-dev.service`
   - shared contract, env, dependency, or routing change -> inspect/restart both
2. Check service status before restarting anything.
3. Read recent logs when a service is unhealthy or a restart does not explain the issue.
4. Restart only the services affected by the change.
5. Verify the result with the narrowest useful check:
   - service status/logs for process health
   - browser verification for frontend behavior
   - API request or app flow verification for backend behavior

## Suggested Command Set

Use the documented systemd workflow from `docs/deployment-hetzner-flow-mentoverse.md`.

```bash
sudo systemctl status mvpipeline-api.service --no-pager
sudo systemctl status mvpipeline-frontend-dev.service --no-pager
sudo journalctl -u mvpipeline-api.service -n 100 --no-pager
sudo journalctl -u mvpipeline-frontend-dev.service -n 100 --no-pager
sudo systemctl restart mvpipeline-api.service
sudo systemctl restart mvpipeline-frontend-dev.service
```

## Verification Guidance

- Backend changes:
  - confirm `mvpipeline-api.service` is active after restart
  - inspect logs for startup/import/config errors
  - verify the changed API behavior with the narrowest request or app flow available
- Frontend changes:
  - confirm `mvpipeline-frontend-dev.service` is active after restart
  - inspect logs for Vite build/startup errors
  - verify the changed UI in the browser, including HMR-sensitive behavior when relevant
- Full-stack changes:
  - restart backend first, then frontend if both changed
  - verify both services before testing the user flow

## Planning And Brainstorming Use

- When planning or brainstorming validation, assume this hot-swap service topology is the default runtime.
- If a proposed change touches frontend runtime config, backend runtime config, package installation, or system wiring, call out the relevant service restart and verification steps in the plan.
- If no runtime verification is needed yet, use this skill as context only; do not restart services unnecessarily.

## Escalation Notes

- If service status is healthy but behavior is wrong, continue with app-level or browser-level verification instead of repeatedly restarting.
- If the issue appears to involve Nginx, TLS, or websocket/HMR proxying, go back to `docs/deployment-hetzner-flow-mentoverse.md` before changing the app runtime.
