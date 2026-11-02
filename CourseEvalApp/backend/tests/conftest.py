import os
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
os.environ["JWT_SECRET_KEY"] = "test-secret-key-for-unit-tests-only-0123456789"
os.environ["DATABASE_URL"] = "sqlite://"  # replaced per test below

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

import app as app_module  # noqa: E402
import database  # noqa: E402
from models import Role, Status, User  # noqa: E402
from security import hash_password  # noqa: E402

PASSWORD = "correct-horse-42"


@pytest.fixture
def db_session(tmp_path):
    engine = database.make_engine(f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
    database.init_db(engine)
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    yield Session
    engine.dispose()


@pytest.fixture
def client(db_session, monkeypatch):
    def override_db():
        db = db_session()
        try:
            yield db
        finally:
            db.close()

    app_module.app.dependency_overrides[database.get_db] = override_db
    monkeypatch.setattr(app_module, "init_db", lambda: None)
    with TestClient(app_module.app) as test_client:
        yield test_client
    app_module.app.dependency_overrides.clear()


@pytest.fixture
def make_user(db_session):
    def _make(email="prof@csumb.edu", role=Role.PROFESSOR, status=Status.APPROVED, password=PASSWORD):
        with db_session() as db:
            user = User(email=email, name=email.split("@")[0], password_hash=hash_password(password), role=role, status=status)
            db.add(user)
            db.commit()
            return user.id
    return _make


def login(client, email, password=PASSWORD):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def auth_header(client, email, password=PASSWORD):
    token = login(client, email, password).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
