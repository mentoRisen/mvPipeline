"""FTP upload service for making files publicly available.

This module exposes a single function:

    uploadToPublic(relativeUrlForFile: str) -> str

The function:
- Reads FTP credentials and configuration from environment variables:
    - PUBLIC_FTP_USER
    - PUBLIC_FTP_PASSWORD
    - PUBLIC_FTP_FOLDER  (remote base folder on the FTP server)
    - PUBLIC_URL         (public HTTP(S) base URL)
- Uploads the local file located at ``relativeUrlForFile`` (relative to the
  project root directory) to the configured FTP folder, preserving the same
  relative path on the remote.
- Returns the public URL for the uploaded file, which is simply:
    PUBLIC_URL + relativeUrlForFile
"""

from __future__ import annotations

import os
import posixpath
from ftplib import FTP
from pathlib import Path
from typing import Final
from urllib.parse import urlparse


def _get_project_root() -> Path:
    """Return the project root directory (repository root)."""
    # This file lives at app/services/ftpupload.py
    # project_root = .../mvPipeline
    return Path(__file__).resolve().parents[2]


def _get_env_required(name: str) -> str:
    """Get a required environment variable or raise a clear error."""
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Environment variable {name} is required but not set")
    return value


def _ensure_remote_directories(ftp: FTP, remote_dir: str) -> None:
    """Create remote directories on the FTP server if they don't exist.

    This walks each path component and attempts to ``cwd`` into it,
    creating it with ``mkd`` when necessary.
    """
    if not remote_dir or remote_dir == "/":
        return

    # Normalize to POSIX-style path and split into components
    parts = [p for p in remote_dir.split("/") if p]
    for part in parts:
        try:
            ftp.cwd(part)
        except Exception:
            # Directory does not exist; create it then change into it
            ftp.mkd(part)
            ftp.cwd(part)


def uploadToPublic(relativeUrlForFile: str) -> str:
    """Upload a file to the public FTP and return its public URL.

    Args:
        relativeUrlForFile: Path to the file relative to the project root,
            e.g. ``\"images/output.png\"``.

    Returns:
        The public URL as ``PUBLIC_URL + relativeUrlForFile``.

    Raises:
        RuntimeError: If required environment variables are missing or FTP fails.
        FileNotFoundError: If the local file does not exist.
    """
    if not relativeUrlForFile:
        raise ValueError("relativeUrlForFile must be a non-empty string")

    # Always treat the input as a *relative* path:
    # if it starts with "/", strip it so it is relative to project root.
    relative_normalized = relativeUrlForFile.lstrip("/")

    project_root: Final[Path] = _get_project_root()
    local_path = (project_root / relative_normalized).resolve()

    if not local_path.is_file():
        raise FileNotFoundError(f"Local file not found: {local_path}")

    # Environment configuration
    ftp_user = _get_env_required("PUBLIC_FTP_USER")
    ftp_password = _get_env_required("PUBLIC_FTP_PASSWORD")
    ftp_folder = _get_env_required("PUBLIC_FTP_FOLDER")
    public_url_base = _get_env_required("PUBLIC_URL")

    # Derive FTP host from PUBLIC_URL (hostname part)
    parsed = urlparse(public_url_base)
    if not parsed.hostname:
        raise RuntimeError(
            "Could not derive FTP host from PUBLIC_URL; "
            "ensure PUBLIC_URL is a valid URL like 'https://example.com/public/'"
        )
    ftp_host = parsed.hostname

    # Compute remote path: PUBLIC_FTP_FOLDER + relative_normalized
    # Use POSIX-style paths for FTP regardless of OS.
    ftp_folder_normalized = ftp_folder.strip().rstrip("/")
    remote_path = (
        relative_normalized
        if not ftp_folder_normalized
        else posixpath.join(ftp_folder_normalized, relative_normalized)
    )

    remote_dir = posixpath.dirname(remote_path)
    remote_filename = posixpath.basename(remote_path)

    # Perform FTP upload
    ftp = FTP(ftp_host)
    try:
        ftp.login(user=ftp_user, passwd=ftp_password)

        # Ensure base folder exists and change into it
        if ftp_folder_normalized:
            _ensure_remote_directories(ftp, ftp_folder_normalized)
            ftp.cwd("/")  # reset to root before walking full remote_dir below

        # Ensure full path exists and change into the directory of the file
        if remote_dir and remote_dir != ".":
            _ensure_remote_directories(ftp, remote_dir)

        with local_path.open("rb") as f:
            ftp.storbinary(f"STOR {remote_filename}", f)
    finally:
        try:
            ftp.quit()
        except Exception:
            # Ignore errors on quit/close
            pass

    # Build public URL to return
    public_url = public_url_base.rstrip("/") + "/" + relative_normalized
    return public_url


__all__ = ["uploadToPublic"]

