# Glossary

This glossary defines terms as they are used in this repository today. It is grounded in the codebase and docs, especially `README.md`, `docs/project-audit.md`, `docs/runtime-flows.md`, the SQLModel entities, API schemas, and the runtime services.

## Domain Terms

| Term | Definition In This Project | Ambiguity / Notes |
|---|---|---|
| `Mentoverse Pipeline` | The product name for this app: a multi-tenant system for generating image content and publishing it to Instagram. | Grounded in `README.md`. |
| `task` | The main unit of work at the product level: one Instagram-post workflow with status, tenant, metadata, post content, and publish result. | Not the same thing as a background queue task. |
| `job` | A child unit under a task that performs AI/image generation work. Jobs have their own status, generator, prompt, result, and display order. | Easy to confuse with generic “background job”; here it is a DB entity. |
| `tenant` | A project/account boundary that owns tasks and schedule rules. It also carries tenant-specific configuration in `env`. | README also calls this a “project”. |
| `project` | A user-facing synonym for `tenant`. README says the app manages projects (tenants). | Ambiguous because the code consistently uses `tenant`, not `project`, as the canonical model name. |
| `template` | A task type identifier that determines the default `meta` and `post` JSON structure and affects publish behavior. | Currently only `instagram_post` is wired. |
| `instagram_post` | The only registered task template. It produces `meta.theme` and `post.caption` defaults and maps to Instagram publishing behavior. | Defined in `app/template/instagram_post.py` and route template lookup. |
| `meta` | Task JSON metadata. In the current template, this mainly includes fields like `theme`; legacy support also places fields like `quote_text`, `caption_text`, and `image_generator` here. | Ambiguous because some values are true metadata and some are legacy compatibility fields. |
| `post` | Task JSON describing publishable post content. In the current template, this primarily means the Instagram `caption`. | More concrete than `meta`, but still free-form JSON. |
| `caption` | The text sent with an Instagram post. It lives in `task.post.caption`. | `caption_text` also exists as a legacy API/schema term. |
| `theme` | A template-defined metadata field for the content theme/topic of a task. | Exists in `instagram_post` template JSON, but business meaning is intentionally open-ended. |
| `imagecontent` | A job `purpose` value meaning the job’s output is meant to become an image asset for publishing. | Used directly by `publisher_instagram.py` and UI job forms. |
| `publish` | The act of delivering a task’s generated assets to Instagram. | Also used as an API route name, scheduler action, and service function name. |
| `public_url` | A publicly reachable URL for a generated image, usually created after FTP upload and later used for Instagram publishing. | Critical to publish flow; if absent, code may try to reconstruct a URL from `PUBLIC_URL` plus image path. |
| `schedule rule` | A per-tenant rule describing an `action` and a weekly time pattern in `times`. | Stored in `schedule_rules`. |
| `schedule log` | An execution record for a schedule rule at a specific timeslot, optionally tied to a task. | Stored in `schedule_logs`. |
| `timeslot` | A scheduler bucket string in `YYYY-MM-DD-HH` format used to identify one scheduler run window. | Derived in `app/services/scheduler/worker.py`. |

## Internal Technical Terms

| Term | Definition In This Project | Ambiguity / Notes |
|---|---|---|
| `worker` | The long-running tenant-scoped process started by `python -m app.worker` that polls for ready jobs and periodically runs scheduler logic. | One worker per tenant is the intended operating model. |
| `processor` | The service path that executes a job by generator type and writes back job/task state. | In practice, this means `app/services/jobs/processor.py` and generator-specific processors. |
| `generator` | The job field selecting the image-generation implementation, such as `dalle` or `gptimage15`. | Schemas/comments imply broader meanings than what `processor.py` currently supports. |
| `tenant context` | The current tenant stored in a `contextvars` variable and initialized by `init_context_by_tenant()`. | Important because scheduler/notifier logic depends on it being set. |
| `tenant env` | The JSON blob on a tenant record containing tenant-specific config like `INSTAGRAM_ACCESS_TOKEN`, `INSTAGRAM_ACCOUNT_ID`, and `PUBLIC_URL`. | Also copied into `os.environ` by `app/context.py`, which makes it both data and runtime config. |
| `action` | A schedule-rule action string. The scheduler currently handles `testlog` and `publish`. | Schemas/models mention `remind`, but current scheduler code does not implement it. |
| `testlog` | A scheduler action used for testing/logging scheduler execution. | It is real in the code, but primarily operational rather than domain-facing. |
| `/output` | The HTTP-mounted static path that serves generated files from `OUTPUT_DIR`. | Managed in `app/main.py`; frontend previews depend on it. |
| `OUTPUT_DIR` | The local filesystem directory where generated images are written before optional upload/publish. | Defaults to `output/` under repo root. |
| `result` | A JSON field on both `Job` and `Task`. On jobs it stores generation output/errors; on tasks it stores publish logs/results. | Same word, different payload shape depending on entity. |
| `logs` | On a task, `result.logs` is an array of publish results; separately, `logs/` is a filesystem directory for process logs. | Overloaded between DB payloads and filesystem logging. |
| `create_tables()` | Runtime schema creation using `SQLModel.metadata.create_all(engine)`. | This is bootstrapping, not a migration system. |

## Overloaded Or Ambiguous Words

| Term | Meaning In This Project | Why It Is Ambiguous |
|---|---|---|
| `ready` | For a `Task`, ready to publish. For a `Job`, ready to process. | Same word across two different state machines. |
| `processing` | For a `Task`, the content-generation phase. For a `Job`, the individual generator run. For a `ScheduleLog`, rule execution in progress. | Shared label across task, job, and schedule-log statuses. |
| `publish` | A task status transition, an API route, a scheduler action, and a service function. | The same word refers to UI action, HTTP surface, scheduler behavior, and integration logic. |
| `template` | A DB/API field on a task, a Python template class, and a UI/API “JSON template” shape. | Different layers use the same word for type selection and data scaffolding. |
| `job` | A DB entity under a task, but also colloquially “background job”. | The worker loop processes `Job` rows, not an external queue abstraction. |
| `project` | README uses it as a user-facing synonym for `tenant`. | No `Project` model exists. |
| `result` | JSON output on both `Job` and `Task`. | Similar name, different schema and meaning. |
| `logs` | Process log files under `logs/` and publish log entries inside `task.result.logs`. | Storage location and semantics differ completely. |
| `caption_text` | A legacy compatibility field accepted by task creation routes and the frontend JSON flow. | Current canonical publish caption is `task.post.caption`, not a top-level task field. |
| `quote_text` | A legacy compatibility field accepted by task creation routes and mentioned in stale schema/model surfaces. | The current task model does not store a first-class `quote_text` column. |
| `image_generator` | A legacy compatibility field accepted by task creation routes and stuffed into `task.meta`. | Actual runtime generation is driven by `job.generator`, not a task-level image-generator pipeline. |
| `image_generator_prompt` | A legacy schema/response term from an older task-level generator design. | Current runtime generation uses `job.prompt.prompt`. |
| `last_error` | A response-schema field that suggests a task-level error field. | The current task model does not have a first-class `last_error` column. |
| `remind` | Mentioned in schedule-rule docs/schemas as an example action. | Current scheduler implementation does not handle it; only `testlog` and `publish` are matched. |

## Abbreviations And Acronyms

| Term | Meaning In This Project | Ambiguity / Notes |
|---|---|---|
| `API` | Usually the FastAPI HTTP API; in some contexts also external HTTP APIs like OpenAI or Instagram Graph API. | Scope depends on context. |
| `JWT` | The access token issued by `/api/v1/auth/login` and sent as `Authorization: Bearer ...`. | Standard auth term, locally implemented. |
| `Bearer` | The token scheme used for authenticated API calls. | Appears in auth docs and routes. |
| `FTP` | The upload mechanism used to push generated files to a public location for Instagram consumption. | Used by `ftpupload.py`. |
| `DALL-E` / `dalle` | The OpenAI image-generation mode exposed as a job generator value. | Code uses lowercase `dalle` for the enum-like value, mixed case in docs/comments. |
| `GPT-Image-1.5` / `gptimage15` | Another OpenAI image-generation mode exposed as a job generator value. | Code uses compact `gptimage15` as the actual generator string. |
| `DOW` | Day of week. Used in comments and scheduler logic for cron-style weekday lists. | Scheduler uses cron-style mapping where Sunday is `0`. |
| `CORS` | Cross-origin settings on the FastAPI app so the frontend can call the backend. | Configured permissively in `app/main.py`. |
| `DSN` | Sentry DSN for optional error reporting. | Present in config/docs, but Sentry is not part of the main runtime flow. |

## Key Entities And Definitions

| Entity | Definition In This Project | Ambiguity / Notes |
|---|---|---|
| `User` | An authenticated application user with username, optional email, hashed password, and active flag. | There is API support for user CRUD, but no dedicated frontend UI for it. |
| `Tenant` | The multi-tenant boundary for tasks and schedule rules, plus tenant-scoped integration config. | Also described as a “project” in docs. |
| `Task` | The parent entity for one Instagram-post workflow, including status, tenant, template, `meta`, `post`, and publish `result`. | Core domain entity. |
| `Job` | A child entity under a task that performs AI/image generation work, defined by `generator`, `purpose`, `prompt`, and `result`. | Core runtime processing entity. |
| `ScheduleRule` | The per-tenant scheduler definition containing `action`, optional note, and weekly timing JSON. | Execution is separate from CRUD. |
| `ScheduleLog` | The per-timeslot execution record for a schedule rule, optionally tied to a task and storing action result/error JSON. | Contains a `SCHEDULED` status that appears underused in current code. |

### Canonical Status Sets

| Enum | Values | Definition In This Project |
|---|---|---|
| `TaskStatus` | `draft`, `pending_approval`, `disapproved`, `processing`, `pending_confirmation`, `rejected`, `ready`, `publishing`, `published`, `failed` | Lifecycle of a task from creation, through processing and approval, to publish or failure. |
| `JobStatus` | `new`, `ready`, `processing`, `processed`, `error` | Lifecycle of a child generation job. |
| `ScheduleLogStatus` | `scheduled`, `processing`, `no_task`, `error`, `done` | Lifecycle/result of one scheduled action execution. |

### Frontend Route Vocabulary

| Term | Definition In This Project | Ambiguity / Notes |
|---|---|---|
| `/` | Main tasks UI that combines task list and selected task detail. | Uses local selected-task state, not route state. |
| `/tasks/:id` | Direct task-detail route. | Separate from the split-pane home flow. |
| `/tenants` | Tenant management UI. | CRUD for tenant records only. |
| `/scheduler` | Schedule-rule management UI. | Edits rules; does not execute scheduling itself. |
| `/login` | Sign-in route for the frontend. | Public route in the Vue router. |

### Client Storage Vocabulary

| Key | Definition In This Project | Ambiguity / Notes |
|---|---|---|
| `mv_auth_token` | Browser `localStorage` key for JWT access token. | Cleared on logout or `401`. |
| `mv_auth_user` | Browser `localStorage` key for current user snapshot. | Convenience cache, not source of truth. |
| `mentoverse_current_tenant` | Browser `localStorage` key for selected tenant id/name. | Controls frontend tenant scoping, not backend auth scoping. |
