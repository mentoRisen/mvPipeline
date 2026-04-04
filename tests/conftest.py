from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session

import app.models  # noqa: F401
import app.api.routes as routes
import app.db.engine as db_engine
import app.services.schedule_rule_repo as schedule_rule_repo
import app.services.ai_draft_session_repo as ai_draft_session_repo
import app.services.task_repo as task_repo
import app.services.tenant_repo as tenant_repo
import app.services.user_repo as user_repo
from app.main import app
from app.models.tenant import Tenant
from app.models.user import User
from app.services import auth as auth_service


@pytest.fixture
def test_engine(monkeypatch: pytest.MonkeyPatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    monkeypatch.setattr(db_engine, "engine", engine)
    monkeypatch.setattr(task_repo, "engine", engine)
    monkeypatch.setattr(tenant_repo, "engine", engine)
    monkeypatch.setattr(user_repo, "engine", engine)
    monkeypatch.setattr(schedule_rule_repo, "engine", engine)
    monkeypatch.setattr(ai_draft_session_repo, "engine", engine)
    monkeypatch.setattr(routes, "engine", engine)

    SQLModel.metadata.create_all(engine)
    yield engine
    SQLModel.metadata.drop_all(engine)


@pytest.fixture(autouse=True)
def reset_database(test_engine) -> Generator[None, None, None]:
    for table in reversed(SQLModel.metadata.sorted_tables):
        with test_engine.begin() as connection:
            connection.execute(table.delete())
    yield


@pytest.fixture
def db_session(test_engine) -> Generator[Session, None, None]:
    with Session(test_engine) as session:
        yield session


@pytest.fixture
def tenant(db_session: Session) -> Tenant:
    tenant = Tenant(
        name="Acme",
        description="On-brand marketing copy",
        instagram_account="@acme",
        facebook_page="acme-page",
    )
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant


@pytest.fixture
def auth_user(db_session: Session) -> User:
    user = User(
        username="tester",
        hashed_password="not-used",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def client(test_engine, auth_user) -> Generator[TestClient, None, None]:
    app.dependency_overrides[auth_service.get_current_active_user] = lambda: auth_user
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
