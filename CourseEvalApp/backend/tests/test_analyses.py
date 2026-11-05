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
    monkeypatch.setattr(analysis, "_jobs", {})
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


class HeldRunner:
    """Stands in for the worker so jobs stay queued until a test runs them."""

    def __init__(self):
        self.calls = []

    def submit(self, fn, *args):
        self.calls.append((fn, args))


def test_capped_professor_can_queue_only_one_lab_credit_job(client, db_session, make_user, analysis_env, monkeypatch):
    make_user("prof@csumb.edu")
    make_user("other@csumb.edu")
    runner = HeldRunner()
    monkeypatch.setattr(analysis, "_runner", runner)
    headers = auth_header(client, "prof@csumb.edu")
    assert upload(client, headers).status_code == 202
    second = upload(client, headers)
    assert second.status_code == 429 and "already have an analysis" in second.json()["detail"]
    with db_session() as db:
        assert db.query(Upload).count() == 1  # the refused upload is not stored
    assert upload(client, auth_header(client, "other@csumb.edu")).status_code == 202  # the limit is per professor
    fn, args = runner.calls[0]
    fn(*args)  # first job finishes, so the professor may upload again
    assert upload(client, headers).status_code == 202


def test_queued_job_is_refused_when_the_cap_is_reached_before_it_starts(client, db_session, make_user, analysis_env, monkeypatch):
    user_id = make_user("prof@csumb.edu")
    runner = HeldRunner()
    monkeypatch.setattr(analysis, "_runner", runner)
    headers = auth_header(client, "prof@csumb.edu")
    job_id = upload(client, headers).json()["job_id"]
    with db_session() as db:
        db.add(UsageLog(user_id=user_id, cost_usd=25.0))  # spend recorded while the job waited
        db.commit()
    fn, args = runner.calls[0]
    fn(*args)
    job = client.get(f"/api/analyses/{job_id}", headers=headers).json()
    assert job["status"] == "failed" and "AI credit" in job["error"]
    assert not PIPELINE_CALLS


def test_own_key_professors_can_queue_several_jobs(client, db_session, make_user, analysis_env, monkeypatch):
    user_id = make_user("prof@csumb.edu")
    monkeypatch.setattr(analysis, "_runner", HeldRunner())
    headers = auth_header(client, "prof@csumb.edu")
    client.put("/api/me/api-key", json={"api_key": "sk-proj-abcdefghijklmnopqrstuvwxyz1234WXYZ"}, headers=headers)
    with db_session() as db:
        db.get(User, user_id).credit_mode = CreditMode.OWN_KEY
        db.commit()
    assert upload(client, headers).status_code == 202
    assert upload(client, headers).status_code == 202


def test_failed_upload_storage_releases_the_reserved_slot(client, make_user, analysis_env, monkeypatch):
    make_user("prof@csumb.edu")
    monkeypatch.setattr(analysis, "_runner", HeldRunner())
    real_store = analysis.store_upload

    def broken_store(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(analysis, "store_upload", broken_store)
    headers = auth_header(client, "prof@csumb.edu")
    with pytest.raises(OSError):
        upload(client, headers)
    assert analysis._jobs == {}
    monkeypatch.setattr(analysis, "store_upload", real_store)
    assert upload(client, headers).status_code == 202


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


def test_each_professor_may_have_two_active_jobs(client, db_session, make_user, analysis_env, monkeypatch):
    user_id = make_user("prof@csumb.edu")
    monkeypatch.setattr(analysis, "_runner", HeldRunner())
    headers = auth_header(client, "prof@csumb.edu")
    client.put("/api/me/api-key", json={"api_key": "sk-proj-abcdefghijklmnopqrstuvwxyz1234WXYZ"}, headers=headers)
    with db_session() as db:
        db.get(User, user_id).credit_mode = CreditMode.OWN_KEY
        db.commit()
    assert upload(client, headers).status_code == 202
    assert upload(client, headers).status_code == 202
    third = upload(client, headers)
    assert third.status_code == 429 and "2 analyses" in third.json()["detail"]


def test_the_whole_queue_has_a_limit(client, make_user, analysis_env, monkeypatch):
    monkeypatch.setattr(analysis, "_runner", HeldRunner())
    monkeypatch.setattr(analysis, "MAX_ACTIVE_JOBS_TOTAL", 1)
    make_user("a@csumb.edu")
    make_user("b@csumb.edu")
    assert upload(client, auth_header(client, "a@csumb.edu")).status_code == 202
    refused = upload(client, auth_header(client, "b@csumb.edu"))
    assert refused.status_code == 429 and "queue is full" in refused.json()["detail"]


def test_files_with_too_many_comments_are_refused_before_the_ai_runs(client, make_user, analysis_env, monkeypatch):
    make_user("prof@csumb.edu")
    monkeypatch.setattr(analysis, "MAX_COMMENTS_PER_ANALYSIS", 2)
    analysis_env["payload"]["responses"] = [{"text": f"Comment {i}", "question": None, "non_teaching_question": False} for i in range(3)]
    headers = auth_header(client, "prof@csumb.edu")
    job = wait_for(client, headers, upload(client, headers).json()["job_id"])
    assert job["status"] == "failed" and "split it" in job["error"]
    assert not PIPELINE_CALLS


def test_old_finished_jobs_are_forgotten(client, make_user, analysis_env):
    from datetime import datetime, timedelta, timezone
    make_user("prof@csumb.edu")
    old = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat(timespec="seconds")
    analysis._jobs["old"] = {"job_id": "old", "owner_id": 999, "status": "complete", "created": old, "lab_credit": False}
    analysis._jobs["stuck"] = {"job_id": "stuck", "owner_id": 999, "status": "running", "created": old, "lab_credit": False}
    headers = auth_header(client, "prof@csumb.edu")
    wait_for(client, headers, upload(client, headers).json()["job_id"])
    assert "old" not in analysis._jobs and "stuck" in analysis._jobs  # running jobs are never dropped


def test_uploads_without_a_valid_token_are_refused_before_the_body_is_read(client, make_user, analysis_env, monkeypatch):
    read = []
    real_store = analysis.store_upload
    monkeypatch.setattr(analysis, "store_upload", lambda *a, **k: read.append(1) or real_store(*a, **k))
    no_token = client.post("/api/analyses", files={"file": ("a.pdf", b"%PDF fake")}, data={"model_choice": "openai"})
    assert no_token.status_code == 401
    forged = client.post("/api/analyses", files={"file": ("a.pdf", b"%PDF fake")}, data={"model_choice": "openai"},
                         headers={"Authorization": "Bearer not.a.token"})
    assert forged.status_code == 401
    assert not read and not PIPELINE_CALLS


def test_oversized_bodies_are_refused_without_reading_them(client, make_user, analysis_env, monkeypatch):
    import limits
    make_user("prof@csumb.edu")
    headers = auth_header(client, "prof@csumb.edu")
    monkeypatch.setattr(config, "MAX_UPLOAD_MB", 1)
    big = b"%PDF" + b"x" * (3 * 1024 * 1024)
    declared = client.post("/api/analyses", files={"file": ("a.pdf", big)}, data={"model_choice": "openai"}, headers=headers)
    assert declared.status_code == 413 and "1 MB" in declared.json()["detail"]

    def chunks():  # no Content-Length: the limit is enforced while reading
        for _ in range(40):
            yield b"x" * (128 * 1024)

    streamed = client.post("/api/analyses", content=chunks(),
                           headers={**headers, "Content-Type": "multipart/form-data; boundary=zzz"})
    assert streamed.status_code == 413

    monkeypatch.setattr(limits, "MAX_JSON_BODY_BYTES", 1000)
    too_big_json = client.put("/api/reports/1", json={"report": {"notes": "x" * 2000}}, headers=headers)
    assert too_big_json.status_code == 413
    assert not PIPELINE_CALLS


def test_failed_jobs_remove_their_uploaded_file(client, db_session, make_user, analysis_env):
    make_user("prof@csumb.edu")
    analysis_env["payload"] = {"parser": "pdf", "warnings": ["scan"], "quantitative": [], "responses": []}
    headers = auth_header(client, "prof@csumb.edu")
    job = wait_for(client, headers, upload(client, headers).json()["job_id"])
    assert job["status"] == "failed"
    with db_session() as db:
        assert db.query(Upload).count() == 0
    assert not any(p.is_file() for p in (config.STORAGE_DIR / "uploads").rglob("*"))


def test_each_professor_has_a_storage_quota(client, db_session, make_user, analysis_env, monkeypatch):
    user_id = make_user("prof@csumb.edu")
    monkeypatch.setattr(config, "USER_STORAGE_QUOTA_MB", 1)
    with db_session() as db:
        db.add(Upload(owner_id=user_id, original_filename="old.pdf", stored_path="x", size_bytes=1024 * 1024))
        db.commit()
    response = upload(client, auth_header(client, "prof@csumb.edu"))
    assert response.status_code == 413 and "limit" in response.json()["detail"]
    assert analysis._jobs == {}  # the reserved slot was released
    with db_session() as db:
        assert db.query(Upload).count() == 1


def test_very_long_file_names_are_shortened(client, db_session, make_user, analysis_env):
    make_user("prof@csumb.edu")
    headers = auth_header(client, "prof@csumb.edu")
    job = wait_for(client, headers, upload(client, headers, name="A" * 400 + ".pdf").json()["job_id"])
    assert job["status"] == "complete"
    with db_session() as db:
        name = db.query(Upload).one().original_filename
    assert len(name) == config.MAX_FILENAME_CHARS and name.endswith(".pdf")
