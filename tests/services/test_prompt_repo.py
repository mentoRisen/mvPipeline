from __future__ import annotations

from uuid import uuid4

from app.models.prompt import PromptType
from app.services import prompt_repo


def test_create_list_get_update_delete(tenant):
    p = prompt_repo.create_prompt(
        tenant_id=tenant.id,
        name="  Main brief  ",
        prompt_type=PromptType.TASK_CREATION,
        body="Hello world",
    )
    assert p.id is not None
    assert p.name == "  Main brief  "

    rows = prompt_repo.list_prompts_for_tenant(tenant.id)
    assert len(rows) == 1
    assert rows[0].id == p.id

    loaded = prompt_repo.get_prompt_by_id(p.id)
    assert loaded is not None
    assert loaded.body == "Hello world"

    loaded.body = "Updated"
    saved = prompt_repo.save_prompt(loaded)
    assert saved.body == "Updated"
    assert saved.updated_at >= p.updated_at

    prompt_repo.delete_prompt(saved)
    assert prompt_repo.get_prompt_by_id(p.id) is None


def test_list_empty_tenant(tenant):
    other_id = uuid4()
    assert prompt_repo.list_prompts_for_tenant(other_id) == []


def test_get_missing_returns_none():
    assert prompt_repo.get_prompt_by_id(uuid4()) is None
