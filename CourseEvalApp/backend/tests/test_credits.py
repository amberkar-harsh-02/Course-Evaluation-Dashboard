import pytest
from fastapi import HTTPException

import config
import credits
from conftest import auth_header
from models import CreditMode, Role, UsageLog, User

OWN_KEY = "sk-proj-abcdefghijklmnopqrstuvwxyz1234WXYZ"


def spend(db_session, user_id, dollars, own_key=False):
    with db_session() as db:
        db.add(UsageLog(user_id=user_id, cost_usd=dollars, used_own_key=own_key, input_tokens=1000, output_tokens=100))
        db.commit()


def get_user(db_session, user_id):
    with db_session() as db:
        return db.get(User, user_id)


def test_new_professors_get_the_default_dollar_cap(client, make_user):
    make_user("prof@csumb.edu")
    credit = client.get("/api/me/credits", headers=auth_header(client, "prof@csumb.edu")).json()
    assert credit["credit_mode"] == CreditMode.OUR_KEY_CAPPED
    assert credit["yearly_cap_usd"] == 20
    assert credit["remaining_usd"] == 20
    assert credit["allowed_models"] == ["openai"]


def test_cap_blocks_runs_once_used_up(db_session, make_user):
    user_id = make_user("prof@csumb.edu")
    with db_session() as db:
        user = db.get(User, user_id)
        assert credits.plan_run(db, user, "openai").uses_own_key is False
    spend(db_session, user_id, 20.0)
    with db_session() as db:
        with pytest.raises(HTTPException) as refused:
            credits.plan_run(db, db.get(User, user_id), "openai")
        assert refused.value.status_code == 402
        assert credits.credit_status(db, db.get(User, user_id))["remaining_usd"] == 0


def test_unlimited_mode_ignores_the_personal_cap(client, db_session, make_user):
    make_user("admin@csumb.edu", role=Role.ADMIN)
    user_id = make_user("prof@csumb.edu")
    spend(db_session, user_id, 500.0)
    response = client.patch(f"/api/admin/users/{user_id}/credits", json={"credit_mode": "our_key_unlimited"},
                            headers=auth_header(client, "admin@csumb.edu"))
    assert response.status_code == 200
    with db_session() as db:
        assert credits.plan_run(db, db.get(User, user_id), "openai").api_key is None


def test_admin_sets_a_custom_cap(client, db_session, make_user):
    make_user("admin@csumb.edu", role=Role.ADMIN)
    user_id = make_user("prof@csumb.edu")
    response = client.patch(f"/api/admin/users/{user_id}/credits", json={"credit_mode": "our_key_capped", "yearly_cap_usd": 5},
                            headers=auth_header(client, "admin@csumb.edu"))
    assert response.json()["credits"]["yearly_cap_usd"] == 5
    spend(db_session, user_id, 5.0)
    with db_session() as db, pytest.raises(HTTPException):
        credits.plan_run(db, db.get(User, user_id), "openai")


def test_professors_cannot_change_their_own_credits(client, make_user):
    user_id = make_user("prof@csumb.edu")
    response = client.patch(f"/api/admin/users/{user_id}/credits", json={"credit_mode": "our_key_unlimited"},
                            headers=auth_header(client, "prof@csumb.edu"))
    assert response.status_code == 403


def test_own_key_is_stored_encrypted_and_never_returned(client, db_session, make_user):
    user_id = make_user("prof@csumb.edu")
    headers = auth_header(client, "prof@csumb.edu")
    response = client.put("/api/me/api-key", json={"api_key": OWN_KEY}, headers=headers)
    assert response.status_code == 200
    assert response.json()["api_key_last4"] == "WXYZ"
    assert OWN_KEY not in response.text
    assert OWN_KEY not in client.get("/api/auth/me", headers=headers).text

    stored = get_user(db_session, user_id).encrypted_api_key
    assert stored and OWN_KEY not in stored


def test_own_key_mode_uses_the_decrypted_key_and_costs_the_lab_nothing(client, db_session, make_user):
    make_user("admin@csumb.edu", role=Role.ADMIN)
    user_id = make_user("prof@csumb.edu")
    client.put("/api/me/api-key", json={"api_key": OWN_KEY}, headers=auth_header(client, "prof@csumb.edu"))
    client.patch(f"/api/admin/users/{user_id}/credits", json={"credit_mode": "own_key"},
                 headers=auth_header(client, "admin@csumb.edu"))
    with db_session() as db:
        user = db.get(User, user_id)
        plan = credits.plan_run(db, user, "openai")
        assert plan.uses_own_key and plan.api_key == OWN_KEY
        entry = credits.record_usage(db, user, {"input_tokens": 9000, "output_tokens": 900, "estimated_cost_usd": 3.5}, plan)
        assert entry.cost_usd == 0 and entry.input_tokens == 9000
        assert credits.lab_spend_this_year(db) == 0


def test_own_key_mode_without_a_key_is_refused(db_session, make_user):
    user_id = make_user("prof@csumb.edu")
    with db_session() as db:
        user = db.get(User, user_id)
        user.credit_mode = CreditMode.OWN_KEY
        db.commit()
        with pytest.raises(HTTPException) as refused:
            credits.plan_run(db, user, "openai")
        assert "API key" in refused.value.detail


def test_invalid_keys_are_rejected_and_keys_can_be_deleted(client, make_user):
    make_user("prof@csumb.edu")
    headers = auth_header(client, "prof@csumb.edu")
    assert client.put("/api/me/api-key", json={"api_key": "not-a-key"}, headers=headers).status_code == 400
    client.put("/api/me/api-key", json={"api_key": OWN_KEY}, headers=headers)
    deleted = client.delete("/api/me/api-key", headers=headers).json()
    assert deleted["has_own_key"] is False and deleted["api_key_last4"] is None


def test_saving_a_key_without_the_server_secret_fails_safely(client, make_user, monkeypatch):
    make_user("prof@csumb.edu")
    monkeypatch.setattr(config, "KEY_ENCRYPTION_SECRET", "")
    response = client.put("/api/me/api-key", json={"api_key": OWN_KEY}, headers=auth_header(client, "prof@csumb.edu"))
    assert response.status_code == 503


def test_local_model_is_admin_only(db_session, make_user):
    admin_id = make_user("admin@csumb.edu", role=Role.ADMIN)
    prof_id = make_user("prof@csumb.edu")
    with db_session() as db:
        assert credits.plan_run(db, db.get(User, admin_id), "local").model_choice == "local"
        with pytest.raises(HTTPException) as refused:
            credits.plan_run(db, db.get(User, prof_id), "local")
        assert refused.value.status_code == 403
        with pytest.raises(HTTPException):
            credits.plan_run(db, db.get(User, prof_id), "anthropic")


def test_total_budget_stops_lab_key_runs(db_session, make_user, monkeypatch):
    monkeypatch.setattr(config, "TOTAL_CREDIT_BUDGET_USD", 100.0)
    rich_id = make_user("rich@csumb.edu")
    other_id = make_user("other@csumb.edu")
    spend(db_session, rich_id, 100.0)
    with db_session() as db:
        with pytest.raises(HTTPException) as refused:
            credits.plan_run(db, db.get(User, other_id), "openai")
        assert "shared AI credit" in refused.value.detail


def test_spending_before_the_credit_year_does_not_count(db_session, make_user):
    from datetime import timedelta
    user_id = make_user("prof@csumb.edu")
    with db_session() as db:
        db.add(UsageLog(user_id=user_id, cost_usd=50.0, created_at=credits.credit_year_start() - timedelta(days=1)))
        db.commit()
        assert credits.lab_spend_this_year(db, db.get(User, user_id)) == 0


def test_admin_usage_overview(client, db_session, make_user, monkeypatch):
    monkeypatch.setattr(config, "TOTAL_CREDIT_BUDGET_USD", 1000.0)
    make_user("admin@csumb.edu", role=Role.ADMIN)
    a = make_user("a@csumb.edu")
    b = make_user("b@csumb.edu")
    spend(db_session, a, 3.0)
    spend(db_session, a, 2.0)
    spend(db_session, b, 1.0)
    spend(db_session, b, 9.0, own_key=True)
    overview = client.get("/api/admin/usage", headers=auth_header(client, "admin@csumb.edu")).json()
    assert overview["lab_spend_usd"] == 6.0
    assert overview["budget_remaining_usd"] == 994.0
    first = overview["per_user"][0]
    assert first["email"] == "a@csumb.edu" and first["runs"] == 2 and first["lab_cost_usd"] == 5.0


def test_new_columns_are_added_to_an_existing_database(tmp_path):
    """A dev database created by Phase 1 gets the new yearly_cap_usd column on start."""
    import database
    from sqlalchemy import inspect, text
    engine = database.make_engine(f"sqlite:///{(tmp_path / 'old.db').as_posix()}")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY, email VARCHAR(255))"))
    database.init_db(engine)
    assert "yearly_cap_usd" in {c["name"] for c in inspect(engine).get_columns("users")}
