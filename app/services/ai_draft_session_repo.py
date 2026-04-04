"""Persistence for AI draft sessions (tenant + user scoped)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlmodel import Session, select

from app.config import (
    AI_DRAFT_SESSION_MAX_BUNDLE_BYTES,
    AI_DRAFT_SESSION_MAX_PER_USER,
    AI_DRAFT_SESSION_TTL_DAYS,
)
from app.db.engine import engine
from app.models.ai_draft_session import AiDraftSession, AiDraftSessionStatus


def _utcnow() -> datetime:
    return datetime.utcnow()


def _default_expires_at() -> datetime:
    return _utcnow() + timedelta(days=AI_DRAFT_SESSION_TTL_DAYS)


def bundle_dict_from_items(items: list[dict[str, Any]]) -> dict[str, Any]:
    return {"items": items}


def assert_bundle_within_size(bundle: dict[str, Any]) -> None:
    raw = json.dumps(bundle, default=str).encode("utf-8")
    if len(raw) > AI_DRAFT_SESSION_MAX_BUNDLE_BYTES:
        raise HTTPException(
            status_code=422,
            detail="AI draft bundle exceeds maximum stored size",
        )


def _trim_oldest_active_sessions(
    session: Session,
    *,
    tenant_id: UUID,
    user_id: UUID,
    slots_needed: int,
) -> None:
    """Drop oldest active sessions until ``cap - slots_needed`` remain (room for new row)."""

    if slots_needed <= 0:
        return
    target = AI_DRAFT_SESSION_MAX_PER_USER - slots_needed
    now = _utcnow()
    while True:
        q = (
            select(AiDraftSession)
            .where(
                AiDraftSession.tenant_id == tenant_id,
                AiDraftSession.user_id == user_id,
                AiDraftSession.status == AiDraftSessionStatus.ACTIVE,
                AiDraftSession.expires_at > now,
            )
            .order_by(AiDraftSession.updated_at.asc())
        )
        actives = list(session.exec(q).all())
        if len(actives) <= target:
            return
        session.delete(actives[0])
        session.commit()


def get_active_for_user(
    session_id: UUID,
    *,
    tenant_id: UUID,
    user_id: UUID,
) -> Optional[AiDraftSession]:
    """Load session if it exists, matches scope, is ACTIVE, and is non-expired."""
    now = _utcnow()
    with Session(engine) as session:
        row = session.get(AiDraftSession, session_id)
        if row is None:
            return None
        if row.tenant_id != tenant_id or row.user_id != user_id:
            return None
        if row.expires_at <= now:
            return None
        if row.status != AiDraftSessionStatus.ACTIVE:
            return None
        return row


def list_active_for_user(
    *,
    tenant_id: UUID,
    user_id: UUID,
    limit: int = 50,
) -> list[AiDraftSession]:
    now = _utcnow()
    with Session(engine) as session:
        q = (
            select(AiDraftSession)
            .where(
                AiDraftSession.tenant_id == tenant_id,
                AiDraftSession.user_id == user_id,
                AiDraftSession.status == AiDraftSessionStatus.ACTIVE,
                AiDraftSession.expires_at > now,
            )
            .order_by(AiDraftSession.updated_at.desc())
            .limit(limit)
        )
        return list(session.exec(q).all())


def save_after_preview(
    *,
    tenant_id: UUID,
    user_id: UUID,
    brief: str,
    items: list[dict[str, Any]],
    draft_session_id: Optional[UUID] = None,
) -> UUID:
    """Create or update a draft session after a successful AI preview."""

    bundle = bundle_dict_from_items(items)
    assert_bundle_within_size(bundle)
    now = _utcnow()
    exp = _default_expires_at()

    with Session(engine) as session:
        if draft_session_id is not None:
            row = session.get(AiDraftSession, draft_session_id)
            if (
                row is None
                or row.tenant_id != tenant_id
                or row.user_id != user_id
                or row.status != AiDraftSessionStatus.ACTIVE
                or row.expires_at <= now
            ):
                raise HTTPException(status_code=404, detail="AI draft session not found")
            row.brief = brief
            row.bundle = bundle
            row.last_error = None
            row.expires_at = exp
            row.updated_at = now
            session.add(row)
            session.commit()
            session.refresh(row)
            return row.id

        _trim_oldest_active_sessions(
            session,
            tenant_id=tenant_id,
            user_id=user_id,
            slots_needed=1,
        )
        row = AiDraftSession(
            tenant_id=tenant_id,
            user_id=user_id,
            brief=brief,
            bundle=bundle,
            last_error=None,
            status=AiDraftSessionStatus.ACTIVE,
            expires_at=exp,
            created_at=now,
            updated_at=now,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return row.id


def patch_session_bundle(
    *,
    session_id: UUID,
    tenant_id: UUID,
    user_id: UUID,
    brief: Optional[str],
    items: Optional[list[dict[str, Any]]],
) -> AiDraftSession:
    """Replace bundle (and optional brief) for autosave."""

    if items is None and brief is None:
        raise HTTPException(status_code=422, detail="Nothing to update")

    now = _utcnow()
    with Session(engine) as session:
        row = session.get(AiDraftSession, session_id)
        if (
            row is None
            or row.tenant_id != tenant_id
            or row.user_id != user_id
            or row.status != AiDraftSessionStatus.ACTIVE
            or row.expires_at <= now
        ):
            raise HTTPException(status_code=404, detail="AI draft session not found")

        if items is not None:
            bundle = bundle_dict_from_items(items)
            assert_bundle_within_size(bundle)
            row.bundle = bundle
        if brief is not None:
            row.brief = brief
        row.last_error = None
        row.expires_at = _default_expires_at()
        row.updated_at = now
        session.add(row)
        session.commit()
        session.refresh(row)
        return row


def mark_completed(*, session_id: UUID, tenant_id: UUID, user_id: UUID) -> None:
    now = _utcnow()
    with Session(engine) as session:
        row = session.get(AiDraftSession, session_id)
        if (
            row is None
            or row.tenant_id != tenant_id
            or row.user_id != user_id
            or row.status != AiDraftSessionStatus.ACTIVE
        ):
            raise HTTPException(status_code=404, detail="AI draft session not found")
        row.status = AiDraftSessionStatus.COMPLETED
        row.updated_at = now
        row.last_error = None
        session.add(row)
        session.commit()


def mark_discarded(*, session_id: UUID, tenant_id: UUID, user_id: UUID) -> None:
    now = _utcnow()
    with Session(engine) as session:
        row = session.get(AiDraftSession, session_id)
        if row is None or row.tenant_id != tenant_id or row.user_id != user_id:
            raise HTTPException(status_code=404, detail="AI draft session not found")
        if row.status == AiDraftSessionStatus.ACTIVE:
            row.status = AiDraftSessionStatus.DISCARDED
            row.updated_at = now
            session.add(row)
            session.commit()


def set_last_error(
    *,
    session_id: UUID,
    tenant_id: UUID,
    user_id: UUID,
    error: dict[str, Any],
) -> None:
    """Attach structured failure details after confirm or validation error."""

    now = _utcnow()
    with Session(engine) as session:
        row = session.get(AiDraftSession, session_id)
        if (
            row is None
            or row.tenant_id != tenant_id
            or row.user_id != user_id
            or row.status != AiDraftSessionStatus.ACTIVE
            or row.expires_at <= now
        ):
            return
        row.last_error = error
        row.updated_at = now
        row.expires_at = _default_expires_at()
        session.add(row)
        session.commit()
