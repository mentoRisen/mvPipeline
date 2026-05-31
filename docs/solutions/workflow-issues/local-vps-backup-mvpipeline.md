---
title: Local VPS backup for mvPipeline (cron, mysqldump, artifacts)
date: 2026-05-31
category: workflow-issues
module: deployment
problem_type: workflow_issue
component: development_workflow
severity: medium
applies_when:
  - "Backing up MySQL, output/, .env, and workspace on the Hetzner VPS"
  - "mysqldump prints PROCESS privilege / tablespace errors for the mvpipeline MySQL user"
tags:
  - backup
  - cron
  - mysqldump
  - mysql-8
  - hetzner
  - deployment
resolution_type: tooling_addition
---

# Local VPS backup for mvPipeline (cron, mysqldump, artifacts)

## Context

mvPipeline had no automated backups on the Hetzner dev VPS. Generated assets live in gitignored `output/`, secrets in `.env`, and uncommitted VPS edits are not on GitHub. The deployment runbook only recommended backups in prose.

We implemented **Approach C**: a daily cron job runs one shell script that writes four separate artifacts per dated folder under `/var/backups/mvpipeline/`, with 7-day retention and logging outside the repo.

During the first manual run, `mysqldump` printed a tablespace/PROCESS privilege error to stderr even though the script logged success and produced a valid `db.sql.gz`.

## Guidance

**Script and layout**

- Entry point: `scripts/backup_local.sh`
- Backup root: `/var/backups/mvpipeline/YYYY-MM-DD/`
- Artifacts: `db.sql.gz`, `output.tar.gz`, `.env`, `workspace.tar.gz`
- Log: `/var/log/mvpipeline-backup.log`
- Workspace tar excludes `output/`, `venv/`, `frontend/node_modules/`, `.git/`
- Retention keeps the **7 newest daily folders**; prune runs only after a fully successful backup
- Runbook: `docs/deployment-hetzner-flow-mentoverse.md` §15

**MySQL dump (MySQL 8, app user without PROCESS)**

Always pass `--no-tablespaces` to `mysqldump` for the `mvpipeline` database user. Without it, MySQL 8 prints:

```text
mysqldump: Error: 'Access denied; you need (at least one of) the PROCESS privilege(s) for this operation' when trying to dump tablespaces
```

The dump can still **exit 0** and produce a restorable file — stderr looks like failure while the script treats the run as success. The script now:

1. Uses `--no-tablespaces` (clean stderr)
2. Captures mysqldump stderr and fails if any error text remains

**Cron (deployer user)**

One-time paths:

```bash
sudo mkdir -p /var/backups/mvpipeline
sudo touch /var/log/mvpipeline-backup.log
sudo chown deployer:deployer /var/backups/mvpipeline /var/log/mvpipeline-backup.log
chmod +x /opt/mvPipeline/scripts/backup_local.sh
```

Crontab:

```cron
# mvPipeline daily local backup (DB, output, .env, workspace)
0 3 * * * /opt/mvPipeline/scripts/backup_local.sh
```

The script writes its own log lines; cron does not need extra redirection.

## Why This Matters

Local-only backups protect against accidental deletes and bad edits on the VPS, not full disk or server loss. Without `--no-tablespaces`, operators see scary mysqldump errors on every run and may distrust backups that are actually valid. Structured daily folders make partial restores (DB only, output only, etc.) straightforward.

## When to Apply

- Setting up or debugging backups on `flow.mentoverse.eu` / Hetzner VPS
- Any MySQL 8 `mysqldump` using a scoped app user without global `PROCESS`
- Verifying cron: `crontab -l`, then `tail /var/log/mvpipeline-backup.log` after 03:00

## Examples

**Verify today's backup**

```bash
ls -la /var/backups/mvpipeline/$(date +%Y-%m-%d)/
zcat /var/backups/mvpipeline/$(date +%Y-%m-%d)/db.sql.gz | head -20
```

**mysqldump flags in script**

```bash
mysqldump \
  --single-transaction \
  --no-tablespaces \
  --routines \
  --triggers \
  "$db_name"
```

## Related

- Plan: `docs/plans/2026-05-31-001-feat-local-backup-plan.md`
- Requirements: `docs/brainstorms/2026-05-31-backup-strategy-requirements.md`
- Tests: `tests/ops/test_backup_local.py`
