from __future__ import annotations

import json

import pytest

from app.models.ai_draft_communication_event import (
    AiDraftCommunicationEvent,
    AiDraftCommunicationKind,
)
from app.services.ai_draft_conversation import (
    build_follow_up_messages_from_events,
    build_initial_preview_messages,
)


def test_build_initial_preview_messages():
    messages = build_initial_preview_messages(
        master_prompt_text="System",
        creation_prompt_text="Create posts",
        tenant_context={"name": "Acme"},
    )
    assert messages[0] == {"role": "system", "content": "System"}
    user = json.loads(messages[1]["content"])
    assert user["creation_prompt"] == "Create posts"
    assert user["tenant_context"]["name"] == "Acme"


def test_build_follow_up_appends_assistant_and_user():
    events = [
        AiDraftCommunicationEvent(
            draft_session_id=None,
            sequence=0,
            kind=AiDraftCommunicationKind.PROMPT_TO_AI.value,
            payload={
                "messages": [
                    {"role": "system", "content": "S"},
                    {"role": "user", "content": "U1"},
                ]
            },
        ),
        AiDraftCommunicationEvent(
            draft_session_id=None,
            sequence=1,
            kind=AiDraftCommunicationKind.RESPONSE_FROM_AI.value,
            payload={"content": '{"items":[]}'},
        ),
    ]
    out = build_follow_up_messages_from_events(
        events,
        instruction_text="Make it playful",
        iteration_mode="regenerate",
        target_scope="campaign",
    )
    assert out[-2]["role"] == "assistant"
    assert out[-1]["role"] == "user"
    assert "playful" in out[-1]["content"]


def test_build_follow_up_requires_prior_prompt():
    with pytest.raises(ValueError, match="prompt_to_ai"):
        build_follow_up_messages_from_events(
            [],
            instruction_text="x",
        )
