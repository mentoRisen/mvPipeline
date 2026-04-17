from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi import HTTPException

from app.models.ai_draft_session import AiDraftSession, AiDraftSessionStatus
from app.models.user import User
from app.services import ai_draft_session_repo


def test_save_after_preview_creates_row(tenant, auth_user, db_session):
    sid = ai_draft_session_repo.save_after_preview(
        tenant_id=tenant.id,
        user_id=auth_user.id,
        brief="hello",
        items=[
            {
                "task": {
                    "name": "T1",
                    "template": "instagram_post",
                    "meta": {},
                    "post": {},
                },
                "jobs": [
                    {
                        "generator": "dalle",
                        "purpose": None,
                        "prompt": {"prompt": "x"},
                        "order": 0,
                    }
                ],
                "warnings": [],
            }
        ],
    )
    row = db_session.get(AiDraftSession, sid)
    assert row is not None
    assert row.brief == "hello"
    assert row.status == AiDraftSessionStatus.ACTIVE
    assert len(row.bundle["items"]) == 1


def test_save_after_preview_updates_existing(tenant, auth_user, db_session):
    sid = ai_draft_session_repo.save_after_preview(
        tenant_id=tenant.id,
        user_id=auth_user.id,
        brief="first",
        items=[
            {
                "task": {
                    "name": "A",
                    "template": "instagram_post",
                    "meta": {},
                    "post": {},
                },
                "jobs": [
                    {
                        "generator": "dalle",
                        "purpose": None,
                        "prompt": {"prompt": "x"},
                        "order": 0,
                    }
                ],
                "warnings": [],
            }
        ],
    )
    ai_draft_session_repo.save_after_preview(
        tenant_id=tenant.id,
        user_id=auth_user.id,
        brief="second",
        items=[
            {
                "task": {
                    "name": "B",
                    "template": "instagram_post",
                    "meta": {},
                    "post": {},
                },
                "jobs": [
                    {
                        "generator": "dalle",
                        "purpose": None,
                        "prompt": {"prompt": "y"},
                        "order": 0,
                    }
                ],
                "warnings": [],
            }
        ],
        draft_session_id=sid,
    )
    row = db_session.get(AiDraftSession, sid)
    assert row.brief == "second"
    assert row.bundle["items"][0]["task"]["name"] == "B"


def test_list_active_excludes_expired(tenant, auth_user, db_session):
    from datetime import datetime

    sid = ai_draft_session_repo.save_after_preview(
        tenant_id=tenant.id,
        user_id=auth_user.id,
        brief="old",
        items=[
            {
                "task": {
                    "name": "A",
                    "template": "instagram_post",
                    "meta": {},
                    "post": {},
                },
                "jobs": [
                    {
                        "generator": "dalle",
                        "purpose": None,
                        "prompt": {"prompt": "x"},
                        "order": 0,
                    }
                ],
                "warnings": [],
            }
        ],
    )
    row = db_session.get(AiDraftSession, sid)
    row.expires_at = datetime.utcnow() - timedelta(days=1)
    db_session.add(row)
    db_session.commit()

    listed = ai_draft_session_repo.list_active_for_user(
        tenant_id=tenant.id, user_id=auth_user.id
    )
    assert listed == []


def test_get_active_wrong_user_returns_none(tenant, auth_user, db_session):
    other = User(username="other", hashed_password="x", is_active=True)
    db_session.add(other)
    db_session.commit()
    db_session.refresh(other)

    sid = ai_draft_session_repo.save_after_preview(
        tenant_id=tenant.id,
        user_id=auth_user.id,
        brief="x",
        items=[
            {
                "task": {
                    "name": "A",
                    "template": "instagram_post",
                    "meta": {},
                    "post": {},
                },
                "jobs": [
                    {
                        "generator": "dalle",
                        "purpose": None,
                        "prompt": {"prompt": "x"},
                        "order": 0,
                    }
                ],
                "warnings": [],
            }
        ],
    )
    assert (
        ai_draft_session_repo.get_active_for_user(
            sid, tenant_id=tenant.id, user_id=other.id
        )
        is None
    )


def test_mark_completed_makes_session_invisible(tenant, auth_user, db_session):
    sid = ai_draft_session_repo.save_after_preview(
        tenant_id=tenant.id,
        user_id=auth_user.id,
        brief="x",
        items=[
            {
                "task": {
                    "name": "A",
                    "template": "instagram_post",
                    "meta": {},
                    "post": {},
                },
                "jobs": [
                    {
                        "generator": "dalle",
                        "purpose": None,
                        "prompt": {"prompt": "x"},
                        "order": 0,
                    }
                ],
                "warnings": [],
            }
        ],
    )
    ai_draft_session_repo.mark_completed(
        session_id=sid, tenant_id=tenant.id, user_id=auth_user.id
    )
    assert (
        ai_draft_session_repo.get_active_for_user(
            sid, tenant_id=tenant.id, user_id=auth_user.id
        )
        is None
    )
    row = db_session.get(AiDraftSession, sid)
    assert row.status == AiDraftSessionStatus.COMPLETED


def test_start_preview_run_rejects_new_session_when_cap_reached(
    tenant, auth_user, monkeypatch
):
    monkeypatch.setattr(ai_draft_session_repo, "AI_DRAFT_SESSION_MAX_PER_USER", 1)
    first = ai_draft_session_repo.start_preview_run(
        tenant_id=tenant.id,
        user_id=auth_user.id,
        brief="first",
    )
    assert first is not None

    try:
        ai_draft_session_repo.start_preview_run(
            tenant_id=tenant.id,
            user_id=auth_user.id,
            brief="second",
        )
        assert False, "Expected cap enforcement HTTPException"
    except HTTPException as exc:
        assert exc.status_code == 409
        assert isinstance(exc.detail, dict)
        assert exc.detail.get("error") == "ai_draft_session_limit_reached"


def test_start_preview_run_rerun_allowed_at_cap(
    tenant, auth_user, monkeypatch, db_session
):
    monkeypatch.setattr(ai_draft_session_repo, "AI_DRAFT_SESSION_MAX_PER_USER", 1)
    sid = ai_draft_session_repo.start_preview_run(
        tenant_id=tenant.id,
        user_id=auth_user.id,
        brief="first",
    )
    row = db_session.get(AiDraftSession, sid)
    row.preview_status = "succeeded"
    db_session.add(row)
    db_session.commit()

    same_sid = ai_draft_session_repo.start_preview_run(
        tenant_id=tenant.id,
        user_id=auth_user.id,
        brief="updated brief",
        draft_session_id=sid,
    )
    assert same_sid == sid


def test_finalize_preview_failure_preserves_existing_bundle(tenant, auth_user):
    sid = ai_draft_session_repo.save_after_preview(
        tenant_id=tenant.id,
        user_id=auth_user.id,
        brief="keep me",
        items=[
            {
                "task": {
                    "name": "A",
                    "template": "instagram_post",
                    "meta": {},
                    "post": {},
                },
                "jobs": [
                    {
                        "generator": "dalle",
                        "purpose": None,
                        "prompt": {"prompt": "x"},
                        "order": 0,
                    }
                ],
                "warnings": [],
            }
        ],
    )
    ai_draft_session_repo.start_preview_run(
        tenant_id=tenant.id,
        user_id=auth_user.id,
        brief="rerun",
        draft_session_id=sid,
    )
    ai_draft_session_repo.finalize_preview_failure(
        draft_session_id=sid,
        tenant_id=tenant.id,
        user_id=auth_user.id,
        last_error={"error": "upstream", "access_token": "secret-value"},
    )
    row = ai_draft_session_repo.get_active_for_user(
        sid,
        tenant_id=tenant.id,
        user_id=auth_user.id,
    )
    assert row is not None
    assert row.bundle["items"][0]["task"]["name"] == "A"
    assert row.last_error["access_token"] == "***redacted***"


def test_finalize_preview_success_creates_undo_snapshot(tenant, auth_user):
    sid = ai_draft_session_repo.save_after_preview(
        tenant_id=tenant.id,
        user_id=auth_user.id,
        brief="first",
        items=[
            {
                "task": {
                    "name": "Before",
                    "template": "instagram_post",
                    "meta": {},
                    "post": {},
                },
                "jobs": [
                    {
                        "generator": "dalle",
                        "purpose": None,
                        "prompt": {"prompt": "x"},
                        "order": 0,
                    }
                ],
                "warnings": [],
            }
        ],
    )
    ai_draft_session_repo.start_preview_run(
        tenant_id=tenant.id,
        user_id=auth_user.id,
        brief="second",
        draft_session_id=sid,
    )
    ai_draft_session_repo.finalize_preview_success(
        draft_session_id=sid,
        tenant_id=tenant.id,
        user_id=auth_user.id,
        items=[
            {
                "task": {
                    "name": "After",
                    "template": "instagram_post",
                    "meta": {},
                    "post": {},
                },
                "jobs": [
                    {
                        "generator": "dalle",
                        "purpose": None,
                        "prompt": {"prompt": "y"},
                        "order": 0,
                    }
                ],
                "warnings": [],
            }
        ],
    )
    snaps = ai_draft_session_repo.list_revision_snapshots(
        draft_session_id=sid,
        tenant_id=tenant.id,
        user_id=auth_user.id,
    )
    assert len(snaps) >= 1
    assert snaps[0].bundle["items"][0]["task"]["name"] == "Before"


def test_restore_snapshot_bundle_rejects_when_running(tenant, auth_user):
    sid = ai_draft_session_repo.start_preview_run(
        tenant_id=tenant.id,
        user_id=auth_user.id,
        brief="running",
    )
    with pytest.raises(HTTPException) as exc:
        ai_draft_session_repo.restore_snapshot_bundle(
            draft_session_id=sid,
            snapshot_id=1,
            tenant_id=tenant.id,
            user_id=auth_user.id,
        )
    assert exc.value.status_code == 409


def test_restore_snapshot_bundle_missing_snapshot_404(tenant, auth_user):
    sid = ai_draft_session_repo.save_after_preview(
        tenant_id=tenant.id,
        user_id=auth_user.id,
        brief="first",
        items=[
            {
                "task": {
                    "name": "A",
                    "template": "instagram_post",
                    "meta": {},
                    "post": {},
                },
                "jobs": [
                    {
                        "generator": "dalle",
                        "purpose": None,
                        "prompt": {"prompt": "x"},
                        "order": 0,
                    }
                ],
                "warnings": [],
            }
        ],
    )
    with pytest.raises(HTTPException) as exc:
        ai_draft_session_repo.restore_snapshot_bundle(
            draft_session_id=sid,
            snapshot_id=99999,
            tenant_id=tenant.id,
            user_id=auth_user.id,
        )
    assert exc.value.status_code == 404
