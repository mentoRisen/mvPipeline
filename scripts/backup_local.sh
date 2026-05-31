#!/usr/bin/env bash
# Local VPS backup: MySQL dump, output/, .env, and workspace snapshot.
#
# Usage:
#   scripts/backup_local.sh
#   scripts/backup_local.sh --dry-run
#
# Environment overrides (for tests or non-default paths):
#   MVP_BACKUP_ROOT   default /var/backups/mvpipeline
#   MVP_REPO_ROOT     default /opt/mvPipeline
#   MVP_BACKUP_LOG    default /var/log/mvpipeline-backup.log
#   MVP_RETENTION_DAYS default 7

set -euo pipefail

readonly MVP_BACKUP_ROOT="${MVP_BACKUP_ROOT:-/var/backups/mvpipeline}"
readonly MVP_REPO_ROOT="${MVP_REPO_ROOT:-/opt/mvPipeline}"
readonly MVP_BACKUP_LOG="${MVP_BACKUP_LOG:-/var/log/mvpipeline-backup.log}"
readonly MVP_RETENTION_DAYS="${MVP_RETENTION_DAYS:-7}"

DRY_RUN=false
BACKUP_DATE=""
BACKUP_DIR=""
CREATED_BACKUP_DIR=false

usage() {
  echo "Usage: $(basename "$0") [--dry-run]" >&2
}

log_message() {
  local level="$1"
  shift
  local line
  line="$(date -Iseconds) [$level] $*"
  if [[ "$DRY_RUN" == true ]]; then
    echo "$line"
    return
  fi
  mkdir -p "$(dirname "$MVP_BACKUP_LOG")"
  echo "$line" >>"$MVP_BACKUP_LOG"
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --dry-run)
        DRY_RUN=true
        shift
        ;;
      -h | --help)
        usage
        exit 0
        ;;
      *)
        echo "Unknown option: $1" >&2
        usage
        exit 1
        ;;
    esac
  done
}

read_database_url() {
  local env_file="$MVP_REPO_ROOT/.env"
  if [[ ! -f "$env_file" ]]; then
    echo "Missing .env at $env_file" >&2
    exit 1
  fi

  python3 - "$env_file" <<'PY'
import sys
from urllib.parse import urlparse, unquote

env_file = sys.argv[1]
database_url = None
with open(env_file, encoding="utf-8") as handle:
    for raw_line in handle:
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() != "DATABASE_URL":
            continue
        database_url = value.strip().strip('"').strip("'")
        break

if not database_url:
    raise SystemExit("DATABASE_URL not found in .env")

normalized = database_url.replace("mysql+pymysql://", "mysql://", 1)
parsed = urlparse(normalized)
if parsed.scheme != "mysql" or not parsed.hostname or not parsed.path:
    raise SystemExit("DATABASE_URL is not a valid mysql URL")

username = unquote(parsed.username or "")
password = unquote(parsed.password or "")
hostname = parsed.hostname
port = parsed.port or 3306
database = parsed.path.lstrip("/")
if not username or not database:
    raise SystemExit("DATABASE_URL missing username or database name")

print(username)
print(password)
print(hostname)
print(port)
print(database)
PY
}

cleanup_partial_backup() {
  if [[ "$CREATED_BACKUP_DIR" == true && -n "$BACKUP_DIR" && -d "$BACKUP_DIR" ]]; then
    if [[ "$DRY_RUN" == true ]]; then
      echo "Would remove partial backup directory: $BACKUP_DIR"
    else
      rm -rf "$BACKUP_DIR"
    fi
  fi
}

on_error() {
  local exit_code=$?
  cleanup_partial_backup
  log_message "ERROR" "backup failed for ${BACKUP_DATE:-unknown-date} (exit ${exit_code})"
  exit "$exit_code"
}

ensure_backup_root() {
  if [[ "$DRY_RUN" == true ]]; then
    echo "Would ensure backup root exists: $MVP_BACKUP_ROOT"
    return
  fi
  mkdir -p "$MVP_BACKUP_ROOT"
  chmod 700 "$MVP_BACKUP_ROOT"
}

create_backup_dir() {
  BACKUP_DATE="$(date +%Y-%m-%d)"
  BACKUP_DIR="${MVP_BACKUP_ROOT%/}/${BACKUP_DATE}"
  if [[ "$DRY_RUN" == true ]]; then
    echo "Would create backup directory: $BACKUP_DIR"
    return
  fi
  mkdir -p "$BACKUP_DIR"
  chmod 700 "$BACKUP_DIR"
  CREATED_BACKUP_DIR=true
  umask 077
}

run_mysqldump() {
  local db_user db_pass db_host db_port db_name
  mapfile -t db_parts < <(read_database_url)
  db_user="${db_parts[0]}"
  db_pass="${db_parts[1]}"
  db_host="${db_parts[2]}"
  db_port="${db_parts[3]}"
  db_name="${db_parts[4]}"

  local artifact="$BACKUP_DIR/db.sql.gz"
  local err_file
  err_file="$(mktemp)"
  if [[ "$DRY_RUN" == true ]]; then
    echo "Would mysqldump ${db_name} on ${db_host}:${db_port} -> ${artifact}"
    rm -f "$err_file"
    return
  fi

  # --no-tablespaces: mvpipeline user lacks global PROCESS; without this flag
  # mysqldump still exits 0 but prints a tablespace error to stderr (MySQL 8+).
  if ! MYSQL_PWD="$db_pass" mysqldump \
    --host="$db_host" \
    --port="$db_port" \
    --user="$db_user" \
    --single-transaction \
    --no-tablespaces \
    --routines \
    --triggers \
    "$db_name" 2>"$err_file" | gzip -c >"$artifact"; then
    if [[ -s "$err_file" ]]; then
      cat "$err_file" >&2
    fi
    rm -f "$err_file" "$artifact"
    echo "mysqldump failed for database ${db_name}" >&2
    return 1
  fi
  if [[ -s "$err_file" ]]; then
    cat "$err_file" >&2
    rm -f "$err_file" "$artifact"
    echo "mysqldump reported errors for database ${db_name}" >&2
    return 1
  fi
  rm -f "$err_file"
  chmod 600 "$artifact"
}

archive_output() {
  local artifact="$BACKUP_DIR/output.tar.gz"
  local output_dir="$MVP_REPO_ROOT/output"

  if [[ "$DRY_RUN" == true ]]; then
    if [[ -d "$output_dir" ]]; then
      echo "Would archive output/ -> ${artifact}"
    else
      echo "Would create empty output archive (output/ missing) -> ${artifact}"
    fi
    return
  fi

  if [[ -d "$output_dir" ]]; then
    tar -czf "$artifact" -C "$MVP_REPO_ROOT" output
  else
    tar -czf "$artifact" --files-from /dev/null
    log_message "INFO" "output/ missing; created empty output.tar.gz"
  fi
  chmod 600 "$artifact"
}

copy_env_file() {
  local source="$MVP_REPO_ROOT/.env"
  local artifact="$BACKUP_DIR/.env"

  if [[ "$DRY_RUN" == true ]]; then
    echo "Would copy .env -> ${artifact}"
    return
  fi

  cp "$source" "$artifact"
  chmod 600 "$artifact"
}

archive_workspace() {
  local artifact="$BACKUP_DIR/workspace.tar.gz"

  if [[ "$DRY_RUN" == true ]]; then
    echo "Would archive workspace (excluding output/, venv/, frontend/node_modules/, .git/) -> ${artifact}"
    return
  fi

  tar -czf "$artifact" \
    --exclude='./output' \
    --exclude='./venv' \
    --exclude='./frontend/node_modules' \
    --exclude='./.git' \
    -C "$MVP_REPO_ROOT" .
  chmod 600 "$artifact"
}

prune_old_backups() {
  local cutoff
  local keep_from="$((MVP_RETENTION_DAYS - 1))"
  cutoff="$(date -d "${keep_from} days ago" +%Y-%m-%d)"

  if [[ "$DRY_RUN" == true ]]; then
    echo "Would prune backup folders older than ${cutoff} under ${MVP_BACKUP_ROOT}"
    return
  fi

  shopt -s nullglob
  for dir in "$MVP_BACKUP_ROOT"/*/; do
    local name
    name="$(basename "$dir")"
    if [[ "$name" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]] && [[ "$name" < "$cutoff" ]]; then
      rm -rf "$dir"
      log_message "INFO" "pruned old backup folder ${name}"
    fi
  done
  shopt -u nullglob
}

main() {
  parse_args "$@"
  trap on_error ERR

  ensure_backup_root
  create_backup_dir
  run_mysqldump
  archive_output
  copy_env_file
  archive_workspace

  if [[ "$DRY_RUN" == true ]]; then
    return 0
  fi

  CREATED_BACKUP_DIR=false
  trap - ERR

  prune_old_backups
  log_message "INFO" "backup completed for ${BACKUP_DATE} -> ${BACKUP_DIR}"
}

main "$@"
