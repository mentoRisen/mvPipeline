---
date: 2026-05-31
topic: backup-strategy
---

# Local Backup Strategy

## Summary

Add a daily cron-driven backup on the Hetzner VPS that writes dated artifacts for the MySQL database, `output/`, server `.env`, and a workspace snapshot of the application code — stored outside the repo with automatic rotation. Backups are local-only: they protect against accidental deletes and bad edits, not full server or disk loss.

## Problem Frame

mvPipeline currently has no automated backups. The deployment runbook already recommends daily MySQL dumps and output archives, but nothing implements that. The database (~1 MB), generated assets in `output/` (~107 MB), secrets in `.env`, and uncommitted VPS edits are all at risk from operator mistakes, bad commands, or partial cleanup. Code committed to GitHub is safe; everything else on the server is not.

---

## Key Decisions

- **Structured daily folder (Approach C).** Each run produces a dated directory with separate artifacts per concern rather than one monolithic tarball. Easier to inspect, restore one piece at a time, and extend later.
- **Local-only, same VPS.** No off-site sync in v1. Matches the goal of protecting against accidental loss, not disaster recovery.
- **Cron + shell script.** One script invoked by cron; no systemd timer or manual-only workflow for v1.
- **Workspace snapshot included.** Tar the application tree excluding heavy or separately backed-up paths (`output/`, virtualenv, `node_modules/`, backup destination). Captures uncommitted server edits GitHub does not have.
- **Backup root outside the repo.** Artifacts live under a system backup path (e.g. `/var/backups/mvpipeline/`), not inside `/opt/mvPipeline`, so repo operations cannot wipe backups.

---

## Requirements

**Backup content**

- R1. Each run produces a **MySQL dump** of the `mvpipeline` database, compressed.
- R2. Each run produces a **compressed archive of `output/`** (repo-relative `output/`).
- R3. Each run copies the server **`.env`** file as a distinct artifact (secrets are not in git).
- R4. Each run produces a **workspace archive** of the application tree at `/opt/mvPipeline`, excluding at minimum: `output/` (separate artifact), Python virtualenv, `frontend/node_modules/`, and the backup destination itself. Uncommitted code and local-only files must be included.

**Layout and retention**

- R5. Artifacts are stored under a **dated folder** (one folder per run, e.g. `YYYY-MM-DD/` or `YYYY-MM-DD_HHMMSS/` if multiple daily runs are ever needed).
- R6. Each dated folder contains **separate named artifacts** for database, output, env, and workspace — not a single combined archive.
- R7. A **retention policy** automatically deletes backup folders older than a configured window (default **7 days**).
- R8. The backup destination is **outside the git working tree** and is not included in the workspace archive.

**Automation and operability**

- R9. A **single entry-point script** performs all four artifacts plus rotation in one run.
- R10. A **cron job** invokes the script on a fixed schedule (default **daily**, off-peak time acceptable).
- R11. The script **logs success or failure** to a persistent log file; a failed run must not silently delete newer data.
- R12. Backup artifacts and the log file use **restrictive filesystem permissions** (owner-only read) because `.env` and database dumps contain secrets.

**Documentation**

- R13. The deployment runbook (`docs/deployment-hetzner-flow-mentoverse.md`) is updated with: backup location, cron setup, what is included/excluded, and a short **manual restore checklist** (which artifact to use for each recovery scenario).

---

## Key Flows

- F1. **Scheduled backup**
  - **Trigger:** Cron fires at the configured time.
  - **Steps:** Create dated folder → dump DB → archive output → copy `.env` → archive workspace (with excludes) → prune folders older than retention → append result to log.
  - **Outcome:** Four artifacts exist under the dated folder; old folders beyond retention are removed.

- F2. **Restore database**
  - **Trigger:** Operator needs to recover DB after bad migration, accidental delete, or corruption.
  - **Steps:** Stop or pause API/worker if needed → decompress and import the chosen `db` artifact into MySQL → restart services → verify.
  - **Outcome:** Database matches the backup point in time.

- F3. **Restore output or workspace**
  - **Trigger:** Operator needs to recover generated files or uncommitted code state.
  - **Steps:** Extract the relevant `output` or `workspace` artifact to a staging path → selectively copy needed paths back → verify publish paths / app behavior.
  - **Outcome:** Lost files or code state are recovered without overwriting unrelated live data blindly.

---

## Acceptance Examples

- AE1. **Covers R1, R5, R6.** Given a successful cron run on 2026-05-31, a folder exists with separate database, output, env, and workspace artifacts for that date.
- AE2. **Covers R4, R8.** Given `output/` contains 100 MB of files and the repo has uncommitted edits under `app/`, the workspace artifact excludes `output/` but includes the uncommitted `app/` changes.
- AE3. **Covers R7.** Given backups exist for the last 10 days and retention is 7, after a run only the 7 most recent dated folders remain.
- AE4. **Covers R11.** Given the database dump step fails (e.g. MySQL unavailable), the script exits non-zero, logs the failure, and does not delete existing backup folders as part of a partial run.
- AE5. **Covers R12.** Given a backup completed successfully, `.env` copy and database dump are not world-readable.

---

## Success Criteria

- An operator can point to one script and one cron line as the entire backup setup.
- After any daily run, all four artifact types exist and are restorable without reading source code.
- Retention prevents unbounded disk growth on the VPS (current data sizes are small; policy must still be explicit).
- Deployment docs describe setup and restore well enough that someone other than the original author can recover.

---

## Scope Boundaries

**Deferred for later**

- Off-site backup (S3, Hetzner Storage Box, rsync to another host).
- Automated restore script or one-click recovery.
- Alerting on failure (email, Discord, health check).
- Backing up nginx/systemd unit files (rebuildable from deployment docs).
- Backing up `logs/`, `venv/`, or `node_modules/`.
- Incremental or deduplicated backups (restic, borg).

**Outside this product's identity**

- Full disaster-recovery / multi-region redundancy for mvPipeline.
- Backup-as-a-service UI inside the application.

---

## Dependencies / Assumptions

- MySQL is reachable locally with credentials available to the backup script (from existing `.env` or equivalent).
- The `deployer` user (or the cron identity) can read `/opt/mvPipeline`, write to the backup root, and run `mysqldump`.
- Disk space on the VPS remains sufficient for 7 days of full artifacts at current sizes (~110 MB output + small DB + workspace); retention window can be tuned if growth accelerates.
- GitHub remains the source of truth for **committed** code; the workspace artifact is a safety net for uncommitted VPS state.

---

## Outstanding Questions

**Deferred to Planning**

- Exact backup root path and cron schedule time.
- Whether workspace archive excludes `.git/` (smaller artifacts vs. full clone fidelity).
- Whether to log `git status --porcelain` alongside artifacts as a cheap uncommitted-changes indicator.
