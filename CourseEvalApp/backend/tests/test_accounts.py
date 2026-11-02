from conftest import PASSWORD, auth_header, login
from models import Role, Status


def register(client, email="new@csumb.edu", password=PASSWORD):
    return client.post("/api/auth/register", json={"email": email, "name": "New Prof", "password": password})


def test_register_creates_pending_account_that_cannot_sign_in(client):
    assert register(client).status_code == 201
    response = login(client, "new@csumb.edu")
    assert response.status_code == 403
    assert "approval" in response.json()["detail"]


def test_email_is_case_insensitive_and_unique(client):
    assert register(client, "Prof@CSUMB.edu").status_code == 201
    assert register(client, "prof@csumb.edu").status_code == 409


def test_weak_passwords_are_rejected(client):
    assert register(client, password="short1").status_code == 422
    assert register(client, password="onlyletterslong").status_code == 422


def test_admin_approves_then_professor_can_sign_in(client, make_user):
    make_user("admin@csumb.edu", role=Role.ADMIN)
    register(client)
    admin = auth_header(client, "admin@csumb.edu")
    pending = client.get("/api/admin/users?status=pending", headers=admin).json()
    assert [u["email"] for u in pending] == ["new@csumb.edu"]

    approved = client.post(f"/api/admin/users/{pending[0]['id']}/approve", headers=admin).json()
    assert approved["status"] == Status.APPROVED

    response = login(client, "new@csumb.edu")
    assert response.status_code == 200
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {response.json()['access_token']}"}).json()
    assert me["email"] == "new@csumb.edu" and me["role"] == Role.PROFESSOR
    assert "password_hash" not in me and "encrypted_api_key" not in me


def test_rejected_and_disabled_accounts_lose_access(client, make_user):
    make_user("admin@csumb.edu", role=Role.ADMIN)
    rejected_id = make_user("reject@csumb.edu", status=Status.PENDING)
    active_id = make_user("active@csumb.edu")
    admin = auth_header(client, "admin@csumb.edu")

    assert client.post(f"/api/admin/users/{rejected_id}/reject", headers=admin).status_code == 200
    assert login(client, "reject@csumb.edu").status_code == 403

    professor = auth_header(client, "active@csumb.edu")
    assert client.post(f"/api/admin/users/{active_id}/disable", headers=admin).status_code == 200
    # An already-issued token stops working as soon as the account is disabled
    assert client.get("/api/auth/me", headers=professor).status_code == 401
    assert login(client, "active@csumb.edu").status_code == 403

    assert client.post(f"/api/admin/users/{active_id}/enable", headers=admin).status_code == 200
    assert login(client, "active@csumb.edu").status_code == 200


def test_professors_cannot_use_admin_endpoints(client, make_user):
    make_user("prof@csumb.edu")
    professor = auth_header(client, "prof@csumb.edu")
    assert client.get("/api/admin/users", headers=professor).status_code == 403
    assert client.get("/api/admin/users").status_code == 401


def test_admin_cannot_lock_themselves_out(client, make_user):
    admin_id = make_user("admin@csumb.edu", role=Role.ADMIN)
    admin = auth_header(client, "admin@csumb.edu")
    assert client.post(f"/api/admin/users/{admin_id}/disable", headers=admin).status_code == 400
    assert client.patch(f"/api/admin/users/{admin_id}/role", json={"role": "professor"}, headers=admin).status_code == 400


def test_invalid_status_transitions_are_refused(client, make_user):
    make_user("admin@csumb.edu", role=Role.ADMIN)
    active_id = make_user("active@csumb.edu")
    admin = auth_header(client, "admin@csumb.edu")
    assert client.post(f"/api/admin/users/{active_id}/reject", headers=admin).status_code == 409


def test_repeated_wrong_passwords_lock_the_account(client, make_user):
    make_user("prof@csumb.edu")
    for _ in range(5):
        assert login(client, "prof@csumb.edu", "wrong-password-1").status_code == 401
    # Locked now, even with the right password
    assert login(client, "prof@csumb.edu").status_code == 429


def test_unknown_email_and_wrong_password_give_the_same_answer(client, make_user):
    make_user("prof@csumb.edu")
    unknown = login(client, "nobody@csumb.edu")
    wrong = login(client, "prof@csumb.edu", "wrong-password-1")
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json() == wrong.json()


def test_change_password_signs_out_old_tokens(client, make_user):
    make_user("prof@csumb.edu")
    old = auth_header(client, "prof@csumb.edu")
    response = client.post("/api/auth/change-password", headers=old,
                           json={"current_password": PASSWORD, "new_password": "new-password-99"})
    assert response.status_code == 200
    assert client.get("/api/auth/me", headers=old).status_code == 401
    assert login(client, "prof@csumb.edu", "new-password-99").status_code == 200


def test_tampered_or_missing_tokens_are_rejected(client, make_user):
    make_user("prof@csumb.edu")
    token = login(client, "prof@csumb.edu").json()["access_token"]
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {token[:-2]}xx"}).status_code == 401
    assert client.get("/api/auth/me").status_code == 401


def test_admin_summary_counts(client, make_user):
    make_user("admin@csumb.edu", role=Role.ADMIN)
    make_user("p1@csumb.edu", status=Status.PENDING)
    make_user("p2@csumb.edu", status=Status.PENDING)
    summary = client.get("/api/admin/summary", headers=auth_header(client, "admin@csumb.edu")).json()
    assert summary["pending"] == 2 and summary["approved"] == 1


def test_create_admin_command_needs_no_hardcoded_password(db_session, monkeypatch):
    import manage
    answers = iter(["Boss@CSUMB.edu", "Head Admin"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    monkeypatch.setattr(manage.getpass, "getpass", lambda prompt="": "admin-pass-2026")
    monkeypatch.setattr(manage, "SessionLocal", db_session)
    monkeypatch.setattr(manage, "init_db", lambda: None)
    manage.create_admin()
    with db_session() as db:
        from sqlalchemy import select
        from models import User
        admin = db.scalar(select(User).where(User.email == "boss@csumb.edu"))
        assert admin.role == Role.ADMIN and admin.status == Status.APPROVED
        assert admin.password_hash != "admin-pass-2026"


def test_guide_shows_until_marked_seen(client, make_user):
    make_user("prof@csumb.edu")
    headers = auth_header(client, "prof@csumb.edu")
    assert client.get("/api/auth/me", headers=headers).json()["guide_seen_at"] is None

    first = client.post("/api/auth/guide-seen", headers=headers).json()["guide_seen_at"]
    assert first is not None
    # Seeing it again keeps the first date (SQLite drops the timezone suffix, so compare to the second)
    again = client.post("/api/auth/guide-seen", headers=headers).json()["guide_seen_at"]
    assert again[:19] == first[:19]
    assert client.get("/api/auth/me", headers=headers).json()["guide_seen_at"][:19] == first[:19]
    assert client.post("/api/auth/guide-seen").status_code == 401
