---
title: "feat: Local VPS backup (DB, output, env, workspace)"
type: feat
status: completed
date: 2026-05-31
origin: docs/brainstorms/2026-05-31-backup-strategy-requirements.md
---

# feat: Local VPS backup (DB, output, env, workspace)

## Summary

Add a daily cron-driven local backup for the Hetzner VPS: one shell script writes four separate artifacts per dated folder (MySQL dump, `output/` archive, `.env` copy, workspace snapshot) under `/var/backups/mvpipeline/`, rotates folders older than seven days only after a fully successful run, and logs outcomes to a persistent file outside the repo. Update the deployment runbook with setup and manual restore steps.

## Problem Frame

mvPipeline has no automated backups today. The deployment runbook recommends daily MySQL dumps and output archives but provides no script or procedure. Database rows, generated assets in gitignored `output/`, secrets in `.env`, and uncommitted VPS edits are recoverable only from GitHub for committed code — everything else is at risk from operator mistakes. (see origin: `docs/brainstorms/2026-05-31-backup-strategy-requirements.md`)

---

## Requirements

Traceability to origin requirements (R1–R13):

- R1. Compressed MySQL dump of `mvpipeline` database.
- R2. Compressed archive of repo `output/`.
- R3. Distinct copy of server `.env`.
- R4. Workspace archive excluding `output/`, `venv/`, `frontend/node_modules/`, and backup destination; includes uncommitted edits.
- R5. Dated folder per run (`YYYY-MM-DD`).
- R6. Four separate named artifacts — not one combined tarball.
- R7. Retention deletes folders older than seven days (configurable constant in script).
- R8. Backup root outside git working tree; not included in workspace archive.
- R9. Single entry-point script performs all steps plus rotation.
- R10. Cron invokes script daily (documented in runbook; installed on server by operator).
- R11. Persistent log records success/failure; failed run does not prune existing backups.
- R12. Sensitive artifacts use owner-only permissions.
- R13. Deployment runbook updated with location, cron, includes/excludes, restore checklist.

Origin flows F1–F3 and acceptance examples AE1–AE5 are covered by U1–U3 test scenarios and runbook restore steps.

---

## Key Technical Decisions

- **Entry point:** `scripts/backup_local.sh` — matches existing ops script location (`scripts/sync_schema.py`, `startup.sh` bash precedent) and gives cron a single target (see origin KTD: cron + shell script).
- **Backup root:** `/var/backups/mvpipeline/` on the VPS — outside `/opt/mvPipeline` so repo operations cannot delete backups (R8).
- **Dated folder naming:** `YYYY-MM-DD` — sufficient for once-daily cron; a same-day manual re-run overwrites artifacts in that day's folder.
- **Artifact names:** `db.sql.gz`, `output.tar.gz`, `.env`, `workspace.tar.gz` — predictable restore mapping (R6).
- **Database credentials:** Parse `DATABASE_URL` from `/opt/mvPipeline/.env`; never hardcode passwords or log credential material (security rule + R12).
- **Workspace excludes:** `output/`, `venv/`, `frontend/node_modules/`, `.git/` — `.git/` excluded per planning decision (GitHub is source of truth for committed history; smaller artifacts). Uncommitted file content still captured.
- **No `git-status.txt` sidecar:** omitted per user preference during planning — uncommitted state is visible inside the workspace tar.
- **Failure handling:** `set -euo pipefail`; on any step failure, remove the in-progress dated folder if partially created, log failure, exit non-zero, **skip retention prune** (AE4).
- **Retention timing:** Prune only after all four artifacts succeed — never delete older folders during a failed run.
- **Permissions:** `umask 077` during artifact creation (or explicit `chmod 600` on files) so dumps and `.env` are not group/world-readable (AE5).
- **Log file:** `/var/log/mvpipeline-backup.log` — outside repo, append-only timestamped lines, no secret payloads.
- **Cron:** `deployer` crontab, `0 3 * * *` (03:00 daily server local time) — documented in runbook; not committed as a repo file.
- **Testing:** `tests/ops/test_backup_local.py` with stubbed `mysqldump`/`tar` in temp dirs — aligns with `.cursor/rules/03-testing.mdc` (no permanent `scripts/test_*.py`).

---

## High-Level Technical Design

```mermaid
flowchart TB
  cron[Cron 03:00 deployer] --> script[scripts/backup_local.sh]
  script --> mkdir[Create YYYY-MM-DD folder]
  mkdir --> db[mysqldump → db.sql.gz]
  db --> out[tar output/ → output.tar.gz]
  out --> env[copy .env]
  env --> ws[tar workspace → workspace.tar.gz]
  ws --> prune[Delete folders older than 7 days]
  prune --> log[Append success to log]
  db -.->|failure| fail[Remove partial folder, log error, exit 1]
  out -.->|failure| fail
  env -.->|failure| fail
  ws -.->|failure| fail
```

**Configurable via script constants or env overrides (for tests):**

| Variable | Default | Purpose |
|----------|---------|---------|
| `MVP_BACKUP_ROOT` | `/var/backups/mvpipeline` | Destination root |
| `MVP_REPO_ROOT` | `/opt/mvPipeline` | Application tree |
| `MVP_BACKUP_LOG` | `/var/log/mvpipeline-backup.log` | Log path |
| `MVP_RETENTION_DAYS` | `7` | Folder retention window |

---

## Scope Boundaries

**In scope**

- Backup script, pytest coverage, runbook setup/restore documentation.

**Deferred for later** (from origin — unchanged)

- Off-site sync, automated restore, failure alerting, nginx/systemd unit backups, `logs/`/`venv`/`node_modules/` as separate artifacts, restic/borg.

**Deferred to Follow-Up Work**

- Optional `ce-compound` learning doc after first successful production cron run.

---

## Risks & Dependencies

- **Cron identity must match file access:** `deployer` needs read on repo, write on backup root and log file. First-time server setup must `mkdir` backup root and log with correct ownership (documented in runbook).
- **Partial disk fill:** Seven daily full copies of ~110 MB output is manageable today; retention constant is easy to tune if `output/` grows.
- **MySQL unavailable during dump:** Script fails closed; existing backups preserved (AE4).

---

## Implementation Units

### U1. Local backup shell script

**Goal:** Single script that produces four artifacts, enforces permissions, rotates old folders on success only, and logs outcomes.

**Requirements:** R1–R4, R5–R9, R11–R12

**Dependencies:** None

**Files:**

- Create: `scripts/backup_local.sh`

**Approach:**

- Bash with `set -euo pipefail`, following `startup.sh` conventions (`SCRIPT_DIR`, explicit error messages).
- Resolve paths from env overrides with production defaults above.
- Load `.env` safely: extract host, user, password, database from `DATABASE_URL` (`mysql+pymysql://user:pass@host:port/db`) using bash parameter expansion or a small inline parser — do not `source` `.env` wholesale (avoids executing arbitrary shell).
- Steps in order: create dated dir → `mysqldump | gzip` → `tar czf output/` (if directory exists; empty tar or skip with log if missing) → `cp .env` → `tar czf` workspace with `--exclude` flags → prune by parsing folder names or `find -mtime` → log success.
- On error: trap removes `$BACKUP_ROOT/$DATE/` if created this run; append failure line to log; exit 1 without running prune.
- Prune: delete subdirectories of backup root whose names parse as dates older than retention window; only run when all steps succeeded.
- Script accepts optional `--dry-run` flag that prints planned actions without writing (useful for operator verification; not required by origin but low-cost).

**Patterns to follow:**

- `startup.sh` — `set -euo pipefail`, `SCRIPT_DIR`, clear usage header.
- `scripts/sync_schema.py` — module docstring with Usage block at top of script (as comments in shell).

**Test expectation:** none — covered by U2

**Verification:**

- Manual run on VPS (after creating backup root) produces four artifacts under today's dated folder with `600` permissions.
- Simulated mysqldump failure leaves prior dated folders untouched.

---

### U2. Ops pytest coverage

**Goal:** Automated regression coverage for backup script behavior without live MySQL.

**Requirements:** R1–R4, R6–R8, R11–R12; covers AE1, AE2, AE3, AE4, AE5

**Dependencies:** U1

**Files:**

- Create: `tests/ops/test_backup_local.py`
- Create: `tests/ops/__init__.py` (if needed for package discovery)

**Approach:**

- Use `tmp_path` fixtures for fake repo layout: minimal `output/`, `.env` with test `DATABASE_URL`, dummy file under `app/` for uncommitted content, stub `venv/` and `frontend/node_modules/` dirs.
- Place a stub `mysqldump` executable early in `PATH` that writes a marker SQL file to stdout.
- Invoke `bash scripts/backup_local.sh` via `subprocess` with env overrides pointing `MVP_BACKUP_ROOT`, `MVP_REPO_ROOT`, `MVP_BACKUP_LOG`, and shortened `MVP_RETENTION_DAYS`.
- Assert artifact presence, separate files (not monolithic), workspace tar excludes `output/` but includes dummy app file, permissions are owner-only, retention removes old dated folders after success.
- Failure test: stub `mysqldump` exits 1 → script exits non-zero, pre-existing backup folder remains, new partial folder removed.

**Test scenarios:**

- Covers AE1. Happy path: four artifacts created under dated folder with expected filenames.
- Covers AE2. Workspace tar excludes `output/` contents but includes test file under `app/`.
- Covers AE3. Given ten pre-seeded dated folders and retention 7, after successful run only seven newest remain.
- Covers AE4. Given mysqldump failure, script exits non-zero and does not delete pre-existing backup folders.
- Covers AE5. Given successful run, `.env` copy and db artifact are not group/world-readable (`stat` mode check).
- Edge case: empty or missing `output/` directory — script completes without error (creates empty archive or skips with logged note; behavior pinned in test).

**Verification:**

- `pytest tests/ops/test_backup_local.py` passes in CI/local venv.

---

### U3. Deployment runbook updates

**Goal:** Operators can install cron, locate backups, and restore DB/output/workspace/env without reading script source.

**Requirements:** R10, R13; supports origin flows F2, F3

**Dependencies:** U1

**Files:**

- Modify: `docs/deployment-hetzner-flow-mentoverse.md`

**Approach:**

- Replace/extend §13 Operational Notes backup bullet with concrete procedure.
- Add new section (§15 Local Backups) covering:
  - One-time setup: `sudo mkdir -p /var/backups/mvpipeline`, `touch /var/log/mvpipeline-backup.log`, `chown deployer:deployer` both.
  - Script path and manual test command.
  - Cron line for `deployer`: `0 3 * * * /opt/mvPipeline/scripts/backup_local.sh >> /var/log/mvpipeline-backup.log 2>&1` (or rely on script's internal logging — pick one pattern, document clearly).
  - Artifact layout table and workspace exclude list.
  - **Restore checklist:**
    - **Database:** stop `mvpipeline-api.service` and `mvpipeline-worker.service` → import `db.sql.gz` → optional `python scripts/sync_schema.py --check-only` → restart services.
    - **Output:** extract `output.tar.gz` to staging → copy needed task folders back to `output/`.
    - **Workspace:** extract to staging → merge selected paths (warn about overwriting live tree).
    - **`.env`:** restore only when secrets lost; verify permissions after copy.
  - Explicit note: local-only — does not protect against full VPS/disk loss (defers off-site to future work).

**Test expectation:** none — documentation-only unit

**Verification:**

- Runbook section is self-contained; paths and service names match existing §7 systemd units.

---

## Sources & Research

- Origin: `docs/brainstorms/2026-05-31-backup-strategy-requirements.md`
- Runbook: `docs/deployment-hetzner-flow-mentoverse.md` (§13 recommendation, §4 MySQL, §7 systemd)
- Bash precedent: `startup.sh`
- Ops script precedent: `scripts/sync_schema.py`
- Testing rule: `.cursor/rules/03-testing.mdc`
- Security rule: `.cursor/rules/04-security.mdc`
