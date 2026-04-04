from __future__ import annotations

from datetime import timedelta

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
