"""Choosing an AI provider and model for a professor's own key (no AI calls)."""
import credits
from conftest import auth_header
from models import CreditMode, Role, User

ANTHROPIC_KEY = "sk-ant-api03-abcdefghijklmnopqrstuvwxyz1234ANTH"
GEMINI_KEY = "AIzaSyAbcdefghijklmnopqrstuvwxyz12345GEMI"
OPENAI_KEY = "sk-proj-abcdefghijklmnopqrstuvwxyz1234WXYZ"


def own_key_professor(client, make_user):
    make_user("admin@csumb.edu", role=Role.ADMIN)
    user_id = make_user("prof@csumb.edu")
    client.patch(f"/api/admin/users/{user_id}/credits", json={"credit_mode": "own_key"},
                 headers=auth_header(client, "admin@csumb.edu"))
    return user_id, auth_header(client, "prof@csumb.edu")


def test_models_list_has_three_providers(client, make_user):
    make_user("prof@csumb.edu")
    catalog = client.get("/api/models", headers=auth_header(client, "prof@csumb.edu")).json()
    assert [p["provider"] for p in catalog] == ["openai", "anthropic", "gemini"]
    assert all(p["models"] and "input" not in p["models"][0] for p in catalog)  # no prices sent to the browser


def test_anthropic_key_and_model_are_used_for_runs(client, db_session, make_user):
    user_id, headers = own_key_professor(client, make_user)
    saved = client.put("/api/me/api-key", json={"provider": "anthropic", "model": "claude-haiku-5-5",
                                                "api_key": ANTHROPIC_KEY}, headers=headers)
    assert saved.status_code == 200
    body = saved.json()
    assert body["api_provider"] == "anthropic" and body["api_model"] == "claude-haiku-5-5"
    assert body["api_model_label"] == "Claude Haiku 5.5" and body["api_key_last4"] == "ANTH"
    assert ANTHROPIC_KEY not in saved.text
    with db_session() as db:
        plan = credits.plan_run(db, db.get(User, user_id), "openai")
    assert (plan.model_choice, plan.model_id, plan.api_key, plan.uses_own_key) == (
        "anthropic", "claude-haiku-5-5", ANTHROPIC_KEY, True)


def test_key_must_match_the_provider(client, make_user):
    _, headers = own_key_professor(client, make_user)
    for provider, key in (("anthropic", OPENAI_KEY), ("openai", ANTHROPIC_KEY), ("gemini", OPENAI_KEY), ("openai", GEMINI_KEY)):
        response = client.put("/api/me/api-key", json={"provider": provider, "api_key": key}, headers=headers)
        assert response.status_code == 400, (provider, key)
    assert "AIza" in client.put("/api/me/api-key", json={"provider": "gemini", "api_key": "nope"}, headers=headers).json()["detail"]
    assert client.put("/api/me/api-key", json={"provider": "gemini", "api_key": GEMINI_KEY}, headers=headers).status_code == 200


def test_unknown_provider_or_model_is_refused(client, make_user):
    _, headers = own_key_professor(client, make_user)
    assert client.put("/api/me/api-key", json={"provider": "mistral", "api_key": OPENAI_KEY}, headers=headers).status_code == 400
    assert client.put("/api/me/api-key", json={"provider": "openai", "model": "gpt-2", "api_key": OPENAI_KEY},
                      headers=headers).status_code == 400


def test_model_can_change_without_the_key_but_not_the_provider(client, db_session, make_user):
    user_id, headers = own_key_professor(client, make_user)
    client.put("/api/me/api-key", json={"provider": "gemini", "api_key": GEMINI_KEY}, headers=headers)
    changed = client.put("/api/me/api-model", json={"provider": "gemini", "model": "gemini-2.5-pro"}, headers=headers)
    assert changed.status_code == 200 and changed.json()["api_model"] == "gemini-2.5-pro"
    other = client.put("/api/me/api-model", json={"provider": "anthropic", "model": "claude-sonnet-5-5"}, headers=headers)
    assert other.status_code == 400 and "another provider" in other.json()["detail"]
    with db_session() as db:
        assert credits.plan_run(db, db.get(User, user_id), "openai").model_id == "gemini-2.5-pro"


def test_removing_the_key_clears_provider_and_model(client, make_user):
    _, headers = own_key_professor(client, make_user)
    client.put("/api/me/api-key", json={"provider": "anthropic", "api_key": ANTHROPIC_KEY}, headers=headers)
    body = client.delete("/api/me/api-key", headers=headers).json()
    assert body["has_own_key"] is False and body["api_provider"] is None and body["api_model"] is None


def test_keys_saved_before_providers_existed_run_on_openai(client, db_session, make_user):
    user_id, headers = own_key_professor(client, make_user)
    client.put("/api/me/api-key", json={"api_key": OPENAI_KEY}, headers=headers)  # old request shape
    with db_session() as db:
        user = db.get(User, user_id)
        user.api_provider = None  # as stored by the earlier version
        user.api_model = None
        db.commit()
        plan = credits.plan_run(db, user, "openai")
    assert plan.model_choice == "openai" and plan.api_key == OPENAI_KEY
    assert client.get("/api/me/credits", headers=headers).json()["api_provider"] == "openai"


def test_lab_credit_users_stay_on_the_lab_model(db_session, make_user):
    user_id = make_user("prof@csumb.edu")
    with db_session() as db:
        user = db.get(User, user_id)
        user.credit_mode = CreditMode.OUR_KEY_UNLIMITED
        user.api_provider, user.api_model = "anthropic", "claude-opus-5-5"
        db.commit()
        plan = credits.plan_run(db, user, "openai")
    assert (plan.model_choice, plan.model_id, plan.api_key) == ("openai", None, None)
