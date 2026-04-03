# Runtime Flows

This document describes the runtime behavior that is actually wired in the current codebase. It follows the current FastAPI app, Vue frontend, background worker, scheduler, and integration services rather than an idealized architecture.

## Main User Request Flows

### Login And Session Bootstrap

- Trigger: user submits the login form in `frontend/src/views/LoginView.vue`, or the router guard in `frontend/src/main.js` checks whether a stored session is still valid.
- Sequence of layers/components:
  `LoginView.vue` -> `authStore.login()` in `frontend/src/authStore.js` -> `authService.login()` in `frontend/src/services/api.js` -> `POST /api/v1/auth/login` in `app/api/auth_routes.py` -> `auth_service.authenticate_user()` in `app/services/auth.py` -> `user_repo`.
- Persistence touchpoints:
  backend reads `users` from MySQL; frontend stores JWT in `localStorage` as `mv_auth_token` and user snapshot as `mv_auth_user`.
- Integration touchpoints:
  none; JWT issuance and validation are local.
- Notable risks or inconsistencies:
  the router guard calls `authStore.bootstrap()` on every navigation; API `401` responses trigger client-side logout through the Axios interceptor. User admin endpoints exist on the API, but there is no matching UI for user management.

### Tenant Selection And Tenant Management

- Trigger: authenticated app mount in `frontend/src/App.vue`, tenant picker interaction in the header, or navigation to `/tenants`.
- Sequence of layers/components:
  `App.vue` -> `tenantService.getDefaultTenant()` / `tenantService.getTenants()` -> `GET /api/v1/tenants/default` or `GET /api/v1/tenants` in `app/api/routes.py` -> `tenant_repo`.
  Tenant CRUD flow uses `frontend/src/views/TenantsView.vue`, `components/TenantList.vue`, and `components/TenantDetail.vue` -> `tenantService.createTenant/updateTenant/deleteTenant` -> matching tenant routes in `app/api/routes.py`.
- Persistence touchpoints:
  selected tenant is stored client-side in `localStorage` as `mentoverse_current_tenant`; tenant records are stored in MySQL.
- Integration touchpoints:
  none directly; tenant `env` JSON is stored for later Instagram/public URL usage.
- Notable risks or inconsistencies:
  tenant selection remains client-driven, but tenant-scoped API routes require the `X-Tenant-Id` header (see `app/api/tenant_deps.py`). The client sets it from `tenantStore` in `frontend/src/services/api.js` for all calls except a small bootstrap set (login, session refresh, listing/creating tenants). Bootstrap routes live on `bootstrap_router` in `app/api/routes.py`; everything else uses `scoped_router`, which runs `tenant_context_dependency` and loads `app.context`.

### Task List, Detail, Create, Update, And Delete

- Trigger: navigation to `/`, task row selection, task creation modal, JSON task creation modal, task edit form, or delete action.
- Sequence of layers/components:
  `frontend/src/views/TasksView.vue` embeds `TaskList.vue` and `TaskDetail.vue`.
  `TaskList.loadTasks()` -> `taskService.getTasks()` -> `GET /api/v1/tasks` in `app/api/routes.py` -> `task_repo.list_all_tasks()` or `list_tasks_by_status()`.
  `TaskDetail.loadTask()` -> `taskService.getTask()` -> `GET /api/v1/tasks/{id}` -> `task_repo.get_task_by_id()` plus inline `Job` query in `app/api/routes.py`.
  Create flow: `TaskList.vue` -> `taskService.createTask()` -> `POST /api/v1/tasks` -> template hydration in `app/api/routes.py` -> `task_repo.save()`.
  AI create flow: `TaskList.vue` -> `AiTaskDraftModal.vue` -> `taskService.previewAiTaskDraft()` -> `POST /api/v1/tasks/ai-draft-preview` in `app/api/routes.py` -> `app/services/ai_task_draft_service.py` -> `app/services/integrations/llm_text_adapter.py`.
  AI confirm flow: `AiTaskDraftModal.vue` -> `taskService.confirmAiTaskDraft()` -> `POST /api/v1/tasks/ai-draft-confirm` -> `app/services/ai_task_draft_service.py` -> `task_repo.create_task_bundle_with_jobs()` (one transaction for the whole bundle).
  Update flow: `TaskDetail.vue` -> `taskService.updateTask()` -> `PUT /api/v1/tasks/{id}` -> `task_repo.save()`.
  Delete flow: `TaskDetail.vue` -> `taskService.deleteTask()` -> `DELETE /api/v1/tasks/{id}` -> inline job deletion + task deletion in `app/api/routes.py`.
- Persistence touchpoints:
  tasks and jobs are stored in MySQL. Create/update/delete happens through a mix of repository functions and direct `Session(engine)` blocks in `app/api/routes.py`. AI preview does not write to MySQL; AI confirm creates every task and job in the reviewed bundle through one shared backend workflow and **one** transaction (all-or-nothing).
- Integration touchpoints:
  AI preview calls an external text-LLM adapter with an allowlisted subset of tenant context. Plain list/detail/create/update/delete have no external integration.
- Notable risks or inconsistencies:
  the home route uses local component state for selected task rather than the `/tasks/:id` route, so deep linking and in-app selection use different UI shells. The route layer still mixes HTTP handling, template shaping, and direct DB access in one file, although the AI draft preview/confirm path now moves multi-step draft logic into `app/services/ai_task_draft_service.py`. AI draft bundles (one or many tasks) remain browser-memory only until the user confirms or closes the modal; there is no cross-refresh persisted draft session yet.

### Job CRUD And Manual Job Processing

- Trigger: user creates, edits, deletes, marks ready, processes, or retries a job from `frontend/src/components/TaskDetail.vue`.
- Sequence of layers/components:
  `TaskDetail.vue` -> `taskService.createJob/updateJob/deleteJob/processJob` in `frontend/src/services/api.js` -> job routes in `app/api/routes.py`.
  Job processing route `POST /api/v1/tasks/{task_id}/jobs/{job_id}/process` -> `app/services/jobs/processor.process_job()`.
- Persistence touchpoints:
  jobs are created and updated in MySQL. Processing updates `Job.status`, `Job.result`, and may update parent `Task.status` to `PENDING_CONFIRMATION`.
- Integration touchpoints:
  processing may call OpenAI image APIs and FTP upload through the processor path.
- Notable risks or inconsistencies:
  the same processor is reachable both from the worker and from direct user action, so production-like background behavior can also be triggered synchronously via HTTP.

### Task Status Transition And Manual Publish

- Trigger: user clicks submit, approve, disapprove, approve for publication, reject, override processing, or preview/publish actions in `frontend/src/components/TaskDetail.vue`.
- Sequence of layers/components:
  `TaskDetail.vue` -> transition methods in `frontend/src/services/api.js` -> task transition routes in `app/api/routes.py`.
  Most transitions delegate to `app/services/task_repo.py`.
  Publish is special: `POST /api/v1/tasks/{id}/publish` -> `app/services.tasks.publisher.publish_task()` -> `app/services/tasks/publisher_instagram.py`.
- Persistence touchpoints:
  task status changes are persisted in MySQL; `approve_task_for_processing()` also changes matching `Job.status` values from `NEW` to `READY`. Publish appends integration result data to `Task.result.logs`.
- Integration touchpoints:
  manual publish can call Instagram Graph API and depends on previously generated public image URLs.
- Notable risks or inconsistencies:
  route handlers own some workflow checks while repository and publisher layers own others. The API accepts publish from `READY`, `PUBLISHING`, or `FAILED`, which is broader than a simple one-way transition model.

## Background Job Flows

### Tenant Worker Loop

- Trigger: `python -m app.worker` or `startup.sh --worker` (optional `--tenant-id=<UUID>` or `WORKER_TENANT_ID` to scope one tenant).
- Sequence of layers/components:
  `app/worker.py` loads active tenants via `tenant_repo.list_active_tenants()` (or a single tenant if filtered) -> for each tenant, `init_context_by_tenant()` then job poll / optional `run_scheduler()` -> `reset_tenant_context()` after each full pass.
  The loop polls one `READY` job whose parent task is `PROCESSING` and belongs to the current tenant, then calls `app/services/jobs/processor.py`.
- Persistence touchpoints:
  worker reads and writes MySQL through `SQLModel` sessions; it also calls `create_tables()` on startup.
- Integration touchpoints:
  none at the worker-loop level; downstream job processing and scheduler paths do the real external work.
- Notable risks or inconsistencies:
  there is no queue; work discovery is DB polling only. One worker process visits tenants sequentially each cycle. Scheduler execution shares the same loop, so a slow job or many tenants can delay scheduled actions for later tenants in the same pass.

### Image Job Processing

- Trigger: worker picks a `READY` job, or the API route `/tasks/{task_id}/jobs/{job_id}/process` calls the processor directly.
- Sequence of layers/components:
  `app/services/jobs/processor.py` reloads the `Job` from DB -> sets `PROCESSING` -> dispatches by `job.generator`.
  `dalle` uses `app/services/jobs/processor_dalle.py`.
  `gptimage15` uses `app/services/jobs/processor_gptimage15.py`.
  After image generation, `processor.py` optionally calls `app/services/ftpupload.py` to create a `public_url`, persists `Job.result`, and may move the parent `Task` to `PENDING_CONFIRMATION`.
- Persistence touchpoints:
  writes `Job.status`, `Job.updated_at`, `Job.result`, and sometimes parent `Task.status` in MySQL; writes generated files under `output/{task_id}/{job_id}.jpeg`.
- Integration touchpoints:
  OpenAI Images API, optional FTP upload to public hosting.
- Notable risks or inconsistencies:
  processing combines external HTTP calls, filesystem writes, FTP upload, DB writes, and task transition logic in one flow. FTP upload is best-effort, so a job can complete without a public URL, leaving later publish behavior to reconstruct or fail.

### Publish Execution

- Trigger: manual API publish, scheduler publish action, or CLI `scripts/publish_task.py`.
- Sequence of layers/components:
  caller -> `app/services/tasks/publisher.py` -> reload task from DB -> mark `PUBLISHING` -> dispatch by `task.template`.
  Current supported path is `instagram_post` -> `publish_task_instagram()` in `app/services/tasks/publisher_instagram.py`.
  `publisher_instagram.py` loads imagecontent jobs, resolves public image URLs, builds caption, loads tenant/env credentials, then posts to Instagram Graph API.
- Persistence touchpoints:
  task status transitions `READY/PUBLISHING/FAILED` -> `PUBLISHING` -> `PUBLISHED` or `FAILED`; publish result is appended into `Task.result.logs`. Job records are read to build the media set.
- Integration touchpoints:
  Instagram Graph API; tenant env or process env for `INSTAGRAM_ACCESS_TOKEN`, `INSTAGRAM_ACCOUNT_ID`, and optionally `PUBLIC_URL`.
- Notable risks or inconsistencies:
  publish depends on prior processor output shape (`public_url`, `image_path`) and on external accessibility of those images. `publisher.py` and `publisher_instagram.py` both open DB sessions, so the flow crosses multiple persistence boundaries mid-operation.

## Event/Message Flows

### HTTP Auth Failure Event On The Frontend

- Trigger: any authenticated Axios request receives `401`.
- Sequence of layers/components:
  response interceptor in `frontend/src/services/api.js` -> `setUnauthorizedHandler()` -> `authStore.logout()` in `frontend/src/authStore.js` -> clear token and user state -> clear selected tenant.
- Persistence touchpoints:
  removes auth token, user snapshot, and current tenant from `localStorage`.
- Integration touchpoints:
  none; this is client-side reaction to API response.
- Notable risks or inconsistencies:
  session loss is global and immediate for any `401`, regardless of which API call triggered it.

### Scheduler Notification Message Flow

- Trigger: scheduler rule run completes with `DONE`, `NO_TASK`, or `ERROR`.
- Sequence of layers/components:
  `app/services/scheduler/worker.py` -> `_log_schedule_rule_result()` -> `app/services/notifier.notify()` -> Discord webhook POST.
- Persistence touchpoints:
  `ScheduleLog` row is created or updated before notification; notification payload may include serialized `log.result`.
- Integration touchpoints:
  Discord webhook using `DISCORD_WEBHOOK_URL`.
- Notable risks or inconsistencies:
  there is no queue or retry beyond a single HTTP attempt; notifications are tied to current tenant context and silently degrade to logs when webhook configuration is missing.

### Inbound Message/Webhook Flow

- Trigger: none in current code.
- Sequence of layers/components:
  no inbound webhook route or message consumer is wired in `app/main.py`, `app/api/routes.py`, or `app/api/auth_routes.py`.
- Persistence touchpoints:
  none.
- Integration touchpoints:
  none inbound.
- Notable risks or inconsistencies:
  the project uses outbound webhooks and third-party APIs, but currently has no inbound integration surface for callbacks or event-driven processing.

## Webhook Or Scheduled Flows

### Schedule Rule CRUD

- Trigger: user opens `/scheduler` and creates, edits, or deletes rules in `frontend/src/views/SchedulerView.vue`.
- Sequence of layers/components:
  `SchedulerView.vue` -> `scheduleRuleService` in `frontend/src/services/api.js` -> schedule rule routes in `app/api/routes.py` -> `app/services/schedule_rule_repo.py`.
- Persistence touchpoints:
  `ScheduleRule` records are stored in MySQL with `times` JSON of the form `{ hour, days[] }`.
- Integration touchpoints:
  none during CRUD.
- Notable risks or inconsistencies:
  the scheduler UI manages rule definitions only; actual execution happens separately in the worker process.

### Scheduled Rule Evaluation And Action Dispatch

- Trigger: worker loop decides it is time to run scheduler based on `SCHEDULER_CHECK_INTERVAL_SECONDS`.
- Sequence of layers/components:
  `app/worker.py` -> `app/services/scheduler/worker.run_worker()`.
  Scheduler computes current timeslot -> checks existing `ScheduleLog` rows -> scans tenant `ScheduleRule` rows -> evaluates `rule_matches_timeslot()` -> `run_schedule_rule()`.
  Action `testlog` uses `app/services/scheduler/action_testlog.py`.
  Action `publish` uses `app/services/scheduler/action_publish.py` -> `app/services/tasks/publisher.py`.
- Persistence touchpoints:
  reads `ScheduleRule`; creates or updates `ScheduleLog`; resolves a task either from `ScheduleLog.task_id` or `task_repo.fetch_ready_task()`.
- Integration touchpoints:
  `publish` may call Instagram; scheduler result notifications may call Discord.
- Notable risks or inconsistencies:
  scheduler uses `ScheduleRule.times` and current timeslot, not `Task.scheduled_for`. The code handles `ScheduleLogStatus.SCHEDULED`, but no writer for that state is visible in the current codebase, so that branch appears effectively orphaned.

## Data Persistence Flow

### Relational Persistence

- Trigger: nearly every runtime path, including API requests, worker polling, scheduler actions, and publish processing.
- Sequence of layers/components:
  `app/db/engine.py` creates a shared SQLAlchemy/SQLModel engine for MySQL.
  API startup in `app/main.py` and worker startup in `app/worker.py` both call `create_tables()`.
  Callers then persist through a mix of repository helpers (`task_repo`, `tenant_repo`, `schedule_rule_repo`, `user_repo`) and direct `Session(engine)` usage in routes and services.
- Persistence touchpoints:
  MySQL tables for users, tenants, tasks, jobs, schedule rules, and schedule logs.
- Integration touchpoints:
  none directly; persistence is local to MySQL.
- Notable risks or inconsistencies:
  there is no migration layer; schema creation is runtime `create_all()`. Persistence responsibilities are spread across repositories, route handlers, processors, publishers, and scheduler logic rather than a single service boundary.

### Generated File Persistence

- Trigger: image job generation or frontend preview/load of generated outputs.
- Sequence of layers/components:
  `processor_dalle.py` and `processor_gptimage15.py` write files under `OUTPUT_DIR / task_id / job_id.jpeg`.
  `app/main.py` mounts `OUTPUT_DIR` under `/output` and disables cache for `/output/*`.
  Frontend image preview logic in `TaskDetail.vue` consumes job result URLs or `/output/...` paths.
- Persistence touchpoints:
  local filesystem under `output/`; job records persist relative output paths in `Job.result`.
- Integration touchpoints:
  FTP upload may copy generated files to a public host; Instagram publish may consume either uploaded public URLs or URLs constructed from `PUBLIC_URL`.
- Notable risks or inconsistencies:
  file persistence is partly local and partly externalized through FTP/public hosting; the resulting path/url contract is implicit in `Job.result`.

## External Integration Flow

### OpenAI Image Generation

- Trigger: job processing for `generator == "dalle"` or `generator == "gptimage15"`.
- Sequence of layers/components:
  `app/services/jobs/processor.py` -> generator-specific processor module -> OpenAI HTTP POST -> optional image download for DALL-E -> local file write -> result returned to processor.
- Persistence touchpoints:
  generated image file written locally; result metadata stored in `Job.result`.
- Integration touchpoints:
  OpenAI Images API.
- Notable risks or inconsistencies:
  integration errors are wrapped and stored on the job, but there is no retry queue beyond rerunning the same processor path.

### FTP Public Upload

- Trigger: successful image generation in `app/services/jobs/processor.py`.
- Sequence of layers/components:
  `processor.py` -> `app/services/ftpupload.uploadToPublic()` -> FTP server -> `public_url` returned to processor.
- Persistence touchpoints:
  returned `public_url` is written into `Job.result`.
- Integration touchpoints:
  FTP server and public URL host.
- Notable risks or inconsistencies:
  upload is best-effort; failures do not fail the job. That means downstream Instagram publishing may later fail or fall back to constructing a URL from `PUBLIC_URL` and stored image path.

### Instagram Delivery

- Trigger: manual publish or scheduled publish action.
- Sequence of layers/components:
  `app/services/tasks/publisher.py` -> `app/services/tasks/publisher_instagram.py` -> `_InstagramPublisherClient` -> Graph API media creation -> optional publish retry on error code `9007` -> media info fetch.
- Persistence touchpoints:
  reads task and imagecontent jobs; writes final publish status and result data back to task.
- Integration touchpoints:
  Instagram Graph API.
- Notable risks or inconsistencies:
  publishing only works with publicly reachable image URLs. Credentials are pulled from tenant `env` first, then process env, so integration configuration is partly stored in database data and partly in environment state.

### Discord Notifications

- Trigger: scheduler result logging.
- Sequence of layers/components:
  `app/services/scheduler/worker.py` -> `app/services/notifier.py` -> `requests.post()` to webhook URL.
- Persistence touchpoints:
  notification uses already-persisted `ScheduleLog` state as message input; no dedicated notification table exists.
- Integration touchpoints:
  Discord webhook.
- Notable risks or inconsistencies:

  notification is outbound-only and scheduler-specific; processor and publish failures are not centrally routed through the same notifier.
