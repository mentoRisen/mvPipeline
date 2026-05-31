"""Tests for scripts/backup_local.sh operational backup flow."""

from __future__ import annotations

import os
import stat
import subprocess
import tarfile
from datetime import date, timedelta
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKUP_SCRIPT = REPO_ROOT / "scripts" / "backup_local.sh"


def _run_backup(
    tmp_path: Path,
    *,
    repo_root: Path,
    backup_root: Path | None = None,
    log_path: Path | None = None,
    retention_days: str = "7",
    path_prefix: str | None = None,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["MVP_REPO_ROOT"] = str(repo_root)
    env["MVP_BACKUP_ROOT"] = str(backup_root or tmp_path / "backups")
    env["MVP_BACKUP_LOG"] = str(log_path or tmp_path / "backup.log")
    env["MVP_RETENTION_DAYS"] = retention_days
    if path_prefix is not None:
        env["PATH"] = f"{path_prefix}:{env['PATH']}"
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        ["bash", str(BACKUP_SCRIPT)],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _stub_mysqldump(path: Path) -> None:
    script = path / "mysqldump"
    script.write_text(
        "#!/usr/bin/env bash\n"
        'echo "-- stub mysqldump"\n'
        'echo "CREATE TABLE example (id INT);"\n',
        encoding="utf-8",
    )
    script.chmod(0o755)


def _stub_mysqldump_failing(path: Path) -> None:
    script = path / "mysqldump"
    script.write_text("#!/usr/bin/env bash\nexit 1\n", encoding="utf-8")
    script.chmod(0o755)


def _prepare_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "output").mkdir(parents=True)
    (repo / "output" / "task.txt").write_text("generated", encoding="utf-8")
    (repo / "app").mkdir()
    (repo / "app" / "uncommitted.py").write_text("local edit", encoding="utf-8")
    (repo / "venv").mkdir()
    (repo / "frontend" / "node_modules").mkdir(parents=True)
    (repo / ".env").write_text(
        'DATABASE_URL=mysql+pymysql://mvpipeline:secr%2B%2B%2B@localhost:3306/mvpipeline\n',
        encoding="utf-8",
    )
    return repo


def _backup_dir_for_today(backup_root: Path) -> Path:
    return backup_root / date.today().isoformat()


def test_backup_creates_four_artifacts(tmp_path: Path) -> None:
    """Covers AE1: separate artifacts under dated folder."""
    stubs = tmp_path / "stubs"
    stubs.mkdir()
    _stub_mysqldump(stubs)
    repo = _prepare_repo(tmp_path)
    backup_root = tmp_path / "backups"

    result = _run_backup(tmp_path, repo_root=repo, backup_root=backup_root, path_prefix=str(stubs))

    assert result.returncode == 0, result.stderr
    backup_dir = _backup_dir_for_today(backup_root)
    assert backup_dir.is_dir()
    assert (backup_dir / "db.sql.gz").is_file()
    assert (backup_dir / "output.tar.gz").is_file()
    assert (backup_dir / ".env").is_file()
    assert (backup_dir / "workspace.tar.gz").is_file()


def test_workspace_excludes_output_but_includes_app_changes(tmp_path: Path) -> None:
    """Covers AE2: workspace tar excludes output/ but keeps uncommitted app files."""
    stubs = tmp_path / "stubs"
    stubs.mkdir()
    _stub_mysqldump(stubs)
    repo = _prepare_repo(tmp_path)
    backup_root = tmp_path / "backups"

    result = _run_backup(tmp_path, repo_root=repo, backup_root=backup_root, path_prefix=str(stubs))
    assert result.returncode == 0, result.stderr

    workspace_tar = _backup_dir_for_today(backup_root) / "workspace.tar.gz"
    with tarfile.open(workspace_tar, "r:gz") as archive:
        names = archive.getnames()
    assert not any(
        name.lstrip("./") == "output" or name.lstrip("./").startswith("output/")
        for name in names
    )
    assert any(name.endswith("app/uncommitted.py") for name in names)


def test_retention_keeps_only_newest_seven_folders(tmp_path: Path) -> None:
    """Covers AE3: prune folders older than retention window."""
    stubs = tmp_path / "stubs"
    stubs.mkdir()
    _stub_mysqldump(stubs)
    repo = _prepare_repo(tmp_path)
    backup_root = tmp_path / "backups"
    backup_root.mkdir()

    start = date.today() - timedelta(days=10)
    for offset in range(10):
        folder_name = (start + timedelta(days=offset)).isoformat()
        (backup_root / folder_name).mkdir()
        (backup_root / folder_name / "marker.txt").write_text("old", encoding="utf-8")

    result = _run_backup(
        tmp_path,
        repo_root=repo,
        backup_root=backup_root,
        path_prefix=str(stubs),
        retention_days="7",
    )
    assert result.returncode == 0, result.stderr

    remaining = sorted(path.name for path in backup_root.iterdir() if path.is_dir())
    assert len(remaining) == 7
    cutoff = date.today() - timedelta(days=6)
    for name in remaining:
        assert name >= cutoff.isoformat()


def test_mysqldump_failure_preserves_existing_backups(tmp_path: Path) -> None:
    """Covers AE4: failed run does not prune and removes partial folder."""
    stubs = tmp_path / "stubs"
    stubs.mkdir()
    _stub_mysqldump_failing(stubs)
    repo = _prepare_repo(tmp_path)
    backup_root = tmp_path / "backups"
    existing = backup_root / "2020-01-01"
    existing.mkdir(parents=True)
    (existing / "db.sql.gz").write_text("keep", encoding="utf-8")

    result = _run_backup(tmp_path, repo_root=repo, backup_root=backup_root, path_prefix=str(stubs))

    assert result.returncode != 0
    assert existing.exists()
    assert not _backup_dir_for_today(backup_root).exists()


def test_sensitive_artifacts_are_owner_only(tmp_path: Path) -> None:
    """Covers AE5: db dump and .env copy are not group/world readable."""
    stubs = tmp_path / "stubs"
    stubs.mkdir()
    _stub_mysqldump(stubs)
    repo = _prepare_repo(tmp_path)
    backup_root = tmp_path / "backups"

    result = _run_backup(tmp_path, repo_root=repo, backup_root=backup_root, path_prefix=str(stubs))
    assert result.returncode == 0, result.stderr

    backup_dir = _backup_dir_for_today(backup_root)
    for artifact in (backup_dir / "db.sql.gz", backup_dir / ".env"):
        mode = stat.S_IMODE(artifact.stat().st_mode)
        assert mode & stat.S_IRGRP == 0
        assert mode & stat.S_IROTH == 0


def test_missing_output_directory_still_succeeds(tmp_path: Path) -> None:
    """Edge case: missing output/ creates empty archive without failing."""
    stubs = tmp_path / "stubs"
    stubs.mkdir()
    _stub_mysqldump(stubs)
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app").mkdir()
    (repo / ".env").write_text(
        "DATABASE_URL=mysql+pymysql://user:pass@localhost:3306/mvpipeline\n",
        encoding="utf-8",
    )
    backup_root = tmp_path / "backups"

    result = _run_backup(tmp_path, repo_root=repo, backup_root=backup_root, path_prefix=str(stubs))

    assert result.returncode == 0, result.stderr
    output_tar = _backup_dir_for_today(backup_root) / "output.tar.gz"
    assert output_tar.is_file()
    with tarfile.open(output_tar, "r:gz") as archive:
        assert archive.getmembers() == []


@pytest.mark.skipif(not BACKUP_SCRIPT.is_file(), reason="backup script missing")
def test_dry_run_does_not_write_artifacts(tmp_path: Path) -> None:
    repo = _prepare_repo(tmp_path)
    backup_root = tmp_path / "backups"
    env = os.environ.copy()
    env.update(
        {
            "MVP_REPO_ROOT": str(repo),
            "MVP_BACKUP_ROOT": str(backup_root),
            "MVP_BACKUP_LOG": str(tmp_path / "backup.log"),
        }
    )
    result = subprocess.run(
        ["bash", str(BACKUP_SCRIPT), "--dry-run"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "Would mysqldump" in result.stdout
    assert not backup_root.exists() or list(backup_root.iterdir()) == []
