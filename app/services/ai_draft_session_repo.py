"""Persistence for AI draft sessions (tenant + user scoped)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import delete, func
from sqlmodel import Session, select

from app.config import (
    AI_DRAFT_COMMUNICATION_MAX_PAYLOAD_BYTES,
    AI_DRAFT_SESSION_MAX_BUNDLE_BYTES,
    AI_DRAFT_SESSION_MAX_PER_USER,
    AI_DRAFT_SESSION_TTL_DAYS,
)
from app.db.engine import engine
from app.models.ai_draft_communication_event import (
    AiDraftCommunicationEvent,
    AiDraftCommunicationKind,
)
from app.models.ai_draft_revision_snapshot import AiDraftRevisionSnapshot
from app.models.ai_draft_session import (
    AiDraftSession,
    AiDraftPreviewStatus,
    AiDraftSessionStatus,
)

UNDO_SNAPSHOT_MAX_PER_SESSION = 3
REDACTED_PLACEHOLDER = "***redacted***"


def _utcnow() -> datetime:
    return datetime.utcnow()


def _preview_status_key(row: AiDraftSession) -> str:
    ps = row.preview_status
    if isinstance(ps, AiDraftPreviewStatus):
        return ps.value
    return str(ps)


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


def assert_communication_payload_within_size(payload: dict[str, Any]) -> None:
    raw = json.dumps(payload, default=str).encode("utf-8")
    if len(raw) > AI_DRAFT_COMMUNICATION_MAX_PAYLOAD_BYTES:
        raise HTTPException(
            status_code=422,
            detail="AI draft communication event exceeds maximum stored size",
        )


def _sanitize_secret_like_values(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, raw in value.items():
            key_l = str(key).lower()
            if any(
                token in key_l
                for token in ("token", "password", "secret", "authorization", "api_key")
            ):
                sanitized[key] = REDACTED_PLACEHOLDER
            else:
                sanitized[key] = _sanitize_secret_like_values(raw)
        return sanitized
    if isinstance(value, list):
        return [_sanitize_secret_like_values(v) for v in value]
    if isinstance(value, str):
        lowered = value.lower()
        if "bearer " in lowered or "sk-" in lowered:
            return REDACTED_PLACEHOLDER
    return value


def _next_communication_sequence(db: Session, draft_session_id: UUID) -> int:
    current = db.exec(
        select(func.max(AiDraftCommunicationEvent.sequence)).where(
            AiDraftCommunicationEvent.draft_session_id == draft_session_id
        )
    ).first()
    if current is None:
        return 0
    return int(current) + 1


def append_communication_event(
    *,
    draft_session_id: UUID,
    tenant_id: UUID,
    user_id: UUID,
    kind: AiDraftCommunicationKind,
    payload: dict[str, Any],
) -> None:
    """Append one transcript row; visible to poll clients after commit."""

    payload = _sanitize_secret_like_values(payload)
    assert_communication_payload_within_size(payload)
    now = _utcnow()
    with Session(engine) as db:
        row = db.get(AiDraftSession, draft_session_id)
        if (
            row is None
            or row.tenant_id != tenant_id
            or row.user_id != user_id
            or row.status != AiDraftSessionStatus.ACTIVE
            or row.expires_at <= now
        ):
            return
        seq = _next_communication_sequence(db, draft_session_id)
        ev = AiDraftCommunicationEvent(
            draft_session_id=draft_session_id,
            sequence=seq,
            kind=kind.value,
            payload=payload,
            created_at=_utcnow(),
        )
        db.add(ev)
        row.updated_at = _utcnow()
        db.add(row)
        db.commit()


def list_communication_events(
    *,
    draft_session_id: UUID,
    tenant_id: UUID,
    user_id: UUID,
) -> list[AiDraftCommunicationEvent]:
    now = _utcnow()
    with Session(engine) as db:
        row = db.get(AiDraftSession, draft_session_id)
        if (
            row is None
            or row.tenant_id != tenant_id
            or row.user_id != user_id
            or row.expires_at <= now
        ):
            return []
        if row.status != AiDraftSessionStatus.ACTIVE:
            return []
        q = (
            select(AiDraftCommunicationEvent)
            .where(AiDraftCommunicationEvent.draft_session_id == draft_session_id)
            .order_by(AiDraftCommunicationEvent.sequence)
        )
        return list(db.exec(q).all())


def _count_open_active_sessions(
    session: Session,
    *,
    tenant_id: UUID,
    user_id: UUID,
) -> int:
    now = _utcnow()
    q = (
        select(func.count())
        .select_from(AiDraftSession)
        .where(
            AiDraftSession.tenant_id == tenant_id,
            AiDraftSession.user_id == user_id,
            AiDraftSession.status == AiDraftSessionStatus.ACTIVE,
            AiDraftSession.expires_at > now,
        )
    )
    count = session.exec(q).one()
    return int(count or 0)


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


def start_preview_run(
    *,
    tenant_id: UUID,
    user_id: UUID,
    brief: str,
    draft_session_id: Optional[UUID] = None,
) -> UUID:
    """Create or reset a draft session for async preview; ``preview_status`` becomes RUNNING."""

    now = _utcnow()
    exp = _default_expires_at()
    with Session(engine) as db:
        if draft_session_id is not None:
            row = db.get(AiDraftSession, draft_session_id)
            if (
                row is None
                or row.tenant_id != tenant_id
                or row.user_id != user_id
                or row.status != AiDraftSessionStatus.ACTIVE
                or row.expires_at <= now
            ):
                raise HTTPException(status_code=404, detail="AI draft session not found")
            if _preview_status_key(row) == AiDraftPreviewStatus.RUNNING.value:
                raise HTTPException(
                    status_code=409,
                    detail="AI draft preview already in progress for this session",
                )
            row.brief = brief
            if row.bundle is None:
                row.bundle = {"items": []}
            row.last_error = None
            row.preview_status = AiDraftPreviewStatus.RUNNING
            row.expires_at = exp
            row.updated_at = now
            db.add(row)
            db.commit()
            return row.id

        open_count = _count_open_active_sessions(
            db,
            tenant_id=tenant_id,
            user_id=user_id,
        )
        if open_count >= AI_DRAFT_SESSION_MAX_PER_USER:
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "ai_draft_session_limit_reached",
                    "message": (
                        "Maximum open AI drafts reached. Discard old drafts to continue."
                    ),
                    "max_per_user": AI_DRAFT_SESSION_MAX_PER_USER,
                },
            )
        row = AiDraftSession(
            tenant_id=tenant_id,
            user_id=user_id,
            brief=brief,
            bundle={"items": []},
            last_error=None,
            status=AiDraftSessionStatus.ACTIVE,
            preview_status=AiDraftPreviewStatus.RUNNING,
            expires_at=exp,
            created_at=now,
            updated_at=now,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row.id


def finalize_preview_success(
    *,
    draft_session_id: UUID,
    tenant_id: UUID,
    user_id: UUID,
    items: list[dict[str, Any]],
) -> None:
    """Persist validated bundle and mark preview SUCCEEDED (must be RUNNING)."""

    bundle = bundle_dict_from_items(items)
    assert_bundle_within_size(bundle)
    now = _utcnow()
    with Session(engine) as db:
        row = db.get(AiDraftSession, draft_session_id)
        if (
            row is None
            or row.tenant_id != tenant_id
            or row.user_id != user_id
            or row.status != AiDraftSessionStatus.ACTIVE
            or row.expires_at <= now
        ):
            return
        if _preview_status_key(row) != AiDraftPreviewStatus.RUNNING.value:
            return
        _snapshot_current_bundle(db=db, row=row)
        row.bundle = bundle
        row.preview_status = AiDraftPreviewStatus.SUCCEEDED
        row.last_error = None
        row.expires_at = _default_expires_at()
        row.updated_at = now
        db.add(row)
        db.commit()


def finalize_preview_failure(
    *,
    draft_session_id: UUID,
    tenant_id: UUID,
    user_id: UUID,
    last_error: dict[str, Any],
) -> None:
    """Mark preview FAILED while preserving current bundle."""

    now = _utcnow()
    with Session(engine) as db:
        row = db.get(AiDraftSession, draft_session_id)
        if (
            row is None
            or row.tenant_id != tenant_id
            or row.user_id != user_id
            or row.status != AiDraftSessionStatus.ACTIVE
            or row.expires_at <= now
        ):
            return
        if _preview_status_key(row) != AiDraftPreviewStatus.RUNNING.value:
            return
        row.preview_status = AiDraftPreviewStatus.FAILED
        row.last_error = _sanitize_secret_like_values(last_error)
        row.expires_at = _default_expires_at()
        row.updated_at = now
        db.add(row)
        db.commit()


def _snapshot_current_bundle(*, db: Session, row: AiDraftSession) -> None:
    current_bundle = row.bundle if isinstance(row.bundle, dict) else {"items": []}
    existing_items = current_bundle.get("items")
    if not isinstance(existing_items, list) or len(existing_items) == 0:
        return
    snap = AiDraftRevisionSnapshot(
        draft_session_id=row.id,
        tenant_id=row.tenant_id,
        user_id=row.user_id,
        bundle=current_bundle,
        created_at=_utcnow(),
    )
    db.add(snap)
    db.flush()
    q = (
        select(AiDraftRevisionSnapshot)
        .where(AiDraftRevisionSnapshot.draft_session_id == row.id)
        .order_by(AiDraftRevisionSnapshot.created_at.desc())
    )
    snaps = list(db.exec(q).all())
    for stale in snaps[UNDO_SNAPSHOT_MAX_PER_SESSION:]:
        db.delete(stale)


def list_revision_snapshots(
    *,
    draft_session_id: UUID,
    tenant_id: UUID,
    user_id: UUID,
) -> list[AiDraftRevisionSnapshot]:
    now = _utcnow()
    with Session(engine) as db:
        row = db.get(AiDraftSession, draft_session_id)
        if (
            row is None
            or row.tenant_id != tenant_id
            or row.user_id != user_id
            or row.status != AiDraftSessionStatus.ACTIVE
            or row.expires_at <= now
        ):
            return []
        q = (
            select(AiDraftRevisionSnapshot)
            .where(AiDraftRevisionSnapshot.draft_session_id == draft_session_id)
            .order_by(AiDraftRevisionSnapshot.created_at.desc())
        )
        return list(db.exec(q).all())


def restore_snapshot_bundle(
    *,
    draft_session_id: UUID,
    snapshot_id: int,
    tenant_id: UUID,
    user_id: UUID,
) -> AiDraftSession:
    now = _utcnow()
    with Session(engine) as db:
        row = db.get(AiDraftSession, draft_session_id)
        if (
            row is None
            or row.tenant_id != tenant_id
            or row.user_id != user_id
            or row.status != AiDraftSessionStatus.ACTIVE
            or row.expires_at <= now
        ):
            raise HTTPException(status_code=404, detail="AI draft session not found")
        if _preview_status_key(row) == AiDraftPreviewStatus.RUNNING.value:
            raise HTTPException(
                status_code=409,
                detail="Cannot restore draft while AI preview is in progress",
            )
        snapshot = db.exec(
            select(AiDraftRevisionSnapshot).where(
                AiDraftRevisionSnapshot.id == snapshot_id,
                AiDraftRevisionSnapshot.draft_session_id == draft_session_id,
                AiDraftRevisionSnapshot.tenant_id == tenant_id,
                AiDraftRevisionSnapshot.user_id == user_id,
            )
        ).first()
        if snapshot is None:
            raise HTTPException(status_code=404, detail="Undo snapshot not found")
        row.bundle = (
            snapshot.bundle if isinstance(snapshot.bundle, dict) else {"items": []}
        )
        row.last_error = None
        row.preview_status = AiDraftPreviewStatus.SUCCEEDED
        row.updated_at = now
        row.expires_at = _default_expires_at()
        db.delete(snapshot)
        db.add(row)
        db.commit()
        db.refresh(row)
        return row


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
            row.preview_status = AiDraftPreviewStatus.SUCCEEDED
            row.expires_at = exp
            row.updated_at = now
            session.add(row)
            session.commit()
            session.refresh(row)
            return row.id

        open_count = _count_open_active_sessions(
            session,
            tenant_id=tenant_id,
            user_id=user_id,
        )
        if open_count >= AI_DRAFT_SESSION_MAX_PER_USER:
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "ai_draft_session_limit_reached",
                    "message": (
                        "Maximum open AI drafts reached. Discard old drafts to continue."
                    ),
                    "max_per_user": AI_DRAFT_SESSION_MAX_PER_USER,
                },
            )
        row = AiDraftSession(
            tenant_id=tenant_id,
            user_id=user_id,
            brief=brief,
            bundle=bundle,
            last_error=None,
            status=AiDraftSessionStatus.ACTIVE,
            preview_status=AiDraftPreviewStatus.SUCCEEDED,
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
        if _preview_status_key(row) == AiDraftPreviewStatus.RUNNING.value:
            raise HTTPException(
                status_code=409,
                detail="Cannot edit draft while AI preview is in progress",
            )

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
        if _preview_status_key(row) != AiDraftPreviewStatus.SUCCEEDED.value:
            raise HTTPException(
                status_code=404,
                detail="AI draft session not found or preview not complete",
            )
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
