from __future__ import annotations

from app.services.public_url import construct_public_url, public_url_for_image_path


def test_public_url_for_image_path_uses_env(monkeypatch) -> None:
    monkeypatch.setenv("PUBLIC_URL", "https://flow.mentoverse.eu/")
    assert public_url_for_image_path("/output/t/j.jpeg") == (
        "https://flow.mentoverse.eu/output/t/j.jpeg"
    )


def test_public_url_for_image_path_returns_none_without_base(monkeypatch) -> None:
    monkeypatch.delenv("PUBLIC_URL", raising=False)
    assert public_url_for_image_path("/output/t/j.jpeg") is None


def test_construct_public_url_explicit_base() -> None:
    assert construct_public_url("https://example.com", "output/a.jpg") == (
        "https://example.com/output/a.jpg"
    )
