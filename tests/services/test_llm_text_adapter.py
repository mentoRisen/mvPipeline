from __future__ import annotations

import json

import pytest
import requests

from app.services.integrations.llm_text_adapter import (
    OpenAITextDraftAdapter,
    TextDraftRefusalError,
    TextDraftUpstreamError,
)


class FakeResponse:
    def __init__(self, payload=None, *, status_error: Exception | None = None):
        self.payload = payload
        self.status_error = status_error

    def raise_for_status(self):
        if self.status_error:
            raise self.status_error

    def json(self):
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


class FakeSession:
    def __init__(self, result):
        self.result = result

    def post(self, *args, **kwargs):
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def build_adapter(result, *, api_key="test-key"):
    return OpenAITextDraftAdapter(
        api_key=api_key,
        session=FakeSession(result),
        model="fake-model",
        api_url="https://example.test/v1/chat/completions",
        timeout_seconds=5,
        max_bundle_items=12,
    )


def _prompt_kwargs():
    return {
        "master_prompt_text": "Generate instagram_post drafts.",
        "creation_prompt_text": "Create a launch post",
        "tenant_context": {"name": "Acme"},
    }


def test_build_preview_messages_uses_master_and_creation():
    adapter = build_adapter(FakeResponse({}))
    messages = adapter.build_preview_messages(
        master_prompt_text="System rules",
        creation_prompt_text="User campaign",
        tenant_context={"name": "Acme"},
    )
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == "System rules"
    assert messages[1]["role"] == "user"
    assert "User campaign" in messages[1]["content"]


def test_complete_preview_chat_uses_json_schema_format():
    captured = {}

    class CapturingSession(FakeSession):
        def post(self, *args, **kwargs):
            captured.update(kwargs.get("json") or {})
            return FakeResponse(
                {
                    "choices": [
                        {"message": {"content": '{"items":[]}'}}
                    ]
                }
            )

    adapter = OpenAITextDraftAdapter(
        api_key="test-key",
        session=CapturingSession(None),
        model="fake-model",
        api_url="https://example.test/v1/chat/completions",
    )
    adapter.complete_preview_chat(
        [{"role": "user", "content": "hi"}],
        max_tasks=3,
        max_jobs=5,
    )
    assert captured["response_format"]["type"] == "json_schema"
    schema = captured["response_format"]["json_schema"]["schema"]
    assert schema["properties"]["items"]["maxItems"] == 3
    assert (
        schema["properties"]["items"]["items"]["properties"]["jobs"]["maxItems"] == 5
    )


def test_adapter_requires_api_key():
    adapter = build_adapter(FakeResponse({}), api_key=None)

    with pytest.raises(TextDraftUpstreamError):
        adapter.generate_campaign_draft(**_prompt_kwargs())


def test_adapter_maps_timeout_errors():
    adapter = build_adapter(requests.Timeout("slow"))

    with pytest.raises(TextDraftUpstreamError):
        adapter.generate_campaign_draft(**_prompt_kwargs())


def test_adapter_maps_refusals():
    adapter = build_adapter(
        FakeResponse(
            {
                "choices": [
                    {
                        "message": {
                            "refusal": "unsafe",
                        }
                    }
                ]
            }
        )
    )

    with pytest.raises(TextDraftRefusalError):
        adapter.generate_campaign_draft(**_prompt_kwargs())


def test_adapter_rejects_non_json_content():
    adapter = build_adapter(
        FakeResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": "not json",
                        }
                    }
                ]
            }
        )
    )

    with pytest.raises(TextDraftUpstreamError):
        adapter.generate_campaign_draft(**_prompt_kwargs())


def test_adapter_accepts_list_shaped_content():
    payload = {
        "items": [
            {
                "task": {
                    "name": "Launch post",
                    "template": "instagram_post",
                    "meta": {"theme": "launch"},
                    "post": {"caption": "Hello world"},
                },
                "jobs": [
                    {
                        "generator": "dalle",
                        "purpose": "imagecontent",
                        "prompt": {"prompt": "launch visual"},
                        "order": 0,
                    }
                ],
            }
        ]
    }
    adapter = build_adapter(
        FakeResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": [
                                {
                                    "type": "output_text",
                                    "text": json.dumps(payload),
                                }
                            ],
                        }
                    }
                ]
            }
        )
    )

    result = adapter.generate_campaign_draft(**_prompt_kwargs())

    assert result["items"][0]["task"]["template"] == "instagram_post"
