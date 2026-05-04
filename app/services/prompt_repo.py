"""Database operations for tenant prompts."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlmodel import Session, select, desc

from app.db.engine import engine
from app.models.prompt import Prompt, PromptType


def create_prompt(
    tenant_id: UUID,
    name: str,
    prompt_type: PromptType,
    body: str,
) -> Prompt:
    prompt = Prompt(
        tenant_id=tenant_id,
        name=name,
        prompt_type=prompt_type,
        body=body,
    )
    with Session(engine) as session:
        session.add(prompt)
        session.commit()
        session.refresh(prompt)
    return prompt


def get_prompt_by_id(prompt_id: UUID) -> Optional[Prompt]:
    with Session(engine) as session:
        return session.get(Prompt, prompt_id)


def list_prompts_for_tenant(
    tenant_id: UUID,
    limit: int = 100,
    offset: int = 0,
) -> list[Prompt]:
    with Session(engine) as session:
        statement = (
            select(Prompt)
            .where(Prompt.tenant_id == tenant_id)
            .order_by(desc(Prompt.updated_at))
            .limit(limit)
            .offset(offset)
        )
        return list(session.exec(statement).all())


def save_prompt(prompt: Prompt) -> Prompt:
    prompt.updated_at = datetime.utcnow()
    with Session(engine) as session:
        session.add(prompt)
        session.commit()
        session.refresh(prompt)
    return prompt


def delete_prompt(prompt: Prompt) -> None:
    with Session(engine) as session:
        row = session.get(Prompt, prompt.id)
        if row:
            session.delete(row)
            session.commit()
