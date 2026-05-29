from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.services.public_url import construct_public_url
from app.services.tasks.publisher_instagram import (
    _instagram_api_error,
    resolve_image_url,
)


def test_construct_public_url_joins_base_and_path() -> None:
    assert construct_public_url(
        "https://flow.mentoverse.eu/",
        "/output/task/job.jpeg",
    ) == "https://flow.mentoverse.eu/output/task/job.jpeg"


def test_resolve_image_url_uses_public_url_and_image_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = "https://flow.mentoverse.eu/output/task/job.jpeg"
    monkeypatch.setattr(
        "app.services.tasks.publisher_instagram._is_url_reachable",
        lambda url, **_kwargs: url == expected,
    )

    result = resolve_image_url(
        {
            "public_url": "https://mentoverse.eu/output/task/job.jpeg",
            "image_path": "/output/task/job.jpeg",
        },
        "https://flow.mentoverse.eu/",
    )
    assert result == expected


def test_resolve_image_url_ignores_stale_stored_public_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.tasks.publisher_instagram._is_url_reachable",
        lambda url, **_kwargs: "flow.mentoverse.eu" in url,
    )

    result = resolve_image_url(
        {
            "public_url": "https://mentoverse.eu/output/task/job.jpeg",
            "image_path": "/output/task/job.jpeg",
        },
        "https://flow.mentoverse.eu/",
    )
    assert result == "https://flow.mentoverse.eu/output/task/job.jpeg"


def test_resolve_image_url_returns_none_when_unreachable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.tasks.publisher_instagram._is_url_reachable",
        lambda *_args, **_kwargs: False,
    )

    assert (
        resolve_image_url(
            {"image_path": "/output/task/job.jpeg"},
            "https://flow.mentoverse.eu/",
        )
        is None
    )


def test_instagram_api_error_extracts_graph_message() -> None:
    response = MagicMock()
    response.status_code = 400
    response.json.return_value = {
        "error": {
            "message": "Only photo or video can be accepted as media type.",
            "code": 100,
            "error_subcode": 33,
        }
    }
    assert "Only photo or video" in _instagram_api_error(response)
    assert "code=100" in _instagram_api_error(response)
