from __future__ import annotations

import pytest

import app.config as app_config
from app.services.integrations.runway_config import resolve_runway_api_key


def test_resolve_runway_api_key_prefers_tenant_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(app_config, "RUNWAY_API_KEY", "global-key")
    monkeypatch.delenv("RUNWAY_API_KEY", raising=False)

    assert (
        resolve_runway_api_key(tenant_env={"RUNWAY_API_KEY": "tenant-key"})
        == "tenant-key"
    )


def test_resolve_runway_api_key_falls_back_to_global_config(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(app_config, "RUNWAY_API_KEY", "global-key")
    monkeypatch.delenv("RUNWAY_API_KEY", raising=False)

    assert resolve_runway_api_key(tenant_env={}) == "global-key"


def test_resolve_runway_api_key_falls_back_to_os_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(app_config, "RUNWAY_API_KEY", None)
    monkeypatch.setenv("RUNWAY_API_KEY", "env-key")

    assert resolve_runway_api_key() == "env-key"


def test_resolve_runway_api_key_missing_raises(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(app_config, "RUNWAY_API_KEY", None)
    monkeypatch.delenv("RUNWAY_API_KEY", raising=False)

    with pytest.raises(ValueError, match="RUNWAY_API_KEY not set"):
        resolve_runway_api_key(tenant_env={})
