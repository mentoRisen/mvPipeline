"""Build public HTTP URLs for generated files served from this host."""

from __future__ import annotations

import os


def construct_public_url(public_url_base: str, image_path: str) -> str:
    """Join PUBLIC_URL base with a relative image path (e.g. /output/...)."""
    base = str(public_url_base).rstrip("/")
    path = str(image_path).lstrip("/")
    return f"{base}/{path}"


def public_url_for_image_path(
    image_path: str,
    *,
    public_url_base: str | None = None,
) -> str | None:
    """Return the public URL for a local output path, or None if PUBLIC_URL is unset."""
    base = public_url_base or os.getenv("PUBLIC_URL")
    if not base or not image_path:
        return None
    return construct_public_url(base, image_path)
