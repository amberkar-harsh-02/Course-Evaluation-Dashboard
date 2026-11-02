"""Upload -> analysis -> report flow with a fake OCR server and a fake NLP pipeline (no AI calls, no cost)."""
import time
import types

import pytest

import analysis
import config
from conftest import auth_header
from models import CreditMode, Report, Role, UsageLog, Upload, User

PIPELINE_CALLS = []


def fake_pipeline(**kwargs):
    PIPELINE_CALLS.append(kwargs)
    if kwargs.get("api_key") == "sk-bad":
        raise type("LLMAccountError", (RuntimeError,), {})("The OpenAI API key was rejected. Check the key and try again.")
    kwargs["progress"]("comments", 1, 1)
    return {
        "course_id": kwargs["course_id"],
        "overall_score": 4.25,
        "category_scores": [],
        "topic_summaries": [],
        "categories": [{"topic": "Pace", "comments": [{"feedback": c["text"], "score": 4} for c in kwargs["raw_comments"]]}],
        "metadata": {"model_id": "gpt-test", "usage": {"input_tokens": 10_000, "cached_input_tokens": 8_000,
                                                        "output_tokens": 1_000, "estimated_cost_usd": 0.5}},
    }


@pytest.fixture
def analysis_env(db_session, tmp_path, monkeypatch):
    PIPELINE_CALLS.clear()
    ocr = {"payload": {"parser": "pdf", "warnings": [], "quantitative": [],
                       "responses": [{"text": "Lectures were clear.", "question": None, "non_teaching_question": False}]}}
    monkeypatch.setattr(analysis, "session_factory", db_session)
    monkeypatch.setattr(config, "STORAGE_DIR", tmp_path / "storage")
    monkeypatch.setattr(analysis, "extract_comments", lambda path, name: ocr["payload"])
    monkeypatch.setattr(analysis, "load_pipeline", lambda: types.SimpleNamespace(analysis_pipeline=fake_pipeline))
    return ocr


def upload(client, headers, name="CHEM_110_F25.pdf", data=None, **form):
    return client.post("/api/analyses", files={"file": (name, b"%PDF fake")}, data={"model_choice": "openai", **form}, headers=headers)


def wait_for(client, headers, job_id):
    for _ in range(200):
        job = client.get(f"/api/analyses/{job_id}", headers=headers).json()
        if job["status"] in ("complete", "failed"):
            return job
        time.sleep(0.02)
    raise AssertionError(f"job did not finish: {job}")


def test_upload_runs_analysis_and_saves_a_private_report(client, db_session, make_user, analysis_env):
    user_id = make_user("prof@csumb.edu")
    headers = auth_header(client, "prof@csumb.edu")
    response = upload(client, headers, term="Fall 2025")
    assert response.status_code == 202
    job = wait_for(client, headers, response.json()["job_id"])
    assert job["status"] == "complete", job

    reports = client.get("/api/reports", headers=headers).json()
    assert len(reports) == 1
    assert reports[0]["course"] == "CHEM_110_F25" and reports[0]["term"] == "Fall 2025"
    assert reports[0]["overall_score"] == 4.25 and reports[0]["original_filename"] == "CHEM_110_F25.pdf"

    full = client.get(f"/api/reports/{reports[0]['id']}", headers=headers).json()
    assert full["report"]["categories"][0]["comments"][0]["feedback"] == "Lectures were clear."

    with db_session() as db:
        usage = db.query(UsageLog).one()
        assert usage.user_id == user_id and usage.cost_usd == 0.5 and usage.report_id == reports[0]["id"]
        stored = db.query(Upload).one()
        assert stored.original_filename == "CHEM_110_F25.pdf"
        assert str(config.STORAGE_DIR) in stored.stored_path


def test_reports_are_private_even_from_admins(client, make_user, analysis_env):
    make_user("prof@csumb.edu")
    make_user("other@csumb.edu")
    make_user("admin@csumb.edu", role=Role.ADMIN)
    prof = auth_header(client, "prof@csumb.edu")
    wait_for(client, prof, upload(client, prof).json()["job_id"])
    report_id = client.get("/api/reports", headers=prof).json()[0]["id"]

    for outsider in ("other@csumb.edu", "admin@csumb.edu"):
        headers = auth_header(client, outsider)
        assert client.get(f"/api/reports/{report_id}", headers=headers).status_code == 404
        assert client.get("/api/reports", headers=headers).json() == []
        assert client.delete(f"/api/reports/{report_id}", headers=headers).status_code == 404


def test_jobs_are_private(client, make_user, analysis_env):
    make_user("prof@csumb.edu")
    make_user("other@csumb.edu")
    prof = auth_header(client, "prof@csumb.edu")
    job_id = upload(client, prof).json()["job_id"]
    wait_for(client, prof, job_id)
    assert client.get(f"/api/analyses/{job_id}", headers=auth_header(client, "other@csumb.edu")).status_code == 404


def test_course_name_can_be_set_and_own_key_is_passed_to_the_pipeline(client, db_session, make_user, analysis_env):
    user_id = make_user("prof@csumb.edu")
    headers = auth_header(client, "prof@csumb.edu")
    client.put("/api/me/api-key", json={"api_key": "sk-proj-abcdefghijklmnopqrstuvwxyz1234WXYZ"}, headers=headers)
    with db_session() as db:
        db.get(User, user_id).credit_mode = CreditMode.OWN_KEY
        db.commit()
    wait_for(client, headers, upload(client, headers, course="Chemistry 110").json()["job_id"])
    assert PIPELINE_CALLS[-1]["api_key"] == "sk-proj-abcdefghijklmnopqrstuvwxyz1234WXYZ"
    assert client.get("/api/reports", headers=headers).json()[0]["course"] == "Chemistry 110"
    with db_session() as db:
        assert db.query(UsageLog).one().cost_usd == 0  # own key costs the lab nothing


def test_capped_professor_is_refused_before_anything_is_stored(client, db_session, make_user, analysis_env):
    user_id = make_user("prof@csumb.edu")
    with db_session() as db:
        db.add(UsageLog(user_id=user_id, cost_usd=25.0))
        db.commit()
    response = upload(client, auth_header(client, "prof@csumb.edu"))
    assert response.status_code == 402
    assert not PIPELINE_CALLS
    with db_session() as db:
        assert db.query(Upload).count() == 0


def test_professors_cannot_pick_the_local_model(client, make_user, analysis_env):
    make_user("prof@csumb.edu")
    response = client.post("/api/analyses", files={"file": ("a.pdf", b"x")}, data={"model_choice": "local"},
                           headers=auth_header(client, "prof@csumb.edu"))
    assert response.status_code == 403


def test_bad_files_are_rejected(client, make_user, analysis_env, monkeypatch):
    make_user("prof@csumb.edu")
    headers = auth_header(client, "prof@csumb.edu")
    assert upload(client, headers, name="notes.txt").status_code == 400
    monkeypatch.setattr(config, "MAX_UPLOAD_MB", 0)
    assert upload(client, headers).status_code == 413


def test_files_without_comments_fail_with_the_extractor_warning(client, make_user, analysis_env):
    analysis_env["payload"] = {"responses": [], "warnings": ["This PDF has almost no text layer (it may be a scan)."]}
    make_user("prof@csumb.edu")
    headers = auth_header(client, "prof@csumb.edu")
    job = wait_for(client, headers, upload(client, headers).json()["job_id"])
    assert job["status"] == "failed" and "scan" in job["error"]
    assert client.get("/api/reports", headers=headers).json() == []


def test_rejected_own_key_fails_the_job_with_a_clear_message(client, db_session, make_user, analysis_env, monkeypatch):
    user_id = make_user("prof@csumb.edu")
    import credits
    monkeypatch.setattr(analysis.credits, "record_usage", credits.record_usage)
    original = credits.plan_run

    def plan_with_bad_key(db, user, model_choice):
        plan = original(db, user, model_choice)
        plan.api_key = "sk-bad"
        return plan

    import app as app_module
    monkeypatch.setattr(app_module, "plan_run", plan_with_bad_key)
    headers = auth_header(client, "prof@csumb.edu")
    job = wait_for(client, headers, upload(client, headers).json()["job_id"])
    assert job["status"] == "failed" and "rejected" in job["error"]


def test_saving_an_edited_report_updates_the_score(client, make_user, analysis_env):
    make_user("prof@csumb.edu")
    headers = auth_header(client, "prof@csumb.edu")
    wait_for(client, headers, upload(client, headers).json()["job_id"])
    report_id = client.get("/api/reports", headers=headers).json()[0]["id"]
    edited = client.get(f"/api/reports/{report_id}", headers=headers).json()["report"]
    edited["overall_score"] = 3.9
    edited["categories"][0]["comments"][0]["ignored"] = True
    assert client.put(f"/api/reports/{report_id}", json={"report": edited}, headers=headers).status_code == 200
    saved = client.get(f"/api/reports/{report_id}", headers=headers).json()["report"]
    assert saved["categories"][0]["comments"][0]["ignored"] is True
    assert client.get("/api/reports", headers=headers).json()[0]["overall_score"] == 3.9
    assert client.put(f"/api/reports/{report_id}", json={"report": {"nope": 1}}, headers=headers).status_code == 400


def test_deleting_a_report_removes_the_file_but_keeps_the_spending_record(client, db_session, make_user, analysis_env):
    make_user("prof@csumb.edu")
    headers = auth_header(client, "prof@csumb.edu")
    wait_for(client, headers, upload(client, headers).json()["job_id"])
    report_id = client.get("/api/reports", headers=headers).json()[0]["id"]
    with db_session() as db:
        stored_path = db.query(Upload).one().stored_path
    assert client.delete(f"/api/reports/{report_id}", headers=headers).status_code == 204
    assert client.get("/api/reports", headers=headers).json() == []
    import os
    assert not os.path.exists(stored_path)
    with db_session() as db:
        assert db.query(Report).count() == 0 and db.query(Upload).count() == 0
        assert db.query(UsageLog).one().cost_usd == 0.5


def test_admin_sees_report_counts_but_not_contents(client, make_user, analysis_env):
    make_user("prof@csumb.edu")
    make_user("admin@csumb.edu", role=Role.ADMIN)
    prof = auth_header(client, "prof@csumb.edu")
    wait_for(client, prof, upload(client, prof).json()["job_id"])
    users = client.get("/api/admin/users", headers=auth_header(client, "admin@csumb.edu")).json()
    assert {u["email"]: u["report_count"] for u in users} == {"prof@csumb.edu": 1, "admin@csumb.edu": 0}
