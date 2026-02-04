"""Database operations for schedule rules."""

from typing import Optional
from uuid import UUID

from sqlmodel import Session, select

from app.models.schedule_rule import ScheduleRule
from app.db.engine import engine


def create_schedule_rule(
    tenant_id: UUID,
    action: str,
    note: Optional[str] = None,
    times: Optional[dict] = None,
) -> ScheduleRule:
    """Create a new schedule rule."""
    rule = ScheduleRule(tenant_id=tenant_id, action=action, note=note, times=times or [])
    with Session(engine) as session:
        session.add(rule)
        session.commit()
        session.refresh(rule)
    return rule


def get_schedule_rule_by_id(rule_id: UUID) -> Optional[ScheduleRule]:
    """Get a schedule rule by its UUID."""
    with Session(engine) as session:
        return session.get(ScheduleRule, rule_id)


def list_schedule_rules_by_tenant(
    tenant_id: UUID,
    limit: int = 100,
    offset: int = 0,
) -> list[ScheduleRule]:
    """List schedule rules for a tenant."""
    with Session(engine) as session:
        statement = (
            select(ScheduleRule)
            .where(ScheduleRule.tenant_id == tenant_id)
            .order_by(ScheduleRule.created_at.asc())
            .limit(limit)
            .offset(offset)
        )
        return list(session.exec(statement).all())


def save_schedule_rule(rule: ScheduleRule) -> ScheduleRule:
    """Save (update) a schedule rule."""
    from datetime import datetime
    rule.updated_at = datetime.utcnow()
    with Session(engine) as session:
        session.add(rule)
        session.commit()
        session.refresh(rule)
    return rule


def delete_schedule_rule(rule: ScheduleRule) -> None:
    """Delete a schedule rule."""
    with Session(engine) as session:
        rule_in_session = session.get(ScheduleRule, rule.id)
        if rule_in_session:
            session.delete(rule_in_session)
            session.commit()
