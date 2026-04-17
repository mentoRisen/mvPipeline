from __future__ import annotations

import json

from app.services import ai_draft_session_repo
from app.services.ai_draft_preview_runner import run_ai_draft_preview_job
from app.services.integrations.llm_text_adapter import OpenAITextDraftAdapter


def _bundle(name: str) -> dict:
    return {
        "items": [
            {
                "task": {
                    "name": name,
                    "template": "instagram_post",
                    "meta": {},
                    "post": {"caption": "x"},
                },
                "jobs": [
                    {
                        "generator": "dalle",
                        "purpose": "imagecontent",
                        "prompt": {"prompt": "x"},
                        "order": 0,
                    }
                ],
                "warnings": [],
            }
        ]
    }


def test_runner_failure_preserves_previous_bundle(tenant, auth_user, monkeypatch):
    sid = ai_draft_session_repo.save_after_preview(
        tenant_id=tenant.id,
        user_id=auth_user.id,
        brief="first",
        items=_bundle("Before")["items"],
    )
    ai_draft_session_repo.start_preview_run(
        tenant_id=tenant.id,
        user_id=auth_user.id,
        brief="rerun",
        draft_session_id=sid,
    )

    def _raise_upstream(self, _messages):
        raise RuntimeError("Authorization: Bearer super-secret")

    monkeypatch.setattr(OpenAITextDraftAdapter, "complete_preview_chat", _raise_upstream)
    run_ai_draft_preview_job(
        draft_session_id=sid,
        tenant_id=tenant.id,
        user_id=auth_user.id,
        brief="rerun",
        iteration_mode="regenerate",
        instruction_text="refresh",
        target_scope="campaign",
    )
    row = ai_draft_session_repo.get_active_for_user(
        sid,
        tenant_id=tenant.id,
        user_id=auth_user.id,
    )
    assert row is not None
    assert row.bundle["items"][0]["task"]["name"] == "Before"
    events = ai_draft_session_repo.list_communication_events(
        draft_session_id=sid, tenant_id=tenant.id, user_id=auth_user.id
    )
    assert any(ev.kind == "error" for ev in events)


def test_runner_success_appends_round_events(tenant, auth_user, monkeypatch):
    monkeypatch.setattr(
        OpenAITextDraftAdapter,
        "complete_preview_chat",
        lambda self, _messages: json.dumps(_bundle("After")),
    )
    sid = ai_draft_session_repo.start_preview_run(
        tenant_id=tenant.id,
        user_id=auth_user.id,
        brief="first",
    )
    run_ai_draft_preview_job(
        draft_session_id=sid,
        tenant_id=tenant.id,
        user_id=auth_user.id,
        brief="first",
    )
    ai_draft_session_repo.start_preview_run(
        tenant_id=tenant.id,
        user_id=auth_user.id,
        brief="second",
        draft_session_id=sid,
    )
    run_ai_draft_preview_job(
        draft_session_id=sid,
        tenant_id=tenant.id,
        user_id=auth_user.id,
        brief="second",
        iteration_mode="targeted_intent",
        instruction_text="improve tone",
        target_scope="campaign",
    )
    events = ai_draft_session_repo.list_communication_events(
        draft_session_id=sid, tenant_id=tenant.id, user_id=auth_user.id
    )
    assert len(events) >= 6
    assert any(ev.kind == "response_from_ai" for ev in events)
    user_inputs = [ev for ev in events if ev.kind == "user_input"]
    assert user_inputs
    assert user_inputs[-1].payload.get("iteration_mode") == "targeted_intent"
