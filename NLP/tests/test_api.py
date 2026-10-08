"""API tests. Every path (uploads, results, history) is redirected to a temp folder,
so the real saved_inputs/, saved_results/ and history.json are never touched."""
import json

import pytest
from fastapi.testclient import TestClient

import api


class FakeOCRResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


@pytest.fixture
def client(tmp_path, monkeypatch, fake_llm):
    monkeypatch.setattr(api, "INPUT_DIR", tmp_path / "inputs")
    monkeypatch.setattr(api, "RESULT_DIR", tmp_path / "results")
    monkeypatch.setattr(api, "HISTORY_FILE", tmp_path / "history.json")
    (tmp_path / "inputs").mkdir()
    (tmp_path / "results").mkdir()
    return TestClient(api.app)


def fake_ocr(monkeypatch, payload):
    monkeypatch.setattr(api.requests, "post", lambda *args, **kwargs: FakeOCRResponse(payload))


def test_analyze_uses_whole_responses_and_rating_tables(client, monkeypatch, tmp_path):
    fake_ocr(monkeypatch, {
        "parser": "tabular-export",
        "warnings": [],
        "quantitative": [{"question": "Overall", "n": 3, "mean": 4.0, "distribution": {"4": 3}}],
        "responses": [
            {"question": "What helped?", "text": "Explanations were clear. Lectures were great too.", "non_teaching_question": False},
        ],
        "extracted_text": "ignored",
    })
    response = client.post("/api/analyze", files={"file": ("CHEM_1_F25.xlsx", b"x")}, data={"model_choice": "openai"})
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["metadata"]["processed_comments"] == 1
    assert data["quantitative"][0]["mean"] == 4.0
    assert (tmp_path / "results" / "CHEM_1_F25_COMBINED_REPORT.json").exists()
    history = json.loads((tmp_path / "history.json").read_text())
    assert history[-1]["status"] == "Success"


def test_analyze_returns_422_when_no_comments(client, monkeypatch, tmp_path):
    fake_ocr(monkeypatch, {"parser": "pdf", "warnings": ["No written student comments were found in this file."],
                           "quantitative": [], "responses": [], "extracted_text": ""})
    response = client.post("/api/analyze", files={"file": ("scan.pdf", b"x")}, data={"model_choice": "openai"})
    assert response.status_code == 422
    assert "No written student comments" in response.json()["detail"]
    history = json.loads((tmp_path / "history.json").read_text())
    assert history[-1]["status"].startswith("No comments")


def test_legacy_ocr_text_still_works(client, monkeypatch):
    fake_ocr(monkeypatch, {"extracted_text": "Explanations were very clear.\n\nshort"})
    response = client.post("/api/analyze", files={"file": ("old.pdf", b"x")}, data={"model_choice": "openai"})
    assert response.status_code == 200
    assert response.json()["data"]["metadata"]["processed_comments"] == 1


def ok_ocr(monkeypatch):
    fake_ocr(monkeypatch, {"parser": "pdf", "warnings": [], "quantitative": [],
                           "responses": [{"question": None, "text": "Explanations were clear.", "non_teaching_question": False}]})


def test_upload_name_cannot_escape_inputs_folder(client, monkeypatch, tmp_path):
    ok_ocr(monkeypatch)
    response = client.post("/api/analyze", files={"file": ("../../evil.pdf", b"x")}, data={"model_choice": "openai"})
    assert response.status_code == 200
    assert (tmp_path / "inputs" / "evil.pdf").exists()
    assert not (tmp_path / "evil.pdf").exists()


def test_download_rejects_path_traversal(client):
    assert client.get("/api/download/..%2F..%2Fhistory").status_code in (400, 404)
    assert client.post("/api/download-zip", json={"course_ids": ["../secret"]}).status_code == 400


def test_bad_model_choice_is_rejected(client):
    response = client.post("/api/analyze", files={"file": ("a.pdf", b"x")}, data={"model_choice": "gpt-unknown"})
    assert response.status_code == 400


def test_reupload_archives_previous_report(client, monkeypatch, tmp_path):
    ok_ocr(monkeypatch)
    for _ in range(2):
        assert client.post("/api/analyze", files={"file": ("COURSE.pdf", b"x")}, data={"model_choice": "openai"}).status_code == 200
    archived = list((tmp_path / "results" / "archive").glob("COURSE_*_COMBINED_REPORT.json"))
    assert len(archived) == 1
    assert (tmp_path / "results" / "COURSE_COMBINED_REPORT.json").exists()


def test_zip_download_streams_reports(client, monkeypatch):
    ok_ocr(monkeypatch)
    client.post("/api/analyze", files={"file": ("ZIPME.pdf", b"x")}, data={"model_choice": "openai"})
    response = client.post("/api/download-zip", json={"course_ids": ["ZIPME"]})
    assert response.status_code == 200
    import io, zipfile
    assert zipfile.ZipFile(io.BytesIO(response.content)).namelist() == ["ZIPME_Evaluation_Data.json"]


def test_api_key_is_enforced_when_configured(client, monkeypatch):
    monkeypatch.setattr(api.settings, "API_KEY", "secret")
    assert client.get("/api/history").status_code == 401
    assert client.get("/api/history", headers={"X-API-Key": "secret"}).status_code == 200


def test_jobs_report_progress_until_complete(client, monkeypatch):
    import time
    ok_ocr(monkeypatch)
    job_id = client.post("/api/jobs", files={"file": ("JOB.pdf", b"x")}, data={"model_choice": "openai"}).json()["job_id"]
    for _ in range(100):
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] in ("complete", "failed"):
            break
        time.sleep(0.05)
    assert job["status"] == "complete", job
    assert job["overall_score"] == 5
    assert client.get("/api/jobs/unknown").status_code == 404
